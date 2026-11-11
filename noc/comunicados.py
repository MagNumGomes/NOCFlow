"""Validação do formulário e templates locais para tickets e comunicados."""

import base64
from datetime import datetime
from html import escape
import io
import re

from .configuracao import url_valida
from .incidentes import CAMPOS_FORMULARIO
from .atendimento import link_ticket


def validar_dados(dados, finalidade, permitir_sem_ticket=False):
    erros = {}
    obrigatorios = ["alerta"]
    if dados.get("origem_atendimento", "") in ("", "Zabbix"):
        obrigatorios.append("servidor")
    if finalidade in ("WhatsApp", "Teams", "E-mail") and not permitir_sem_ticket:
        obrigatorios.append("ticket")
    for campo in obrigatorios:
        if not dados.get(campo, "").strip():
            erros[campo] = "Preencha este campo."
    ticket = dados.get("ticket", "")
    if finalidade != "Movidesk" and ticket and not re.fullmatch(r"[0-9]{1,30}", ticket):
        erros["ticket"] = "Informe somente os números do ticket (até 30 dígitos)."
    link = dados.get("link_zabbix", "")
    if link and not url_valida(link):
        erros["link_zabbix"] = "Informe um link completo, começando com https:// ou http://."
    return erros


def obter_saudacao():
    hora = datetime.now().hour
    return "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"


def gerar_assunto_email(dados, modelo="Abertura normal"):
    assunto = " - ".join(" ".join(dados.get(campo, "").split()) for campo in ("ticket", "alerta", "servidor"))
    return assunto if modelo in ("Abertura", "Abertura normal", "Abertura inicial") else f"[{modelo}] {assunto}"


def gerar_template(d, canal, url, nome_operador="", modelo="Abertura normal", atualizacao=""):
    if modelo == "Acionamento inicial" or d.get("origem_atendimento", "") not in ("", "Zabbix"):
        identificacao = " ".join(nome_operador.split())
        linhas = [f"{identificacao} - Equipe NOC" if identificacao else "Equipe NOC", modelo,
                  f"Ticket: {d.get('ticket') or 'em abertura'}", f"Resumo: {d.get('alerta', '')}"]
        for rotulo, campo in (("Serviço", "servico"), ("Ativo", "servidor"), ("Impacto relatado", "impacto"),
                              ("Situação", "situacao"), ("Prioridade", "prioridade"), ("Equipe", "time_resp")):
            if d.get(campo):
                linhas.append(f"{rotulo}: {d[campo]}")
        if atualizacao.strip():
            linhas.append("Relato: " + atualizacao.strip())
        if canal == "Teams" and d.get("ticket") and re.fullmatch(r"[0-9]{1,30}", d["ticket"]):
            linhas.append(link_ticket(url, d["ticket"]))
        return "\n".join(linhas)
    if modelo not in ("Abertura", "Abertura normal", "Abertura inicial"):
        nome = " ".join(nome_operador.split())
        identificacao = f"{nome} - Equipe NOC" if nome else "Equipe NOC"
        link = link_ticket(url, d["ticket"]) if d.get("ticket") and d["ticket"].isascii() and d["ticket"].isdigit() and len(d["ticket"]) <= 30 else ""
        introducao = {"Atualização": "Atualização do atendimento", "Acionamento": "Acionamento de equipe",
                      "Normalização": "Normalização do incidente", "Encerramento": "Encerramento do acompanhamento"}.get(modelo, modelo)
        linhas = [f"{introducao}", f"Ticket: {d['ticket']}", f"Servidor: {d['servidor']}", f"Alerta: {d['alerta']}"]
        if modelo == "Acionamento":
            linhas.append(f"Equipe acionada: {d.get('acionamento') or d.get('time_resp', '')}")
        linhas.append(f"{'Normalização' if modelo == 'Normalização' else 'Atualização'}: {atualizacao.strip()}")
        if canal == "Teams":
            linhas.extend([link, d.get("time_resp", "")])
        if canal == "WhatsApp":
            return f"{identificacao}\n{obter_saudacao()},\n\n" + "\n".join(linhas)
        if canal == "Teams":
            return "\n".join(linha for linha in linhas if linha)
        return "Prezados,\n\n" + "\n".join(linhas)
    if canal == "WhatsApp":
        nome = " ".join(nome_operador.split())
        identificacao = f"{nome} - Equipe NOC" if nome else "Equipe NOC"
        cabecalho = f"{identificacao}\n{obter_saudacao()}," if modelo in ("Abertura", "Abertura inicial") else identificacao
        return f"""{cabecalho}

• Ticket aberto no Movidesk: {d['ticket']}
• Servidor impactado: {d['servidor']}
• Severidade: {d['severidade']}
• Erro: {d['alerta']}
• Situação atual: {d['situacao']}
• Acionamento: {d['acionamento']}"""
    if canal == "Teams":
        return f"{d['ticket']}\n{d['alerta']}\n{url}/Ticket/Edit/{d['ticket']}\n{d['time_resp']}"
    return f"""Prezados,

Gostaria de informar sobre alertas detectados no sistema Zabbix. Abaixo estão os detalhes da falha:

N° do Ticket criado: {d['ticket']}
Alerta: {d['alerta']}
Severidade: {d['severidade']}
Servidor: {d['servidor']}
Dados operacionais: {d['situacao']}
Horário da Falha: {d['horario']}"""


def codificar_imagem_png(imagem):
    if imagem is None:
        return ""
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def gerar_html(dados, imagem=None):
    d = {campo: escape(dados.get(campo, ""), quote=True) for campo in CAMPOS_FORMULARIO}
    b64 = codificar_imagem_png(imagem if imagem is not None else dados.get("_imagem"))
    itens = (("Alerta", "alerta"), ("Servidor", "servidor"),
             ("Severidade", "severidade"), ("Dados Operacionais", "situacao"),
             ("Horário da Falha", "horario"))
    itens += tuple((rotulo, campo) for rotulo, campo in (("Origem", "origem_atendimento"), ("Natureza", "natureza"),
                   ("Serviço", "servico"), ("Impacto relatado", "impacto"), ("Prioridade aplicada", "prioridade"),
                   ("Relato original", "relato_original")) if d.get(campo))
    linhas = "".join(f"<li><strong>{label}:</strong> {d[campo].replace(chr(10), '<br>')}</li>" for label, campo in itens)
    link = f'<p><strong>Link do Zabbix:</strong> <a href="{d["link_zabbix"]}">{d["link_zabbix"]}</a></p>' if d["link_zabbix"] else ""
    evidencia = f'<p><img src="data:image/png;base64,{b64}" alt="Evidência" style="max-width:100%;height:auto"></p>' if b64 else ""
    return f"<p><strong>Abertura de Ticket via NOCFlow:</strong></p><ul>{linhas}</ul>{link}{evidencia}"
