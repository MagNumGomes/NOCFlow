"""Limites explícitos antes de descomprimir evidências externas."""

import base64
import binascii
import io
import warnings

from PIL import Image, UnidentifiedImageError

MAX_PIXELS = 16_000_000
MAX_DIMENSAO = 8192


def decodificar_imagem(valor: str, limite: int | None = None) -> Image.Image:
    try:
        bruto = valor.split(",", 1)[-1].strip() if valor.startswith("data:image/") else valor.strip()
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(base64.b64decode(bruto, validate=True))) as imagem:
                if imagem.format not in ("PNG", "JPEG"):
                    raise ValueError("Evidência deve ser PNG ou JPEG.")
                if max(imagem.size) > MAX_DIMENSAO or imagem.width * imagem.height > min(MAX_PIXELS, MAX_PIXELS if limite is None else limite):
                    raise ValueError("Evidência excede o limite de dimensões/pixels.")
                return imagem.convert("RGB")
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Imagem inválida na importação.") from exc
