"""OCR local do Windows com reconstrução espacial de linhas e colunas."""

import asyncio
import os

from PIL import Image


def organizar_palavras(palavras):
    """Agrupa palavras pela posição vertical; preserva separação entre colunas."""
    linhas = []
    for texto, x, y, largura, altura in sorted(palavras, key=lambda p: (p[2] + p[4] / 2, p[1])):
        centro = y + altura / 2
        linha = next((l for l in reversed(linhas[-3:]) if abs(l[0] - centro) <= min(l[1], altura) * 0.45), None)
        if linha is None:
            linha = [centro, altura, []]
            linhas.append(linha)
        linha[2].append((x, largura, texto))
    resultado = []
    for _, altura, palavras_linha in sorted(linhas):
        fim, partes = None, []
        for x, largura, texto in sorted(palavras_linha):
            if fim is not None:
                partes.append("  " if x - fim > max(12, altura * 0.85) else " ")
            partes.append(texto)
            fim = x + largura
        resultado.append("".join(partes))
    return "\n".join(resultado).strip()


def extrair_texto(imagem, timeout=15):
    if os.name != "nt":
        raise ValueError("O OCR local está disponível no Windows 10/11.")
    try:
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter
        # Projeções de coleções são necessárias para percorrer OcrResult.lines.
        import winrt.windows.foundation.collections  # noqa: F401
    except ImportError:
        raise ValueError("O OCR do Windows não está incluído nesta instalação. Atualize o executável ou instale requirements.txt.") from None

    async def reconhecer():
        motor = OcrEngine.try_create_from_user_profile_languages()
        if motor is None:
            for idioma in ("pt-BR", "en-US"):
                motor = OcrEngine.try_create_from_language(Language(idioma))
                if motor is not None:
                    break
        if motor is None:
            raise ValueError("Nenhum idioma de OCR está instalado no Windows. Adicione Português ou Inglês em Configurações > Hora e idioma > Idioma e região.")

        limite = OcrEngine.max_image_dimension
        fator = min(2.0, limite / max(imagem.size))
        preparada = imagem.convert("RGBA")
        if fator != 1:
            preparada = preparada.resize(
                (max(1, round(imagem.width * fator)), max(1, round(imagem.height * fator))),
                Image.Resampling.LANCZOS,
            )
        with DataWriter() as writer:
            writer.write_bytes(preparada.tobytes("raw", "BGRA"))
            bitmap = SoftwareBitmap.create_copy_with_alpha_from_buffer(
                writer.detach_buffer(), BitmapPixelFormat.BGRA8,
                preparada.width, preparada.height, BitmapAlphaMode.IGNORE,
            )
        try:
            resultado = await motor.recognize_async(bitmap)
            palavras = []
            for linha in resultado.lines:
                for palavra in linha.words:
                    caixa = palavra.bounding_rect
                    palavras.append((palavra.text, caixa.x, caixa.y, caixa.width, caixa.height))
            texto = organizar_palavras(palavras)
        finally:
            bitmap.close()
        if not texto:
            raise ValueError("O OCR não encontrou texto legível no print. Capture somente o alerta, com os campos visíveis, e tente novamente.")
        return texto

    async def com_limite():
        return await asyncio.wait_for(reconhecer(), timeout=timeout)

    try:
        return asyncio.run(com_limite())
    except TimeoutError:
        raise ValueError(f"O OCR local excedeu {timeout}s. Recorte o print para mostrar somente o alerta e tente novamente.") from None
    except OSError:
        raise ValueError("O OCR do Windows não conseguiu ler a imagem. Confira se Português ou Inglês está instalado em Idioma e região e tente outra captura.") from None
