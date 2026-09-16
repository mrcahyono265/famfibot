from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Family,
    FamilyMember,
    FamilySettings,
    GroupMember,
    GroupType,
    MemberRole,
    TelegramGroup,
    User,
)
from app.services.permissions import set_tenant_context


def find_or_create_user(
    session: Session, telegram_user_id: int, display_name: str, telegram_username: str | None
) -> User:
    user = session.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
    if user is None:
        user = User(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            telegram_username=telegram_username,
        )
        session.add(user)
        session.flush()
    else:
        user.display_name = display_name
        user.telegram_username = telegram_username
    return user


def create_workspace_for_group(
    session: Session, user: User, telegram_chat_id: int, group_name: str
) -> Family:
    existing = session.scalar(select(TelegramGroup).where(TelegramGroup.telegram_chat_id == telegram_chat_id))
    if existing is not None:
        raise ValueError("This Telegram group is already connected to a workspace")

    family = Family(name=group_name, created_by_user_id=user.id)
    session.add(family)
    session.flush()
    set_tenant_context(session, family.id)
    session.add(FamilyMember(family_id=family.id, user_id=user.id, role=MemberRole.OWNER))
    session.add(FamilySettings(family_id=family.id))
    group = TelegramGroup(
        family_id=family.id,
        telegram_chat_id=telegram_chat_id,
        name=group_name,
        group_type=GroupType.GENERAL,
    )
    session.add(group)
    session.flush()
    session.add(GroupMember(group_id=group.id, user_id=user.id))
    session.add(
        AuditLog(
            family_id=family.id,
            actor_user_id=user.id,
            entity_type="family",
            entity_id=family.id,
            action="CREATED",
            before_data=None,
            after_data={"name": group_name, "telegram_chat_id": telegram_chat_id},
            reason="Telegram /setup",
        )
    )
    return family
