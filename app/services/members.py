from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, FamilyMember, GroupMember, MemberRole, MembershipStatus, TelegramGroup, User
from app.services.permissions import require_workspace_admin


class MemberRuleError(ValueError):
    pass


def add_member(session: Session, family_id: UUID, actor_user_id: UUID, member: User, role: MemberRole = MemberRole.MEMBER) -> None:
    require_workspace_admin(session, family_id, actor_user_id)
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
    existing = session.scalar(select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == member.id))
    if existing is None:
        session.add(GroupMember(group_id=group.id, user_id=member.id))
    else:
        existing.status = MembershipStatus.ACTIVE
