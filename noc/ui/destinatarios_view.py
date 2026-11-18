"""Cadastro e cópia de listas de e-mail, independente do incidente ativo."""

import tkinter as tk
from tkinter import messagebox, ttk

import pyperclip

from ..services.destinatarios import carregar, emails, salvar, validar


class DestinatariosView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.caminho = app.config.dados_dir / "destinatarios.json"
        self.empresas = []
        self.nome = tk.StringVar(self)
        self.resumo = tk.StringVar(self, "Carregando destinatários…")
        self.pronto = False
        self.ocupado = False
        self.dialogo = None
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="Empresa").grid(row=0, column=0, padx=(0, 6))
        self.seletor = ttk.Combobox(self, textvariable=self.nome, state="readonly", width=20)
        self.seletor.grid(row=0, column=1, sticky="ew")
        self.seletor.bind("<<ComboboxSelected>>", lambda _: self.atualizar())
        self.nova = ttk.Button(self, text="Cadastrar", command=lambda: self.editar(nova=True))
        self.nova.grid(row=0, column=2, padx=(6, 0))
        self.edicao = ttk.Button(self, text="Editar", command=self.editar)
        self.edicao.grid(row=0, column=3, padx=(6, 0))
        linha = ttk.Frame(self)
        linha.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(4, 6))
        self.para = ttk.Button(linha, text="Copiar Para", command=lambda: self.copiar("para"))
        self.para.pack(side="left")
        self.cc = ttk.Button(linha, text="Copiar Cc", command=lambda: self.copiar("cc"))
        self.cc.pack(side="left", padx=6)
        ttk.Label(linha, textvariable=self.resumo, style="Discreto.TLabel").pack(side="left")
        self.atualizar()

    def carregar(self):
        caminho = self.caminho
        def trabalhar():
            try:
                return carregar(caminho), ""
            except (OSError, ValueError) as exc:
                return None, str(exc)
        def concluir(resultado):
            empresas, erro = resultado
            if erro:
                self.resumo.set("Falha ao carregar cadastro")
                self.app.exibir_erro(erro)
                return
            self.empresas = empresas
            self.pronto = True
            self.atualizar()
        self.app.tarefas.enviar("destinatarios_carga", trabalhar, concluir)

    def selecionada(self):
        return next((item for item in self.empresas if item["empresa"] == self.nome.get()), None)

    def atualizar(self):
        item = self.selecionada()
        self.seletor.configure(values=[e["empresa"] for e in self.empresas])
        livre = self.pronto and not self.ocupado
        self.nova.configure(state="normal" if livre else "disabled")
        self.edicao.configure(state="normal" if livre and item else "disabled")
        for campo, botao in (("para", self.para), ("cc", self.cc)):
            botao.configure(state="normal" if livre and item and item[campo] else "disabled")
        if self.pronto:
            self.resumo.set(f'{len(item["para"])} Para · {len(item["cc"])} Cc' if item else "Selecione ou cadastre uma empresa")

    def copiar(self, campo):
        item = self.selecionada()
        if not item or not item[campo]:
            return
        texto = "; ".join(item[campo])
        def concluir(_):
            self.resumo.set(f'{"Para" if campo == "para" else "Cc"} copiado')
        self.app.tarefas.enviar("destinatarios_copia", lambda: pyperclip.copy(texto), concluir)

    def editar(self, nova=False):
        if self.dialogo and self.dialogo.winfo_exists():
            self.dialogo.lift()
            return
        original = None if nova else self.selecionada()
        if not nova and not original:
            return
        janela = self.dialogo = tk.Toplevel(self)
        janela.title("Destinatários de e-mail")
        janela.transient(self.winfo_toplevel())
        janela.columnconfigure(1, weight=1)
        nome = tk.StringVar(janela, original["empresa"] if original else "")
        ttk.Label(janela, text="Empresa").grid(row=0, column=0, padx=10, pady=10)
        entrada = ttk.Entry(janela, textvariable=nome, width=45)
        entrada.grid(row=0, column=1, sticky="ew", padx=10)
        campos = {}
        for linha, (campo, rotulo) in enumerate((("para", "Para"), ("cc", "Cc (com cópia)")), 1):
            ttk.Label(janela, text=rotulo).grid(row=linha, column=0, padx=10, sticky="nw")
            texto = campos[campo] = tk.Text(janela, height=4, width=45, wrap="word")
            texto.grid(row=linha, column=1, sticky="ew", padx=10, pady=5)
            texto.insert("1.0", "; ".join(original[campo]) if original else "")
        ttk.Label(janela, text="Separe os e-mails por ;, vírgula ou quebra de linha.").grid(row=3, column=0, columnspan=2, padx=10)
        mensagem = tk.StringVar(janela)
        ttk.Label(janela, textvariable=mensagem, wraplength=450).grid(row=4, column=0, columnspan=2, padx=10)
        botoes = ttk.Frame(janela)
        botoes.grid(row=5, column=0, columnspan=2, pady=10)

        def fechar():
            if not self.ocupado:
                janela.destroy()

        def gravar(excluir=False):
            if self.ocupado:
                return
            try:
                novos = [dict(e) for e in self.empresas if e is not original]
                selecionado = ""
                if not excluir:
                    item = {"empresa": nome.get(), **{c: emails(t.get("1.0", "end")) for c, t in campos.items()}}
                    novos.append(item)
                    selecionado = nome.get().strip()
                novos = validar(novos)
            except ValueError as exc:
                mensagem.set(str(exc))
                return
            if excluir and not messagebox.askyesno("Excluir empresa", "Excluir este cadastro de destinatários?", parent=janela):
                return
            caminho = self.caminho
            def trabalhar():
                try:
                    return salvar(caminho, novos), ""
                except (OSError, ValueError) as exc:
                    return None, str(exc)
            def concluir(resultado):
                self.ocupado = False
                empresas, erro = resultado
                if erro:
                    mensagem.set(f"Não foi possível salvar: {erro}")
                else:
                    self.empresas = empresas
                    self.nome.set(selecionado)
                    janela.destroy()
                self.atualizar()
            if self.app.tarefas.enviar("destinatarios_salvar", trabalhar, concluir):
                self.ocupado = True
                mensagem.set("Salvando…")
                self.atualizar()
            else:
                mensagem.set("Aguarde as tarefas em andamento e tente novamente.")

        ttk.Button(botoes, text="Salvar", command=gravar).pack(side="left", padx=4)
        if original:
            ttk.Button(botoes, text="Excluir", command=lambda: gravar(True)).pack(side="left", padx=4)
        ttk.Button(botoes, text="Cancelar", command=fechar).pack(side="left", padx=4)
        janela.protocol("WM_DELETE_WINDOW", fechar)
        entrada.focus_set()
