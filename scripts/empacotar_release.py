"""Empacota somente a distribuição validada e produz checksum e notas da release."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def empacotar(raiz: Path = RAIZ, pasta_dist: Path = Path("dist")) -> Path:
    versao = (raiz / "VERSION").read_text(encoding="utf-8").strip()
    pacote = raiz / pasta_dist / "NOCFlow"
    relatorio = json.loads((raiz / "build/verificacao.json").read_text(encoding="utf-8"))
    if (relatorio.get("status") != "ok" or relatorio.get("empacotado") is not True
            or relatorio.get("versao") != versao
            or Path(relatorio.get("executavel", "")).resolve() != (pacote / "NOCFlow.exe").resolve()
            or not (pacote / "NOCFlow.exe").is_file()):
        raise ValueError("O pacote precisa passar pelo smoke desta versão antes da release.")
    arquivos = sorted(p for p in pacote.rglob("*") if p.is_file())
    for arquivo in arquivos:
        if arquivo.is_symlink() or any(parte.lower() in (".env", ".noc_data", "sessao.lock") for parte in arquivo.relative_to(pacote).parts):
            raise ValueError("O pacote contém dados locais ou links simbólicos.")
    saida = raiz / "dist/release"
    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / f"NOCFlow-v{versao}-windows-x64.zip"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zipado:
        for arquivo in arquivos:
            zipado.write(arquivo, arquivo.relative_to(pacote.parent))
    with destino.open("rb") as arquivo:
        checksum = hashlib.file_digest(arquivo, "sha256").hexdigest()
    (saida / "SHA256SUMS.txt").write_text(f"{checksum}  {destino.name}\n", encoding="utf-8", newline="\n")
    changelog = (raiz / "docs/CHANGELOG.md").read_text(encoding="utf-8")
    marcador = f"## [{versao}]"
    if marcador not in changelog:
        raise ValueError("Inclua as notas desta versão em docs/CHANGELOG.md.")
    notas = changelog.split(marcador, 1)[1].split("\n## [", 1)[0].strip()
    (saida / "NOTAS.md").write_text(
        f"# NOCFlow {versao}\n\n{notas}\n\n"
        "## Instalação e atualização\n"
        "Extraia a pasta NOCFlow inteira. Feche o aplicativo antes de substituir a distribuição. "
        "Configurações e cadastros permanecem em %LOCALAPPDATA%\\NOCFlow. "
        "Após abrir a nova versão, recarregue a extensão no Edge e atualize as páginas dos sistemas.\n",
        encoding="utf-8", newline="\n")
    return destino


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta-dist", type=Path, default=Path("dist"))
    args = parser.parse_args()
    print(empacotar(pasta_dist=args.pasta_dist))
