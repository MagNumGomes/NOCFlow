import tempfile
from pathlib import Path
import unittest

from noc.incidentes import FilaIncidentes
from noc.recorrencia import analisar_recorrencia, formatar_recorrencia
from noc.exportacao_pdf import exportar_pdf


def item(ticket, alerta="Falha de conexão", **dados):
    registro = FilaIncidentes().obter()
    registro["dados"].update(ticket=ticket, alerta=alerta, **dados)
    registro["meta"]["recebido_em"] = "2030-01-01T12:00:00+00:00"
    return registro


class RecorrenciaTests(unittest.TestCase):
    def test_conta_tickets_distintos_e_preserva_referencias(self):
        itens = [item("123"), item("00123", "  FALHA de conexao "), item("456"), item("")]
        r = analisar_recorrencia(itens)
        self.assertEqual(r["tickets_distintos"], 2)
        self.assertEqual(r["registros_analisados"], 3)
        self.assertEqual(r["sem_ticket"], 1)
        self.assertEqual(r["grupos_recorrentes"], 1)
        self.assertEqual(r["ranking"][0]["quantidade"], 2)
        self.assertEqual(r["ranking"][0]["percentual"], 100)
        texto = formatar_recorrencia(r)
        for registro in itens[:3]:
            self.assertIn(registro["id"], texto)

    def test_perfil_servico_e_ativo_controlam_agrupamento(self):
        itens = [item("1", perfil="A", servico="VPN", servidor="host-1"),
                 item("2", perfil="A", servico="VPN", servidor="host-2"),
                 item("3", perfil="B", servico="VPN"), item("4", perfil="A", servico="Banco")]
        self.assertEqual(len(analisar_recorrencia(itens)["ranking"]), 3)
        self.assertEqual(len(analisar_recorrencia(itens, por_ativo=True)["ranking"]), 4)
        self.assertEqual(analisar_recorrencia(itens)["ranking"][0]["quantidade"], 2)

    def test_periodo_respeita_fuso_limites_e_datas_ausentes(self):
        itens = [item("1"), item("2"), item("3"), item("4")]
        itens[1]["meta"]["recebido_em"] = "2030-01-01T13:00:00+00:00"
        itens[2]["meta"] = {}
        itens[3]["meta"]["arquivado"] = True
        r = analisar_recorrencia(itens, "2030-01-01T09:00:00-03:00", "2030-01-01T10:00:00-03:00")
        self.assertEqual(r["tickets_distintos"], 1)
        self.assertEqual(r["sem_data"], 1)
        self.assertEqual(r["fora_periodo"], 1)
        self.assertEqual(r["arquivados_excluidos"], 1)
        self.assertEqual(analisar_recorrencia(itens, incluir_arquivados=True)["tickets_distintos"], 4)
        with self.assertRaises(ValueError):
            analisar_recorrencia(itens, "2030-01-02T00:00:00Z", "2030-01-01T00:00:00Z")

    def test_ticket_em_grupos_diferentes_nao_infla_total(self):
        r = analisar_recorrencia([item("1", "CPU"), item("1", "Memória")])
        self.assertEqual(r["tickets_distintos"], 1)
        self.assertEqual(r["grupos_recorrentes"], 0)
        self.assertEqual(len(r["ranking"]), 2)

    def test_fila_vazia_nao_cria_problema_recorrente(self):
        r = analisar_recorrencia([FilaIncidentes().obter()])
        self.assertEqual(r["tickets_distintos"], 0)
        self.assertIn("Nenhum ticket", formatar_recorrencia(r))

    def test_pdf_pagina_relatorio_longo_com_texto_literal(self):
        from pypdf import PdfReader
        texto = "Auditoria de recorrência\nFalha <VPN> & conexão\n" + "\n".join(
            f"Ticket {i}: serviço indisponível; referência de auditoria." for i in range(180))
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "relatorio.pdf"
            exportar_pdf(caminho, texto)
            pdf = PdfReader(caminho)
            self.assertGreater(len(pdf.pages), 1)
            extraido = "\n".join(p.extract_text() for p in pdf.pages)
            self.assertIn("Falha <VPN> & conexão", extraido)
            self.assertIn("Ticket 179", extraido)
            self.assertIn("Página 2", extraido)
            with self.assertRaises(ValueError):
                exportar_pdf(caminho, " ")
            self.assertGreater(caminho.stat().st_size, 0)
