"""Estado operacional e apresentação dos atendimentos, sem I/O ou widgets."""

from datetime import datetime
import re
import unicodedata
from .historico_atendimento import tem_envio

ETAPAS = ("Recebido", "Em revisão", "Aguardando ticket", "Pronto para comunicar", "Aguardando ciência",
          "Em acompanhamento", "Aguardando validação", "Validado", "Concluído", "Arquivado")
MODELOS_ABERTURA = ("Abertura normal", "Abertura inicial")
MODELOS = (*MODELOS_ABERTURA, "Acionamento inicial", "Acionamento", "Atualização", "Cobrança",
           "Passagem de turno", "Normalização", "Encerramento")
ROTULOS_CAMPOS = {"alerta": "Alerta", "servidor": "Servidor", "severidade": "Severidade",
                  "situacao": "Dados operacionais", "horario": "Horário", "link_zabbix": "Link Zabbix",
                  "assunto": "Título", "descricao": "Descrição", "tipo": "Tipo/ação interna",
                  "categoria": "Categoria", "urgencia": "Urgência", "tempo_apontado": "Tempo apontado (00:03)",
                  "atividade": "Atividade (Observability)"}
STATUS_PREENCHIMENTO = {"preenchido": "preenchido", "pendente": "pendente",
                       "nao_localizado": "não localizado"}


def agora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto)).lower()
                   if unicodedata.category(c) != "Mn")


def severidade_padrao(valor):
    texto = normalizar(valor).strip()
    grupos = (("Desastre", ("disaster", "desastre", "critica", "urgente")),
              ("Alta", ("high", "alta")), ("Média", ("average", "media", "normal")),
              ("Aviso", ("warning", "aviso", "atencao")),
              ("Informação", ("information", "informacao")),
              ("Não classificado", ("not classified", "nao classificado")))
    return next((rotulo for rotulo, nomes in grupos if texto in nomes), valor or "Não informado")


def ticket_valido(valor):
    return bool(re.fullmatch(r"[0-9]{1,30}", valor or ""))


def link_ticket(url, ticket):
    if not ticket_valido(ticket):
        raise ValueError("Informe somente os números do ticket (até 30 dígitos).")
    return f"{url.rstrip('/')}/Ticket/Edit/{ticket}"


def etapa_incidente(item):
    meta, dados = item["meta"], item["dados"]
    if meta.get("arquivado"):
        return "Arquivado"
    estado = meta.get("acompanhamento", {}).get("estado")
    if estado in ETAPAS:
        return estado
    if ticket_valido(dados.get("ticket")) and dados.get("alerta") and (dados.get("servidor") or dados.get("origem_atendimento")):
        if tem_envio(item):
            return "Aguardando ciência"
        return "Pronto para comunicar"
    if meta.get("pedido", {}).get("estado") in ("abrindo", "aguardando"):
        return "Aguardando ticket"
    if meta.get("em_revisao") or meta.get("campos_revisados"):
        return "Em revisão"
    return "Recebido"


def pendencias_incidente(item):
    dados, meta = item["dados"], item["meta"]
    mensagens = list(meta.get("avisos_coleta", []))
    campos = ("alerta", "servidor", "severidade", "situacao", "horario") if dados.get("origem_atendimento", "") in ("", "Zabbix") else ("alerta",)
    faltantes = [ROTULOS_CAMPOS[c] for c in campos
                 if not dados.get(c)]
    if faltantes:
        mensagens.append("Campos sem informação: " + ", ".join(faltantes) + ".")
    if meta.get("atualizacoes"):
        mensagens.append(f"{len(meta['atualizacoes'])} atualização(ões) disponível(is); sua revisão foi preservada.")
    for campo, estado in meta.get("preenchimento", {}).items():
        if estado != "preenchido" and not ticket_valido(dados.get("ticket")):
            mensagens.append(f"Movidesk — {ROTULOS_CAMPOS.get(campo, campo)}: {STATUS_PREENCHIMENTO.get(estado, estado)}.")
    if meta.get("pedido", {}).get("mensagem"):
        mensagens.append(meta["pedido"]["mensagem"])
    if meta.get("ticket_conflito"):
        mensagens.append(f"Ticket retornado {meta['ticket_conflito']['ticket']} difere do informado. Confira o chamado.")
    return mensagens


def proxima_acao(item):
    dados, meta = item["dados"], item["meta"]
    etapa = etapa_incidente(item)
    if etapa == "Arquivado":
        return "Arquivado · Reabra o atendimento pela fila quando necessário."
    proxima = meta.get("acompanhamento", {}).get("proxima")
    if proxima:
        return f"{etapa} · {proxima['texto']} · {proxima['prazo']}"
    if etapa in ("Aguardando ciência", "Em acompanhamento", "Aguardando validação", "Validado", "Concluído"):
        return f"{etapa} · Consulte o histórico e defina a próxima ação na Central operacional."
    if meta.get("ticket_conflito"):
        return "Confira o ticket vinculado · Há um número diferente no retorno. Abra Pendências."
    if etapa == "Pronto para comunicar":
        return f"Pronto para comunicar · Ticket {dados['ticket']} vinculado."
    pedido = meta.get("pedido", {}).get("estado")
    if pedido in ("abrindo", "aguardando"):
        return "Aguardando ticket · Revise e salve o formulário no Movidesk."
    if pedido in ("erro", "expirado", "interrompido"):
        return "Retorno interrompido · Informe o ticket salvo ou prepare um novo formulário."
    if not dados.get("alerta") or not dados.get("servidor"):
        return f"{etapa} · Importe o evento ou complete alerta e servidor."
    return f"{etapa} · Revise os dados e crie ou informe o ticket."
