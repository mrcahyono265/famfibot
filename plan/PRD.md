# Product Requirements Document

**Status:** APPROVED

## Product

Family Finance Bot is a Telegram-first financial recording platform for families and other communities. Users record financial activity conversationally while the backend maintains a structured, auditable ledger.

## Goals

- Make everyday financial recording as easy as sending a Telegram message.
- Isolate data completely between workspaces.
- Support multiple Telegram groups and users in each workspace.
- Preserve financial correctness, privacy, auditability, and reconstructable balances.
- Use PostgreSQL as source of truth, with Google Sheets and PDF as outputs.

## Primary Users

- Family owners and administrators.
- Family members, including children with restricted access.
- Other communities such as shops, RT groups, or hobby communities.

## Approved Product Decisions

- The internal tenant term is **workspace**; the existing `families` database naming is retained for user-facing family usage.
- One Telegram user may belong to several workspaces.
- One workspace may bind several Telegram chats such as `GENERAL` and `PARENTS`.
- A Telegram group is a financial-flow group, not a personal conversation group.
- Private recording is done in direct chat with the bot. The user selects an active workspace there once, then may change it with `/ganti-komunitas`.
- MVP currency is IDR only.
- Rule-based Indonesian parsing comes before any LLM integration.
- Transfer confirmation is mandatory at Rp500.000 or above and whenever wallet, recipient, or intent is materially ambiguous.
- Google Sheets uses one spreadsheet per workspace per calendar year, with a monthly recap and transaction tabs per active month.

## In Scope

- Workspace setup and Telegram group binding.
- Membership roles, wallet ownership, wallet visibility, and transaction visibility.
- Income, expense, transfer, ledger, balance, audit logs, search, correction, and undo.
- Commands: `/start`, `/help`, `/setup`, `/ganti-komunitas`, `/saldo`, `/laporan`, `/cek`, `/wallet`, `/anggota`, `/undo`, `/export-laporan-pdf`.
- Google Sheets synchronization and on-demand PDF reports after the financial core is stable.

## Out of Scope for Initial MVP

- Web dashboard.
- Multi-currency and exchange rates.
- Automatic banking integration.
- Automatic per-user spreadsheets.
- LLM-first parsing or unrestricted chat-history analysis.
- Global balance across workspaces.

## Acceptance Criteria

- A user in workspace A cannot access data from workspace B.
- Admins can create and manage wallets and members.
- Users can record income, expense, and transfer through Telegram.
- Transfers never count as workspace income or expense.
- Wallet balances always reconstruct from ledger entries.
- Privacy filters apply to transaction queries, reports, PDF, and Sheets projections.
- Ambiguous financial instructions require clarification.
- Financial changes are auditable and not hard-deleted.
