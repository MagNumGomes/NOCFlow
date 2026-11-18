"""Redimensionamento assíncrono, descartando renderizações de zoom obsoletas."""

from PIL import Image, ImageTk

from .tarefas import TarefasUI


class ImagemCanvas:
    def __init__(self, janela, canvas, imagem, ao_renderizar=lambda: None):
        self.janela = janela
        self.canvas = canvas
        self.imagem = imagem
        self.ao_renderizar = ao_renderizar
        self.desejado = None
        self.exibido = None
        self.foto = None
        self.tarefas = TarefasUI(janela, self.erro)
        janela.bind("<Destroy>", self.destruido, add="+")

    def destruido(self, evento):
        if evento.widget is self.janela:
            self.tarefas.fechar()

    def erro(self, mensagem):
        self.canvas.create_text(10, 10, text=mensagem, fill="white", anchor="nw", width=300)

    def solicitar(self, tamanho):
        self.desejado = tamanho
        self.canvas.configure(scrollregion=(0, 0, *tamanho))
        if tamanho == self.exibido or self.tarefas.callbacks:
            return
        imagem = self.imagem
        def concluir(pronta):
            if tamanho == self.desejado:
                self.foto = ImageTk.PhotoImage(pronta, master=self.janela)
                self.canvas.delete("imagem")
                self.canvas.create_image(0, 0, anchor="nw", image=self.foto, tags="imagem")
                self.canvas.tag_lower("imagem")
                self.exibido = tamanho
                self.ao_renderizar()
            else:
                self.solicitar(self.desejado)
        self.tarefas.enviar("redimensionar", lambda: imagem.resize(tamanho, Image.Resampling.LANCZOS), concluir)
