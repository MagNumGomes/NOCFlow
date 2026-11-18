"""Contratos incrementais; o formato JSON persistido permanece compatível."""

from dataclasses import dataclass
from typing import TypedDict


class DadosEvento(TypedDict):
    alerta: str
    servidor: str
    severidade: str
    situacao: str
    horario: str


class SnapshotFila(TypedDict):
    ativo: str
    itens: list[dict]
    operacional: dict


@dataclass(frozen=True)
class ResultadoTarefa:
    identificador: str
    valor: object = None
    erro: str = ""
