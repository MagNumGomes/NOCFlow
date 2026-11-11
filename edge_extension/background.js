import {preencherFormulario} from "./preencher.js";

const PONTE = "http://127.0.0.1:18764";
const ZABBIX = new Set(["https://zabbix.example.com", "https://zabbix-secondary.example.com"]);
const chave = tabId => `nocflow:${tabId}`;
const emAndamento = new Set();

async function consultar(token) {
  const resposta = await fetch(`${PONTE}/api/request/${token}`, {
    headers: {"X-NOC-Token": token}, cache: "no-store", signal: AbortSignal.timeout(5000)
  });
  if (!resposta.ok) throw new Error("Pedido encerrado ou expirado. Conecte ou abra o ticket novamente pelo NOCFlow.");
  return resposta.json();
}

async function informar(token, tipo, mensagem = "", extra = {}) {
  const resposta = await fetch(`${PONTE}/api/result/${token}`, {
    method: "POST", headers: {"Content-Type": "application/json", "X-NOC-Token": token},
    body: JSON.stringify({tipo, mensagem, ...extra}), signal: AbortSignal.timeout(5000)
  });
  if (!resposta.ok) throw new Error("Pedido expirado ou dados inválidos. Confira o NOCFlow e conecte novamente.");
}

async function abrir(mensagem, sender) {
  const origem = new URL(sender.url);
  if (sender.frameId !== 0 || origem.origin !== PONTE || origem.pathname !== `/request/${mensagem.token}` ||
      !/^[A-Za-z0-9_-]{43}$/.test(mensagem.token)) throw new Error("Solicitação NOCFlow inválida.");
  const dados = await consultar(mensagem.token);
  if (dados.tipo === "conectar") {
    await chrome.storage.session.set({conexaoNocFlow: {token: mensagem.token, expira: Date.now() + 43200000}});
    await informar(mensagem.token, "ok");
    await chrome.alarms.create("nocflow-conexao", {periodInMinutes: 1});
    return {mensagem: "NOCFlow conectado. Use Enviar ao NOCFlow nas páginas do Zabbix. Você pode fechar esta guia."};
  }
  if (dados.tipo === "retomar") {
    try {
      const registros = await chrome.storage.session.get(null);
      const registro = Object.entries(registros).find(([k, v]) => k.startsWith("nocflow:") && v.token === dados.token_original);
      if (!registro) throw new Error("Guia não localizada nesta sessão. Informe o ticket salvo no NOCFlow.");
      const tab = await chrome.tabs.get(Number(registro[0].slice("nocflow:".length)));
      if (new URL(tab.url).origin !== new URL(registro[1].url).origin) throw new Error("A guia mudou de site. Confira o ticket no Movidesk.");
      await chrome.tabs.update(tab.id, {active: true});
      await chrome.windows.update(tab.windowId, {focused: true});
      await informar(mensagem.token, "ok");
      // Só a guia local temporária desta retomada é fechada.
      await chrome.tabs.remove(sender.tab.id);
      return {ok: true};
    } catch (erro) {
      await informar(mensagem.token, "erro", erro.message).catch(() => {});
      throw erro;
    }
  }
  const destino = new URL(dados.url);
  if (!["http:", "https:"].includes(destino.protocol)) throw new Error("Endereço do Movidesk inválido.");
  await chrome.storage.session.set({[chave(sender.tab.id)]: {
    token: mensagem.token, url: destino.href, fase: "preencher", expira: Date.now() + (dados.timeout_login || 120) * 1000,
    retorno: dados.timeout_retorno || 28800
  }});
  await informar(mensagem.token, "progresso", "Extensão conectada. Abrindo Movidesk na sua sessão do Edge…");
  await chrome.tabs.update(sender.tab.id, {url: destino.href, active: true});
  return {ok: true};
}

function numeroTicket(href, pedido) {
  const atual = new URL(href), destino = new URL(pedido.url);
  if (atual.origin !== destino.origin) return "";
  const base = destino.pathname.replace(/\/Ticket\/Create\/?$/i, "");
  const caminho = atual.pathname.slice(base.length);
  if (!atual.pathname.startsWith(base)) return "";
  const match = caminho.match(/^\/Ticket\/(?:Edit|Create)\/(\d+)\/?$/i);
  if (match) return match[1];
  if (/^\/Ticket\/(?:Edit|Create)\/?$/i.test(caminho)) {
    const id = atual.searchParams.get("id") || "";
    if (/^\d+$/.test(id)) return id;
  }
  return "";
}

async function preencher(sender) {
  if (sender.frameId !== 0) return {};
  const id = sender.tab.id;
  const pedido = (await chrome.storage.session.get(chave(id)))[chave(id)];
  if (!pedido) return {};
  if (emAndamento.has(id)) return {aguardar: true};
  emAndamento.add(id);
  try {
    if (Date.now() >= pedido.expira) throw new Error("Prazo do pedido encerrado. Informe o ticket no NOCFlow manualmente.");
    const tab = await chrome.tabs.get(id);
    const atual = new URL(tab.url), destino = new URL(pedido.url);
    if (atual.origin !== destino.origin) return {aguardar: true};
    if (pedido.fase === "salvar") {
      let ticket = numeroTicket(tab.url, pedido);
      if (!ticket) {
        try {
          const resModal = await chrome.scripting.executeScript({
            target: {tabId: id},
            func: () => {
              const modal = document.querySelector(".protocol-modal");
              if (modal?.getClientRects().length && getComputedStyle(modal).visibility !== "hidden") {
                const num = modal.querySelector(".ticket-number")?.textContent?.trim();
                if (/^\d+$/.test(num)) return num;
              }
              return "";
            }
          });
          ticket = resModal[0]?.result || "";
        } catch {}
      }
      if (!ticket) return {aguardando_ticket: true};
      const url = new URL(pedido.url);
      url.pathname = url.pathname.replace(/\/Ticket\/Create\/?$/i, `/Ticket/Edit/${ticket}`);
      url.search = "";
      url.hash = "";
      await informar(pedido.token, "ticket", "", {ticket, url: url.href});
      await chrome.storage.session.remove(chave(id));
      return {mensagem: `NOCFlow: ticket ${ticket} devolvido ao incidente correspondente.`};
    }
    const dados = await consultar(pedido.token);
    const respostas = await chrome.scripting.executeScript({target: {tabId: id}, world: "MAIN", func: preencherFormulario, args: [dados]});
    if (respostas[0]?.result?.aguardar) return {aguardar: true};
    if (respostas[0]?.result?.erro) throw new Error(respostas[0].result.erro);
    if (!respostas[0]?.result?.ok) throw new Error("Não foi possível preencher o editor. Revise a guia aberta.");
    const campos = respostas[0].result.campos || {};
    await informar(pedido.token, "ok", "", {campos});
    await chrome.storage.session.set({[chave(id)]: {...pedido, fase: "salvar", expira: Date.now() + pedido.retorno * 1000}});
    const nomes = {assunto: "título", descricao: "descrição", tipo: "tipo/ação interna", categoria: "categoria", urgencia: "urgência", tempo_apontado: "tempo apontado (00:03)", atividade: "atividade (Observability)"};
    const pendentes = Object.entries(campos).filter(([, estado]) => estado !== "preenchido").map(([campo]) => nomes[campo]);
    const detalhe = pendentes.length ? ` Confira os campos pendentes: ${pendentes.join(", ")}.` : " Campos confirmados.";
    return {aguardando_ticket: true, mensagem: `NOCFlow: título e descrição preenchidos.${detalhe} Revise e salve; o número será devolvido ao aplicativo.`};
  } catch (erro) {
    const mensagem = erro.message || String(erro);
    await informar(pedido.token, "erro", mensagem).catch(() => {});
    await chrome.storage.session.remove(chave(id));
    return {erro: mensagem, mensagem: `NOCFlow: ${mensagem}`};
  } finally { emAndamento.delete(id); }
}

async function zabbix(mensagem, sender) {
  if (sender.frameId !== 0 || !ZABBIX.has(new URL(sender.url).origin)) throw new Error("Origem Zabbix não configurada.");
  if (mensagem.tipo === "carregar_renderizador") {
    await chrome.scripting.executeScript({target: {tabId: sender.tab.id}, files: ["vendor/html2canvas.min.js"]});
    return {ok: true};
  }
  const conexao = (await chrome.storage.session.get("conexaoNocFlow")).conexaoNocFlow;
  if (!conexao || Date.now() >= conexao.expira) throw new Error("No aplicativo, clique em Conectar Zabbix ao NOCFlow primeiro.");
  const payload = mensagem.payload;
  if (!Array.isArray(payload?.eventos) || !payload.eventos.length || payload.eventos.length > 100 ||
      payload.eventos.some(e => new URL(e.link_zabbix).origin !== new URL(sender.url).origin)) throw new Error("Lote de eventos inválido.");
  await informar(conexao.token, "importar", "", {payload});
  return {ok: true};
}

chrome.runtime.onMessage.addListener((mensagem, sender, responder) => {
  if (!sender.tab || sender.id !== chrome.runtime.id) return;
  const tarefa = mensagem.tipo === "abrir" ? abrir(mensagem, sender) :
    mensagem.tipo === "preencher" ? preencher(sender) :
    ["importar_zabbix", "carregar_renderizador"].includes(mensagem.tipo) ? zabbix(mensagem, sender) : Promise.resolve({});
  tarefa.then(responder).catch(erro => responder({erro: erro.message || String(erro)}));
  return true;
});

// onUpdated cobre mudanças de URL por History API e navegações após salvar.
chrome.tabs.onUpdated.addListener((id, mudancas, tab) => {
  if (mudancas.url) preencher({tab, frameId: 0}).catch(() => {});
});
chrome.tabs.onRemoved.addListener(async id => {
  const pedido = (await chrome.storage.session.get(chave(id)))[chave(id)];
  await chrome.storage.session.remove(chave(id));
  if (pedido) await informar(pedido.token, "erro", "Guia fechada. Se o ticket foi salvo, informe seu número manualmente no NOCFlow.").catch(() => {});
});

// Um sinal por minuto, somente no loopback; não consulta Zabbix ou Movidesk.
chrome.alarms.onAlarm.addListener(async alarme => {
  if (alarme.name !== "nocflow-conexao") return;
  const {conexaoNocFlow: conexao} = await chrome.storage.session.get("conexaoNocFlow");
  if (!conexao || Date.now() >= conexao.expira) {
    await chrome.alarms.clear(alarme.name);
    await chrome.storage.session.remove("conexaoNocFlow");
    return;
  }
  try { await informar(conexao.token, "sinal"); }
  catch {
    await chrome.storage.session.remove("conexaoNocFlow");
    await chrome.alarms.clear(alarme.name);
  }
});
