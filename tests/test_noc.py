import json
import os
from pathlib import Path
from dataclasses import replace
import queue
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from PIL import Image

from noc.interface import NOCFlow
from noc.incidentes import CAMPOS_FORMULARIO as CAMPOS
from noc.configuracao import Config, carregar_config, diretorio_aplicacao
from noc.comunicados import gerar_html, validar_dados
from noc.rascunhos import RascunhoWorker


def dados_incidente(**valores):
    dados = dict.fromkeys(CAMPOS, "")
    dados.update(alerta="CPU alta", servidor="host-01", ticket="123")
    dados.update(valores)
    return dados


class ExecutavelTests(unittest.TestCase):
    def test_configuracao_fica_fora_do_pacote_e_sobrevive_a_atualizacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            pacote = raiz / "_internal"
            pacote.mkdir()
            (pacote / ".env.example").write_text("GEMINI_API_KEY=exemplo\n", encoding="utf-8")
            with patch.dict(os.environ, {"LOCALAPPDATA": str(raiz / "usuario")}), patch("sys.frozen", True, create=True), patch("sys._MEIPASS", str(pacote), create=True):
                destino = diretorio_aplicacao()
                self.assertEqual(destino, raiz / "usuario" / "NOCFlow")
                arquivo = destino / ".env"
                self.assertEqual(arquivo.read_text(encoding="utf-8"), "GEMINI_API_KEY=exemplo\n")
                arquivo.write_text("GEMINI_API_KEY=configuracao_do_usuario\n", encoding="utf-8")
                (pacote / ".env.example").write_text("OUTRO_PADRAO=1\n", encoding="utf-8")
                self.assertEqual(diretorio_aplicacao(), destino)
                self.assertEqual(arquivo.read_text(encoding="utf-8"), "GEMINI_API_KEY=configuracao_do_usuario\n")


class DadosTests(unittest.TestCase):
    def test_validacao_depende_da_etapa(self):
        dados = dados_incidente(ticket="")
        self.assertEqual(validar_dados(dados, "Movidesk"), {})
        self.assertIn("ticket", validar_dados(dados, "Teams"))
        self.assertIn("ticket", validar_dados(dados_incidente(ticket="123/456"), "Teams"))
        self.assertIn("link_zabbix", validar_dados(dados_incidente(link_zabbix="javascript:alert(1)"), "Movidesk"))

    def test_html_preserva_texto_sem_injetar_marcacao(self):
        html = gerar_html(dados_incidente(alerta='<script>alert("x")</script>', horario="10:42", situacao="valor < 5 & > 1"))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("10:42", html)
        self.assertIn("&amp;", html)
        com_imagem = gerar_html(
            dados_incidente(link_zabbix="https://zabbix.example.com/tr_events.php?triggerid=1&eventid=2"),
            Image.new("RGB", (4, 4), "orange"),
        )
        self.assertIn("data:image/png;base64,", com_imagem)
        self.assertIn('href="https://zabbix.example.com/tr_events.php?triggerid=1&amp;eventid=2"', com_imagem)


class RascunhoTests(unittest.TestCase):
    def test_ultimo_snapshot_recupera_campos_e_imagem(self):
        with tempfile.TemporaryDirectory() as pasta:
            config = Config(Path(pasta))
            eventos = queue.Queue()
            worker = RascunhoWorker(config, eventos)
            worker.start()
            self.assertEqual(eventos.get(timeout=3)[0], "rascunho_carregado")
            imagem = Image.new("RGB", (16, 12), "red")
            worker.comandos.put((1, dados_incidente(ticket="123"), imagem))
            worker.comandos.put((2, dados_incidente(ticket="456"), imagem))
            worker.comandos.put(None)
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            dados, recuperada = RascunhoWorker(config, eventos).carregar()
            self.assertEqual(dados["ticket"], "456")
            self.assertEqual(recuperada.getpixel((0, 0)), (255, 0, 0))
            self.assertFalse((config.dados_dir / "rascunho.tmp").exists())

    def test_novo_incidente_remove_tambem_imagem_do_rascunho(self):
        with tempfile.TemporaryDirectory() as pasta:
            config = Config(Path(pasta))
            worker = RascunhoWorker(config, queue.Queue())
            worker.start()
            worker.comandos.put((1, dados_incidente(), Image.new("RGB", (2, 2))))
            worker.comandos.put((2, dict.fromkeys(CAMPOS, ""), None))
            worker.comandos.put(None)
            worker.join(timeout=5)
            dados, imagem = worker.carregar()
            self.assertFalse(any(dados.values()))
            self.assertIsNone(imagem)

    def test_rascunho_corrompido_e_preservado_antes_de_nova_gravacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            config = Config(Path(pasta))
            config.dados_dir.mkdir()
            arquivo = config.dados_dir / "rascunho.json"
            arquivo.write_text("JSON interrompido", encoding="utf-8")
            eventos = queue.Queue()
            worker = RascunhoWorker(config, eventos)
            with self.assertLogs("noc", level="ERROR"):
                worker.start()
                self.assertEqual(eventos.get(timeout=3)[0], "rascunho_erro_carga")
            worker.comandos.put((1, dados_incidente(), None))
            worker.comandos.put(None)
            worker.join(timeout=5)
            backups = list(config.dados_dir.glob("rascunho-invalido-*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "JSON interrompido")
            self.assertEqual(json.loads(arquivo.read_text(encoding="utf-8"))["dados"]["ticket"], "123")


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = NOCFlow(self.root, Config(Path(self.pasta.name), api_key="teste"))
        self.aguardar(lambda: not self.app.carregando)

    def aguardar(self, predicado, timeout=5):
        limite = time.monotonic() + timeout
        while not predicado() and time.monotonic() < limite:
            self.root.update()
            time.sleep(0.005)
        self.assertTrue(predicado(), "A interface não concluiu a operação no prazo do teste")

    def tearDown(self):
        self.app.fechar()
        self.aguardar(lambda: not self.app.movidesk.is_alive() and not self.app.rascunho.is_alive())
        if self.app.poll_after:
            self.root.after_cancel(self.app.poll_after)
        if self.root.tk.call("info", "commands", "."):
            self.root.destroy()
        self.pasta.cleanup()

    def test_ia_lenta_mantem_event_loop_e_impede_disparo_duplicado(self):
        liberar = threading.Event()
        iniciou = threading.Event()
        threads = []

        def ia_lenta(*_, **kwargs):
            threads.append(threading.get_ident())
            iniciou.set()
            if not liberar.wait(5):
                raise TimeoutError("Teste excedeu o prazo")
            return {"alerta": "Disco cheio", "servidor": "host-02", "severidade": "Alta", "situacao": "95%", "horario": "12:30"}

        self.app.definir_dados(dados_incidente(link_zabbix="https://zabbix.test/event/1", acionamento="Equipe antiga"))
        self.app.definir_imagem(Image.new("RGB", (10, 10)))
        heartbeat = []
        try:
            with patch("noc.interface.extrair_dados", side_effect=ia_lenta) as mock_ia:
                self.app.extrair_com_ia()
                self.app.extrair_com_ia()
                self.root.after(10, lambda: heartbeat.append(True))
                self.aguardar(lambda: iniciou.is_set() and bool(heartbeat))
                self.assertIsNotNone(self.app.operacao)
                self.assertEqual(mock_ia.call_count, 1)
                self.assertNotEqual(threads[0], threading.get_ident())
                self.assertEqual(str(self.app.btn_ler_print["state"]), "disabled")
                liberar.set()
                self.aguardar(lambda: self.app.operacao is None)
        finally:
            liberar.set()
        dados = self.app.obter_dados()
        self.assertEqual(dados["alerta"], "Disco cheio")
        self.assertEqual(dados["situacao"], "95%")
        self.assertEqual(dados["ticket"], "")
        self.assertEqual(dados["link_zabbix"], "")
        self.assertEqual(dados["acionamento"], "")

    def test_falha_ia_libera_controles_e_preserva_print(self):
        imagem = Image.new("RGB", (10, 10), "blue")
        with patch("noc.interface.ImageGrab.grabclipboard", return_value=imagem), patch("noc.interface.extrair_dados", side_effect=TimeoutError("Tempo excedido")), self.assertLogs("noc", level="ERROR"):
            self.app.extrair_com_ia()
            self.aguardar(lambda: self.app.operacao is None)
        self.assertIn("Tempo excedido", self.app.status.get())
        self.assertIsNotNone(self.app.imagem)
        self.assertEqual(str(self.app.btn_ler_print["state"]), "normal")

    def test_ler_print_usa_nova_captura_sem_misturar_evidencias_ou_campos(self):
        anterior = Image.new("RGB", (10, 10), "red")
        nova = Image.new("RGB", (12, 12), "blue")
        self.app.definir_dados(dados_incidente(severidade="Alta", horario="10:42"))
        self.app.definir_imagem(anterior)
        primeiro = self.app.fila.ativo
        with patch("noc.interface.ImageGrab.grabclipboard", return_value=nova) as clipboard, \
                patch("noc.ocr_windows.extrair_texto", return_value="Host: host-02\nTrigger: Disco cheio"):
            self.app.ler_print()
            self.aguardar(lambda: self.app.operacao is None)
        clipboard.assert_called_once()
        self.assertNotEqual(self.app.fila.ativo, primeiro)
        self.assertIs(self.app.fila.obter(primeiro)["imagem"], anterior)
        self.assertEqual(self.app.fila.obter(primeiro)["dados"]["ticket"], "123")
        self.assertEqual(self.app.imagem.getpixel((0, 0)), (0, 0, 255))
        self.assertEqual(self.app.obter_dados()["servidor"], "host-02")
        for campo in ("ticket", "severidade", "horario"):
            self.assertEqual(self.app.obter_dados()[campo], "")

    def test_reler_print_guardado_independe_do_clipboard(self):
        imagem = Image.new("RGB", (10, 10), "red")
        self.app.definir_imagem(imagem)
        with patch("noc.interface.ImageGrab.grabclipboard") as clipboard, \
                patch("noc.ocr_windows.extrair_texto", return_value="Host: host-01"):
            self.app.extrair_com_ia(False)
            self.aguardar(lambda: self.app.operacao is None)
        clipboard.assert_not_called()
        self.assertIs(self.app.imagem, imagem)

    def test_interface_mostra_groq_apos_ocr_incompleto(self):
        from google.api_core.exceptions import ServiceUnavailable

        self.app.config = replace(self.app.config, groq_api_key="groq-teste")
        self.app.definir_imagem(Image.new("RGB", (10, 10)))
        resposta = json.dumps({"alerta": "CPU alta", "servidor": "host-01", "severidade": "Alta", "situacao": "95%", "horario": "10:42"})
        with patch("noc.extracao.consultar_gemini", side_effect=ServiceUnavailable("alta demanda")), patch("noc.ocr_windows.extrair_texto", return_value="CPU alta host-01"), patch("noc.extracao.consultar_groq", return_value=resposta):
            self.app.extrair_com_ia()
            self.aguardar(lambda: self.app.operacao is None)
        self.assertIn("Groq", self.app.status.get())
        self.assertIn("OCR local", self.app.status.get())
        self.assertEqual(self.app.obter_dados()["servidor"], "host-01")
        self.assertEqual(str(self.app.btn_ler_print["state"]), "normal")

    def test_novo_incidente_e_desfazer_restauram_print_e_dados(self):
        dados = dados_incidente()
        imagem = Image.new("RGB", (10, 10))
        self.app.definir_dados(dados)
        self.app.definir_imagem(imagem)
        self.app.novo_incidente()
        self.assertFalse(any(self.app.obter_dados().values()))
        self.assertIsNone(self.app.imagem)
        self.app.desfazer_novo()
        self.assertEqual(self.app.obter_dados(), dados)
        self.assertIs(self.app.imagem, imagem)

    def test_retorno_ticket_atualiza_incidente_original_apos_trocar_fila(self):
        from noc.incidentes import importar_eventos
        eventos = [{"eventid": str(i), "alerta": "CPU alta", "servidor": "host-01", "link_zabbix": f"https://zabbix.test/tr_events.php?eventid={i}"} for i in (10, 11)]
        self.app.aplicar_importacao(importar_eventos({"versao": 1, "origem": "zabbix", "eventos": eventos}))
        primeiro = self.app.fila.ativo
        self.app.seletor_fila.current(1)
        self.app.selecionar_incidente()
        segundo = self.app.fila.ativo
        self.app.vars["situacao"].set("99%")
        self.app.eventos.put(("ticket_recebido", primeiro, {"ticket": "456", "url": "https://empresa.movidesk.com/Ticket/Edit/456"}))
        self.aguardar(lambda: self.app.fila.obter(primeiro)["dados"]["ticket"] == "456")
        self.assertEqual(self.app.fila.ativo, segundo)
        self.assertEqual(self.app.obter_dados()["ticket"], "")
        self.assertEqual(self.app.obter_dados()["situacao"], "99%")
        self.app.seletor_fila.current(0)
        self.app.selecionar_incidente()
        self.assertEqual(self.app.obter_dados()["ticket"], "456")

    def test_importacao_externa_aguarda_operacao_sem_sobrescrever_campos(self):
        from noc.incidentes import importar_eventos
        id_op = self.app.iniciar_operacao("ia", "Teste")
        evento = importar_eventos({"versao": 1, "origem": "zabbix", "link_zabbix": "https://zabbix.test/tr_events.php?eventid=10", "alerta": "CPU alta", "servidor": "host-01"})
        self.app.eventos.put(("zabbix_importado", None, evento))
        self.aguardar(lambda: bool(self.app.importacoes_pendentes))
        self.assertEqual(self.app.obter_dados()["servidor"], "")
        self.app.eventos.put(("erro", id_op, "Teste concluído"))
        self.aguardar(lambda: self.app.obter_dados()["servidor"] == "host-01")
        self.assertEqual(self.app.fila.obter()["meta"]["eventid"], "10")

    def test_ocr_local_sem_chaves_funciona_pela_interface(self):
        self.app.config = replace(self.app.config, api_key="", groq_api_key="")
        self.app.definir_imagem(Image.new("RGB", (10, 10)))
        with patch("noc.ocr_windows.extrair_texto", return_value="Host: local-01\nTrigger: CPU alta"), patch("noc.extracao.consultar_gemini") as gemini, patch("noc.extracao.consultar_groq") as groq:
            self.app.extrair_com_ia(False)
            self.aguardar(lambda: self.app.operacao is None)
            self.assertEqual(self.app.obter_dados()["servidor"], "local-01")
            gemini.assert_not_called()
            groq.assert_not_called()

    def test_evento_consumo_nao_encerra_operacao_e_atualiza_painel(self):
        identificador = self.app.iniciar_operacao("ia", "Analisando")
        dados = {"provedor": "Groq", "horario": "10:42:00", "entrada": 100, "saida": 50, "total": 150, "cotas": {}}
        self.app.mostrar_tokens()
        self.app.eventos.put(("ia_consumo", identificador, dados))
        self.aguardar(lambda: "Total: 150" in self.app.resumo_tokens.get())
        self.assertIsNotNone(self.app.operacao)
        self.app.eventos.put(("erro", identificador, "Resposta truncada"))
        self.aguardar(lambda: self.app.operacao is None)
        self.assertIn("Total: 150", self.app.resumo_tokens.get())

    def test_assunto_email_atualiza_e_valida_ticket_antes_de_copiar(self):
        self.app.definir_dados(dados_incidente())
        self.assertEqual(self.app.assunto_email.get(), "123 - CPU alta - host-01")
        self.app.vars["ticket"].set("456")
        with patch("noc.interface.pyperclip.copy") as copiar:
            self.app.copiar_assunto_email()
            copiar.assert_called_once_with("456 - CPU alta - host-01")
        self.app.vars["ticket"].set("")
        with patch("noc.interface.pyperclip.copy") as copiar:
            self.app.copiar_assunto_email()
            copiar.assert_not_called()
        self.assertIn("Preencha", self.app.erros["ticket"].get())

    def test_nome_salvo_e_reutilizado_apos_novo_incidente_e_reinicio(self):
        arquivo = Path(self.pasta.name) / ".env"
        configuracao_original = "# Configuração do operador\nGEMINI_API_KEY='teste-preservado'\nMOVIDESK_URL=https://empresa.movidesk.com\n"
        arquivo.write_text(configuracao_original + "NOME_OPERADOR=Anterior\n", encoding="utf-8")
        self.app.definir_dados(dados_incidente())
        self.app.nome_operador.set("  João   D'Ávila  ")
        self.assertEqual(self.app.previa.get("1.0", "1.end"), "João D'Ávila - Equipe NOC")
        self.app.btn_salvar_nome.invoke()
        self.assertIn("Nome salvo", self.app.status.get())
        self.assertIn(configuracao_original, arquivo.read_text(encoding="utf-8"))
        self.app.novo_incidente()
        self.assertEqual(self.app.nome_operador.get(), "João D'Ávila")
        self.assertNotIn("nome_operador", self.app.obter_dados())

        self.app.fechar()
        self.aguardar(lambda: not self.root.tk.call("info", "commands", "."))
        with patch.dict(os.environ, {}, clear=True):
            config = carregar_config(Path(self.pasta.name))
        self.assertEqual(config.nome_operador, "João D'Ávila")
        self.assertEqual(config.api_key, "teste-preservado")
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = NOCFlow(self.root, config)
        self.aguardar(lambda: not self.app.carregando)
        self.assertEqual(self.app.nome_operador.get(), "João D'Ávila")
        self.app.definir_dados(dados_incidente())
        with patch("noc.interface.pyperclip.copy") as copiar:
            self.app.copiar_comunicado("WhatsApp")
            self.assertEqual(copiar.call_args.args[0].splitlines()[0], "João D'Ávila - Equipe NOC")
        self.app.nome_operador.set("")
        self.app.btn_salvar_nome.invoke()
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(carregar_config(Path(self.pasta.name)).nome_operador, "")
        self.assertEqual(self.app.previa.get("1.0", "1.end"), "Equipe NOC")

    def test_copia_recortes_em_worker_e_novo_print_limpa_selecoes(self):
        imagem = Image.new("RGB", (100, 100), "blue")
        self.app.definir_imagem(imagem)
        self.app.recortes_email = {"Host": (0, 0, 50, 10), "Trigger": (0, 20, 80, 30), "Severity": (0, 40, 30, 50)}
        self.app.atualizar_controles()
        recebidas = []
        def copiar(recorte, hwnd):
            recebidas.append((recorte.size, threading.get_ident()))
        with patch("noc.interface.copiar_imagem", side_effect=copiar):
            self.app.copiar_imagem_email()
            self.aguardar(lambda: self.app.operacao is None)
        self.assertEqual(recebidas[0][0], (80, 42))
        self.assertNotEqual(recebidas[0][1], threading.get_ident())
        self.assertIs(self.app.imagem, imagem)
        self.assertIn("Recorte copiado", self.app.status.get())
        self.app.definir_imagem(Image.new("RGB", (50, 50)))
        self.assertEqual(self.app.recortes_email, {})
        self.assertEqual(str(self.app.btn_imagem_email["state"]), "disabled")

    def test_receber_evento_mantem_contexto_e_reimportar_preserva_edicao(self):
        from noc.incidentes import importar_eventos
        def evento(numero, **campos):
            return importar_eventos({"versao": 1, "origem": "zabbix", "alerta": "CPU", "servidor": "host",
                                     "situacao": "CPU 95%", "link_zabbix": f"https://zabbix.test/tr_events.php?eventid={numero}", **campos})
        self.app.aplicar_importacao(evento(1))
        primeiro = self.app.fila.ativo
        entrada = self.app.entradas["situacao"]
        entrada.delete("1.0", "end")
        entrada.insert("1.0", "Revisado pelo operador")
        entrada.mark_set("insert", "1.5")
        self.root.update()
        self.app.eventos.put(("zabbix_importado", None, evento(2)))
        self.aguardar(lambda: len(self.app.fila.itens) == 2)
        self.assertEqual(self.app.fila.ativo, primeiro)
        self.assertEqual(entrada.index("insert"), "1.5")
        self.app.eventos.put(("zabbix_importado", None, evento(1, situacao="CPU 99%")))
        self.aguardar(lambda: bool(self.app.fila.obter()["meta"].get("atualizacoes")))
        self.assertEqual(self.app.obter_dados()["situacao"], "Revisado pelo operador")
        self.assertEqual(entrada.index("insert"), "1.5")
        self.assertEqual(self.app.fila.obter()["meta"]["atualizacoes"]["situacao"], "CPU 99%")
        self.app.ver_recebidos()
        self.assertNotEqual(self.app.fila.ativo, primeiro)

    def test_ticket_contextual_reabre_salvo_e_retorna_ao_pendente(self):
        self.app.definir_dados(dados_incidente())
        with patch("noc.interface.abrir_no_edge") as abrir, patch.object(self.app.movidesk.comandos, "put") as enviar:
            self.app.preencher_movidesk()
            self.aguardar(lambda: self.app.operacao is None)
            abrir.assert_called_once_with("https://empresa.movidesk.com/Ticket/Edit/123")
            enviar.assert_not_called()
            self.app.vars["ticket"].set("")
            imagem = Image.new("RGB", (100, 100))
            self.app.definir_imagem(imagem)
            self.app.recortes_email = {"Host": (0, 0, 50, 10), "Trigger": (0, 20, 80, 30), "Severity": (0, 40, 30, 50)}
            self.app.preencher_movidesk()
            self.assertIs(enviar.call_args.args[0][1]["_imagem"], imagem)
            operacao = self.app.operacao[0]
            self.app.eventos.put(("pedido_status", self.app.fila.ativo, {"estado": "aguardando", "campos": {"categoria": "pendente"}}))
            self.app.eventos.put(("movidesk_ok", operacao, None))
            self.aguardar(lambda: self.app.operacao is None)
            self.app.preencher_movidesk()
            self.assertTrue(enviar.call_args.args[0][1]["_retomar"])
            self.app.eventos.put(("retomar_ok", self.app.operacao[0], None))
            self.aguardar(lambda: self.app.operacao is None)
            self.app.fila.obter()["meta"]["pedido"] = {"estado": "erro"}
            chamadas = enviar.call_count
            self.app.preencher_movidesk()
            self.assertEqual(enviar.call_count, chamadas)
            self.app.evidencia_escolha.set("Recorte")
            self.app.escolher_evidencia()
            self.app.preencher_movidesk(novo_formulario=True)
            self.assertTrue(enviar.call_args.args[0][1]["_novo_pedido"])
            self.assertEqual(enviar.call_args.args[0][1]["_imagem"].size, (80, 42))
            self.app.eventos.put(("erro", self.app.operacao[0], "Fim da simulação"))
            self.aguardar(lambda: self.app.operacao is None)

    def test_retorno_preserva_cursor_e_acompanha_incidente_removido_ate_desfazer(self):
        self.app.definir_dados(dados_incidente(ticket="", situacao="Texto sendo revisado"))
        self.app.guardar_incidente()
        entrada = self.app.entradas["situacao"]
        entrada.mark_set("insert", "1.5")
        primeiro = self.app.fila.ativo
        self.app.eventos.put(("ticket_recebido", primeiro, {"ticket": "456", "url": "https://empresa.movidesk.com/Ticket/Edit/456"}))
        self.aguardar(lambda: self.app.vars["ticket"].get() == "456")
        self.assertEqual(entrada.index("insert"), "1.5")
        self.app.novo_incidente()
        self.app.definir_dados(dados_incidente(ticket="", servidor="outro-host"))
        segundo = self.app.fila.ativo
        self.app.remover_incidente()
        self.app.eventos.put(("ticket_recebido", segundo, {"ticket": "789", "url": "https://empresa.movidesk.com/Ticket/Edit/789"}))
        self.aguardar(lambda: self.app.incidente_do_retorno(segundo)["dados"]["ticket"] == "789")
        self.assertIsNone(self.app.fila.obter(segundo))
        self.assertEqual(self.app.fila.ativo, primeiro)
        self.assertEqual(self.app.vars["ticket"].get(), "456")
        self.app.desfazer_remocao()
        self.assertEqual(self.app.fila.ativo, segundo)
        self.assertEqual(self.app.vars["ticket"].get(), "789")

    def test_recortes_modelo_e_estado_sobrevivem_ao_reinicio(self):
        self.app.definir_dados(dados_incidente(ticket=""))
        self.app.definir_imagem(Image.new("RGB", (100, 100)))
        caixas = {"Host": (0, 0, 50, 10), "Trigger": (0, 20, 80, 30), "Severity": (0, 40, 30, 50)}
        self.app.recortes_email = caixas
        self.app.evidencia_escolha.set("Recorte")
        self.app.escolher_evidencia()
        self.app.modelo_comunicado.set("Abertura inicial")
        self.app.mudar_modelo()
        self.app.texto_atualizacao.set("Equipe investigando o alerta")
        identificador = self.app.fila.ativo
        self.app.novo_incidente()
        self.app.desfazer_novo()
        self.assertEqual(self.app.recortes_email, caixas)
        self.assertEqual(self.app.modelo_comunicado.get(), "Abertura inicial")
        self.app.fila.obter()["meta"]["pedido"] = {"estado": "aguardando", "expira": time.time() + 3600}
        self.app.fechar()
        self.aguardar(lambda: not self.root.tk.call("info", "commands", "."))
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = NOCFlow(self.root, Config(Path(self.pasta.name)))
        self.aguardar(lambda: not self.app.carregando)
        self.assertEqual(self.app.fila.ativo, identificador)
        self.assertEqual(self.app.recortes_email, caixas)
        self.assertEqual(self.app.evidencia_escolha.get(), "Recorte")
        self.assertEqual(self.app.texto_atualizacao.get(), "Equipe investigando o alerta")
        self.assertEqual(self.app.fila.obter()["meta"]["pedido"]["estado"], "interrompido")
        self.assertEqual(self.app.btn_movidesk.cget("text"), "Informar ticket")

    def test_desfazer_apos_reimportar_mantem_vinculo_do_retorno_original(self):
        from noc.incidentes import importar_eventos
        eventos = importar_eventos({"versao": 1, "origem": "zabbix", "alerta": "CPU", "servidor": "host",
                                   "link_zabbix": "https://zabbix.test/tr_events.php?eventid=1"})
        self.app.aplicar_importacao(eventos)
        original = self.app.fila.ativo
        self.app.fila.obter()["meta"]["pedido"] = {"estado": "aguardando"}
        self.app.remover_incidente()
        self.app.aplicar_importacao(eventos)
        reimportado = self.app.fila.ativo
        self.app.desfazer_remocao()
        self.assertEqual(self.app.fila.ativo, reimportado)
        self.assertEqual(len(self.app.fila.itens), 1)
        self.assertEqual(self.app.fila.obter()["meta"]["pedido"]["estado"], "aguardando")
        self.app.eventos.put(("ticket_recebido", original, {"ticket": "456", "url": "https://empresa.movidesk.com/Ticket/Edit/456"}))
        self.aguardar(lambda: self.app.vars["ticket"].get() == "456")

    def test_fila_filtra_avanca_arquiva_e_desfaz_remocao(self):
        from noc.incidentes import importar_eventos
        from noc.atendimento import etapa_incidente
        eventos = [{"alerta": "CPU", "servidor": f"host-{n}", "severidade": "Disaster" if n == 3 else "High",
                    "link_zabbix": f"https://zabbix.test/tr_events.php?eventid={n}"} for n in (1, 2, 3)]
        self.app.aplicar_importacao(importar_eventos({"versao": 1, "origem": "zabbix", "eventos": eventos}))
        ids = [i["id"] for i in self.app.fila.itens]
        self.app.vars["ticket"].set("123")
        with patch("noc.interface.pyperclip.copy"):
            self.app.copiar_comunicado("WhatsApp")
        self.app.fila.obter(ids[1])["meta"]["pedido"] = {"estado": "aguardando"}
        self.app.proximo_pendente()
        self.assertEqual(self.app.fila.ativo, ids[2])
        self.app.painel_fila.severidade.set("Desastre")
        self.app.painel_fila.filtrar()
        self.assertEqual(self.app.painel_fila.lista.get_children(), (ids[2],))
        self.app.arquivar_incidente()
        self.assertEqual(etapa_incidente(self.app.fila.obter()), "Arquivado")
        self.assertEqual(self.app.painel_fila.lista.get_children(), ())
        self.app.painel_fila.etapa.set("Arquivado")
        self.app.painel_fila.filtrar()
        self.assertEqual(self.app.painel_fila.lista.get_children(), (ids[2],))
        self.app.remover_incidente()
        self.assertIsNone(self.app.fila.obter(ids[2]))
        self.app.desfazer_remocao()
        self.assertEqual(self.app.fila.ativo, ids[2])
        self.app.arquivar_incidente()
        self.assertFalse(self.app.fila.obter()["meta"]["arquivado"])

    def test_modelos_exigem_relato_e_registram_apenas_copia_bem_sucedida(self):
        self.app.definir_dados(dados_incidente())
        self.app.modelo_comunicado.set("Normalização")
        self.app.mudar_modelo()
        with patch("noc.interface.pyperclip.copy") as copiar:
            self.app.copiar_comunicado("WhatsApp")
            copiar.assert_not_called()
        self.app.texto_atualizacao.set("CPU estabilizada em 30% às 15:00.")
        with patch("noc.interface.pyperclip.copy", side_effect=OSError("Clipboard ocupado")):
            self.app.copiar_comunicado("WhatsApp")
        self.assertNotIn("copias", self.app.fila.obter()["meta"])
        with patch("noc.interface.pyperclip.copy") as copiar:
            self.app.copiar_comunicado("WhatsApp")
            self.assertIn("CPU estabilizada em 30%", copiar.call_args.args[0])
            self.assertIn("Normalização do incidente", copiar.call_args.args[0])
        self.assertEqual(self.app.fila.obter()["meta"]["copias"]["WhatsApp"]["modelo"], "Normalização")
        self.assertIn("Copiado:", self.app.copias_resumo.get())

    def test_arquivo_copiado_nao_e_tratado_como_imagem(self):
        with patch("noc.interface.ImageGrab.grabclipboard", return_value=["arquivo.png"]):
            with self.assertRaisesRegex(ValueError, "Win\\+Shift\\+S"):
                self.app.ler_clipboard()

    def test_fechar_durante_ia_nao_espera_rede_nem_aplica_resultado_tardio(self):
        liberar = threading.Event()
        iniciou = threading.Event()
        threads = []

        def ia_lenta(*_, **kwargs):
            threads.append(threading.current_thread())
            iniciou.set()
            liberar.wait(5)
            return {"alerta": "Resultado tardio", "servidor": "outro-host"}

        self.app.definir_dados(dados_incidente())
        self.app.definir_imagem(Image.new("RGB", (10, 10)))
        try:
            with patch("noc.interface.extrair_dados", side_effect=ia_lenta):
                self.app.extrair_com_ia()
                self.aguardar(iniciou.is_set)
                self.app.fechar()
                self.aguardar(lambda: not self.root.tk.call("info", "commands", "."), timeout=3)
                self.assertTrue(threads[0].is_alive())
        finally:
            liberar.set()
            for thread in threads:
                thread.join(timeout=3)
        salvo = json.loads((Path(self.pasta.name) / ".noc_data/rascunho.json").read_text(encoding="utf-8"))
        self.assertEqual(salvo["dados"]["alerta"], "CPU alta")

    def test_falha_ao_salvar_no_fechamento_permite_manter_janela_e_dados(self):
        self.app.definir_dados(dados_incidente())
        self.app.rascunho.permitir_salvamento = False
        try:
            with patch("noc.interface.messagebox.askyesno", return_value=False) as confirmar, self.assertLogs("noc", level="ERROR"):
                self.app.fechar()
                self.aguardar(lambda: not self.app.fechando)
            confirmar.assert_called_once()
            self.assertEqual(self.app.obter_dados()["ticket"], "123")
            self.assertTrue(self.app.rascunho.is_alive())
            self.assertTrue(self.app.movidesk.is_alive())
        finally:
            self.app.rascunho.permitir_salvamento = True


if __name__ == "__main__":
    unittest.main()
