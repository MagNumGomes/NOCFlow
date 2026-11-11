"""Coordenação assíncrona dos pedidos Zabbix/Movidesk pela ponte local."""

import logging
import queue
import threading
import time

from .comunicados import gerar_html
from .edge_bridge import EdgeBridge, abrir_no_edge

LOGGER = logging.getLogger("noc")


class MovideskWorker(threading.Thread):
    """Coordena pedidos à extensão sem assumir nem fechar o navegador pessoal."""

    def __init__(self, config, eventos, abrir=abrir_no_edge, ponte=None):
        super().__init__(name="noc-movidesk", daemon=True)
        self.config = config
        self.eventos = eventos
        self.comandos = queue.Queue()
        self.encerrar = threading.Event()
        self.abrir = abrir
        self.ponte = ponte or EdgeBridge()
        self.pendentes = {}
        self.estado_conexao = "desconectado"

    def status(self, operacao, texto):
        self.eventos.put(("progresso", operacao, texto))

    def run(self):
        try:
            while not self.encerrar.is_set():
                self.receber_pendentes()
                try:
                    operacao, dados = self.comandos.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    if dados.get("_transferir_incidente"):
                        for token, (pedido, incidente) in list(self.pendentes.items()):
                            if incidente == dados["_transferir_incidente"]:
                                self.pendentes[token] = (pedido, dados["_destino"])
                    elif dados.get("_conectar"):
                        self.conectar(operacao)
                    elif dados.get("_retomar"):
                        self.retomar(operacao, dados["_incidente_id"])
                    elif self.preencher(operacao, dados):
                        self.eventos.put(("movidesk_ok", operacao, None))
                except Exception as exc:
                    LOGGER.exception("Falha na integração com o Movidesk")
                    if dados.get("_incidente_id"):
                        self.eventos.put(("pedido_status", dados["_incidente_id"], {"estado": "erro", "mensagem": str(exc)}))
                    if dados.get("_conectar"):
                        self.publicar_conexao("desconectado")
                    self.eventos.put(("erro", operacao, str(exc)))
        finally:
            self.ponte.fechar()

    def receber_pendentes(self):
        for token, (pedido, incidente) in list(self.pendentes.items()):
            remover = time.monotonic() >= pedido.expira
            if remover:
                if incidente is None:
                    self.publicar_conexao("expirado")
                else:
                    self.eventos.put(("pedido_status", incidente, {"estado": "expirado",
                        "mensagem": "Retorno expirado. Informe o número do ticket salvo; confira a guia antes de criar outro."}))
            elif incidente is None:
                self.publicar_conexao("conectado" if time.monotonic() - pedido.ultimo_sinal < 150 else "sem_resposta", pedido)
            while not remover:
                try:
                    tipo, mensagem = pedido.eventos.get_nowait()
                except queue.Empty:
                    break
                if tipo == "importar":
                    self.eventos.put(("zabbix_importado", None, mensagem))
                elif tipo == "ticket":
                    self.eventos.put(("ticket_recebido", incidente, mensagem))
                    remover = True
                elif tipo == "erro":
                    if incidente is None:
                        self.publicar_conexao("desconectado")
                    else:
                        self.eventos.put(("pedido_status", incidente, {"estado": "interrompido", "mensagem": mensagem}))
                    self.eventos.put(("integracao_aviso", incidente, mensagem))
                    remover = True
            if remover:
                self.ponte.descartar(pedido)
                self.pendentes.pop(token, None)

    def publicar_conexao(self, estado, pedido=None):
        if estado != self.estado_conexao:
            self.estado_conexao = estado
            self.eventos.put(("conexao_status", None, {"estado": estado,
                "expira": time.time() + pedido.expira - time.monotonic() if pedido else None}))

    def retomar(self, operacao, incidente):
        original = next((p for p, i in self.pendentes.values() if i == incidente and p.expira > time.monotonic()), None)
        if original is None:
            raise ValueError("O retorno não está mais ativo. Informe o ticket salvo ou prepare um novo formulário.")
        pedido = self.ponte.criar_pedido({"tipo": "retomar", "token_original": original.token}, 15)
        try:
            self.abrir(f"{self.ponte.url}/request/{pedido.token}")
            while not self.encerrar.is_set() and time.monotonic() < pedido.expira:
                self.receber_pendentes()
                try:
                    tipo, mensagem = pedido.eventos.get(timeout=0.1)
                except queue.Empty:
                    continue
                if tipo == "ok":
                    self.eventos.put(("pedido_status", incidente, {"estado": "aguardando",
                        "expira": time.time() + original.expira - time.monotonic()}))
                    self.eventos.put(("retomar_ok", operacao, None))
                    return
                if tipo == "erro":
                    raise ValueError(mensagem)
            if not self.encerrar.is_set():
                raise TimeoutError("Não foi possível localizar a guia. Confira a extensão e informe o ticket salvo.")
        finally:
            self.ponte.descartar(pedido)

    def conectar(self, operacao):
        pedido = self.ponte.criar_pedido({"tipo": "conectar"}, 15)
        try:
            self.abrir(f"{self.ponte.url}/request/{pedido.token}")
            while not self.encerrar.is_set() and time.monotonic() < pedido.expira:
                self.receber_pendentes()
                try:
                    tipo, mensagem = pedido.eventos.get(timeout=0.1)
                except queue.Empty:
                    continue
                if tipo == "ok":
                    for token, (anterior, incidente) in list(self.pendentes.items()):
                        if incidente is None:
                            self.ponte.descartar(anterior)
                            self.pendentes.pop(token, None)
                    pedido.expira = time.monotonic() + 43200
                    pedido.ultimo_sinal = time.monotonic()
                    self.pendentes[pedido.token] = (pedido, None)
                    # Uma reconexão renova o prazo mesmo se o estado anterior já era conectado.
                    self.estado_conexao = "conectando"
                    self.publicar_conexao("conectado", pedido)
                    self.eventos.put(("conexao_ok", operacao, None))
                    return
                if tipo == "erro":
                    raise ValueError(mensagem)
            if not self.encerrar.is_set():
                raise TimeoutError("A extensão não respondeu. Instale/recarregue a extensão NOCFlow e conecte novamente.")
        finally:
            if pedido.token not in self.pendentes:
                self.ponte.descartar(pedido)

    def preencher(self, operacao, dados):
        if self.encerrar.is_set():
            return False
        incidente = dados.get("_incidente_id", str(operacao))
        if dados.get("_novo_pedido"):
            for token, (anterior, origem) in list(self.pendentes.items()):
                if origem == incidente:
                    self.ponte.descartar(anterior)
                    self.pendentes.pop(token, None)
        if any(i == incidente and p.expira > time.monotonic() for p, i in self.pendentes.values()):
            self.retomar(operacao, incidente)
            return False
        pedido = self.ponte.criar_pedido({
            "url": f"{self.config.movidesk_url}/Ticket/Create",
            "assunto": " - ".join(v for v in (dados['alerta'], dados.get('servidor') or dados.get('servico', '')) if v),
            "alerta": dados["alerta"],
            "servidor": dados.get("servidor", ""),
            "severidade": dados.get("prioridade") or dados.get("severidade", ""),
            "categoria": dados.get("categoria", "Alerta") or "Alerta",
            "link_zabbix": dados.get("link_zabbix", ""),
            "html": gerar_html(dados),
            "timeout_login": self.config.timeout_login, "timeout_retorno": self.config.timeout_ticket,
        }, self.config.timeout_login)
        self.eventos.put(("pedido_status", incidente, {"estado": "abrindo"}))
        try:
            self.status(operacao, "Abrindo guia no seu Edge e aguardando a extensão NOCFlow…")
            self.abrir(f"{self.ponte.url}/request/{pedido.token}")
            limite_conexao = time.monotonic() + 15
            while not self.encerrar.is_set():
                self.receber_pendentes()
                if time.monotonic() >= pedido.expira:
                    raise TimeoutError("O formulário não ficou pronto no prazo. Confira o login e a extensão NOCFlow no Edge. Revise a guia aberta antes de tentar novamente.")
                if not pedido.conectado.is_set() and time.monotonic() >= limite_conexao:
                    raise TimeoutError("A extensão NOCFlow não respondeu. Clique em Instalar extensão do Edge e instale/ative a extensão no perfil em que o Movidesk está logado. Depois tente novamente.")
                try:
                    tipo, mensagem = pedido.eventos.get(timeout=0.2)
                except queue.Empty:
                    continue
                if tipo == "ok":
                    pedido.expira = time.monotonic() + self.config.timeout_ticket
                    self.pendentes[pedido.token] = (pedido, incidente)
                    self.eventos.put(("pedido_status", incidente, {"estado": "aguardando",
                        "expira": time.time() + self.config.timeout_ticket,
                        "campos": mensagem.get("campos", {}) if isinstance(mensagem, dict) else {}}))
                    return True
                if tipo == "erro":
                    raise ValueError(mensagem)
                self.status(operacao, mensagem)
            return False
        finally:
            if pedido.token not in self.pendentes:
                self.ponte.descartar(pedido)
