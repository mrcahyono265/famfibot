from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self) -> None:
        token = get_settings().telegram_bot_token
        self._base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, chat_id: int, text: str) -> None:
        try:
            response = httpx.post(f"{self._base_url}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.exception("sendMessage failed chat_id=%s status=%s body=%s", chat_id, e.response.status_code, e.response.text[:500])
            raise
        except Exception:
            logger.exception("sendMessage failed chat_id=%s", chat_id)
            raise

    def is_chat_admin(self, chat_id: int, user_id: int) -> bool:
        try:
            response = httpx.post(
                f"{self._base_url}/getChatMember",
                json={"chat_id": chat_id, "user_id": user_id},
                timeout=10,
            )
            response.raise_for_status()
            status = response.json()["result"]["status"]
            return status in {"creator", "owner", "administrator"}
        except httpx.HTTPStatusError as e:
            logger.exception("getChatMember failed chat_id=%s user_id=%s status=%s", chat_id, user_id, e.response.status_code)
            raise
        except Exception:
            logger.exception("getChatMember failed chat_id=%s user_id=%s", chat_id, user_id)
            raise
