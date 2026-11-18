"""Preparação de evidências reutilizável pelos workers e pelas views."""

import math

from PIL import Image

CAMPOS_RECORTE = ("Host", "Trigger", "Severity")


def caixa_original(inicio, fim, tamanho_original, tamanho_exibido):
    """Converte coordenadas da visualização em pixels da evidência original."""
    largura, altura = tamanho_original
    exibida_largura, exibida_altura = tamanho_exibido
    x1, x2 = sorted((inicio[0], fim[0]))
    y1, y2 = sorted((inicio[1], fim[1]))
    caixa = (
        max(0, min(largura, math.floor(x1 * largura / exibida_largura))),
        max(0, min(altura, math.floor(y1 * altura / exibida_altura))),
        max(0, min(largura, math.ceil(x2 * largura / exibida_largura))),
        max(0, min(altura, math.ceil(y2 * altura / exibida_altura))),
    )
    if caixa[2] - caixa[0] < 2 or caixa[3] - caixa[1] < 2:
        raise ValueError("Arraste para marcar uma área com pelo menos 2 × 2 pixels.")
    return caixa


def montar_recortes(imagem: Image.Image, caixas: dict) -> Image.Image:
    """Empilha trechos sem esticar pixels nem alterar a imagem recebida."""
    recortes = []
    for campo in CAMPOS_RECORTE:
        caixa = caixas.get(campo)
        if caixa is None or len(caixa) != 4:
            raise ValueError(f"Selecione a área de {campo} no print.")
        x1, y1, x2, y2 = caixa
        if not (0 <= x1 < x2 <= imagem.width and 0 <= y1 < y2 <= imagem.height):
            raise ValueError(f"O recorte de {campo} está fora do print. Selecione novamente.")
        recortes.append(imagem.crop(caixa).convert("RGB"))
    largura = max(recorte.width for recorte in recortes)
    altura = sum(recorte.height for recorte in recortes) + 12
    resultado = Image.new("RGB", (largura, altura), recortes[0].getpixel((0, 0)))
    y = 0
    for recorte in recortes:
        resultado.paste(recorte.getpixel((0, 0)), (0, y, largura, y + recorte.height))
        resultado.paste(recorte, (0, y))
        y += recorte.height + 6
    return resultado


def preparar_miniatura(imagem: Image.Image, tamanho: tuple[int, int], caixas: dict | None = None) -> Image.Image:
    copia = montar_recortes(imagem, caixas) if caixas else imagem.copy()
    copia.thumbnail(tamanho)
    return copia
