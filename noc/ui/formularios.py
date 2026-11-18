"""Componentes de formulário sem dependências do estado operacional."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk


def texto_area(pai, altura=10, editavel=False):
    area = ttk.Frame(pai)
    area.pack(fill="both", expand=True, pady=4)
    texto = tk.Text(area, wrap="word", height=altura, width=1, font=("Segoe UI", 10), padx=8, pady=8)
    barra = ttk.Scrollbar(area, command=texto.yview)
    texto.configure(yscrollcommand=barra.set)
    barra.pack(side="right", fill="y")
    texto.pack(side="left", fill="both", expand=True)
    if not editavel:
        texto.configure(state="disabled")
    return texto


def mostrar_texto(widget, texto):
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", texto)
    widget.configure(state="disabled")


def dialogo(pai: tk.Misc, titulo: str, campos: list, confirmar: Callable, ao_salvar: Callable) -> tk.Toplevel:
    janela = tk.Toplevel(pai)
    janela.title(titulo)
    janela.transient(pai)
    janela.geometry("700x640" if len(campos) > 10 else "680x520")
    aviso = tk.StringVar(janela)
    ttk.Label(janela, textvariable=aviso, wraplength=640).pack(side="bottom", fill="x", padx=12, pady=4)
    botoes = ttk.Frame(janela, padding=8)
    botoes.pack(side="bottom", fill="x")
    canvas = tk.Canvas(janela, highlightthickness=0)
    barra = ttk.Scrollbar(janela, command=canvas.yview)
    canvas.configure(yscrollcommand=barra.set)
    barra.pack(side="right", fill="y")
    canvas.pack(fill="both", expand=True)
    corpo = ttk.Frame(canvas, padding=12)
    corpo.columnconfigure(1, weight=1)
    janela_canvas = canvas.create_window((0, 0), window=corpo, anchor="nw")
    corpo.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(janela_canvas, width=e.width))
    valores = {}
    for n, (chave, rotulo, valor, opcoes) in enumerate(campos):
        ttk.Label(corpo, text=rotulo, wraplength=180).grid(row=n, column=0, sticky="nw", padx=(0, 8), pady=4)
        if opcoes == "texto":
            entrada = tk.Text(corpo, name=chave, height=5, width=35, wrap="word", font=("Segoe UI", 10))
            entrada.insert("1.0", valor)
            valores[chave] = entrada
        else:
            variavel = tk.StringVar(janela, valor)
            valores[chave] = variavel
            entrada = ttk.Combobox(corpo, name=chave, textvariable=variavel, values=opcoes, state="readonly") if opcoes else ttk.Entry(corpo, name=chave, textvariable=variavel)
        entrada.grid(row=n, column=1, sticky="ew", pady=4)

    def salvar():
        try:
            dados = {c: (v.get("1.0", "end-1c") if isinstance(v, tk.Text) else v.get()).strip() for c, v in valores.items()}
            confirmar(dados)
            janela.destroy()
            ao_salvar()
        except (ValueError, OSError, KeyError, TypeError) as exc:
            aviso.set(str(exc))
    ttk.Button(botoes, text="Salvar", command=salvar).pack(side="right")
    ttk.Button(botoes, text="Cancelar", command=janela.destroy).pack(side="right", padx=8)
    return janela
