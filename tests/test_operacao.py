from copy import deepcopy
import json
from pathlib import Path
import queue
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from PIL import Image

from noc.agenda_operacional import criar_rotina, em_janela, proximo_horario, registrar_execucao, validar_agenda
from noc.assistente_ia import organizar_relato, responder_com_fontes
from noc.base_conhecimento import buscar, carregar_base
from noc.central_operacional import PERFIL_EXEMPLO
from noc.comunicados import gerar_html, validar_dados
from noc.configuracao import Config
from noc.historico_atendimento import agendar_acao, concluir_acompanhamento, instante, pendente_operacional, registrar_evento
from noc.incidentes import FilaIncidentes
from noc.interface import NOCFlow
from noc.rascunhos import RascunhoWorker
from noc.regras_operacionais import aplicar_regra, avaliar_regras, prazos_atendimento, validar_perfis
from noc.relatorios import diario_bordo, exportar_csv, indicadores, passagem_turno

AGORA = "2030-01-07T12:00:00+00:00"


def perfil_validado():
    dados = deepcopy(PERFIL_EXEMPLO)
    dados["perfis"][0]["regras"][0]["estado"] = "validada"
    return dados


def atendimento():
    item = FilaIncidentes().obter()
    item["dados"].update(alerta="Serviço indisponível", ticket="123", perfil="demonstracao", origem_atendimento="Telefone")
    return item


class RegrasTests(unittest.TestCase):
    def test_excecao_tem_precedencia_e_preserva_severidade_original(self):
        dados = perfil_validado()
        regras = dados["perfis"][0]["regras"]
        excecao = deepcopy(regras[0])
        excecao.update(id="excecao", precedencia=10, condicoes={"servico": ["Backup"]})
        excecao["resultado"]["prioridade"] = "Desastre"
        regras.append(excecao)
        perfis = validar_perfis(dados)
        item = atendimento()
        item["dados"].update(servico="Backup", severidade="High")
        decisao = avaliar_regras(perfis, item["dados"], AGORA)
        aplicar_regra(item, decisao, "Operador fictício")
        self.assertEqual(item["dados"]["severidade"], "High")
        self.assertEqual(item["dados"]["prioridade"], "Desastre")
        self.assertEqual(decisao["fontes"][0]["id"], "excecao")
        item["dados"]["servico"] = ""
        self.assertEqual(avaliar_regras(perfis, item["dados"], AGORA)["estado"], "pendente")

    def test_conflito_de_mesma_precedencia_nao_escolhe_arbitrariamente(self):
        dados = perfil_validado()
        regra = deepcopy(dados["perfis"][0]["regras"][0])
        regra["id"] = "outra"
        regra["resultado"]["equipe"] = "Outra equipe fictícia"
        dados["perfis"][0]["regras"].append(regra)
        resultado = avaliar_regras(validar_perfis(dados), atendimento()["dados"], AGORA)
        self.assertEqual(resultado["estado"], "conflito")
        self.assertEqual(resultado["resultado"], {})
        self.assertEqual(len(resultado["fontes"]), 2)

    def test_rascunho_vencido_e_fora_da_janela_nao_entram_na_decisao(self):
        dados = perfil_validado()
        regra = dados["perfis"][0]["regras"][0]
        for alteracao in ({"estado": "rascunho"}, {"vigente_ate": "2029-12-31"}, {"janela": {"inicio": "20:00", "fim": "06:00"}}):
            with self.subTest(alteracao=alteracao):
                teste = deepcopy(dados)
                teste["perfis"][0]["regras"][0].update(alteracao)
                self.assertEqual(avaliar_regras(validar_perfis(teste), atendimento()["dados"], AGORA)["estado"], "sem_regra")
        regra["resultado"]["politica_ticket"] = "apagar"
        with self.assertRaises(ValueError):
            validar_perfis(dados)

    def test_prazos_exigem_marco_registrado_e_usam_retorno_real(self):
        item = atendimento()
        decisao = avaliar_regras(validar_perfis(perfil_validado()), item["dados"], AGORA)
        self.assertEqual(prazos_atendimento(item, decisao)[0]["prazo"], "")
        registrar_evento(item, "Envio registrado", "Mensagem enviada", em=AGORA)
        self.assertEqual(prazos_atendimento(item, decisao)[0]["prazo"], "2030-01-07T12:15:00+00:00")


class AgendaTests(unittest.TestCase):
    def test_turno_noturno_usa_fuso_e_dia_de_inicio(self):
        calendario = {"fuso": "America/Sao_Paulo", "dias": [0], "feriados": []}
        self.assertTrue(em_janela("2030-01-08T04:00:00+00:00", calendario, "22:00", "06:00"))
        self.assertFalse(em_janela("2030-01-08T12:00:00+00:00", calendario, "22:00", "06:00"))
        calendario["feriados"] = ["2030-01-07"]
        self.assertFalse(em_janela("2030-01-08T04:00:00+00:00", calendario, "22:00", "06:00"))

    def test_fim_de_semana_feriado_e_horario_inexistente(self):
        rotina = criar_rotina("Checagem", AGORA, "horários", calendario={"fuso": "UTC", "dias": [0, 1, 2, 3, 4], "feriados": ["2030-01-07"]}, horarios=["09:00"])
        self.assertEqual(proximo_horario(rotina, "2030-01-04T10:00:00+00:00"), "2030-01-08T09:00:00+00:00")
        rotina["calendario"] = {"fuso": "America/New_York"}
        rotina["horarios"] = ["02:30"]
        proximo = proximo_horario(rotina, "2030-03-10T05:00:00+00:00")
        self.assertEqual(proximo, "2030-03-11T06:30:00+00:00")

    def test_execucao_atrasada_nao_pula_ocorrencias_pendentes(self):
        rotina = criar_rotina("Verificação", AGORA, "intervalo", intervalo_minutos=30)
        estado = {"rotinas": [rotina]}
        registrar_execucao(estado, rotina["id"], "Não executada", "Ausência registrada", em="2030-01-07T14:00:00+00:00")
        self.assertEqual(rotina["proxima"], "2030-01-07T12:30:00+00:00")
        self.assertEqual(len(estado["execucoes"]), 1)
        self.assertEqual(estado["execucoes"][0]["prevista"], AGORA)

    def test_dependencia_precisa_sucesso_no_dia_e_ciclo_e_rejeitado(self):
        a = criar_rotina("Primeira etapa", AGORA)
        b = criar_rotina("Segunda etapa", AGORA, dependencias=[a["id"]])
        estado = {"rotinas": [a, b]}
        with self.assertRaisesRegex(ValueError, "Dependência"):
            registrar_execucao(estado, b["id"], "OK", "Checado", em=AGORA)
        registrar_execucao(estado, a["id"], "OK", "Checado", em=AGORA)
        registrar_execucao(estado, b["id"], "OK", "Checado", em=AGORA)
        self.assertFalse(b["ativa"])
        a["dependencias"] = [b["id"]]
        with self.assertRaisesRegex(ValueError, "Ciclo"):
            validar_agenda(estado)

    def test_datas_sem_fuso_sao_rejeitadas(self):
        with self.assertRaises(ValueError):
            instante("2030-01-07T12:00:00")


class HistoricoTests(unittest.TestCase):
    def test_copia_nao_e_envio_e_validacao_precisa_ser_nova_apos_reabertura(self):
        item = atendimento()
        registrar_evento(item, "Mensagem copiada", "Texto", em=AGORA)
        self.assertTrue(pendente_operacional(item, AGORA))
        registrar_evento(item, "Envio registrado", "Enviado", em=AGORA)
        regra = {"estado": "aplicada", "resultado": {"encerramento": "apos_validacao"}}
        with self.assertRaises(ValueError):
            concluir_acompanhamento(item, regra)
        registrar_evento(item, "Validação confirmada", "Confirmado", em="2020-01-01T12:00:00+00:00")
        concluir_acompanhamento(item, regra)
        self.assertFalse(pendente_operacional(item))
        registrar_evento(item, "Acompanhamento reaberto", "Recorrência")
        with self.assertRaises(ValueError):
            concluir_acompanhamento(item, regra)

    def test_historico_agenda_e_dados_multicanal_sobrevivem_ao_reinicio(self):
        with tempfile.TemporaryDirectory() as pasta:
            fila = FilaIncidentes()
            item = fila.obter()
            item["dados"].update(alerta="Solicitação", origem_atendimento="E-mail", servico="Serviço exemplo", relato_original="Texto recebido")
            registrar_evento(item, "Recebido", "Recebido por e-mail", em=AGORA)
            agendar_acao(item, "Solicitar retorno", "2030-01-07T13:00:00+00:00")
            fila.operacional["rotinas"] = [criar_rotina("Rotina", AGORA)]
            config = Config(Path(pasta))
            worker = RascunhoWorker(config, queue.Queue())
            worker.start()
            worker.comandos.put((1, item["dados"], None, fila.snapshot()))
            worker.comandos.put(None)
            worker.join(5)
            restaurador = RascunhoWorker(config, queue.Queue())
            restaurador.carregar()
            restaurada = FilaIncidentes()
            restaurada.restaurar(restaurador.fila_carregada)
            self.assertEqual(restaurada.snapshot(), fila.snapshot())
            snapshot = fila.snapshot()
            snapshot["operacional"]["rotinas"][0]["titulo"] = "Alterado"
            self.assertEqual(fila.operacional["rotinas"][0]["titulo"], "Rotina")

    def test_dados_multicanal_nao_exigem_servidor_e_html_preserva_contexto_com_imagem(self):
        item = atendimento()
        d = item["dados"]
        d["relato_original"] = "Relato <original>"
        self.assertEqual(validar_dados(d, "Movidesk"), {})
        d["ticket"] = ""
        self.assertIn("ticket", validar_dados(d, "Teams"))
        self.assertEqual(validar_dados(d, "Teams", permitir_sem_ticket=True), {})
        html = gerar_html(d, Image.new("RGB", (3, 3)))
        self.assertIn("Relato &lt;original&gt;", html)
        self.assertIn("Serviço indisponível", html)
        self.assertIn("data:image/png;base64", html)


class ConhecimentoIATests(unittest.TestCase):
    def test_sdk_envia_schema_e_nao_revela_corpo_de_erros(self):
        import httpx
        from groq import Groq
        requisicoes = []
        resposta = {"sugestoes": [{"campo": "servico", "valor": "VPN", "trecho": "VPN não conecta"}], "informacoes_faltantes": []}
        def transporte(request):
            requisicoes.append(request)
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": json.dumps(resposta)}, "finish_reason": "stop"}],
                                             "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}})
        def cliente(**kwargs):
            self.assertEqual(kwargs["max_retries"], 0)
            return Groq(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transporte)))
        config = Config(Path("."), groq_api_key="chave-ficticia")
        with patch("groq.Groq", side_effect=cliente):
            resultado = organizar_relato(config, "VPN não conecta")
        self.assertEqual(resultado["metricas"]["tokens"], 30)
        self.assertEqual(len(requisicoes), 1)
        conteudo = json.loads(requisicoes[0].content)
        self.assertTrue(conteudo["response_format"]["json_schema"]["strict"])
        self.assertEqual(json.loads(conteudo["messages"][1]["content"]), {"relato": "VPN não conecta"})
        def indisponivel(request):
            return httpx.Response(429, json={"error": {"message": "CONTEUDO_PRIVADO"}})
        with patch("groq.Groq", side_effect=lambda **kw: Groq(**kw, http_client=httpx.Client(transport=httpx.MockTransport(indisponivel)))):
            with self.assertRaisesRegex(ValueError, "HTTP 429") as exc:
                organizar_relato(config, "VPN não conecta")
        self.assertNotIn("CONTEUDO_PRIVADO", str(exc.exception))

    def test_busca_respeita_perfil_servico_estado_vigencia_e_limites_de_pasta(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            (raiz / "vpn.md").write_text("# VPN\nConsultar conectividade e registrar evidência.", encoding="utf-8")
            doc = {"id": "vpn", "titulo": "VPN", "versao": "1", "estado": "validado", "arquivo": "vpn.md", "perfis": ["exemplo"], "servicos": ["VPN"]}
            indice = raiz / "indice.json"
            indice.write_text(json.dumps({"versao": 1, "documentos": [doc]}), encoding="utf-8")
            base = carregar_base(raiz)
            self.assertFalse(buscar(base, "VPN", "outro", "VPN"))
            self.assertFalse(buscar(base, "VPN", "exemplo", "Banco"))
            self.assertEqual(buscar(base, "VPN", "exemplo", "VPN")[0]["id"], "vpn:1:0")
            doc["arquivo"] = "../fora.md"
            indice.write_text(json.dumps({"versao": 1, "documentos": [doc]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "dentro da pasta"):
                carregar_base(raiz)

    def test_relato_exige_trecho_real_e_nao_aplica_sugestoes(self):
        config = Config(Path("."))
        resposta = {"sugestoes": [{"campo": "servico", "valor": "VPN", "trecho": "VPN não conecta"}], "informacoes_faltantes": ["Abrangência"]}
        with patch("noc.assistente_ia.consultar_texto", return_value=(resposta, {"segundos": 1})):
            resultado = organizar_relato(config, "A VPN não conecta")
        self.assertEqual(resultado["relato_original"], "A VPN não conecta")
        resposta["sugestoes"][0]["trecho"] = "Equipe confirmou recuperação"
        with patch("noc.assistente_ia.consultar_texto", return_value=(resposta, {})), self.assertRaisesRegex(ValueError, "trecho"):
            organizar_relato(config, "A VPN não conecta")

    def test_resposta_rejeita_fonte_ou_citacao_inventada(self):
        resposta = {"afirmacoes": [{"texto": "Acompanhar", "fonte": "inexistente", "trecho": "Acompanhar"}], "pendencias": []}
        fontes = [{"id": "documento:1:0", "texto": "Acompanhar o retorno"}]
        with patch("noc.assistente_ia.consultar_texto", return_value=(resposta, {})), self.assertRaisesRegex(ValueError, "referências"):
            responder_com_fontes(Config(Path(".")), "Como proceder?", fontes)


class RelatoriosTests(unittest.TestCase):
    def test_indicadores_periodo_e_fontes_sao_reproduziveis(self):
        item = atendimento()
        registrar_evento(item, "Recebido", "Recebido", em=AGORA)
        registrar_evento(item, "Envio registrado", "Enviado", em="2030-01-07T12:10:00+00:00")
        registrar_evento(item, "Nota", "Fora do período", em="2030-01-08T00:00:00+00:00")
        fim = "2030-01-08T00:00:00+00:00"
        resultado = indicadores([item], {}, AGORA, fim)
        self.assertNotIn("Nota", resultado["eventos"])
        self.assertEqual(resultado["tempos_desde_recebimento"]["notificacao"], {"amostras": 1, "media_segundos": 600})
        self.assertIsNone(resultado["tempos_desde_recebimento"]["registro"]["media_segundos"])
        self.assertIn("Fonte:", diario_bordo([item], AGORA, fim))
        self.assertIn(item["id"], passagem_turno([item], {}, AGORA))
        registrar_evento(item, "Nota", "=SOMA(1;2)", em=AGORA)
        self.assertIn("'=SOMA", exportar_csv([item], AGORA, fim))


class CentralInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = NOCFlow(self.root, Config(Path(self.pasta.name)))
        self.aguardar(lambda: not self.app.carregando)
        self.app.abrir_central()
        self.central = self.app.central

    def aguardar(self, funcao):
        limite = time.monotonic() + 5
        while not funcao() and time.monotonic() < limite:
            self.root.update()
            time.sleep(0.005)
        self.assertTrue(funcao())

    def tearDown(self):
        self.app.fechar()
        self.aguardar(lambda: not self.app.rascunho.is_alive() and not self.app.movidesk.is_alive())
        if self.app.poll_after:
            self.root.after_cancel(self.app.poll_after)
        if self.root.tk.call("info", "commands", "."):
            self.root.destroy()
        self.pasta.cleanup()

    def widgets(self, raiz):
        for w in raiz.winfo_children():
            yield w
            yield from self.widgets(w)

    def preencher_dialogo(self, titulo, valores):
        janela = next(w for w in self.widgets(self.root) if isinstance(w, tk.Toplevel) and w.title() == titulo)
        for campo, valor in valores.items():
            w = next(w for w in self.widgets(janela) if w.winfo_name() == campo)
            if isinstance(w, ttk.Combobox):
                w.set(valor)
            elif isinstance(w, tk.Text):
                w.delete("1.0", "end")
                w.insert("1.0", valor)
            else:
                w.delete(0, "end")
                w.insert(0, valor)
        next(w for w in self.widgets(janela) if isinstance(w, ttk.Button) and w.cget("text") == "Salvar").invoke()

    def test_atendimento_sem_host_historico_e_agenda_pela_tela(self):
        self.central.editar_atendimento()
        self.preencher_dialogo("Dados do atendimento", {"alerta": "Pedido por telefone", "origem_atendimento": "Telefone", "ticket": "456", "relato_original": "Solicitante relata falha"})
        self.assertEqual(self.app.obter_dados()["servidor"], "")
        self.assertTrue(self.app.validar("Movidesk"))
        with patch("noc.interface.pyperclip.copy"):
            self.app.copiar_comunicado("Teams")
        self.assertTrue(pendente_operacional(self.app.fila.obter()))
        self.central.registrar_acao()
        self.preencher_dialogo("Registrar ação · envio informado manualmente", {"texto": "Comunicado enviado", "destino": "Equipe de exemplo", "canal": "Teams"})
        self.assertEqual(etapa := self.app.fila.obter()["meta"]["acompanhamento"]["estado"], "Aguardando ciência")
        self.assertIn(etapa, self.app.proxima_acao.get())
        self.central.nova_rotina()
        self.preencher_dialogo("Rotina ou verificação de dashboard", {"titulo": "Validar painel", "proxima": "2020-01-01T10:00:00+00:00", "esperado": "Verificar dados do período"})
        rotina = self.app.fila.operacional["rotinas"][0]
        self.central.lista_agenda.selection_set(rotina["id"])
        self.central.execucao()
        self.preencher_dialogo("Registrar esta ocorrência", {"evidencia": "Painel consultado; resultado esperado presente"})
        self.assertFalse(rotina["ativa"])
        self.assertEqual(len(self.app.fila.operacional["execucoes"]), 1)

    def test_consulta_ia_nao_bloqueia_interface_nem_sobrescreve_edicao(self):
        liberar, iniciou = threading.Event(), threading.Event()
        self.app.vars["alerta"].set("Resumo original")
        self.app.vars["relato_original"].set("VPN não conecta")
        self.app.guardar_incidente()
        resultado = {"sugestoes": [{"campo": "alerta", "valor": "Falha de VPN", "trecho": "VPN não conecta"}],
                     "informacoes_faltantes": [], "relato_original": "VPN não conecta", "metricas": {"segundos": 1}}
        def consultar(*args):
            iniciou.set()
            liberar.wait(4)
            return resultado
        try:
            with patch("noc.central_operacional.organizar_relato", side_effect=consultar):
                self.central.ia_relato()
                self.aguardar(iniciou.is_set)
                self.app.vars["alerta"].set("Revisado durante a consulta")
                liberar.set()
                self.aguardar(lambda: not self.central.ia_ativa)
            self.assertEqual(self.app.obter_dados()["alerta"], "Revisado durante a consulta")
            janela = next(w for w in self.widgets(self.root) if isinstance(w, tk.Toplevel) and "Sugestões de IA" in w.title())
            next(w for w in self.widgets(janela) if isinstance(w, ttk.Checkbutton)).invoke()
            next(w for w in self.widgets(janela) if isinstance(w, ttk.Button) and w.cget("text") == "Aplicar campos selecionados").invoke()
            self.assertEqual(self.app.obter_dados()["alerta"], "Revisado durante a consulta")
            self.assertTrue(janela.winfo_exists())
        finally:
            liberar.set()

    def test_acionamento_sem_ticket_depende_de_regra_e_conflito_bloqueia(self):
        d = perfil_validado()
        regra = d["perfis"][0]["regras"][0]
        regra["resultado"]["comunicar_sem_ticket"] = True
        self.app.perfis_operacionais = validar_perfis(d)
        self.app.vars["alerta"].set("Falha")
        self.app.vars["origem_atendimento"].set("Telefone")
        self.app.vars["perfil"].set("demonstracao")
        self.app.modelo_comunicado.set("Acionamento inicial")
        self.assertTrue(self.app.validar("Teams"))
        outra = deepcopy(regra)
        outra["id"] = "conflitante"
        outra["resultado"]["comunicar_sem_ticket"] = False
        d["perfis"][0]["regras"].append(outra)
        self.app.perfis_operacionais = validar_perfis(d)
        self.assertFalse(self.app.validar("Teams"))


if __name__ == "__main__":
    unittest.main()
