import base64
import gc
import io
import json
import queue
import socket
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

from noc.agenda_operacional import proximo_horario
from noc.configuracao import Config
from noc.edge_bridge import EdgeBridge
from noc.infra.imagens import decodificar_imagem
from noc.infra.persistencia import ExclusividadeDados, escrever_texto
from noc.movidesk import MovideskWorker


class PersistenciaTests(unittest.TestCase):
    def test_recorte_e_processado_no_worker_antes_de_gerar_html(self):
        with tempfile.TemporaryDirectory() as pasta:
            ponte = EdgeBridge(porta=0)
            worker = MovideskWorker(Config(Path(pasta)), queue.Queue(), abrir=lambda _: None, ponte=ponte)
            criar = ponte.criar_pedido
            def pedido_pronto(dados, segundos):
                pedido = criar(dados, segundos)
                pedido.eventos.put(("ok", {}))
                return pedido
            caixas = {"Host": (0, 0, 50, 10), "Trigger": (0, 20, 80, 30), "Severity": (0, 40, 30, 50)}
            try:
                with patch.object(ponte, "criar_pedido", side_effect=pedido_pronto), patch("noc.movidesk.gerar_html", return_value="") as html:
                    worker.preencher(1, {"alerta": "CPU", "_imagem": Image.new("RGB", (100, 100)), "_recortes": caixas})
                    self.assertEqual(html.call_args.args[0]["_imagem"].size, (80, 42))
            finally:
                ponte.fechar()

    def test_horario_ambiguo_usa_primeira_ocorrencia_sem_duplicar(self):
        rotina = {"calendario": {"fuso": "America/New_York"}, "horarios": ["01:30"]}
        self.assertEqual(proximo_horario(rotina, "2026-11-01T05:00:00+00:00"), "2026-11-01T05:30:00+00:00")
        self.assertEqual(proximo_horario(rotina, "2026-11-01T05:30:00+00:00"), "2026-11-02T06:30:00+00:00")

    def test_ano_bissexto_e_limite_exclusivo(self):
        rotina = {"calendario": {"fuso": "UTC"}, "horarios": ["09:00"]}
        self.assertEqual(proximo_horario(rotina, "2028-02-28T09:00:00+00:00"), "2028-02-29T09:00:00+00:00")
    def test_falhas_de_flush_ou_replace_preservam_original_e_limpam_temporario(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "estado.json"
            destino.write_text("original", encoding="utf-8")
            for alvo in ("noc.infra.persistencia.os.fsync", "pathlib.Path.replace"):
                with self.subTest(alvo=alvo), patch(alvo, side_effect=OSError("disco indisponível")), self.assertRaises(OSError):
                    escrever_texto(destino, "novo")
                self.assertEqual(destino.read_text(encoding="utf-8"), "original")
                self.assertEqual(list(Path(pasta).glob("*.tmp")), [])

    def test_diretorio_exclusivo_e_liberado_apos_fechar(self):
        with tempfile.TemporaryDirectory() as pasta:
            lock = ExclusividadeDados(Path(pasta))
            try:
                with self.assertRaises(OSError):
                    ExclusividadeDados(Path(pasta))
            finally:
                lock.fechar()
            ExclusividadeDados(Path(pasta)).fechar()

    def test_limite_de_pixels_e_verificado_antes_da_conversao(self):
        buffer = io.BytesIO()
        Image.new("RGB", (20, 20)).save(buffer, format="PNG")
        with patch("noc.infra.imagens.MAX_PIXELS", 100), patch.object(Image.Image, "convert") as converter:
            with self.assertRaises(ValueError):
                decodificar_imagem(base64.b64encode(buffer.getvalue()).decode())
            converter.assert_not_called()


class PonteResilienteTests(unittest.TestCase):
    def setUp(self):
        # A suíte gráfica anterior deixa ciclos Tcl; nunca coletá-los no handler HTTP.
        gc.collect()
        self.ponte = EdgeBridge(porta=0, timeout_leitura=0.2)
        self.pedido = self.ponte.criar_pedido({}, 10)

    def tearDown(self):
        self.ponte.fechar()

    def post(self, corpo=b'{"tipo":"ok"}', **headers):
        return urlopen(Request(f"{self.ponte.url}/api/result/{self.pedido.token}", data=corpo,
            headers={"X-NOC-Token": self.pedido.token, "Content-Type": "application/json", **headers}), timeout=3)

    def test_rejeita_origem_web_tamanho_e_transfer_encoding(self):
        for headers in ({"Origin": "https://evil.test"}, {"Origin": "null"},
                        {"Content-Length": "99999"}, {"Transfer-Encoding": "chunked"}):
            with self.subTest(headers=headers), self.assertRaises(HTTPError):
                self.post(**headers)
        self.assertTrue(self.pedido.eventos.empty())

    def test_fila_cheia_retorna_429_sem_bloquear_handler(self):
        for _ in range(self.pedido.eventos.maxsize):
            self.pedido.eventos.put_nowait(("ok", ""))
        with self.assertRaises(HTTPError) as erro:
            self.post()
        self.assertEqual(erro.exception.code, 429)

    def test_corpo_incompleto_tem_timeout(self):
        with socket.create_connection(("127.0.0.1", self.ponte.porta), timeout=3) as cliente:
            headers = (f"POST /api/result/{self.pedido.token} HTTP/1.0\r\n"
                       f"Host: 127.0.0.1:{self.ponte.porta}\r\nX-NOC-Token: {self.pedido.token}\r\n"
                       "Content-Type: application/json\r\nContent-Length: 100\r\n\r\n{")
            cliente.sendall(headers.encode())
            self.assertIn(b"408", cliente.recv(4096))
        self.assertTrue(self.pedido.eventos.empty())

    def test_descarte_durante_validacao_nao_publica_resultado(self):
        entrou, liberar = threading.Event(), threading.Event()
        self.pedido.dados = {"tipo": "conectar"}
        def validar(_):
            entrou.set()
            if not liberar.wait(3):
                raise TimeoutError()
            return []
        with patch("noc.edge_bridge.importar_eventos", side_effect=validar), ThreadPoolExecutor() as executor:
            futuro = executor.submit(self.post, json.dumps({"tipo": "importar", "payload": {}}).encode())
            try:
                self.assertTrue(entrou.wait(3))
                self.ponte.descartar(self.pedido)
            finally:
                liberar.set()
            with self.assertRaises(HTTPError) as erro:
                futuro.result(timeout=3)
            self.assertEqual(erro.exception.code, 404)
        self.assertTrue(self.pedido.eventos.empty())

    def test_inicializacao_concorrente_compartilha_um_servidor(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            pedidos = list(executor.map(lambda _: self.ponte.criar_pedido({}, 10), range(12)))
        self.assertEqual(len({p.token for p in pedidos}), 12)
        self.assertEqual(len(self.ponte.pedidos), 13)
