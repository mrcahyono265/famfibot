# Database and Ledger Design

**Status:** APPROVED

## Tenant Boundary

`families` represents a workspace. Every financial table stores `family_id`; queries must scope by it. PostgreSQL Row-Level Security provides a second enforcement layer.

## Entities

| Table | Purpose |
|---|---|
| `users` | Global Telegram identity and display name |
| `families` | Workspace tenant |
| `family_members` | Workspace role and membership state |
| `groups` | Telegram chat bound to one workspace |
| `group_members` | Explicit application membership in a group |
| `wallets` | Money locations and initial balances |
| `wallet_access_grants` | Explicit wallet access outside ownership defaults |
| `categories` | Workspace-local reporting categories |
| `transactions` | Business event and user-facing details |
| `ledger_entries` | Immutable signed wallet movements |
| `transaction_participants` | Users financially involved in a transaction |
| `transaction_access_grants` | Explicit transaction visibility grants |
| `audit_logs` | Actor, action, before/after snapshot, and reason |
| `google_integrations` | Workspace spreadsheet binding per reporting year and encrypted credentials |
| `family_settings` | Workspace defaults and confirmation threshold |

## Required Fields

```text
users: id, telegram_user_id UNIQUE, display_name, telegram_username, created_at
families: id, name, created_by_user_id, created_at
family_members: family_id, user_id, role, status, created_at
groups: id, family_id, telegram_chat_id UNIQUE, name, group_type, is_active
wallets: id, family_id, owner_user_id NULL, name, type, initial_balance, currency, status
transactions: id, family_id, created_by_user_id, type, amount, description, note,
              transaction_date, status, source_wallet_id, destination_wallet_id,
              category_id, origin_chat_id, origin_message_id, original_message, confidence
ledger_entries: id, family_id, transaction_id, wallet_id, signed_amount, entry_date
google_integrations: id, family_id, reporting_year, spreadsheet_id, encrypted_credentials
```

`google_integrations` is unique on `(family_id, reporting_year)` so a workspace can retain its annual spreadsheet archive.

## Financial Invariants

- Amount is a positive integer in rupiah. Do not use floats.
- `EXPENSE` has a source wallet and one negative entry.
- `INCOME` has a destination wallet and one positive entry.
- `TRANSFER` has distinct source/destination wallets and exactly two entries whose signed sum is zero.
- Only `ACTIVE` transactions contribute ledger entries to balances.
- `VOIDED` and `SUPERSEDED` transactions remain stored.
- Corrections void or supersede the old transaction and create a new active transaction.
- A financial transaction, its entries, and its audit log commit in one database transaction.

## Balance Formulas

```text
wallet balance = initial_balance + SUM(active ledger_entries.signed_amount)
workspace net worth = SUM(wallet balances visible to the requester)
income/expense report = only ACTIVE transactions of matching type
```

Transfers are excluded from workspace income and expense reports.

## Indexes

```text
users(telegram_user_id)
family_members(family_id, user_id)
groups(telegram_chat_id)
wallets(family_id, status)
transactions(family_id, transaction_date DESC)
ledger_entries(family_id, wallet_id, entry_date)
audit_logs(family_id, entity_type, entity_id, created_at DESC)
```
