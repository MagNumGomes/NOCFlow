"""Interpretação conservadora do OCR e cache limitado por captura."""

from collections import OrderedDict
import hashlib
import re
import unicodedata

from .incidentes import CAMPOS_EVENTO

ROTULOS = {
    "host": "servidor", "servidor": "servidor", "trigger": "alerta", "event name": "alerta",
    "nome do evento": "alerta", "gatilho": "alerta", "severity": "severidade", "severidade": "severidade",
    "operational data": "situacao", "dados operacionais": "situacao", "time": "horario", "hora": "horario",
    "horario": "horario", "horario da falha": "horario",
}
PADRAO_ROTULO = re.compile(r"^(" + "|".join(sorted(ROTULOS, key=len, reverse=True)) + r")(?=\s*:|\s{2,}|$)", re.I)
LIMITADORES = re.compile(r"^(?:status|estado|duration|duracao|acknowledg\w*|reconhec\w*|tags|actions|acoes|recovery time|tempo de recuperacao)\b", re.I)


def normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def interpretar_ocr(texto):
    dados = dict.fromkeys(CAMPOS_EVENTO, "")
    valores = {c: [] for c in CAMPOS_EVENTO}
    atual, linhas = None, []

    def terminar():
        if atual and linhas:
            valores[atual].append("\n".join(linhas).strip())

    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        match = PADRAO_ROTULO.match(normalizar(linha))
        if match:
            terminar()
            atual = ROTULOS[match[1].lower()]
            linhas = []
            valor = linha[match.end():].lstrip(" :\t")
            if valor:
                linhas.append(valor)
        elif LIMITADORES.match(normalizar(linha)):
            terminar()
            atual, linhas = None, []
        elif atual:
            linhas.append(linha)
    terminar()
    ambiguos = []
    for campo, opcoes in valores.items():
        unicos = list(dict.fromkeys(opcoes))
        if len(unicos) == 1:
            dados[campo] = unicos[0]
        elif len(unicos) > 1:
            ambiguos.append(campo)
    horario = dados["horario"]
    if horario and not re.search(r"\b(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b", horario):
        dados["horario"] = ""
        ambiguos.append("horario")
    return dados, ambiguos


def texto_relevante(texto, limite=8000):
    """Exclui cabeçalhos de navegação; nunca corta silenciosamente um bloco extenso."""
    linhas = texto.splitlines()
    inicio = next((i for i, l in enumerate(linhas) if PADRAO_ROTULO.match(normalizar(l.strip()))), 0)
    trecho = "\n".join(linhas[inicio:]).strip()
    if len(trecho) > limite:
        raise ValueError("O OCR contém texto demais. Recorte somente o alerta antes de usar IA.")
    return trecho


class CacheExtracao:
    def __init__(self, limite=20):
        self.limite = limite
        self.dados = OrderedDict()

    def chave(self, imagem, modo):
        digest = hashlib.sha256()
        digest.update(f"{imagem.mode}:{imagem.size}:{modo}".encode())
        digest.update(imagem.tobytes())
        return digest.hexdigest()

    def obter(self, chave):
        if chave in self.dados:
            self.dados.move_to_end(chave)
            return dict(self.dados[chave])
        return None

    def guardar(self, chave, dados):
        self.dados[chave] = dict(dados)
        self.dados.move_to_end(chave)
        while len(self.dados) > self.limite:
            self.dados.popitem(last=False)
