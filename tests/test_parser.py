from datetime import date

from app.models import TransactionType
from app.services.parser import parse_transaction


def test_parses_indonesian_expense_amount() -> None:
    parsed = parse_transaction("Beli makan 25rb", date(2026, 9, 16))
    assert parsed is not None
    assert parsed.transaction_type == TransactionType.EXPENSE
    assert parsed.amount == 25_000


def test_parses_transfer_recipient() -> None:
    parsed = parse_transaction("Transfer 300rb ke Ibu", date(2026, 9, 16))
    assert parsed is not None
    assert parsed.transaction_type == TransactionType.TRANSFER
    assert parsed.recipient_name == "Ibu"
