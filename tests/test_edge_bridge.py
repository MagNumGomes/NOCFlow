import json
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from noc.edge_bridge import EdgeBridge


class EdgeBridgeTests(unittest.TestCase):
    def setUp(self):
        self.ponte = EdgeBridge(porta=0)
        self.pedido = self.ponte.criar_pedido({"assunto": "Incidente privado"}, 10)

    def tearDown(self):
        self.ponte.fechar()

    def requisicao(self, rota="request", headers=None, data=None):
        return Request(f"{self.ponte.url}/api/{rota}/{self.pedido.token}", headers=headers or {}, data=data)

    def test_dados_exigem_token_e_nao_aparecem_na_pagina_de_conexao(self):
        with self.assertRaises(HTTPError) as erro:
            urlopen(self.requisicao(), timeout=3)
        self.assertEqual(erro.exception.code, 404)
        with urlopen(f"{self.ponte.url}/request/{self.pedido.token}", timeout=3) as resposta:
            self.assertNotIn("Incidente privado", resposta.read().decode())
        with urlopen(self.requisicao(headers={"X-NOC-Token": self.pedido.token}), timeout=3) as resposta:
            self.assertEqual(json.load(resposta)["assunto"], "Incidente privado")
        self.assertTrue(self.pedido.conectado.is_set())

    def test_resultado_chega_ao_worker_e_pedido_descartado_nao_pode_ser_reutilizado(self):
        headers = {"X-NOC-Token": self.pedido.token, "Content-Type": "application/json"}
        with urlopen(self.requisicao("result", headers, b'{"tipo":"ok"}'), timeout=3) as resposta:
            self.assertEqual(resposta.status, 200)
        self.assertEqual(self.pedido.eventos.get(timeout=1), ("ok", ""))
        self.ponte.descartar(self.pedido)
        with self.assertRaises(HTTPError) as erro:
            urlopen(self.requisicao(headers=headers), timeout=3)
        self.assertEqual(erro.exception.code, 404)

    def test_expiracao_e_host_incorreto_bloqueiam_acesso(self):
        headers = {"X-NOC-Token": self.pedido.token, "Host": "outro-host"}
        with self.assertRaises(HTTPError):
            urlopen(self.requisicao(headers=headers), timeout=3)
        self.pedido.expira = time.monotonic() - 1
        with self.assertRaises(HTTPError):
            urlopen(self.requisicao(headers={"X-NOC-Token": self.pedido.token}), timeout=3)

    def test_importacao_so_no_canal_de_conexao_autenticado(self):
        payload = {"versao": 1, "origem": "zabbix", "eventid": "10", "link_zabbix": "https://zabbix.test/tr_events.php?eventid=10", "servidor": "host-01"}
        corpo = json.dumps({"tipo": "importar", "payload": payload}).encode()
        headers = {"Content-Type": "application/json", "X-NOC-Token": self.pedido.token}
        with self.assertRaises(HTTPError):
            urlopen(self.requisicao("result", headers, corpo), timeout=3)
        self.pedido.dados = {"tipo": "conectar"}
        with urlopen(self.requisicao("result", headers, corpo), timeout=3) as resposta:
            self.assertEqual(resposta.status, 200)
        tipo, eventos = self.pedido.eventos.get(timeout=1)
        self.assertEqual(tipo, "importar")
        self.assertEqual(eventos[0]["meta"]["eventid"], "10")
        with self.assertRaises(HTTPError):
            urlopen(self.requisicao("result", {"Content-Type": "application/json"}, corpo), timeout=3)

    def test_retorno_ticket_exige_url_da_instancia_e_id_correspondente(self):
        self.pedido.dados = {"url": "https://empresa.movidesk.com/Ticket/Create"}
        headers = {"Content-Type": "application/json", "X-NOC-Token": self.pedido.token}
        for link in ("https://outra.movidesk.com/Ticket/Edit/123", "https://empresa.movidesk.com/Ticket/Edit/999", "https://empresa.movidesk.com/Outro/123"):
            with self.subTest(link=link), self.assertRaises(HTTPError):
                urlopen(self.requisicao("result", headers, json.dumps({"tipo": "ticket", "ticket": "123", "url": link}).encode()), timeout=3)
        link = "https://empresa.movidesk.com/Ticket/Edit/123"
        with urlopen(self.requisicao("result", headers, json.dumps({"tipo": "ticket", "ticket": "123", "url": link}).encode()), timeout=3):
            pass
        self.assertEqual(self.pedido.eventos.get(timeout=1), ("ticket", {"ticket": "123", "url": link}))

    def test_relatorio_por_campo_e_sinal_de_conexao_sao_validados(self):
        headers = {"Content-Type": "application/json", "X-NOC-Token": self.pedido.token}
        for campos in ({"categoria": "desconhecido"}, {"qualquer": "preenchido"}, []):
            with self.subTest(campos=campos), self.assertRaises(HTTPError):
                urlopen(self.requisicao("result", headers, json.dumps({"tipo": "ok", "campos": campos}).encode()), timeout=3)
        campos = {"assunto": "preenchido", "categoria": "pendente", "urgencia": "nao_localizado",
                  "tempo_apontado": "preenchido", "atividade": "pendente"}
        with urlopen(self.requisicao("result", headers, json.dumps({"tipo": "ok", "campos": campos}).encode()), timeout=3):
            pass
        self.assertEqual(self.pedido.eventos.get(timeout=1)[1]["campos"], campos)
        with self.assertRaises(HTTPError):
            urlopen(self.requisicao("result", headers, b'{"tipo":"sinal"}'), timeout=3)
        self.pedido.dados = {"tipo": "conectar"}
        self.pedido.ultimo_sinal = 0
        with urlopen(self.requisicao("result", headers, b'{"tipo":"sinal"}'), timeout=3):
            pass
        self.assertGreater(self.pedido.ultimo_sinal, 0)
