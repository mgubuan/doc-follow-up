# Client Documentation Follow-Up

Manage open documentation requests across a bookkeeping team: register what you need, track deadlines, draft follow-up emails, and close the loop when documents arrive.

The rules live in `core/`. This file is the Claude Code entry point. A chat-only agent with no filesystem follows `core/README.md` and `core/flows/one-shot.md` instead.

Load `core/safety.md` for every task.

## Folder map

```
doc-follow-up/
├── CLAUDE.md
├── CONTEXT.md
├── core/                  rules, schema, one-shot flow, reference engine
├── demo/                  12-client sample firm, dates relative to today
├── setup/questionnaire.md
├── shared/
│   ├── firm.md            the only setup store
│   ├── tracker.csv        local working tracker (header until you add rows)
│   ├── follow-up-rules.md pointer to core
│   └── email-defaults.md
├── stages/01–05           local pipeline on top of core
└── tests/                 LOTR regression fixture and run_tests.py
```

## Triggers

| Keyword | Action |
|---|---|
| `setup` | `setup/questionnaire.md`. Optional. Does not block `demo`. |
| `demo` | Resolve `demo/tracker.csv` against today and run `core/flows/one-shot.md`. |
| `one-shot` | Paste or upload a list. Follow `core/flows/one-shot.md`. Do not write their clients into the repo. |
| `status` | Count the local tracker. See below. |
| `register` | `stages/01-register/CONTEXT.md` |
| `assess` | `stages/02-assess/CONTEXT.md` |
| `draft` | `stages/03-draft/CONTEXT.md` |
| `received` | `stages/04-receive/CONTEXT.md` |
| `review` | `stages/05-review/CONTEXT.md` |

### How `status` works

Read `shared/tracker.csv`. Count rows by status: Open, Partial, Received, Accepted, Returned, Bad contact, Call needed. For Open, Partial, and Returned, recompute the next action from `core/follow-up-rules.md`. Render:

```
Documentation tracker: [firm name from shared/firm.md]

Open: X (Y due for email today)
Partial: X
Received (pending review): X
Accepted: X
Returned: X
Bad contact: X
Call needed: X

Due for email today:
  - [Client] — [doc type] — [description] — deadline [YYYY-MM-DD]
Call, do not email:
  - [Client] — [doc type]
Bad contact, do not email:
  - [Client] — [doc type]
```

## What to load

| Task | Load | Do not load |
|---|---|---|
| Any task | `core/safety.md` | |
| Register | `shared/tracker.csv`, `core/schema.md`, `core/follow-up-rules.md`, `core/document-types.md`, `shared/firm.md` | Stages 02–05 |
| Assess | `shared/tracker.csv`, `core/follow-up-rules.md` | Stages 01, 03–05 |
| Draft | latest `stages/02-assess/output/*`, `shared/tracker.csv` (not `internal_notes`), `shared/firm.md`, `core/email-templates.md`, `core/tone-guide.md`, `core/document-types.md` | Stages 01, 04–05 |
| Receive | `shared/tracker.csv`, `core/pre-check-rules.md`, the attached file | Stages 01–03, 05 |
| Review | `stages/04-receive/output/*`, `shared/tracker.csv`, `core/email-templates.md`, `core/pre-check-rules.md` | Stages 01–03 |

## Stage handoffs

Stages run in any order. The local tracker connects them.

- Stage 01 appends rows.
- Stage 02 reads and does not trust a stored next-touch over the rules.
- Stage 03 drafts. It does not send.
- Stage 04 sets Received, or Partial when only some lines arrived.
- Stage 05 sets Accepted, or Returned (touch count back to 0, anchor today).
