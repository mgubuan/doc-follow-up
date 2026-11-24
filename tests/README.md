# Tests

```bash
python3 -m pip install -r requirements.txt
python3 tests/run_tests.py
```

`pypdf` is only used to read the fixture PDFs. The date rules, the tracker, the drafts, and the masking use the standard library.

What the run checks:

- Every worked example in `core/follow-up-rules.md` matches `core/engine.py`.
- Halfway of an 11-day window is day 5. A holiday is not an email day. The tier is not recomputed when the window shrinks. A stored `next_touch` is ignored.
- The call flag does not fire on or before the deadline. A bounce stays Bad contact.
- `tests/fixtures/lotr/` as of Monday 2026-09-14: who is emailed, who is grouped, who is called, whose address is dead, and that internal notes are absent from drafts.
- The purchase-order PDF is PO #ELF-2021 for Miruvor and points at Lembas as ELF-2019. The check must not ask for ELF-2021 again. The May statement does not satisfy the June request. One catering receipt does not close both lines.
- SSNs and account numbers are masked. A paste does not invent a name, a period, or an amount. "Called twice" is not two email touches.
- `demo/tracker.csv`, resolved on every day of 2026, is never an all-overdue board and never emails on a weekend.

The Lord of the Rings material is a fixture, not the public demo. See `tests/fixtures/lotr/README.md`.
