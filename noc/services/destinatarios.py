"""Cadastro local de destinatários por empresa."""

import json
import re
from pathlib import Path

from ..infra.persistencia import escrever_texto


def emails(texto: str) -> list[str]:
    resultado = []
    vistos = set()
    for valor in re.split(r"[;,\s]+", texto.strip()):
        if not valor:
            continue
        if not re.fullmatch(r"[^@\s<>;,]+@[^@\s<>;,]+\.[^@\s<>;,]+", valor):
            raise ValueError(f"E-mail inválido: {valor}")
        if valor.casefold() not in vistos:
            resultado.append(valor)
            vistos.add(valor.casefold())
    return resultado


def validar(empresas: list) -> list[dict]:
    if not isinstance(empresas, list):
        raise ValueError("Cadastro de destinatários inválido.")
    resultado, nomes = [], set()
    for item in empresas:
        if not isinstance(item, dict) or not isinstance(item.get("empresa"), str):
            raise ValueError("Empresa inválida no cadastro.")
        nome = item["empresa"].strip()
        if not nome or nome.casefold() in nomes:
            raise ValueError("Informe um nome de empresa único.")
        listas = {}
        for campo in ("para", "cc"):
            valores = item.get(campo)
            if not isinstance(valores, list) or not all(isinstance(v, str) for v in valores):
                raise ValueError("Lista de destinatários inválida.")
            listas[campo] = emails(";".join(valores))
        if not listas["para"] and not listas["cc"]:
            raise ValueError("Informe pelo menos um destinatário em Para ou Cc.")
        nomes.add(nome.casefold())
        resultado.append({"empresa": nome, **listas})
    return sorted(resultado, key=lambda item: item["empresa"].casefold())


def carregar(caminho: Path) -> list[dict]:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Não foi possível ler o cadastro de destinatários. O arquivo foi preservado.") from exc
    if not isinstance(dados, dict) or dados.get("versao") != 1:
        raise ValueError("Versão inválida do cadastro de destinatários.")
    return validar(dados.get("empresas"))


def salvar(caminho: Path, empresas: list) -> list[dict]:
    validadas = validar(empresas)
    escrever_texto(caminho, json.dumps({"versao": 1, "empresas": validadas}, ensure_ascii=False, indent=2))
    return validadas
