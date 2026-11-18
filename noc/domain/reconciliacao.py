"""Reconciliação de um atendimento removido e depois reimportado."""

from copy import deepcopy

from ..atendimento import link_ticket, ticket_valido
from ..historico_atendimento import instante


def mesclar_atendimento(existente: dict, removido: dict, campos_evento: tuple[str, ...], movidesk_url: str) -> None:
    meta = removido["meta"]
    for campo, valor in removido["dados"].items():
        if not existente["dados"].get(campo):
            existente["dados"][campo] = valor
        elif valor and valor != existente["dados"][campo] and campo in (*campos_evento, "link_zabbix"):
            existente["meta"].setdefault("atualizacoes", {})[campo] = valor
        elif campo == "ticket" and ticket_valido(valor) and valor != existente["dados"][campo]:
            existente["meta"]["ticket_conflito"] = {"ticket": valor, "url": link_ticket(movidesk_url, valor)}
    if existente["imagem"] is None:
        existente["imagem"] = removido["imagem"]
        existente["meta"]["recortes"] = deepcopy(meta.get("recortes", {}))
        existente["meta"]["evidencia_ticket"] = meta.get("evidencia_ticket", "original")
    for chave in ("pedido", "preenchimento", "copias", "arquivado", "arquivado_em", "em_revisao",
                  "acompanhamento", "regra", "coordenacao", "ultima_ia_relato", "recebido_em"):
        if chave in meta:
            existente["meta"].setdefault(chave, deepcopy(meta[chave]))
    historico = {e["id"]: e for e in existente["meta"].get("historico", [])}
    historico.update({e["id"]: deepcopy(e) for e in meta.get("historico", [])})
    existente["meta"]["historico"] = sorted(historico.values(), key=lambda e: instante(e["em"]))
    for chave in ("referencias", "relacionados"):
        valores = existente["meta"].setdefault(chave, [])
        for valor in meta.get(chave, []):
            if valor not in valores:
                valores.append(deepcopy(valor))
    if not existente["meta"].get("comunicacao", {}).get("texto") and meta.get("comunicacao"):
        existente["meta"]["comunicacao"] = deepcopy(meta["comunicacao"])
    existente["meta"]["campos_revisados"] = sorted(set(meta.get("campos_revisados", [])) | set(existente["meta"].get("campos_revisados", [])))
