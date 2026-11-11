"""Importação versionada e fila de eventos, sem rede e sem IA."""

import base64
from copy import deepcopy
import io
import json
import math
import uuid
from urllib.parse import parse_qs, urlsplit, urlunsplit

from PIL import Image

from .configuracao import url_valida
from .atendimento import agora
from .historico_atendimento import registrar_evento, validar_historico
from .agenda_operacional import validar_agenda

CAMPOS_EVENTO = ("alerta", "servidor", "severidade", "situacao", "horario")
CAMPOS_FORMULARIO = CAMPOS_EVENTO + ("link_zabbix", "ticket", "acionamento", "time_resp",
    "origem_atendimento", "natureza", "servico", "perfil", "ambiente", "solicitante",
    "relato_original", "impacto", "prioridade", "tags")
MAX_EVENTOS = 100
MAX_IMPORTACAO = 2_000_000


def identidade_evento(link):
    if not url_valida(link):
        raise ValueError("O evento precisa de um link HTTP/HTTPS válido do Zabbix.")
    url = urlsplit(link)
    evento = parse_qs(url.query).get("eventid", [""])[0]
    if not evento.isascii() or not evento.isdigit():
        raise ValueError("O link do Zabbix precisa conter eventid numérico.")
    instancia = urlunsplit((url.scheme.lower(), url.netloc.lower(), url.path.rsplit("/", 1)[0], "", ""))
    return instancia, evento


def importar_eventos(conteudo):
    if isinstance(conteudo, str):
        if len(conteudo.encode("utf-8")) > MAX_IMPORTACAO:
            raise ValueError("Importação muito grande; limite de 2 MB.")
        try:
            conteudo = json.loads(conteudo)
        except ValueError:
            raise ValueError("Copie os dados JSON pelo botão do Zabbix antes de importar.") from None
    if not isinstance(conteudo, dict) or conteudo.get("versao") != 1 or conteudo.get("origem") != "zabbix":
        raise ValueError("Formato desconhecido. Use a exportação NOCFlow versão 1 do Zabbix.")
    eventos = conteudo.get("eventos", [conteudo])
    if not isinstance(eventos, list) or not 1 <= len(eventos) <= MAX_EVENTOS:
        raise ValueError(f"Importe entre 1 e {MAX_EVENTOS} eventos por vez.")
    resultado = []
    for evento in eventos:
        if not isinstance(evento, dict):
            raise ValueError("Evento inválido na importação.")
        dados = {}
        for campo in CAMPOS_EVENTO + ("link_zabbix",):
            valor = evento.get(campo, "")
            if not isinstance(valor, str) or len(valor) > 30000:
                raise ValueError(f"Campo inválido ou muito extenso: {campo}.")
            dados[campo] = valor.strip()
        instancia, eventid = identidade_evento(dados["link_zabbix"])
        if evento.get("eventid", eventid) != eventid:
            raise ValueError("O eventid não corresponde ao link importado.")
        imagem = None
        imagem_b64 = evento.get("imagem_base64", "")
        if not isinstance(imagem_b64, str) or len(imagem_b64) > MAX_IMPORTACAO:
            raise ValueError("Campo inválido ou muito extenso: imagem_base64.")
        if imagem_b64:
            bruto = imagem_b64.split(",", 1)[-1].strip() if imagem_b64.startswith("data:image/") else imagem_b64.strip()
            try:
                with Image.open(io.BytesIO(base64.b64decode(bruto, validate=True))) as img:
                    imagem = img.convert("RGB")
            except Exception:
                raise ValueError("Imagem inválida na importação.") from None
        item_importado = {"dados": dados, "meta": {"origem": "DOM", "instancia": instancia, "eventid": eventid}}
        aviso = evento.get("aviso", "")
        if not isinstance(aviso, str) or len(aviso) > 1200:
            raise ValueError("Aviso de coleta inválido ou muito extenso.")
        item_importado["meta"]["avisos_coleta"] = [aviso] if aviso else []
        if imagem is not None:
            item_importado["imagem"] = imagem
        resultado.append(item_importado)
    return resultado


class FilaIncidentes:
    def __init__(self):
        self.itens = []
        self.ativo = ""
        self.operacional = {}
        self.novo()

    def novo(self):
        item = {"id": uuid.uuid4().hex, "dados": dict.fromkeys(CAMPOS_FORMULARIO, ""), "meta": {}, "imagem": None}
        self.itens.append(item)
        self.ativo = item["id"]
        return item

    def obter(self, identificador=None):
        return next((i for i in self.itens if i["id"] == (identificador or self.ativo)), None)

    def importar(self, eventos):
        ids = []
        for evento in eventos:
            meta = evento["meta"]
            item = next((i for i in self.itens if (i["meta"].get("instancia"), i["meta"].get("eventid")) == (meta["instancia"], meta["eventid"])), None)
            if item is None:
                item = next((i for i in self.itens if not any(i["dados"].values()) and i["imagem"] is None
                             and not i["meta"].get("eventid") and not i["meta"].get("arquivado")), None)
                if item is None:
                    ativo = self.ativo
                    item = self.novo()
                    self.ativo = ativo
            revisados = set(item["meta"].get("campos_revisados", []))
            atualizacoes = item["meta"].setdefault("atualizacoes", {})
            # Correções do operador permanecem; diferenças podem ser aplicadas por campo.
            for campo, valor in evento["dados"].items():
                if campo in revisados and valor and valor != item["dados"].get(campo):
                    atualizacoes[campo] = valor
                    continue
                if valor == item["dados"].get(campo):
                    atualizacoes.pop(campo, None)
                if valor or not item["dados"].get(campo):
                    item["dados"][campo] = valor
            if evento.get("imagem") is not None:
                item["imagem"] = evento["imagem"]
                item["meta"].pop("recortes", None)
                item["meta"].pop("evidencia_ticket", None)
            item["meta"].update(meta)
            item["meta"]["coletado_em"] = agora()
            if not item["meta"].get("recebido_em"):
                registrar_evento(item, "Recebido", "Evento importado do Zabbix.", fonte="importacao")
            item["dados"]["origem_atendimento"] = "Zabbix"
            item["dados"]["natureza"] = item["dados"].get("natureza") or "Incidente"
            ids.append(item["id"])
        return list(dict.fromkeys(ids))

    def snapshot(self):
        return {"ativo": self.ativo, "itens": [{**i, "dados": dict(i["dados"]), "meta": deepcopy(i["meta"])} for i in self.itens],
                "operacional": deepcopy(self.operacional)}

    def resolver_atualizacao(self, identificador, campo, aplicar):
        item = self.obter(identificador)
        if item is None:
            return
        valor = item["meta"].get("atualizacoes", {}).pop(campo, None)
        if aplicar and valor is not None:
            item["dados"][campo] = valor
            item["meta"]["campos_revisados"] = [c for c in item["meta"].get("campos_revisados", []) if c != campo]

    def restaurar(self, estado):
        if not isinstance(estado, dict) or not isinstance(estado.get("itens"), list) or not estado["itens"]:
            raise ValueError("Fila de incidentes inválida.")
        validar_agenda(estado.get("operacional", {}))
        ids = set()
        for item in estado["itens"]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or item["id"] in ids:
                raise ValueError("Identificador inválido na fila.")
            ids.add(item["id"])
            if not isinstance(item.get("dados"), dict) or any(not isinstance(item["dados"].get(c, ""), str) for c in CAMPOS_FORMULARIO):
                raise ValueError("Dados inválidos na fila.")
            if not isinstance(item.get("meta"), dict):
                raise ValueError("Metadados inválidos na fila.")
            meta = item["meta"]
            validar_historico(meta)
            for chave in ("atualizacoes", "recortes", "comunicacao", "copias", "pedido", "preenchimento", "ticket_conflito"):
                if chave in meta and not isinstance(meta[chave], dict):
                    raise ValueError(f"Metadados inválidos: {chave}.")
            for chave in ("avisos_coleta", "campos_revisados"):
                if chave in meta and (not isinstance(meta[chave], list) or any(not isinstance(v, str) for v in meta[chave])):
                    raise ValueError(f"Metadados inválidos: {chave}.")
            for campo, valor in meta.get("atualizacoes", {}).items():
                if campo not in (*CAMPOS_EVENTO, "link_zabbix") or not isinstance(valor, str):
                    raise ValueError("Atualização de campo inválida.")
            if not isinstance(meta.get("comunicacao", {}).get("texto", ""), str):
                raise ValueError("Texto de comunicação inválido.")
            if any(not isinstance(v, str) for v in meta.get("preenchimento", {}).values()):
                raise ValueError("Resultado de preenchimento inválido.")
            if any(not isinstance(meta.get("pedido", {}).get(c, ""), str) for c in ("estado", "mensagem")):
                raise ValueError("Estado de retorno inválido.")
            conflito = meta.get("ticket_conflito")
            if conflito and any(not isinstance(conflito.get(c), str) for c in ("ticket", "url")):
                raise ValueError("Conflito de ticket inválido.")
            if not isinstance(meta.get("coletado_em", ""), str):
                raise ValueError("Horário de coleta inválido.")
            if any(not isinstance(c, dict) or not all(isinstance(v, str) for v in c.values()) for c in meta.get("copias", {}).values()):
                raise ValueError("Registro de cópia inválido.")
            prazo = meta.get("pedido", {}).get("expira")
            if prazo is not None and (not isinstance(prazo, (float, int)) or not math.isfinite(prazo) or not 0 < prazo < 10**11):
                raise ValueError("Prazo de retorno inválido.")
        if estado.get("ativo") not in ids:
            raise ValueError("Incidente ativo não encontrado na fila.")
        self.itens = [{**item, "dados": {c: item["dados"].get(c, "") for c in CAMPOS_FORMULARIO},
                       "meta": deepcopy(item["meta"]), "imagem": item.get("imagem")} for item in estado["itens"]]
        self.ativo = estado["ativo"]
        self.operacional = deepcopy(estado.get("operacional", {}))
