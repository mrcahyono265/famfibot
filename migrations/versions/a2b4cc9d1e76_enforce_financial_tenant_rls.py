"""enforce financial tenant rls

Revision ID: a2b4cc9d1e76
Revises: 263e24352feb
Create Date: 2026-09-16

"""
from collections.abc import Sequence

from alembic import op

revision: str = "a2b4cc9d1e76"
down_revision: str | Sequence[str] | None = "263e24352feb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("wallets", "categories", "transactions", "ledger_entries", "audit_logs")
TENANT_ID = "NULLIF(current_setting('app.current_family_id', true), '')::uuid"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_policy ON {table} "
            f"USING (family_id = {TENANT_ID}) WITH CHECK (family_id = {TENANT_ID})"
        )
    op.execute("ALTER TABLE wallet_access_grants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE wallet_access_grants FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY wallet_access_grants_tenant_policy ON wallet_access_grants "
        "USING (EXISTS (SELECT 1 FROM wallets WHERE wallets.id = wallet_access_grants.wallet_id)) "
        "WITH CHECK (EXISTS (SELECT 1 FROM wallets WHERE wallets.id = wallet_access_grants.wallet_id))"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP POLICY wallet_access_grants_tenant_policy ON wallet_access_grants")
    op.execute("ALTER TABLE wallet_access_grants NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE wallet_access_grants DISABLE ROW LEVEL SECURITY")
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY {table}_tenant_policy ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
