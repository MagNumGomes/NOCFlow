"""Configuração, localização de recursos e diretórios de dados do NOCFlow."""

import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

LOGGER = logging.getLogger("noc")


def diretorio_recursos() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def diretorio_aplicacao() -> Path:
    """Dados do executável ficam fora do pacote, sobrevivendo a novos builds."""
    if not getattr(sys, "frozen", False):
        return diretorio_recursos()
    base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    diretorio = base / "NOCFlow"
    diretorio.mkdir(parents=True, exist_ok=True)
    destino = diretorio / ".env"
    if not destino.exists():
        try:
            with destino.open("x", encoding="utf-8") as arquivo:
                arquivo.write((diretorio_recursos() / ".env.example").read_text(encoding="utf-8"))
        except FileExistsError:
            pass
    return diretorio


@dataclass(frozen=True)
class Config:
    diretorio: Path
    api_key: str = ""
    modelo: str = "gemini-3.8-flash"
    movidesk_url: str = "https://empresa.movidesk.com"
    timeout_ia: int = 60
    timeout_login: int = 120
    groq_api_key: str = ""
    groq_modelo: str = "openai/gpt-oss-120b"
    timeout_groq: int = 30
    timeout_ocr: int = 15
    groq_fallback_enabled: bool = True
    gemini_max_output_tokens: int = 2048
    groq_max_completion_tokens: int = 2048
    ia_automatica: bool = False
    timeout_ticket: int = 28800
    nome_operador: str = ""
    ia_externa: bool = False
    confirmar_ia: Callable[[str, str], bool] | None = field(default=None, repr=False, compare=False)

    @property
    def dados_dir(self) -> Path:
        return self.diretorio / ".noc_data"


def preparar_config_apis(diretorio):
    """Adiciona só opções ausentes, sem substituir chaves ou preferências existentes."""
    from dotenv import dotenv_values

    arquivo = diretorio / ".env"
    exemplo = diretorio_recursos() / ".env.example"
    if not arquivo.exists():
        diretorio.mkdir(parents=True, exist_ok=True)
        try:
            with arquivo.open("x", encoding="utf-8") as destino:
                destino.write(exemplo.read_text(encoding="utf-8"))
        except FileExistsError:
            pass
    atuais = dotenv_values(arquivo, interpolate=False)
    padroes = dotenv_values(exemplo, interpolate=False)
    faltantes = {nome: valor for nome, valor in padroes.items() if nome not in atuais}
    if faltantes:
        with arquivo.open("a", encoding="utf-8") as destino:
            destino.write("\n# Opções adicionadas pelo NOCFlow\n")
            destino.writelines(f"{nome}={valor or ''}\n" for nome, valor in faltantes.items())
    return arquivo


def salvar_nome_operador(diretorio, nome):
    """Grava a identificação global sem substituir as outras opções do usuário."""
    from dotenv import set_key

    nome = " ".join(nome.split())
    arquivo = preparar_config_apis(diretorio)
    salvo, _, _ = set_key(arquivo, "NOME_OPERADOR", nome, quote_mode="always", encoding="utf-8")
    if not salvo:
        raise OSError("Não foi possível salvar o nome do operador no .env.")
    return nome


def carregar_config(diretorio: Path) -> Config:
    from dotenv import load_dotenv

    from .infra.protecao import carregar_chaves

    try:
        preparar_config_apis(diretorio)
    except OSError:
        LOGGER.warning("Não foi possível preparar o .env; usando a configuração disponível.")
    chaves = carregar_chaves(diretorio)
    load_dotenv(diretorio / ".env")

    def inteiro(nome, padrao, minimo, maximo):
        try:
            return max(minimo, min(maximo, int(os.getenv(nome, str(padrao)))))
        except ValueError:
            return padrao

    def habilitado(nome, padrao):
        return os.getenv(nome, padrao).strip().lower() in ("true", "1", "sim", "yes")

    url = os.getenv("MOVIDESK_URL", "https://empresa.movidesk.com").strip().rstrip("/")
    if not url_valida(url) or urlsplit(url).query or urlsplit(url).fragment:
        raise ValueError("MOVIDESK_URL deve ser uma URL HTTPS válida, sem credenciais, query ou fragmento.")
    return Config(
        diretorio=diretorio,
        api_key=chaves["GEMINI_API_KEY"],
        modelo=os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
        movidesk_url=url,
        timeout_ia=inteiro("GEMINI_TIMEOUT_SECONDS", 60, 5, 300),
        timeout_login=inteiro("MOVIDESK_LOGIN_TIMEOUT_SECONDS", 120, 5, 300),
        groq_api_key=chaves["GROQ_API_KEY"],
        groq_modelo=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip(),
        timeout_groq=inteiro("GROQ_TIMEOUT_SECONDS", 30, 5, 300),
        timeout_ocr=inteiro("OCR_TIMEOUT_SECONDS", 15, 5, 300),
        groq_fallback_enabled=habilitado("GROQ_FALLBACK_ENABLED", "true"),
        gemini_max_output_tokens=inteiro("GEMINI_MAX_OUTPUT_TOKENS", 2048, 128, 32768),
        groq_max_completion_tokens=inteiro("GROQ_MAX_COMPLETION_TOKENS", 2048, 128, 32768),
        ia_automatica=habilitado("IA_AUTOMATICA", "false"),
        ia_externa=habilitado("IA_EXTERNA_APROVADA", "false"),
        timeout_ticket=inteiro("MOVIDESK_RETORNO_TIMEOUT_SECONDS", 28800, 60, 86400),
        nome_operador=" ".join(os.getenv("NOME_OPERADOR", "").split()),
    )


def url_valida(valor: object) -> bool:
    if not isinstance(valor, str) or any(c.isspace() or ord(c) < 32 for c in valor):
        return False
    try:
        url = urlsplit(valor)
        return (url.scheme == "https" and bool(url.hostname)
                and url.username is None and url.password is None
                and (url.port is None or url.port > 0))
    except ValueError:
        return False
