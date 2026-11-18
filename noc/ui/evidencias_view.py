"""Controles visuais de evidências; processamento de pixels é feito nos workers."""

from tkinter import ttk


def montar_evidencias(self):
    self.area_recortes = ttk.Frame(self.pagina_evidencias)
    self.area_recortes.pack(fill="x", pady=(0, 6))
    self.btn_adicionar_print = ttk.Button(self.area_recortes, text="Adicionar print", command=self.capturar_print)
    self.btn_adicionar_print.pack(side="left", padx=(0, 6))
    self.btn_ampliar = ttk.Button(self.area_recortes, text="Ampliar", command=self.ampliar_imagem)
    self.btn_ampliar.pack(side="left", padx=(0, 6))
    self.btn_recortar_email = ttk.Button(self.area_recortes, text="Recortar print", command=self.recortar_imagem_email)
    self.btn_recortar_email.pack(side="left")
    copia_imagem = ttk.Frame(self.pagina_evidencias)
    copia_imagem.pack(fill="x", pady=(0, 6))
    self.btn_print = ttk.Button(copia_imagem, text="Copiar print", command=self.copiar_print)
    self.btn_print.pack(side="left", padx=(0, 6))
    self.btn_imagem_email = ttk.Button(copia_imagem, text="Copiar recorte", command=self.copiar_imagem_email)
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
