// ==UserScript==
// @name         NOCFlow - Movidesk - Local
// @namespace    nocflow
// @version      2.3.0
// @description  Copia número, assunto, link e template sem polling periódico
// @match        https://empresa.movidesk.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

// Gerado por gerar_userscripts.py; edite as fontes em edge_extension/.
/* Utilitários locais também distribuídos como userscript Tampermonkey. */
(() => {
  if (globalThis.nocflowUtilitariosMovidesk || globalThis.nocUtilitariosMovidesk) return;
  globalThis.nocflowUtilitariosMovidesk = globalThis.nocUtilitariosMovidesk = true;
  let timer;
  const visivel = el => Boolean(el?.getClientRects().length) && getComputedStyle(el).visibility !== "hidden";
  const seletoresAssunto = 'input#TicketSubject:not([type="hidden"]), input.subject:not([type="hidden"]), input[name="Subject"]:not([type="hidden"]), input[id*="Subject" i]:not([type="hidden"]), input[placeholder*="Assunto" i]:not([type="hidden"])';
  function escopoAtivo() {
    const abas = Array.from(document.querySelectorAll("section.tab-ticket.ticket.active, .tab-pane.active, form.ticket-form, .container-ticket")).filter(visivel);
    if (abas.length === 1) return abas[0];
    const inputs = Array.from(document.querySelectorAll(seletoresAssunto)).filter(visivel);
    if (inputs.length === 1) {
      return inputs[0].closest("section.tab-ticket, .tab-pane, form.ticket-form, .container-ticket, form") || document;
    }
    return abas[0] || document;
  }
  function numeroNoEscopo(raiz) {
    if (!raiz || raiz === document) return "";
    const hidden = Array.from(raiz.querySelectorAll(".ticket-number-hidden, input[name='Number'], input[name='Id'], input[id*='TicketNumber' i], input[id*='TicketId' i]"))
      .map(el => el.value?.trim())
      .find(val => /^\d+$/.test(val));
    if (hidden) return hidden;
    const texto = Array.from(raiz.querySelectorAll(".ticket-number, .ticket-header-number, [data-ticket-number], [data-ticket-id]"))
      .filter(visivel)
      .map(el => (el.getAttribute("data-ticket-number") || el.getAttribute("data-ticket-id") || el.textContent || "").trim())
      .find(val => /^\d+$/.test(val));
    if (texto) return texto;
    const attr = [raiz.getAttribute?.("data-ticket-number"), raiz.getAttribute?.("data-ticket-id"), raiz.id]
      .map(v => String(v || "").match(/\b(\d{4,})\b/)?.[1])
      .find(Boolean);
    return attr || "";
  }
  function numeroAbaAtiva() {
    const guias = Array.from(document.querySelectorAll(
      '.nav-tabs li.active, .nav-tabs .active, [role="tab"][aria-selected="true"], .tab-header .active, .tabs-ticket .active'
    )).filter(visivel);
    for (const guia of guias) {
      const m = (guia.getAttribute("title") || guia.getAttribute("data-original-title") || guia.textContent || "")
        .trim()
        .match(/\b(\d{4,})\b/);
      if (m) return m[1];
    }
    return "";
  }
  function numero() {
    const modal = Array.from(document.querySelectorAll(".protocol-modal")).find(visivel);
    const modalNum = modal?.querySelector(".ticket-number")?.textContent?.trim();
    if (/^\d+$/.test(modalNum)) return modalNum;
    const escopo = escopoAtivo();
    const numEscopo = numeroNoEscopo(escopo);
    if (numEscopo) return numEscopo;
    const numAba = numeroAbaAtiva();
    if (numAba) return numAba;
    const url = new URL(location.href);
    const match = url.pathname.match(/\/Ticket\/(?:Edit|Create)\/(\d+)\/?$/i);
    const id = match?.[1] || url.searchParams.get("id") || "";
    if (/^\d+$/.test(id)) return id;
    const hiddenGlobal = Array.from(document.querySelectorAll(".ticket-number-hidden, input[name='Number']"))
      .filter(el => {
        const aba = el.closest("section.tab-ticket, .tab-pane, form.ticket-form, .container-ticket");
        return !aba || visivel(aba);
      })
      .map(el => el.value?.trim())
      .find(val => /^\d+$/.test(val));
    if (hiddenGlobal) return hiddenGlobal;
    return "";
  }
  function assunto() {
    const escopo = escopoAtivo();
    const input = Array.from(escopo.querySelectorAll(seletoresAssunto)).find(visivel) ||
      Array.from(document.querySelectorAll(seletoresAssunto)).find(visivel);
    if (input && input.value.trim()) return input.value.trim();
    const el = Array.from(escopo.querySelectorAll('[data-field="Subject"], .ticket-subject, #ticketSubject')).find(visivel) ||
      Array.from(document.querySelectorAll('[data-field="Subject"], .ticket-subject, #ticketSubject')).find(visivel);
    return (el?.innerText || el?.textContent || "").trim();
  }
  function linkTicket() {
    const id = numero();
    if (!id) throw new Error("Salve o ticket para copiar seu link definitivo.");
    const url = new URL(location.href);
    url.pathname = url.pathname.replace(/\/Ticket\/(?:Edit|Create)(?:\/\d+)?\/?$/i, `/Ticket/Edit/${id}`);
    url.search = "";
    url.hash = "";
    return url.href;
  }
  function atualizar() {
    const permitido = /\/Ticket\/(?:Edit|Create)(?:\/\d+)?\/?$/i.test(location.pathname);
    let painel = document.getElementById("nocflow-movidesk-utilitarios") || document.getElementById("noc-movidesk-utilitarios");
    if (!permitido) { painel?.remove(); return; }
    if (painel) return;
    painel = document.createElement("details");
    painel.id = "nocflow-movidesk-utilitarios";
    Object.assign(painel.style, {position: "fixed", bottom: "16px", left: "16px", zIndex: "2147483647", background: "#202630", color: "white", padding: "12px", borderRadius: "8px", font: "13px Segoe UI,sans-serif"});
    const resumo = document.createElement("summary");
    resumo.textContent = "NOCFlow — Zabbix e Movidesk";
    resumo.style.cursor = "pointer";
    painel.append(resumo);
    const status = document.createElement("div");
    status.setAttribute("role", "status");
    for (const [rotulo, obter] of [
      ["Copiar número", () => { if (!numero()) throw new Error("Salve o ticket para obter o número pela URL."); return numero(); }],
      ["Copiar ticket + assunto", () => { if (!assunto()) throw new Error("Assunto não localizado neste layout."); return [numero(), assunto()].filter(Boolean).join(" - "); }],
      ["Copiar template", () => { if (!numero() || !assunto()) throw new Error("Número ou assunto não encontrado. Confira o ticket salvo."); return `${numero()}\n${assunto()}\n${linkTicket()}`; }]
    ]) {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.textContent = rotulo;
      Object.assign(botao.style, {margin: "8px 4px 4px 0", padding: "8px", cursor: "pointer", border: "1px solid #8793a3", borderRadius: "4px", background: "#303d50", color: "white"});
      if (rotulo === "Copiar template") Object.assign(botao.style, {background: "#215dcc", borderColor: "#93b4fa", fontWeight: "600"});
      botao.onclick = async () => { try { await navigator.clipboard.writeText(obter()); status.textContent = "Copiado."; } catch (erro) { status.textContent = erro.message; } };
      painel.append(botao);
    }
    painel.append(status);
    document.body.append(painel);
  }
  new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(atualizar, 200); }).observe(document.body, {childList: true, subtree: true});
  window.addEventListener("popstate", atualizar);
  atualizar();
})();
