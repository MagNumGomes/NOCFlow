"""Carga de perfis sobre snapshots, apropriada para execução em worker."""

from pathlib import Path

from ..regras_operacionais import carregar_perfis


def ler_perfis(arquivo: str, anterior: tuple | None) -> tuple:
    try:
        caminho = Path(arquivo)
        stat = caminho.stat()
        chave = (str(caminho), stat.st_mtime_ns, stat.st_size)
        return chave, None if chave == anterior else carregar_perfis(caminho), ""
    except (ValueError, OSError) as exc:
        return None, [], f"Perfis indisponíveis: {exc}"
