(() => {
  if (document.getElementById("nocflow-zabbix") || document.getElementById("noc-zabbix")) return;
  const coletor = globalThis.NOCFlowZabbix || globalThis.NocZabbix;
  const extensao = typeof chrome !== "undefined" && Boolean(chrome.runtime?.id);
  const lista = new URL(location.href).searchParams.get("action") === "problem.view";
  if (!lista && !location.pathname.endsWith("/tr_events.php")) return;
  const painel = document.createElement("details");
  painel.id = "noc-zabbix";
  Object.assign(painel.style, {position: "fixed", bottom: "16px", left: "16px", zIndex: "2147483647", background: "#202630", color: "white", padding: "12px", borderRadius: "8px", font: "13px Segoe UI,sans-serif", maxWidth: "520px"});
  const titulo = document.createElement("summary");
  titulo.textContent = "NOCFlow — Zabbix e Movidesk";
  titulo.style.cursor = "pointer";
  painel.append(titulo);
  const botoes = document.createElement("div");
  Object.assign(botoes.style, {display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "10px"});
  const extras = document.createElement("details");
  const resumoExtras = document.createElement("summary");
  resumoExtras.textContent = "Mais opções";
  Object.assign(resumoExtras.style, {cursor: "pointer", marginTop: "10px"});
  const secundarios = document.createElement("div");
  Object.assign(secundarios.style, {display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px"});
  extras.append(resumoExtras, secundarios);
  const status = document.createElement("div");
  status.setAttribute("role", "status");
  status.style.marginTop = "8px";
  painel.append(botoes, extras, status);
  document.body.append(painel);
  let ocupado = false, carregandoRenderizador, cacheImagem;
  function botao(nome, acao, principal = false) {
    const el = document.createElement("button");
    el.type = "button";
    el.textContent = nome;
    Object.assign(el.style, {padding: "8px", cursor: "pointer", border: "1px solid #8793a3", borderRadius: "4px", background: "#303d50", color: "white"});
    if (principal) Object.assign(el.style, {background: "#215dcc", borderColor: "#93b4fa", fontWeight: "600"});
    el.onclick = async () => {
      if (ocupado) return;
      ocupado = true;
      for (const b of painel.querySelectorAll("button")) b.disabled = true;
      status.textContent = "Processando localmente…";
      try { status.textContent = await acao() || "Copiado."; }
      catch (erro) { status.textContent = erro.message || String(erro); }
      finally { ocupado = false; for (const b of painel.querySelectorAll("button")) b.disabled = false; }
    };
    (principal ? botoes : secundarios).append(el);
  }
  async function mensagem(dados) {
    const resposta = await chrome.runtime.sendMessage(dados);
    if (resposta?.erro) throw new Error(resposta.erro);
    if (!resposta?.ok) throw new Error("Recarregue a extensão NOCFlow em edge://extensions e atualize a página (F5).");
    return resposta;
  }
  const blobParaDataUrl = blob => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
  async function renderizador() {
    if (typeof globalThis.html2canvas === "function") return;
    if (!carregandoRenderizador) carregandoRenderizador = (async () => {
      if (extensao) await mensagem({tipo: "carregar_renderizador"});
      else {
        const amd = globalThis.define?.amd;
        if (amd) delete globalThis.define.amd;
        try {
          await new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
            script.onload = resolve;
            script.onerror = () => reject(new Error("Não foi possível carregar o renderizador. A cópia de dados continua disponível."));
            document.head.append(script);
          });
        } finally {
          if (amd && globalThis.define) globalThis.define.amd = amd;
        }
      }
      if (typeof globalThis.html2canvas !== "function") {
        throw new Error("Renderizador indisponível. Recarregue a extensão NOCFlow em edge://extensions e atualize a página (F5).");
      }
    })().catch(erro => { carregandoRenderizador = null; throw erro; });
    await carregandoRenderizador;
  }
  async function imagem() {
    const linhas = coletor.linhasRotuladas(document);
    const selecionadas = ["servidor", "alerta", "severidade"].map(c => {
      const opcoes = linhas.filter(l => l.campo === c);
      if (new Set(opcoes.map(l => l.valor)).size > 1) throw new Error(`Mais de um valor de ${c} na página. Use Win+Shift+S para a evidência.`);
      return opcoes[0]?.linha;
    });
    if (selecionadas.some(l => !l)) throw new Error("Host, Trigger e Severity não foram localizados para a imagem.");
    const chave = location.href + selecionadas.map(l => l.outerHTML + [l, ...l.cells].map(el => {
      const s = getComputedStyle(el);
      return s.color + s.backgroundColor + s.font + el.getBoundingClientRect().width;
    }).join("")).join("") + devicePixelRatio;
    if (cacheImagem?.chave === chave) return cacheImagem.blob;
    await renderizador();
    const wrapper = document.createElement("div");
    const estilo = getComputedStyle(selecionadas[0].closest("table"));
    Object.assign(wrapper.style, {position: "fixed", left: "-20000px", top: "0", padding: "10px", background: getComputedStyle(document.body).backgroundColor, color: estilo.color, font: estilo.font});
    const tabela = selecionadas[0].closest("table").cloneNode(false);
    tabela.removeAttribute("id");
    tabela.style.width = `${Math.ceil(selecionadas[0].closest("table").getBoundingClientRect().width)}px`;
    const corpo = document.createElement("tbody");
    for (const linha of selecionadas) corpo.append(linha.cloneNode(true));
    tabela.append(corpo);
    wrapper.append(tabela);
    document.body.append(wrapper);
    try {
      const canvas = await globalThis.html2canvas(wrapper, {scale: devicePixelRatio || 1, backgroundColor: getComputedStyle(document.body).backgroundColor});
      const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("Não foi possível gerar a imagem.");
      cacheImagem = {chave, blob};
      return blob;
    } finally { wrapper.remove(); }
  }
  async function payload(incluirImagem = false) {
    const eventos = lista ? await coletor.completar(coletor.selecionados(document, location.href)) : [coletor.extrair(document, location.href)];
    if (!lista && (incluirImagem || cacheImagem?.blob)) {
      try {
        eventos[0].imagem_base64 = await blobParaDataUrl(await imagem());
      } catch (erro) { eventos[0].aviso = `Dados coletados sem imagem: ${erro.message || erro}`.slice(0, 1200); }
    }
    return {versao: 1, origem: "zabbix", eventos};
  }
  async function copiarComImagem(texto, cabecalho) {
    const img = document.createElement("img");
    img.src = await blobParaDataUrl(await imagem());
    img.alt = "Host / Trigger / Severity";
    img.style.maxWidth = "100%";
    const paragrafo = document.createElement("p");
    paragrafo.append(img);
    const conteudo = document.createElement("div");
    conteudo.append(cabecalho, paragrafo);
    await navigator.clipboard.write([new ClipboardItem({
      "text/plain": new Blob([texto], {type: "text/plain"}),
      "text/html": new Blob([conteudo.outerHTML], {type: "text/html"})
    })]);
  }
  botao(lista ? "Copiar selecionados para NOCFlow" : "Copiar dados para NOCFlow", async () => {
    await navigator.clipboard.writeText(JSON.stringify(await payload(extensao)));
    return "Dados copiados. Use Importar dados no aplicativo NOCFlow.";
  }, !extensao);
  if (extensao) botao(lista ? "Enviar selecionados ao NOCFlow" : "Enviar ao NOCFlow", async () => {
    const dados = await payload(true);
    await mensagem({tipo: "importar_zabbix", payload: dados});
    const avisos = dados.eventos.filter(e => e.aviso).length;
    return `${dados.eventos.length} evento(s) enviado(s) à fila do NOCFlow.${avisos ? ` ${avisos} com pendências de coleta; confira no aplicativo.` : ""}`;
  }, true);
  if (lista) {
    botao("Selecionar primeiras N linhas", async () => {
      const valor = prompt("Quantas linhas selecionar? (1–100)", "4");
      if (valor === null) return "Cancelado.";
      return `${coletor.selecionar(document, location.href, Number(valor))} linha(s) selecionada(s).`;
    }, true);
    botao("Copiar links selecionados", async () => navigator.clipboard.writeText(coletor.selecionados(document, location.href).map(e => e.link_zabbix).join("\n")));
    return;
  }
  botao("Copiar link", async () => navigator.clipboard.writeText(location.href));
  botao("Copiar Trigger - Host", async () => {
    const d = coletor.extrair(document, location.href);
    await navigator.clipboard.writeText(`${d.alerta} - ${d.servidor}`);
  });
  botao("Copiar chamado reconhecido", async () => {
    const numero = coletor.numeroChamado(document);
    if (!numero) throw new Error("Chamado não encontrado na tabela de reconhecimentos.");
    await navigator.clipboard.writeText(numero);
  });
  const template = d => `Prezados,\n\nRecebemos o seguinte alerta:\n\nN° do Ticket criado:\nAlerta: ${d.alerta}\nSeveridade: ${d.severidade}\nServidor: ${d.servidor}\nDados operacionais: ${d.situacao}\nHorário da Falha: ${d.horario}`;
  botao("Copiar imagem Host / Trigger / Severity", async () => navigator.clipboard.write([new ClipboardItem({"image/png": await imagem()})]));
  botao("Copiar link + imagem", async () => {
    const link = document.createElement("a");
    link.href = location.href;
    link.textContent = location.href;
    const cabecalho = document.createElement("p");
    cabecalho.append(link);
    await copiarComImagem(location.href, cabecalho);
    return "Link e imagem copiados.";
  }, true);
  botao("Copiar e-mail + imagem", async () => {
    const texto = template(coletor.extrair(document, location.href));
    const pre = document.createElement("div");
    pre.style.whiteSpace = "pre-wrap";
    pre.textContent = texto;
    await copiarComImagem(texto, pre);
  });
})();
