# LOTR fixture

Internal regression data. Do not use it as the public demo. The public demo is `demo/`.

As-of date: **Monday 2026-09-14**.

## One tracker

There used to be two trackers. `shared/tracker.csv` had REQ-001 and REQ-003 as Accepted on 2026-09-15. `test-data/lotr-tracker.xlsx` still had them Open, with different registration dates and amounts written as `$847,000` versus `847000`. The spreadsheet was also full of Excel serial dates.

This CSV is the only copy. It is the morning of 2026-09-14, before the 2026-09-15 acceptance, so REQ-001 and REQ-003 are still Open. Dates are `YYYY-MM-DD`. Amounts are plain numbers. The spreadsheet is gone.

The old "next follow-up" column is not stored. The rules recompute it. Where the old files disagreed with the rules, the expected result is the rule:

| Row | What the old files did | What the rules say on 2026-09-14 |
|---|---|---|
| REQ-001 | Next touch 2026-09-14, which happens to match the plan slot | Plan slot Monday 2026-09-14. Last contact was Friday, so the two-business-day gap holds the email until Tuesday. |
| REQ-002 | Next touch was the initial, which matches | Initial on 2026-09-14. Not skipped. |
| REQ-003 | Open in the spreadsheet, accepted the next day in the CSV | Overdue email is waiting on the gap, because the last logged contact was Sunday. Not a call yet. |
| REQ-004 | Next touch Saturday 2026-09-19 | Monday 2026-09-21. |
| REQ-005 | Open, with "phone call" buried in the notes | Status `Call needed`. No email. |
| REQ-007 | Next touch 2026-09-21, skipping the initial | Initial on 2026-09-14. Salutation is blank, so the draft says Hello. |
| REQ-008 | Open, bounce buried in the notes, count already 4 | Status `Bad contact`. No email. |
| REQ-009 | Next touch 2026-09-15, and elevenses only in the notes | The plan slot is Monday 2026-09-14. The last contact was Saturday, so the gap holds the email until Tuesday. Both vendors are lines. |

Contact addresses in this fixture use `.example`. Monday 2026-09-07 is Labor Day, so it is not an email day.

## Documents

The PDFs in `documents/` are the traps:

- May versus June bank statement, same account ending 1111.
- PO #ELF-2021 is Miruvor Wine and says the Lembas order is PO #ELF-2019, issued 2026-08-05.
- Second Breakfast on August 3 and Elevenses on August 17, two lines of one request.
- Invoice #RCS-4087 and the insurance receipt, which match the requests they belong to.

`internal_notes` on these rows are the phrases that must never appear in a client draft.
