"""Sincroniza manifesto/userscripts ou verifica sua versão sem modificar arquivos."""

import argparse
import json
import re
from pathlib import Path

try:
    from .gerar_userscripts import artefatos
except ImportError:
    from gerar_userscripts import artefatos

RAIZ = Path(__file__).resolve().parents[1]


def validar_versao(valor: str) -> str:
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", valor):
        raise ValueError("Use MAJOR.MINOR.PATCH, sem prefixo v nem zeros à esquerda.")
    if any(int(parte) > 65535 for parte in valor.split(".")) or valor == "0.0.0":
        raise ValueError("Versão incompatível com o manifesto da extensão.")
    return valor


def sincronizar(check=False, tag=None):
    versao = validar_versao((RAIZ / "VERSION").read_text(encoding="utf-8").strip())
    if tag is not None and tag != f"v{versao}":
        raise ValueError(f"Tag {tag!r} difere da versão v{versao}.")
    caminho = RAIZ / "edge_extension/manifest.json"
    manifesto = json.loads(caminho.read_text(encoding="utf-8"))
    if check:
        if manifesto.get("version") != versao:
            raise ValueError("Manifesto desatualizado; execute python scripts/versionar.py.")
    else:
        manifesto["version"] = versao
        caminho.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    for nome, conteudo in artefatos():
        destino = RAIZ / "tampermonkey" / nome
        if check:
            if not destino.exists() or destino.read_text(encoding="utf-8") != conteudo:
                raise ValueError(f"Userscript desatualizado: {nome}")
        else:
            destino.write_text(conteudo, encoding="utf-8", newline="\n")
    return versao


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Somente verifica; não altera arquivos")
    parser.add_argument("--tag", help="Exige correspondência exata com a tag de release")
    args = parser.parse_args()
    try:
        print(sincronizar(args.check, args.tag))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
