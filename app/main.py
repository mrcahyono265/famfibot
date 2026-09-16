from __future__ import annotations

import logging
import secrets
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
from pydantic import BaseModel, Field
from app.config import get_settings
from app.database import SessionLocal
from app.models import Family, FamilyMember, MembershipStatus, UserWorkspaceContext, WalletType
from app.services.permissions import PermissionDenied
from app.services.setup import create_workspace_for_group, find_or_create_user
from app.services.wallets import WalletRuleError, accessible_wallets, create_wallet
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

    update = TelegramUpdate.model_validate(await request.json())
    message = update.message
    if message is None or message.text is None or message.from_ is None:
        logger.info("telegram update ignored update_id=%s", update.update_id)
        return {"ok": True}

    command, arguments = _command(message.text)
    logger.info("telegram command received update_id=%s chat_type=%s command=%s", update.update_id, message.chat.type, command)

    try:
        if command == "/setup":
            _handle_setup(message)
        elif command == "/start":
            _handle_start(message)
        elif command == "/ganti-komunitas":
            _handle_switch_workspace(message, arguments)
        elif command == "/wallet":
            _handle_wallet(message, arguments)
        elif command == "/saldo":
            _handle_balance(message)
    except Exception:
        logger.exception("telegram command failed update_id=%s command=%s", update.update_id, command)
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
        logger.exception("sendMessage setup success failed")


def _handle_start(message: TelegramMessage) -> None:
    sender = message.from_
    if sender is None:
        return
    if message.chat.type != "private":
        telegram.send_message(message.chat.id, "Untuk mencatat privat, buka chat pribadi saya lalu gunakan /start.")
        return
    with SessionLocal.begin() as session:
        find_or_create_user(session, sender.id, sender.display_name, sender.username)
    telegram.send_message(
        message.chat.id,
        "Gunakan /ganti-komunitas untuk memilih komunitas, /wallet untuk wallet, atau /saldo untuk saldo.",
    )


def _handle_switch_workspace(message: TelegramMessage, arguments: str) -> None:
    if not _require_private_chat(message):
        return
    sender = message.from_
    if sender is None:
        return
    with SessionLocal.begin() as session:
        user = find_or_create_user(session, sender.id, sender.display_name, sender.username)
        memberships = session.execute(
            select(Family)
            .join(FamilyMember, FamilyMember.family_id == Family.id)
            .where(FamilyMember.user_id == user.id, FamilyMember.status == MembershipStatus.ACTIVE)
            .order_by(Family.name)
        ).scalars().all()
        if not memberships:
            text = "Kamu belum menjadi anggota komunitas mana pun. Jalankan /setup di Group keuangan."
        elif not arguments:
            text = "Pilih dengan /ganti-komunitas <nama>:\n" + "\n".join(f"- {family.name}" for family in memberships)
        else:
            family = next((item for item in memberships if item.name.casefold() == arguments.casefold()), None)
            if family is None:
                text = "Komunitas tidak ditemukan. Gunakan /ganti-komunitas tanpa nama untuk melihat daftar."
            else:
                context = session.get(UserWorkspaceContext, user.id)
                if context is None:
                    session.add(UserWorkspaceContext(user_id=user.id, family_id=family.id))
                else:
                    context.family_id = family.id
                text = f"Komunitas aktif: {family.name}"
    telegram.send_message(message.chat.id, text)


def _handle_wallet(message: TelegramMessage, arguments: str) -> None:
    if not _require_private_chat(message):
        return
    sender = message.from_
    if sender is None:
        return
    with SessionLocal.begin() as session:
        user = find_or_create_user(session, sender.id, sender.display_name, sender.username)
        family = _active_family(session, user.id)
        if family is None:
            text = "Pilih komunitas terlebih dahulu dengan /ganti-komunitas."
        elif not arguments:
            wallets = accessible_wallets(session, family.id, user.id)
            text = _wallet_list(wallets) if wallets else "Belum ada wallet yang dapat kamu akses."
        elif arguments.lower().startswith("tambah "):
            try:
                name, wallet_type, initial_balance = _parse_wallet_create(arguments[7:])
                wallet = create_wallet(session, family.id, user.id, name, wallet_type, initial_balance)
                text = f"Wallet {wallet.name} berhasil dibuat dengan saldo awal {_rupiah(wallet.initial_balance)}."
            except (PermissionDenied, WalletRuleError, ValueError) as error:
                text = f"Wallet tidak dibuat: {error}"
        else:
            text = "Gunakan /wallet atau /wallet tambah <nama> <BANK|CASH|E_WALLET|OTHER> <saldo_awal>."
    telegram.send_message(message.chat.id, text)


def _handle_balance(message: TelegramMessage) -> None:
    if not _require_private_chat(message):
        return
    sender = message.from_
    if sender is None:
        return
    with SessionLocal.begin() as session:
        user = find_or_create_user(session, sender.id, sender.display_name, sender.username)
        family = _active_family(session, user.id)
        if family is None:
            text = "Pilih komunitas terlebih dahulu dengan /ganti-komunitas."
        else:
            wallets = accessible_wallets(session, family.id, user.id)
            if not wallets:
                text = "Belum ada wallet yang dapat kamu akses."
            else:
                total = sum(balance for _, balance in wallets)
                text = f"Saldo {family.name}\n" + _wallet_list(wallets) + f"\n\nTotal: {_rupiah(total)}"
    telegram.send_message(message.chat.id, text)


def _active_family(session: Session, user_id: UUID) -> Family | None:
    context = session.get(UserWorkspaceContext, user_id)
    if context is None:
        return None
    return session.scalar(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(
            Family.id == context.family_id,
            FamilyMember.user_id == user_id,
            FamilyMember.status == MembershipStatus.ACTIVE,
        )
    )


def _require_private_chat(message: TelegramMessage) -> bool:
    if message.chat.type == "private":
        return True
    telegram.send_message(message.chat.id, "Untuk menjaga privacy, gunakan command ini di chat pribadi bot.")
    return False


def _command(text: str) -> tuple[str, str]:
    command, _, arguments = text.strip().partition(" ")
    return command.lower().split("@", 1)[0], arguments.strip()


def _parse_wallet_create(arguments: str) -> tuple[str, WalletType, int]:
    try:
        name, type_text, balance_text = arguments.rsplit(maxsplit=2)
        return name, WalletType(type_text.upper()), int(balance_text)
    except ValueError as error:
        raise WalletRuleError("Format: /wallet tambah <nama> <BANK|CASH|E_WALLET|OTHER> <saldo_awal>") from error


def _wallet_list(wallets) -> str:
    return "\n".join(f"{wallet.name}: {_rupiah(balance)}" for wallet, balance in wallets)


def _rupiah(amount: int) -> str:
    return f"Rp{amount:,}".replace(",", ".")
