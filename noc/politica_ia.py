"""Barreira única de saída: opt-in explícito e redação antes do SDK."""

import json
import logging
import re

from .infra.auditoria import registrar

PADROES = (
    r"(?i)\b(?:senha|password|passwd|api[_ -]?key|token|secret|authorization)\s*[:=]\s*[^\s,;]+",
    r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*",
    r"\b(?:gsk_|sk-|AIza)[A-Za-z0-9_-]{16,}\b",
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    r"\b(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:]{0,39}\b",
    r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
    r"(?<!\w)(?:\+55\s*)?\(?\d{2}\)?[ -]?\d{4,5}[ -]?\d{4}(?!\w)",
)


def preparar_texto(config, texto):
    if not config.ia_externa:
        registrar("ia_bloqueada")
        raise ValueError("IA externa bloqueada. Habilite IA_EXTERNA_APROVADA somente após aprovação dos dados e do provedor.")
    if re.search(r"(?i)\b(confidencial|restrito|confidential|restricted)\b|-----BEGIN .*PRIVATE KEY-----", texto):
        registrar("ia_bloqueada")
        raise ValueError("Conteúdo classificado/segredo bloqueado para IA externa.")
    texto = re.sub(r'(?i)"(?:senha|password|passwd|api[_ -]?key|token|secret|authorization)"\s*:\s*"(?:[^"\\]|\\.)*"',
                   '"credencial": "[REMOVIDO]"', texto)
    for padrao in PADROES:
        texto = re.sub(padrao, "[REMOVIDO]", texto)
    registrar("ia_texto_redigido")
    return texto


def confirmar_envio(config, provedor, mensagens):
    if provedor not in ("Groq", "Gemini"):
        raise ValueError("Provedor de IA não aprovado.")
    previa = json.dumps(mensagens, ensure_ascii=False, indent=2)
    if not config.confirmar_ia or not config.confirmar_ia(provedor, previa):
        registrar("ia_bloqueada")
        raise ValueError("Envio à IA cancelado: confirme a prévia do conteúdo redigido.")
    logging.getLogger("noc.seguranca").info(
        "ia_decisao provedor=%s resultado=aprovado classificacao=nao_classificado finalidade=assistencia_operacional origem=operador", provedor)
