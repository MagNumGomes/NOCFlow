"""Proteção de dados locais com DPAPI vinculada ao usuário Windows."""

import base64
import ctypes
import json
import os
import re
import subprocess
from ctypes import wintypes
from pathlib import Path

PREFIXO = b"NOCFLOW-DPAPI-1\n"


def restringir_diretorio(diretorio):
    """DACL protegida: somente SID do operador e SYSTEM, herdável pelos filhos."""
    if os.name != "nt":
        raise OSError("Proteção do diretório exige Windows.")
    diretorio.mkdir(parents=True, exist_ok=True)
    sistema = ctypes.create_unicode_buffer(32768)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetSystemDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    kernel.GetSystemDirectoryW.restype = wintypes.UINT
    if not 0 < kernel.GetSystemDirectoryW(sistema, len(sistema)) < len(sistema):
        raise OSError("Diretório do Windows indisponível.")
    whoami = Path(sistema.value) / "whoami.exe"
    identidade = subprocess.check_output([str(whoami), "/user", "/fo", "csv", "/nh"],
                                        creationflags=subprocess.CREATE_NO_WINDOW).decode(errors="replace")
    sid = re.search(r"S-1-5-\d+(?:-\d+)+", identidade)
    if not sid:
        raise OSError("Não foi possível identificar o SID do operador.")
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    converter = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    converter.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    converter.restype = wintypes.BOOL
    obter = advapi.GetSecurityDescriptorDacl
    obter.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
    obter.restype = wintypes.BOOL
    aplicar = advapi.SetNamedSecurityInfoW
    aplicar.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    aplicar.restype = wintypes.DWORD
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    descritor, acl = ctypes.c_void_p(), ctypes.c_void_p()
    presente, padrao = wintypes.BOOL(), wintypes.BOOL()
    if not converter(f"D:P(A;OICI;FA;;;{sid[0]})(A;OICI;FA;;;SY)", 1, ctypes.byref(descritor), None):
        raise OSError("Não foi possível preparar a ACL privada.")
    try:
        if not obter(descritor, ctypes.byref(presente), ctypes.byref(acl), ctypes.byref(padrao)):
            raise OSError("ACL privada inválida.")
        if aplicar(str(diretorio.resolve()), 1, 0x80000004, None, None, acl, None):
            raise OSError("Não foi possível restringir o diretório de dados.")
    finally:
        kernel.LocalFree(descritor)


def _dpapi(dados, proteger):
    if os.name != "nt":
        raise OSError("Persistência sensível exige DPAPI no Windows.")

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buffer = ctypes.create_string_buffer(dados)
    entrada = Blob(len(dados), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    saida = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    funcao = crypt32.CryptProtectData if proteger else crypt32.CryptUnprotectData
    funcao.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    funcao.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not funcao(ctypes.byref(entrada), None, None, None, None, 1, ctypes.byref(saida)):
        raise OSError("Não foi possível proteger/abrir os dados deste usuário (DPAPI).")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        kernel32.LocalFree(saida.pbData)


def proteger(dados):
    return PREFIXO + base64.b64encode(_dpapi(dados, True))


def desproteger(dados):
    if not dados.startswith(PREFIXO):
        raise ValueError("Arquivo protegido inválido.")
    return _dpapi(base64.b64decode(dados[len(PREFIXO):], validate=True), False)


def carregar_chaves(diretorio):
    """Migra antes de remover o segredo legado; nunca cria cópia em texto claro."""
    from dotenv import dotenv_values, unset_key

    from .persistencia import escrever_bytes

    arquivo = diretorio / ".noc_data" / "credenciais.dpapi"
    restringir_diretorio(arquivo.parent)
    chaves = json.loads(desproteger(arquivo.read_bytes())) if arquivo.exists() else {}
    legado = dotenv_values(diretorio / ".env", interpolate=False)
    nomes = ("GEMINI_API_KEY", "GROQ_API_KEY")
    migrar = {nome: legado[nome] for nome in nomes if legado.get(nome) and not legado[nome].lower().startswith("sua_chave")}
    if migrar:
        chaves.update(migrar)
        escrever_bytes(arquivo, proteger(json.dumps(chaves).encode("utf-8")))
        for nome in migrar:
            removida, _ = unset_key(diretorio / ".env", nome)
            if not removida:
                raise OSError("Chave protegida, mas não foi possível remover o valor legado do .env.")
    return {nome: os.getenv(nome, chaves.get(nome, "")).strip() for nome in nomes}
