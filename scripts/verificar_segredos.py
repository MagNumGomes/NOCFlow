"""Gate heurístico de segredos nas fontes versionadas, sem exibir valores."""

import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PADROES = (
    rb"(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"\bAIza[0-9A-Za-z_-]{35}\b",
    rb"\bgsk_[0-9A-Za-z]{40,}\b",
    rb"\bgh[pousr]_[0-9A-Za-z]{36,}\b",
    rb"\bAKIA[0-9A-Z]{16}\b",
)


def verificar():
    arquivos = subprocess.check_output(["git", "ls-files", "-z"], cwd=RAIZ).split(b"\0")
    falhas = []
    for nome in arquivos:
        if not nome:
            continue
        arquivo = RAIZ / nome.decode("utf-8")
        if arquivo.is_file() and any(re.search(padrao, arquivo.read_bytes()) for padrao in PADROES):
            falhas.append(nome.decode("utf-8"))
    for nome in falhas:
        print(f"Possível segredo: {nome} (valor omitido)")
    return bool(falhas)


if __name__ == "__main__":
    raise SystemExit(verificar())
