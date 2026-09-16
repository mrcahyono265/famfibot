# MVP Implementation Plan

**Status:** APPROVED

## Phase 1: Financial Core and Tenant Safety

1. Initialize FastAPI, SQLAlchemy, Alembic, PostgreSQL configuration, Docker deployment, and webhook endpoint.
2. Build users, workspaces, memberships, Telegram group binding, and tenant/RLS enforcement.
3. Build wallets, wallet access grants, default wallet selection, and categories.
4. Build transaction service, immutable ledger entries, balances, and audit logs.
5. Implement `/setup`, `/wallet`, `/anggota`, `/saldo`, and direct-chat workspace switching.
6. Add unit/integration tests for ledger and cross-tenant access.

## Phase 2: Conversational Financial Input

1. Add Indonesian rule parser for amounts, expense, income, transfer, and simple dates.
2. Add confirmation sessions and inline keyboards for ambiguous inputs.
3. Add `/cek`, `/laporan`, and transaction search.
4. Add correction and `/undo` with audit preservation.

## Phase 3: Reporting Integrations

1. Add Google OAuth and encrypted workspace integration storage.
2. Add initial and incremental Google Sheets sync with retries.
3. Add ReportLab PDF export with portrait summary and landscape transaction appendix.

## Phase 4: Optional Intelligence and Web

1. Add DeepSeek fallback with token-minimized structured extraction.
2. Add advanced natural language search/reporting only after access controls are fully tested.
3. Consider web dashboard after Telegram workflows are proven.

## Definition of Done for Phase 1

- A Telegram group can create or bind to a workspace.
- A user can belong to multiple workspaces without data mixing.
- Wallets and financial transactions are tenant-scoped and permission-checked.
- Ledger-derived balances remain correct under income, expense, and transfer.
- Cross-tenant and privacy tests pass.
- Production deployment has HTTPS webhook, secrets, migrations, and backup procedure.
