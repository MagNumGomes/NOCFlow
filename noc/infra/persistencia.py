"""Escrita transacional no mesmo volume e exclusividade do diretório de dados."""

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, TextIO


@contextmanager
def arquivo_atomico(destino: Path, encoding: str | None = "utf-8") -> Iterator[TextIO | BinaryIO]:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(prefix=f".{destino.name}-", suffix=".tmp", dir=destino.parent)
    temporario = Path(nome)
    try:
        with os.fdopen(fd, "w" if encoding else "wb", encoding=encoding) as arquivo:
            yield arquivo
            arquivo.flush()
            os.fsync(arquivo.fileno())
        temporario.replace(destino)
    finally:
        temporario.unlink(missing_ok=True)


def escrever_texto(destino: Path, texto: str, encoding: str = "utf-8") -> None:
    with arquivo_atomico(destino, encoding) as arquivo:
        arquivo.write(texto)


def escrever_bytes(destino: Path, conteudo: bytes) -> None:
    with arquivo_atomico(destino, encoding=None) as arquivo:
        arquivo.write(conteudo)


class ExclusividadeDados:
    """Lock liberado pelo SO mesmo após encerramento inesperado do processo."""

    def __init__(self, diretorio: Path):
        diretorio.mkdir(parents=True, exist_ok=True)
        self.arquivo = (diretorio / "sessao.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                if self.arquivo.seek(0, 2) == 0:
                    self.arquivo.write(b"0")
                    self.arquivo.flush()
                self.arquivo.seek(0)
                msvcrt.locking(self.arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.arquivo.close()
            raise OSError("Este diretório de dados já está aberto em outra instância do NOCFlow.") from exc

    def fechar(self) -> None:
        self.arquivo.close()
