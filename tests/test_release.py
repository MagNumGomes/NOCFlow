import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.empacotar_release import empacotar
from scripts.versionar import sincronizar, validar_versao


class ReleaseTests(unittest.TestCase):
    def test_versao_e_artefatos_sincronizados(self):
        versao = sincronizar(check=True)
        self.assertEqual(sincronizar(check=True, tag=f"v{versao}"), versao)
        with self.assertRaises(ValueError):
            sincronizar(check=True, tag="v0.0.1")

    def test_versoes_invalidas_nao_chegam_ao_manifesto(self):
        for valor in ("v2.3.0", "2.3", "02.3.0", "2.3.0-beta", "65536.0.0", "0.0.0"):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                validar_versao(valor)

    def test_zip_completo_checksum_e_rejeicao_de_dados_privados(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            (raiz / "VERSION").write_text("2.3.0", encoding="utf-8")
            (raiz / "docs").mkdir(exist_ok=True)
            (raiz / "docs/CHANGELOG.md").write_text("## [2.3.0]\nTeste\n\n## [2.2.3]\nAnterior", encoding="utf-8")
            pacote = raiz / "dist/NOCFlow"
            (pacote / "_internal").mkdir(parents=True)
            executavel = pacote / "NOCFlow.exe"
            executavel.write_bytes(b"fixture")
            (pacote / "_internal/VERSION").write_text("2.3.0", encoding="utf-8")
            (raiz / "build").mkdir()
            relatorio = {"status": "ok", "empacotado": True, "versao": "2.3.0", "executavel": str(executavel)}
            (raiz / "build/verificacao.json").write_text(json.dumps(relatorio), encoding="utf-8")
            destino = empacotar(raiz)
            with zipfile.ZipFile(destino) as zipado:
                self.assertEqual(sorted(zipado.namelist()), ["NOCFlow/NOCFlow.exe", "NOCFlow/_internal/VERSION"])
            soma = hashlib.sha256(destino.read_bytes()).hexdigest()
            self.assertEqual((destino.parent / "SHA256SUMS.txt").read_text().strip(), f"{soma}  {destino.name}")
            self.assertNotIn("Anterior", (destino.parent / "NOTAS.md").read_text(encoding="utf-8"))
            (pacote / ".env").write_text("PRIVADO=teste", encoding="utf-8")
            with self.assertRaises(ValueError):
                empacotar(raiz)
            (pacote / ".env").unlink()
            relatorio["status"] = "erro"
            (raiz / "build/verificacao.json").write_text(json.dumps(relatorio), encoding="utf-8")
            with self.assertRaises(ValueError):
                empacotar(raiz)
