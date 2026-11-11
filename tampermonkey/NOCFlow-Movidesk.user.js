// ==UserScript==
// @name         NOCFlow - Movidesk - Local
// @namespace    nocflow
// @version      2.1.0
// @description  Copia número, assunto, link e template sem polling periódico
// @match        https://*.movidesk.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

// Gerado por gerar_userscripts.py; edite as fontes em edge_extension/.
/* Utilitários locais também distribuídos como userscript Tampermonkey. */
(() => {
  if (globalThis.nocflowUtilitariosMovidesk || globalThis.nocUtilitariosMovidesk) return;
  globalThis.nocflowUtilitariosMovidesk = globalThis.nocUtilitariosMovidesk = true;
  let timer;
  function numero() {
    const url = new URL(location.href);
    const match = url.pathname.match(/\/Ticket\/(?:Edit|Create)\/(\d+)\/?$/i);
    const id = match?.[1] || url.searchParams.get("id") || "";
    if (/^\d+$/.test(id)) return id;
    const modal = document.querySelector(".protocol-modal");
    const modalNum = modal?.getClientRects().length && getComputedStyle(modal).visibility !== "hidden" ? modal.querySelector(".ticket-number")?.textContent?.trim() : "";
    if (/^\d+$/.test(modalNum)) return modalNum;
    const hiddenNum = document.querySelector(".ticket-number-hidden, input[name='Number']")?.value?.trim();
    if (/^\d+$/.test(hiddenNum)) return hiddenNum;
    return "";
  }
  function assunto() {
    const escopo = document.querySelector("section.tab-ticket.ticket.active, .tab-pane.active") || document;
    const input = escopo.querySelector('input.subject:not([type="hidden"]), input[name="Subject"]:not([type="hidden"]), input[id*="Subject" i]:not([type="hidden"]), input#TicketSubject') ||
      Array.from(document.querySelectorAll('input[name="Subject"], input[id*="Subject" i], input#TicketSubject')).find(el => el.type !== "hidden" && el.getClientRects().length);
    if (input?.getClientRects().length && input.value.trim()) return input.value.trim();
    const el = document.querySelector('[data-field="Subject"], .ticket-subject, #ticketSubject');
    return (el?.innerText || "").trim();
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
      ["Copiar link", linkTicket],
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
