from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.models import TransactionType

AMOUNT = re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(jt|juta|rb|ribu|k)?\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedMessage:
    transaction_type: TransactionType
    amount: int
    description: str
    transaction_date: date
    confidence: int
    recipient_name: str | None = None


def parse_transaction(text: str, today: date) -> ParsedMessage | None:
    normalized = " ".join(text.lower().split())
    amount = _amount(normalized)
    if amount is None:
        return None
    transaction_date = today - timedelta(days=1) if "kemarin" in normalized else today
    if normalized.startswith(("transfer ", "kirim ")):
        recipient = re.search(r"(?:ke|kepada)\s+(.+)$", normalized)
        return ParsedMessage(TransactionType.TRANSFER, amount, "Transfer", transaction_date, 85, recipient.group(1).title() if recipient else None)
    if any(word in normalized for word in ("gaji", "masuk", "dapat", "terima", "dari ayah", "dari ibu")):
        return ParsedMessage(TransactionType.INCOME, amount, _description(normalized, "Pemasukan"), transaction_date, 90)
    if any(word in normalized for word in ("beli", "bayar", "makan", "bensin", "belanja", "habis")):
        return ParsedMessage(TransactionType.EXPENSE, amount, _description(normalized, "Pengeluaran"), transaction_date, 90)
    return None


def _amount(text: str) -> int | None:
    match = AMOUNT.search(text)
    if match is None:
        return None
    value = float(match.group(1).replace(",", "."))
    multiplier = {"jt": 1_000_000, "juta": 1_000_000, "rb": 1_000, "ribu": 1_000, "k": 1_000}.get(match.group(2), 1)
    return int(value * multiplier)


def _description(text: str, fallback: str) -> str:
    cleaned = AMOUNT.sub("", text).strip(" -")
    return cleaned.title() if cleaned else fallback
