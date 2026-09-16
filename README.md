# Family Finance Bot

Telegram-first, multi-workspace financial recording backend. Project requirements and approved architecture are in `plan/`.

## Phase 1

The current implementation provides PostgreSQL migrations, workspace/group setup, private wallet and balance commands, wallet/ledger models, ledger transaction rules, audit logs, health endpoint, and a protected Telegram webhook endpoint.

## VPS Deployment

1. Copy `.env.example` to `.env` and set strong values. Do not commit `.env`.
2. Keep `DATABASE_URL` host as `postgres` because API and PostgreSQL run in the same Compose network.
3. Build and start with `docker compose up -d --build`.
4. Verify through the public proxy with `curl https://famfibot.birrul.xyz/health`.
5. Connect the API container to the external Docker proxy network used by Nginx.
6. Register Telegram's webhook with the HTTPS endpoint and the same `TELEGRAM_WEBHOOK_SECRET`.

Telegram webhook target:

```text
https://famfibot.birrul.xyz/webhooks/telegram
```

Make the bot a group administrator before running `/setup`; Phase 2 natural-language group recording also requires the bot to receive ordinary group messages.

## Current Commands

Run `/setup` in a Telegram financial group as a Telegram group admin. Wallet and balance data are intentionally private and only work in a direct chat with the bot.

```text
/start
/ganti-komunitas
/wallet
/wallet tambah Cash Budi CASH 100000
/saldo
/masuk 7000000 Gaji September
/keluar 25000 Makan siang
/transfer 300000 ke Ibu
/cek
/laporan
/undo
/export-laporan-pdf
```

Natural input is supported after a default wallet exists, for example `Beli makan 25rb`, `Gaji 7jt`, and `Transfer 300rb ke Ibu`. Transfers at or above Rp500.000 require a `Ya` confirmation. Set `DEEPSEEK_API_KEY` only when rule-based parsing needs optional fallback.

## Local Verification

```text
python -m pip install -e .
python -m pip install pytest
python -m pytest
```
