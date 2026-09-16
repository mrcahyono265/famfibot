from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MemberRole(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class MembershipStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class GroupType(StrEnum):
    GENERAL = "GENERAL"
    PARENTS = "PARENTS"


class WalletType(StrEnum):
    BANK = "BANK"
    CASH = "CASH"
    E_WALLET = "E_WALLET"
    OTHER = "OTHER"


class WalletStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class WalletPermission(StrEnum):
    READ = "READ"
    WRITE = "WRITE"


class TransactionType(StrEnum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"


class TransactionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    VOIDED = "VOIDED"
    SUPERSEDED = "SUPERSEDED"


class PendingActionType(StrEnum):
    TRANSACTION = "TRANSACTION"


def new_id() -> UUID:
    return uuid4()


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Timestamped, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    telegram_username: Mapped[str | None] = mapped_column(String(128))


class Family(Timestamped, Base):
    __tablename__ = "families"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)


class FamilyMember(Timestamped, Base):
    __tablename__ = "family_members"
    __table_args__ = (UniqueConstraint("family_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default=MemberRole.MEMBER)
    status: Mapped[str] = mapped_column(String(16), default=MembershipStatus.ACTIVE)


class TelegramGroup(Timestamped, Base):
    __tablename__ = "groups"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    group_type: Mapped[str] = mapped_column(String(16), default=GroupType.GENERAL)
    is_active: Mapped[bool] = mapped_column(default=True)


class GroupMember(Timestamped, Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    group_id: Mapped[UUID] = mapped_column(ForeignKey("groups.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=MembershipStatus.ACTIVE)


class FamilySettings(Timestamped, Base):
    __tablename__ = "family_settings"

    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), default="IDR")
    transfer_confirmation_threshold: Mapped[int] = mapped_column(BigInteger, default=500_000)


class UserWorkspaceContext(Timestamped, Base):
    __tablename__ = "user_workspace_contexts"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), index=True)
    default_wallet_id: Mapped[UUID | None] = mapped_column(ForeignKey("wallets.id"))


class Wallet(Timestamped, Base):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("family_id", "name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), index=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    wallet_type: Mapped[str] = mapped_column(String(16))
    initial_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="IDR")
    status: Mapped[str] = mapped_column(String(16), default=WalletStatus.ACTIVE)


class WalletAccessGrant(Timestamped, Base):
    __tablename__ = "wallet_access_grants"
    __table_args__ = (UniqueConstraint("wallet_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    wallet_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    permission: Mapped[str] = mapped_column(String(16))


class Category(Timestamped, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("family_id", "name", "transaction_type"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    transaction_type: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(default=True)


class Transaction(Timestamped, Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("origin_chat_id", "origin_message_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), index=True)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    transaction_type: Mapped[str] = mapped_column(String(16))
    amount: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(256))
    note: Mapped[str | None] = mapped_column(Text)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(24), default=TransactionStatus.ACTIVE)
    source_wallet_id: Mapped[UUID | None] = mapped_column(ForeignKey("wallets.id"))
    destination_wallet_id: Mapped[UUID | None] = mapped_column(ForeignKey("wallets.id"))
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"))
    origin_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    origin_message_id: Mapped[int | None] = mapped_column(BigInteger)
    original_message: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[int | None] = mapped_column()


class PendingAction(Base):
    __tablename__ = "pending_actions"
    __table_args__ = (UniqueConstraint("family_id", "user_id", "chat_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    action_type: Mapped[str] = mapped_column(String(32), default=PendingActionType.TRANSACTION)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), index=True)
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("transactions.id"), index=True)
    wallet_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.id"), index=True)
    signed_amount: Mapped[int] = mapped_column(BigInteger)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[UUID] = mapped_column(ForeignKey("families.id"), index=True)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[UUID] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(64))
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
