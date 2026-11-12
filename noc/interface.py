"""Interface Tkinter e coordenação dos eventos dos workers."""

import logging
from dataclasses import replace
from copy import deepcopy
from logging.handlers import RotatingFileHandler
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageGrab, ImageTk
import pyperclip

from .edge_bridge import abrir_no_edge, preparar_extensao
from .tokens_ia import ConsumoIA
from .recortes_email import CAMPOS_RECORTE, EditorRecortes, VisualizadorImagem, montar_recortes
from .painel_fila import PainelFila
from .atendimento import (MODELOS, MODELOS_ABERTURA, ROTULOS_CAMPOS, STATUS_PREENCHIMENTO, agora, etapa_incidente,
                          link_ticket, pendencias_incidente, proxima_acao, ticket_valido)
from .incidentes import FilaIncidentes, importar_eventos, CAMPOS_EVENTO, CAMPOS_FORMULARIO as CAMPOS
from .extracao_local import CacheExtracao
from .configuracao import carregar_config, diretorio_aplicacao, preparar_config_apis
from .configuracao import salvar_nome_operador as gravar_nome_operador
from .comunicados import gerar_assunto_email, gerar_template, validar_dados
from .clipboard_windows import copiar_imagem
from .extracao import extrair_dados
from .movidesk import MovideskWorker
from .rascunhos import RascunhoWorker
from .historico_atendimento import instante, pendente_operacional, registrar_evento
from .regras_operacionais import avaliar_regras, carregar_perfis


class NOCFlow:
    def __init__(self, root, config=None):
        self.root = root
        self.config = config or carregar_config(diretorio_aplicacao())
        self.eventos = queue.Queue()
        self.imagem = None
        self.imagem_extracao = None
        self.recortes_email = {}
        self.miniatura = None
        self.miniatura_chave = None
        self.imagem_after = None
        self.operacao = None
        self.sequencia = 0
        self.revisao = 0
        self.carregando = True
        self.fechando = False
        self.atualizando = False
        self.save_after = None
        self.poll_after = None
        self.ultimo_erro = ""
        self.anterior = None
        self.removidos = []
        self.vinculos_retorno = {}
        self.recebidos = []
        self.ids_seletor = []
        self.nome_em_edicao = not bool(self.config.nome_operador)
        self.estado_conexao = "desconectado"
        self.perfis_operacionais = []
        self.erro_perfis = ""
        self.central = None
        self.ultima_agenda = 0
        self.fila = FilaIncidentes()
        self.cache_extracao = CacheExtracao()
        self.importacoes_pendentes = []
        self.avisos_extracao = []
        self.metricas_extracao = {}
        self.tokens_extracao = 0
        self.inicio_operacao = 0
        self.vars = {campo: tk.StringVar(root) for campo in CAMPOS}
        self.erros = {campo: tk.StringVar(root) for campo in CAMPOS}
        self.entradas = {}
        self.status = tk.StringVar(root, "Recuperando rascunho…")
        self.status_rascunho = tk.StringVar(root, "")
        self.tempo = tk.StringVar(root, "")
        self.assunto_email = tk.StringVar(root, "")
        self.canal = tk.StringVar(root, "WhatsApp")
        self.nome_operador = tk.StringVar(root, self.config.nome_operador)
        self.nome_resumo = tk.StringVar(root)
        self.modelo_comunicado = tk.StringVar(root, "Abertura normal")
        self.texto_atualizacao = tk.StringVar(root)
        self.copias_resumo = tk.StringVar(root)
        self.evidencia_escolha = tk.StringVar(root, "Print completo")
        self.evidencia_resumo = tk.StringVar(root, "Sem print")
        self.proxima_acao = tk.StringVar(root)
        self.conexao_resumo = tk.StringVar(root, "Zabbix: desconectado")
        self.consumo_ia = ConsumoIA()
        self.resumo_tokens = tk.StringVar(root, self.consumo_ia.resumo(self.config))

        self.root.title("NOCFlow")
        altura = min(720, self.root.winfo_screenheight() - 90)
        self.root.geometry(f"900x{max(520, altura)}")
        self.root.minsize(600, 520)
        self.root.protocol("WM_DELETE_WINDOW", self.fechar)
        self.montar_interface()
        for campo, variavel in self.vars.items():
            variavel.trace_add("write", lambda *_, c=campo: self.alterado(c))
        self.nome_operador.trace_add("write", lambda *_: self.atualizar_previews())
        self.texto_atualizacao.trace_add("write", self.comunicacao_alterada)
        self.root.bind("<Control-n>", lambda _: self.novo_incidente())
        self.root.bind("<Control-Shift-V>", lambda _: self.ler_print())
        self.root.bind("<Control-i>", lambda _: self.importar_clipboard())
        self.root.bind("<MouseWheel>", self.rolar)

        self.movidesk = MovideskWorker(self.config, self.eventos)
        self.rascunho = RascunhoWorker(self.config, self.eventos)
        self.movidesk.start()
        self.rascunho.start()
        self.atualizar_controles()
        self.atualizar_menu()
        self.poll_after = self.root.after(100, self.processar_eventos)

    # ---------- interface ----------

    def montar_interface(self):
        estilo = ttk.Style(self.root)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        self.root.configure(background="#f6f7f9")
        estilo.configure(".", font=("Segoe UI", 10), background="#f6f7f9", foreground="#182230")
        estilo.configure("TButton", padding=(10, 6))
        estilo.configure("Compacto.TButton", padding=(6, 2))
        estilo.configure("TEntry", padding=4, fieldbackground="white")
        estilo.configure("TCombobox", padding=4, fieldbackground="white")
        estilo.configure("TNotebook.Tab", padding=(16, 7))
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 16, "bold"))
        estilo.configure("Discreto.TLabel", foreground="#667085", font=("Segoe UI", 9))
        estilo.configure("Erro.TLabel", foreground="#b42318", font=("Segoe UI", 9))
        estilo.configure("Principal.TButton", background="#215dcc", foreground="white", borderwidth=0)
        estilo.map("Principal.TButton", background=[("disabled", "#dfe5ed"), ("active", "#194ba8")],
                   foreground=[("disabled", "#667085")])

        topo = ttk.Frame(self.root, padding=(16, 10))
        topo.pack(fill="x")
        ttk.Label(topo, text="NOCFlow", style="Titulo.TLabel").pack(side="left")
        self.seletor_fila = ttk.Combobox(topo, state="readonly", width=34)
        self.seletor_fila.pack(side="left", fill="x", expand=True, padx=(16, 8))
        self.seletor_fila.bind("<<ComboboxSelected>>", self.selecionar_incidente)
        self.btn_fila = ttk.Button(topo, text="Fila", width=6, command=self.alternar_fila)
        self.btn_fila.pack(side="left", padx=(0, 6))
        self.btn_novo = ttk.Button(topo, text="+ Novo", width=8, command=self.novo_incidente)
        self.btn_novo.pack(side="left", padx=(0, 6))
        self.btn_mais = ttk.Menubutton(topo, text="⋯", width=4)
        self.btn_mais.pack(side="left")
        self.menu_mais = tk.Menu(self.btn_mais, tearoff=False)
        self.btn_mais.configure(menu=self.menu_mais)
        self.acoes_menu = {}
        itens = (
            ("conectar", "Conectar Zabbix", self.conectar_zabbix),
            None,
            ("capturar", "Guardar print sem extrair", self.capturar_print),
            ("reler", "Reler print guardado", lambda: self.extrair_com_ia(False)),
            ("ia", "Completar com IA", self.extrair_com_ia),
            ("copiar_print", "Copiar print", self.copiar_print),
            None,
            ("extensao", "Instalar extensão do Edge", self.configurar_extensao),
            ("config", "Configurações", self.configurar_apis),
            ("consumo", "Consumo e detalhes", self.mostrar_tokens),
            None,
            ("desfazer", "Desfazer novo incidente", self.desfazer_novo),
            ("arquivar", "Arquivar / reabrir atendimento", self.arquivar_incidente),
            ("remover", "Remover incidente da fila", self.remover_incidente),
            ("restaurar", "Desfazer remoção", self.desfazer_remocao),
            ("atendimento", "Detalhes e atualizações do atendimento", self.detalhes_atendimento),
        )
        for item in itens:
            if item is None:
                self.menu_mais.add_separator()
            else:
                chave, rotulo, comando = item
                self.menu_mais.add_command(label=rotulo, command=comando)
                self.acoes_menu[chave] = self.menu_mais.index("end")

        conexao = ttk.Frame(self.root, padding=(16, 0, 16, 6))
        conexao.pack(fill="x")
        ttk.Label(conexao, textvariable=self.conexao_resumo, style="Discreto.TLabel").pack(side="left")
        self.btn_conectar = ttk.Button(conexao, text="Conectar", style="Compacto.TButton", command=self.conectar_zabbix)
        self.btn_conectar.pack(side="left", padx=(8, 0))
        self.btn_operacao = ttk.Button(conexao, text="Central operacional", style="Compacto.TButton", command=self.abrir_central)
        self.btn_operacao.pack(side="right")
        self.btn_recebidos = ttk.Button(conexao, style="Compacto.TButton", command=self.ver_recebidos)
        self.painel_fila = PainelFila(self.root, self.selecionar_da_lista, self.proximo_pendente, self.arquivar_incidente)

        rodape = ttk.Frame(self.root, padding=(16, 6))
        rodape.pack(side="bottom", fill="x")
        self.status_label = ttk.Label(rodape, textvariable=self.status, wraplength=640, style="Discreto.TLabel")
        self.status_label.pack(fill="x", anchor="w")
        self.progresso = ttk.Progressbar(rodape, mode="indeterminate")
        linha_status = ttk.Frame(rodape)
        linha_status.pack(fill="x")
        ttk.Label(linha_status, textvariable=self.status_rascunho, style="Discreto.TLabel").pack(side="left")
        ttk.Label(linha_status, textvariable=self.tempo, style="Discreto.TLabel").pack(side="right")
        self.btn_detalhes = ttk.Button(rodape, text="Detalhes", command=self.detalhes_erro)
        rodape.bind("<Configure>", lambda e: self.status_label.configure(wraplength=max(200, e.width - 32)))

        acoes = ttk.Frame(self.root, padding=(16, 8))
        acoes.pack(side="bottom", fill="x")
        orientacao = ttk.Frame(acoes)
        orientacao.pack(fill="x", pady=(0, 5))
        self.etapa_label = ttk.Label(orientacao, textvariable=self.proxima_acao, wraplength=650, style="Discreto.TLabel")
        self.etapa_label.pack(side="left", fill="x", expand=True)
        self.btn_atendimento = ttk.Button(orientacao, text="Detalhes", style="Compacto.TButton", command=self.detalhes_atendimento)
        self.btn_atendimento.pack(side="right", padx=(8, 0))
        acoes.bind("<Configure>", lambda e: self.etapa_label.configure(wraplength=max(250, e.width - 150)))
        linha_acoes = ttk.Frame(acoes)
        linha_acoes.pack(fill="x")
        ticket_area = ttk.Frame(linha_acoes)
        ticket_area.pack(side="left", fill="x", expand=True)
        ttk.Label(ticket_area, text="Ticket", style="Discreto.TLabel").pack(side="left", padx=(0, 6))
        ticket_linha = ttk.Frame(ticket_area)
        ticket_linha.pack(side="left", fill="x", expand=True)
        self.entradas["ticket"] = ttk.Entry(ticket_linha, textvariable=self.vars["ticket"], width=18)
        self.entradas["ticket"].pack(side="left")
        self.entradas["ticket"].bind("<FocusIn>", lambda _: self.mostrar_campo(self.entradas["ticket"]))
        self.erro_ticket = ttk.Label(ticket_linha, textvariable=self.erros["ticket"], style="Erro.TLabel")
        self.erro_ticket.pack(side="left", padx=(8, 0))
        self.btn_movidesk = ttk.Button(linha_acoes, text="Criar ticket", style="Principal.TButton",
                                        command=self.preencher_movidesk)
        self.btn_comunicado = ttk.Button(linha_acoes, text="Copiar mensagem", style="Principal.TButton",
                                          command=lambda: self.copiar_comunicado(self.canal.get()))
        self.btn_proximo = ttk.Button(linha_acoes, text="Próximo", command=self.proximo_pendente)
        self.btn_proximo.pack(side="right", padx=(6, 0))

        self.paginas = ttk.Notebook(self.root)
        self.paginas.pack(fill="both", expand=True, padx=16)
        self.pagina_incidente = ttk.Frame(self.paginas)
        self.pagina_comunicar = ttk.Frame(self.paginas, padding=(12, 8))
        self.pagina_evidencias = ttk.Frame(self.paginas, padding=(12, 12))
        self.paginas.add(self.pagina_incidente, text="Incidente")
        self.paginas.add(self.pagina_comunicar, text="Comunicar")
        self.paginas.add(self.pagina_evidencias, text="Evidências")
        self.paginas.bind("<<NotebookTabChanged>>", self.mudar_pagina)

        area = ttk.Frame(self.pagina_incidente)
        area.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(area, highlightthickness=0, background="#f6f7f9")
        barra = ttk.Scrollbar(area, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.conteudo = ttk.Frame(self.canvas, padding=(12, 12))
        janela = self.canvas.create_window((0, 0), window=self.conteudo, anchor="nw")
        self.conteudo.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(janela, width=e.width))

        entrada = ttk.Frame(self.conteudo)
        entrada.pack(fill="x", pady=(0, 12))
        self.btn_importar = ttk.Button(entrada, text="Importar dados", command=self.importar_clipboard)
        self.btn_importar.pack(side="left", padx=(0, 8))
        self.btn_ler_print = ttk.Button(entrada, text="Ler print", command=self.ler_print)
        self.btn_ler_print.pack(side="left")
        if self.config.ia_automatica:
            self.btn_ler_print.configure(text="Ler print + IA")
        ttk.Label(entrada, text="Do Zabbix (Ctrl+I) ou print (Win+Shift+S).",
                  style="Discreto.TLabel").pack(side="left", padx=(12, 0))

        campos = ttk.Frame(self.conteudo)
        campos.pack(fill="x")
        campos.columnconfigure((0, 1), weight=1, uniform="campos")
        for rotulo, campo, linha, coluna, largura in (
            ("Alerta / resumo *", "alerta", 0, 0, 2),
            ("Servidor (alertas Zabbix)", "servidor", 1, 0, 1),
            ("Severidade", "severidade", 1, 1, 1),
            ("Dados operacionais", "situacao", 2, 0, 2),
            ("Horário", "horario", 3, 0, 1),
            ("Link Zabbix", "link_zabbix", 3, 1, 1),
        ):
            self.criar_campo(campos, rotulo, campo, linha=linha, coluna=coluna, colunas=largura)

        evidencia = ttk.Frame(self.conteudo, padding=(4, 6))
        evidencia.pack(fill="x")
        ttk.Label(evidencia, textvariable=self.evidencia_resumo, style="Discreto.TLabel").pack(side="left")
        ttk.Button(evidencia, text="Ver evidências", command=self.mostrar_evidencias).pack(side="right")

        escolhas = ttk.Frame(self.pagina_comunicar)
        escolhas.pack(fill="x", pady=(0, 6))
        escolhas.columnconfigure((1, 3), weight=1)
        ttk.Label(escolhas, text="Canal", style="Discreto.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Label(escolhas, text="Modelo", style="Discreto.TLabel").grid(row=0, column=2, sticky="w", padx=(12, 6))
        self.seletor_canal = ttk.Combobox(escolhas, textvariable=self.canal,
                                          values=("WhatsApp", "Teams", "E-mail"), state="readonly", width=14)
        self.seletor_canal.grid(row=0, column=1, sticky="ew")
        self.seletor_canal.bind("<<ComboboxSelected>>", self.mudar_canal)
        self.seletor_modelo = ttk.Combobox(escolhas, textvariable=self.modelo_comunicado, values=MODELOS, state="readonly", width=14)
        self.seletor_modelo.grid(row=0, column=3, sticky="ew")
        self.seletor_modelo.bind("<<ComboboxSelected>>", self.mudar_modelo)
        self.opcoes_canal = ttk.Frame(self.pagina_comunicar)
        self.opcoes_canal.pack(fill="x")
        self.campos_canal = {}
        for canal, campo, rotulo in (("WhatsApp", "acionamento", "Acionamento"),
                                     ("Teams", "time_resp", "Time responsável")):
            frame = ttk.Frame(self.opcoes_canal)
            if canal == "WhatsApp":
                nome_area = ttk.Frame(frame)
                nome_area.pack(fill="x", pady=(0, 4))
                self.nome_compacto = ttk.Frame(nome_area)
                ttk.Label(self.nome_compacto, textvariable=self.nome_resumo, style="Discreto.TLabel").pack(side="left")
                ttk.Button(self.nome_compacto, text="Editar nome", style="Compacto.TButton", command=self.editar_nome_operador).pack(side="right")
                self.linha_nome = ttk.Frame(nome_area)
                ttk.Label(self.linha_nome, text="Seu nome:", style="Discreto.TLabel").pack(side="left", padx=(0, 6))
                self.entrada_nome_operador = ttk.Entry(self.linha_nome, textvariable=self.nome_operador)
                self.entrada_nome_operador.pack(side="left", fill="x", expand=True)
                self.entrada_nome_operador.bind("<Return>", lambda _: self.salvar_nome_operador())
                self.btn_salvar_nome = ttk.Button(self.linha_nome, text="Salvar nome", style="Compacto.TButton", command=self.salvar_nome_operador)
                self.btn_salvar_nome.pack(side="right", padx=(8, 0))
            linha = ttk.Frame(frame)
            linha.pack(fill="x", pady=(0, 6))
            ttk.Label(linha, text=rotulo, style="Discreto.TLabel").pack(side="left", padx=(0, 6))
            self.entradas[campo] = ttk.Entry(linha, textvariable=self.vars[campo])
            self.entradas[campo].pack(side="left", fill="x", expand=True)
            self.campos_canal[canal] = frame
        email = ttk.Frame(self.opcoes_canal)
        self.campos_canal["E-mail"] = email
        email_linha = ttk.Frame(email)
        email_linha.pack(fill="x", pady=(0, 8))
        ttk.Entry(email_linha, textvariable=self.assunto_email, state="readonly").pack(
            side="left", fill="x", expand=True)
        self.btn_assunto = ttk.Button(email_linha, text="Assunto", style="Compacto.TButton", command=self.copiar_assunto_email)
        self.btn_assunto.pack(side="right", padx=(8, 0))
        self.atualizacao_area = ttk.Frame(self.pagina_comunicar)
        relato = ttk.Frame(self.atualizacao_area)
        relato.pack(fill="x", pady=(0, 4))
        ttk.Label(relato, text="Relato", style="Discreto.TLabel").pack(side="left", padx=(0, 6))
        self.entrada_atualizacao = ttk.Entry(relato, textvariable=self.texto_atualizacao)
        self.entrada_atualizacao.pack(side="left", fill="x", expand=True)
        self.acionamento_email = ttk.Frame(self.atualizacao_area)
        ttk.Label(self.acionamento_email, text="Equipe acionada:", style="Discreto.TLabel").pack(side="left")
        self.entrada_acionamento_email = ttk.Entry(self.acionamento_email, textvariable=self.vars["acionamento"])
        self.entrada_acionamento_email.pack(side="left", fill="x", expand=True, padx=(6, 0))

        fim_comunicacao = ttk.Frame(self.pagina_comunicar)
        fim_comunicacao.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Button(fim_comunicacao, text="Ampliar prévia", style="Compacto.TButton", command=self.ampliar_previa).pack(side="right", padx=(8, 0))
        copia_label = ttk.Label(fim_comunicacao, textvariable=self.copias_resumo, style="Discreto.TLabel", wraplength=390)
        copia_label.pack(side="left", fill="x", expand=True)
        fim_comunicacao.bind("<Configure>", lambda e: copia_label.configure(wraplength=max(150, e.width - 130)))
        self.area_previa = ttk.Frame(self.pagina_comunicar)
        self.area_previa.pack(fill="both", expand=True)
        self.previa = tk.Text(self.area_previa, height=5, width=1, wrap="word",
                              font=("Segoe UI", 10), relief="flat", padx=10, pady=8,
                              background="white", foreground="#182230", state="disabled")
        barra_previa = ttk.Scrollbar(self.area_previa, orient="vertical", command=self.previa.yview)
        barra_previa.pack(side="right", fill="y")
        self.previa.configure(yscrollcommand=barra_previa.set)
        self.previa.pack(fill="both", expand=True)

        self.area_recortes = ttk.Frame(self.pagina_evidencias)
        self.area_recortes.pack(fill="x", pady=(0, 6))
        self.btn_adicionar_print = ttk.Button(self.area_recortes, text="Adicionar print", command=self.capturar_print)
        self.btn_adicionar_print.pack(side="left", padx=(0, 6))
        self.btn_ampliar = ttk.Button(self.area_recortes, text="Ampliar", command=self.ampliar_imagem)
        self.btn_ampliar.pack(side="left", padx=(0, 6))
        self.btn_recortar_email = ttk.Button(self.area_recortes, text="Recortar print",
                                             command=self.recortar_imagem_email)
        self.btn_recortar_email.pack(side="left")
        copia_imagem = ttk.Frame(self.pagina_evidencias)
        copia_imagem.pack(fill="x", pady=(0, 6))
        self.btn_print = ttk.Button(copia_imagem, text="Copiar print", command=self.copiar_print)
        self.btn_print.pack(side="left", padx=(0, 6))
        self.btn_imagem_email = ttk.Button(copia_imagem, text="Copiar recorte",
                                           command=self.copiar_imagem_email)
        self.btn_imagem_email.pack(side="left")
        ttk.Label(self.pagina_evidencias, text="Capture com Win+Shift+S e use Adicionar print. Clique na prévia para ampliar.",
                  style="Discreto.TLabel", wraplength=540).pack(anchor="w")
        resumo_imagem = ttk.Label(self.pagina_evidencias, textvariable=self.evidencia_resumo, style="Discreto.TLabel")
        resumo_imagem.pack(side="bottom", anchor="w", pady=(4, 0))
        destino_imagem = ttk.Frame(self.pagina_evidencias)
        destino_imagem.pack(side="bottom", fill="x")
        ttk.Label(destino_imagem, text="Imagem no ticket:", style="Discreto.TLabel").pack(side="left")
        self.seletor_evidencia = ttk.Combobox(destino_imagem, textvariable=self.evidencia_escolha,
                                             values=("Print completo", "Recorte"), state="readonly", width=18)
        self.seletor_evidencia.pack(side="left", padx=8)
        self.seletor_evidencia.bind("<<ComboboxSelected>>", self.escolher_evidencia)
        self.preview_imagem = ttk.Label(self.pagina_evidencias, style="Discreto.TLabel", anchor="center")
        self.preview_imagem.pack(fill="both", expand=True, pady=6)
        self.preview_imagem.bind("<Button-1>", lambda _: self.ampliar_imagem())
        self.preview_imagem.bind("<Configure>", self.agendar_miniatura)
        self.btns_copiar = (self.btn_comunicado, self.btn_assunto)
        self.atualizar_nome_operador()
        self.mudar_canal()
        self.mudar_pagina()
        self.atualizar_previews()
        self.atualizar_fila()

    def criar_campo(self, pai, rotulo, campo, linha=None, coluna=None, colunas=1):
        frame = ttk.Frame(pai)
        if linha is None:
            frame.pack(fill="x", pady=(0, 8))
        else:
            frame.grid(row=linha, column=coluna, columnspan=colunas, sticky="ew", padx=4, pady=(0, 8))
        ttk.Label(frame, text=rotulo, style="Discreto.TLabel").pack(anchor="w")
        if campo == "situacao":
            entrada = tk.Text(frame, height=3, wrap="word", font=("Segoe UI", 10), width=1, undo=True,
                              relief="flat", padx=8, pady=8, background="white")
            entrada.bind("<<Modified>>", self.situacao_alterada)
        elif campo == "severidade":
            entrada = ttk.Combobox(frame, textvariable=self.vars[campo], values=(
                "Não classificado", "Informação", "Aviso", "Média", "Alta", "Desastre"))
        else:
            entrada = ttk.Entry(frame, textvariable=self.vars[campo])
        entrada.pack(fill="x", pady=(2, 0))
        entrada.bind("<FocusIn>", lambda _: self.mostrar_campo(entrada))
        self.entradas[campo] = entrada
        aviso = ttk.Label(frame, textvariable=self.erros[campo], style="Erro.TLabel")

        def mostrar_erro(*_):
            if self.erros[campo].get():
                aviso.pack(anchor="w")
            else:
                aviso.pack_forget()

        self.erros[campo].trace_add("write", mostrar_erro)

    def mudar_pagina(self, _=None):
        try:
            comunicar = self.paginas.select() == str(self.pagina_comunicar)
        except tk.TclError:
            comunicar = False
        self.btn_movidesk.pack_forget()
        self.btn_comunicado.pack_forget()
        (self.btn_comunicado if comunicar else self.btn_movidesk).pack(side="right", padx=(12, 0))
        self.agendar_miniatura()

    def mudar_canal(self, _=None):
        for frame in self.campos_canal.values():
            frame.pack_forget()
        self.campos_canal[self.canal.get()].pack(fill="x")
        self.btn_comunicado.configure(
            text="Copiar e-mail" if self.canal.get() == "E-mail" else "Copiar mensagem")
        self.mostrar_opcoes_modelo()
        self.atualizar_previews()

    def mostrar_opcoes_modelo(self):
        self.atualizacao_area.pack_forget()
        self.acionamento_email.pack_forget()
        if self.modelo_comunicado.get() not in MODELOS_ABERTURA:
            self.atualizacao_area.pack(fill="x", before=self.area_previa, pady=(0, 4))
            if self.modelo_comunicado.get() == "Acionamento" and self.canal.get() == "E-mail":
                self.acionamento_email.pack(fill="x", pady=(0, 4))

    def mudar_modelo(self, _=None):
        self.mostrar_opcoes_modelo()
        self.comunicacao_alterada()

    def comunicacao_alterada(self, *_):
        self.atualizar_previews()
        if not self.carregando and not self.atualizando and not self.fechando:
            self.revisao += 1
            self.agendar_salvamento()

    def mostrar_evidencias(self):
        self.recolher_fila()
        self.paginas.select(self.pagina_evidencias)

    def ampliar_previa(self):
        janela = tk.Toplevel(self.root)
        janela.title(f"Prévia · {self.canal.get()} · {self.modelo_comunicado.get()}")
        janela.transient(self.root)
        janela.geometry("700x500")
        barra = ttk.Scrollbar(janela, orient="vertical")
        barra.pack(side="right", fill="y")
        texto = tk.Text(janela, wrap="word", font=("Segoe UI", 11), padx=16, pady=16, yscrollcommand=barra.set)
        texto.insert("1.0", self.previa.get("1.0", "end-1c"))
        texto.configure(state="disabled")
        texto.pack(fill="both", expand=True)
        barra.configure(command=texto.yview)
        janela.bind("<Escape>", lambda _: janela.destroy())

    def ampliar_imagem(self):
        if self.imagem is not None and not self.fechando:
            VisualizadorImagem(self.root, self.imagem)

    def escolher_evidencia(self, _=None):
        if self.evidencia_escolha.get() == "Recorte" and not all(c in self.recortes_email for c in CAMPOS_RECORTE):
            self.evidencia_escolha.set("Print completo")
            self.informar("Selecione os três recortes antes de usá-los no ticket.")
            return
        self.revisao += 1
        self.guardar_incidente()
        self.atualizar_resumo_evidencia()
        self.agendar_salvamento()

    def atualizar_resumo_evidencia(self):
        if self.imagem is None:
            self.evidencia_resumo.set("Sem print · Adicione uma evidência se necessário.")
        else:
            recortes = len(self.recortes_email)
            self.evidencia_resumo.set(f"{self.imagem.width} × {self.imagem.height}px · {recortes}/3 recortes · Ticket: {self.evidencia_escolha.get().lower()}")

    def atualizar_nome_operador(self):
        self.nome_compacto.pack_forget()
        self.linha_nome.pack_forget()
        self.nome_resumo.set(f"{self.config.nome_operador} - Equipe NOC" if self.config.nome_operador else "Equipe NOC · Nome não informado")
        (self.linha_nome if self.nome_em_edicao else self.nome_compacto).pack(fill="x")

    def editar_nome_operador(self):
        self.nome_em_edicao = True
        self.atualizar_nome_operador()
        self.entrada_nome_operador.focus_set()

    # ---------- fila ----------

    def guardar_incidente(self):
        item = self.fila.obter()
        if item is None:
            return
        dados = self.obter_dados()
        if not self.carregando:
            if dados.get("alerta") and not item["dados"].get("alerta") and not item["meta"].get("recebido_em"):
                registrar_evento(item, "Recebido", "Atendimento registrado localmente.", self.config.nome_operador)
            if ticket_valido(dados.get("ticket")) and dados["ticket"] != item["dados"].get("ticket"):
                registrar_evento(item, "Ticket vinculado", dados["ticket"], self.config.nome_operador)
        item["dados"] = dados
        item["imagem"] = self.imagem
        item["meta"]["recortes"] = dict(self.recortes_email)
        item["meta"]["evidencia_ticket"] = "recorte" if self.evidencia_escolha.get() == "Recorte" else "original"
        item["meta"]["comunicacao"] = {"modelo": self.modelo_comunicado.get(), "texto": self.texto_atualizacao.get()}

    def atualizar_fila(self):
        valores = []
        itens = [i for i in self.fila.itens if not i["meta"].get("arquivado") or i["id"] == self.fila.ativo]
        self.ids_seletor = [i["id"] for i in itens]
        for n, item in enumerate(itens, 1):
            d = item["dados"]
            base = f"{n}. {d.get('servidor') or 'Novo'} — {d.get('alerta') or 'sem alerta'}"[:90]
            if d.get("ticket"):
                base += f" · {d['ticket']}"
            valores.append(base)
        self.seletor_fila.configure(values=valores)
        try:
            indice = self.ids_seletor.index(self.fila.ativo)
        except ValueError:
            indice = 0
        if valores:
            self.seletor_fila.current(indice)
        self.btn_fila.configure(text="Voltar" if self.painel_fila.winfo_manager() else f"Fila ({len(self.fila.itens)})")
        self.painel_fila.atualizar(self.fila.itens, self.fila.ativo)
        self.atualizar_fluxo()

    def ativar_incidente(self, identificador, revisar=True):
        self.fila.ativo = identificador
        item = self.fila.obter()
        if revisar and any(item["dados"].values()):
            item["meta"]["em_revisao"] = True
        self.definir_dados(item["dados"])
        self.definir_imagem(item["imagem"], restaurar=True)
        self.atualizando = True
        try:
            comunicacao = item["meta"].get("comunicacao", {})
            self.modelo_comunicado.set(comunicacao.get("modelo") if comunicacao.get("modelo") in MODELOS else "Abertura normal")
            self.texto_atualizacao.set(comunicacao.get("texto", ""))
        finally:
            self.atualizando = False
        self.mostrar_opcoes_modelo()
        self.atualizar_previews()
        self.recebidos = [i for i in self.recebidos if i != identificador]
        self.atualizar_recebidos()
        self.atualizar_fila()
        self.atualizar_menu()
        self.revisao += 1
        self.agendar_salvamento()

    def selecionar_incidente(self, _=None):
        if self.operacao or self.carregando or self.fechando:
            return
        indice = self.seletor_fila.current()
        if 0 <= indice < len(self.ids_seletor):
            self.guardar_incidente()
            self.ativar_incidente(self.ids_seletor[indice])
            self.recolher_fila()

    def selecionar_da_lista(self, identificador):
        if not self.operacao and not self.carregando and not self.fechando and self.fila.obter(identificador):
            self.guardar_incidente()
            self.ativar_incidente(identificador)
            self.recolher_fila()

    def alternar_fila(self):
        if self.painel_fila.winfo_manager():
            self.recolher_fila()
        else:
            self.guardar_incidente()
            self.atualizar_fila()
            self.paginas.pack_forget()
            self.painel_fila.pack(fill="both", expand=True)
            self.btn_fila.configure(text="Voltar")

    def recolher_fila(self):
        if self.painel_fila.winfo_manager():
            self.painel_fila.pack_forget()
            self.paginas.pack(fill="both", expand=True, padx=16)
            self.btn_fila.configure(text=f"Fila ({len(self.fila.itens)})")

    def proximo_pendente(self):
        if self.operacao or self.carregando or self.fechando:
            return
        self.guardar_incidente()
        itens = self.fila.itens
        indice = next((n for n, i in enumerate(itens) if i["id"] == self.fila.ativo), 0)
        for item in itens[indice + 1:] + itens[:indice + 1]:
            if not item["meta"].get("arquivado") and etapa_incidente(item) != "Aguardando ticket" and (
                pendente_operacional(item)
            ):
                self.ativar_incidente(item["id"])
                self.recolher_fila()
                self.paginas.select(self.pagina_comunicar if ticket_valido(item["dados"].get("ticket")) else self.pagina_incidente)
                return
        self.informar("Nenhum atendimento com comunicação pendente ou acompanhamento vencido.")

    def arquivar_incidente(self):
        if self.operacao or self.carregando or self.fechando:
            return
        self.guardar_incidente()
        meta = self.fila.obter()["meta"]
        meta["arquivado"] = not meta.get("arquivado", False)
        meta["arquivado_em"] = agora() if meta["arquivado"] else ""
        self.revisao += 1
        self.salvar_rascunho()
        self.atualizar_controles()
        self.informar("Atendimento arquivado." if meta["arquivado"] else "Atendimento reaberto.")

    def atualizar_recebidos(self):
        self.recebidos = [i for i in self.recebidos if self.fila.obter(i)]
        if self.recebidos:
            self.btn_recebidos.configure(text=f"{len(self.recebidos)} recebido(s) · Ver")
            self.btn_recebidos.pack(side="right")
        else:
            self.btn_recebidos.pack_forget()

    def ver_recebidos(self):
        if self.recebidos:
            self.selecionar_da_lista(self.recebidos[0])

    def remover_incidente(self):
        if self.operacao or self.carregando or self.fechando:
            return
        self.guardar_incidente()
        atual = self.fila.obter()
        if atual in self.fila.itens:
            self.removidos.append((self.fila.itens.index(atual), atual))
            self.removidos = self.removidos[-20:]
            self.fila.itens.remove(atual)
        if not self.fila.itens:
            self.fila.novo()
        self.anterior = None
        self.ativar_incidente(self.fila.itens[0]["id"])
        self.informar("Incidente removido. Use ⋯ > Desfazer remoção para recuperá-lo.")

    def desfazer_remocao(self):
        if not self.removidos or self.operacao or self.carregando or self.fechando:
            return
        self.guardar_incidente()
        indice, item = self.removidos.pop()
        meta = item["meta"]
        existente = next((i for i in self.fila.itens if meta.get("eventid") and
                          (i["meta"].get("instancia"), i["meta"].get("eventid")) ==
                          (meta.get("instancia"), meta["eventid"])), None)
        if existente:
            for campo, valor in item["dados"].items():
                if not existente["dados"].get(campo):
                    existente["dados"][campo] = valor
                elif valor and valor != existente["dados"][campo] and campo in (*CAMPOS_EVENTO, "link_zabbix"):
                    existente["meta"].setdefault("atualizacoes", {})[campo] = valor
                elif campo == "ticket" and ticket_valido(valor) and valor != existente["dados"][campo]:
                    existente["meta"]["ticket_conflito"] = {"ticket": valor, "url": link_ticket(self.config.movidesk_url, valor)}
            if existente["imagem"] is None:
                existente["imagem"] = item["imagem"]
                existente["meta"]["recortes"] = meta.get("recortes", {})
                existente["meta"]["evidencia_ticket"] = meta.get("evidencia_ticket", "original")
            for chave in ("pedido", "preenchimento", "copias", "arquivado", "arquivado_em", "em_revisao"):
                if chave in meta:
                    existente["meta"].setdefault(chave, deepcopy(meta[chave]))
            for chave in ("acompanhamento", "regra", "coordenacao", "ultima_ia_relato", "recebido_em"):
                if chave in meta:
                    existente["meta"].setdefault(chave, deepcopy(meta[chave]))
            historico = {e["id"]: e for e in existente["meta"].get("historico", [])}
            historico.update({e["id"]: deepcopy(e) for e in meta.get("historico", [])})
            existente["meta"]["historico"] = sorted(historico.values(), key=lambda e: instante(e["em"]))
            for chave in ("referencias", "relacionados"):
                valores = existente["meta"].setdefault(chave, [])
                for valor in meta.get(chave, []):
                    if valor not in valores:
                        valores.append(deepcopy(valor))
            if not existente["meta"].get("comunicacao", {}).get("texto") and meta.get("comunicacao"):
                existente["meta"]["comunicacao"] = deepcopy(meta["comunicacao"])
            existente["meta"]["campos_revisados"] = sorted(set(meta.get("campos_revisados", [])) | set(existente["meta"].get("campos_revisados", [])))
            self.vinculos_retorno[item["id"]] = existente["id"]
            self.movidesk.comandos.put((None, {"_transferir_incidente": item["id"], "_destino": existente["id"]}))
            item = existente
        else:
            self.fila.itens.insert(min(indice, len(self.fila.itens)), item)
        self.ativar_incidente(item["id"], revisar=False)
        self.salvar_rascunho()
        self.informar("Remoção desfeita. Campos e evidência recuperados.")

    def atualizar_menu(self):
        try:
            self.menu_mais.entryconfig(self.acoes_menu["desfazer"],
                                        state="normal" if self.anterior else "disabled")
            self.menu_mais.entryconfig(self.acoes_menu["restaurar"], state="normal" if self.removidos else "disabled")
        except (tk.TclError, KeyError, AttributeError):
            pass

    # ---------- entrada ----------

    def importar_clipboard(self):
        if self.operacao or self.carregando or self.fechando:
            return
        try:
            self.aplicar_importacao(importar_eventos(pyperclip.paste()))
        except Exception as exc:
            self.exibir_erro(str(exc))

    def aplicar_importacao(self, eventos, selecionar=True):
        inicio = time.monotonic()
        self.guardar_incidente()
        atual = self.fila.obter()
        vazio = not any(atual["dados"].values()) and atual["imagem"] is None
        ids = self.fila.importar(eventos)
        for identificador in ids:
            item = self.fila.obter(identificador)
            item["meta"]["metricas"] = {"origem": "DOM", "segundos": time.monotonic() - inicio, "chamadas": 0}
        if selecionar or vazio:
            self.ativar_incidente(ids[0], revisar=False)
        else:
            # Só atualiza valores alterados da coleta. Não reinicia cursor/seleção da edição atual.
            self.atualizando = True
            try:
                for campo in CAMPOS:
                    valor = atual["dados"].get(campo, "")
                    if self.vars[campo].get() != valor:
                        self.vars[campo].set(valor)
                        if campo == "situacao":
                            self.entradas[campo].delete("1.0", "end")
                            self.entradas[campo].insert("1.0", valor)
                            self.entradas[campo].edit_modified(False)
            finally:
                self.atualizando = False
            if atual["imagem"] is not self.imagem:
                self.definir_imagem(atual["imagem"], restaurar=True)
            self.recebidos = list(dict.fromkeys([*self.recebidos, *(i for i in ids if i != self.fila.ativo)]))
            self.atualizar_recebidos()
            self.atualizar_previews()
            self.revisao += 1
        self.salvar_rascunho()
        msg = "Evento importado. Revise e crie ou informe o ticket." if len(ids) == 1 else \
            f"{len(ids)} eventos recebidos na fila."
        self.informar(msg)

    def conectar_zabbix(self):
        identificador = self.iniciar_operacao("conexao", "Conectando ao Zabbix…")
        if identificador is not None:
            self.conexao_resumo.set("Zabbix: conectando…")
            self.movidesk.comandos.put((identificador, {"_conectar": True}))

    def ler_print(self):
        self.extrair_com_ia(self.config.ia_automatica, usar_clipboard=True)

    def situacao_alterada(self, _=None):
        entrada = self.entradas["situacao"]
        if entrada.edit_modified():
            entrada.edit_modified(False)
            self.vars["situacao"].set(entrada.get("1.0", "end-1c"))

    def definir_dados(self, dados):
        self.atualizando = True
        try:
            for campo in CAMPOS:
                self.vars[campo].set(dados.get(campo, ""))
                self.erros[campo].set("")
            texto = self.entradas["situacao"]
            estado = texto.cget("state")
            texto.configure(state="normal")
            texto.delete("1.0", "end")
            texto.insert("1.0", self.vars["situacao"].get())
            texto.edit_modified(False)
            texto.edit_reset()
            texto.configure(state=estado)
        finally:
            self.atualizando = False
        self.atualizar_previews()

    def obter_dados(self):
        return {campo: variavel.get().strip() for campo, variavel in self.vars.items()}

    def alterado(self, campo=None):
        if self.atualizando or self.carregando or self.fechando:
            return
        for erro in self.erros.values():
            erro.set("")
        self.revisao += 1
        item = self.fila.obter()
        if item is not None:
            item["meta"]["em_revisao"] = True
            revisados = set(item["meta"].get("campos_revisados", []))
            if campo in (*CAMPOS_EVENTO, "link_zabbix") and self.vars[campo].get().strip() != item["dados"].get(campo, ""):
                revisados.add(campo)
            item["meta"]["campos_revisados"] = sorted(revisados)
            if campo == "ticket" and self.vars["ticket"].get().strip() != item["dados"].get("ticket", ""):
                item["meta"].pop("ticket_conflito", None)
                if ticket_valido(self.vars["ticket"].get().strip()):
                    item["meta"]["pedido"] = {"estado": "concluido"}
        self.atualizar_previews()
        self.atualizar_fluxo()
        self.agendar_salvamento()

    def atualizar_previews(self):
        if not hasattr(self, "previa"):
            return
        dados = self.obter_dados()
        self.assunto_email.set(gerar_assunto_email(dados, self.modelo_comunicado.get()))
        self.previa.configure(state="normal")
        self.previa.delete("1.0", "end")
        self.previa.insert("1.0", gerar_template(dados, self.canal.get(), self.config.movidesk_url,
                                                self.nome_operador.get(), self.modelo_comunicado.get(),
                                                self.texto_atualizacao.get()))
        self.previa.configure(state="disabled")
        item = self.fila.obter()
        copia = item["meta"].get("copias", {}).get(self.canal.get(), {}) if item else {}
        quando = copia.get("em", "")[:19].replace("T", " ")
        self.copias_resumo.set(f"Copiado: {quando} · {copia.get('modelo', 'Abertura')}" if quando else "Nenhuma mensagem copiada neste canal.")

    def salvar_nome_operador(self):
        if self.carregando or self.fechando:
            return
        try:
            nome = gravar_nome_operador(self.config.diretorio, self.nome_operador.get())
            self.config = replace(self.config, nome_operador=nome)
            self.nome_operador.set(nome)
            self.nome_em_edicao = False
            self.atualizar_nome_operador()
            self.informar("Nome salvo para os próximos atendimentos.")
        except Exception as exc:
            self.exibir_erro(f"Não foi possível salvar seu nome.\n\n{exc}")

    def rolar(self, evento):
        try:
            if evento.widget.winfo_toplevel() != self.root or isinstance(evento.widget, (tk.Text, ttk.Combobox)):
                return
            self.canvas.yview_scroll(-int(evento.delta / 120), "units")
        except (tk.TclError, AttributeError):
            pass

    def mostrar_campo(self, entrada):
        try:
            self.root.update_idletasks()
            y = entrada.winfo_rooty() - self.conteudo.winfo_rooty()
            topo = self.canvas.canvasy(0)
            if y < topo or y + entrada.winfo_height() > topo + self.canvas.winfo_height():
                self.canvas.yview_moveto(max(0, y - 24) / max(1, self.conteudo.winfo_height()))
        except (tk.TclError, AttributeError):
            pass

    def atualizar_controles(self):
        bloqueado = self.carregando or self.fechando
        ocupado = bloqueado or self.operacao is not None
        for botao in (self.btn_novo, self.btn_importar, self.btn_ler_print, self.btn_movidesk,
                      self.btn_comunicado, self.btn_conectar, self.btn_proximo, self.btn_recebidos,
                      self.btn_adicionar_print, self.btn_operacao):
            try:
                botao.configure(state="disabled" if ocupado else "normal")
            except tk.TclError:
                pass
        for combo in (self.seletor_fila, self.seletor_canal, self.seletor_modelo):
            try:
                combo.configure(state="disabled" if ocupado else "readonly")
            except tk.TclError:
                pass
        try:
            self.btn_mais.configure(state="disabled" if ocupado else "normal")
        except tk.TclError:
            pass
        self.btn_print.configure(state="disabled" if ocupado or self.imagem is None else "normal")
        self.btn_ampliar.configure(state="disabled" if self.fechando or self.imagem is None else "normal")
        self.seletor_evidencia.configure(state="disabled" if ocupado or self.imagem is None else "readonly")
        self.btn_recortar_email.configure(state="disabled" if ocupado or self.imagem is None else "normal")
        self.btn_imagem_email.configure(
            state="normal" if not ocupado and self.imagem is not None
            and all(c in self.recortes_email for c in CAMPOS_RECORTE) else "disabled")
        edicao_bloqueada = bloqueado or (self.operacao and self.operacao[1] == "ia")
        self.entrada_nome_operador.configure(state="disabled" if edicao_bloqueada else "normal")
        self.btn_salvar_nome.configure(state="disabled" if edicao_bloqueada else "normal")
        self.entrada_atualizacao.configure(state="disabled" if edicao_bloqueada else "normal")
        self.entrada_acionamento_email.configure(state="disabled" if edicao_bloqueada else "normal")
        self.painel_fila.bloquear(ocupado)
        for entrada in self.entradas.values():
            try:
                entrada.configure(state="disabled" if edicao_bloqueada else "normal")
            except tk.TclError:
                pass
        for botao in self.btns_copiar:
            botao.configure(state="disabled" if edicao_bloqueada else "normal")
        self.atualizar_fluxo()

    def atualizar_fluxo(self):
        if not hasattr(self, "btn_atendimento"):
            return
        item = self.fila.obter()
        if item is None:
            return
        atual = {**item, "dados": self.obter_dados()}
        self.proxima_acao.set(proxima_acao(atual))
        pedido = item["meta"].get("pedido", {}).get("estado")
        ticket = atual["dados"].get("ticket", "")
        if ticket_valido(ticket):
            rotulo = f"Abrir ticket #{ticket}"
        elif ticket:
            rotulo = "Revisar ticket"
        elif pedido in ("abrindo", "aguardando"):
            rotulo = "Voltar ao formulário"
        elif pedido in ("erro", "expirado", "interrompido"):
            rotulo = "Informar ticket"
        else:
            rotulo = "Criar ticket"
        self.btn_movidesk.configure(text=rotulo)
        bloqueado = self.carregando or self.fechando or self.operacao is not None
        self.btn_movidesk.configure(state="disabled" if bloqueado or (item["meta"].get("arquivado") and not ticket) else "normal")
        quantidade = len(pendencias_incidente(atual))
        self.btn_atendimento.configure(text=f"Pendências ({quantidade})" if quantidade else "Atendimento",
                                       state="disabled" if self.carregando or self.fechando else "normal")

    def detalhes_atendimento(self):
        if self.carregando or self.fechando:
            return
        self.guardar_incidente()
        identificador = self.fila.ativo
        janela = tk.Toplevel(self.root)
        janela.title("Atendimento · Pendências e atualizações")
        janela.transient(self.root)
        janela.geometry("760x560")
        conteudo = ttk.Frame(janela, padding=12)
        conteudo.pack(fill="both", expand=True)
        texto = tk.Text(conteudo, height=8, wrap="word", font=("Segoe UI", 10))
        barra = ttk.Scrollbar(conteudo, orient="vertical", command=texto.yview)
        texto.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        texto.pack(fill="both", expand=True)
        atualizacoes = ttk.Treeview(conteudo, columns=("campo", "atual", "novo"), show="headings", height=4, selectmode="browse")
        for c, rotulo, largura in (("campo", "Campo", 120), ("atual", "Sua revisão", 270), ("novo", "Valor disponível", 270)):
            atualizacoes.heading(c, text=rotulo)
            atualizacoes.column(c, width=largura, minwidth=70)
        atualizacoes.pack(fill="x", pady=8)
        acoes = ttk.Frame(conteudo)
        acoes.pack(fill="x")

        def atualizar():
            item = self.fila.obter(identificador)
            if item is None:
                janela.destroy()
                return
            meta = item["meta"]
            linhas = [f"{item['dados'].get('servidor', '')} — {item['dados'].get('alerta', '')}",
                      proxima_acao(item), f"Origem: {meta.get('origem', 'manual')} · Última coleta: {meta.get('coletado_em', '—')}", ""]
            linhas.extend(pendencias_incidente(item) or ["Nenhuma pendência registrada."])
            if meta.get("pedido", {}).get("expira"):
                linhas.append("Prazo do retorno: " + time.strftime("%d/%m/%Y %H:%M", time.localtime(meta["pedido"]["expira"])))
            if meta.get("preenchimento"):
                linhas.append("\nResultado do preenchimento automático (antes da revisão no site):")
                linhas.extend(f"• {ROTULOS_CAMPOS.get(c, c)}: {STATUS_PREENCHIMENTO.get(s, s)}" for c, s in meta["preenchimento"].items())
            for c, valor in meta.get("atualizacoes", {}).items():
                linhas.append(f"\n{ROTULOS_CAMPOS.get(c, c)}\nSua revisão: {item['dados'].get(c, '')}\nDisponível: {valor}")
            for canal, copia in meta.get("copias", {}).items():
                linhas.append(f"\n{canal}: {copia.get('modelo', 'Abertura')} copiado em {copia.get('em', '')}.")
            texto.configure(state="normal")
            texto.delete("1.0", "end")
            texto.insert("1.0", "\n".join(linhas))
            texto.configure(state="disabled")
            atualizacoes.delete(*atualizacoes.get_children())
            for campo, valor in meta.get("atualizacoes", {}).items():
                atualizacoes.insert("", "end", iid=campo, values=(ROTULOS_CAMPOS.get(campo, campo), item["dados"].get(campo, ""), valor))

        def resolver(aplicar):
            if self.operacao or self.fechando or not atualizacoes.selection():
                return
            if self.fila.obter(identificador) is None:
                janela.destroy()
                return
            if identificador == self.fila.ativo:
                self.guardar_incidente()
            self.fila.resolver_atualizacao(identificador, atualizacoes.selection()[0], aplicar)
            if identificador == self.fila.ativo:
                self.definir_dados(self.fila.obter()["dados"])
            self.revisao += 1
            self.salvar_rascunho()
            atualizar()

        ttk.Button(acoes, text="Aplicar valor selecionado", command=lambda: resolver(True)).pack(side="left")
        ttk.Button(acoes, text="Manter minha revisão", command=lambda: resolver(False)).pack(side="left", padx=6)
        item = self.fila.obter(identificador)
        if item["meta"].get("ticket_conflito"):
            def resolver_ticket(usar_recebido):
                item = self.fila.obter(identificador)
                if self.operacao or self.fechando or item is None:
                    return
                if identificador == self.fila.ativo:
                    self.guardar_incidente()
                conflito = item["meta"].pop("ticket_conflito", None)
                if usar_recebido and conflito:
                    item["dados"]["ticket"] = conflito["ticket"]
                    item["meta"]["link_movidesk"] = conflito["url"]
                    if identificador == self.fila.ativo:
                        self.vars["ticket"].set(conflito["ticket"])
                self.revisao += 1
                self.salvar_rascunho()
                janela.destroy()
            conflito_acoes = ttk.Frame(conteudo)
            conflito_acoes.pack(fill="x", pady=6)
            ttk.Button(conflito_acoes, text="Usar ticket retornado", command=lambda: resolver_ticket(True)).pack(side="left")
            ttk.Button(conflito_acoes, text="Manter ticket informado", command=lambda: resolver_ticket(False)).pack(side="left", padx=6)
        if item["meta"].get("pedido", {}).get("estado") in ("erro", "expirado", "interrompido") and not item["dados"].get("ticket"):
            def novo_formulario():
                if self.operacao or self.fechando or self.fila.obter(identificador) is None:
                    return
                self.selecionar_da_lista(identificador)
                janela.destroy()
                self.preencher_movidesk(novo_formulario=True)
            ttk.Button(conteudo, text="Preparar novo formulário (após conferir a guia anterior)", command=novo_formulario).pack(fill="x", pady=6)
        atualizar()

    def iniciar_operacao(self, tipo, mensagem):
        if self.operacao or self.carregando or self.fechando:
            return None
        self.sequencia += 1
        self.operacao = (self.sequencia, tipo)
        self.inicio_operacao = time.monotonic()
        self.informar(mensagem)
        self.progresso.pack(after=self.status_label, fill="x", pady=4)
        self.progresso.start(12)
        self.atualizar_controles()
        return self.sequencia

    def executar(self, tipo, mensagem, funcao):
        identificador = self.iniciar_operacao(tipo, mensagem)
        if identificador is None:
            return
        eventos = self.eventos

        def tarefa():
            try:
                resultado = funcao()
                eventos.put((f"{tipo}_ok", identificador, resultado))
            except Exception as exc:
                logging.getLogger("noc").exception("Falha na operação %s", tipo)
                eventos.put(("erro", identificador, str(exc)))

        threading.Thread(target=tarefa, name=f"noc-{tipo}", daemon=True).start()

    @staticmethod
    def ler_clipboard():
        imagem = ImageGrab.grabclipboard()
        if not isinstance(imagem, Image.Image):
            raise ValueError("Sem imagem no clipboard. Use Win+Shift+S e tente de novo.")
        return imagem.convert("RGB")

    def capturar_print(self):
        self.executar("captura", "Guardando print…", self.ler_clipboard)

    def definir_imagem(self, imagem, restaurar=False):
        if restaurar:
            item = self.fila.obter()
            caixas = item["meta"].get("recortes", {})
            self.recortes_email = {c: tuple(v) for c, v in caixas.items() if imagem is not None and c in CAMPOS_RECORTE
                                   and isinstance(v, (tuple, list)) and len(v) == 4 and all(isinstance(n, int) for n in v)
                                   and 0 <= v[0] < v[2] <= imagem.width and 0 <= v[1] < v[3] <= imagem.height}
            recorte = item["meta"].get("evidencia_ticket") == "recorte" and len(self.recortes_email) == 3
            self.evidencia_escolha.set("Recorte" if recorte else "Print completo")
        elif imagem is not self.imagem:
            self.recortes_email = {}
            self.evidencia_escolha.set("Print completo")
        self.imagem = imagem
        self.miniatura = None
        self.miniatura_chave = None
        self.preview_imagem.configure(image="", text="Sem print (opcional)" if imagem is None else "")
        self.agendar_miniatura()
        self.atualizar_controles()
        self.atualizar_resumo_evidencia()

    def agendar_miniatura(self, _=None):
        if self.imagem_after:
            self.root.after_cancel(self.imagem_after)
        if not self.fechando:
            self.imagem_after = self.root.after_idle(self.renderizar_miniatura)

    def renderizar_miniatura(self):
        self.imagem_after = None
        if self.imagem is None or not self.preview_imagem.winfo_viewable():
            return
        tamanho = (max(1, min(500, self.preview_imagem.winfo_width())), max(1, min(240, self.preview_imagem.winfo_height())))
        chave = (id(self.imagem), *tamanho)
        if chave != self.miniatura_chave:
            miniatura = self.imagem.copy()
            miniatura.thumbnail(tamanho)
            self.miniatura = ImageTk.PhotoImage(miniatura, master=self.root)
            self.miniatura_chave = chave
            self.preview_imagem.configure(image=self.miniatura, text="")

    def mostrar_tokens(self):
        self.guardar_incidente()
        janela = tk.Toplevel(self.root)
        janela.title("Consumo e detalhes")
        janela.transient(self.root)
        conteudo = ttk.Frame(janela, padding=20)
        conteudo.pack(fill="both", expand=True)
        ttk.Label(conteudo, textvariable=self.resumo_tokens, wraplength=560,
                  justify="left").pack(fill="x")
        medidas = [i["meta"].get("metricas", {}) for i in self.fila.itens if i["meta"].get("metricas")]
        locais = sum(1 for m in medidas if m.get("chamadas", 0) == 0)
        linhas = [f"Incidentes com operação local: {locais}/{len(medidas)}." if medidas
                   else "Nenhuma importação/extração registrada."]
        for n, item in enumerate(self.fila.itens, 1):
            meta = item["meta"]
            m = meta.get("metricas", {})
            linhas.append(
                f"{n}. {item['dados'].get('servidor') or 'Novo'} · {meta.get('origem', 'manual')} · "
                f"{m.get('segundos', 0):.1f}s · {m.get('chamadas', 0)} IA · "
                f"{meta.get('tokens_reportados', 0)} tokens")
        ttk.Label(conteudo, text="\n".join(linhas), wraplength=560, justify="left",
                  style="Discreto.TLabel").pack(fill="x", pady=(12, 0))
        ttk.Button(conteudo, text="Configurações", command=self.configurar_apis).pack(anchor="w", pady=(12, 0))

    def configurar_apis(self):
        try:
            arquivo = preparar_config_apis(self.config.diretorio)
            subprocess.Popen(["notepad.exe", str(arquivo)])
            self.informar("Ajuste o .env, salve e reinicie o NOCFlow.")
        except Exception as exc:
            self.exibir_erro(f"Não foi possível abrir as configurações.\n\n{exc}")

    def extrair_com_ia(self, permitir_ia=True, usar_clipboard=False):
        if self.operacao or self.carregando or self.fechando:
            return
        imagem = self.imagem
        eventos = self.eventos
        config = self.config
        conhecidos = {c: self.vars[c].get().strip() for c in CAMPOS_EVENTO} if permitir_ia and not usar_clipboard else {}

        def tarefa():
            capturada = NOCFlow.ler_clipboard() if usar_clipboard or imagem is None else imagem
            eventos.put(("imagem", identificador, capturada))
            return extrair_dados(config, capturada, lambda tipo, texto: eventos.put((tipo, identificador, texto)),
                                permitir_ia=permitir_ia, cache=self.cache_extracao, conhecidos=conhecidos)

        self.provedor_ia = "IA"
        self.imagem_extracao = None
        self.avisos_extracao = []
        self.metricas_extracao = {}
        self.tokens_extracao = 0
        identificador = self.iniciar_operacao("ia", "Lendo print…")
        if identificador is None:
            return

        def executar_ia():
            try:
                eventos.put(("ia_ok", identificador, tarefa()))
            except Exception as exc:
                logging.getLogger("noc").exception("Falha na extração com IA")
                eventos.put(("erro", identificador, str(exc)))

        threading.Thread(target=executar_ia, name="noc-ia", daemon=True).start()

    def copiar_assunto_email(self):
        if self.fechando or self.carregando or not self.validar("E-mail"):
            return
        try:
            pyperclip.copy(gerar_assunto_email(self.obter_dados(), self.modelo_comunicado.get()))
            self.informar("Assunto copiado.")
        except Exception as exc:
            self.exibir_erro(f"Não foi possível copiar.\n\n{exc}")

    def recortar_imagem_email(self):
        if self.imagem is None or self.operacao or self.carregando or self.fechando:
            return
        imagem = self.imagem

        def confirmar(caixas):
            if self.imagem is not imagem or self.fechando:
                return
            self.recortes_email = caixas
            self.revisao += 1
            self.salvar_rascunho()
            self.atualizar_resumo_evidencia()
            self.atualizar_controles()
            self.informar("Recortes salvos neste incidente. Escolha Recorte para usá-los no ticket ou copie a montagem.")

        EditorRecortes(self.root, imagem, self.recortes_email, confirmar)

    def copiar_imagem_email(self):
        if self.imagem is None or not all(c in self.recortes_email for c in CAMPOS_RECORTE):
            return
        imagem, caixas = self.imagem, dict(self.recortes_email)
        hwnd = self.root.winfo_id()
        self.executar("imagem_email", "Copiando recorte…",
                      lambda: copiar_imagem(montar_recortes(imagem, caixas), hwnd))

    def copiar_print(self):
        if self.imagem is not None:
            imagem = self.imagem
            hwnd = self.root.winfo_id()
            self.executar("print", "Copiando print…", lambda: copiar_imagem(imagem, hwnd))

    def validar(self, finalidade):
        permitir_sem_ticket = False
        if self.modelo_comunicado.get() == "Acionamento inicial":
            decisao = self.avaliar_perfil(self.obter_dados())
            permitir_sem_ticket = decisao.get("estado") == "aplicada" and decisao["resultado"].get("comunicar_sem_ticket", False)
        erros = validar_dados(self.obter_dados(), finalidade, permitir_sem_ticket)
        for campo, variavel in self.erros.items():
            variavel.set(erros.get(campo, ""))
        if erros:
            self.recolher_fila()
            campo = next(iter(erros))
            try:
                self.paginas.select(str(self.pagina_comunicar if campo in ("ticket", "acionamento", "time_resp")
                                        else self.pagina_incidente))
            except tk.TclError:
                pass
            try:
                self.entradas[campo].focus_set()
            except (tk.TclError, KeyError):
                pass
            self.informar("Revise os campos destacados.")
        if not erros and finalidade in ("WhatsApp", "Teams", "E-mail") and self.modelo_comunicado.get() not in (*MODELOS_ABERTURA, "Acionamento inicial"):
            if not self.texto_atualizacao.get().strip():
                self.paginas.select(self.pagina_comunicar)
                self.entrada_atualizacao.focus_set()
                self.informar("Descreva a atualização ou normalização antes de copiar.")
                return False
            if self.modelo_comunicado.get() == "Acionamento" and not (self.vars["acionamento"].get().strip() or self.vars["time_resp"].get().strip()):
                self.paginas.select(self.pagina_comunicar)
                self.informar("Informe a equipe acionada ou o time responsável.")
                return False
        return not erros

    def preencher_movidesk(self, novo_formulario=False):
        if self.operacao or self.carregando or self.fechando:
            return
        ticket = self.vars["ticket"].get().strip()
        if ticket:
            try:
                url = link_ticket(self.config.movidesk_url, ticket)
            except ValueError as exc:
                self.erros["ticket"].set(str(exc))
                self.entradas["ticket"].focus_set()
                return
            self.executar("abrir_ticket", f"Abrindo ticket {ticket}…", lambda: abrir_no_edge(url))
            return
        item = self.fila.obter()
        if item["meta"].get("arquivado"):
            self.informar("Reabra o atendimento antes de criar outro ticket.")
            return
        estado = item["meta"].get("pedido", {}).get("estado")
        if estado in ("abrindo", "aguardando"):
            identificador = self.iniciar_operacao("retomar", "Localizando formulário no Edge…")
            self.movidesk.comandos.put((identificador, {"_retomar": True, "_incidente_id": self.fila.ativo}))
            return
        if estado in ("erro", "expirado", "interrompido") and not novo_formulario:
            self.entradas["ticket"].focus_set()
            self.informar("Informe o ticket salvo. Para um novo formulário, abra Pendências e confira a guia anterior.")
            return
        if not self.validar("Movidesk"):
            return
        self.guardar_incidente()
        if item["dados"].get("perfil"):
            decisao = self.avaliar_perfil(item["dados"])
            if decisao["estado"] != "aplicada":
                self.informar(decisao["mensagem"])
                return
            if decisao["resultado"].get("politica_ticket") == "vincular":
                self.informar("Este perfil orienta vincular um ticket existente. Informe o número ou use Referências na Central.")
                return
            if item["meta"].get("regra", {}).get("assinatura") != decisao.get("assinatura"):
                self.informar("O perfil ou contexto precisa de revisão. Use Central operacional > Avaliar regra e aplique a orientação vigente.")
                return
            if decisao["resultado"].get("prioridade") and item["dados"].get("prioridade") != decisao["resultado"]["prioridade"]:
                self.informar("Confira e aplique a prioridade indicada em Central operacional > Avaliar regra.")
                return
        identificador = self.iniciar_operacao("movidesk", "Abrindo Movidesk…")
        imagem = montar_recortes(self.imagem, self.recortes_email) if self.imagem is not None and self.evidencia_escolha.get() == "Recorte" else self.imagem
        item["meta"]["pedido"] = {"estado": "abrindo"}
        item["meta"].pop("preenchimento", None)
        item["meta"]["em_revisao"] = True
        self.revisao += 1
        self.salvar_rascunho()
        self.movidesk.comandos.put((identificador, {
            **self.obter_dados(),
            "_incidente_id": self.fila.ativo,
            "_imagem": imagem,
            "_novo_pedido": novo_formulario,
        }))

    def configurar_extensao(self):
        try:
            pasta = preparar_extensao(self.config.diretorio)
        except Exception as exc:
            self.exibir_erro(f"Não foi possível preparar a extensão.\n\n{exc}")
            return
        janela = tk.Toplevel(self.root)
        janela.title("Extensão do Edge")
        janela.transient(self.root)
        conteudo = ttk.Frame(janela, padding=20)
        conteudo.pack(fill="both", expand=True)
        ttk.Label(conteudo, text="Instale uma vez no perfil do Edge com Zabbix e Movidesk.",
                  wraplength=480).pack(anchor="w")
        ttk.Label(conteudo, text="1. Abra edge://extensions/ e ative o modo desenvolvedor.\n"
                  "2. Carregar sem compactação na pasta abaixo.\n3. Recarregue após atualizar.",
                  wraplength=480).pack(anchor="w", pady=12)
        caminho = ttk.Entry(conteudo, width=70)
        caminho.insert(0, str(pasta))
        caminho.configure(state="readonly")
        caminho.pack(fill="x", pady=(0, 10))

        def abrir_extensoes():
            try:
                abrir_no_edge("edge://extensions/")
            except Exception as exc:
                self.exibir_erro(str(exc))

        def copiar_caminho():
            try:
                pyperclip.copy(str(pasta))
                self.informar("Caminho copiado.")
            except Exception as exc:
                self.exibir_erro(str(exc))

        ttk.Button(conteudo, text="Abrir extensões", command=abrir_extensoes).pack(fill="x", pady=3)
        ttk.Button(conteudo, text="Copiar caminho", command=copiar_caminho).pack(fill="x", pady=3)

    def copiar_comunicado(self, canal):
        if self.fechando or self.carregando or not self.validar(canal):
            return
        try:
            pyperclip.copy(gerar_template(self.obter_dados(), canal, self.config.movidesk_url,
                                          self.nome_operador.get(), self.modelo_comunicado.get(),
                                          self.texto_atualizacao.get()))
            self.fila.obter()["meta"].setdefault("copias", {})[canal] = {"em": agora(), "modelo": self.modelo_comunicado.get()}
            registrar_evento(self.fila.obter(), "Mensagem copiada", self.modelo_comunicado.get(), self.config.nome_operador, canal)
            self.revisao += 1
            self.salvar_rascunho()
            self.atualizar_previews()
            self.informar(f"{canal} copiado.")
        except Exception as exc:
            self.exibir_erro(f"Não foi possível copiar.\n\n{exc}")

    def novo_incidente(self):
        if self.operacao or self.carregando or self.fechando:
            return
        self.guardar_incidente()
        self.recolher_fila()
        self.anterior = self.fila.ativo
        self.fila.novo()
        self.definir_dados({})
        self.definir_imagem(None)
        self.atualizando = True
        try:
            self.modelo_comunicado.set("Abertura normal")
            self.texto_atualizacao.set("")
        finally:
            self.atualizando = False
        self.mostrar_opcoes_modelo()
        self.atualizar_previews()
        self.atualizar_fila()
        self.atualizar_menu()
        self.revisao += 1
        self.salvar_rascunho()
        try:
            self.paginas.select(str(self.pagina_incidente))
            self.canvas.yview_moveto(0)
        except tk.TclError:
            pass
        self.entradas["alerta"].focus_set()
        self.informar("Novo incidente. Importe os dados ou preencha.")

    def desfazer_novo(self):
        if self.anterior is None or self.operacao or self.carregando or self.fechando:
            return
        self.guardar_incidente()
        if self.fila.obter(self.anterior) is None:
            return
        atual = self.fila.obter()
        if atual is not None and not any(atual["dados"].values()) and atual["imagem"] is None:
            self.fila.itens.remove(atual)
        self.ativar_incidente(self.anterior)
        self.anterior = None
        self.atualizar_menu()
        self.revisao += 1
        self.salvar_rascunho()
        self.informar("Incidente anterior restaurado.")

    def agendar_salvamento(self):
        self.status_rascunho.set("Alterações pendentes…")
        if self.save_after:
            self.root.after_cancel(self.save_after)
        self.save_after = self.root.after(750, self.salvar_rascunho)

    def salvar_rascunho(self):
        if self.save_after:
            self.root.after_cancel(self.save_after)
            self.save_after = None
        if not self.carregando:
            self.guardar_incidente()
            self.atualizar_fila()
            self.status_rascunho.set("Salvando…")
            self.rascunho.comandos.put((self.revisao, self.obter_dados(), self.imagem, self.fila.snapshot()))

    def informar(self, mensagem):
        self.status.set(mensagem)
        self.ultimo_erro = ""
        self.btn_detalhes.pack_forget()

    def exibir_erro(self, mensagem):
        self.ultimo_erro = mensagem
        self.status.set(mensagem.split("\n")[0][:350])
        self.btn_detalhes.pack(anchor="w", pady=(4, 0))

    def detalhes_erro(self):
        messagebox.showerror("Detalhes", self.ultimo_erro, parent=self.root)

    def incidente_do_retorno(self, identificador):
        # Remover é reversível nesta sessão; o retorno acompanha o item até o desfazer.
        while identificador in self.vinculos_retorno:
            identificador = self.vinculos_retorno[identificador]
        return self.fila.obter(identificador) or next((i for _, i in self.removidos if i["id"] == identificador), None)

    def processar_eventos(self):
        self.poll_after = None
        try:
            while True:
                tipo, identificador, resultado = self.eventos.get_nowait()
                if tipo == "rascunho_carregado":
                    if not self.fechando:
                        dados, imagem = resultado
                        self.definir_dados(dados)
                        self.definir_imagem(imagem)
                        if self.rascunho.fila_carregada:
                            self.fila.restaurar(self.rascunho.fila_carregada)
                            for item in self.fila.itens:
                                if item["meta"].get("pedido", {}).get("estado") in ("abrindo", "aguardando"):
                                    item["meta"]["pedido"] = {"estado": "interrompido",
                                        "mensagem": "A sessão anterior terminou. Informe o número do ticket salvo; o retorno precisa de uma conexão ativa."}
                            self.ativar_incidente(self.fila.ativo, revisar=False)
                        else:
                            self.guardar_incidente()
                        self.atualizar_fila()
                        self.atualizar_menu()
                        self.carregando = False
                        self.carregar_perfis_operacionais()
                        self.atualizar_controles()
                        self.informar("Pronto. Importe os dados do Zabbix." if not any(dados.values()) and not imagem
                                      else "Rascunho recuperado.")
                elif tipo == "rascunho_erro_carga":
                    self.carregando = False
                    self.atualizar_controles()
                    self.exibir_erro(f"Rascunho inválido. Veja .noc_data/rascunho.json.\n\n{resultado}")
                elif tipo == "rascunho_salvo":
                    if identificador == self.revisao:
                        self.status_rascunho.set("✓ Salvo")
                        if self.fechando:
                            self.encerrar_workers()
                elif tipo == "rascunho_erro":
                    if identificador == self.revisao:
                        self.status_rascunho.set("Não salvo — verifique espaço/permissão")
                        self.exibir_erro(f"Não foi possível salvar.\n\n{resultado}")
                        if self.fechando:
                            if messagebox.askyesno("Rascunho não salvo",
                                                  "Fechar sem salvar?", parent=self.root):
                                self.encerrar_workers()
                            else:
                                self.fechando = False
                                self.atualizar_controles()
                elif tipo == "zabbix_importado" and not self.fechando:
                    self.importacoes_pendentes.append(resultado)
                elif tipo == "conexao_status" and not self.fechando:
                    self.estado_conexao = resultado["estado"]
                    nomes = {"conectado": "conectado", "desconectado": "desconectado", "expirado": "conexão expirada",
                             "sem_resposta": "sem resposta do navegador"}
                    texto = "Zabbix: " + nomes.get(self.estado_conexao, self.estado_conexao)
                    if self.estado_conexao == "conectado" and resultado.get("expira"):
                        texto += " até " + time.strftime("%H:%M", time.localtime(resultado["expira"]))
                    self.conexao_resumo.set(texto)
                    self.btn_conectar.configure(text="Reconectar" if self.estado_conexao != "desconectado" else "Conectar")
                elif tipo == "pedido_status" and not self.fechando:
                    item = self.incidente_do_retorno(identificador)
                    if item:
                        identificador = item["id"]
                        if identificador == self.fila.ativo:
                            self.guardar_incidente()
                        pedido = dict(resultado)
                        if "campos" in pedido:
                            item["meta"]["preenchimento"] = pedido.pop("campos")
                        item["meta"]["pedido"] = {"estado": "concluido"} if ticket_valido(item["dados"].get("ticket")) else pedido
                        self.revisao += 1
                        self.salvar_rascunho()
                elif tipo == "ticket_recebido" and not self.fechando:
                    item = self.incidente_do_retorno(identificador)
                    if item:
                        identificador = item["id"]
                        if identificador == self.fila.ativo:
                            self.guardar_incidente()
                        existente = item["dados"].get("ticket")
                        if existente and existente != resultado["ticket"]:
                            item["meta"]["ticket_conflito"] = resultado
                            item["meta"]["pedido"] = {"estado": "concluido"}
                            self.revisao += 1
                            self.salvar_rascunho()
                            self.exibir_erro(f"Ticket {resultado['ticket']} retornado, mas há {existente}. Revise.")
                        else:
                            item["dados"]["ticket"] = resultado["ticket"]
                            if existente != resultado["ticket"]:
                                registrar_evento(item, "Ticket vinculado", resultado["ticket"], fonte="extensao")
                            item["meta"]["link_movidesk"] = resultado["url"]
                            item["meta"]["pedido"] = {"estado": "concluido"}
                            item["meta"].pop("ticket_conflito", None)
                            if identificador == self.fila.ativo:
                                self.atualizando = True
                                try:
                                    self.vars["ticket"].set(resultado["ticket"])
                                finally:
                                    self.atualizando = False
                                self.atualizar_previews()
                            self.revisao += 1
                            self.salvar_rascunho()
                            self.informar(f"Ticket {resultado['ticket']} recebido.")
                elif tipo == "integracao_aviso" and not self.fechando:
                    if identificador in (None, self.fila.ativo):
                        self.informar(resultado)
                elif not self.fechando and self.operacao and identificador == self.operacao[0]:
                    if tipo == "ia_consumo":
                        self.consumo_ia.registrar(resultado)
                        self.resumo_tokens.set(self.consumo_ia.resumo(self.config))
                        self.tokens_extracao += resultado.get("total") or 0
                        continue
                    if tipo == "extracao_aviso":
                        self.avisos_extracao.append(resultado)
                        continue
                    if tipo == "extracao_metricas":
                        self.metricas_extracao = resultado
                        continue
                    if tipo == "ia_provedor":
                        self.provedor_ia = resultado
                        continue
                    if tipo == "progresso":
                        self.informar(resultado)
                        continue
                    if tipo == "imagem":
                        self.imagem_extracao = resultado
                        continue
                    self.operacao = None
                    self.progresso.stop()
                    self.progresso.pack_forget()
                    self.tempo.set("")
                    self.atualizar_controles()
                    if tipo == "erro":
                        self.exibir_erro(resultado)
                        if self.imagem_extracao is not None:
                            self.definir_imagem(self.imagem_extracao)
                            self.imagem_extracao = None
                            self.revisao += 1
                            self.salvar_rascunho()
                        if self.tokens_extracao:
                            meta = self.fila.obter()["meta"]
                            meta["tokens_reportados"] = meta.get("tokens_reportados", 0) + self.tokens_extracao
                            self.tokens_extracao = 0
                            self.revisao += 1
                            self.salvar_rascunho()
                    elif tipo == "captura_ok":
                        self.definir_imagem(resultado)
                        self.revisao += 1
                        self.salvar_rascunho()
                        self.informar("Print guardado.")
                    elif tipo == "ia_ok":
                        dados = self.obter_dados()
                        mudou = any(dados[c] and resultado.get(c) and dados[c] != resultado[c]
                                    for c in ("alerta", "servidor"))
                        if mudou:
                            self.guardar_incidente()
                            self.fila.novo()
                            dados = dict.fromkeys(CAMPOS, "")
                            self.atualizando = True
                            try:
                                self.modelo_comunicado.set("Abertura normal")
                                self.texto_atualizacao.set("")
                            finally:
                                self.atualizando = False
                            self.mostrar_opcoes_modelo()
                        dados.update({c: v for c, v in resultado.items() if v or not dados.get(c)})
                        self.definir_dados(dados)
                        if self.imagem_extracao is not None:
                            self.definir_imagem(self.imagem_extracao)
                            self.imagem_extracao = None
                        meta = self.fila.obter()["meta"]
                        meta["origem"] = self.provedor_ia
                        meta["metricas"] = self.metricas_extracao
                        meta["avisos_coleta"] = list(self.avisos_extracao)
                        meta["coletado_em"] = agora()
                        meta["tokens_reportados"] = meta.get("tokens_reportados", 0) + self.tokens_extracao
                        self.tokens_extracao = 0
                        self.revisao += 1
                        self.salvar_rascunho()
                        extra = " Novo incidente criado." if mudou else ""
                        avisos = f" {' | '.join(self.avisos_extracao)}" if self.avisos_extracao else ""
                        self.informar(f"Dados prontos via {self.provedor_ia}.{extra}{avisos}")
                    elif tipo == "conexao_ok":
                        self.informar("Zabbix conectado. Use Enviar ao NOCFlow no navegador.")
                    elif tipo == "movidesk_ok":
                        campos = self.fila.obter()["meta"].get("preenchimento", {})
                        pendentes = sum(s != "preenchido" for s in campos.values())
                        self.informar(f"Título e descrição preenchidos. Confira {pendentes} pendência(s) no formulário e salve."
                                      if pendentes else "Formulário preenchido. Revise e salve; o número volta sozinho.")
                    elif tipo == "retomar_ok":
                        self.informar("Formulário localizado no Edge. Revise e salve o ticket.")
                    elif tipo == "abrir_ticket_ok":
                        self.informar("Ticket vinculado aberto no Edge.")
                    elif tipo == "print_ok":
                        self.informar("✓ Print copiado (Ctrl+V no ticket).")
                    elif tipo == "imagem_email_ok":
                        self.informar("Recorte copiado. Cole no e-mail (Ctrl+V).")
        except queue.Empty:
            pass
        if self.importacoes_pendentes and not self.operacao and not self.carregando and not self.fechando:
            while self.importacoes_pendentes:
                self.aplicar_importacao(self.importacoes_pendentes.pop(0), selecionar=False)
        if self.operacao:
            self.tempo.set(f"{int(time.monotonic() - self.inicio_operacao)}s")
        if not self.carregando and not self.fechando and time.monotonic() - self.ultima_agenda > 5:
            self.ultima_agenda = time.monotonic()
            self.atualizar_agenda_resumo()
        if self.fechando and not self.movidesk.is_alive() and not self.rascunho.is_alive():
            self.progresso.stop()
            self.painel_fila.encerrar()
            self.root.destroy()
            return
        self.poll_after = self.root.after(100, self.processar_eventos)

    def fechar(self):
        if self.fechando:
            return
        self.fechando = True
        if self.central and not self.central.fechada:
            self.central.fechar()
        if self.imagem_after:
            self.root.after_cancel(self.imagem_after)
            self.imagem_after = None
        self.painel_fila.encerrar()
        self.salvar_rascunho()
        if self.carregando:
            self.encerrar_workers()
        self.atualizar_controles()
        self.informar("Salvando e encerrando…")

    def encerrar_workers(self):
        self.rascunho.comandos.put(None)
        self.movidesk.encerrar.set()

    def carregar_perfis_operacionais(self):
        self.perfis_operacionais = []
        self.erro_perfis = ""
        arquivo = self.fila.operacional.get("arquivo_perfis")
        if arquivo:
            try:
                self.perfis_operacionais = carregar_perfis(arquivo)
            except (ValueError, OSError) as exc:
                self.erro_perfis = f"Perfis indisponíveis: {exc}"

    def avaliar_perfil(self, dados):
        if self.fila.operacional.get("arquivo_perfis"):
            self.carregar_perfis_operacionais()
        if self.erro_perfis:
            return {"estado": "pendente", "mensagem": self.erro_perfis, "fontes": [], "resultado": {}}
        return avaliar_regras(self.perfis_operacionais, dados)

    def abrir_central(self):
        if self.carregando or self.fechando or self.operacao:
            return
        self.guardar_incidente()
        if self.central and not self.central.fechada:
            self.central.janela.lift()
            self.central.atualizar()
        else:
            from .central_operacional import CentralOperacional
            self.central = CentralOperacional(self)

    def atualizar_agenda_resumo(self):
        momento = instante()
        vencidos = sum(r.get("ativa", True) and instante(r["proxima"]) <= momento for r in self.fila.operacional.get("rotinas", []))
        vencidos += sum(bool(i["meta"].get("acompanhamento", {}).get("proxima"))
                        and not i["meta"].get("arquivado")
                        and instante(i["meta"]["acompanhamento"]["proxima"]["prazo"]) <= momento for i in self.fila.itens)
        self.btn_operacao.configure(text=f"Central · {vencidos} vencida(s)" if vencidos else "Central operacional")


def main():
    root = tk.Tk()
    try:
        config = carregar_config(diretorio_aplicacao())
        config.dados_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(config.dados_dir / "noc.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s"))
        logging.getLogger("noc").addHandler(handler)
        logging.getLogger("noc").setLevel(logging.INFO)
        try:
            preparar_extensao(config.diretorio)
        except Exception:
            # A extensão é opcional: uma configuração inválida não pode impedir o uso do aplicativo.
            logging.getLogger("noc").warning("Não foi possível atualizar a extensão do Edge.", exc_info=True)
        NOCFlow(root, config)
    except Exception as exc:
        messagebox.showerror("Não foi possível iniciar", str(exc), parent=root)
        root.destroy()
        return
    root.mainloop()
