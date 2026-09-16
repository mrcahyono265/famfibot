from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, FamilyMember, GroupMember, MemberRole, MembershipStatus, TelegramGroup, User
from app.services.permissions import require_workspace_admin, set_tenant_context


class MemberRuleError(ValueError):
    pass


def add_member(session: Session, family_id: UUID, actor_user_id: UUID, member: User, role: MemberRole = MemberRole.MEMBER) -> None:
    require_workspace_admin(session, family_id, actor_user_id)
    set_tenant_context(session, family_id)
    existing = session.scalar(select(FamilyMember).where(FamilyMember.family_id == family_id, FamilyMember.user_id == member.id))
    if existing is None:
        session.add(FamilyMember(family_id=family_id, user_id=member.id, role=role))
    else:
        existing.status = MembershipStatus.ACTIVE
        existing.role = role
    session.add(AuditLog(family_id=family_id, actor_user_id=actor_user_id, entity_type="family_member", entity_id=member.id, action="ADDED", before_data=None, after_data={"role": role}, reason=None))


def add_member_to_group(session: Session, family_id: UUID, actor_user_id: UUID, group: TelegramGroup, member: User) -> None:
    require_workspace_admin(session, family_id, actor_user_id)
    if group.family_id != family_id:
        raise MemberRuleError("Group is not in this workspace")
    set_tenant_context(session, family_id)
    existing = session.scalar(select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == member.id))
    if existing is None:
        session.add(GroupMember(group_id=group.id, user_id=member.id))
    else:
        existing.status = MembershipStatus.ACTIVE


def bind_group(session: Session, family_id: UUID, actor_user_id: UUID, telegram_chat_id: int, name: str) -> TelegramGroup:
    require_workspace_admin(session, family_id, actor_user_id)
    existing = session.scalar(select(TelegramGroup).where(TelegramGroup.telegram_chat_id == telegram_chat_id))
    if existing is not None:
        raise MemberRuleError("Group ini sudah terhubung ke komunitas keuangan.")
    set_tenant_context(session, family_id)
    group = TelegramGroup(family_id=family_id, telegram_chat_id=telegram_chat_id, name=name, group_type="GROUP")
    session.add(group)
    session.flush()
    session.add(AuditLog(family_id=family_id, actor_user_id=actor_user_id, entity_type="group", entity_id=group.id, action="BOUND", before_data=None, after_data={"telegram_chat_id": telegram_chat_id, "name": name}, reason="Telegram /hubungkan-group"))
    return group


def request_group_membership(session: Session, group: TelegramGroup, member: User) -> bool:
    set_tenant_context(session, group.family_id)
    family_member = session.scalar(select(FamilyMember).where(FamilyMember.family_id == group.family_id, FamilyMember.user_id == member.id))
    group_member = session.scalar(select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == member.id))
    if family_member is not None and family_member.status == MembershipStatus.ACTIVE and group_member is not None and group_member.status == MembershipStatus.ACTIVE:
        return False
    if family_member is None:
        session.add(FamilyMember(family_id=group.family_id, user_id=member.id, role=MemberRole.MEMBER, status=MembershipStatus.PENDING))
    elif family_member.status != MembershipStatus.ACTIVE:
        family_member.status = MembershipStatus.PENDING
    if group_member is None:
        session.add(GroupMember(group_id=group.id, user_id=member.id, status=MembershipStatus.PENDING))
    elif group_member.status != MembershipStatus.ACTIVE:
        group_member.status = MembershipStatus.PENDING
    return True


def approve_member(session: Session, family_id: UUID, actor_user_id: UUID, member: User, group_name: str | None = None) -> bool:
    require_workspace_admin(session, family_id, actor_user_id)
    family_member = session.scalar(select(FamilyMember).where(FamilyMember.family_id == family_id, FamilyMember.user_id == member.id))
    if family_member is None:
        return False
    set_tenant_context(session, family_id)
    group_members = session.scalars(
        select(GroupMember).join(TelegramGroup, TelegramGroup.id == GroupMember.group_id).where(
            TelegramGroup.family_id == family_id,
            GroupMember.user_id == member.id,
            GroupMember.status == MembershipStatus.PENDING,
        )
    ).all()
    if group_name:
        group_members = session.scalars(
            select(GroupMember).join(TelegramGroup, TelegramGroup.id == GroupMember.group_id).where(
                TelegramGroup.family_id == family_id,
                TelegramGroup.name.ilike(group_name),
                GroupMember.user_id == member.id,
                GroupMember.status == MembershipStatus.PENDING,
            )
        ).all()
    elif len(group_members) > 1:
        raise MemberRuleError("Pilih group dengan /anggota setujui <nama> di <nama group>.")
    if not group_members:
        return False
    if family_member.status == MembershipStatus.PENDING:
        family_member.status = MembershipStatus.ACTIVE
    for group_member in group_members:
        group_member.status = MembershipStatus.ACTIVE
    session.add(AuditLog(family_id=family_id, actor_user_id=actor_user_id, entity_type="family_member", entity_id=member.id, action="APPROVED", before_data={"status": MembershipStatus.PENDING}, after_data={"status": MembershipStatus.ACTIVE}, reason="Telegram /anggota setujui"))
    return True
