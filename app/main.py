from __future__ import annotations

import logging
import secrets
from datetime import date
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
from pydantic import BaseModel, Field
from app.config import get_settings
from app.database import SessionLocal
from app.models import Family, FamilyMember, FamilySettings, MemberRole, MembershipStatus, TelegramGroup, Transaction, TransactionStatus, TransactionType, User, UserWorkspaceContext, Wallet, WalletStatus, WalletType
from app.services.members import MemberRuleError, add_member
from app.services.parser import ParsedMessage, parse_transaction
from app.services.deepseek import parse_with_deepseek
from app.services.pending import save_transaction_confirmation, take_transaction_confirmation
from app.services.pdf import build_report_pdf
from app.services.permissions import PermissionDenied
from app.services.setup import create_workspace_for_group, find_or_create_user
from app.services.transactions import RecordTransaction, TransactionRuleError, recent_transactions, record_transaction, void_transaction, wallet_balance
from app.services.wallets import default_wallet
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
        elif command == "/anggota":
            _handle_members(message, arguments)
        elif command == "/cek":
            _handle_check(message, arguments)
        elif command == "/laporan":
            _handle_report(message)
        elif command == "/undo":
            _handle_undo(message)
        elif command == "/export-laporan-pdf":
            _handle_pdf_export(message)
        else:
            _handle_transaction_input(message, command, arguments)
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


def _handle_members(message: TelegramMessage, arguments: str) -> None:
    if not _require_private_chat(message):
        return
    sender = message.from_
    if sender is None:
        return
    with SessionLocal.begin() as session:
        actor = find_or_create_user(session, sender.id, sender.display_name, sender.username)
        family = _active_family(session, actor.id)
        if family is None:
            text = "Pilih komunitas terlebih dahulu dengan /ganti-komunitas."
        elif not arguments:
            members = session.execute(
                select(User, FamilyMember).join(FamilyMember, FamilyMember.user_id == User.id).where(FamilyMember.family_id == family.id, FamilyMember.status == MembershipStatus.ACTIVE).order_by(User.display_name)
            ).all()
            text = "\n".join(f"{user.display_name} - {member.role}" for user, member in members)
        elif arguments.lower().startswith("tambah "):
            try:
                name, role_text = arguments[7:].rsplit(maxsplit=1)
                role = MemberRole(role_text.upper())
                member = session.scalar(select(User).where(User.display_name.ilike(name)))
                if member is None:
                    raise MemberRuleError("User belum chat /start ke bot.")
                add_member(session, family.id, actor.id, member, role)
                text = f"{member.display_name} ditambahkan sebagai {role}."
            except (ValueError, MemberRuleError, PermissionDenied) as error:
                text = f"Anggota tidak ditambahkan: {error}"
        else:
            text = "Gunakan /anggota atau /anggota tambah <nama> <OWNER|ADMIN|MEMBER|VIEWER>."
    telegram.send_message(message.chat.id, text)


def _handle_check(message: TelegramMessage, arguments: str) -> None:
    if not _require_private_chat(message):
        return
    sender = message.from_
    if sender is None:
        return
    try:
        requested_date = date.fromisoformat(arguments) if arguments else None
    except ValueError:
        telegram.send_message(message.chat.id, "Gunakan tanggal format YYYY-MM-DD, misalnya /cek 2026-09-16.")
        return
    with SessionLocal.begin() as session:
        user = find_or_create_user(session, sender.id, sender.display_name, sender.username)
        family = _active_family(session, user.id)
        transactions = recent_transactions(session, family.id, user.id, requested_date) if family else []
        if family is None:
            text = "Pilih komunitas terlebih dahulu dengan /ganti-komunitas."
        elif not transactions:
            text = "Tidak ada transaksi yang dapat kamu lihat."
        else:
            text = "\n".join(f"{index}. {transaction.description} - {_rupiah(transaction.amount)} ({transaction.transaction_date.isoformat()})" for index, transaction in enumerate(transactions, 1))
    telegram.send_message(message.chat.id, text)


def _handle_report(message: TelegramMessage) -> None:
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
            transactions = recent_transactions(session, family.id, user.id)
            income = sum(tx.amount for tx in transactions if tx.transaction_type == TransactionType.INCOME)
            expense = sum(tx.amount for tx in transactions if tx.transaction_type == TransactionType.EXPENSE)
            text = f"Laporan {family.name}\nPemasukan: {_rupiah(income)}\nPengeluaran: {_rupiah(expense)}\nArus bersih: {_rupiah(income - expense)}"
    telegram.send_message(message.chat.id, text)


def _handle_undo(message: TelegramMessage) -> None:
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
            transaction = session.scalar(
                select(Transaction)
                .where(
                    Transaction.family_id == family.id,
                    Transaction.created_by_user_id == user.id,
                    Transaction.status == TransactionStatus.ACTIVE,
                )
                .order_by(Transaction.created_at.desc())
            )
            if transaction is None:
                text = "Tidak ada transaksi aktif untuk dibatalkan."
            else:
                void_transaction(session, family.id, user.id, transaction.id)
                text = f"Transaksi {transaction.description} dibatalkan."
    telegram.send_message(message.chat.id, text)


def _handle_pdf_export(message: TelegramMessage) -> None:
    if not _require_private_chat(message):
        return
    sender = message.from_
    if sender is None:
        return
    with SessionLocal.begin() as session:
        user = find_or_create_user(session, sender.id, sender.display_name, sender.username)
        family = _active_family(session, user.id)
        if family is None:
            telegram.send_message(message.chat.id, "Pilih komunitas terlebih dahulu dengan /ganti-komunitas.")
            return
        content = build_report_pdf(family.name, recent_transactions(session, family.id, user.id))
    telegram.send_document(message.chat.id, "laporan-keuangan.pdf", content)


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


def _handle_transaction_input(message: TelegramMessage, command: str, arguments: str) -> None:
    sender = message.from_
    if sender is None:
        return
    text = message.text or ""
    normalized = text.strip().lower()
    with SessionLocal.begin() as session:
        user = find_or_create_user(session, sender.id, sender.display_name, sender.username)
        family = _message_family(session, message, user.id)
        if family is None:
            return
        if normalized in {"ya", "/ya"}:
            payload = take_transaction_confirmation(session, family.id, user.id, message.chat.id)
            if payload is None:
                response = "Tidak ada transaksi yang menunggu konfirmasi."
            else:
                transaction = _record_payload(session, family.id, user.id, payload, message)
                response = _transaction_response(session, transaction, message.chat.type == "private")
        else:
            candidate = _parse_input(command, arguments, text) or (parse_with_deepseek(text, date.today()) if not command.startswith("/") else None)
            if candidate is None:
                return
            payload = _transaction_payload(session, family.id, user.id, candidate)
            if payload is None:
                response = "Wallet default atau wallet tujuan belum jelas. Gunakan /wallet dan /ganti-komunitas terlebih dahulu."
            elif candidate.transaction_type == TransactionType.TRANSFER and candidate.amount >= _confirmation_threshold(session, family.id):
                save_transaction_confirmation(session, family.id, user.id, message.chat.id, payload)
                response = f"Transfer {_rupiah(candidate.amount)} akan dicatat. Balas Ya untuk menyimpan."
            else:
                transaction = _record_payload(session, family.id, user.id, payload, message)
                response = _transaction_response(session, transaction, message.chat.type == "private")
    telegram.send_message(message.chat.id, response)


def _message_family(session: Session, message: TelegramMessage, user_id: UUID) -> Family | None:
    if message.chat.type == "private":
        return _active_family(session, user_id)
    group = session.scalar(select(TelegramGroup).where(TelegramGroup.telegram_chat_id == message.chat.id, TelegramGroup.is_active.is_(True)))
    if group is None:
        return None
    return session.scalar(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(Family.id == group.family_id, FamilyMember.user_id == user_id, FamilyMember.status == MembershipStatus.ACTIVE)
    )


def _parse_input(command: str, arguments: str, text: str) -> ParsedMessage | None:
    if command == "/keluar":
        return parse_transaction(f"beli {arguments}", date.today())
    if command == "/masuk":
        return parse_transaction(f"masuk {arguments}", date.today())
    if command == "/transfer":
        return parse_transaction(f"transfer {arguments}", date.today())
    if command.startswith("/"):
        return None
    return parse_transaction(text, date.today())


def _transaction_payload(session: Session, family_id: UUID, user_id: UUID, candidate: ParsedMessage) -> dict | None:
    source = default_wallet(session, family_id, user_id) if candidate.transaction_type != TransactionType.INCOME else None
    destination = default_wallet(session, family_id, user_id) if candidate.transaction_type == TransactionType.INCOME else None
    if candidate.transaction_type == TransactionType.TRANSFER:
        destination = _wallet_for_recipient(session, family_id, candidate.recipient_name)
    if (candidate.transaction_type == TransactionType.EXPENSE and source is None) or (candidate.transaction_type == TransactionType.INCOME and destination is None) or (candidate.transaction_type == TransactionType.TRANSFER and (source is None or destination is None)):
        return None
    return {
        "type": candidate.transaction_type,
        "amount": candidate.amount,
        "description": candidate.description,
        "date": candidate.transaction_date.isoformat(),
        "source_wallet_id": str(source.id) if source else None,
        "destination_wallet_id": str(destination.id) if destination else None,
        "confidence": candidate.confidence,
    }


def _wallet_for_recipient(session: Session, family_id: UUID, recipient_name: str | None) -> Wallet | None:
    if not recipient_name:
        return None
    wallets = session.execute(
        select(Wallet, User)
        .outerjoin(User, Wallet.owner_user_id == User.id)
        .where(Wallet.family_id == family_id, Wallet.status == WalletStatus.ACTIVE)
    ).all()
    matches = [wallet for wallet, owner in wallets if wallet.name.casefold() == recipient_name.casefold() or (owner and owner.display_name.casefold() == recipient_name.casefold())]
    return matches[0] if len(matches) == 1 else None


def _record_payload(session: Session, family_id: UUID, user_id: UUID, payload: dict, message: TelegramMessage):
    return record_transaction(
        session,
        RecordTransaction(
            family_id=family_id,
            actor_user_id=user_id,
            transaction_type=TransactionType(payload["type"]),
            amount=payload["amount"],
            description=payload["description"],
            transaction_date=date.fromisoformat(payload["date"]),
            source_wallet_id=UUID(payload["source_wallet_id"]) if payload["source_wallet_id"] else None,
            destination_wallet_id=UUID(payload["destination_wallet_id"]) if payload["destination_wallet_id"] else None,
            origin_chat_id=message.chat.id,
            origin_message_id=message.message_id,
            original_message=message.text,
            confidence=payload["confidence"],
        ),
    )


def _confirmation_threshold(session: Session, family_id: UUID) -> int:
    settings = session.get(FamilySettings, family_id)
    return settings.transfer_confirmation_threshold if settings else 500_000


def _transaction_response(session: Session, transaction, include_balance: bool) -> str:
    label = {TransactionType.EXPENSE: "Pengeluaran", TransactionType.INCOME: "Pemasukan", TransactionType.TRANSFER: "Transfer"}[TransactionType(transaction.transaction_type)]
    text = f"{label} {_rupiah(transaction.amount)} tercatat."
    wallet_id = transaction.source_wallet_id if transaction.transaction_type == TransactionType.EXPENSE else transaction.destination_wallet_id
    if include_balance and wallet_id is not None:
        text += f"\nSaldo: {_rupiah(wallet_balance(session, transaction.family_id, wallet_id))}"
    return text
