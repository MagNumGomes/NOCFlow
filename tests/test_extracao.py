from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from google.api_core import exceptions
from PIL import Image, ImageDraw, ImageFont

from noc.configuracao import Config, preparar_config_apis
from noc.extracao import consultar_groq, extrair_dados
from noc.ocr_windows import extrair_texto


DADOS = {"alerta": "CPU usage high", "servidor": "servidor-01", "severidade": "High", "situacao": "CPU 95%", "horario": "10:42"}
TEXTO_OCR = "Trigger: CPU usage high\nHost: servidor-01\nSeverity: High\nOperational data: CPU 95%\nTime: 10:42"


class ExtracaoLocalTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(Path("."), api_key="gemini-teste", groq_api_key="groq-teste")
        self.imagem = Image.new("RGB", (20, 20))

    def test_ocr_completo_nao_aciona_apis_mesmo_com_ia_permitida(self):
        with patch("noc.extracao.consultar_gemini") as gemini, patch("noc.ocr_windows.extrair_texto", return_value=TEXTO_OCR), patch("noc.extracao.consultar_groq") as groq:
            self.assertEqual(extrair_dados(self.config, self.imagem, permitir_ia=True), DADOS)
            gemini.assert_not_called()
            groq.assert_not_called()

    def test_local_com_campos_parciais_nao_chama_apis(self):
        with patch("noc.extracao.consultar_gemini") as gemini, patch("noc.ocr_windows.extrair_texto", return_value="Host: servidor-01"), patch("noc.extracao.consultar_groq") as groq:
            dados = extrair_dados(self.config, self.imagem)
            self.assertEqual(dados["servidor"], "servidor-01")
            self.assertEqual(dados["alerta"], "")
            gemini.assert_not_called()
            groq.assert_not_called()

    def test_groq_completa_so_faltantes_sem_alterar_host_local(self):
        with patch("noc.extracao.consultar_gemini") as gemini, patch("noc.ocr_windows.extrair_texto", return_value="Host: servidor-01"), patch("noc.extracao.consultar_groq", return_value=json.dumps({**DADOS, "servidor": "inventado"})) as groq:
            self.assertEqual(extrair_dados(self.config, self.imagem, permitir_ia=True), DADOS)
            self.assertNotIn("servidor", groq.call_args.kwargs["campos"])
            gemini.assert_not_called()

    def test_falha_groq_usa_visao_uma_vez(self):
        eventos = []
        with patch("noc.extracao.consultar_gemini", return_value=json.dumps(DADOS)) as gemini, patch("noc.ocr_windows.extrair_texto", return_value="Host: servidor-01"), patch("noc.extracao.consultar_groq", side_effect=ValueError("Groq 429")) as groq:
            self.assertEqual(extrair_dados(self.config, self.imagem, lambda t, d: eventos.append((t, d)), permitir_ia=True), DADOS)
            gemini.assert_called_once()
            groq.assert_called_once()
            self.assertEqual([d for t, d in eventos if t == "extracao_metricas"][0]["chamadas"], 2)

    def test_resposta_parcial_groq_deixa_apenas_pendencias_para_visao(self):
        parcial = {**DADOS, "horario": ""}
        with patch("noc.ocr_windows.extrair_texto", return_value="Host: servidor-01"), \
                patch("noc.extracao.consultar_groq", return_value=json.dumps(parcial)) as groq, \
                patch("noc.extracao.consultar_gemini", return_value='{"horario":"10:42"}') as gemini:
            self.assertEqual(extrair_dados(self.config, self.imagem, permitir_ia=True), DADOS)
        groq.assert_called_once()
        gemini.assert_called_once()
        self.assertEqual(gemini.call_args.kwargs["campos"], ["horario"])

    def test_ocr_ilegivel_nao_envia_texto_vazio_usa_apenas_visao(self):
        with patch("noc.extracao.consultar_gemini", return_value=json.dumps(DADOS)), patch("noc.ocr_windows.extrair_texto", side_effect=ValueError("Texto ilegível")), patch("noc.extracao.consultar_groq") as groq:
            self.assertEqual(extrair_dados(self.config, self.imagem, permitir_ia=True), DADOS)
            groq.assert_not_called()

    def test_falhas_preservam_campos_e_reportam_avisos_sem_corpo_http(self):
        eventos = []
        with patch("noc.extracao.consultar_gemini", side_effect=exceptions.ServiceUnavailable("PRIVADO")), patch("noc.ocr_windows.extrair_texto", return_value="Host: servidor-01"), patch("noc.extracao.consultar_groq", side_effect=ValueError("Groq indisponível")):
            dados = extrair_dados(self.config, self.imagem, lambda t, d: eventos.append((t, d)), permitir_ia=True)
        self.assertEqual(dados["servidor"], "servidor-01")
        avisos = str([d for t, d in eventos if t == "extracao_aviso"])
        self.assertIn("Groq indisponível", avisos)
        self.assertIn("ServiceUnavailable", avisos)
        self.assertNotIn("PRIVADO", avisos)

    def test_cache_e_invalidado_por_imagem_e_configuracao(self):
        from noc.extracao_local import CacheExtracao
        cache = CacheExtracao()
        with patch("noc.ocr_windows.extrair_texto", return_value="Host: servidor-01") as ocr, patch("noc.extracao.consultar_groq", return_value=json.dumps(DADOS)) as groq:
            for _ in range(2):
                self.assertEqual(extrair_dados(self.config, self.imagem, permitir_ia=True, cache=cache), DADOS)
            self.assertEqual(groq.call_count, 1)
            self.assertEqual(ocr.call_count, 1)
            self.imagem.putpixel((0, 0), (255, 0, 0))
            extrair_dados(self.config, self.imagem, permitir_ia=True, cache=cache)
            extrair_dados(replace(self.config, groq_modelo="outro"), self.imagem, permitir_ia=True, cache=cache)
            self.assertEqual(groq.call_count, 3)

    def test_campos_revisados_nao_sao_reenviados_para_ia(self):
        with patch("noc.ocr_windows.extrair_texto", return_value="Host: servidor-01"), patch("noc.extracao.consultar_groq") as groq, patch("noc.extracao.consultar_gemini") as gemini:
            self.assertEqual(extrair_dados(self.config, self.imagem, permitir_ia=True, conhecidos=DADOS), DADOS)
            groq.assert_not_called()
            gemini.assert_not_called()

    def test_sem_chave_continua_com_dados_parciais_e_aviso(self):
        eventos = []
        with patch("noc.ocr_windows.extrair_texto", return_value="Host: servidor-01"):
            dados = extrair_dados(replace(self.config, api_key="", groq_api_key=""), self.imagem, lambda t, d: eventos.append((t, d)), permitir_ia=True)
        self.assertEqual(dados["servidor"], "servidor-01")
        self.assertTrue(any(t == "extracao_aviso" and "não configurada" in d for t, d in eventos))

    def test_json_invalido_da_ia_nao_apaga_dados_locais(self):
        with patch("noc.ocr_windows.extrair_texto", return_value="Host: servidor-01"), patch("noc.extracao.consultar_groq", return_value='{"alerta": []}'):
            dados = extrair_dados(replace(self.config, api_key=""), self.imagem, permitir_ia=True)
        self.assertEqual(dados["servidor"], "servidor-01")
        self.assertEqual(dados["alerta"], "")


@unittest.skipUnless(importlib.util.find_spec("groq"), "Instale requirements.txt para testar o SDK Groq")
class GroqSDKTests(unittest.TestCase):
    def executar_com_resposta(self, status, corpo, headers=None, notificar=None):
        import httpx
        from groq import Groq

        recebidas = []

        def responder(requisicao):
            recebidas.append(requisicao)
            return httpx.Response(status, json=corpo, headers=headers)

        def cliente(**kwargs):
            self.assertEqual(kwargs["max_retries"], 0)
            return Groq(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(responder)))

        config = Config(Path("."), groq_api_key="chave-de-teste", timeout_groq=12, groq_max_completion_tokens=1500)
        with patch("groq.Groq", side_effect=cliente):
            try:
                resultado = consultar_groq(config, TEXTO_OCR, notificar=notificar)
                return resultado, recebidas, None
            except ValueError as exc:
                return None, recebidas, str(exc)

    def test_envia_somente_texto_schema_e_modelo_corretos(self):
        resposta = {"choices": [{"message": {"role": "assistant", "content": json.dumps(DADOS)}, "finish_reason": "stop"}]}
        resultado, recebidas, erro = self.executar_com_resposta(200, resposta)
        self.assertIsNone(erro)
        self.assertEqual(json.loads(resultado), DADOS)
        self.assertEqual(len(recebidas), 1)
        requisicao = recebidas[0]
        self.assertEqual(str(requisicao.url), "https://api.groq.com/openai/v1/chat/completions")
        corpo = json.loads(requisicao.content)
        self.assertEqual(corpo["model"], "openai/gpt-oss-120b")
        self.assertEqual(corpo["max_completion_tokens"], 1500)
        self.assertEqual(corpo["messages"][1]["content"], TEXTO_OCR)
        self.assertTrue(corpo["response_format"]["json_schema"]["strict"])
        self.assertEqual(requisicao.extensions["timeout"]["read"], 12)
        self.assertNotIn("image_url", requisicao.content.decode())

    def test_erros_http_nao_retentam_nem_expoem_corpo_da_api(self):
        for status in (401, 403, 404, 429, 503):
            with self.subTest(status=status):
                _, recebidas, erro = self.executar_com_resposta(status, {"error": {"message": "CONTEUDO_PRIVADO"}})
                self.assertEqual(len(recebidas), 1)
                self.assertIn(str(status), erro)
                self.assertNotIn("CONTEUDO_PRIVADO", erro)

    def test_resposta_cortada_e_rejeitada(self):
        _, _, erro = self.executar_com_resposta(200, {"choices": [{"message": {"role": "assistant", "content": '{"alerta":'}, "finish_reason": "length"}]})
        self.assertIn("GROQ_MAX_COMPLETION_TOKENS", erro)

    def test_uso_e_cotas_reais_do_sdk_incluindo_429(self):
        eventos = []
        headers = {"x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "7200", "x-ratelimit-reset-tokens": "6s", "authorization": "privado"}
        resposta = {"choices": [{"message": {"role": "assistant", "content": json.dumps(DADOS)}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
        _, _, erro = self.executar_com_resposta(200, resposta, headers, lambda t, d: eventos.append((t, d)))
        self.assertIsNone(erro)
        self.assertEqual(eventos[0][0], "ia_consumo")
        self.assertEqual(eventos[0][1]["total"], 150)
        self.assertEqual(eventos[0][1]["entrada"], 100)
        self.assertEqual(eventos[0][1]["cotas"]["x-ratelimit-remaining-tokens"], "7200")
        self.assertNotIn("authorization", eventos[0][1]["cotas"])
        eventos.clear()
        _, _, erro = self.executar_com_resposta(429, {"error": {"message": "limite"}}, {"retry-after": "4", "x-ratelimit-remaining-tokens": "0"}, lambda t, d: eventos.append((t, d)))
        self.assertIn("429", erro)
        self.assertIsNone(eventos[0][1]["total"])
        self.assertEqual(eventos[0][1]["cotas"]["retry-after"], "4")


class ConfigReservaTests(unittest.TestCase):
    def test_adiciona_campos_sem_alterar_chaves_e_preferencias(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / ".env"
            original = "# Configuração existente\nGEMINI_API_KEY=segredo-teste\nGROQ_API_KEY=groq-teste\nGROQ_FALLBACK_ENABLED=false\n"
            arquivo.write_text(original, encoding="utf-8")
            preparar_config_apis(Path(pasta))
            preparar_config_apis(Path(pasta))
            texto = arquivo.read_text(encoding="utf-8")
            self.assertTrue(texto.startswith(original))
            self.assertEqual(texto.count("GROQ_API_KEY="), 1)
            self.assertEqual(texto.count("GROQ_MODEL="), 1)
            self.assertIn("GROQ_FALLBACK_ENABLED=false", texto)


@unittest.skipUnless(os.name == "nt" and importlib.util.find_spec("winrt"), "Requer OCR nativo do Windows e dependências WinRT")
class OCRWindowsTests(unittest.TestCase):
    def test_ocr_real_em_thread_preserva_host_percentual_e_horario(self):
        imagem = Image.new("RGB", (900, 260), "white")
        fonte = ImageFont.truetype(str(Path(os.environ["WINDIR"]) / "Fonts/arial.ttf"), 26)
        ImageDraw.Draw(imagem).multiline_text((20, 20), TEXTO_OCR, font=fonte, fill="black", spacing=8)
        with ThreadPoolExecutor(max_workers=1) as pool:
            texto = pool.submit(extrair_texto, imagem).result(timeout=25)
        self.assertIn("servidor-01", texto)
        self.assertIn("95%", texto)
        self.assertIn("10:42", texto)

    def test_print_vazio_retorna_erro_local(self):
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaisesRegex(ValueError, "texto legível"):
                pool.submit(extrair_texto, Image.new("RGB", (200, 100), "white")).result(timeout=25)
