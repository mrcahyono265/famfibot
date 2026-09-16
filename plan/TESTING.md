# Testing Strategy

**Status:** APPROVED

## Required Test Layers

| Area | Essential checks |
|---|---|
| Ledger | Income, expense, transfer, correction, void, balance reconstruction |
| Tenant isolation | Workspace A cannot query or mutate workspace B |
| Permissions | Restricted member cannot view/use parent wallet or transaction |
| Idempotency | Replayed Telegram update creates no duplicate transaction |
| Parser | Indonesian amounts and basic intent classification |
| Telegram flows | Setup, direct-chat workspace selection, group context, confirmation |
| Reports | Transfers excluded from income/expense; privacy filtering retained |
| Integrations | Failed Sheets/PDF job cannot change committed financial state |

## Minimum Financial Test Cases

```text
initial balance 100000
expense 25000 -> balance 75000
income 50000 -> balance 125000
transfer 40000 between wallets -> total unchanged
void an expense -> original balance restored
repeat same Telegram message -> only one transaction
```

## Production Checks

- Health endpoint works.
- Webhook secret rejection is tested.
- Migration runs on empty database.
- Backup restoration is tested before real production data is accepted.
