"""Publicação de imagens e conteúdo rico (HTML + texto) no clipboard nativo do Windows."""

import ctypes
import io
import os
import time
import pyperclip


def formatar_cf_html(fragmento_html):
    marcador = (
        "Version:0.9\r\n"
        "StartHTML:{:010d}\r\n"
        "EndHTML:{:010d}\r\n"
        "StartFragment:{:010d}\r\n"
        "EndFragment:{:010d}\r\n"
    )
    prefixo = "<html><body><!--StartFragment-->"
    sufixo = "<!--EndFragment--></body></html>"
    base = len(marcador.format(0, 0, 0, 0).encode("utf-8"))
    prefixo_b = prefixo.encode("utf-8")
    frag_b = fragmento_html.encode("utf-8")
    sufixo_b = sufixo.encode("utf-8")
    inicio_html = base
    inicio_frag = inicio_html + len(prefixo_b)
    fim_frag = inicio_frag + len(frag_b)
    fim_html = fim_frag + len(sufixo_b)
    cabecalho = marcador.format(inicio_html, fim_html, inicio_frag, fim_frag).encode("utf-8")
    return cabecalho + prefixo_b + frag_b + sufixo_b


def _alocar_bloco(kernel32, dados):
    memoria = kernel32.GlobalAlloc(0x0042, len(dados))
    if not memoria:
        raise ctypes.WinError(ctypes.get_last_error())
    destino = kernel32.GlobalLock(memoria)
    if not destino:
        kernel32.GlobalFree(memoria)
        raise ctypes.WinError(ctypes.get_last_error())
    ctypes.memmove(destino, dados, len(dados))
    kernel32.GlobalUnlock(memoria)
    return memoria


def copiar_html_texto(texto, fragmento_html, hwnd=None):
    """Publica CF_UNICODETEXT e HTML Format no clipboard do Windows."""
    if os.name != "nt":
        pyperclip.copy(texto)
        return
    from ctypes import wintypes

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
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT

    cf_html = user32.RegisterClipboardFormatW("HTML Format")
    if not cf_html:
        raise ctypes.WinError(ctypes.get_last_error())
    mem_texto = _alocar_bloco(kernel32, texto.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-16-le") + b"\x00\x00")
    mem_html = None
    aberto = False
    try:
        mem_html = _alocar_bloco(kernel32, formatar_cf_html(fragmento_html) + b"\x00")
        for _ in range(10):
            if user32.OpenClipboard(hwnd or None):
                aberto = True
                break
            time.sleep(0.05)
        if not aberto:
            raise OSError("Área de transferência ocupada. Tente copiar novamente.")
        if not user32.EmptyClipboard():
            raise ctypes.WinError(ctypes.get_last_error())
        if not user32.SetClipboardData(13, mem_texto):
            raise ctypes.WinError(ctypes.get_last_error())
        mem_texto = None
        if not user32.SetClipboardData(cf_html, mem_html):
            raise ctypes.WinError(ctypes.get_last_error())
        mem_html = None
    finally:
        if aberto:
            user32.CloseClipboard()
        if mem_texto:
            kernel32.GlobalFree(mem_texto)
        if mem_html:
            kernel32.GlobalFree(mem_html)


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
