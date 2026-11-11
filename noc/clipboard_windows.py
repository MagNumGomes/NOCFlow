"""Publicação de imagens no clipboard nativo do Windows."""

import ctypes
import io
import os
import time


def copiar_imagem(imagem, hwnd):
    """Publica CF_DIB no clipboard do Windows, sem dependências adicionais."""
    if os.name != "nt":
        raise OSError("A cópia de imagem está disponível no Windows.")
    from ctypes import wintypes

    buffer = io.BytesIO()
    imagem.convert("RGB").save(buffer, format="BMP")
    dib = buffer.getvalue()[14:]
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    memoria = kernel32.GlobalAlloc(0x0002, len(dib))
    if not memoria:
        raise ctypes.WinError(ctypes.get_last_error())
    aberto = False
    try:
        destino = kernel32.GlobalLock(memoria)
        if not destino:
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.memmove(destino, dib, len(dib))
        kernel32.GlobalUnlock(memoria)
        for _ in range(10):
            if user32.OpenClipboard(hwnd):
                aberto = True
                break
            time.sleep(0.05)
        if not aberto:
            raise OSError("Área de transferência ocupada. Tente copiar o print novamente.")
        if not user32.EmptyClipboard() or not user32.SetClipboardData(8, memoria):
            raise ctypes.WinError(ctypes.get_last_error())
        memoria = None  # O Windows passa a ser proprietário da memória.
    finally:
        if aberto:
            user32.CloseClipboard()
        if memoria:
            kernel32.GlobalFree(memoria)
