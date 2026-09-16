import json
from datetime import date

import httpx

from app.config import get_settings
from app.models import TransactionType
from app.services.parser import ParsedMessage


def parse_with_deepseek(text: str, today: date) -> ParsedMessage | None:
    settings = get_settings()
    if not settings.deepseek_api_key:
        return None
    response = httpx.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
        json={
            "model": settings.deepseek_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Extract one Indonesian financial transaction. Return JSON only: type (INCOME|EXPENSE|TRANSFER), amount integer rupiah, description string, recipient_name optional. Return {} if unclear."},
                {"role": "user", "content": text},
            ],
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()["choices"][0]["message"]["content"]
    data = json.loads(payload)
    if not data or not isinstance(data.get("amount"), int) or data["amount"] <= 0:
        return None
    return ParsedMessage(
        TransactionType(data["type"]),
        data["amount"],
        str(data.get("description") or "Transaksi"),
        today,
        60,
        data.get("recipient_name"),
    )
