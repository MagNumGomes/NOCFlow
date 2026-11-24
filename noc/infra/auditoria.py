"""Eventos de segurança sem conteúdo, URLs, identidade pessoal ou tokens."""

import logging
import threading
from collections import Counter

LOGGER = logging.getLogger("noc.seguranca")
_contadores = Counter()
_lock = threading.Lock()
_TIPOS = frozenset({"ponte_rejeitada", "ponte_payload", "ponte_saturada", "ia_bloqueada", "ia_texto_redigido"})


def registrar(tipo):
    if tipo not in _TIPOS:
        raise ValueError("Evento de segurança desconhecido.")
    with _lock:
        _contadores[tipo] += 1
        total = _contadores[tipo]
    # Agrega rajadas, mantendo memória e volume de log limitados.
    if tipo == "ia_texto_redigido":
        LOGGER.info("seguranca tipo=%s contador=%d", tipo, total)
    elif total & (total - 1) == 0:
        LOGGER.warning("seguranca tipo=%s contador=%d alerta=%s", tipo, total, total >= 8)
