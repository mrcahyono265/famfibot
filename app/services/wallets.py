from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, UserWorkspaceContext, Wallet, WalletAccessGrant, WalletStatus, WalletType
from app.services.permissions import require_workspace_admin, set_tenant_context
from app.services.transactions import wallet_balance


class WalletRuleError(ValueError):
    pass


def create_wallet(
    session: Session,
    family_id: UUID,
    actor_user_id: UUID,
    name: str,
    wallet_type: WalletType,
    initial_balance: int,
) -> Wallet:
    if not name.strip():
        raise WalletRuleError("Wallet name is required")
    if initial_balance < 0:
        raise WalletRuleError("Initial balance cannot be negative")

    set_tenant_context(session, family_id)
    require_workspace_admin(session, family_id, actor_user_id)
    wallet = Wallet(
        family_id=family_id,
        owner_user_id=actor_user_id,
        name=name.strip(),
        wallet_type=wallet_type,
        initial_balance=initial_balance,
    )
    session.add(wallet)
    session.flush()
    context = session.get(UserWorkspaceContext, actor_user_id)
    if context is not None and context.family_id == family_id and context.default_wallet_id is None:
        context.default_wallet_id = wallet.id
    session.add(
        AuditLog(
            family_id=family_id,
            actor_user_id=actor_user_id,
            entity_type="wallet",
            entity_id=wallet.id,
            action="CREATED",
            before_data=None,
            after_data={"name": wallet.name, "type": wallet_type, "initial_balance": initial_balance},
            reason=None,
        )
    )
    return wallet


def accessible_wallets(session: Session, family_id: UUID, user_id: UUID) -> list[tuple[Wallet, int]]:
    set_tenant_context(session, family_id)
    wallets = session.scalars(
        select(Wallet)
        .outerjoin(
            WalletAccessGrant,
            (WalletAccessGrant.wallet_id == Wallet.id) & (WalletAccessGrant.user_id == user_id),
        )
        .where(
            Wallet.family_id == family_id,
            Wallet.status == WalletStatus.ACTIVE,
            or_(Wallet.owner_user_id == user_id, WalletAccessGrant.user_id.is_not(None)),
        )
        .order_by(Wallet.name)
    ).all()
    return [(wallet, wallet_balance(session, family_id, wallet.id)) for wallet in wallets]


def default_wallet(session: Session, family_id: UUID, user_id: UUID) -> Wallet | None:
    set_tenant_context(session, family_id)
    context = session.get(UserWorkspaceContext, user_id)
    if context is None or context.family_id != family_id or context.default_wallet_id is None:
        return None
    return session.scalar(
        select(Wallet).where(
            Wallet.id == context.default_wallet_id,
            Wallet.family_id == family_id,
            Wallet.status == WalletStatus.ACTIVE,
        )
    )
