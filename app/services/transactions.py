from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, LedgerEntry, Transaction, TransactionStatus, TransactionType, Wallet
from app.services.permissions import require_active_member, require_wallet_write, set_tenant_context


class TransactionRuleError(ValueError):
    pass


@dataclass(frozen=True)
class RecordTransaction:
    family_id: UUID
    actor_user_id: UUID
    transaction_type: TransactionType
    amount: int
    description: str
    transaction_date: date
    source_wallet_id: UUID | None = None
    destination_wallet_id: UUID | None = None
    note: str | None = None
    origin_chat_id: int | None = None
    origin_message_id: int | None = None
    original_message: str | None = None
    confidence: int | None = None


def record_transaction(session: Session, command: RecordTransaction) -> Transaction:
    if command.amount <= 0:
        raise TransactionRuleError("Amount must be positive")

    set_tenant_context(session, command.family_id)
    require_active_member(session, command.family_id, command.actor_user_id)
    source = _wallet(session, command.family_id, command.source_wallet_id)
    destination = _wallet(session, command.family_id, command.destination_wallet_id)
    _validate(command, source, destination)

    if source is not None:
        require_wallet_write(session, source, command.actor_user_id)
    if destination is not None and command.transaction_type == TransactionType.INCOME:
        require_wallet_write(session, destination, command.actor_user_id)

    transaction = Transaction(
        family_id=command.family_id,
        created_by_user_id=command.actor_user_id,
        transaction_type=command.transaction_type,
        amount=command.amount,
        description=command.description,
        note=command.note,
        transaction_date=command.transaction_date,
        source_wallet_id=command.source_wallet_id,
        destination_wallet_id=command.destination_wallet_id,
        origin_chat_id=command.origin_chat_id,
        origin_message_id=command.origin_message_id,
        original_message=command.original_message,
        confidence=command.confidence,
    )
    session.add(transaction)
    session.flush()

    if source is not None:
        session.add(
            LedgerEntry(
                family_id=command.family_id,
                transaction_id=transaction.id,
                wallet_id=source.id,
                signed_amount=-command.amount,
                entry_date=command.transaction_date,
            )
        )
    if destination is not None:
        session.add(
            LedgerEntry(
                family_id=command.family_id,
                transaction_id=transaction.id,
                wallet_id=destination.id,
                signed_amount=command.amount,
                entry_date=command.transaction_date,
            )
        )

    session.add(
        AuditLog(
            family_id=command.family_id,
            actor_user_id=command.actor_user_id,
            entity_type="transaction",
            entity_id=transaction.id,
            action="CREATED",
            before_data=None,
            after_data={"amount": command.amount, "type": command.transaction_type},
            reason=None,
        )
    )
    return transaction


def wallet_balance(session: Session, family_id: UUID, wallet_id: UUID) -> int:
    set_tenant_context(session, family_id)
    wallet = _wallet(session, family_id, wallet_id)
    if wallet is None:
        raise TransactionRuleError("Wallet not found in workspace")
    movements = session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.signed_amount), 0))
        .join(Transaction, LedgerEntry.transaction_id == Transaction.id)
        .where(
            LedgerEntry.family_id == family_id,
            LedgerEntry.wallet_id == wallet_id,
            Transaction.status == TransactionStatus.ACTIVE,
        )
    )
    return wallet.initial_balance + int(movements or 0)


def void_transaction(session: Session, family_id: UUID, actor_user_id: UUID, transaction_id: UUID) -> None:
    set_tenant_context(session, family_id)
    require_active_member(session, family_id, actor_user_id)
    transaction = session.scalar(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.family_id == family_id)
    )
    if transaction is None:
        raise TransactionRuleError("Transaction not found in workspace")
    if transaction.created_by_user_id != actor_user_id:
        raise TransactionRuleError("Only the transaction creator may void it at this stage")
    if transaction.status != TransactionStatus.ACTIVE:
        raise TransactionRuleError("Only active transactions can be voided")

    transaction.status = TransactionStatus.VOIDED
    session.add(
        AuditLog(
            family_id=family_id,
            actor_user_id=actor_user_id,
            entity_type="transaction",
            entity_id=transaction.id,
            action="VOIDED",
            before_data={"status": TransactionStatus.ACTIVE},
            after_data={"status": TransactionStatus.VOIDED},
            reason=None,
        )
    )


def recent_transactions(session: Session, family_id: UUID, user_id: UUID, transaction_date: date | None = None) -> list[Transaction]:
    set_tenant_context(session, family_id)
    source_owner = Wallet.__table__.alias("source_owner")
    destination_owner = Wallet.__table__.alias("destination_owner")
    conditions = [
        Transaction.family_id == family_id,
        Transaction.status == TransactionStatus.ACTIVE,
        or_(
            Transaction.created_by_user_id == user_id,
            source_owner.c.owner_user_id == user_id,
            destination_owner.c.owner_user_id == user_id,
        ),
    ]
    if transaction_date is not None:
        conditions.append(Transaction.transaction_date == transaction_date)
    return list(session.scalars(
        select(Transaction)
        .outerjoin(source_owner, Transaction.source_wallet_id == source_owner.c.id)
        .outerjoin(destination_owner, Transaction.destination_wallet_id == destination_owner.c.id)
        .where(and_(*conditions))
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .limit(20)
    ).all())


def _wallet(session: Session, family_id: UUID, wallet_id: UUID | None) -> Wallet | None:
    if wallet_id is None:
        return None
    return session.scalar(select(Wallet).where(Wallet.id == wallet_id, Wallet.family_id == family_id))


def _validate(command: RecordTransaction, source: Wallet | None, destination: Wallet | None) -> None:
    if command.transaction_type == TransactionType.EXPENSE:
        if source is None or destination is not None:
            raise TransactionRuleError("Expense requires only a source wallet")
    elif command.transaction_type == TransactionType.INCOME:
        if destination is None or source is not None:
            raise TransactionRuleError("Income requires only a destination wallet")
    elif command.transaction_type == TransactionType.TRANSFER:
        if source is None or destination is None or source.id == destination.id:
            raise TransactionRuleError("Transfer requires two different wallets")
    else:
        raise TransactionRuleError("Unsupported transaction type")
