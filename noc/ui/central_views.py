"""Construção das abas operacionais; callbacks são fornecidos pelo controlador."""

import tkinter as tk
from datetime import timedelta
from tkinter import ttk

import pyperclip

from ..historico_atendimento import instante
from .formularios import texto_area


def montar_acompanhamento(self):
    linha = ttk.Frame(self.painel)
    linha.pack(fill="x")
    for texto, funcao in (("Registrar ação", self.registrar_acao), ("Próxima ação", self.proxima_acao),
                          ("Avaliar regra", self.ver_regra), ("Referências", self.vincular_referencia),
                          ("Relacionar", self.relacionar), ("Concluir / reabrir", self.concluir)):
        ttk.Button(linha, text=texto, command=lambda f=funcao: self.executar(f)).pack(side="left", padx=2)
    linha2 = ttk.Frame(self.painel)
    linha2.pack(fill="x", pady=4)
    for texto, funcao in (("Carregar perfis privados", self.abrir_perfis), ("Exportar perfil de exemplo", self.exemplo_perfil),
                          ("Organizar relato com IA", self.ia_relato), ("Coordenação / pós-incidente", self.coordenacao)):
        ttk.Button(linha2, text=texto, command=lambda f=funcao: self.executar(f)).pack(side="left", padx=2)
    self.historico = texto_area(self.painel)


def montar_pendencias(self):
    ttk.Label(self.pendencias, text="Atendimentos ativos, ordenados pela próxima ação. Dê dois cliques para abrir.").pack(anchor="w", pady=6)
    self.lista_pendencias = ttk.Treeview(self.pendencias, columns=("resumo", "estado", "acao", "prazo"), show="headings")
    for coluna, titulo in (("resumo", "Atendimento"), ("estado", "Estado local"), ("acao", "Próxima ação"), ("prazo", "Prazo")):
        self.lista_pendencias.heading(coluna, text=titulo)
        self.lista_pendencias.column(coluna, width=200)
    self.lista_pendencias.tag_configure("vencida", background="#fef2f2", foreground="#991b1b")
    self.lista_pendencias.pack(fill="both", expand=True)
    self.lista_pendencias.bind("<Double-1>", lambda _: self.executar(self.abrir_pendencia))


def montar_agenda(self):
    botoes = ttk.Frame(self.agenda)
    botoes.pack(fill="x")
    for texto, funcao in (("Nova rotina", self.nova_rotina), ("Registrar execução", self.execucao),
                          ("Abrir dashboard", self.abrir_dashboard), ("Pausar / retomar", self.pausar_rotina)):
        ttk.Button(botoes, text=texto, command=lambda f=funcao: self.executar(f)).pack(side="left", padx=3)
    self.lista_agenda = ttk.Treeview(self.agenda, columns=("titulo", "prazo", "estado", "responsavel"), show="headings", height=8)
    for c, titulo in (("titulo", "Rotina"), ("prazo", "Próxima execução"), ("estado", "Estado"), ("responsavel", "Responsável")):
        self.lista_agenda.heading(c, text=titulo)
        self.lista_agenda.column(c, width=190)
    self.lista_agenda.tag_configure("vencida", background="#fef2f2", foreground="#991b1b")
    self.lista_agenda.tag_configure("pausada", foreground="#667085")
    self.lista_agenda.pack(fill="both", expand=True, pady=8)
    self.lista_agenda.bind("<<TreeviewSelect>>", lambda _: self.detalhar_rotina())
    self.detalhe_rotina = texto_area(self.agenda, altura=5)


def montar_conhecimento(self):
    topo = ttk.Frame(self.conhecimento)
    topo.pack(fill="x")
    ttk.Button(topo, text="Selecionar base privada", command=lambda: self.executar(self.abrir_base)).pack(side="left")
    ttk.Button(topo, text="Exportar índice modelo", command=lambda: self.executar(self.exemplo_base)).pack(side="left", padx=4)
    self.consulta = tk.StringVar(self.janela)
    ttk.Entry(topo, textvariable=self.consulta).pack(side="left", fill="x", expand=True, padx=6)
    ttk.Button(topo, text="Buscar localmente", command=lambda: self.executar(self.buscar_base)).pack(side="left")
    linha = ttk.Frame(self.conhecimento)
    linha.pack(fill="x", pady=4)
    ttk.Button(linha, text="Explicar fontes com IA", command=lambda: self.executar(self.ia_procedimentos)).pack(side="left")
    ttk.Button(linha, text="Revisar lacunas com IA", command=lambda: self.executar(lambda: self.ia_procedimentos(True))).pack(side="left", padx=6)
    ttk.Label(self.conhecimento, text="A busca usa o perfil e serviço do atendimento. A IA recebe apenas os trechos exibidos abaixo.", wraplength=850).pack(anchor="w")
    self.resultado_busca = texto_area(self.conhecimento)


def montar_relatorios(self):
    linha = ttk.Frame(self.relatorios)
    linha.pack(fill="x")
    self.inicio = tk.StringVar(self.janela, (instante() - timedelta(hours=12)).astimezone().isoformat(timespec="seconds"))
    self.fim = tk.StringVar(self.janela, instante().astimezone().isoformat(timespec="seconds"))
    for rotulo, var in (("De (inclusivo)", self.inicio), ("Até (exclusivo)", self.fim)):
        ttk.Label(linha, text=rotulo).pack(side="left")
        ttk.Entry(linha, textvariable=var, width=27).pack(side="left", padx=5)
    botoes = ttk.Frame(self.relatorios)
    botoes.pack(fill="x", pady=6)
    for texto, funcao in (("Diário", self.gerar_diario), ("Passagem", self.gerar_passagem), ("Indicadores", self.gerar_indicadores),
                          ("Exportar CSV", self.exportar), ("Resumo com IA", self.ia_resumo), ("Registrar recebimento", self.receber_turno)):
        ttk.Button(botoes, text=texto, command=lambda f=funcao: self.executar(f)).pack(side="left", padx=2)
    filtros = ttk.Frame(self.relatorios)
    filtros.pack(fill="x", pady=4)
    self.recorrencia_periodo = tk.BooleanVar(self.janela, False)
    self.recorrencia_arquivados = tk.BooleanVar(self.janela, False)
    self.recorrencia_ativo = tk.BooleanVar(self.janela, False)
    ttk.Button(filtros, text="Recorrência de tickets", command=lambda: self.executar(self.gerar_recorrencia)).pack(side="left")
    for rotulo, var in (("Usar período acima", self.recorrencia_periodo),
                        ("Incluir arquivados", self.recorrencia_arquivados), ("Separar por ativo", self.recorrencia_ativo)):
        ttk.Checkbutton(filtros, text=rotulo, variable=var).pack(side="left", padx=4)
    ttk.Label(self.relatorios, text="Recorrência: tickets distintos por perfil, serviço e resumo. Gere novamente após mudar os filtros.",
              wraplength=850).pack(anchor="w")
    self.relatorio = texto_area(self.relatorios)
    ttk.Button(self.relatorios, text="Exportar PDF do texto exibido", command=lambda: self.executar(self.exportar_relatorio_pdf)).pack(anchor="e", pady=3)
    ttk.Button(self.relatorios, text="Copiar texto exibido", command=lambda: self.executar(lambda: pyperclip.copy(self.relatorio.get("1.0", "end-1c")))).pack(anchor="e")
