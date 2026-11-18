"""Diagnóstico estruturado sem conteúdo de incidentes, credenciais ou tokens."""

import json
import logging
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path


class FormatoLocal(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dados = {"em": self.formatTime(record), "nivel": record.levelname,
                 "logger": record.name, "thread": record.threadName,
                 "local": f"{record.module}:{record.lineno}"}
        # Exceções de SDKs podem incluir corpos HTTP e tokens em suas mensagens.
        if record.exc_info:
            dados["erro"] = record.exc_info[0].__name__
            dados["evento"] = record.getMessage()
            dados["pilha"] = [{"arquivo": Path(frame.filename).name, "linha": frame.lineno, "funcao": frame.name}
                              for frame in traceback.extract_tb(record.exc_info[2])]
        else:
            dados["evento"] = record.getMessage()
        return json.dumps(dados, ensure_ascii=False)


def configurar_logging(dados_dir: Path) -> logging.Logger:
    destino = dados_dir / "logs" / "noc.jsonl"
    destino.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("noc")
    for anterior in list(logger.handlers):
        if getattr(anterior, "nocflow", False):
            logger.removeHandler(anterior)
            anterior.close()
    handler = RotatingFileHandler(destino, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.nocflow = True
    handler.setFormatter(FormatoLocal())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
