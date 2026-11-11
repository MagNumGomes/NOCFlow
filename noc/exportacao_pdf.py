"""Exportação local do relatório exibido, com paginação automática."""

import io
from pathlib import Path
from xml.sax.saxutils import escape


def exportar_pdf(caminho, texto):
    if not texto.strip():
        raise ValueError("Gere um relatório antes de exportar.")
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = io.BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm, title="Relatório NOCFlow", author="NOCFlow")
    estilo = ParagraphStyle("Corpo", fontName="Helvetica", fontSize=9, leading=13, spaceAfter=5,
                            splitLongWords=True)
    titulo = ParagraphStyle("Titulo", parent=estilo, fontName="Helvetica-Bold", fontSize=14, leading=18,
                            textColor=colors.HexColor("#17365d"), spaceAfter=12)
    elementos = []
    for n, linha in enumerate(texto.splitlines()):
        if linha.strip():
            elementos.append(Paragraph(escape(linha), titulo if n == 0 else estilo))
        else:
            elementos.append(Spacer(1, 5))

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, 12 * mm, "NOCFlow | Relatório local")
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    Path(caminho).write_bytes(buffer.getvalue())
