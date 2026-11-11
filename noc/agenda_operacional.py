"""Calendários e ocorrências persistentes; cálculo sem IA e com fusos explícitos."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import uuid

from .historico_atendimento import instante


def fuso(nome):
    try:
        return ZoneInfo(nome)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError("Fuso desconhecido. Use um nome IANA, como UTC ou America/Sao_Paulo.") from None


def hora(valor):
    try:
        if not isinstance(valor, str) or len(valor) != 5:
            raise ValueError
        return datetime.strptime(valor, "%H:%M").time()
    except (TypeError, ValueError):
        raise ValueError("Horário inválido; use HH:MM.") from None


def calendario_valido(calendario):
    if not isinstance(calendario, dict) or set(calendario) - {"fuso", "dias", "feriados", "ignorar_feriados"}:
        raise ValueError("Calendário inválido.")
    fuso(calendario.get("fuso", "UTC"))
    dias = calendario.get("dias", list(range(7)))
    feriados = calendario.get("feriados", [])
    if not isinstance(dias, list) or not dias or any(type(d) is not int or d not in range(7) for d in dias):
        raise ValueError("Dias devem ser uma lista de 0 (segunda) a 6 (domingo).")
    if not isinstance(feriados, list) or type(calendario.get("ignorar_feriados", True)) is not bool:
        raise ValueError("Feriados inválidos.")
    for d in feriados:
        try:
            if not isinstance(d, str):
                raise ValueError
            date.fromisoformat(d)
        except ValueError:
            raise ValueError("Feriado inválido; use AAAA-MM-DD.") from None


def dia_permitido(dia, calendario):
    return dia.weekday() in calendario.get("dias", list(range(7))) and not (
        calendario.get("ignorar_feriados", True) and dia.isoformat() in calendario.get("feriados", []))


def em_janela(agora, calendario, inicio="00:00", fim="00:00"):
    local = instante(agora).astimezone(fuso(calendario.get("fuso", "UTC")))
    a, b = hora(inicio), hora(fim)
    if a == b:
        return dia_permitido(local.date(), calendario)
    if a < b:
        return dia_permitido(local.date(), calendario) and a <= local.time() < b
    # Janela noturna pertence ao dia em que se iniciou.
    dia = local.date() if local.time() >= a else local.date() - timedelta(days=1)
    return dia_permitido(dia, calendario) and (local.time() >= a or local.time() < b)


def proximo_horario(rotina, depois):
    limite = instante(depois)
    calendario = rotina["calendario"]
    zona = fuso(calendario.get("fuso", "UTC"))
    inicio = limite.astimezone(zona).date()
    horarios = [hora(h) for h in rotina["horarios"]]
    for n in range(370):
        dia = inicio + timedelta(days=n)
        if not dia_permitido(dia, calendario):
            continue
        candidatos = []
        for h in horarios:
            local = datetime.combine(dia, h, zona)
            utc = local.astimezone(timezone.utc)
            # Horários inexistentes na transição de verão não geram ocorrência.
            if utc.astimezone(zona).replace(tzinfo=None) != datetime.combine(dia, h):
                continue
            if utc > limite:
                candidatos.append(utc)
        if candidatos:
            return min(candidatos).isoformat()
    raise ValueError("Nenhum horário disponível no calendário nos próximos 370 dias.")


def validar_rotina(rotina):
    if not isinstance(rotina, dict):
        raise ValueError("Rotina inválida.")
    for campo in ("id", "titulo", "proxima", "tipo", "responsavel", "esperado", "url"):
        if not isinstance(rotina.get(campo), str):
            raise ValueError(f"Campo de rotina inválido: {campo}.")
    if not rotina["titulo"].strip() or rotina["tipo"] not in ("única", "intervalo", "horários"):
        raise ValueError("Informe título e tipo da rotina.")
    instante(rotina["proxima"])
    calendario_valido(rotina.get("calendario", {}))
    if type(rotina.get("ativa", True)) is not bool:
        raise ValueError("Estado da rotina inválido.")
    tolerancia = rotina.get("tolerancia_minutos", 0)
    if type(tolerancia) is not int or not 0 <= tolerancia <= 10080:
        raise ValueError("Tolerância deve estar entre 0 e 10080 minutos.")
    if rotina["tipo"] == "intervalo":
        minutos = rotina.get("intervalo_minutos")
        if type(minutos) is not int or not 1 <= minutos <= 525600:
            raise ValueError("Intervalo deve estar entre 1 e 525600 minutos.")
    if rotina["tipo"] == "horários":
        horarios = rotina.get("horarios")
        if not isinstance(horarios, list) or not horarios or len(horarios) > 96:
            raise ValueError("Informe de 1 a 96 horários.")
        for h in horarios:
            hora(h)
    dependencias = rotina.get("dependencias", [])
    if not isinstance(dependencias, list) or any(not isinstance(d, str) or d == rotina["id"] for d in dependencias):
        raise ValueError("Dependências inválidas.")


def criar_rotina(titulo, proxima, tipo="única", responsavel="", esperado="", url="", calendario=None,
                 intervalo_minutos=60, horarios=None, dependencias=None, tolerancia_minutos=0):
    from .configuracao import url_valida
    if url and not url_valida(url):
        raise ValueError("URL da rotina inválida.")
    rotina = dict(id=uuid.uuid4().hex, titulo=titulo.strip(), proxima=instante(proxima).isoformat(), tipo=tipo,
                  responsavel=responsavel.strip(), esperado=esperado.strip(), url=url.strip(), ativa=True,
                  calendario=calendario or {"fuso": "UTC"}, intervalo_minutos=intervalo_minutos,
                  horarios=horarios or [], dependencias=dependencias or [], tolerancia_minutos=tolerancia_minutos)
    validar_rotina(rotina)
    return rotina


def registrar_execucao(estado, identificador, resultado, evidencia, autor="", em=None):
    rotina = next((r for r in estado.get("rotinas", []) if r["id"] == identificador), None)
    if rotina is None or not rotina.get("ativa", True):
        raise ValueError("Rotina não encontrada ou inativa.")
    if resultado not in ("OK", "Falha", "Não executada") or not evidencia.strip():
        raise ValueError("Informe resultado e evidência/justificativa.")
    quando = instante(em)
    previsto = instante(rotina["proxima"])
    if quando < previsto:
        raise ValueError("Esta ocorrência ainda não está no horário previsto.")
    execucoes = estado.get("execucoes", [])
    if any(e["rotina"] == identificador and e["prevista"] == rotina["proxima"] for e in execucoes):
        raise ValueError("Ocorrência já registrada.")
    if resultado == "OK":
        dia = previsto.astimezone(fuso(rotina["calendario"].get("fuso", "UTC"))).date()
        for dependencia in rotina.get("dependencias", []):
            registros = [e for e in execucoes if e["rotina"] == dependencia and instante(e["em"]) <= quando
                         and instante(e["prevista"]).astimezone(fuso(rotina["calendario"].get("fuso", "UTC"))).date() == dia]
            ultimo = max(registros, key=lambda e: instante(e["em"]), default=None)
            if ultimo is None or ultimo["resultado"] != "OK":
                raise ValueError("Dependência ainda não concluída com sucesso no dia da ocorrência.")
    proxima = None
    if rotina["tipo"] == "horários":
        proxima = proximo_horario(rotina, previsto)
    elif rotina["tipo"] == "intervalo":
        candidato = previsto + timedelta(minutes=rotina["intervalo_minutos"])
        for _ in range(370):
            local = candidato.astimezone(fuso(rotina["calendario"].get("fuso", "UTC")))
            if dia_permitido(local.date(), rotina["calendario"]):
                break
            candidato = datetime.combine(local.date() + timedelta(days=1), time.min, local.tzinfo).astimezone(timezone.utc)
        else:
            raise ValueError("Calendário sem próxima execução disponível.")
        proxima = candidato.isoformat()
    registro = dict(id=uuid.uuid4().hex, rotina=identificador, titulo=rotina["titulo"], prevista=rotina["proxima"],
                    em=quando.isoformat(), resultado=resultado, evidencia=evidencia.strip(), autor=autor.strip(),
                    limite=(previsto + timedelta(minutes=rotina.get("tolerancia_minutos", 0))).isoformat())
    estado.setdefault("execucoes", []).append(registro)
    if proxima:
        rotina["proxima"] = proxima
    else:
        rotina["ativa"] = False
    return registro


def validar_agenda(estado):
    if not isinstance(estado, dict):
        raise ValueError("Estado operacional inválido.")
    rotinas, execucoes = estado.get("rotinas", []), estado.get("execucoes", [])
    if not isinstance(rotinas, list) or not isinstance(execucoes, list):
        raise ValueError("Agenda inválida.")
    ids = set()
    for rotina in rotinas:
        validar_rotina(rotina)
        if rotina["id"] in ids:
            raise ValueError("Rotina duplicada.")
        ids.add(rotina["id"])
    for rotina in rotinas:
        if not set(rotina.get("dependencias", [])) <= ids:
            raise ValueError("Dependência de rotina não encontrada.")
    mapa = {r["id"]: r.get("dependencias", []) for r in rotinas}
    visitados = set()
    def visitar(identificador, caminho):
        if identificador in caminho:
            raise ValueError("Ciclo nas dependências de rotinas.")
        if identificador not in visitados:
            for dependencia in mapa[identificador]:
                visitar(dependencia, caminho | {identificador})
            visitados.add(identificador)
    for identificador in mapa:
        visitar(identificador, set())
    for e in execucoes:
        if not isinstance(e, dict) or any(not isinstance(e.get(c), str) for c in
                                         ("id", "rotina", "titulo", "prevista", "em", "resultado", "evidencia", "autor")):
            raise ValueError("Execução de rotina inválida.")
        instante(e["em"])
        instante(e["prevista"])
        if "limite" in e:
            instante(e["limite"])
        if e["resultado"] not in ("OK", "Falha", "Não executada"):
            raise ValueError("Resultado de execução inválido.")
    for campo in ("arquivo_perfis", "diretorio_conhecimento"):
        if not isinstance(estado.get(campo, ""), str):
            raise ValueError("Caminho de configuração inválido.")
    if not isinstance(estado.get("passagens", []), list):
        raise ValueError("Passagens inválidas.")
    for passagem in estado.get("passagens", []):
        if not isinstance(passagem, dict) or any(not isinstance(passagem.get(c), str) for c in ("em", "responsavel", "observacao", "resumo")):
            raise ValueError("Registro de passagem inválido.")
        instante(passagem["em"])
