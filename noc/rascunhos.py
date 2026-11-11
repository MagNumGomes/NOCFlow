"""Persistência atômica da fila e migração dos rascunhos locais."""

import base64
import io
import json
import logging
import os
import queue
import shutil
import threading
import time

from PIL import Image

from .incidentes import FilaIncidentes, CAMPOS_FORMULARIO

LOGGER = logging.getLogger("noc")


class RascunhoWorker(threading.Thread):
    """Serializa gravações atômicas; snapshots antigos nunca vencem os novos."""

    def __init__(self, config, eventos):
        super().__init__(name="noc-rascunho", daemon=True)
        self.arquivo = config.dados_dir / "rascunho.json"
        self.eventos = eventos
        self.comandos = queue.Queue()
        self.permitir_salvamento = True
        self.fila_carregada = None

    def carregar(self):
        self.fila_carregada = None
        if not self.arquivo.exists():
            return {}, None
        payload = json.loads(self.arquivo.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("versao") not in (1, 2) or not isinstance(payload.get("dados"), dict):
            raise ValueError("Formato de rascunho inválido.")
        dados = {campo: payload["dados"].get(campo, "") for campo in CAMPOS_FORMULARIO}
        if not all(isinstance(valor, str) for valor in dados.values()):
            raise ValueError("Campos do rascunho inválidos.")

        def decodificar(valor):
            if valor:
                with Image.open(io.BytesIO(base64.b64decode(valor, validate=True))) as original:
                    return original.convert("RGB")
            return None

        imagem = decodificar(payload.get("imagem"))
        if "fila" in payload:
            fila = FilaIncidentes()
            fila.restaurar(payload["fila"])
            for item in fila.itens:
                item["imagem"] = decodificar(item.get("imagem"))
            self.fila_carregada = fila.snapshot()
        return dados, imagem

    def run(self):
        try:
            self.eventos.put(("rascunho_carregado", None, self.carregar()))
        except Exception as exc:
            LOGGER.exception("Falha ao recuperar rascunho")
            detalhe = str(exc)
            try:
                backup = self.arquivo.with_name(f"rascunho-invalido-{time.time_ns()}.json")
                shutil.copy2(self.arquivo, backup)
                detalhe += f"\nUma cópia do arquivo original foi preservada em {backup.name}."
            except OSError:
                self.permitir_salvamento = False
                detalhe += "\nNão foi possível preservar o arquivo original; o salvamento está suspenso nesta sessão."
            self.eventos.put(("rascunho_erro_carga", None, detalhe))
        cache_imagens = {}
        while True:
            comando = self.comandos.get()
            if comando is None:
                return
            encerrar_apos_gravacao = False
            # Durante I/O lento, basta persistir o snapshot mais recente da fila.
            while True:
                try:
                    seguinte = self.comandos.get_nowait()
                except queue.Empty:
                    break
                if seguinte is None:
                    encerrar_apos_gravacao = True
                    break
                comando = seguinte
            revisao, dados, imagem = comando[:3]
            estado = comando[3] if len(comando) > 3 else None
            try:
                if not self.permitir_salvamento:
                    raise OSError("O rascunho original precisa ser recuperado antes de gravar novos dados.")
                usados = {}

                def codificar(valor):
                    if valor is None:
                        return None
                    chave = id(valor)
                    anterior = usados.get(chave) or cache_imagens.get(chave)
                    if anterior and anterior[0] is valor:
                        convertido = anterior[1]
                    else:
                        buffer = io.BytesIO()
                        valor.save(buffer, format="PNG")
                        convertido = base64.b64encode(buffer.getvalue()).decode("ascii")
                    usados[chave] = (valor, convertido)
                    return convertido

                payload = {"versao": 2, "dados": dados, "imagem": codificar(imagem)}
                if estado:
                    payload["fila"] = {"ativo": estado["ativo"], "itens": [{**i, "imagem": codificar(i.get("imagem"))} for i in estado["itens"]],
                                       "operacional": estado.get("operacional", {})}
                cache_imagens = usados
                self.arquivo.parent.mkdir(parents=True, exist_ok=True)
                temporario = self.arquivo.with_suffix(".tmp")
                with temporario.open("w", encoding="utf-8") as arquivo:
                    json.dump(payload, arquivo, ensure_ascii=False)
                    arquivo.flush()
                    os.fsync(arquivo.fileno())
                temporario.replace(self.arquivo)
                self.eventos.put(("rascunho_salvo", revisao, None))
            except Exception as exc:
                LOGGER.exception("Falha ao salvar rascunho")
                self.eventos.put(("rascunho_erro", revisao, str(exc)))
            if encerrar_apos_gravacao:
                return
