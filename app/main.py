from __future__ import annotations

import logging
import secrets

from fastapi import FastAPI, HTTPException, Request

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
from pydantic import BaseModel, Field
from app.config import get_settings
from app.database import SessionLocal
from app.services.setup import create_workspace_for_group, find_or_create_user
from app.telegram import TelegramClient


class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None

    @property
    def display_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)


class TelegramChat(BaseModel):
    id: int
    type: str
    title: str | None = None


class TelegramMessage(BaseModel):
    message_id: int
    from_: TelegramUser | None = Field(default=None, alias="from")
    chat: TelegramChat
    text: str | None = None

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None


app = FastAPI(title="Family Finance Bot", version="0.1.0", docs_url=None, redoc_url=None)
telegram = TelegramClient()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhooks/telegram")
async def telegram_webhook(request: Request) -> dict[str, bool]:
    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secrets.compare_digest(supplied_secret, get_settings().telegram_webhook_secret):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    body = await request.json()
    logger.info("webhook raw body=%s headers_secret=%s", str(body)[:800], supplied_secret[:8] + "***")
    update = TelegramUpdate.model_validate(body)
    message = update.message
    if message is None or message.text is None or message.from_ is None:
        logger.info("webhook early return message=%s text=%s from=%s", message, getattr(message, 'text', None) if message else None, getattr(message, 'from_', None) if message else None)
        return {"ok": True}
    logger.info("webhook received chat_id=%s type=%s text=%r from_id=%s", message.chat.id, message.chat.type, message.text, message.from_.id if message.from_ else None)

    try:
        if message.text.split(maxsplit=1)[0].lower().split("@", 1)[0] == "/setup":
            _handle_setup(message)
        elif message.text.split(maxsplit=1)[0].lower().split("@", 1)[0] == "/start":
            telegram.send_message(message.chat.id, "Selamat datang. Tambahkan saya ke group keuangan lalu jalankan /setup.")
    except Exception:
        logger.exception("webhook handler failed chat_id=%s text=%s", message.chat.id, message.text[:100])
        return {"ok": True}
    return {"ok": True}


def _handle_setup(message: TelegramMessage) -> None:
    sender = message.from_
    if sender is None:
        return
    if message.chat.type not in {"group", "supergroup"}:
        try:
            telegram.send_message(message.chat.id, "/setup hanya dapat digunakan di group Telegram.")
        except Exception:
            logger.exception("sendMessage /setup private failed")
        return
    try:
        is_admin = telegram.is_chat_admin(message.chat.id, sender.id)
    except Exception:
        logger.exception("is_chat_admin failed chat_id=%s", message.chat.id)
        try:
            telegram.send_message(message.chat.id, "Gagal cek admin. Pastikan bot adalah admin group.")
        except Exception:
            logger.exception("sendMessage admin check failed")
        return
    if not is_admin:
        try:
            telegram.send_message(message.chat.id, "Hanya admin group Telegram yang dapat menjalankan /setup.")
        except Exception:
            logger.exception("sendMessage not admin failed")
        return

    with SessionLocal.begin() as session:
        user = find_or_create_user(
            session,
            sender.id,
            sender.display_name,
            sender.username,
        )
        try:
            family = create_workspace_for_group(
                session,
                user,
                message.chat.id,
                message.chat.title or "Komunitas Keuangan",
            )
        except ValueError:
            try:
                telegram.send_message(message.chat.id, "Group ini sudah terhubung ke komunitas keuangan.")
            except Exception:
                logger.exception("sendMessage already connected failed")
            return
    try:
        telegram.send_message(message.chat.id, f"Komunitas {family.name} berhasil dibuat. Kamu adalah OWNER.")
    except Exception:
        logger.exception("sendMessage setup success failed chat_id=%s", message.chat.id)
