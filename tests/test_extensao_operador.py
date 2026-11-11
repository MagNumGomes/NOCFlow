import os
from pathlib import Path
import unittest


@unittest.skipUnless(os.getenv("NOC_TEST_BROWSER") == "1", "Defina NOC_TEST_BROWSER=1")
class ExtensaoOperadorTests(unittest.TestCase):
    def setUp(self):
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(channel="chromium", headless=True)
        self.page = self.browser.new_page()
        self.raiz = Path(__file__).resolve().parents[1] / "edge_extension"

    def tearDown(self):
        self.browser.close()
        self.playwright.stop()

    def preencher(self):
        self.page.add_script_tag(content=(self.raiz / "preencher.js").read_text(encoding="utf-8").replace("export async function", "async function", 1))
        return self.page.evaluate("() => preencherFormulario({assunto: 'Teste', html: '<p>Descrição</p>'})")

    def test_interno_independe_do_valor_numerico_e_apontamento_preserva_contabilizado(self):
        self.page.set_content('''<form><input id="TicketSubject"><textarea class="description"></textarea>
          <input type="radio" class="ticketTypeOption" name="tipo" id="publico" value="1" checked><label for="publico">Público</label>
          <input type="radio" class="ticketTypeOption" name="tipo" id="interno" value="2"><label for="interno">Interno</label>
          <input type="radio" class="actionTypeOption" name="acao" id="acao" value="7"><label for="acao">Interna</label>
          <label for="tempo">Tempo apontado</label><input id="tempo" value="00:00">
          <label for="contabilizado">Tempo contabilizado</label><input id="contabilizado" value="00:00" readonly>
          <label for="atividade">Atividade</label><select id="atividade"><option>Outra</option><option value="obs">Observability</option></select>
          </form>''')
        self.page.evaluate("window.eventos = []; document.addEventListener('change', e => eventos.push(e.target.id))")
        resultado = self.preencher()
        self.assertTrue(resultado["ok"])
        for campo in ("tipo", "tempo_apontado", "atividade"):
            self.assertEqual(resultado["campos"][campo], "preenchido")
        self.assertTrue(self.page.locator("#interno").is_checked())
        self.assertFalse(self.page.locator("#publico").is_checked())
        self.assertEqual(self.page.locator("#tempo").input_value(), "00:03")
        self.assertEqual(self.page.locator("#contabilizado").input_value(), "00:00")
        self.assertEqual(self.page.locator("#atividade").input_value(), "obs")
        self.assertIn("interno", self.page.evaluate("eventos"))
        self.page.locator("#tempo").fill("00:15")
        self.assertEqual(self.preencher()["campos"]["tempo_apontado"], "pendente")
        self.assertEqual(self.page.locator("#tempo").input_value(), "00:15")

    def test_horas_recolhidas_e_atividade_ausente_sao_reportadas(self):
        self.page.set_content('''<input id="TicketSubject"><textarea class="description"></textarea>
          <button title="Apontar horas" onclick="document.querySelector('table').hidden=false">Relógio</button>
          <table hidden><thead><tr><th>Tempo apontado</th><th>Tempo contabilizado</th><th>Atividade</th></tr></thead>
          <tbody><tr><td><input value=""></td><td><input value="00:00" readonly></td><td><select><option>Faturada</option></select></td></tr></tbody></table>''')
        campos = self.preencher()["campos"]
        self.assertEqual(campos["tempo_apontado"], "preenchido")
        self.assertEqual(campos["atividade"], "pendente")
        self.assertEqual(campos["tipo"], "nao_localizado")

    def test_whatsapp_assina_rascunho_sem_enviar_nem_duplicar(self):
        self.page.route("https://web.whatsapp.com/**", lambda r: r.fulfill(body='''<div contenteditable="true" role="textbox" id="busca">Busca</div>
          <footer><div contenteditable="true" role="textbox">Olá, <b>equipe</b>!<br>Atualização do atendimento.</div>
          <button onclick="window.enviado=true">Enviar</button></footer>''', content_type="text/html; charset=utf-8"))
        self.page.goto("https://web.whatsapp.com/")
        fonte = (self.raiz / "whatsapp.js").read_text(encoding="utf-8").replace("export function", "function", 1)
        self.page.add_script_tag(content=fonte)
        self.page.evaluate("window.inputs=0; document.querySelector('footer').addEventListener('input', () => inputs++)")
        resultado = self.page.evaluate("() => assinarMensagem('Operador Teste')")
        self.assertNotIn("erro", resultado)
        editor = self.page.locator("footer [contenteditable]")
        self.assertTrue(editor.inner_text().startswith("Operador Teste - Equipe NOC"))
        self.assertIn("Atualização do atendimento.", editor.inner_text())
        self.assertEqual(editor.locator("b").inner_text(), "equipe")
        self.assertGreater(self.page.evaluate("inputs"), 0)
        self.page.evaluate("() => assinarMensagem('Operador Teste')")
        self.assertEqual(editor.inner_text().count("Equipe NOC"), 1)
        self.assertIsNone(self.page.evaluate("window.enviado"))
        self.assertEqual(self.page.locator("#busca").inner_text(), "Busca")
        self.assertIn("erro", self.page.evaluate("() => assinarMensagem('Outra pessoa')"))
        editor.fill("")
        self.assertIn("erro", self.page.evaluate("() => assinarMensagem('Operador Teste')"))

    def test_popup_salva_nome_e_solicita_assinatura_apenas_no_whatsapp(self):
        self.page.set_content((self.raiz / "popup.html").read_text(encoding="utf-8"))
        self.page.evaluate('''() => {
          window.armazenado = {nomeOperadorWhatsApp: 'Nome salvo'};
          window.chrome = {storage: {local: {get: async () => armazenado,
            set: async dados => Object.assign(armazenado, dados)}},
            tabs: {query: async () => [{id: 42, url: 'https://web.whatsapp.com/'}]},
            scripting: {executeScript: async dados => {window.injecao = dados; return [{result: {mensagem: 'Assinatura inserida'}}];}}};
        }''')
        fonte = (self.raiz / "popup.js").read_text(encoding="utf-8").replace('import {assinarMensagem} from "./whatsapp.js";', 'const assinarMensagem = () => {};')
        self.page.add_script_tag(content=fonte, type="module")
        self.page.wait_for_function("document.querySelector('#nome').value === 'Nome salvo'")
        self.page.locator("#nome").fill("  Operador   Teste  ")
        self.page.locator("#assinar").click()
        self.page.wait_for_function("window.injecao")
        self.assertEqual(self.page.evaluate("armazenado.nomeOperadorWhatsApp"), "Operador Teste")
        self.assertEqual(self.page.evaluate("injecao.args"), ["Operador Teste"])
        self.assertEqual(self.page.evaluate("injecao.target.tabId"), 42)
