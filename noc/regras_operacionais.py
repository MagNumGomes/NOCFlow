"""Perfis privados e decisões determinísticas, com versão, fontes e conflitos."""

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

from .agenda_operacional import calendario_valido, em_janela, fuso, hora
from .atendimento import normalizar, severidade_padrao
from .historico_atendimento import instante, registrar_evento

CONDICOES = {"origem_atendimento", "natureza", "servico", "ambiente", "severidade", "alerta_contem", "tags"}
RESULTADOS = {"prioridade", "equipe", "canais", "politica_ticket", "encerramento", "comunicar_sem_ticket", "prazos"}
MARCOS = {"recebimento": "Recebido", "ticket": "Ticket vinculado", "envio": "Envio registrado",
          "ciencia": "Ciência confirmada", "retorno": "Retorno técnico"}


def _texto(obj, campo, obrigatorio=True):
    valor = obj.get(campo, "")
    if not isinstance(valor, str) or len(valor) > 30000 or (obrigatorio and not valor.strip()):
        raise ValueError(f"Campo obrigatório ou inválido: {campo}.")


def validar_perfis(conteudo):
    if not isinstance(conteudo, dict) or set(conteudo) != {"versao", "perfis"} or conteudo["versao"] != 1:
        raise ValueError("Use um arquivo de perfis versão 1 com a lista perfis.")
    perfis = conteudo["perfis"]
    if not isinstance(perfis, list) or not perfis or len(perfis) > 200:
        raise ValueError("Informe de 1 a 200 perfis.")
    ids = set()
    for perfil in perfis:
        if not isinstance(perfil, dict) or set(perfil) - {"id", "nome", "calendario", "regras"}:
            raise ValueError("Perfil inválido.")
        for campo in ("id", "nome"):
            _texto(perfil, campo)
        if perfil["id"] in ids:
            raise ValueError("Identificador de perfil duplicado.")
        ids.add(perfil["id"])
        calendario_valido(perfil.get("calendario", {}))
        regras = perfil.get("regras")
        if not isinstance(regras, list) or len(regras) > 1000:
            raise ValueError("Lista de regras inválida.")
        regras_ids = set()
        for regra in regras:
            if not isinstance(regra, dict) or set(regra) - {
                "id", "versao", "estado", "fonte", "responsavel", "precedencia", "vigente_de", "vigente_ate",
                "condicoes", "janela", "resultado",
            }:
                raise ValueError("Regra inválida ou com campos desconhecidos.")
            for campo in ("id", "versao", "estado", "fonte", "responsavel"):
                _texto(regra, campo)
            if regra["id"] in regras_ids or regra["estado"] not in ("rascunho", "validada", "suspensa", "substituida"):
                raise ValueError("Regra duplicada ou estado inválido.")
            regras_ids.add(regra["id"])
            if type(regra.get("precedencia")) is not int:
                raise ValueError("Defina a precedência numérica da regra.")
            for campo in ("vigente_de", "vigente_ate"):
                if regra.get(campo):
                    date.fromisoformat(regra[campo])
            if regra.get("vigente_de") and regra.get("vigente_ate") and regra["vigente_de"] > regra["vigente_ate"]:
                raise ValueError("Vigência invertida.")
            condicoes = regra.get("condicoes", {})
            if not isinstance(condicoes, dict) or set(condicoes) - CONDICOES:
                raise ValueError("Condição de regra desconhecida.")
            for valores in condicoes.values():
                if not isinstance(valores, list) or not valores or any(not isinstance(v, str) or not v.strip() for v in valores):
                    raise ValueError("Condições devem conter listas de textos não vazios.")
            janela = regra.get("janela", {})
            if not isinstance(janela, dict) or set(janela) - {"inicio", "fim"}:
                raise ValueError("Janela inválida.")
            hora(janela.get("inicio", "00:00"))
            hora(janela.get("fim", "00:00"))
            resultado = regra.get("resultado")
            if not isinstance(resultado, dict) or not resultado or set(resultado) - RESULTADOS:
                raise ValueError("Resultado de regra inválido.")
            for campo, opcoes in (
                ("politica_ticket", ("novo", "vincular", "decisao_manual")),
                ("encerramento", ("equipe_resolvedora", "apos_envio", "apos_ciencia", "apos_validacao")),
                ("prioridade", ("Desastre", "Alta", "Média", "Aviso", "Informação", "Não classificado")),
            ):
                if campo in resultado and resultado[campo] not in opcoes:
                    raise ValueError(f"Opção inválida: {campo}.")
            if "equipe" in resultado:
                _texto(resultado, "equipe")
            if "comunicar_sem_ticket" in resultado and type(resultado["comunicar_sem_ticket"]) is not bool:
                raise ValueError("comunicar_sem_ticket deve ser booleano.")
            canais = resultado.get("canais", [])
            if not isinstance(canais, list) or any(c not in ("Teams", "WhatsApp", "E-mail", "Telefone") for c in canais):
                raise ValueError("Canais inválidos.")
            prazos = resultado.get("prazos", [])
            if not isinstance(prazos, list):
                raise ValueError("Prazos inválidos.")
            for prazo in prazos:
                if not isinstance(prazo, dict) or set(prazo) != {"acao", "marco", "minutos"}:
                    raise ValueError("Prazo exige ação, marco e minutos.")
                _texto(prazo, "acao")
                if prazo["marco"] not in MARCOS or type(prazo["minutos"]) is not int or not 1 <= prazo["minutos"] <= 525600:
                    raise ValueError("Marco ou duração de prazo inválidos.")
    return deepcopy(perfis)


def carregar_perfis(caminho):
    arquivo = Path(caminho)
    if arquivo.stat().st_size > 2_000_000:
        raise ValueError("Arquivo de perfis excede 2 MB.")
    try:
        return validar_perfis(json.loads(arquivo.read_text(encoding="utf-8-sig")))
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Arquivo de perfis inválido.") from exc


def avaliar_regras(perfis, dados, agora=None):
    perfil = next((p for p in perfis if p["id"] == dados.get("perfil")), None)
    if perfil is None:
        return {"estado": "sem_regra", "mensagem": "Selecione um perfil operacional.", "fontes": [], "resultado": {}}
    momento = instante(agora)
    dia = momento.astimezone(fuso(perfil.get("calendario", {}).get("fuso", "UTC"))).date().isoformat()
    candidatas, incompletas = [], []
    for regra in perfil["regras"]:
        if regra["estado"] != "validada" or (regra.get("vigente_de") and dia < regra["vigente_de"]) or (
                regra.get("vigente_ate") and dia > regra["vigente_ate"]):
            continue
        janela = regra.get("janela", {})
        if not em_janela(momento, perfil.get("calendario", {}), janela.get("inicio", "00:00"), janela.get("fim", "00:00")):
            continue
        faltantes, corresponde = [], True
        for campo, valores in regra.get("condicoes", {}).items():
            valor = dados.get("alerta" if campo == "alerta_contem" else campo, "")
            if not valor:
                faltantes.append(campo)
                continue
            if campo == "severidade":
                corresponde &= severidade_padrao(valor) in [severidade_padrao(v) for v in valores]
            elif campo == "alerta_contem":
                corresponde &= any(normalizar(v) in normalizar(valor) for v in valores)
            elif campo == "tags":
                corresponde &= {normalizar(v.strip()) for v in valores} <= {normalizar(v.strip()) for v in valor.split(",")}
            else:
                corresponde &= normalizar(valor) in [normalizar(v) for v in valores]
        if corresponde:
            (incompletas if faltantes else candidatas).append((regra, faltantes))
    precedencia = max((r["precedencia"] for r, _ in candidatas), default=float("-inf"))
    incertas = [(r, f) for r, f in incompletas if r["precedencia"] >= precedencia]
    escolhidas = [r for r, _ in candidatas if r["precedencia"] == precedencia]
    fontes = [{"id": r["id"], "versao": r["versao"], "fonte": r["fonte"]} for r in escolhidas]
    if incertas:
        return {"estado": "pendente", "mensagem": "Faltam dados para avaliar regras: " + ", ".join(sorted({c for _, f in incertas for c in f})),
                "fontes": fontes + [{"id": r["id"], "versao": r["versao"], "fonte": r["fonte"]} for r, _ in incertas], "resultado": {}}
    if not escolhidas:
        return {"estado": "sem_regra", "mensagem": "Nenhuma regra vigente corresponde ao atendimento.", "fontes": [], "resultado": {}}
    distintos = {json.dumps(r["resultado"], sort_keys=True, ensure_ascii=False) for r in escolhidas}
    if len(distintos) != 1:
        return {"estado": "conflito", "mensagem": "Regras de mesma precedência têm resultados diferentes.", "fontes": fontes, "resultado": {}}
    resultado = deepcopy(escolhidas[0]["resultado"])
    contexto = {
        c: dados.get(c, "") for c in (CONDICOES - {"alerta_contem"}) | {"alerta", "perfil"}}
    return {"estado": "aplicada", "mensagem": "Regra identificada; confira o resultado antes de aplicar.",
            "fontes": fontes, "resultado": resultado, "contexto": contexto, "avaliada_em": momento.isoformat(),
            "assinatura": hashlib.sha256(json.dumps({"perfil": perfil, "contexto": contexto}, sort_keys=True).encode()).hexdigest()}


def aplicar_regra(item, decisao, autor=""):
    if decisao.get("estado") != "aplicada":
        raise ValueError(decisao.get("mensagem", "Regra não resolvida."))
    resultado = decisao["resultado"]
    anterior = item["meta"].get("regra", {}).get("resultado", {})
    for campo, regra_campo in (("prioridade", "prioridade"), ("time_resp", "equipe"), ("acionamento", "equipe")):
        if regra_campo not in resultado and anterior.get(regra_campo) and item["dados"].get(campo) == anterior[regra_campo]:
            item["dados"][campo] = ""
    if resultado.get("prioridade"):
        item["dados"]["prioridade"] = resultado["prioridade"]
    if resultado.get("equipe"):
        item["dados"]["time_resp"] = resultado["equipe"]
        item["dados"]["acionamento"] = resultado["equipe"]
    item["meta"]["regra"] = deepcopy(decisao)
    registrar_evento(item, "Regra aplicada", json.dumps({"fontes": decisao["fontes"], "resultado": resultado}, ensure_ascii=False), autor)


def prazos_atendimento(item, decisao):
    if decisao.get("estado") != "aplicada":
        return []
    prazos = []
    for prazo in decisao["resultado"].get("prazos", []):
        eventos = [e for e in item["meta"].get("historico", []) if e["tipo"] == MARCOS[prazo["marco"]]]
        if eventos:
            # Recebimento/ticket são marcos iniciais; cobranças seguem o retorno mais recente.
            evento = (min if prazo["marco"] in ("recebimento", "ticket") else max)(eventos, key=lambda e: instante(e["em"]))
            prazos.append({**prazo, "prazo": (instante(evento["em"]) + timedelta(minutes=prazo["minutos"])).isoformat(), "registro": evento["id"]})
        else:
            prazos.append({**prazo, "prazo": "", "registro": ""})
    return prazos
