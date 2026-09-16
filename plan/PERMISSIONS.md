# Permissions and Privacy

**Status:** APPROVED

## Roles

| Role | Capability |
|---|---|
| `OWNER` | Workspace configuration, integrations, groups, membership, wallets, and authorized corrections |
| `ADMIN` | Member/wallet management and authorized reports/corrections |
| `MEMBER` | Record and view allowed financial data |
| `VIEWER` | View allowed financial data only |

Role is not blanket permission to view private money. Every wallet and transaction also requires access evaluation.

## Wallet Access

- Personal wallet: owner plus explicit grants.
- Child wallet: child and authorized parents.
- Parents wallet: owner plus authorized parents.
- Shared wallet: eligible workspace members.
- A user must have write access to use a wallet as a transaction source or destination.

## Transaction Visibility

| Visibility | Read access |
|---|---|
| `PRIVATE` | Creator, owner, and explicit grants |
| `INVOLVED` | Creator, participants, and explicit grants |
| `GROUP` | Explicit group members and grants |
| `FAMILY` | Eligible workspace members and grants |

## Default Policies

| Context | Default readers |
|---|---|
| Child transaction in General | Child recorder and authorized Parents |
| Shared transaction in General | General group members |
| Transaction in Parents | Parents group members |
| Parent personal wallet | Owner and explicit parent grants |

## Enforcement

Every read path uses the same permission service: Telegram commands, transaction search, balance, reports, Google Sheets, and PDF. Denials must not disclose whether an inaccessible resource exists.
