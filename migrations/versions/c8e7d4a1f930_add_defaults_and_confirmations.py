"""add defaults and confirmations

Revision ID: c8e7d4a1f930
Revises: a2b4cc9d1e76
Create Date: 2026-09-16

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "c8e7d4a1f930"
down_revision: str | Sequence[str] | None = "a2b4cc9d1e76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_workspace_contexts", sa.Column("default_wallet_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_context_default_wallet", "user_workspace_contexts", "wallets", ["default_wallet_id"], ["id"])
    op.create_table(
        "pending_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("family_id", sa.Uuid(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("family_id", "user_id", "chat_id"),
    )
    op.create_index("ix_pending_actions_family_id", "pending_actions", ["family_id"])
    op.create_index("ix_pending_actions_user_id", "pending_actions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_pending_actions_user_id", table_name="pending_actions")
    op.drop_index("ix_pending_actions_family_id", table_name="pending_actions")
    op.drop_table("pending_actions")
    op.drop_constraint("fk_context_default_wallet", "user_workspace_contexts", type_="foreignkey")
    op.drop_column("user_workspace_contexts", "default_wallet_id")
