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

    def test_tags_solicitante_servico_e_apontamento_na_mesma_linha(self):
        self.page.set_content('''<form><input id="TicketSubject"><textarea class="description"></textarea>
          <input type="radio" name="tipo" id="pub" checked><label for="pub">Público</label>
          <input type="radio" name="tipo" id="int"><label for="int">Interno</label>
          <label for="client">Solicitante</label><input id="client" class="clients" type="hidden">
          <label for="service">Serviço</label><input id="service" class="service" type="hidden">
          <table><thead><tr><th>Tempo apontado</th><th>Atividade</th></tr></thead><tbody>
          <tr><td><input value="00:00"></td><td><select><option></option><option>Observability</option></select></td></tr>
          <tr><td><input value=""></td><td><select><option></option><option>Observability</option></select></td></tr>
          </tbody></table></form>''')
        self.page.evaluate('''() => {
          const cliente = document.querySelector('#client');
          const servico = document.querySelector('#service');
          let selecionado = null;
          let atualServico = null;
          const select2 = {
            opts: {ajax: {url: '/Ticket/JsonGetClients', type: 'GET',
              data: (q, page) => ({q, pageLimit: 50, page}),
              results: r => ({results: r.results, more: r.more})}},
            data: item => { if (item === undefined) return selecionado; selecionado = item; return select2; }
          };
          const widget = {
            setValue: valor => { atualServico = valor; window.servicoSelecionado = valor; },
            getValue: () => atualServico,
            getOptions: () => ({searchUrl: '/Service/JsonSearchServices', type: 'GET', ticketType: '1',
              urlParameters: {'accessProfileList[0]': 1403}}),
            getItems: () => ({data: []})
          };
          cliente.__noc = {select2};
          Object.assign(servico.__noc = {}, widget);
          window.clienteSelecionado = () => selecionado;
          const jq = alvo => ({
            data(nome, valor) {
              alvo.__noc = alvo.__noc || {};
              if (arguments.length > 1) { alvo.__noc[nome] = valor; return this; }
              if (nome === undefined) return alvo.__noc;
              return alvo.__noc[nome];
            },
            trigger(evento) { alvo.dispatchEvent(new CustomEvent(evento.type, {bubbles: true, detail: evento})); return this; },
            each() { return this; }
          });
          jq.ajax = opcoes => {
            const url = String(opcoes.url);
            let resposta;
            if (url.includes('JsonSearchServices')) {
              window.ultimaBuscaServico = opcoes.data.query;
              resposta = [{Id: 3538, value: JSON.stringify({id: 3538, name: 'Database', path: 'Database', allowSelection: true}),
                html: '<div>Database</div>', items: [
                  {Id: 870802, value: JSON.stringify({id: 870802, name: 'SQL Server', path: 'Database', allowSelection: true}),
                   html: '<div class="notActive">SQL Server</div>', items: []},
                  {Id: 907198, value: JSON.stringify({id: 907198, name: 'SQL Server', path: 'Database', allowSelection: true, allowFinishTicket: true}),
                   html: '<div>SQL Server</div>', items: []}
                ]}];
            } else {
              window.ultimaBuscaSolicitante = opcoes.data.q;
              resposta = {results: [
                {id: '24729635', text: 'Empresa Exemplo Ltda', name: '[Empresa Exemplo] SQLServer | SRVSQL01',
                 personType: 4, email: '', hierarchy: [{id: 22614729, personType: 2}, {id: 22614932, personType: 4}]},
                {id: '34914451', text: 'Empresa Exemplo Ltda', name: 'Contato Exemplo',
                 personType: 1, email: 'contato@example.com', hierarchy: [{id: 22614729, personType: 2}, {id: 22614932, personType: 4}, {id: 31720188, personType: 1}]}
              ], more: false};
            }
            setTimeout(() => opcoes.success(resposta), 0);
          };
          window.jQuery = window.$ = jq;
        }''')
        self.page.add_script_tag(content=(self.raiz / "preencher.js").read_text(encoding="utf-8").replace("export async function", "async function", 1))
        for _ in range(2):
            resultado = self.page.evaluate("() => preencherFormulario({assunto:'Teste',html:'<p>Link</p>',solicitante:'596092884',servico:'DBA SQL'})")
            self.assertTrue(resultado.get("ok"), resultado)
        self.assertTrue(self.page.locator("#int").is_checked())
        self.assertEqual(resultado["campos"]["solicitante"], "preenchido")
        self.assertEqual(resultado["campos"]["servico"], "preenchido")
        self.assertEqual(self.page.evaluate("ultimaBuscaSolicitante"), "596092884")
        self.assertEqual(self.page.evaluate("ultimaBuscaServico"), "SQL Server")
        self.assertEqual(self.page.evaluate("clienteSelecionado().id"), "24729635")
        self.assertEqual(self.page.evaluate("clienteSelecionado().personType"), 4)
        self.assertEqual(self.page.evaluate("servicoSelecionado.id"), 907198)
        self.assertEqual(self.page.evaluate("servicoSelecionado.name"), "SQL Server")
        self.assertEqual(self.page.locator("tbody input").evaluate_all("els => els.map(e => e.value)"), ["00:03", ""])
        self.assertEqual(self.page.locator("tbody select").evaluate_all("els => els.map(e => e.value)"), ["Observability", ""])

    def test_print_usa_upload_do_editor_em_vez_de_base64_no_corpo(self):
        self.page.set_content('<input id="TicketSubject"><div class="fr-element" contenteditable="true"></div>')
        self.page.evaluate('''() => {
          const el = document.querySelector('.fr-element');
          el.innerHTML = '<p>Atenciosamente,</p><p><img src="https://empresa.movidesk.com/Storage/assinatura.png"></p>';
          window.FroalaEditor = {INSTANCES: [{el, html: {get: () => el.innerHTML, set: v => el.innerHTML=v},
            image: {upload: files => { window.arquivos = files.map(f => [f.name, f.type, f.size]);
              el.innerHTML += '<p><img src="https://empresa.movidesk.com/Storage/alerta.png"></p>'; }}}]};
        }''')
        self.page.add_script_tag(content=(self.raiz / "preencher.js").read_text(encoding="utf-8").replace("export async function", "async function", 1))
        resultado = self.page.evaluate("() => preencherFormulario({assunto:'Teste',link_zabbix:'https://zabbix.example.com/tr_events.php?eventid=1',html:'<p><a href=\\\"https://zabbix.example.com/tr_events.php?eventid=1\\\">https://zabbix.example.com/tr_events.php?eventid=1</a></p><img src=\\\"data:image/png;base64,aGVsbG8=\\\">'})")
        self.assertTrue(resultado.get("ok"), resultado)
        self.assertEqual(self.page.evaluate("arquivos[0]"), ["alerta.png", "image/png", 5])
        html = self.page.locator(".fr-element").inner_html()
        self.assertNotIn("base64", html)
        bloco = self.page.locator('[data-nocflow-conteudo="1"]').inner_html()
        self.assertIn("/Storage/alerta.png", bloco)
        self.assertNotIn("/Storage/assinatura.png", bloco)
        self.assertLess(html.index("tr_events.php"), html.index("/Storage/alerta.png"))
        self.assertLess(html.index("/Storage/alerta.png"), html.index("Atenciosamente"))
        self.assertIn("/Storage/assinatura.png", html)

    def test_coleta_tags_sem_duplicar_tecnologia(self):
        self.page.set_content('''<table><tr><td>Tags</td><td>
          <span class="tag">Equipe: DBA MySQL</span><span class="tag">Equipe: DBA mySQL</span>
          <span class="tag">Movidesk: 1249803422</span></td></tr></table>''')
        self.page.add_script_tag(content=(self.raiz / "coletor.js").read_text(encoding="utf-8"))
        dados = self.page.evaluate("() => NOCFlowZabbix.extrair(document, 'https://zabbix.example.com/tr_events.php?eventid=1')")
        from noc.incidentes import importar_eventos, FilaIncidentes
        eventos = importar_eventos({"versao": 1, "origem": "zabbix", "eventos": [dados]})
        fila = FilaIncidentes()
        ids = fila.importar(eventos)
        item = next(i for i in fila.itens if i["id"] == ids[0])
        self.assertEqual(item["dados"]["solicitante"], "1249803422")
        self.assertEqual(item["dados"]["servico"], "MySQL")
        self.page.set_content('''<table><tr><td>Trigger</td><td>MSSQL: SQL Wait Time</td></tr>
          <tr><td>Host</td><td>Servidor Linux SQL</td></tr>
          <tr><td>Tags</td><td><span class="tag">Org: DBA SQL</span><span class="tag">Org: DBA SQLServer</span>
          <span class="tag">Movidesk: 709597589</span></td></tr></table>''')
        self.page.add_script_tag(content=(self.raiz / "coletor.js").read_text(encoding="utf-8"))
        dados_sql = self.page.evaluate("() => NOCFlowZabbix.extrair(document, 'https://zabbix.example.com/tr_events.php?eventid=2')")
        self.assertEqual(dados_sql["servico"], "SQL Server")

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
