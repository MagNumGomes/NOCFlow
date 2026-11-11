import {assinarMensagem} from "./whatsapp.js";

const nome = document.getElementById("nome");
const status = document.getElementById("status");
const assinar = document.getElementById("assinar");
const carregado = chrome.storage.local.get("nomeOperadorWhatsApp").then(dados => {
  nome.value = dados.nomeOperadorWhatsApp || "";
}).catch(() => { status.textContent = "Não foi possível carregar o nome salvo."; });

async function salvar() {
  const valor = nome.value.replace(/\s+/g, " ").trim();
  if (!valor || valor.length > 120) throw new Error("Informe seu nome (até 120 caracteres).");
  await chrome.storage.local.set({nomeOperadorWhatsApp: valor});
  nome.value = valor;
  return valor;
}
document.getElementById("salvar").addEventListener("click", async () => {
  try { await carregado; await salvar(); status.textContent = "Nome salvo neste navegador."; }
  catch (erro) { status.textContent = erro.message; }
});
assinar.addEventListener("click", async () => {
  assinar.disabled = true;
  try {
    await carregado;
    const valor = await salvar();
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.url || new URL(tab.url).origin !== "https://web.whatsapp.com") throw new Error("Abra uma conversa no WhatsApp Web e clique na extensão novamente.");
    const [resposta] = await chrome.scripting.executeScript({target: {tabId: tab.id}, func: assinarMensagem, args: [valor]});
    status.textContent = resposta?.result?.erro || resposta?.result?.mensagem || "Não foi possível acessar o campo da mensagem.";
  } catch (erro) { status.textContent = erro.message; }
  finally { assinar.disabled = false; }
});
