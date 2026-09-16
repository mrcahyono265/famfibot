# Architecture

**Status:** APPROVED

## Style

Use a modular monolith deployed on the private VPS. This is the smallest architecture that keeps the financial core independent from Telegram while avoiding premature distributed-system complexity.

```text
Telegram Group / Direct Chat
        -> FastAPI webhook adapter
        -> command and conversation handlers
        -> application services
        -> parser, permission, transaction, ledger, report services
        -> PostgreSQL
        -> background jobs for Sheets, PDF, and future DeepSeek fallback
```

## Boundaries

| Layer | Responsibility |
|---|---|
| `bot` | Telegram updates, commands, keyboards, and user-facing responses |
| `domain` | Workspace, member, wallet, transaction, ledger, permission, and report rules |
| `services` | Use cases that coordinate domain rules and persistence |
| `database` | SQLAlchemy models, migrations, repository/query helpers, and RLS setup |
| `workers` | Retriable non-financial side effects after a committed transaction |

Telegram handlers must not contain financial calculations or permission decisions.

## Core Transaction Flow

```text
message
-> resolve workspace and sender
-> parse / validate
-> resolve wallet and participants
-> authorize
-> request confirmation when needed
-> commit transaction, ledger entries, and audit log atomically
-> reply to Telegram
-> enqueue projection work
```

## Deployment

- FastAPI receives Telegram HTTPS webhooks on the VPS.
- PostgreSQL runs as a managed or local VPS service with backups.
- A single worker process handles Sheets synchronization and PDF generation.
- A reverse proxy terminates TLS.
- Secrets are injected as environment variables, never committed.

## Scaling

Start with one API process, one worker, and PostgreSQL. Add workers only when PDF or Sheets queues become slow. The ledger database remains the coordination point; do not split it into services without measured need.
