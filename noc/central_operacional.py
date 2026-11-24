"""Telas operacionais isoladas do editor de captura e da integração do navegador."""

import json
import queue
import tkinter as tk
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from tkinter import filedialog, ttk

import pyperclip

from .agenda_operacional import criar_rotina, registrar_execucao, validar_agenda
from .assistente_ia import organizar_relato, responder_com_fontes
from .atendimento import etapa_incidente
from .base_conhecimento import buscar, carregar_base
from .concorrencia import disparar_assistente
from .configuracao import url_valida
from .edge_bridge import abrir_no_edge
from .exportacao_pdf import exportar_pdf
from .historico_atendimento import (
    TIPOS_EVENTO,
    agendar_acao,
    concluir_acompanhamento,
    instante,
    registrar_evento,
)
from .infra.persistencia import escrever_texto
from .recorrencia import analisar_recorrencia, formatar_recorrencia
from .regras_operacionais import aplicar_regra, carregar_perfis, prazos_atendimento
from .relatorios import diario_bordo, exportar_csv, indicadores, passagem_turno
from .ui import central_views
from .ui.formularios import dialogo, mostrar_texto, texto_area
from .ui.tarefas import TarefasUI

ORIGENS = ("Zabbix", "Grafana", "Teams", "WhatsApp", "E-mail", "Telefone", "Manual", "Dynatrace", "Jira")
NATUREZAS = ("Incidente", "Solicitação", "Encaminhamento", "Mudança", "Rotina")
PERFIL_EXEMPLO = {"versao": 1, "perfis": [{
    "id": "demonstracao", "nome": "Demonstração fictícia", "calendario": {"fuso": "UTC", "dias": list(range(7)), "feriados": []},
    "regras": [{"id": "fluxo-exemplo", "versao": "1", "estado": "rascunho", "fonte": "Procedimento fictício de demonstração",
                "responsavel": "Responsável pelo perfil", "precedencia": 0, "condicoes": {},
                "resultado": {"equipe": "Equipe de exemplo", "canais": ["Teams"], "politica_ticket": "decisao_manual",
                              "encerramento": "apos_validacao", "comunicar_sem_ticket": False,
                              "prazos": [{"acao": "Solicitar retorno", "marco": "envio", "minutos": 15}]}}],
}]}


class CentralOperacional:
    def __init__(self, app):
        self.app = app
        self.janela = tk.Toplevel(app.root)
        self.janela.title("NOCFlow · Central operacional")
        self.janela.configure(background="#f6f7f9")
        self.janela.geometry("1000x760")
        self.janela.minsize(760, 580)
        self.janela.transient(app.root)
        self.janela.protocol("WM_DELETE_WINDOW", self.fechar)
        self.fechada = False
        self.timer = None
        self.ia_ativa = False
        self.eventos = queue.Queue()
        self.documentos = []
        self.fontes_busca = []
        self.resumo = tk.StringVar(self.janela)
        self.aviso = tk.StringVar(self.janela)
        self.tarefas = TarefasUI(self.janela, self.aviso.set)
        self.cache_tela = None
        self.rodadas = 0
        topo = ttk.Frame(self.janela, padding=10)
        topo.pack(fill="x")
        ttk.Label(topo, textvariable=self.resumo, wraplength=700).pack(side="left", fill="x", expand=True)
        ttk.Button(topo, text="Editar atendimento", command=lambda: self.executar(self.editar_atendimento)).pack(side="right")
        ttk.Button(topo, text="Novo atendimento", command=lambda: self.executar(self.novo_atendimento)).pack(side="right", padx=6)
        ttk.Label(self.janela, textvariable=self.aviso, wraplength=900).pack(side="bottom", fill="x", padx=10, pady=8)
        abas = ttk.Notebook(self.janela)
        abas.pack(fill="both", expand=True, padx=10)
        self.abas = abas
        self.painel = ttk.Frame(abas, padding=8)
        self.pendencias = ttk.Frame(abas, padding=8)
        self.agenda = ttk.Frame(abas, padding=8)
        self.conhecimento = ttk.Frame(abas, padding=8)
        self.relatorios = ttk.Frame(abas, padding=8)
        for aba, nome in ((self.pendencias, "Pendências"), (self.painel, "Acompanhamento"), (self.agenda, "Agenda"),
                          (self.conhecimento, "Procedimentos e IA"), (self.relatorios, "Diário e passagem")):
            abas.add(aba, text=nome)
        central_views.montar_acompanhamento(self)
        central_views.montar_pendencias(self)
        central_views.montar_agenda(self)
        central_views.montar_conhecimento(self)
        central_views.montar_relatorios(self)
        self.atualizar()
        self.timer = self.janela.after(150, self.processar)

    def executar(self, funcao):
        if self.app.carregando or self.app.fechando or self.app.operacao:
            self.aviso.set("Aguarde a operação atual do aplicativo.")
            return
        try:
            self.app.guardar_incidente()
            funcao()
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self.aviso.set(str(exc))

    def salvar(self, mensagem="Registro salvo."):
        self.app.revisao += 1
        self.app.salvar_rascunho()
        self.cache_tela = None
        self.atualizar()
        self.aviso.set(mensagem)

    def item(self):
        return self.app.fila.obter()

    def decisao(self):
        return self.app.avaliar_perfil(self.item()["dados"])

    def dialogo(self, titulo, campos, confirmar):
        def aplicar(dados):
            if self.app.fechando or self.app.carregando or self.app.operacao:
                raise ValueError("Aguarde a operação do aplicativo.")
            self.app.guardar_incidente()
            confirmar(dados)
        return dialogo(self.janela, titulo, campos, aplicar, self.salvar)

    def localizar(self, identificador):
        item = self.app.fila.obter(identificador)
        if item is None:
            raise ValueError("O atendimento foi removido. Reabra a tela após recuperá-lo.")
        return item

    def abrir_pendencia(self):
        selecao = self.lista_pendencias.selection()
        if selecao:
            self.app.selecionar_da_lista(selecao[0])
            self.abas.select(self.painel)
            self.atualizar()

    def novo_atendimento(self):
        self.app.novo_incidente()
        self.editar_atendimento()

    def editar_atendimento(self):
        item = self.item()
        identificador = item["id"]
        original = dict(item["dados"])
        perfis = [""] + [p["id"] for p in self.app.perfis_operacionais]
        campos = [(c, r, original.get(c, "") or padrao, opcoes) for c, r, padrao, opcoes in (
            ("alerta", "Resumo *", "", None), ("origem_atendimento", "Origem", "Manual", ORIGENS),
            ("natureza", "Natureza", "Incidente", NATUREZAS), ("perfil", "Perfil", "", perfis),
            ("servico", "Serviço", "", None), ("ambiente", "Ambiente", "", None),
            ("servidor", "Ativo / servidor", "", None), ("solicitante", "Solicitante", "", None),
            ("impacto", "Impacto relatado", "", None), ("tags", "Tags (vírgulas)", "", None),
            ("ticket", "Ticket Movidesk existente", "", None), ("relato_original", "Relato original", "", "texto"),
        )]

        def confirmar(dados):
            from .atendimento import ticket_valido
            if not dados["alerta"] or any(len(v) > 30000 for v in dados.values()):
                raise ValueError("Informe um resumo e use até 30 mil caracteres por campo.")
            if dados["ticket"] and not ticket_valido(dados["ticket"]):
                raise ValueError("Ticket Movidesk deve ser numérico. Outros sistemas: use Referências.")
            atual = self.localizar(identificador)
            for c in dados:
                if atual["dados"].get(c, "") != original.get(c, "") and dados[c] != atual["dados"].get(c, ""):
                    raise ValueError("O atendimento recebeu alterações. Reabra o editor para comparar os dados.")
            antes = atual["dados"].get("ticket")
            atual["dados"].update(dados)
            if not atual["meta"].get("recebido_em"):
                registrar_evento(atual, "Recebido", "Atendimento registrado pelo operador.", self.app.config.nome_operador)
            if dados["ticket"] and dados["ticket"] != antes:
                registrar_evento(atual, "Ticket vinculado", dados["ticket"], self.app.config.nome_operador)
            registrar_evento(atual, "Nota", "Dados do atendimento revisados.", self.app.config.nome_operador)
            if self.app.fila.ativo == identificador:
                self.app.definir_dados(atual["dados"])
        self.dialogo("Dados do atendimento", campos, confirmar)

    def registrar_acao(self):
        identificador = self.item()["id"]
        tipos = tuple(t for t in TIPOS_EVENTO if t not in ("Recebido", "Mensagem copiada", "Regra aplicada", "Próxima ação",
                     "Acompanhamento concluído", "Acompanhamento reaberto", "Ticket vinculado", "Evento relacionado", "Sugestão IA aplicada"))

        def confirmar(d):
            if not d["texto"]:
                raise ValueError("Descreva a ação ou o retorno recebido.")
            if d["tipo"] in ("Envio registrado", "Tentativa de contato", "Ciência confirmada") and not (d["canal"] and d["destino"]):
                raise ValueError("Informe canal e destinatário.")
            registrar_evento(self.localizar(identificador), d["tipo"], d["texto"], self.app.config.nome_operador,
                             d["canal"], d["destino"], d["em"])
        self.dialogo("Registrar ação · envio informado manualmente", [
            ("tipo", "Tipo", "Envio registrado", tipos), ("canal", "Canal", self.app.canal.get(), ("", "Teams", "WhatsApp", "E-mail", "Telefone", "Sistema")),
            ("destino", "Destinatário / equipe", self.item()["dados"].get("time_resp", ""), None),
            ("em", "Data e hora com fuso", instante().astimezone().isoformat(timespec="seconds"), None),
            ("texto", "Registro / evidência", "", "texto")], confirmar)

    def proxima_acao(self):
        identificador = self.item()["id"]
        proxima = self.item()["meta"].get("acompanhamento", {}).get("proxima", {})
        def confirmar(d):
            agendar_acao(self.localizar(identificador), d["texto"], d["prazo"], d["responsavel"], self.app.config.nome_operador)
        self.dialogo("Próxima ação", [
            ("texto", "Ação", proxima.get("texto", ""), None),
            ("prazo", "Prazo com fuso", proxima.get("prazo", (instante() + timedelta(minutes=15)).astimezone().isoformat(timespec="seconds")), None),
            ("responsavel", "Responsável", proxima.get("responsavel", ""), None)], confirmar)

    def abrir_perfis(self):
        arquivo = filedialog.askopenfilename(parent=self.janela, title="Selecionar perfis privados", filetypes=[("JSON", "*.json")])
        if not arquivo:
            return
        def concluir(perfis):
            self.app.perfis_operacionais = perfis
            self.app.erro_perfis = ""
            self.app.fila.operacional["arquivo_perfis"] = arquivo
            self.salvar(f"{len(perfis)} perfil(is) carregado(s). Selecione o perfil em Editar atendimento.")
        self.tarefas.enviar("perfis", lambda: carregar_perfis(arquivo), concluir)

    def exemplo_perfil(self):
        arquivo = filedialog.asksaveasfilename(parent=self.janela, title="Salvar exemplo fictício", defaultextension=".json", initialfile="perfil-demonstracao.json")
        if arquivo:
            texto = json.dumps(PERFIL_EXEMPLO, ensure_ascii=False, indent=2)
            self.tarefas.enviar("exemplo_perfil", lambda: escrever_texto(Path(arquivo), texto),
                                lambda _: self.aviso.set("Exemplo salvo como rascunho; ajuste os parâmetros e o estado antes de usar."))

    def ver_regra(self):
        decisao = self.decisao()
        identificador = self.item()["id"]
        janela = tk.Toplevel(self.janela)
        janela.title("Regra e prazos — conferir antes de aplicar")
        janela.geometry("720x560")
        area = texto_area(janela)
        mostrar_texto(area, json.dumps({**decisao, "prazos_calculados": prazos_atendimento(self.item(), decisao)}, ensure_ascii=False, indent=2))

        def aplicar():
            item = self.localizar(identificador)
            atual = self.app.avaliar_perfil(item["dados"])
            if atual.get("assinatura") != decisao.get("assinatura") or atual.get("fontes") != decisao.get("fontes"):
                raise ValueError("O contexto ou a regra mudou. Avalie novamente.")
            aplicar_regra(item, atual, self.app.config.nome_operador)
            if self.app.fila.ativo == identificador:
                self.app.definir_dados(item["dados"])
            self.salvar("Regra aplicada; severidade original preservada.")
            janela.destroy()
        if decisao["estado"] == "aplicada":
            ttk.Button(janela, text="Aplicar equipe e prioridade", command=lambda: self.executar(aplicar)).pack(pady=8)
            prazos = prazos_atendimento(self.item(), decisao)
            for prazo in prazos:
                if not prazo["prazo"]:
                    continue
                def agendar(p=prazo):
                    item = self.localizar(identificador)
                    atual = self.app.avaliar_perfil(item["dados"])
                    calculados = prazos_atendimento(item, atual)
                    if atual.get("assinatura") != decisao.get("assinatura") or p not in calculados:
                        raise ValueError("A regra ou seu marco mudou; avalie novamente.")
                    agendar_acao(item, p["acao"], p["prazo"], item["dados"].get("time_resp", ""), self.app.config.nome_operador)
                    self.salvar("Próxima ação agendada a partir do marco registrado.")
                    janela.destroy()
                ttk.Button(janela, text=f"Agendar: {prazo['acao']} · {prazo['prazo']}", command=lambda f=agendar: self.executar(f)).pack(pady=2)

    def vincular_referencia(self):
        identificador = self.item()["id"]
        def confirmar(d):
            if not d["sistema"] or not d["numero"] or not url_valida(d["url"]):
                raise ValueError("Informe sistema, identificador e URL HTTP/HTTPS válida.")
            item = self.localizar(identificador)
            referencias = item["meta"].setdefault("referencias", [])
            if d not in referencias:
                referencias.append(d)
                registrar_evento(item, "Referência vinculada", f"{d['sistema']} · {d['numero']} · {d['url']}", self.app.config.nome_operador)
        self.dialogo("Vincular registro externo", [("sistema", "Sistema", "", None), ("numero", "Identificador", "", None),
                                                  ("url", "URL", "", None)], confirmar)

    def relacionar(self):
        identificador = self.item()["id"]
        opcoes = {f"{i['id'][:8]} · {i['dados'].get('alerta', '')}": i["id"] for i in self.app.fila.itens if i["id"] != identificador}
        if not opcoes:
            raise ValueError("Não há outro atendimento para relacionar.")
        def confirmar(d):
            a, b = self.localizar(identificador), self.localizar(opcoes[d["outro"]])
            if not d["motivo"]:
                raise ValueError("Informe a relação observada.")
            for origem, destino in ((a, b), (b, a)):
                relacoes = origem["meta"].setdefault("relacionados", [])
                if destino["id"] not in relacoes:
                    relacoes.append(destino["id"])
                    registrar_evento(origem, "Evento relacionado", destino["id"] + " · " + d["motivo"], self.app.config.nome_operador)
        self.dialogo("Relacionar atendimentos · eventos e tickets serão preservados", [
            ("outro", "Atendimento", next(iter(opcoes)), list(opcoes)), ("motivo", "Relação observada", "", "texto")], confirmar)

    def concluir(self):
        if self.item()["meta"].get("acompanhamento", {}).get("estado") == "Concluído":
            registrar_evento(self.item(), "Acompanhamento reaberto", "Reabertura local.", self.app.config.nome_operador)
        else:
            concluir_acompanhamento(self.item(), self.decisao(), self.app.config.nome_operador)
        self.salvar("Estado do acompanhamento atualizado; consulte o ticket para o status remoto.")

    def coordenacao(self):
        identificador = self.item()["id"]
        anterior = self.item()["meta"].get("coordenacao", {})
        def confirmar(d):
            if d["url"] and not url_valida(d["url"]):
                raise ValueError("Link da sala inválido.")
            if d["prazo"]:
                instante(d["prazo"])
            item = self.localizar(identificador)
            item["meta"]["coordenacao"] = d
            registrar_evento(item, "Coordenação de incidente", json.dumps(d, ensure_ascii=False), self.app.config.nome_operador)
            if d["acao"] and d["prazo"]:
                agendar_acao(item, d["acao"], d["prazo"], d["responsavel"], self.app.config.nome_operador)
        self.dialogo("Coordenação e pós-incidente", [(c, r, anterior.get(c, padrao), opcoes) for c, r, padrao, opcoes in (
            ("tipo", "Tipo", "Technical Bridge", ("Technical Bridge", "War Room")), ("url", "Link da sala", "", None),
            ("participantes", "Papéis / participantes", "", "texto"), ("situacao", "Situação", "Investigação", ("Investigação", "Mitigado", "Restabelecido", "Encerrado")),
            ("causa", "Causa confirmada (se houver)", "", "texto"), ("acao", "Ação pós-incidente", "", None),
            ("responsavel", "Responsável", "", None), ("prazo", "Prazo com fuso", "", None))], confirmar)

    def rotina(self):
        selecionadas = self.lista_agenda.selection()
        if not selecionadas:
            raise ValueError("Selecione uma rotina.")
        return next(r for r in self.app.fila.operacional.get("rotinas", []) if r["id"] == selecionadas[0])

    def detalhar_rotina(self):
        if self.lista_agenda.selection():
            rotina = self.rotina()
            registros = [e for e in self.app.fila.operacional.get("execucoes", []) if e["rotina"] == rotina["id"]]
            linhas = [
                f"Rotina: {rotina['titulo']} ({'Ativa' if rotina.get('ativa', True) else 'Pausada / concluída'})",
                f"Recorrência: {rotina['tipo']} · Próxima execução: {rotina['proxima']} · Responsável: {rotina.get('responsavel') or '—'}",
            ]
            if rotina.get("url"):
                linhas.append(f"URL: {rotina['url']}")
            if rotina.get("esperado"):
                linhas.append(f"Critério: {rotina['esperado']}")
            if registros:
                linhas.append("\nÚltimas execuções:")
                for reg in registros[-10:]:
                    linhas.append(f"• [{reg['em']}] {reg['resultado']} ({reg.get('autor') or 'operador'}): {reg['evidencia']}")
            else:
                linhas.append("\nNenhuma execução registrada ainda.")
            mostrar_texto(self.detalhe_rotina, "\n".join(linhas))

    def nova_rotina(self):
        def confirmar(d):
            dias = [int(v.strip()) for v in d["dias"].split(",")]
            calendario = {"fuso": d["fuso"], "dias": dias, "feriados": [v.strip() for v in d["feriados"].split(",") if v.strip()]}
            rotina = criar_rotina(d["titulo"], d["proxima"], d["tipo"], d["responsavel"], d["esperado"], d["url"], calendario,
                                  int(d["intervalo"]), [v.strip() for v in d["horarios"].split(",") if v.strip()],
                                  [v.strip() for v in d["dependencias"].split(",") if v.strip()], int(d["tolerancia"]))
            candidato = deepcopy(self.app.fila.operacional)
            candidato.setdefault("rotinas", []).append(rotina)
            validar_agenda(candidato)
            self.app.fila.operacional = candidato
        self.dialogo("Rotina ou verificação de dashboard", [
            ("titulo", "Título", "", None), ("tipo", "Recorrência", "única", ("única", "intervalo", "horários")),
            ("proxima", "Primeira execução com fuso", instante().astimezone().isoformat(timespec="seconds"), None),
            ("responsavel", "Responsável", "", None), ("esperado", "Critério e ação em caso de falha", "", "texto"),
            ("url", "Dashboard / procedimento (URL)", "", None), ("fuso", "Fuso IANA", "UTC", None),
            ("dias", "Dias: 0=seg … 6=dom", "0,1,2,3,4,5,6", None), ("feriados", "Feriados AAAA-MM-DD (vírgulas)", "", None),
            ("intervalo", "Intervalo em minutos", "60", None), ("horarios", "Horários HH:MM (vírgulas)", "09:00", None),
            ("tolerancia", "Tolerância em minutos", "0", None),
            ("dependencias", "IDs de dependências (vírgulas)", "", None)], confirmar)

    def execucao(self):
        identificador = self.rotina()["id"]
        def confirmar(d):
            registrar_execucao(self.app.fila.operacional, identificador, d["resultado"], d["evidencia"], self.app.config.nome_operador)
        self.dialogo("Registrar esta ocorrência", [("resultado", "Resultado", "OK", ("OK", "Falha", "Não executada")),
                                                   ("evidencia", "Evidência / justificativa", "", "texto")], confirmar)

    def abrir_dashboard(self):
        url = self.rotina()["url"]
        if not url_valida(url):
            raise ValueError("Esta rotina não possui URL válida.")
        abrir_no_edge(url)

    def pausar_rotina(self):
        rotina = self.rotina()
        rotina["ativa"] = not rotina.get("ativa", True)
        self.salvar("Rotina atualizada; ocorrências anteriores preservadas.")

    def abrir_base(self):
        pasta = filedialog.askdirectory(parent=self.janela, title="Base privada com indice.json e procedimentos Markdown")
        if not pasta:
            return
        def concluir(documentos):
            self.documentos = documentos
            self.fontes_busca = []
            self.app.fila.operacional["diretorio_conhecimento"] = pasta
            self.salvar(f"{len(documentos)} documento(s) validado(s) disponível(is).")
        self.tarefas.enviar("base", lambda: carregar_base(pasta), concluir)

    def exemplo_base(self):
        arquivo = filedialog.asksaveasfilename(parent=self.janela, title="Salvar índice demonstrativo", defaultextension=".json", initialfile="indice.json")
        if arquivo:
            exemplo = {"versao": 1, "documentos": [{"id": "procedimento-exemplo", "titulo": "Procedimento de demonstração",
                "versao": "1", "estado": "rascunho", "arquivo": "procedimento-exemplo.md", "perfis": ["demonstracao"], "servicos": []}]}
            texto = json.dumps(exemplo, ensure_ascii=False, indent=2)
            self.tarefas.enviar("exemplo_base", lambda: escrever_texto(Path(arquivo), texto),
                                lambda _: self.aviso.set("Índice modelo salvo. Cadastre seus arquivos privados e marque como validado somente o conteúdo vigente."))

    def buscar_base(self, ao_concluir=None):
        pasta = self.app.fila.operacional.get("diretorio_conhecimento")
        if not pasta:
            raise ValueError("Selecione a pasta da base privada. Ela deve conter indice.json versão 1 e documentos com id, titulo, versao, estado, arquivo, perfis e servicos.")
        dados, consulta = dict(self.item()["dados"]), self.consulta.get()
        identificador = self.item()["id"]
        def consultar():
            return buscar(carregar_base(pasta), consulta, dados.get("perfil", ""), dados.get("servico", ""))
        def concluir(fontes):
            atual = self.item()
            if atual["id"] != identificador or any(atual["dados"].get(c) != dados.get(c) for c in ("perfil", "servico")):
                self.aviso.set("O contexto mudou. Faça uma nova busca.")
                return
            self.fontes_busca = fontes
            mostrar_texto(self.resultado_busca, "\n\n".join(f"[{f['id']}] {f['titulo']} · {f['secao']}\n{f['texto']}" for f in fontes)
                          or "Nenhum procedimento vigente e aplicável encontrado.")
            if ao_concluir:
                ao_concluir(fontes)
        self.tarefas.enviar("busca", consultar, concluir)

    def iniciar_ia(self, funcao, ao_concluir, tarefa="consulta"):
        if self.ia_ativa:
            raise ValueError("Já existe uma solicitação de IA em andamento.")
        self.ia_ativa = True
        identificador = self.item()["id"]
        self.aviso.set("Consultando IA de texto; os dados atuais permanecem disponíveis.")
        disparar_assistente(self.eventos, identificador, tarefa, funcao, ao_concluir)

    def ia_relato(self):
        item = self.item()
        identificador, original = item["id"], dict(item["dados"])
        relato = original.get("relato_original", "")
        if not relato:
            raise ValueError("Preencha o relato original em Editar atendimento.")
        config = self.app.config
        self.iniciar_ia(lambda: organizar_relato(config, relato), lambda r: self.revisar_sugestoes(identificador, original, r), "organizar_relato")

    def revisar_sugestoes(self, identificador, original, resposta):
        janela = tk.Toplevel(self.janela)
        janela.title("Sugestões de IA · selecione os campos a aplicar")
        janela.geometry("800x650")
        escolhas = []
        for sugestao in resposta["sugestoes"]:
            marcado = tk.BooleanVar(janela, False)
            ttk.Checkbutton(janela, text=f"{sugestao['campo']}: {sugestao['valor'][:140]}", variable=marcado).pack(anchor="w", padx=10)
            escolhas.append((marcado, sugestao))
        area = texto_area(janela)
        mostrar_texto(area, json.dumps(resposta, ensure_ascii=False, indent=2))
        aviso = tk.StringVar(janela)
        ttk.Label(janela, textvariable=aviso, wraplength=750).pack(fill="x")

        def aplicar():
            try:
                if self.app.fechando or self.app.operacao:
                    raise ValueError("Aguarde a operação atual.")
                self.app.guardar_incidente()
                item = self.localizar(identificador)
                selecionadas = [s for marcado, s in escolhas if marcado.get()]
                if not selecionadas:
                    raise ValueError("Selecione ao menos um campo.")
                if item["dados"].get("relato_original") != resposta["relato_original"]:
                    raise ValueError("O relato mudou; gere novas sugestões.")
                for s in selecionadas:
                    if item["dados"].get(s["campo"], "") != original.get(s["campo"], ""):
                        raise ValueError("Um campo foi alterado desde a consulta; revise novamente.")
                for s in selecionadas:
                    item["dados"][s["campo"]] = s["valor"]
                    revisados = item["meta"].setdefault("campos_revisados", [])
                    if s["campo"] in ("alerta", "servidor", "horario", "situacao") and s["campo"] not in revisados:
                        revisados.append(s["campo"])
                item["meta"]["ultima_ia_relato"] = resposta
                item["meta"].setdefault("assistente_metricas", []).append({"em": instante().isoformat(), "tarefa": "aplicar_sugestoes",
                    "sugeridos": len(resposta["sugestoes"]), "aplicados": len(selecionadas)})
                registrar_evento(item, "Sugestão IA aplicada", json.dumps(selecionadas, ensure_ascii=False), self.app.config.nome_operador)
                if self.app.fila.ativo == identificador:
                    self.app.definir_dados(item["dados"])
                self.salvar("Campos selecionados aplicados com trechos de origem preservados.")
                janela.destroy()
            except ValueError as exc:
                aviso.set(str(exc))
        ttk.Button(janela, text="Aplicar campos selecionados", command=aplicar).pack(pady=8)

    def ia_procedimentos(self, revisar=False):
        pergunta = "Identifique lacunas, ambiguidades e conflitos nos procedimentos fornecidos, sem inventar regras." if revisar else self.consulta.get()
        config = self.app.config
        def consultar(fontes):
            self.iniciar_ia(lambda: responder_com_fontes(config, pergunta, fontes), self.mostrar_resposta_ia,
                           "revisar_procedimentos" if revisar else "consultar_procedimentos")
        self.buscar_base(consultar)

    def mostrar_resposta_ia(self, resposta):
        janela = tk.Toplevel(self.janela)
        janela.title("Resposta de IA com fontes · revisão do operador")
        janela.geometry("780x580")
        area = texto_area(janela)
        texto = "\n\n".join(f"{a['texto']}\nFonte: {a['fonte']}\nTrecho: {a['trecho']}" for a in resposta["afirmacoes"])
        texto += "\n\nPendências:\n" + "\n".join(resposta["pendencias"])
        mostrar_texto(area, texto)
        ttk.Button(janela, text="Copiar rascunho", command=lambda: self.executar(lambda: pyperclip.copy(texto))).pack(pady=8)

    def gerar_diario(self):
        mostrar_texto(self.relatorio, diario_bordo(self.app.fila.itens, self.inicio.get(), self.fim.get()))

    def gerar_recorrencia(self):
        relatorio = analisar_recorrencia(self.app.fila.itens,
            self.inicio.get() if self.recorrencia_periodo.get() else None,
            self.fim.get() if self.recorrencia_periodo.get() else None,
            incluir_arquivados=self.recorrencia_arquivados.get(), por_ativo=self.recorrencia_ativo.get())
        mostrar_texto(self.relatorio, formatar_recorrencia(relatorio))

    def exportar_relatorio_pdf(self):
        texto = self.relatorio.get("1.0", "end-1c").strip()
        if not texto:
            raise ValueError("Gere um relatório antes de exportar.")
        destino = filedialog.asksaveasfilename(parent=self.janela, title="Exportar relatório em PDF",
            defaultextension=".pdf", initialfile="relatorio-noc.pdf", filetypes=[("PDF", "*.pdf")])
        if destino:
            self.tarefas.enviar("pdf", lambda: exportar_pdf(destino, texto),
                                lambda _: self.aviso.set("PDF exportado com o relatório exibido."))

    def gerar_passagem(self):
        mostrar_texto(self.relatorio, passagem_turno(self.app.fila.itens, self.app.fila.operacional))

    def gerar_indicadores(self):
        mostrar_texto(self.relatorio, json.dumps(indicadores(self.app.fila.itens, self.app.fila.operacional, self.inicio.get(), self.fim.get()), ensure_ascii=False, indent=2))

    def exportar(self):
        itens = self.app.fila.snapshot()["itens"]
        inicio, fim = self.inicio.get(), self.fim.get()
        destino = filedialog.asksaveasfilename(parent=self.janela, defaultextension=".csv", initialfile="diario-noc.csv")
        if destino:
            self.tarefas.enviar("csv", lambda: escrever_texto(Path(destino), exportar_csv(itens, inicio, fim), "utf-8-sig"),
                                lambda _: self.aviso.set("CSV exportado com os registros do período selecionado."))

    def ia_resumo(self):
        texto = self.relatorio.get("1.0", "end-1c").strip()
        if not texto:
            raise ValueError("Gere um relatório primeiro, como a recorrência de tickets.")
        fontes = [{"id": "relatorio-local", "texto": texto}]
        config = self.app.config
        self.iniciar_ia(lambda: responder_com_fontes(config, "Resuma ações, pendências e próximos passos. Preserve os valores já calculados e cite as fontes.", fontes), self.mostrar_resposta_ia, "resumir_registros")

    def receber_turno(self):
        def confirmar(d):
            if not d["responsavel"]:
                raise ValueError("Informe quem recebe o turno.")
            self.app.fila.operacional.setdefault("passagens", []).append({"em": instante().isoformat(), "responsavel": d["responsavel"],
                "observacao": d["observacao"], "resumo": passagem_turno(self.app.fila.itens, self.app.fila.operacional)})
        self.dialogo("Registrar recebimento da passagem", [("responsavel", "Responsável entrante", "", None),
                                                           ("observacao", "Observações", "", "texto")], confirmar)

    def atualizar(self):
        item = self.item()
        self.resumo.set(f"{item['dados'].get('alerta') or 'Novo atendimento'} · {etapa_incidente(item)}")
        chave = (item["id"], self.app.revisao)
        if self.cache_tela != chave:
            self.cache_tela = chave
            linhas = [f"Perfil: {item['dados'].get('perfil') or 'não selecionado'}", f"Serviço: {item['dados'].get('servico') or 'não informado'}"]
            if self.app.erro_perfis:
                linhas.append(self.app.erro_perfis)
            proxima = item["meta"].get("acompanhamento", {}).get("proxima")
            if proxima:
                linhas.append(f"Próxima ação: {proxima['texto']} · {proxima['prazo']} · {proxima['responsavel']}")
            for e in reversed(item["meta"].get("historico", [])):
                linhas.extend(["", f"[{e['em']}] {e['tipo']} · {e['autor']} · {e['canal']} · {e['destinatario']}", e["texto"], f"Registro: {e['id']}"])
            mostrar_texto(self.historico, "\n".join(linhas))
        existentes = set(self.lista_agenda.get_children())
        for rotina in self.app.fila.operacional.get("rotinas", []):
            estado = "Pausada / concluída" if not rotina.get("ativa", True) else "Vencida" if instante(rotina["proxima"]) <= instante() else "Prevista"
            valores = (rotina["titulo"], rotina["proxima"], estado, rotina["responsavel"])
            tags = ("pausada",) if estado == "Pausada / concluída" else ("vencida",) if estado == "Vencida" else ()
            if rotina["id"] in existentes:
                if self.lista_agenda.item(rotina["id"], "values") != valores or tuple(self.lista_agenda.item(rotina["id"], "tags")) != tags:
                    self.lista_agenda.item(rotina["id"], values=valores, tags=tags)
                existentes.remove(rotina["id"])
            else:
                self.lista_agenda.insert("", "end", iid=rotina["id"], values=valores, tags=tags)
        for identificador in existentes:
            self.lista_agenda.delete(identificador)
        ids = set(self.lista_pendencias.get_children())
        ativos = [i for i in self.app.fila.itens if not i["meta"].get("arquivado") and any(i["dados"].values())
                  and i["meta"].get("acompanhamento", {}).get("estado") != "Concluído"]
        ativos.sort(key=lambda i: i["meta"].get("acompanhamento", {}).get("proxima", {}).get("prazo", "9999"))
        for n, atendimento in enumerate(ativos):
            proxima = atendimento["meta"].get("acompanhamento", {}).get("proxima", {})
            vencida = bool(proxima and instante(proxima["prazo"]) <= instante())
            valores = (atendimento["dados"].get("alerta", ""), etapa_incidente(atendimento),
                       proxima.get("texto", "Definir próxima ação"), ("VENCIDA · " if vencida else "") + proxima.get("prazo", ""))
            tags = ("vencida",) if vencida else ()
            identificador = atendimento["id"]
            if identificador in ids:
                if self.lista_pendencias.item(identificador, "values") != valores or tuple(self.lista_pendencias.item(identificador, "tags")) != tags:
                    self.lista_pendencias.item(identificador, values=valores, tags=tags)
                ids.remove(identificador)
            else:
                self.lista_pendencias.insert("", "end", iid=identificador, values=valores, tags=tags)
            self.lista_pendencias.move(identificador, "", n)
        for identificador in ids:
            self.lista_pendencias.delete(identificador)

    def processar(self):
        self.timer = None
        if self.fechada or self.app.fechando:
            self.fechar()
            return
        try:
            while True:
                callback, resultado, erro, identificador, tarefa = self.eventos.get_nowait()
                self.ia_ativa = False
                if erro:
                    self.aviso.set(erro)
                else:
                    metricas = resultado["metricas"]
                    item = self.app.fila.obter(identificador)
                    if item:
                        item["meta"].setdefault("assistente_metricas", []).append({"em": instante().isoformat(), "tarefa": tarefa, **metricas})
                        self.app.revisao += 1
                        self.app.salvar_rascunho()
                    self.app.consumo_ia.registrar({"provedor": "Groq", "horario": instante().astimezone().strftime("%H:%M:%S"),
                        "entrada": metricas.get("entrada"), "saida": metricas.get("saida"), "total": metricas.get("tokens"), "cotas": {}})
                    self.app.resumo_tokens.set(self.app.consumo_ia.resumo(self.app.config))
                    self.aviso.set(f"Resposta recebida em {resultado['metricas']['segundos']:.1f}s. Revise as fontes.")
                    callback(resultado)
        except queue.Empty:
            pass
        self.rodadas += 1
        if self.rodadas % 10 == 0:
            self.atualizar()
        self.timer = self.janela.after(150, self.processar)

    def fechar(self):
        if self.fechada:
            return
        if self.tarefas.callbacks:
            self.aviso.set("Aguarde a conclusão das tarefas locais antes de fechar.")
            self.janela.after(100, self.fechar)
            return
        self.fechada = True
        self.tarefas.fechar()
        if self.timer:
            self.janela.after_cancel(self.timer)
            self.timer = None
        self.janela.destroy()
