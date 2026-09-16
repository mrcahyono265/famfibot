# Telegram Flows

**Status:** APPROVED

## Workspace Setup

```text
Admin adds bot to a financial Telegram group
-> admin sends /setup
-> bot verifies the sender is a Telegram group admin
-> create a new workspace or bind the group to an existing eligible workspace
-> creator becomes OWNER for a new workspace
```

## Group Context

Every linked group maps to one workspace. A message in the group automatically uses that workspace.

```text
General Keluarga Kecil: "Beli makan 25rb"
-> Keluarga Kecil context

Operasional Toko: "Beli stok 250rb"
-> Toko context
```

## Direct Chat Context

In direct chat the bot uses the user’s active workspace.

```text
User: "Beli makan 25rb"
Bot: "Pilih komunitas: Keluarga Orang Tua, Keluarga Kecil, Toko"
User selects Keluarga Kecil
Bot stores active workspace for this direct-chat session
```

`/ganti-komunitas` changes that active workspace.

## Recording Rules

- High-confidence rule-parser results may commit immediately.
- Missing wallet, unclear recipient, or ambiguous intent requires a question.
- Transfers at or above Rp500.000 require explicit confirmation.
- General-group confirmation omits private wallet and balance details.
- Direct-chat confirmation can show details only the user is authorized to see.

## Correction and Undo

```text
"Yang makan kemarin harusnya 75rb"
-> find authorized candidates
-> if multiple, show numbered candidates
-> user selects one
-> show correction summary
-> confirm
-> supersede old transaction, create correction, write audit log
```

`/undo` voids the last eligible transaction created by the requesting user after confirmation when required.
