# doc-follow-up

A bookkeeping or tax firm is waiting on client documents. This repo decides who to contact today, drafts the email, and checks a file that comes back before anyone treats it as done.

Two ways to use it:

- **Chat, no clone required.** Follow `core/`. Paste a list or say `demo`. The tracker comes back as a CSV. Nothing is stored.
- **Claude Code.** Open this folder. The `stages/` pipeline reads the same core and keeps a local tracker in `shared/tracker.csv`.

## Layout

```
core/          schema, safety, follow-up rules, templates, one-shot flow
demo/          fictional 12-client firm, dates relative to today
shared/        local firm profile and working tracker
stages/        register, assess, draft, receive, review
tests/         regression suite, including the old sample as a fixture
```

## Try it

In a chat agent pointed at `core/`, say `demo`. You get a mixed board for Northline Ledger Co.: items due today, items on track, one recent overdue, a call, a bad contact, a partial, a file waiting for review, and one accepted item. Dates are offsets from today, so the board does not age into an all-overdue list.

Or paste a list. The agent shows what it understood, asks about gaps, and hands back drafts plus a CSV.

`setup` is optional. It only fills `shared/firm.md` (name, reply-to, phone, team with titles, extra document types, how clients send files).

## Tests

```bash
python3 -m pip install -r requirements.txt
python3 tests/run_tests.py
```

`requirements.txt` includes `pypdf`. The engine uses it to read text from a digital PDF during the received-file check. A scanned image with no text layer is not read that way. You still tell the agent what a scan says, or a person opens it.

The suite checks the worked examples in `core/follow-up-rules.md` against `core/engine.py`, the fixture in `tests/fixtures/lotr/` as of 2026-09-14 (the engine reads those PDFs), privacy masking, mark-sent, the two-business-day gap, and the demo firm on every day of 2026 including federal holidays.

"Today" is the date in `America/Los_Angeles` unless the firm sets another time zone. `shared/tracker.csv` is gitignored so a working client list is not committed. The empty header is `shared/tracker.template.csv`. Copy it to `shared/tracker.csv` to start.

## Rules that do not change

- The cadence comes from the deadline, not a priority label.
- The initial email counts as touch 1. At most four emails. Then a phone call, and not before the deadline.
- One email per client per day. No email on a weekend.
- Drafts only. A person sends them.
- A received file is checked for type, period, entity, and completeness before it is accepted. Some lines can arrive without closing the rest. A file that shows the request itself is wrong is flagged that way, instead of asking the client for a document that does not exist.

## License

MIT. See `LICENSE`.
