import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from noc.configuracao import Config, carregar_config
from noc.extracao import consultar_gemini
from noc.tokens_ia import ConsumoIA


class TokensTests(unittest.TestCase):
    def test_gemini_envia_teto_e_informa_consumo_mesmo_quando_truncado(self):
        from google.generativeai.types import GenerateContentResponse
        from google.generativeai import protos

        for motivo in (1, 2):
            with self.subTest(motivo=motivo):
                # Usa o objeto real do SDK, inclusive o enum MAX_TOKENS.
                resposta = GenerateContentResponse.from_response(protos.GenerateContentResponse({
                    "candidates": [{"content": {"parts": [{"text": "{}"}]}, "finish_reason": motivo}],
                    "usage_metadata": {"prompt_token_count": 100, "candidates_token_count": 30, "total_token_count": 150},
                }))
                eventos = []
                with patch("google.generativeai.configure"), patch("google.generativeai.GenerativeModel") as modelo:
                    modelo.return_value.generate_content.return_value = resposta
                    config = Config(Path("."), gemini_max_output_tokens=1024)
                    if motivo == 2:
                        with self.assertRaisesRegex(ValueError, "GEMINI_MAX_OUTPUT_TOKENS"):
                            consultar_gemini(config, Image.new("RGB", (10, 10)), lambda t, d: eventos.append(d))
                    else:
                        self.assertEqual(consultar_gemini(config, Image.new("RGB", (10, 10)), lambda t, d: eventos.append(d)), "{}")
                    enviado = modelo.return_value.generate_content.call_args.kwargs["generation_config"]
                    self.assertEqual(enviado["max_output_tokens"], 1024)
                self.assertEqual(eventos[0]["total"], 150)
                self.assertEqual(eventos[0]["saida"], 30)

    def test_ausencia_de_uso_nao_e_exibida_como_consumo_zero(self):
        from noc.extracao import notificar_consumo

        consumo = ConsumoIA()
        notificar_consumo(lambda t, d: consumo.registrar(d), "Groq", SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30))
        notificar_consumo(lambda t, d: consumo.registrar(d), "Groq", headers={"x-ratelimit-remaining-tokens": "0", "retry-after": "5"})
        texto = consumo.resumo(Config(Path(".")))
        self.assertIn("Total: não informado", texto)
        self.assertIn("sessão: 30 tokens", texto)
        self.assertIn("restantes 0", texto)
        self.assertIn("5 segundos", texto)
        self.assertNotIn("restantes 0 / limite 0", texto)

    def test_config_limites_validos_invalidos_e_migracao(self):
        for valor, esperado in (("1024", 1024), ("abc", 2048), ("0", 128), ("999999", 32768)):
            with self.subTest(valor=valor), tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, {"GEMINI_MAX_OUTPUT_TOKENS": valor, "GROQ_MAX_COMPLETION_TOKENS": valor}, clear=True):
                arquivo = Path(pasta) / ".env"
                arquivo.write_text("GEMINI_API_KEY=teste\n", encoding="utf-8")
                config = carregar_config(Path(pasta))
                self.assertEqual(config.gemini_max_output_tokens, esperado)
                self.assertEqual(config.groq_max_completion_tokens, esperado)
                self.assertIn("GEMINI_MAX_OUTPUT_TOKENS=2048", arquivo.read_text(encoding="utf-8"))
