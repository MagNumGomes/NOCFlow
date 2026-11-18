"""Construção visual da aba Comunicar; ações e estado pertencem ao controlador."""

import tkinter as tk
from tkinter import ttk

from ..atendimento import MODELOS
from .destinatarios_view import DestinatariosView


def montar_comunicacao(self):
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
    self.destinatarios = DestinatariosView(email, self)
    self.destinatarios.pack(fill="x", pady=(0, 6))
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
