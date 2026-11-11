(() => {
  if (location.origin !== "http://127.0.0.1:18764") return;
  const match = location.pathname.match(/^\/request\/([A-Za-z0-9_-]{43})$/);
  if (!match) return;
  chrome.runtime.sendMessage({tipo: "abrir", token: match[1]}).then(resposta => {
    if (resposta?.erro) document.querySelector("h1").textContent = resposta.erro;
    else if (resposta?.mensagem) {
      document.querySelector("h1").textContent = "Conectado ao NOCFlow";
      document.querySelector("p").textContent = resposta.mensagem;
      for (const p of Array.from(document.querySelectorAll("p")).slice(1)) p.remove();
    }
  }).catch(() => {
    document.querySelector("h1").textContent = "Recarregue a extensão NOCFlow e tente novamente pelo aplicativo.";
  });
})();
