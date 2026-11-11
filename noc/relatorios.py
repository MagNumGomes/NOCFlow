"""Diário, passagem e indicadores reproduzíveis a partir dos registros locais."""

from collections import Counter
import csv
import io

from .historico_atendimento import instante


def eventos_periodo(itens, inicio, fim):
    a, b = instante(inicio), instante(fim)
    if a >= b:
        raise ValueError("O fim do período deve ser posterior ao início.")
    eventos = []
    for item in itens:
        for evento in item["meta"].get("historico", []):
            if a <= instante(evento["em"]) < b:
                eventos.append({**evento, "atendimento": item["id"], "ticket": item["dados"].get("ticket", ""),
                                "resumo": item["dados"].get("alerta", "")})
    return sorted(eventos, key=lambda e: (instante(e["em"]), e["id"]))


def diario_bordo(itens, inicio, fim):
    eventos = eventos_periodo(itens, inicio, fim)
    linhas = [f"Diário de bordo — [{inicio}, {fim})", f"Registros: {len(eventos)}", ""]
    for e in eventos:
        linhas.extend([f"[{e['em']}] {e['tipo']} · Ticket {e['ticket'] or 'não informado'} · {e['resumo']}",
                       f"Autor: {e['autor'] or 'não informado'} · Canal: {e['canal'] or '—'} · Destino: {e['destinatario'] or '—'}",
                       e["texto"], f"Fonte: atendimento {e['atendimento']} / registro {e['id']}", ""])
    return "\n".join(linhas)


def passagem_turno(itens, estado, agora=None):
    momento = instante(agora)
    linhas = [f"Passagem de turno — {momento.isoformat()}"]
    for item in itens:
        meta, d = item["meta"], item["dados"]
        if meta.get("arquivado") or meta.get("acompanhamento", {}).get("estado") == "Concluído" or not any(d.values()):
            continue
        acomp = meta.get("acompanhamento", {})
        linhas.extend(["", f"{d.get('alerta', '')} · Ticket {d.get('ticket') or 'não informado'}",
                       f"Estado local: {acomp.get('estado', 'Em triagem')} · Equipe: {d.get('time_resp') or 'não informada'}"])
        for tipo in ("Envio registrado", "Ciência confirmada", "Retorno técnico", "Normalização observada"):
            registros = [e for e in meta.get("historico", []) if e["tipo"] == tipo]
            if registros:
                e = max(registros, key=lambda e: instante(e["em"]))
                linhas.append(f"{tipo}: {e['em']} · {e['texto']} [registro {e['id']}]")
        proxima = acomp.get("proxima")
        linhas.append(f"Próxima ação: {proxima['texto']} · {proxima['prazo']} · {proxima['responsavel'] or 'sem responsável'}"
                      if proxima else "Próxima ação: não definida")
        linhas.append(f"Fonte: atendimento {item['id']}")
    linhas.append("\nRotinas pendentes:")
    for rotina in estado.get("rotinas", []):
        if rotina.get("ativa", True):
            vencida = instante(rotina["proxima"]) <= momento
            linhas.append(f"{'VENCIDA' if vencida else 'Prevista'} · {rotina['titulo']} · {rotina['proxima']} [rotina {rotina['id']}]")
    return "\n".join(linhas)


def indicadores(itens, estado, inicio, fim):
    eventos = eventos_periodo(itens, inicio, fim)
    a, b = instante(inicio), instante(fim)
    tipos = Counter(e["tipo"] for e in eventos)
    execucoes = [e for e in estado.get("execucoes", []) if a <= instante(e["prevista"]) < b]
    realizados = [e for e in execucoes if e["resultado"] != "Não executada"]
    duracoes = {}
    consultas_ia = [m for item in itens for m in item["meta"].get("assistente_metricas", [])
                    if a <= instante(m["em"]) < b]
    for nome, marco in (("registro", "Ticket vinculado"), ("notificacao", "Envio registrado"), ("ciencia", "Ciência confirmada")):
        amostras = []
        for item in itens:
            hist = item["meta"].get("historico", [])
            recebidos = [instante(e["em"]) for e in hist if e["tipo"] == "Recebido"]
            finais = [instante(e["em"]) for e in hist if e["tipo"] == marco]
            if recebidos and finais:
                recebido = min(recebidos)
                final = min(finais)
                if a <= recebido < b and final >= recebido and final < b:
                    amostras.append((final - recebido).total_seconds())
        duracoes[nome] = {"amostras": len(amostras), "media_segundos": sum(amostras) / len(amostras) if amostras else None}
    return {"inicio_inclusivo": a.isoformat(), "fim_exclusivo": b.isoformat(),
            "escopo": "Registros locais disponíveis; não representa o inventário completo dos sistemas remotos.",
            "eventos": dict(tipos), "tempos_desde_recebimento": duracoes,
            "assistente": {"consultas": sum(m["tarefa"] != "aplicar_sugestoes" for m in consultas_ia),
                           "tokens_reportados": sum(m.get("tokens") or 0 for m in consultas_ia),
                           "consultas_sem_tokens_reportados": sum(m["tarefa"] != "aplicar_sugestoes" and m.get("tokens") is None for m in consultas_ia),
                           "campos_aplicados": sum(m.get("aplicados", 0) for m in consultas_ia)},
            "rotinas_registradas": len(execucoes), "rotinas_executadas": len(realizados),
            "rotinas_executadas_no_prazo": sum(instante(e["em"]) <= instante(e.get("limite", e["prevista"])) for e in realizados),
            "percentual_pontual_das_executadas": (100 * sum(instante(e["em"]) <= instante(e.get("limite", e["prevista"])) for e in realizados) / len(realizados)) if realizados else None,
            "rotinas_com_falha": sum(e["resultado"] == "Falha" for e in execucoes),
            "rotinas_nao_executadas": sum(e["resultado"] == "Não executada" for e in execucoes)}


def exportar_csv(itens, inicio, fim):
    saida = io.StringIO(newline="")
    campos = ("em", "atendimento", "ticket", "resumo", "tipo", "autor", "canal", "destinatario", "texto", "id")
    writer = csv.DictWriter(saida, fieldnames=campos, extrasaction="ignore")
    writer.writeheader()
    for e in eventos_periodo(itens, inicio, fim):
        # Exportação de relatos para planilha não deve virar fórmula executável.
        writer.writerow({c: "'" + str(e[c]) if str(e[c]).lstrip().startswith(("=", "+", "-", "@")) else e[c] for c in campos})
    return saida.getvalue()
