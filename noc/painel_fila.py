"""Lista recolhível de atendimentos, com filtros locais e atualização incremental."""

import tkinter as tk
from tkinter import ttk

from .atendimento import ETAPAS, etapa_incidente, normalizar, severidade_padrao


class PainelFila(ttk.Frame):
    def __init__(self, pai, ao_selecionar, ao_proximo, ao_arquivar):
        super().__init__(pai, padding=(16, 0, 16, 6))
        self.ao_selecionar = ao_selecionar
        self.itens = []
        self.ativo = ""
        self.bloqueado = False
        self.filtro_after = None
        self.registros = {}
        self.busca = tk.StringVar(self)
        self.severidade = tk.StringVar(self, "Todas as severidades")
        self.ticket = tk.StringVar(self, "Todos os tickets")
        self.etapa = tk.StringVar(self, "Ativos")
        self.contadores = tk.StringVar(self)
        filtros = ttk.Frame(self)
        filtros.pack(fill="x", pady=(0, 4))
        ttk.Label(filtros, text="Buscar:").pack(side="left")
        ttk.Entry(filtros, textvariable=self.busca, width=18).pack(side="left", fill="x", expand=True, padx=(6, 8))
        linha_filtros = ttk.Frame(self)
        linha_filtros.pack(fill="x", pady=(0, 4))
        for variavel, valores, largura in (
            (self.severidade, ("Todas as severidades", "Desastre", "Alta", "Média", "Aviso", "Informação", "Não classificado", "Não informado"), 20),
            (self.ticket, ("Todos os tickets", "Com ticket", "Sem ticket"), 16),
            (self.etapa, ("Ativos", "Todos", *ETAPAS), 23),
        ):
            combo = ttk.Combobox(linha_filtros, textvariable=variavel, values=valores, state="readonly", width=largura)
            combo.pack(side="left", fill="x", expand=True, padx=(0, 4))
        for variavel in (self.busca, self.severidade, self.ticket, self.etapa):
            variavel.trace_add("write", self.agendar_filtro)

        area = ttk.Frame(self)
        area.pack(fill="both", expand=True)
        colunas = ("servidor", "alerta", "severidade", "horario", "etapa", "ticket")
        self.lista = ttk.Treeview(area, columns=colunas, show="headings", height=4, selectmode="browse")
        for coluna, rotulo, largura in zip(colunas, ("Servidor", "Alerta", "Severidade", "Horário", "Etapa", "Ticket"), (160, 220, 90, 140, 170, 75)):
            self.lista.heading(coluna, text=rotulo)
            self.lista.column(coluna, width=largura, minwidth=60, stretch=True)
        vertical = ttk.Scrollbar(area, orient="vertical", command=self.lista.yview)
        horizontal = ttk.Scrollbar(area, orient="horizontal", command=self.lista.xview)
        self.lista.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.lista.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        area.columnconfigure(0, weight=1)
        area.rowconfigure(0, weight=1)
        self.lista.bind("<<TreeviewSelect>>", self.selecionar)
        rodape = ttk.Frame(self)
        rodape.pack(fill="x", pady=(4, 0))
        ttk.Label(rodape, textvariable=self.contadores, style="Discreto.TLabel").pack(side="left", fill="x", expand=True)
        self.btn_arquivar = ttk.Button(rodape, text="Arquivar", command=ao_arquivar)
        self.btn_arquivar.pack(side="right")
        self.btn_proximo = ttk.Button(rodape, text="Próximo pendente", command=ao_proximo)
        self.btn_proximo.pack(side="right", padx=6)

    def agendar_filtro(self, *_):
        if self.filtro_after:
            self.after_cancel(self.filtro_after)
        self.filtro_after = self.after(180, self.filtrar)

    def atualizar(self, itens, ativo):
        self.itens, self.ativo = itens, ativo
        ativos = [i for i in itens if not i["meta"].get("arquivado")]
        aguardando = sum(etapa_incidente(i) == "Aguardando ticket" for i in ativos)
        prontos = sum(etapa_incidente(i) == "Pronto para comunicar" for i in ativos)
        self.contadores.set(f"{len(ativos)} ativos · {aguardando} aguardando · {prontos} prontos")
        atual = next((i for i in itens if i["id"] == ativo), None)
        self.btn_arquivar.configure(text="Reabrir" if atual and atual["meta"].get("arquivado") else "Arquivar")
        self.filtrar()

    def filtrar(self):
        if self.filtro_after:
            self.after_cancel(self.filtro_after)
            self.filtro_after = None
        existentes = {i["id"] for i in self.itens}
        for identificador in self.registros.keys() - existentes:
            self.lista.delete(identificador)
            del self.registros[identificador]
        busca = normalizar(self.busca.get().strip())
        visiveis = []
        for item in self.itens:
            d, meta = item["dados"], item["meta"]
            etapa, severidade = etapa_incidente(item), severidade_padrao(d.get("severidade", ""))
            valores = (d.get("servidor") or "Novo", d.get("alerta") or "Sem alerta", severidade,
                       d.get("horario", ""), etapa, d.get("ticket", ""))
            identificador = item["id"]
            if identificador not in self.registros:
                self.lista.insert("", "end", iid=identificador, values=valores)
            elif self.registros[identificador] != valores:
                self.lista.item(identificador, values=valores)
            self.registros[identificador] = valores
            mostrar = (not busca or busca in normalizar(" ".join(valores)))
            mostrar &= self.severidade.get() == "Todas as severidades" or severidade == self.severidade.get()
            mostrar &= self.ticket.get() == "Todos os tickets" or bool(d.get("ticket")) == (self.ticket.get() == "Com ticket")
            mostrar &= (self.etapa.get() == "Todos" or (self.etapa.get() == "Ativos" and not meta.get("arquivado")) or self.etapa.get() == etapa)
            if mostrar:
                visiveis.append(identificador)
            else:
                self.lista.detach(identificador)
        atuais = self.lista.get_children()
        for indice, identificador in enumerate(visiveis):
            if indice >= len(atuais) or atuais[indice] != identificador:
                self.lista.move(identificador, "", indice)
        if self.ativo in visiveis:
            if self.lista.selection() != (self.ativo,):
                self.lista.selection_set(self.ativo)
                self.lista.see(self.ativo)
        else:
            self.lista.selection_remove(self.lista.selection())

    def selecionar(self, _=None):
        selecao = self.lista.selection()
        if not self.bloqueado and selecao and selecao[0] != self.ativo:
            self.ao_selecionar(selecao[0])

    def bloquear(self, bloqueado):
        self.bloqueado = bloqueado
        for botao in (self.btn_arquivar, self.btn_proximo):
            botao.configure(state="disabled" if bloqueado else "normal")

    def encerrar(self):
        if self.filtro_after:
            self.after_cancel(self.filtro_after)
            self.filtro_after = None
