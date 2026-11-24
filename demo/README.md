# Demo firm

Northline Ledger Co. is a fictional bookkeeping and tax practice. The twelve clients are fictional. Mailboxes use `.example`.

`tracker.csv` stores dates as offsets from today (`+10d`, `-3d`, `0d`) and periods as `month:-1` or `year:-1`. Resolve them before assessing. `core/engine.py` does that with `resolve_tracker_text`. A chat agent follows `core/flows/one-shot.md`.

On a weekday the board always has something to send, including two Brightpath items in one email, and it always has items that are not overdue. On a weekend nothing is emailed. No deadline is more than three weeks in the past.

Northwind Outfitters has a blank salutation on purpose. The draft says `Hello,`. It does not turn `books@` into a name. The internal note on Brightpath is firm-only. It must not show up in the draft.

| Id | Client | What the row is for |
|---|---|---|
| DEMO-001, DEMO-002 | Brightpath Dental PLLC | Two items, one email. One of them carries a private note. |
| DEMO-003 | Cedarline Construction Inc | Initial still unsent. |
| DEMO-004 | Fieldnote Consulting LLC | 1099-NEC, on track. |
| DEMO-005 | Hearthside Bakery LLC | Partial. One vendor in, one still open. |
| DEMO-006 | Juniper Pediatrics PC | Overdue by a few days. One overdue email, not a call yet. |
| DEMO-007 | Keystone Property Group | Call needed. Do not email. |
| DEMO-008 | Lumen Studio LLC | Bad contact. The `ap@` address bounced. |
| DEMO-009 | Marlowe Finch LLP | Prior-year return, waiting. |
| DEMO-010 | Northwind Outfitters | Blank salutation. |
| DEMO-011 | Oak Street Cafe | Received, waiting for a person. |
| DEMO-012 | Parkside Veterinary Clinic | Accepted. |
| DEMO-013 | Redbird Logistics Inc | Comfortable, next touch still ahead. |

Firm signature, if a draft needs one:

| | |
|---|---|
| Name | Northline Ledger Co. |
| Email | hello@northline.example |
| Phone | 555-014-2200 |

Team: Avery Chen, Senior Bookkeeper. Jordan Ellis, Staff Accountant. Riley Okonkwo, Tax Associate. Morgan Hale, Client Manager.
