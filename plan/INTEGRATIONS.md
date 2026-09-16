# Google Sheets, PDF, and AI Integrations

**Status:** APPROVED

## Google Sheets

PostgreSQL is authoritative. Google Sheets only receives committed data projections.

```text
PostgreSQL commit
-> queue sync job
-> write spreadsheet
-> retry transient failures
-> record persistent failure
```

Each workspace has one spreadsheet per calendar year. The backend creates the next year's spreadsheet on the first transaction of that year and notifies the workspace admin.

```text
Keluarga Kecil - Keuangan 2026
|- Rekap Bulanan
|- Januari
|- Februari
`- Other month tabs, created only when they receive a transaction
```

`Rekap Bulanan` contains month, income, expense, net cash flow, and ending balance. Each monthly tab contains only these columns:

```text
Tanggal | Masuk | Keluar | Keterangan | Sumber | User | Saldo | Catatan
```

`Sumber` is the affected wallet. `Saldo` is that wallet's balance after the row, not a workspace-wide balance. A transfer is projected as two rows so both wallet movements and balances are clear.

The backend calculates and writes all balances. A correction or backdated transaction refreshes the affected monthly tab so its running wallet balances remain accurate.

The main spreadsheet is shared only with OWNER/ADMIN users allowed to see the complete workspace data. Google Sheets cannot safely provide row-level privacy. Any limited user view requires a separate filtered spreadsheet in a later phase.

## PDF

PDF is generated on demand with ReportLab.

```text
Portrait pages: workspace, period, income, expense, cash flow, categories, allowed balances
Last landscape page: authorized transaction table
```

The report query is permission-filtered before rendering. The renderer must never receive unauthorized rows.

## DeepSeek

DeepSeek is Phase 6 fallback only. It receives only the input message and minimal authorized context: current date, relevant member names, relevant wallet names, and strict JSON output schema.

DeepSeek must not:

- Receive full chat history by default.
- Receive OAuth credentials or secrets.
- Read/write PostgreSQL.
- Commit a transaction without schema validation, business rules, authorization, and confirmation handling.
