from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import FamilyMember, MembershipStatus, User, Wallet, WalletAccessGrant, WalletPermission


class PermissionDenied(Exception):
    pass


def set_tenant_context(session: Session, family_id: UUID) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT set_config('app.current_family_id', :family_id, true)"),
            {"family_id": str(family_id)},
        )


def require_active_member(session: Session, family_id: UUID, user_id: UUID) -> None:
    member = session.scalar(
        select(FamilyMember).where(
            FamilyMember.family_id == family_id,
            FamilyMember.user_id == user_id,
            FamilyMember.status == MembershipStatus.ACTIVE,
        )
    )
    if member is None:
        raise PermissionDenied("User is not an active workspace member")


def require_wallet_write(session: Session, wallet: Wallet, user_id: UUID) -> None:
    if wallet.owner_user_id == user_id:
        return

    grant = session.scalar(
        select(WalletAccessGrant).where(
            WalletAccessGrant.wallet_id == wallet.id,
            WalletAccessGrant.user_id == user_id,
            WalletAccessGrant.permission == WalletPermission.WRITE,
        )
    )
    if grant is None:
        raise PermissionDenied("User does not have write access to this wallet")
