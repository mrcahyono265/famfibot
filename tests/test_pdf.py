from datetime import date

from app.models import Transaction, TransactionType
from app.services.pdf import build_report_pdf


def test_pdf_report_is_generated() -> None:
    report = build_report_pdf(
        "Keluarga Budi",
        [
            Transaction(transaction_type=TransactionType.INCOME, amount=1_000_000, description="Gaji", transaction_date=date(2026, 9, 1), family_id=None, created_by_user_id=None),
            Transaction(transaction_type=TransactionType.EXPENSE, amount=25_000, description="Makan", transaction_date=date(2026, 9, 2), family_id=None, created_by_user_id=None),
        ],
    )
    assert report.startswith(b"%PDF")
