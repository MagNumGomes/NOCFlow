// Função autocontida, injetada somente após o clique na extensão.
export function assinarMensagem(nome) {
  if (location.origin !== "https://web.whatsapp.com") return {erro: "Abra uma conversa no WhatsApp Web."};
  nome = String(nome || "").replace(/\s+/g, " ").trim();
  if (!nome || nome.length > 120) return {erro: "Informe seu nome (até 120 caracteres)."};
  const editores = Array.from(document.querySelectorAll('footer [contenteditable="true"][role="textbox"]'))
    .filter(el => el.getClientRects().length && el.getAttribute("aria-disabled") !== "true");
  if (editores.length !== 1) return {erro: "Não foi possível identificar o campo da mensagem. Abra uma conversa e escreva o texto."};
  const editor = editores[0];
  const texto = editor.innerText.replace(/\u00a0/g, " ");
  if (!texto.trim()) return {erro: "Escreva a mensagem antes de assinar."};
  const assinatura = `${nome} - Equipe NOC`;
  if (texto.trimStart().startsWith(assinatura + "\n") || texto.trim() === assinatura) return {mensagem: "Esta mensagem já está assinada."};
  if (/^.+ - Equipe NOC\s*$/m.test(texto.split("\n")[0])) return {erro: "A mensagem já possui outra assinatura. Revise o nome no texto antes de assinar."};
  editor.focus();
  const selecao = window.getSelection();
  const intervalo = document.createRange();
  intervalo.selectNodeContents(editor);
  intervalo.collapse(true);
  selecao.removeAllRanges();
  selecao.addRange(intervalo);
  // Inserção nativa preserva o restante do rascunho, formatação e histórico de desfazer.
  const inserido = document.execCommand("insertText", false, assinatura + "\n\n");
  if (!inserido || !editor.innerText.startsWith(assinatura)) return {erro: "O editor não confirmou a assinatura. Confira a mensagem."};
  intervalo.selectNodeContents(editor);
  intervalo.collapse(false);
  selecao.removeAllRanges();
  selecao.addRange(intervalo);
  return {mensagem: "Assinatura inserida. Revise e envie pelo WhatsApp."};
}
