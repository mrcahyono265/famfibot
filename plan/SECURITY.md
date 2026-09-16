# Security Model

**Status:** APPROVED

## Trust Boundaries

| Boundary | Required control |
|---|---|
| Telegram to webhook | HTTPS and `X-Telegram-Bot-Api-Secret-Token` verification |
| User to workspace | Telegram identity plus active membership check |
| Workspace to data | `family_id` query scoping and PostgreSQL RLS |
| User to wallet/transaction | Permission service before every read/write |
| Backend to Google | Encrypted OAuth tokens and least-privilege scopes |
| Backend to DeepSeek | Minimal redacted context; no direct database tool access |

## Required Controls

- Validate every webhook payload and callback payload.
- Use `telegram_chat_id + origin_message_id` as an idempotency key for recorded messages.
- Use prepared SQLAlchemy queries; no string-concatenated SQL.
- Set database tenant/user context with `SET LOCAL` inside each request transaction for RLS policies.
- Encrypt Google OAuth refresh tokens at rest.
- Keep bot token, database URL, OAuth secrets, encryption key, and DeepSeek key in environment secrets.
- Redact sensitive information from logs.
- Apply rate limits to webhook, commands, and LLM fallback.
- Back up PostgreSQL and test restoration before production use.

## Privacy Constraint

A bot that processes ordinary messages in a Telegram group must receive those messages. Therefore financial recording groups must be separate from non-financial private conversation groups. The backend retains only messages needed for transaction processing and audit.
