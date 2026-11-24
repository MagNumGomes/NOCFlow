import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import patch

from noc.services.destinatarios import carregar, emails, salvar
from noc.ui.destinatarios_view import DestinatariosView
from noc.ui.tarefas import TarefasUI


class CadastroTests(unittest.TestCase):
    def test_separadores_duplicatas_e_validacao(self):
        self.assertEqual(emails("noc@empresa.com; NOC@empresa.com, suporte@empresa.com\nplantao@empresa.com"),
                         ["noc@empresa.com", "suporte@empresa.com", "plantao@empresa.com"])
        with self.assertRaises(ValueError):
            emails("email-invalido")

    def test_persistencia_e_falha_preservam_cadastro(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "destinatarios.json"
            self.assertEqual(carregar(caminho), [])
            empresas = [{"empresa": "Empresa Á", "para": ["noc@empresa.com"], "cc": ["gestao@empresa.com"]}]
            salvar(caminho, empresas)
            self.assertEqual(carregar(caminho), empresas)
            with patch("noc.infra.persistencia.os.fsync", side_effect=OSError("disco indisponível")), self.assertRaises(OSError):
                salvar(caminho, [])
            self.assertEqual(carregar(caminho), empresas)
            with self.assertRaises(ValueError):
                salvar(caminho, empresas * 2)
            self.assertEqual(carregar(caminho), empresas)
            caminho.write_text("inválido", encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar(caminho)
            self.assertEqual(caminho.read_text(encoding="utf-8"), "inválido")


class DestinatariosUITests(unittest.TestCase):
    def test_copia_listas_separadas_sem_alterar_clipboard_para_cc_vazio(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = tk.Tk()
            erros = []
            tarefas = TarefasUI(raiz, erros.append)
            try:
                caminho = Path(pasta) / "destinatarios.json"
                salvar(caminho, [{"empresa": "Cliente", "para": ["a@cliente.com", "b@cliente.com"], "cc": ["c@cliente.com"]}])
                app = SimpleNamespace(config=SimpleNamespace(dados_dir=Path(pasta)), tarefas=tarefas)
                view = DestinatariosView(raiz, app)
                view.pack()
                view.carregar()
                def aguardar():
                    fim = time.monotonic() + 3
                    while tarefas.callbacks and time.monotonic() < fim:
                        raiz.update()
                        time.sleep(0.01)
                    self.assertFalse(tarefas.callbacks)
                aguardar()
                view.nome.set("Cliente")
                view.atualizar()
                with patch("noc.ui.destinatarios_view.pyperclip.copy") as copiar:
                    view.copiar("para")
                    aguardar()
                    copiar.assert_called_with("a@cliente.com; b@cliente.com")
                    view.copiar("cc")
                    aguardar()
                    copiar.assert_called_with("c@cliente.com")
                    view.empresas[0]["cc"] = []
                    view.atualizar()
                    self.assertEqual(str(view.cc["state"]), "disabled")
                    view.copiar("cc")
                    self.assertEqual(copiar.call_count, 2)
                self.assertEqual(erros, [])
                # Testa sugestão automática por contexto do servidor/alerta.
                view.nome.set("")
                view.sugerir_por_contexto({"servidor": "Firewall Fortigate - Cliente", "alerta": "High error rate"})
                self.assertEqual(view.nome.get(), "Cliente")
                self.assertEqual(view.para.cget("text"), "Copiar Para (2)")
                # Exercita cadastro, edição e exclusão pelos controles reais.
                def botao(texto):
                    janela = view.dialogo
                    return next(b for frame in janela.winfo_children() if isinstance(frame, ttk.Frame)
                                for b in frame.winfo_children() if isinstance(b, ttk.Button) and b["text"] == texto)
                view.editar(nova=True)
                janela = view.dialogo
                next(w for w in janela.winfo_children() if isinstance(w, ttk.Entry)).insert(0, "Novo cliente")
                textos = [w for w in janela.winfo_children() if isinstance(w, tk.Text)]
                textos[0].insert("1.0", "novo@cliente.com; outro@cliente.com")
                botao("Salvar").invoke()
                aguardar()
                self.assertEqual(view.nome.get(), "Novo cliente")
                self.assertEqual(len(carregar(caminho)), 2)
                view.editar()
                textos = [w for w in view.dialogo.winfo_children() if isinstance(w, tk.Text)]
                textos[1].insert("1.0", "cc@cliente.com")
                botao("Salvar").invoke()
                aguardar()
                self.assertEqual(view.selecionada()["cc"], ["cc@cliente.com"])
                view.editar()
                with patch("noc.ui.destinatarios_view.messagebox.askyesno", return_value=True):
                    botao("Excluir").invoke()
                aguardar()
                self.assertEqual([e["empresa"] for e in carregar(caminho)], ["Cliente"])
            finally:
                tarefas.fechar()
                raiz.destroy()
