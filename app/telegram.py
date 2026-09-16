from __future__ import annotations

import httpx

from app.config import get_settings


class TelegramClient:
    def __init__(self) -> None:
        token = get_settings().telegram_bot_token
        self._base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, chat_id: int, text: str) -> None:
        response = httpx.post(f"{self._base_url}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
        response.raise_for_status()

    def is_chat_admin(self, chat_id: int, user_id: int) -> bool:
        response = httpx.post(
            f"{self._base_url}/getChatMember",
            json={"chat_id": chat_id, "user_id": user_id},
            timeout=10,
        )
        response.raise_for_status()
        status = response.json()["result"]["status"]
        return status in {"creator", "owner", "administrator"}
