(() => {
  if (globalThis.nocflowPreenchimentoAtivo || globalThis.nocPreenchimentoAtivo) return;
  globalThis.nocflowPreenchimentoAtivo = globalThis.nocPreenchimentoAtivo = true;
  let timer, fallback, ocupado = false, ativo = true, retentativasFalha = 0;
  const observador = new MutationObserver(mudancas => {
    if (mudancas.some(m => !m.target.closest?.(".nocflow-aviso, .noc-aviso"))) agendar();
  });
  function parar() {
    ativo = false;
    observador.disconnect();
    clearTimeout(timer);
    clearTimeout(fallback);
    document.removeEventListener("load", agendar, true);
    globalThis.nocflowPreenchimentoAtivo = globalThis.nocPreenchimentoAtivo = false;
  }
  function mostrar(texto, erro) {
    let aviso = document.querySelector(".nocflow-aviso");
    if (!aviso) {
      aviso = document.createElement("div");
      aviso.className = "nocflow-aviso noc-aviso";
      Object.assign(aviso.style, {position: "fixed", bottom: "20px", right: "20px", zIndex: "2147483647", maxWidth: "440px", padding: "16px", color: "white", borderRadius: "8px", font: "14px Segoe UI,sans-serif", boxShadow: "0 4px 12px rgba(0,0,0,0.3)"});
      document.body.append(aviso);
    }
    aviso.textContent = texto;
    aviso.style.background = erro ? "#b42318" : "#175cd3";
    setTimeout(() => aviso.remove(), 12000);
  }
  function agendar() {
    if (!ativo || ocupado) return;
    clearTimeout(timer);
    timer = setTimeout(tentar, 250);
  }
  async function tentar() {
    if (!ativo || ocupado) return;
    ocupado = true;
    clearTimeout(fallback);
    try {
      const resposta = await chrome.runtime.sendMessage({tipo: "preencher"});
      retentativasFalha = 0;
      if (resposta?.mensagem) mostrar(resposta.mensagem, Boolean(resposta.erro));
      if (!resposta?.aguardar && !resposta?.aguardando_ticket) parar();
      else if (resposta.aguardar) fallback = setTimeout(tentar, 1000);
    } catch {
      retentativasFalha++;
      if (retentativasFalha < 15) {
        fallback = setTimeout(tentar, 1000);
      } else {
        parar();
      }
    }
    finally { ocupado = false; }
  }
  observador.observe(document.body, {
    childList: true, subtree: true, characterData: true,
    attributes: true, attributeFilter: ["class", "style", "hidden"]
  });
  document.addEventListener("load", agendar, true);
  tentar();
})();
