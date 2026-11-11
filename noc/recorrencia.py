"""Auditoria determinística de recorrência sobre um retrato da fila local."""

from .atendimento import normalizar, ticket_valido
from .historico_atendimento import instante


def _rotulo(valor):
    return " ".join(valor.split())


def _recebido(meta):
    valores = [meta.get("recebido_em")]
    valores += [e.get("em") for e in meta.get("historico", []) if e.get("tipo") == "Recebido"]
    datas = []
    for valor in valores:
        if valor:
            try:
                datas.append(instante(valor))
            except ValueError:
                pass
    return min(datas) if datas else None


def analisar_recorrencia(itens, inicio=None, fim=None, incluir_arquivados=False, por_ativo=False, em=None):
    if (inicio is None) != (fim is None):
        raise ValueError("Informe início e fim do período.")
    a, b = (instante(inicio), instante(fim)) if inicio is not None else (None, None)
    if a is not None and a >= b:
        raise ValueError("O fim deve ser posterior ao início.")
    grupos, tickets = {}, set()
    sem_ticket = sem_data = fora_periodo = arquivados = registros = 0
    for item in itens:
        dados, meta = item["dados"], item["meta"]
        if not any(dados.values()):
            continue
        if meta.get("arquivado") and not incluir_arquivados:
            arquivados += 1
            continue
        ticket = dados.get("ticket", "").strip()
        if not ticket_valido(ticket):
            sem_ticket += 1
            continue
        recebido = _recebido(meta)
        if recebido is None:
            sem_data += 1
            if a is not None:
                continue
        if a is not None and not a <= recebido < b:
            fora_periodo += 1
            continue
        registros += 1
        # Números com zeros iniciais representam o mesmo ticket Movidesk.
        ticket = str(int(ticket))
        tickets.add(ticket)
        campos = ("perfil", "servico", "alerta") + (("servidor",) if por_ativo else ())
        rotulos = {c: _rotulo(dados.get(c, "")) for c in campos}
        chave = tuple(normalizar(rotulos[c]) for c in campos)
        grupo = grupos.setdefault(chave, {"campos": rotulos, "tickets": set(), "registros": [], "datas": []})
        grupo["tickets"].add(ticket)
        if recebido is not None:
            grupo["datas"].append(recebido)
        grupo["registros"].append({"id": item["id"], "ticket": ticket,
            "servidor": dados.get("servidor", ""), "recebido": recebido.isoformat() if recebido else "",
            "arquivado": bool(meta.get("arquivado"))})
    ranking = []
    for grupo in grupos.values():
        ids = sorted(grupo["tickets"], key=int)
        ranking.append({"campos": grupo["campos"], "tickets": ids, "quantidade": len(ids),
            "percentual": 100 * len(ids) / len(tickets), "registros": grupo["registros"],
            "primeiro": min(grupo["datas"]).isoformat() if grupo["datas"] else "",
            "ultimo": max(grupo["datas"]).isoformat() if grupo["datas"] else ""})
    ranking.sort(key=lambda g: (-g["quantidade"], tuple(normalizar(v) for v in g["campos"].values())))
    return {"gerado_em": instante(em).isoformat(), "inicio": a.isoformat() if a else "",
        "fim": b.isoformat() if b else "", "incluir_arquivados": incluir_arquivados, "por_ativo": por_ativo,
        "tickets_distintos": len(tickets), "registros_analisados": registros, "sem_ticket": sem_ticket,
        "sem_data": sem_data, "fora_periodo": fora_periodo, "arquivados_excluidos": arquivados,
        "grupos_recorrentes": sum(g["quantidade"] >= 2 for g in ranking), "ranking": ranking}


def formatar_recorrencia(relatorio):
    r = relatorio
    linhas = ["Auditoria de recorrência — tickets da fila", f"Gerado em: {r['gerado_em']}",
        "Escopo: fila local completa, independentemente dos filtros visuais; não consulta o histórico remoto.",
        "Arquivados: " + ("incluídos" if r["incluir_arquivados"] else "excluídos"),
        (f"Recebimento local: [{r['inicio']}, {r['fim']})" if r["inicio"] else "Período: todos os registros disponíveis"),
        "Agrupamento: perfil + serviço + resumo" + (" + ativo" if r["por_ativo"] else ""),
        "Comparação ignora caixa, acentos e espaços repetidos; números e demais diferenças são preservados.",
        "Um ticket conta uma vez por grupo. Um mesmo ticket em grupos diferentes pode elevar a soma dos percentuais acima de 100%.",
        "Recorrência indica dois ou mais tickets distintos com o mesmo agrupamento; não comprova causa comum.", "",
        f"Tickets distintos: {r['tickets_distintos']} | Registros analisados: {r['registros_analisados']}",
        f"Grupos recorrentes: {r['grupos_recorrentes']}",
        f"Sem ticket válido (excluídos): {r['sem_ticket']} | Arquivados excluídos: {r['arquivados_excluidos']}",
        f"Sem data de recebimento: {r['sem_data']} ({'excluídos pelo filtro' if r['inicio'] else 'incluídos'})",
        f"Fora do período: {r['fora_periodo']}", "", "Ranking de problemas"]
    if not r["ranking"]:
        linhas.append("Nenhum ticket encontrado para os critérios selecionados.")
    for n, grupo in enumerate(r["ranking"], 1):
        campos = grupo["campos"]
        linhas.extend(["", f"{n}. {campos['alerta'] or '(resumo não informado)'}",
            f"Perfil: {campos['perfil'] or 'não informado'} | Serviço: {campos['servico'] or 'não informado'}"])
        if r["por_ativo"]:
            linhas.append(f"Ativo: {campos['servidor'] or 'não informado'}")
        linhas.extend([f"Frequência: {grupo['quantidade']} ticket(s) distinto(s) — {grupo['percentual']:.1f}% dos tickets analisados",
            "Tickets: " + ", ".join(grupo["tickets"]),
            f"Primeiro / último recebimento local: {grupo['primeiro'] or 'sem data'} / {grupo['ultimo'] or 'sem data'}",
            "Referências da fila:"])
        for registro in grupo["registros"]:
            linhas.append(f"  Ticket {registro['ticket']} | Ativo: {_rotulo(registro['servidor']) or 'não informado'} | "
                          f"Recebido: {registro['recebido'] or 'sem data'} | Atendimento {registro['id']}"
                          + (" | Arquivado" if registro["arquivado"] else ""))
    return "\n".join(linhas)
