"""Integração real da extensão com cookies preexistentes e servidor local."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import shutil
import tempfile
import threading
import time
import unittest

from noc.edge_bridge import EdgeBridge
from noc.incidentes import CAMPOS_FORMULARIO as CAMPOS
from noc.configuracao import Config
from noc.movidesk import MovideskWorker


FORMULARIO = b"""<html><body><input id="TicketSubject">
<select id="TicketCategory"><option value="">Selecione</option><option value="alerta">Alerta</option></select>
<select id="TicketUrgency"><option value="">Selecione</option><option value="2">2. Alta</option><option value="3">3. M\xc3\xa9dia</option></select>
<iframe class="tox-edit-area__iframe" srcdoc="<html><body contenteditable='true'><p>Atenciosamente, Equipe NOC</p></body></html>"></iframe>
<script>window.addEventListener('load', () => {
  const frame = document.querySelector('iframe');
  frame.contentDocument.body.addEventListener('change', () => {
    fetch('/resultado', {method: 'POST', body: JSON.stringify({
      assunto: document.querySelector('input').value,
      categoria: document.querySelector('#TicketCategory').value,
      urgencia: document.querySelector('#TicketUrgency').value,
      texto: frame.contentDocument.body.innerText,
      imagens: frame.contentDocument.querySelectorAll('img').length,
      scripts: frame.contentDocument.querySelectorAll('script').length,
      injetado: Boolean(frame.contentWindow.injetado)
    })});
  });
});</script></body></html>"""

EVENTO = b"""<html><body><table><tr><td>Host</td><td>host-zabbix</td></tr>
<tr><td>Trigger</td><td>CPU alta</td></tr><tr><td>Severity</td><td>High</td></tr>
<tr><td>Operational data</td><td>95%</td></tr><tr><td>Time</td><td>10:42</td></tr></table></body></html>"""


@unittest.skipUnless(os.getenv("NOC_TEST_BROWSER") == "1", "Defina NOC_TEST_BROWSER=1 para testar a extensão no Chromium")
class MovideskLocalTests(unittest.TestCase):
    def test_extensao_reutiliza_login_e_mantem_guias_apos_fechar_aplicativo(self):
        from playwright.sync_api import sync_playwright

        resultados = queue.Queue()
        cookies = queue.Queue()
        login = threading.Event()
        login.set()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                cookie = self.headers.get("Cookie", "")
                if self.path == "/Ticket/Create":
                    cookies.put(cookie)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                corpo = EVENTO if self.path.startswith("/tr_events.php") else FORMULARIO
                self.wfile.write(corpo if login.is_set() and "sessao=ja-logado" in cookie else b"<html><body>Login pendente</body></html>")

            def do_POST(self):
                resultados.put(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(200)
                self.end_headers()

        servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        servidor_thread = threading.Thread(target=servidor.serve_forever, daemon=True)
        servidor_thread.start()
        ponte = EdgeBridge(porta=0)
        ponte.iniciar()
        eventos = queue.Queue()
        aberturas = queue.Queue()

        def aguardar_evento(tipo, timeout=20):
            limite = time.monotonic() + timeout
            while time.monotonic() < limite:
                evento = eventos.get(timeout=max(0.01, limite - time.monotonic()))
                if evento[0] == "erro":
                    self.fail(evento[2])
                if evento[0] == tipo:
                    return evento
            self.fail(f"Evento {tipo} não recebido")

        try:
            with tempfile.TemporaryDirectory() as pasta, sync_playwright() as playwright:
                raiz = Path(pasta)
                extensao = raiz / "extensao"
                shutil.copytree(Path(__file__).resolve().parents[1] / "edge_extension", extensao)
                # Só a fixture local recebe permissão extra; a extensão distribuída usa Movidesk.
                manifest = json.loads((extensao / "manifest.json").read_text(encoding="utf-8"))
                manifest["content_scripts"][1]["matches"].append("http://127.0.0.1/*")
                manifest["content_scripts"][2]["matches"].append("http://127.0.0.1/*")
                (extensao / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                for nome in ("background.js", "bridge.js"):
                    arquivo = extensao / nome
                    arquivo.write_text(arquivo.read_text(encoding="utf-8").replace("http://127.0.0.1:18764", ponte.url).replace("https://zabbix.example.com", f"http://127.0.0.1:{servidor.server_port}"), encoding="utf-8")
                # Edge restringe --load-extension; o Chromium testa a mesma extensão MV3.
                navegador = playwright.chromium.launch_persistent_context(
                    str(raiz / "perfil"), channel="chromium", headless=True,
                    args=[f"--disable-extensions-except={extensao}", f"--load-extension={extensao}"],
                )
                worker = MovideskWorker(Config(raiz, movidesk_url=f"http://127.0.0.1:{servidor.server_port}", timeout_login=25), eventos, abrir=aberturas.put, ponte=ponte)
                try:
                    if not navegador.service_workers:
                        navegador.wait_for_event("serviceworker", timeout=10000)
                    service_worker = navegador.service_workers[0]
                    navegador.add_cookies([{"name": "sessao", "value": "ja-logado", "url": f"http://127.0.0.1:{servidor.server_port}"}])
                    existente = navegador.new_page()
                    existente.goto(f"http://127.0.0.1:{servidor.server_port}/")
                    worker.start()
                    dados = dict.fromkeys(CAMPOS, "")
                    dados.update(alerta='CPU ` ${window.injetado=true} <script>erro</script>', servidor="host-01", severidade="Average", horario="10:42")
                    worker.comandos.put((1, dados))
                    pagina = navegador.new_page()
                    pagina.goto(aberturas.get(timeout=5))
                    aguardar_evento("movidesk_ok")
                    recebido = resultados.get(timeout=5)
                    self.assertIn("sessao=ja-logado", cookies.get(timeout=5))
                    self.assertEqual(recebido["assunto"], f"{dados['alerta']} - host-01")
                    self.assertEqual(recebido["categoria"], "alerta")
                    self.assertEqual(recebido["urgencia"], "3")
                    self.assertIn(dados["alerta"], recebido["texto"])
                    self.assertIn("10:42", recebido["texto"])
                    self.assertIn("Atenciosamente, Equipe NOC", recebido["texto"])
                    self.assertEqual(recebido["scripts"], 0)
                    self.assertFalse(recebido["injetado"])
                    # Repetir a ação do mesmo incidente retoma a guia, sem outro formulário.
                    worker.comandos.put((6, {**dados, "_incidente_id": "1"}))
                    retomada = navegador.new_page()
                    retomada.goto(aberturas.get(timeout=5), wait_until="domcontentloaded")
                    aguardar_evento("retomar_ok")
                    pagina.wait_for_timeout(100)
                    self.assertTrue(resultados.empty())
                    self.assertEqual(len(worker.pendentes), 1)
                    self.assertFalse(pagina.is_closed())
                    worker.comandos.put((2, {**dados, "alerta": "Segundo incidente", "severidade": "High"}))
                    segunda = navegador.new_page()
                    segunda.goto(aberturas.get(timeout=5))
                    aguardar_evento("movidesk_ok")
                    segundo_res = resultados.get(timeout=5)
                    self.assertEqual(segundo_res["assunto"], "Segundo incidente - host-01")
                    self.assertEqual(segundo_res["urgencia"], "2")
                    self.assertFalse(pagina.is_closed())
                    # Salva fora de ordem: cada token retorna para o incidente de origem.
                    segunda.evaluate("history.pushState({}, '', '/Ticket/Edit/456')")
                    retorno = aguardar_evento("ticket_recebido")
                    self.assertEqual(retorno[1], "2")
                    self.assertEqual(retorno[2]["ticket"], "456")
                    pagina.goto(f"http://127.0.0.1:{servidor.server_port}/Ticket/Edit/123")
                    retorno = aguardar_evento("ticket_recebido")
                    self.assertEqual(retorno[1], "1")
                    self.assertEqual(retorno[2]["ticket"], "123")
                    # Alguns layouts retornam o número em um modal, mantendo /Ticket/Create.
                    worker.comandos.put((5, {**dados, "alerta": "Ticket por modal"}))
                    modal = navegador.new_page()
                    modal.goto(aberturas.get(timeout=5))
                    aguardar_evento("movidesk_ok")
                    modal.evaluate("""() => {
                        const div = document.createElement('div');
                        div.className = 'protocol-modal';
                        div.style.display = 'none';
                        div.innerHTML = '<span class="ticket-number">789</span>';
                        document.body.append(div);
                    }""")
                    resposta = service_worker.evaluate("""async tabUrl => {
                        const tabs = await chrome.tabs.query({url: tabUrl});
                        const tab = tabs[tabs.length - 1];
                        const [res] = await chrome.scripting.executeScript({target: {tabId: tab.id}, func: () => chrome.runtime.sendMessage({tipo: 'preencher'})});
                        return res.result;
                    }""", modal.url)
                    self.assertTrue(resposta.get("aguardando_ticket"))
                    modal.locator(".protocol-modal").evaluate("el => el.style.display = 'block'")
                    retorno = aguardar_evento("ticket_recebido")
                    self.assertEqual(retorno[1], "5")
                    self.assertEqual(retorno[2], {"ticket": "789", "url": f"http://127.0.0.1:{servidor.server_port}/Ticket/Edit/789"})
                    # Conecta e importa um evento pela extensão real, sem clipboard/API de IA.
                    worker.comandos.put((4, {"_conectar": True}))
                    conexao = navegador.new_page()
                    conexao.goto(aberturas.get(timeout=5))
                    aguardar_evento("conexao_ok")
                    zabbix = navegador.new_page()
                    zabbix.goto(f"http://127.0.0.1:{servidor.server_port}/tr_events.php?triggerid=1&eventid=99")
                    antes = service_worker.evaluate("""async tabUrl => {
                        const [tab] = await chrome.tabs.query({url: tabUrl});
                        const [res] = await chrome.scripting.executeScript({target: {tabId: tab.id}, func: () => typeof globalThis.html2canvas});
                        return res.result;
                    }""", zabbix.url)
                    self.assertEqual(antes, "undefined")
                    zabbix.locator("#noc-zabbix > summary").click()
                    zabbix.get_by_role("button", name="Enviar ao NOCFlow", exact=True).click()
                    recebido = aguardar_evento("zabbix_importado")
                    self.assertEqual(recebido[2][0]["meta"]["eventid"], "99")
                    self.assertEqual(recebido[2][0]["dados"]["servidor"], "host-zabbix")
                    self.assertIsNotNone(recebido[2][0].get("imagem"))
                    # Encerramento durante espera cancela o pedido sem fechar o browser.
                    login.clear()
                    worker.comandos.put((3, dados))
                    terceira = navegador.new_page()
                    terceira.goto(aberturas.get(timeout=5))
                    worker.encerrar.set()
                    worker.join(timeout=5)
                    self.assertFalse(worker.is_alive())
                    self.assertFalse(existente.is_closed())
                    self.assertFalse(segunda.is_closed())
                    self.assertIn("Segundo incidente", segunda.locator("input").input_value())
                finally:
                    worker.encerrar.set()
                    if worker.ident:
                        worker.join(timeout=5)
                    navegador.close()
        finally:
            ponte.fechar()
            servidor.shutdown()
            servidor.server_close()
            servidor_thread.join(timeout=3)


@unittest.skipUnless(os.getenv("NOC_TEST_BROWSER") == "1", "Defina NOC_TEST_BROWSER=1 para fixtures DOM")
class PreenchimentoDOMTests(unittest.TestCase):
    def test_select2_consulta_opcoes_sem_bloquear_pagina(self):
        from playwright.sync_api import sync_playwright

        fonte = (Path(__file__).resolve().parents[1] / "edge_extension/preencher.js").read_text(encoding="utf-8")
        dados = {"assunto": "CPU - host", "alerta": "CPU", "html": "<p>Evidência</p>"}
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chromium", headless=True)
            try:
                page = browser.new_page()
                page.set_content('<input id="TicketSubject"><input id="TicketCategory"><div contenteditable="true">Assinatura</div>')
                page.evaluate("""() => {
                    const select2 = {opts: {ajax: {url: '/categorias'}}, data: valor => {
                        if (valor) window.categoriaEscolhida = valor;
                        return window.categoriaEscolhida;
                    }};
                    window.jQuery = el => ({
                        data: nome => nome === 'select2' && el.id === 'TicketCategory' ? select2 : null,
                        trigger: () => {}, each: () => {}
                    });
                    window.jQuery.ajax = opcoes => {
                        window.sincrono = opcoes.async === false;
                        window.timeoutConsulta = opcoes.timeout;
                        setTimeout(() => {window.paginaResponsiva = true; opcoes.success({results: [{id: 1, text: 'Alerta'}]});}, 20);
                    };
                }""")
                page.add_script_tag(content=fonte.replace("export async function", "async function", 1))
                resultado = page.evaluate("dados => preencherFormulario(dados)", dados)
                self.assertTrue(resultado["ok"])
                self.assertEqual(resultado["campos"]["categoria"], "preenchido")
                self.assertEqual(resultado["campos"]["urgencia"], "nao_localizado")
                self.assertFalse(page.evaluate("window.sincrono"))
                self.assertTrue(page.evaluate("window.paginaResponsiva"))
                self.assertEqual(page.evaluate("window.timeoutConsulta"), 5000)
                self.assertEqual(page.evaluate("window.categoriaEscolhida.text"), "Alerta")
            finally:
                browser.close()

    def test_preserva_conteudo_e_assinatura_sem_duplicar_preenchimento(self):
        from playwright.sync_api import sync_playwright

        fonte = (Path(__file__).resolve().parents[1] / "edge_extension/preencher.js").read_text(encoding="utf-8")
        dados = {"assunto": "CPU alta - host-01", "alerta": "CPU alta", "html": "<p>Evidência NOCFlow</p>"}
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chromium", headless=True)
            try:
                page = browser.new_page()
                for classe in ("fr-element", "editor-generico"):
                    with self.subTest(editor=classe):
                        page.set_content(f'<input id="TicketSubject"><div class="{classe}" contenteditable="true"><p>Anotação sobre CPU alta</p><div class="signature">Assinatura</div></div>')
                        page.add_script_tag(content=fonte.replace("export async function", "async function", 1))
                        for _ in range(2):
                            self.assertTrue(page.evaluate("dados => preencherFormulario(dados)", dados)["ok"])
                        editor = page.locator('[contenteditable="true"]')
                        self.assertIn("Anotação sobre CPU alta", editor.inner_text())
                        self.assertIn("Assinatura", editor.inner_text())
                        self.assertEqual(editor.inner_text().count("Evidência NOCFlow"), 1)
            finally:
                browser.close()

    def test_pendencias_de_campos_e_link_definitivo_apos_salvar_por_modal(self):
        from playwright.sync_api import sync_playwright
        raiz = Path(__file__).resolve().parents[1]
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chromium", headless=True)
            try:
                page = browser.new_page()
                html = '<input id="TicketSubject"><div contenteditable="true">Assinatura</div><select name="Category"><option>Outro</option></select><select name="Urgency"><option>Sem classificação</option></select><div class="protocol-modal"><span class="ticket-number">123456</span></div>'
                page.route("https://empresa.movidesk.com/**", lambda route: route.fulfill(body=html, content_type="text/html"))
                page.goto("https://empresa.movidesk.com/Ticket/Create")
                fonte = (raiz / "edge_extension/preencher.js").read_text(encoding="utf-8")
                page.add_script_tag(content=fonte.replace("export async function", "async function", 1))
                resultado = page.evaluate("d => preencherFormulario(d)", {"assunto": "CPU - host", "alerta": "CPU", "severidade": "High", "html": "<p>Evidência</p>"})
                self.assertTrue(resultado["ok"])
                self.assertEqual(resultado["campos"]["categoria"], "pendente")
                self.assertEqual(resultado["campos"]["urgencia"], "pendente")
                self.assertEqual(resultado["campos"]["descricao"], "preenchido")
                page.set_content('<input id="TicketSubject"><div contenteditable="true">Assinatura</div><select name="Category"><option value="">Outro</option><option value="1">Alerta</option></select>')
                page.locator("select").evaluate("el => el.addEventListener('change', () => el.value = '')")
                resultado = page.evaluate("d => preencherFormulario(d)", {"assunto": "CPU - host", "html": "<p>Evidência</p>"})
                self.assertEqual(resultado["campos"]["categoria"], "pendente")
                page.locator('[contenteditable="true"]').evaluate("el => el.addEventListener('input', () => el.textContent = 'Texto recusado')")
                resultado = page.evaluate("d => preencherFormulario(d)", {"assunto": "CPU - host", "html": "<p>Evidência</p>"})
                self.assertIn("erro", resultado)
                page.set_content(html)
                page.locator("#TicketSubject").fill("CPU - host")
                page.evaluate("Object.defineProperty(navigator, 'clipboard', {value: {writeText: async texto => {window.copiado = texto;}}})")
                page.add_script_tag(content=(raiz / "edge_extension/movidesk.js").read_text(encoding="utf-8"))
                page.locator("#nocflow-movidesk-utilitarios summary").click()
                page.get_by_role("button", name="Copiar template", exact=True).click()
                self.assertEqual(page.evaluate("window.copiado"), "123456\nCPU - host\nhttps://empresa.movidesk.com/Ticket/Edit/123456")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
