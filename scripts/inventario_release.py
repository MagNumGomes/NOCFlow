"""Inventário CycloneDX e proveniência dos arquivos efetivamente distribuídos."""

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def sha256(arquivo):
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


def gerar(pacote):
    lock = RAIZ / "scripts/requirements-windows.txt"
    versao = (RAIZ / "VERSION").read_text().strip()
    componentes = [{"type": "library", "name": nome, "version": versao_pacote,
                    "purl": f"pkg:pypi/{nome.lower()}@{versao_pacote}"}
                   for nome, versao_pacote in re.findall(r"^([\w.-]+)==([^\s;]+)", lock.read_text(), re.M)]
    componentes.append({"type": "application", "name": "NOCFlow Edge Extension", "version": versao})
    for nome, arquivo in (("html2canvas", RAIZ / "edge_extension/vendor/html2canvas.min.js"),
                          ("NOCFlow.exe", pacote / "NOCFlow.exe")):
        componentes.append({"type": "file", "name": nome,
                            "hashes": [{"alg": "SHA-256", "content": sha256(arquivo)}]})
    sbom = {"bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
            "metadata": {"timestamp": datetime.now(UTC).isoformat(),
                         "component": {"type": "application", "name": "NOCFlow", "version": versao}},
            "components": componentes}
    (pacote / "sbom.cdx.json").write_text(json.dumps(sbom, indent=2), encoding="utf-8")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=RAIZ, text=True).strip()
    proveniencia = {"commit": commit, "lock_sha256": sha256(lock), "executavel_sha256": sha256(pacote / "NOCFlow.exe"),
                   "sbom_sha256": sha256(pacote / "sbom.cdx.json"), "plataforma": "Windows x64 / Python 3.12"}
    (pacote / "proveniencia.json").write_text(json.dumps(proveniencia, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pacote", type=Path, required=True)
    gerar(parser.parse_args().pacote)
