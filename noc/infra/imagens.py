"""Limites explícitos antes de descomprimir evidências externas."""

import base64
import binascii
import io

from PIL import Image, UnidentifiedImageError

MAX_PIXELS = 16_000_000


def decodificar_imagem(valor: str, limite: int | None = None) -> Image.Image:
    try:
        bruto = valor.split(",", 1)[-1].strip() if valor.startswith("data:image/") else valor.strip()
        with Image.open(io.BytesIO(base64.b64decode(bruto, validate=True))) as imagem:
            if imagem.width * imagem.height > (MAX_PIXELS if limite is None else limite):
                raise ValueError("Evidência excede o limite de 16 milhões de pixels.")
            return imagem.convert("RGB")
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Imagem inválida na importação.") from exc
