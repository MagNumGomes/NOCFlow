/* Coletor compartilhado pela extensão, userscript e fixtures de navegador. */
(() => {
  const campos = ["alerta", "servidor", "severidade", "situacao", "horario"];
  const normalizar = texto => (texto || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ").trim().replace(/:$/, "").toLowerCase();
  const rotulos = {
    host: "servidor", servidor: "servidor", trigger: "alerta", "event name": "alerta", "nome do evento": "alerta",
    gatilho: "alerta", severity: "severidade", severidade: "severidade", "operational data": "situacao",
    "dados operacionais": "situacao", time: "horario", hora: "horario", horario: "horario"
  };
  function texto(el) {
    if (!el) return "";
    if (el.ownerDocument.defaultView && typeof el.innerText === "string") return el.innerText.replace(/\r/g, "").trim();
    const clone = el.cloneNode(true);
    for (const br of clone.querySelectorAll("br")) br.replaceWith("\n");
    for (const bloco of clone.querySelectorAll("p, div, li")) bloco.append("\n");
    for (const oculto of clone.querySelectorAll("script, style, [hidden]")) oculto.remove();
    return (clone.textContent || "").replace(/\r/g, "").trim();
  }
  function urlEvento(link, base) {
    try {
      const url = new URL(link, base);
      if (!/^https?:$/.test(url.protocol) || url.origin !== new URL(base).origin ||
          !/^\d+$/.test(url.searchParams.get("eventid") || "") || !url.pathname.endsWith("/tr_events.php")) return null;
      return url;
    } catch { return null; }
  }
  function linhasRotuladas(doc) {
    return Array.from(doc.querySelectorAll("tr")).flatMap(linha => {
      const celulas = Array.from(linha.cells);
      if (celulas.length !== 2) return [];
      const campo = rotulos[normalizar(texto(celulas[0]))];
      return campo ? [{campo, valor: texto(celulas[1]), linha}] : [];
    });
  }
  function extrair(doc, href) {
    const url = urlEvento(href, href);
    if (!url) throw new Error("Abra o detalhe de um evento Zabbix com eventid.");
    const dados = Object.fromEntries(campos.map(c => [c, ""]));
    const linhas = linhasRotuladas(doc);
    for (const campo of campos) {
      const valores = [...new Set(linhas.filter(l => l.campo === campo && l.valor).map(l => l.valor))];
      if (valores.length === 1) dados[campo] = valores[0];
    }
    // Alguns layouts mostram Time como cabeçalho na tabela de eventos.
    if (!dados.horario) {
      const candidatos = Array.from(doc.querySelectorAll("tr")).filter(l =>
        Array.from(l.querySelectorAll("a[href]")).some(a => urlEvento(a.getAttribute("href"), href)?.searchParams.get("eventid") === url.searchParams.get("eventid")));
      const horas = [...new Set(candidatos.flatMap(l => {
        const cabecalho = l.closest("table")?.querySelector("thead tr");
        const indice = Array.from(cabecalho?.cells || []).findIndex(c => rotulos[normalizar(texto(c))] === "horario");
        return indice >= 0 && l.cells[indice] ? [texto(l.cells[indice])] : [];
      }))];
      if (horas.length === 1) dados.horario = horas[0];
    }
    return {...dados, link_zabbix: url.href, eventid: url.searchParams.get("eventid")};
  }
  function selecionados(doc, href) {
    const eventos = new Map();
    for (const checkbox of doc.querySelectorAll('tbody input[type="checkbox"]:checked')) {
      const linha = checkbox.closest("tr");
      const url = Array.from(linha?.querySelectorAll("a[href]") || []).map(a => urlEvento(a.getAttribute("href"), href)).find(Boolean);
      if (!url) continue;
      const dados = Object.fromEntries(campos.map(c => [c, ""]));
      const cabecalhos = Array.from(linha.closest("table").querySelector("thead tr")?.cells || []);
      cabecalhos.forEach((c, indice) => {
        const nome = normalizar(texto(c));
        const campo = rotulos[nome] || ({problem: "alerta", problema: "alerta", problems: "alerta"})[nome];
        if (campo) dados[campo] = texto(linha.cells[indice]);
      });
      eventos.set(url.href, {...dados, link_zabbix: url.href, eventid: url.searchParams.get("eventid")});
    }
    if (!eventos.size) throw new Error("Selecione as linhas dos eventos na lista do Zabbix.");
    if (eventos.size > 100) throw new Error("Selecione no máximo 100 eventos por importação.");
    return [...eventos.values()];
  }
  async function completar(eventos, buscar = fetch) {
    const resultado = eventos.map(e => ({...e}));
    let indice = 0;
    async function trabalhar() {
      while (indice < resultado.length) {
        const evento = resultado[indice++];
        if (campos.every(c => evento[c])) continue;
        try {
          const resposta = await buscar(evento.link_zabbix, {credentials: "same-origin", signal: AbortSignal.timeout(8000)});
          if (!resposta.ok || new URL(resposta.url || evento.link_zabbix).origin !== new URL(evento.link_zabbix).origin) throw new Error("Detalhe indisponível");
          const doc = new DOMParser().parseFromString(await resposta.text(), "text/html");
          const detalhe = extrair(doc, evento.link_zabbix);
          for (const campo of campos) if (!evento[campo]) evento[campo] = detalhe[campo];
        } catch { evento.aviso = "Detalhe indisponível; revise os campos vazios no NOCFlow."; }
      }
    }
    await Promise.all([trabalhar(), trabalhar()]);
    return resultado;
  }
  function selecionar(doc, href, quantidade) {
    if (!Number.isInteger(quantidade) || quantidade < 1 || quantidade > 100) throw new Error("Informe um número inteiro de 1 a 100.");
    const caixas = Array.from(doc.querySelectorAll('tbody input[type="checkbox"]')).filter(c =>
      !c.disabled && Array.from(c.closest("tr")?.querySelectorAll("a[href]") || []).some(a => urlEvento(a.getAttribute("href"), href)));
    for (const caixa of caixas.slice(0, quantidade)) if (!caixa.checked) caixa.click();
    return Math.min(quantidade, caixas.length);
  }
  function numeroChamado(doc) {
    // Procura somente no histórico de reconhecimentos, nunca em todos os números da página.
    const tabelas = Array.from(doc.querySelectorAll("table")).filter(t => {
      const cabecalho = normalizar(texto(t.querySelector("thead")));
      const contexto = texto(t.previousElementSibling) + " " + texto(t.closest("section, fieldset")?.querySelector("h2, h3, legend"));
      return /acknowledg|reconhec/i.test(cabecalho + " " + t.id + " " + contexto) ||
        (/message|mensagem|comment|comentario/.test(cabecalho) && /user|usuario/.test(cabecalho));
    });
    for (const tabela of tabelas) {
      const indice = Array.from(tabela.querySelector("thead tr")?.cells || []).findIndex(c => /^(?:message|mensagem|comment|comentario)$/.test(normalizar(texto(c))));
      const celulas = indice >= 0 ? Array.from(tabela.querySelectorAll("tbody tr")).map(l => l.cells[indice]) : Array.from(tabela.querySelectorAll(".message-cell, tbody tr td:nth-child(3)"));
      for (const celula of celulas) {
        const mensagem = texto(celula);
        const prefixado = mensagem.match(/\b(?:INC|CHG|TASK|REQ|SD|WO|TICKET)\d{5,}\b/i);
        const rotulado = mensagem.match(/\b(?:ticket|chamado|movidesk)\s*[:#-]?\s*(\d{5,})\b/i);
        if (prefixado) return prefixado[0];
        if (rotulado) return rotulado[1];
        if (/^\d{5,}$/.test(mensagem)) return mensagem;
      }
    }
    return "";
  }
  globalThis.NOCFlowZabbix = globalThis.NocZabbix = {campos, extrair, selecionados, completar, selecionar, linhasRotuladas, numeroChamado};
})();
