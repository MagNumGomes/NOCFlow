"""Busca local em procedimentos explicitamente selecionados pelo operador."""

import json
from pathlib import Path
import re
from datetime import date

from .atendimento import normalizar


def carregar_base(diretorio):
    raiz = Path(diretorio).resolve()
    indice = raiz / "indice.json"
    if indice.stat().st_size > 1_000_000:
        raise ValueError("Índice de conhecimento excede 1 MB.")
    dados = json.loads(indice.read_text(encoding="utf-8-sig"))
    if not isinstance(dados, dict) or dados.get("versao") != 1 or not isinstance(dados.get("documentos"), list):
        raise ValueError("Use indice.json versão 1 com a lista documentos.")
    if len(dados["documentos"]) > 500:
        raise ValueError("Limite de 500 documentos por base.")
    documentos, ids = [], set()
    tamanho = 0
    for doc in dados["documentos"]:
        if not isinstance(doc, dict) or any(not isinstance(doc.get(c), str) or not doc[c].strip()
                                           for c in ("id", "titulo", "versao", "estado", "arquivo")):
            raise ValueError("Metadados de documento incompletos.")
        if doc["id"] in ids:
            raise ValueError("Documento duplicado no índice.")
        ids.add(doc["id"])
        for campo in ("perfis", "servicos"):
            if not isinstance(doc.get(campo, []), list) or any(not isinstance(v, str) for v in doc.get(campo, [])):
                raise ValueError("Aplicabilidade de documento inválida.")
        if doc["estado"] != "validado":
            continue
        for campo in ("vigente_de", "vigente_ate"):
            if doc.get(campo):
                date.fromisoformat(doc[campo])
        arquivo = (raiz / doc["arquivo"]).resolve()
        if not arquivo.is_relative_to(raiz) or arquivo.suffix.lower() != ".md":
            raise ValueError("Procedimentos devem ser Markdown dentro da pasta selecionada.")
        tamanho += arquivo.stat().st_size
        if arquivo.stat().st_size > 300_000 or tamanho > 10_000_000:
            raise ValueError("Base muito grande; limite de 300 KB por documento e 10 MB no total.")
        texto = arquivo.read_text(encoding="utf-8-sig")
        secao, linhas, secoes = "Introdução", [], []
        for linha in texto.splitlines():
            if re.match(r"^#{1,6}\s", linha):
                if linhas:
                    secoes.append((secao, "\n".join(linhas)))
                secao, linhas = linha.lstrip("# "), []
            else:
                linhas.append(linha)
        if linhas:
            secoes.append((secao, "\n".join(linhas)))
        documentos.append({**doc, "secoes": secoes})
    return documentos


def buscar(documentos, consulta, perfil="", servico="", hoje=None, limite=6):
    termos = set(re.findall(r"\w{3,}", normalizar(consulta))) - {"qual", "como", "para", "com", "uma", "que", "dos", "das"}
    if not termos:
        return []
    dia = (hoje or date.today()).isoformat()
    encontrados = []
    for doc in documentos:
        if doc.get("perfis") and perfil not in doc["perfis"]:
            continue
        if doc.get("servicos") and normalizar(servico) not in [normalizar(s) for s in doc["servicos"]]:
            continue
        if (doc.get("vigente_de") and dia < doc["vigente_de"]) or (doc.get("vigente_ate") and dia > doc["vigente_ate"]):
            continue
        for n, (secao, texto) in enumerate(doc["secoes"]):
            palavras = set(re.findall(r"\w+", normalizar(doc["titulo"] + " " + secao + " " + texto)))
            pontos = len(termos & palavras)
            if pontos:
                encontrados.append({"id": f"{doc['id']}:{doc['versao']}:{n}", "titulo": doc["titulo"], "versao": doc["versao"],
                                    "secao": secao, "texto": texto[:6000], "pontos": pontos})
    return sorted(encontrados, key=lambda d: (-d["pontos"], d["id"]))[:limite]
