"""Seleção de três trechos do print original para a comunicação por e-mail."""

import math
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk


CAMPOS_RECORTE = ("Host", "Trigger", "Severity")
CORES = ("#38bdf8", "#a78bfa", "#fb923c")


def caixa_original(inicio, fim, tamanho_original, tamanho_exibido):
    """Converte coordenadas do canvas com zoom em pixels do print, sem deformar."""
    largura, altura = tamanho_original
    exibida_largura, exibida_altura = tamanho_exibido
    x1, x2 = sorted((inicio[0], fim[0]))
    y1, y2 = sorted((inicio[1], fim[1]))
    caixa = (
        max(0, min(largura, math.floor(x1 * largura / exibida_largura))),
        max(0, min(altura, math.floor(y1 * altura / exibida_altura))),
        max(0, min(largura, math.ceil(x2 * largura / exibida_largura))),
        max(0, min(altura, math.ceil(y2 * altura / exibida_altura))),
    )
    if caixa[2] - caixa[0] < 2 or caixa[3] - caixa[1] < 2:
        raise ValueError("Arraste para marcar uma área com pelo menos 2 × 2 pixels.")
    return caixa


def montar_recortes(imagem, caixas):
    """Empilha Host, Trigger e Severity mantendo os pixels e cores dos recortes."""
    recortes = []
    for campo in CAMPOS_RECORTE:
        caixa = caixas.get(campo)
        if caixa is None or len(caixa) != 4:
            raise ValueError(f"Selecione a área de {campo} no print.")
        x1, y1, x2, y2 = caixa
        if not (0 <= x1 < x2 <= imagem.width and 0 <= y1 < y2 <= imagem.height):
            raise ValueError(f"O recorte de {campo} está fora do print. Selecione novamente.")
        recortes.append(imagem.crop(caixa).convert("RGB"))
    largura = max(recorte.width for recorte in recortes)
    altura = sum(recorte.height for recorte in recortes) + 12
    resultado = Image.new("RGB", (largura, altura), recortes[0].getpixel((0, 0)))
    y = 0
    for recorte in recortes:
        # Completa a largura com a cor da própria linha, sem esticar seu texto.
        resultado.paste(recorte.getpixel((0, 0)), (0, y, largura, y + recorte.height))
        resultado.paste(recorte, (0, y))
        y += recorte.height + 6
    return resultado


class EditorRecortes(tk.Toplevel):
    def __init__(self, root, imagem, caixas, ao_confirmar):
        super().__init__(root)
        self.title("Recortar evidência · Host, Trigger e Severity")
        self.transient(root)
        self.geometry(f"{min(1180, self.winfo_screenwidth() - 80)}x{min(760, self.winfo_screenheight() - 100)}")
        self.minsize(720, 450)
        self.imagem = imagem
        self.caixas = dict(caixas)
        self.ao_confirmar = ao_confirmar
        self.inicio = None
        self.campo = tk.StringVar(self, next((c for c in CAMPOS_RECORTE if c not in caixas), "Host"))
        self.mensagem = tk.StringVar(self)
        self.resumo = tk.StringVar(self)
        self.zoom = tk.StringVar(self, "Ajustar")

        topo = ttk.Frame(self, padding=12)
        topo.pack(fill="x")
        ttk.Label(topo, text="Arraste no print para selecionar apenas o conteúdo de cada campo. A ordem final será Host → Trigger → Severity.", wraplength=900).pack(anchor="w")
        opcoes = ttk.Frame(topo)
        opcoes.pack(fill="x", pady=6)
        for campo in CAMPOS_RECORTE:
            ttk.Radiobutton(opcoes, text=campo, value=campo, variable=self.campo, command=self.orientar).pack(side="left", padx=(0, 12))
        ttk.Label(opcoes, text="Zoom:").pack(side="left")
        zoom = ttk.Combobox(opcoes, textvariable=self.zoom, values=("Ajustar", "100%", "200%"), width=8, state="readonly")
        zoom.pack(side="left", padx=6)
        zoom.bind("<<ComboboxSelected>>", lambda _: self.renderizar())
        ttk.Button(opcoes, text="Limpar seleção", command=self.limpar).pack(side="left")
        ttk.Label(topo, textvariable=self.mensagem, wraplength=900).pack(anchor="w")

        rodape = ttk.Frame(self, padding=12)
        rodape.pack(side="bottom", fill="x")
        self.btn_copiar = ttk.Button(rodape, text="Salvar recortes", command=self.confirmar)
        self.btn_copiar.pack(side="right")
        ttk.Button(rodape, text="Cancelar", command=self.destroy).pack(side="right", padx=8)
        ttk.Label(rodape, text="O print completo permanece guardado.").pack(side="left")

        area = ttk.Frame(self, padding=(12, 0, 12, 0))
        area.pack(fill="both", expand=True)
        previa = ttk.LabelFrame(area, text="Prévia da imagem final", padding=10, width=270)
        previa.pack(side="right", fill="y", padx=(12, 0))
        previa.pack_propagate(False)
        self.preview = ttk.Label(previa, text="Marque os três campos para montar a imagem.", wraplength=240)
        self.preview.pack(anchor="nw")
        ttk.Label(previa, textvariable=self.resumo, wraplength=240).pack(anchor="nw", pady=12)
        ttk.Label(previa, text="Para refazer um trecho, escolha o campo acima e arraste outra vez. Use o zoom e as barras de rolagem para recortes precisos.", wraplength=240).pack(anchor="nw")

        origem = ttk.Frame(area)
        origem.pack(fill="both", expand=True)
        origem.rowconfigure(0, weight=1)
        origem.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(origem, background="#20242b", highlightthickness=0, cursor="crosshair")
        vertical = ttk.Scrollbar(origem, orient="vertical", command=self.canvas.yview)
        horizontal = ttk.Scrollbar(origem, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas.bind("<ButtonPress-1>", self.iniciar)
        self.canvas.bind("<B1-Motion>", self.arrastar)
        self.canvas.bind("<ButtonRelease-1>", self.terminar)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-int(e.delta / 120), "units"))
        self.canvas.bind("<Configure>", lambda _: self.renderizar() if self.zoom.get() == "Ajustar" else None)
        self.bind("<Escape>", lambda _: self.destroy())
        self.update_idletasks()
        self.renderizar()
        self.atualizar_previa()
        self.orientar()
        self.grab_set()

    def orientar(self):
        self.mensagem.set(f"Selecione {self.campo.get()}: clique e arraste do início ao fim do trecho desejado.")

    def renderizar(self):
        self.inicio = None
        if self.zoom.get() == "Ajustar":
            fator = min(1, max(1, self.canvas.winfo_width()) / self.imagem.width,
                        max(1, self.canvas.winfo_height()) / self.imagem.height)
        else:
            fator = int(self.zoom.get().rstrip("%")) / 100
        self.tamanho_exibido = (max(1, round(self.imagem.width * fator)), max(1, round(self.imagem.height * fator)))
        self.foto = ImageTk.PhotoImage(self.imagem.resize(self.tamanho_exibido, Image.Resampling.LANCZOS), master=self)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.foto)
        self.canvas.configure(scrollregion=(0, 0, *self.tamanho_exibido))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.desenhar_caixas()

    def desenhar_caixas(self):
        self.canvas.delete("selecao")
        sx, sy = self.tamanho_exibido[0] / self.imagem.width, self.tamanho_exibido[1] / self.imagem.height
        for campo, cor in zip(CAMPOS_RECORTE, CORES):
            if campo in self.caixas:
                x1, y1, x2, y2 = self.caixas[campo]
                self.canvas.create_rectangle(x1 * sx, y1 * sy, x2 * sx, y2 * sy, outline=cor, width=2, tags="selecao")
                self.canvas.create_text(x1 * sx + 3, y1 * sy + 2, text=campo, anchor="nw", fill=cor, tags="selecao")

    def ponto(self, evento):
        return (max(0, min(self.tamanho_exibido[0], self.canvas.canvasx(evento.x))),
                max(0, min(self.tamanho_exibido[1], self.canvas.canvasy(evento.y))))

    def iniciar(self, evento):
        self.inicio = self.ponto(evento)
        self.canvas.delete("arraste")

    def arrastar(self, evento):
        if self.inicio is not None:
            self.canvas.delete("arraste")
            self.canvas.create_rectangle(*self.inicio, *self.ponto(evento), outline="white", width=2, dash=(4, 2), tags="arraste")

    def terminar(self, evento):
        if self.inicio is None:
            return
        try:
            caixa = caixa_original(self.inicio, self.ponto(evento), self.imagem.size, self.tamanho_exibido)
        except ValueError as exc:
            self.mensagem.set(str(exc))
        else:
            self.caixas[self.campo.get()] = caixa
            self.campo.set(next((c for c in CAMPOS_RECORTE if c not in self.caixas), self.campo.get()))
            self.desenhar_caixas()
            self.atualizar_previa()
            if len(self.caixas) == 3:
                self.mensagem.set("Três campos selecionados. Confira a prévia e clique em Salvar recortes.")
            else:
                self.orientar()
        finally:
            self.inicio = None
            self.canvas.delete("arraste")

    def limpar(self):
        self.caixas.pop(self.campo.get(), None)
        self.desenhar_caixas()
        self.atualizar_previa()
        self.orientar()

    def atualizar_previa(self):
        linhas = [f"{'✓' if c in self.caixas else '○'} {c}" for c in CAMPOS_RECORTE]
        completa = all(c in self.caixas for c in CAMPOS_RECORTE)
        self.btn_copiar.configure(state="normal" if completa else "disabled")
        if completa:
            imagem = montar_recortes(self.imagem, self.caixas)
            linhas.append(f"\nImagem final: {imagem.width} × {imagem.height} px\nPrévia reduzida; cópia em resolução original.")
            imagem.thumbnail((240, 280))
            self.foto_previa = ImageTk.PhotoImage(imagem, master=self)
            self.preview.configure(image=self.foto_previa, text="")
        else:
            self.preview.configure(image="", text="Marque os três campos para montar a imagem.")
            self.foto_previa = None
        self.resumo.set("\n".join(linhas))

    def confirmar(self):
        if all(c in self.caixas for c in CAMPOS_RECORTE):
            caixas = dict(self.caixas)
            self.destroy()
            self.ao_confirmar(caixas)


class VisualizadorImagem(tk.Toplevel):
    """Ampliação criada somente quando solicitada pelo operador."""

    def __init__(self, root, imagem):
        super().__init__(root)
        self.title("Evidência do incidente")
        self.transient(root)
        self.geometry(f"{min(1050, self.winfo_screenwidth() - 80)}x{min(700, self.winfo_screenheight() - 100)}")
        self.imagem = imagem
        self.zoom = tk.StringVar(self, "Ajustar")
        topo = ttk.Frame(self, padding=10)
        topo.pack(fill="x")
        ttk.Label(topo, text=f"{imagem.width} × {imagem.height} px · Zoom:").pack(side="left")
        combo = ttk.Combobox(topo, textvariable=self.zoom, values=("Ajustar", "100%", "200%"), state="readonly", width=10)
        combo.pack(side="left", padx=8)
        combo.bind("<<ComboboxSelected>>", self.renderizar)
        area = ttk.Frame(self)
        area.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(area, background="#202630", highlightthickness=0)
        vertical = ttk.Scrollbar(area, orient="vertical", command=self.canvas.yview)
        horizontal = ttk.Scrollbar(area, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-int(e.delta / 120), "units"))
        self.bind("<Escape>", lambda _: self.destroy())
        self.update_idletasks()
        self.renderizar()

    def renderizar(self, _=None):
        fator = min(1, max(1, self.canvas.winfo_width()) / self.imagem.width,
                    max(1, self.canvas.winfo_height()) / self.imagem.height) if self.zoom.get() == "Ajustar" else int(self.zoom.get()[:-1]) / 100
        tamanho = tuple(max(1, round(d * fator)) for d in self.imagem.size)
        self.foto = ImageTk.PhotoImage(self.imagem.resize(tamanho, Image.Resampling.LANCZOS), master=self)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.foto)
        self.canvas.configure(scrollregion=(0, 0, *tamanho))
