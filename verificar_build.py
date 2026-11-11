"""Smoke test offline executado dentro do binário gerado pelo PyInstaller."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
from urllib.request import Request, urlopen


def verificar(relatorio):
    resultado = {"executavel": sys.executable, "empacotado": bool(getattr(sys, "frozen", False))}
    try:
        import google.generativeai as genai
        from google.ai import generativelanguage
        from google.auth.credentials import AnonymousCredentials
        from PIL import Image, ImageDraw, ImageFont
        from groq import Groq
        from noc.ocr_windows import extrair_texto
        import tkinter as tk

        from noc.interface import NOCFlow
        from noc.configuracao import Config
        from noc.comunicados import gerar_assunto_email
        from noc.recortes_email import montar_recortes
        from noc.edge_bridge import ARQUIVOS_EXTENSAO, EdgeBridge, preparar_extensao, caminho_edge
        from noc.extracao_local import interpretar_ocr
        from noc.incidentes import importar_eventos, FilaIncidentes
        from noc.agenda_operacional import criar_rotina, fuso
        from noc.central_operacional import PERFIL_EXEMPLO
        from noc.historico_atendimento import agendar_acao, registrar_evento
        from noc.regras_operacionais import validar_perfis

        cliente = generativelanguage.GenerativeServiceClient(
            credentials=AnonymousCredentials(),
            client_options={"api_endpoint": "localhost:1"},
        )
        cliente.transport.close()
        resultado["gemini_sdk"] = genai.__version__
        with Groq(api_key="verificacao-offline", max_retries=0):
            resultado["groq_sdk"] = "ok"
        imagem_ocr = Image.new("RGB", (900, 260), "white")
        fonte_ocr = ImageFont.truetype(str(Path(os.environ["WINDIR"]) / "Fonts/arial.ttf"), 26)
        ImageDraw.Draw(imagem_ocr).multiline_text((20, 20), "Trigger: CPU usage high\nHost: servidor-01\nSeverity: High\nOperational data: CPU 95%\nTime: 10:42", font=fonte_ocr, fill="black", spacing=8)
        texto_ocr = extrair_texto(imagem_ocr)
        if "servidor-01" not in texto_ocr or "95%" not in texto_ocr:
            raise RuntimeError("O OCR empacotado não reconheceu a imagem de teste.")
        resultado["ocr_windows"] = "ok"
        dados_ocr, _ = interpretar_ocr(texto_ocr)
        if "servidor-01" not in dados_ocr["servidor"]:
            raise RuntimeError("O interpretador local não identificou o host do OCR.")
        fila = FilaIncidentes()
        fila.importar(importar_eventos({"versao": 1, "origem": "zabbix", **dados_ocr, "link_zabbix": "https://zabbix.test/tr_events.php?eventid=1"}))
        if fila.obter()["meta"].get("eventid") != "1":
            raise RuntimeError("A importação estruturada não identificou o evento.")
        resultado["fluxo_sem_ia"] = "ok"
        recortada = montar_recortes(imagem_ocr, {"Host": (0, 0, 100, 20), "Trigger": (0, 20, 150, 40), "Severity": (0, 40, 80, 60)})
        if recortada.size != (150, 72) or gerar_assunto_email({"ticket": "123", "alerta": "CPU alta", "servidor": "host-01"}) != "123 - CPU alta - host-01":
            raise RuntimeError("A montagem dos recortes ou do assunto do e-mail falhou.")
        resultado["email_recortes"] = "ok"
        validar_perfis(PERFIL_EXEMPLO)
        fuso("America/Sao_Paulo")
        resultado["perfis_e_fusos"] = "ok"
        with tempfile.TemporaryDirectory() as pasta:
            extensao = preparar_extensao(Path(pasta))
            if not all((extensao / nome).is_file() for nome in ARQUIVOS_EXTENSAO):
                raise RuntimeError("A extensão do Edge está incompleta no pacote.")
            resultado["extensao"] = json.loads((extensao / "manifest.json").read_text(encoding="utf-8"))["version"]
            root = tk.Tk()
            root.withdraw()
            app = NOCFlow(root, Config(Path(pasta)))
            erros_interface = []
            def falha_interface(tipo, valor, trace):
                erros_interface.append("".join(traceback.format_exception(tipo, valor, trace)))
                app.fechar()
            root.report_callback_exception = falha_interface
            limite = time.monotonic() + 10
            def exercitar_operacao():
                if app.carregando:
                    if time.monotonic() >= limite:
                        raise RuntimeError("A interface empacotada não recuperou o rascunho no prazo.")
                    root.after(100, exercitar_operacao)
                    return
                app.definir_imagem(Image.new("RGB", (20, 20)))
                app.vars["alerta"].set("Verificação offline da operação")
                app.vars["origem_atendimento"].set("Manual")
                app.guardar_incidente()
                registrar_evento(app.fila.obter(), "Envio registrado", "Registro fictício offline.")
                agendar_acao(app.fila.obter(), "Conferir retorno", "2030-01-01T10:00:00+00:00")
                app.fila.operacional["rotinas"] = [criar_rotina("Rotina fictícia", "2030-01-01T10:00:00+00:00")]
                app.abrir_central()
                app.central.gerar_passagem()
                if not app.central.lista_agenda.get_children():
                    raise RuntimeError("A agenda não carregou a rotina no executável.")
                app.revisao += 1
                app.salvar_rascunho()
                root.after(300, app.fechar)
            root.after(100, exercitar_operacao)
            root.mainloop()
            if erros_interface:
                raise RuntimeError("\n".join(erros_interface))
            salvo = json.loads((Path(pasta) / ".noc_data" / "rascunho.json").read_text(encoding="utf-8"))
            if not salvo["fila"]["operacional"]["rotinas"] or not salvo["fila"]["itens"][0]["meta"].get("historico"):
                raise RuntimeError("Estado operacional não foi persistido no executável.")
            resultado["interface"] = "ok"
            resultado["central_operacional"] = "ok"
        ponte = EdgeBridge(porta=0)
        try:
            pedido = ponte.criar_pedido({"teste": "ok"}, 10)
            requisicao = Request(f"{ponte.url}/api/request/{pedido.token}", headers={"X-NOC-Token": pedido.token})
            with urlopen(requisicao, timeout=5) as resposta:
                if json.load(resposta) != {"teste": "ok"}:
                    raise RuntimeError("A ponte local não retornou os dados esperados.")
            resultado["ponte_local"] = "ok"
        finally:
            ponte.fechar()
        resultado["microsoft_edge"] = str(caminho_edge())
        resultado["status"] = "ok"
        codigo = 0
    except Exception:
        resultado["status"] = "erro"
        resultado["erro"] = traceback.format_exc()
        codigo = 1
    relatorio.parent.mkdir(parents=True, exist_ok=True)
    relatorio.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return codigo
