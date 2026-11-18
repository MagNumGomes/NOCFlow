"""Tarefas de I/O com callbacks retidos somente pela thread Tkinter."""

import logging
import queue
import threading
import tkinter as tk
from collections.abc import Callable

from ..domain.contratos import ResultadoTarefa

LOGGER = logging.getLogger("noc")


def _trabalhar(eventos: queue.Queue, chave: str, funcao: Callable) -> None:
    try:
        resultado = ResultadoTarefa(chave, funcao())
    except Exception as exc:
        LOGGER.exception("Falha em tarefa local %s", chave)
        resultado = ResultadoTarefa(chave, erro=str(exc) if isinstance(exc, (ValueError, OSError))
                                    else f"Falha na operação ({type(exc).__name__}).")
    eventos.put(resultado)


class TarefasUI:
    def __init__(self, root: tk.Misc, ao_erro: Callable[[str], None]):
        self.root = root
        self.ao_erro = ao_erro
        self.eventos = queue.Queue()
        self.callbacks = {}
        self.fechada = False
        self.timer = root.after(50, self.processar)

    def enviar(self, chave: str, funcao: Callable, concluir: Callable = lambda _: None) -> bool:
        if self.fechada or chave in self.callbacks or len(self.callbacks) >= 4:
            return False
        self.callbacks[chave] = concluir
        threading.Thread(target=_trabalhar, args=(self.eventos, chave, funcao),
                         name=f"noc-{chave}", daemon=True).start()
        return True

    def processar(self) -> None:
        self.timer = None
        if self.fechada:
            return
        for _ in range(8):
            try:
                resultado = self.eventos.get_nowait()
            except queue.Empty:
                break
            callback = self.callbacks.pop(resultado.identificador, None)
            if resultado.erro:
                self.ao_erro(resultado.erro)
            elif callback:
                try:
                    callback(resultado.valor)
                except Exception as exc:
                    LOGGER.exception("Falha ao aplicar resultado local %s", resultado.identificador)
                    self.ao_erro(str(exc) if isinstance(exc, ValueError) else "Não foi possível aplicar o resultado da operação.")
        self.timer = self.root.after(50, self.processar)

    def fechar(self) -> None:
        self.fechada = True
        self.callbacks.clear()
        if self.timer:
            self.root.after_cancel(self.timer)
            self.timer = None
