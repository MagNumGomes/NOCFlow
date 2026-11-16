"""Execução de tarefas em background desacoplada dos widgets Tkinter."""

import logging
import threading

LOGGER = logging.getLogger("noc")


def disparar_operacao(eventos, identificador, tipo, funcao, mensagem_log=None):
    """Executa uma operação fora da thread gráfica e publica o evento resultante na fila."""

    def tarefa():
        try:
            resultado = funcao()
            eventos.put((f"{tipo}_ok", identificador, resultado))
        except Exception as exc:
            if mensagem_log:
                LOGGER.exception(mensagem_log)
            else:
                LOGGER.exception("Falha na operação %s", tipo)
            eventos.put(("erro", identificador, str(exc)))

    threading.Thread(target=tarefa, name=f"noc-{tipo}", daemon=True).start()


def disparar_assistente(eventos, identificador, tarefa, funcao, ao_concluir):
    """Executa uma consulta de IA do assistente operacional fora da thread gráfica."""

    def trabalho():
        try:
            resultado = funcao()
            eventos.put((ao_concluir, resultado, None, identificador, tarefa))
        except Exception as exc:
            mensagem = str(exc) if isinstance(exc, ValueError) else f"Falha no assistente ({type(exc).__name__})."
            eventos.put((None, None, mensagem, identificador, tarefa))

    threading.Thread(target=trabalho, name="noc-assistente", daemon=True).start()
