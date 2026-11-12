"""Ponte local entre o aplicativo e a extensão instalada no Edge do usuário."""

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import threading
import time
from urllib.parse import urlsplit, parse_qs

from .configuracao import diretorio_recursos, url_valida
from .incidentes import importar_eventos, MAX_IMPORTACAO

PORTA_EDGE = 18764
ARQUIVOS_EXTENSAO = ("manifest.json", "background.js", "bridge.js", "ticket.js", "preencher.js", "movidesk.js", "zabbix.js", "coletor.js", "popup.html", "popup.css", "popup.js", "whatsapp.js", "vendor/html2canvas.min.js", "vendor/LICENSE.html2canvas")


def caminho_edge():
    candidatos = [
        Path(os.getenv("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.getenv("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    raise FileNotFoundError("Microsoft Edge não encontrado. Instale o Edge para usar a integração com o Movidesk.")


def abrir_no_edge(url):
    # Uma chamada normal ao Edge reutiliza o perfil/janela do próprio usuário.
    subprocess.Popen(
        [str(caminho_edge()), "--new-tab", url],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def preparar_extensao(diretorio):
    origem = diretorio_recursos() / "edge_extension"
    destino = diretorio / "edge_extension"
    if origem.resolve() == destino.resolve():
        destino = diretorio / ".noc_data" / "edge_extension"
    configuracao = diretorio / ".noc_data" / "extensao.json"
    if configuracao.exists():
        preferencias = json.loads(configuracao.read_text(encoding="utf-8"))
        dominios = preferencias.get("zabbix_origens", [])
    else:
        # Migra as permissões da extensão instalada antes de atualizar seus arquivos.
        anterior = destino / "manifest.json"
        manifesto = json.loads((anterior if anterior.exists() else origem / "manifest.json").read_text(encoding="utf-8"))
        dominios = [url.removesuffix("/*") for script in manifesto.get("content_scripts", [])
                    if "zabbix.js" in script.get("js", []) for url in script.get("matches", [])]
    if not isinstance(dominios, list) or not dominios or any(
            not isinstance(url, str) or not url_valida(url) or "*" in url or
            urlsplit(url).path not in ("", "/") or urlsplit(url).query or urlsplit(url).fragment for url in dominios):
        raise ValueError("Configure zabbix_origens em .noc_data/extensao.json com origens HTTP/HTTPS válidas.")
    dominios = list(dict.fromkeys(url.rstrip("/") for url in dominios))
    configuracao.parent.mkdir(parents=True, exist_ok=True)
    if not configuracao.exists():
        configuracao.write_text(json.dumps({"zabbix_origens": dominios}, indent=2), encoding="utf-8")
    destino.mkdir(parents=True, exist_ok=True)
    for nome in ARQUIVOS_EXTENSAO:
        arquivo = origem / nome
        alvo = destino / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        conteudo = arquivo.read_bytes()
        if nome == "manifest.json":
            manifesto = json.loads(conteudo)
            antigos = {url for script in manifesto["content_scripts"] if "zabbix.js" in script["js"] for url in script["matches"]}
            manifesto["host_permissions"] = [url for url in manifesto["host_permissions"] if url not in antigos] + [url + "/*" for url in dominios]
            for script in manifesto["content_scripts"]:
                if "zabbix.js" in script["js"]:
                    script["matches"] = [url + "/*" for url in dominios]
            conteudo = json.dumps(manifesto, ensure_ascii=False, indent=2).encode("utf-8")
        elif nome == "background.js":
            linhas = conteudo.decode("utf-8").splitlines()
            conteudo = ("\n".join("const ZABBIX = new Set(" + json.dumps(dominios) + ");" if linha.startswith("const ZABBIX = new Set(") else linha for linha in linhas) + "\n").encode("utf-8")
        if not alvo.exists() or alvo.read_bytes() != conteudo:
            alvo.write_bytes(conteudo)
    return destino


@dataclass
class Pedido:
    token: str
    dados: dict
    expira: float
    eventos: queue.Queue = field(default_factory=queue.Queue)
    conectado: threading.Event = field(default_factory=threading.Event)
    ultimo_sinal: float = field(default_factory=time.monotonic)


class EdgeBridge:
    def __init__(self, porta=PORTA_EDGE):
        self.porta = porta
        self.servidor = None
        self.thread = None
        self.pedidos = {}
        self.lock = threading.Lock()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.porta}"

    def iniciar(self):
        if self.servidor:
            return
        ponte = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass  # Tokens não devem aparecer em logs HTTP.

            def responder(self, status, conteudo, tipo="application/json; charset=utf-8"):
                corpo = conteudo.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
                self.end_headers()
                try:
                    self.wfile.write(corpo)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def pedido(self, prefixo):
                if self.headers.get("Host") != f"127.0.0.1:{ponte.porta}":
                    return None
                if not self.path.startswith(prefixo):
                    return None
                token = self.path[len(prefixo):]
                with ponte.lock:
                    pedido = ponte.pedidos.get(token)
                    if pedido and pedido.expira > time.monotonic():
                        return pedido
                return None

            def do_GET(self):
                if self.path.startswith("/request/"):
                    if not self.pedido("/request/"):
                        self.responder(404, "Pedido expirado. Volte ao NOCFlow e tente novamente.", "text/plain; charset=utf-8")
                        return
                    self.responder(200, """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Conectando NOCFlow ao Edge</title>
<style>body{font:18px Segoe UI,sans-serif;max-width:760px;margin:60px auto;padding:20px;line-height:1.6}h1{color:#175cd3}</style>
<h1>Conectando NOCFlow ao Edge…</h1>
<p>A extensão NOCFlow está conectando esta operação à sua sessão do Edge.</p>
<p>Se esta tela permanecer aberta, volte ao aplicativo e clique em <b>Instalar extensão do Edge</b>.
Instale a extensão no mesmo perfil do Edge em que você usa o Movidesk e tente novamente.</p>
<p>Após instalar ou recarregar a extensão, retome a operação pelo aplicativo.</p>
</html>""", "text/html; charset=utf-8")
                    return
                pedido = self.pedido("/api/request/")
                if pedido and secrets.compare_digest(self.headers.get("X-NOC-Token", ""), pedido.token):
                    pedido.conectado.set()
                    self.responder(200, json.dumps(pedido.dados, ensure_ascii=False))
                else:
                    self.responder(404, '{"erro":"Pedido expirado ou desconhecido."}')

            def do_POST(self):
                pedido = self.pedido("/api/result/")
                if not pedido or not secrets.compare_digest(self.headers.get("X-NOC-Token", ""), pedido.token):
                    self.responder(404, '{"erro":"Pedido expirado ou desconhecido."}')
                    return
                try:
                    tamanho = int(self.headers.get("Content-Length", "0"))
                    limite = MAX_IMPORTACAO if pedido.dados.get("tipo") == "conectar" else 8192
                    if not 0 < tamanho <= limite or self.headers.get_content_type() != "application/json":
                        raise ValueError()
                    evento = json.loads(self.rfile.read(tamanho))
                    tipo = evento.get("tipo")
                    if tipo == "importar" and pedido.dados.get("tipo") == "conectar":
                        mensagem = importar_eventos(evento.get("payload"))
                    elif tipo == "sinal" and pedido.dados.get("tipo") == "conectar":
                        mensagem = ""
                    elif tipo == "ticket" and pedido.dados.get("url"):
                        ticket, link = evento.get("ticket", ""), evento.get("url", "")
                        if not isinstance(ticket, str) or not ticket.isascii() or not ticket.isdigit() or len(ticket) > 30 or not isinstance(link, str):
                            raise ValueError()
                        origem, destino = urlsplit(link), urlsplit(pedido.dados["url"])
                        caminho = origem.path.rstrip("/").lower()
                        base = destino.path.rsplit("/", 2)[0].lower()
                        rotas = (f"{base}/ticket/edit", f"{base}/ticket/create")
                        id_url = parse_qs(origem.query).get("id", [""])[0]
                        if (origem.scheme, origem.netloc) != (destino.scheme, destino.netloc) or not (any(caminho == f"{r}/{ticket}" for r in rotas) or (caminho in rotas and id_url == ticket)):
                            raise ValueError()
                        mensagem = {"ticket": ticket, "url": link}
                    elif tipo in ("progresso", "ok", "erro") and isinstance(evento.get("mensagem", ""), str):
                        mensagem = evento.get("mensagem", "")[:1200]
                        if tipo == "ok" and "campos" in evento:
                            campos = evento["campos"]
                            permitidos = {"assunto", "descricao", "tipo", "categoria", "urgencia", "tempo_apontado", "atividade"}
                            if not isinstance(campos, dict) or set(campos) - permitidos or any(
                                v not in ("preenchido", "pendente", "nao_localizado") for v in campos.values()
                            ):
                                raise ValueError()
                            mensagem = {"mensagem": mensagem, "campos": campos}
                    else:
                        raise ValueError()
                    pedido.conectado.set()
                    pedido.ultimo_sinal = time.monotonic()
                    pedido.eventos.put((tipo, mensagem))
                    self.responder(200, '{"ok":true}')
                except (ValueError, TypeError, AttributeError):
                    self.responder(400, '{"erro":"Evento inválido."}')

        try:
            self.servidor = ThreadingHTTPServer(("127.0.0.1", self.porta), Handler)
        except OSError as exc:
            raise OSError(f"A porta local {self.porta} está em uso. Feche outra instância do NOCFlow e tente novamente.") from exc
        self.servidor.daemon_threads = True
        self.porta = self.servidor.server_port
        self.thread = threading.Thread(target=self.servidor.serve_forever, name="noc-edge-http", daemon=True)
        self.thread.start()

    def criar_pedido(self, dados, segundos):
        self.iniciar()
        pedido = Pedido(secrets.token_urlsafe(32), dados, time.monotonic() + segundos)
        with self.lock:
            self.pedidos[pedido.token] = pedido
        return pedido

    def descartar(self, pedido):
        with self.lock:
            self.pedidos.pop(pedido.token, None)

    def fechar(self):
        with self.lock:
            self.pedidos.clear()
        if self.servidor:
            self.servidor.shutdown()
            self.servidor.server_close()
            self.thread.join(timeout=3)
            self.servidor = None
