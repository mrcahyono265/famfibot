# Family Finance Bot

Telegram-first, multi-workspace financial recording backend. Project requirements and approved architecture are in `plan/`.

## Phase 1

The current implementation provides PostgreSQL migrations, workspace/group setup, wallet and ledger models, ledger transaction rules, audit logs, health endpoint, and a protected Telegram webhook endpoint.

## VPS Deployment

1. Copy `.env.example` to `.env` and set strong values. Do not commit `.env`.
2. Keep `DATABASE_URL` host as `postgres` because API and PostgreSQL run in the same Compose network.
3. Build and start with `docker compose up -d --build`.
4. Verify locally from the VPS with `curl http://127.0.0.1:8000/health`.
5. Configure Nginx to proxy `https://famfibot.birrul.xyz` to `http://127.0.0.1:8000`.
6. Register Telegram's webhook with the HTTPS endpoint and the same `TELEGRAM_WEBHOOK_SECRET`.

Example Nginx location:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Telegram webhook target:

```text
https://famfibot.birrul.xyz/webhooks/telegram
```

Make the bot a group administrator before running `/setup`; Phase 2 natural-language group recording also requires the bot to receive ordinary group messages.

## Local Verification

```text
python -m pip install -e .
python -m pip install pytest
python -m pytest
```
