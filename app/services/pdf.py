from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

from app.models import Transaction, TransactionType


def build_report_pdf(workspace_name: str, transactions: list[Transaction]) -> bytes:
    income = sum(item.amount for item in transactions if item.transaction_type == TransactionType.INCOME)
    expense = sum(item.amount for item in transactions if item.transaction_type == TransactionType.EXPENSE)
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, title=f"Laporan {workspace_name}")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Laporan Keuangan {workspace_name}", styles["Title"]),
        Paragraph(f"Pemasukan: Rp{income:,}".replace(",", "."), styles["Normal"]),
        Paragraph(f"Pengeluaran: Rp{expense:,}".replace(",", "."), styles["Normal"]),
        Paragraph(f"Arus bersih: Rp{income - expense:,}".replace(",", "."), styles["Normal"]),
        PageBreak(),
    ]
    rows = [["Tanggal", "Masuk", "Keluar", "Keterangan", "Catatan"]]
    for item in transactions:
        rows.append([
            item.transaction_date.isoformat(),
            f"Rp{item.amount:,}".replace(",", ".") if item.transaction_type == TransactionType.INCOME else "",
            f"Rp{item.amount:,}".replace(",", ".") if item.transaction_type == TransactionType.EXPENSE else "",
            item.description,
            item.note or "",
        ])
    table = Table(rows, repeatRows=1, colWidths=[75, 80, 80, 150, 150])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    document.build(story)
    return output.getvalue()
