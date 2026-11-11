from types import SimpleNamespace
import tkinter as tk
import unittest

from PIL import Image

from noc.comunicados import gerar_assunto_email
from noc.recortes_email import EditorRecortes, caixa_original, montar_recortes


class RecortesTests(unittest.TestCase):
    def test_assunto_preserva_template_e_remove_quebras_de_linha(self):
        dados = {"ticket": "915142", "alerta": 'VPN CURITIBA-T2: Phase 2 "CURITIBA-T2" Status is Down', "servidor": "Firewall Fortigate FG120 (proxy1) - Manserv"}
        self.assertEqual(gerar_assunto_email(dados), f"915142 - {dados['alerta']} - {dados['servidor']}")
        dados["alerta"] = "CPU\r\n alta\t"
        self.assertNotIn("\n", gerar_assunto_email(dados))
        self.assertIn("CPU alta", gerar_assunto_email(dados))

    def test_conversao_com_zoom_arraste_invertido_e_limites(self):
        self.assertEqual(caixa_original((80, 30), (20, 10), (1000, 500), (500, 250)), (40, 20, 160, 60))
        self.assertEqual(caixa_original((-20, -10), (3000, 2000), (1000, 500), (2000, 1000)), (0, 0, 1000, 500))
        with self.assertRaises(ValueError):
            caixa_original((10, 10), (10, 10), (1000, 500), (500, 250))

    def test_montagem_preserva_pixels_e_omite_trechos_nao_selecionados(self):
        imagem = Image.new("RGB", (80, 80), "magenta")
        caixas = {"Severity": (30, 50, 60, 60), "Host": (10, 10, 30, 20), "Trigger": (10, 30, 50, 40)}
        for campo, cor in (("Host", "blue"), ("Trigger", "green"), ("Severity", "orange")):
            imagem.paste(cor, caixas[campo])
        imagem.putpixel((12, 12), (1, 2, 3))
        original = imagem.tobytes()
        resultado = montar_recortes(imagem, caixas)
        self.assertEqual(resultado.size, (40, 42))
        self.assertEqual(resultado.getpixel((2, 2)), (1, 2, 3))
        self.assertEqual(resultado.getpixel((0, 16)), (0, 128, 0))
        self.assertEqual(resultado.getpixel((0, 32)), (255, 165, 0))
        self.assertNotIn((255, 0, 255), {cor for _, cor in resultado.getcolors(resultado.width * resultado.height)})
        self.assertEqual(imagem.tobytes(), original)
        with self.assertRaisesRegex(ValueError, "Severity"):
            montar_recortes(imagem, {"Host": caixas["Host"], "Trigger": caixas["Trigger"]})
        with self.assertRaisesRegex(ValueError, "fora do print"):
            montar_recortes(imagem, dict(caixas, Host=(-1, 0, 10, 10)))


class EditorTests(unittest.TestCase):
    def test_ajuste_inicial_usa_dimensoes_da_janela_apos_exibicao(self):
        root = tk.Tk()
        try:
            root.update()
            editor = EditorRecortes(root, Image.new("RGB", (1100, 440)), {}, lambda _: None)
            root.update()
            largura, altura = editor.tamanho_exibido
            self.assertGreater(largura, 100)
            self.assertGreater(altura, 40)
            self.assertLessEqual(largura, editor.canvas.winfo_width())
            self.assertLessEqual(altura, editor.canvas.winfo_height())
        finally:
            root.destroy()

    def test_selecionar_com_zoom_e_rolagem_refazer_e_confirmar(self):
        root = tk.Tk()
        root.withdraw()
        recebidas = []
        editor = EditorRecortes(root, Image.new("RGB", (1600, 900), "gray"), {}, recebidas.append)
        try:
            editor.zoom.set("200%")
            editor.renderizar()
            root.update()
            editor.canvas.xview_moveto(0.2)
            editor.canvas.yview_moveto(0.2)
            inicio, fim = SimpleNamespace(x=10, y=10), SimpleNamespace(x=210, y=50)
            esperado = caixa_original(editor.ponto(inicio), editor.ponto(fim), editor.imagem.size, editor.tamanho_exibido)
            self.assertGreater(esperado[0], 0)
            self.assertEqual(str(editor.btn_copiar["state"]), "disabled")
            for campo in ("Host", "Trigger", "Severity"):
                self.assertEqual(editor.campo.get(), campo)
                editor.iniciar(inicio)
                editor.arrastar(fim)
                editor.terminar(fim)
                self.assertEqual(editor.caixas[campo], esperado)
            self.assertEqual(str(editor.btn_copiar["state"]), "normal")
            editor.campo.set("Host")
            editor.limpar()
            self.assertEqual(str(editor.btn_copiar["state"]), "disabled")
            editor.iniciar(inicio)
            editor.terminar(fim)
            editor.confirmar()
            self.assertEqual(len(recebidas), 1)
            self.assertEqual(recebidas[0]["Host"], esperado)
        finally:
            root.destroy()

    def test_cancelar_nao_altera_selecoes_anteriores(self):
        root = tk.Tk()
        root.withdraw()
        caixas = {"Host": (0, 0, 20, 20)}
        recebidas = []
        try:
            editor = EditorRecortes(root, Image.new("RGB", (100, 100)), caixas, recebidas.append)
            editor.campo.set("Host")
            editor.limpar()
            editor.destroy()
            self.assertEqual(caixas, {"Host": (0, 0, 20, 20)})
            self.assertEqual(recebidas, [])
        finally:
            root.destroy()
