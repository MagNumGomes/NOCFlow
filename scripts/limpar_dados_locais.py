"""Expurga rascunho, cópias de recuperação e logs com o aplicativo fechado."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noc.infra.persistencia import ExclusividadeDados


def limpar(diretorio):
    dados = diretorio / ".noc_data"
    exclusividade = ExclusividadeDados(dados)
    try:
        arquivos = [dados / "rascunho.json", *dados.glob("rascunho-invalido-*.json"), *dados.glob("logs/noc.jsonl*")]
        for arquivo in arquivos:
            if arquivo.is_file() and not arquivo.is_symlink():
                arquivo.unlink()
    finally:
        exclusividade.fechar()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diretorio", type=Path, required=True, help="Diretório de configuração do NOCFlow")
    limpar(parser.parse_args().diretorio)
