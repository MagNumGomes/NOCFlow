"""Linha do tempo e acompanhamento local, independentes do status remoto."""

from datetime import datetime, timezone
import uuid

TIPOS_EVENTO = (
    "Recebido", "Ticket vinculado", "Mensagem copiada", "Envio registrado",
    "Tentativa de contato", "Ciência confirmada", "Retorno técnico", "Cobrança",
    "Reescalonamento", "Normalização observada", "Validação confirmada",
    "Próxima ação", "Acompanhamento concluído", "Acompanhamento reaberto",
    "Regra aplicada", "Referência vinculada", "Evento relacionado", "Nota",
    "Sugestão IA aplicada", "Coordenação de incidente",
)


def instante(valor=None):
    if valor is None:
        return datetime.now(timezone.utc)
    try:
        data = datetime.fromisoformat(valor) if isinstance(valor, str) else valor
        if not isinstance(data, datetime) or data.tzinfo is None or data.utcoffset() is None:
            raise ValueError
        return data.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Informe data e hora com fuso, por exemplo 2030-01-01T10:00:00-03:00.") from None


def registrar_evento(item, tipo, texto="", autor="", canal="", destinatario="", em=None, fonte="operador"):
    if tipo not in TIPOS_EVENTO:
        raise ValueError("Tipo de registro desconhecido.")
    campos = (texto, autor, canal, destinatario, fonte)
    if any(not isinstance(v, str) or len(v) > 30000 for v in campos):
        raise ValueError("Registro inválido ou muito extenso.")
    evento = dict(id=uuid.uuid4().hex, tipo=tipo, texto=texto.strip(), autor=autor.strip(),
                  canal=canal.strip(), destinatario=destinatario.strip(), em=instante(em).isoformat(), fonte=fonte)
    meta = item["meta"]
    meta.setdefault("historico", []).append(evento)
    if tipo == "Recebido":
        meta.setdefault("recebido_em", evento["em"])
    estados = {"Envio registrado": "Aguardando ciência", "Tentativa de contato": "Aguardando ciência",
               "Ciência confirmada": "Em acompanhamento", "Retorno técnico": "Em acompanhamento",
               "Normalização observada": "Aguardando validação", "Validação confirmada": "Validado",
               "Acompanhamento concluído": "Concluído", "Acompanhamento reaberto": "Em acompanhamento"}
    if tipo in estados:
        acompanhamento = meta.setdefault("acompanhamento", {})
        acompanhamento["estado"] = estados[tipo]
        if tipo == "Acompanhamento concluído":
            acompanhamento.pop("proxima", None)
    return evento


def agendar_acao(item, texto, prazo, responsavel="", autor=""):
    if not texto.strip():
        raise ValueError("Descreva a próxima ação.")
    quando = instante(prazo).isoformat()
    evento = registrar_evento(item, "Próxima ação", texto, autor, destinatario=responsavel)
    item["meta"].setdefault("acompanhamento", {})["proxima"] = {
        "texto": texto.strip(), "prazo": quando, "responsavel": responsavel.strip(), "registro": evento["id"],
    }


def tem_envio(item):
    return any(e["tipo"] == "Envio registrado" for e in item["meta"].get("historico", []))


def pendente_operacional(item, agora=None):
    if item["meta"].get("arquivado"):
        return False
    acompanhamento = item["meta"].get("acompanhamento", {})
    if acompanhamento.get("estado") == "Concluído":
        return False
    proxima = acompanhamento.get("proxima")
    if proxima:
        return instante(proxima["prazo"]) <= instante(agora)
    return acompanhamento.get("estado") in ("Aguardando ciência", "Aguardando validação") or not tem_envio(item)


def concluir_acompanhamento(item, regra, autor=""):
    if regra.get("estado") != "aplicada":
        raise ValueError("Selecione um perfil e resolva as pendências de regra antes de concluir.")
    if not item["dados"].get("ticket") and not item["meta"].get("referencias"):
        raise ValueError("Vincule o chamado antes de concluir o acompanhamento.")
    politica = regra["resultado"].get("encerramento", "equipe_resolvedora")
    historico = item["meta"].get("historico", [])
    reaberturas = [instante(e["em"]) for e in historico if e["tipo"] == "Acompanhamento reaberto"]
    if reaberturas:
        historico = [e for e in historico if instante(e["em"]) >= max(reaberturas)]
    tipos = {e["tipo"] for e in historico}
    exigencias = {"apos_envio": {"Envio registrado"}, "apos_ciencia": {"Ciência confirmada"},
                 "apos_validacao": {"Validação confirmada"}}
    if politica not in exigencias:
        raise ValueError("A conclusão é da equipe resolvedora. Registre o retorno recebido.")
    if not exigencias[politica] <= tipos:
        raise ValueError("Falta o registro exigido pela política de conclusão.")
    registrar_evento(item, "Acompanhamento concluído", "Conclusão local conforme " + politica, autor)


def validar_historico(meta):
    historico = meta.get("historico", [])
    if not isinstance(historico, list):
        raise ValueError("Histórico inválido.")
    ids = set()
    for e in historico:
        if (not isinstance(e, dict) or e.get("tipo") not in TIPOS_EVENTO
                or any(not isinstance(e.get(c), str) for c in ("id", "texto", "autor", "canal", "destinatario", "em", "fonte"))
                or not e["id"] or e["id"] in ids):
            raise ValueError("Registro de histórico inválido.")
        ids.add(e["id"])
        instante(e["em"])
    acompanhamento = meta.get("acompanhamento", {})
    if not isinstance(acompanhamento, dict) or not isinstance(acompanhamento.get("estado", ""), str):
        raise ValueError("Acompanhamento inválido.")
    proxima = acompanhamento.get("proxima")
    if proxima is not None:
        if not isinstance(proxima, dict) or any(not isinstance(proxima.get(c), str) for c in ("texto", "prazo", "responsavel", "registro")):
            raise ValueError("Próxima ação inválida.")
        instante(proxima["prazo"])
    for chave in ("referencias", "relacionados"):
        if chave in meta and not isinstance(meta[chave], list):
            raise ValueError(f"Metadados inválidos: {chave}.")
    if any(not isinstance(v, str) for v in meta.get("relacionados", [])):
        raise ValueError("Relações de atendimento inválidas.")
    for referencia in meta.get("referencias", []):
        if not isinstance(referencia, dict) or any(not isinstance(referencia.get(c), str) for c in ("sistema", "numero", "url")):
            raise ValueError("Referência externa inválida.")
    for campo in ("regra", "coordenacao", "ultima_ia_relato"):
        if campo in meta and not isinstance(meta[campo], dict):
            raise ValueError(f"Metadados inválidos: {campo}.")
