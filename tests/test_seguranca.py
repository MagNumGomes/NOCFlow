import base64
import io
import json
import os
import queue
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from noc.assistente_ia import consultar_texto
from noc.configuracao import Config, url_valida
from noc.edge_bridge import preparar_extensao
from noc.extracao import consultar_groq
from noc.infra.imagens import decodificar_imagem
from noc.infra.protecao import carregar_chaves, desproteger, proteger
from noc.politica_ia import preparar_texto
from noc.rascunhos import RascunhoWorker


class SegurancaTests(unittest.TestCase):
    def test_http_remoto_e_loopback_nao_sao_urls_operacionais(self):
        for url in ("http://empresa.movidesk.com", "http://zabbix.test", "http://127.0.0.1", "https://user:pass@host.test"):
            self.assertFalse(url_valida(url))
        self.assertTrue(url_valida("https://monitor.test:8443/zabbix"))

    def test_manifesto_restringe_tenant_e_rejeita_http_antes_de_copiar(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            destino = preparar_extensao(raiz, "https://cliente.movidesk.com")
            manifesto = json.loads((destino / "manifest.json").read_text())
            self.assertIn("https://cliente.movidesk.com/*", manifesto["host_permissions"])
            self.assertNotIn("https://*.movidesk.com/*", manifesto["host_permissions"])
            anterior = (destino / "manifest.json").read_bytes()
            (raiz / ".noc_data/extensao.json").write_text('{"zabbix_origens":["http://monitor.test"]}')
            with self.assertRaises(ValueError):
                preparar_extensao(raiz)
            self.assertEqual((destino / "manifest.json").read_bytes(), anterior)

    def test_ia_bloqueada_antes_do_cliente_e_redacao(self):
        config = Config(Path("."), groq_api_key="fixture")
        with patch("groq.Groq") as cliente:
            with self.assertRaisesRegex(ValueError, "bloqueada"):
                consultar_groq(config, "Host: teste")
            with self.assertRaisesRegex(ValueError, "bloqueada"):
                consultar_texto(config, "teste", {"texto": "teste"}, {})
            cliente.assert_not_called()
        aprovado = replace(config, ia_externa=True)
        texto = preparar_texto(aprovado, "senha=segredo email pessoa@example.org IP 192.168.1.2 CPF 123.456.789-00")
        for sensivel in ("segredo", "pessoa@example.org", "192.168.1.2", "123.456.789-00"):
            self.assertNotIn(sensivel, texto)
        with self.assertRaisesRegex(ValueError, "classificado"):
            preparar_texto(aprovado, "Documento CONFIDENCIAL")
        self.assertNotIn("segredo", preparar_texto(aprovado, '{"senha": "segredo"}'))
        with patch("groq.Groq") as cliente, self.assertRaisesRegex(ValueError, "prévia"):
            consultar_groq(aprovado, "Host: teste")
        cliente.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "DPAPI exige Windows")
    def test_dpapi_migracao_chaves_sem_texto_claro_e_adulteracao(self):
        with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("GROQ_API_KEY", None)
            raiz = Path(pasta)
            (raiz / ".env").write_text("GROQ_API_KEY=segredo-ficticio\n", encoding="utf-8")
            self.assertEqual(carregar_chaves(raiz)["GROQ_API_KEY"], "segredo-ficticio")
            self.assertNotIn("segredo-ficticio", (raiz / ".env").read_text())
            self.assertNotIn(b"segredo-ficticio", (raiz / ".noc_data/credenciais.dpapi").read_bytes())
            self.assertEqual(carregar_chaves(raiz)["GROQ_API_KEY"], "segredo-ficticio")
            protegido = proteger(b"dados privados")
            self.assertEqual(desproteger(protegido), b"dados privados")
            with self.assertRaises((OSError, ValueError)):
                desproteger(protegido[:-8] + b"AAAAAAAA")

    @unittest.skipUnless(os.name == "nt", "DPAPI exige Windows")
    def test_rascunho_migra_e_expira_apos_inatividade(self):
        with tempfile.TemporaryDirectory() as pasta:
            worker = RascunhoWorker(Config(Path(pasta)), queue.Queue())
            worker.arquivo.parent.mkdir()
            worker.arquivo.write_text('{"versao":2,"dados":{"ticket":"123"}}')
            self.assertEqual(worker.carregar()[0]["ticket"], "123")
            self.assertNotIn(b'"ticket"', worker.arquivo.read_bytes())
            self.assertEqual(worker.carregar()[0]["ticket"], "123")
            antigo = time.time() - 31 * 86400
            os.utime(worker.arquivo, (antigo, antigo))
            self.assertEqual(worker.carregar(), ({}, None))
            self.assertFalse(worker.arquivo.exists())

    def test_imagens_extremas_formatos_e_warning_rejeitados(self):
        for formato, tamanho in (("PNG", (8193, 1)), ("JPEG", (1, 8193)), ("GIF", (2, 2))):
            buffer = io.BytesIO()
            Image.new("RGB", tamanho).save(buffer, formato)
            with self.assertRaises(ValueError):
                decodificar_imagem(base64.b64encode(buffer.getvalue()).decode())
        buffer = io.BytesIO()
        Image.new("RGB", (20, 20)).save(buffer, "PNG")
        with patch.object(Image, "MAX_IMAGE_PIXELS", 250), self.assertRaises(ValueError):
            decodificar_imagem(base64.b64encode(buffer.getvalue()).decode())
