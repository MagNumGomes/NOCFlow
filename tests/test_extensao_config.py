import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noc.edge_bridge import preparar_extensao


class ConfigExtensaoTests(unittest.TestCase):
    def test_atualizacao_preserva_origens_instaladas_sem_alterar_fonte(self):
        fonte = Path(__file__).resolve().parents[1] / "edge_extension" / "manifest.json"
        original = fonte.read_bytes()
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            destino = raiz / "edge_extension"
            destino.mkdir()
            destino.joinpath("manifest.json").write_text(json.dumps({"content_scripts": [
                {"js": ["zabbix.js"], "matches": ["https://monitor.example.org/*"]}]}), encoding="utf-8")
            for _ in range(2):
                preparar_extensao(raiz)
                manifesto = json.loads(destino.joinpath("manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifesto["version"], "2.2.0")
                self.assertIn("https://monitor.example.org/*", manifesto["host_permissions"])
                self.assertNotIn("https://zabbix.example.com/*", manifesto["host_permissions"])
                self.assertIn('"https://monitor.example.org"', destino.joinpath("background.js").read_text(encoding="utf-8"))
                self.assertTrue(destino.joinpath("popup.html").is_file())
            self.assertTrue(raiz.joinpath(".noc_data/extensao.json").is_file())
        self.assertEqual(fonte.read_bytes(), original)

    def test_configuracao_invalida_nao_substitui_extensao(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            raiz.joinpath(".noc_data").mkdir()
            raiz.joinpath(".noc_data/extensao.json").write_text('{"zabbix_origens": ["https://*.example.org"]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                preparar_extensao(raiz)
            self.assertFalse(raiz.joinpath("edge_extension").exists())

    def test_execucao_fonte_gera_copia_privada(self):
        raiz = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as pasta:
            import shutil
            destino = Path(pasta)
            shutil.copytree(raiz / "edge_extension", destino / "edge_extension")
            with patch("noc.edge_bridge.diretorio_recursos", return_value=destino):
                self.assertEqual(preparar_extensao(destino), destino / ".noc_data" / "edge_extension")
