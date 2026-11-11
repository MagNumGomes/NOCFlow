from pathlib import Path
import queue
import time
import unittest
import json
from urllib.request import Request, urlopen

from noc.configuracao import Config
from noc.edge_bridge import EdgeBridge
from noc.movidesk import MovideskWorker


class RetornoTests(unittest.TestCase):
    def test_recuperacao_explicita_substitui_vinculo_da_guia_perdida(self):
        eventos = queue.Queue()
        ponte = EdgeBridge(porta=0)
        def confirmar_novo(url):
            token = url.rsplit("/", 1)[-1]
            request = Request(f"{ponte.url}/api/result/{token}", data=json.dumps({"tipo": "ok", "campos": {"assunto": "preenchido"}}).encode(),
                              headers={"Content-Type": "application/json", "X-NOC-Token": token})
            with urlopen(request, timeout=3):
                pass
        worker = MovideskWorker(Config(Path(".")), eventos, abrir=confirmar_novo, ponte=ponte)
        try:
            anterior = ponte.criar_pedido({"url": "https://empresa.movidesk.com/Ticket/Create"}, 3600)
            outro = ponte.criar_pedido({"url": "https://empresa.movidesk.com/Ticket/Create"}, 3600)
            worker.pendentes = {anterior.token: (anterior, "incidente"), outro.token: (outro, "outro")}
            self.assertTrue(worker.preencher(1, {"_incidente_id": "incidente", "_novo_pedido": True, "alerta": "CPU", "servidor": "host"}))
            self.assertNotIn(anterior.token, ponte.pedidos)
            self.assertNotIn(anterior.token, worker.pendentes)
            self.assertIn(outro.token, worker.pendentes)
            self.assertEqual(len(worker.pendentes), 2)
            novo = next(p for p, i in worker.pendentes.values() if i == "incidente")
            self.assertNotEqual(novo.token, anterior.token)
            novo.eventos.put(("ticket", {"ticket": "456", "url": "https://empresa.movidesk.com/Ticket/Edit/456"}))
            worker.receber_pendentes()
            retornos = [e for e in list(eventos.queue) if e[0] == "ticket_recebido"]
            self.assertEqual(retornos[0][1], "incidente")
            self.assertEqual(retornos[0][2]["ticket"], "456")
        finally:
            ponte.fechar()

    def test_expiracao_e_perda_de_sinal_publicam_estado_sem_consultar_sites(self):
        eventos = queue.Queue()
        ponte = EdgeBridge(porta=0)
        worker = MovideskWorker(Config(Path(".")), eventos, ponte=ponte)
        try:
            conexao = ponte.criar_pedido({"tipo": "conectar"}, 3600)
            ticket = ponte.criar_pedido({"url": "https://empresa.movidesk.com/Ticket/Create"}, 60)
            worker.pendentes = {conexao.token: (conexao, None), ticket.token: (ticket, "incidente")}
            worker.receber_pendentes()
            self.assertEqual(eventos.get_nowait()[2]["estado"], "conectado")
            conexao.ultimo_sinal = time.monotonic() - 151
            worker.receber_pendentes()
            self.assertEqual(eventos.get_nowait()[2]["estado"], "sem_resposta")
            conexao.ultimo_sinal = time.monotonic()
            ticket.expira = time.monotonic() - 1
            worker.receber_pendentes()
            self.assertEqual(eventos.get_nowait()[2]["estado"], "conectado")
            tipo, incidente, estado = eventos.get_nowait()
            self.assertEqual((tipo, incidente, estado["estado"]), ("pedido_status", "incidente", "expirado"))
            self.assertNotIn(ticket.token, worker.pendentes)
            self.assertIsNone(worker.receber_pendentes())
            self.assertTrue(eventos.empty())
        finally:
            ponte.fechar()
