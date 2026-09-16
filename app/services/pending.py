from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PendingAction, PendingActionType


def save_transaction_confirmation(session: Session, family_id: UUID, user_id: UUID, chat_id: int, payload: dict) -> None:
    pending = session.scalar(
        select(PendingAction).where(
            PendingAction.family_id == family_id,
            PendingAction.user_id == user_id,
            PendingAction.chat_id == chat_id,
        )
    )
    if pending is None:
        pending = PendingAction(family_id=family_id, user_id=user_id, chat_id=chat_id, action_type=PendingActionType.TRANSACTION, payload=payload, expires_at=datetime.now(UTC) + timedelta(minutes=15))
        session.add(pending)
    else:
        pending.payload = payload
        pending.expires_at = datetime.now(UTC) + timedelta(minutes=15)


def take_transaction_confirmation(session: Session, family_id: UUID, user_id: UUID, chat_id: int) -> dict | None:
    pending = session.scalar(
        select(PendingAction).where(
            PendingAction.family_id == family_id,
            PendingAction.user_id == user_id,
            PendingAction.chat_id == chat_id,
            PendingAction.action_type == PendingActionType.TRANSACTION,
        )
    )
    if pending is None or pending.expires_at < datetime.now(UTC):
        if pending is not None:
            session.delete(pending)
        return None
    payload = pending.payload
    session.delete(pending)
    return payload
