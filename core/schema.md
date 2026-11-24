# Tracker schema

Version 1. A chat agent with no filesystem can follow this page. The same fields are the columns of the CSV, in this order. `core/schema.json` is the machine-readable copy.

One row is one document request. A request that has several pieces (two receipts, three W-2s) keeps those pieces in `lines` instead of hiding them in a note.

## Columns

| Column | Required | What it holds |
|---|---|---|
| `id` | yes | Stable id such as `REQ-014`. Do not reuse one. |
| `client_name` | yes | The client as the firm wrote it. Initials are allowed. Do not expand them. |
| `salutation` | no | First name or initials used in `Hi Mara,`. Blank means the draft says `Hello,`. Never copy this from the mailbox. |
| `contact_email` | no | Where a draft is addressed. Blank means ask. Do not invent one. |
| `contact_phone` | no | Used on a call note or a bad-contact note. Not a reason to email. |
| `doc_type` | no | Bank statement, invoice, W-2, and so on. Ask if the paste does not say. |
| `description` | yes | What is missing, in words a client can read. Specific: account last 4, vendor, form. |
| `period` | no | `2026-06`, `2025`, or `2026-06 to 2026-08`. Ask if a month has no year. |
| `amount` | no | A plain number (`14999` or `1842.16`). No `$` and no commas. Blank if the paste has no amount. |
| `client_reason` | no | Why the firm needs it, safe for the client to read. |
| `internal_notes` | no | Jokes, suspicions, staff comments, bounce details. Never placed in a draft. |
| `deadline` | yes | `YYYY-MM-DD`. |
| `status` | yes | One of the seven statuses below. |
| `owner_name` | no | The person at the firm who owns the chase. |
| `owner_title` | no | Their title, for the signature. Omit the line if it is blank. |
| `touches_sent` | yes | Emails already sent since the schedule anchor, including the initial. `0` if unknown. Calls do not count. |
| `last_touch` | no | `YYYY-MM-DD` of the last email, or blank. |
| `next_touch` | no | Leave blank on intake. The follow-up rules recompute it. A stored value is not authority. |
| `registered` | yes | `YYYY-MM-DD`. If the paste has none, use today and say you did. |
| `schedule_anchor` | no | Defaults to `registered`. Set to today when a return or a partial resets the cadence. |
| `received` | no | `YYYY-MM-DD` the latest file arrived, or blank. |
| `lines` | no | See below. |
| `client_replied` | no | `YYYY-MM-DD` a non-document reply paused the chase, or blank. |

## Statuses

| Status | Meaning | Email? |
|---|---|---|
| `Open` | Still missing. | When the plan says today. |
| `Partial` | Some lines arrived. Chase the open lines only. | When the plan says today. |
| `Received` | A file is in and a person has not reviewed it. | No. |
| `Accepted` | The person accepted it. Closed. | No. |
| `Returned` | The person sent it back. The rejection counts as today's touch. | After the two-business-day gap. |
| `Bad contact` | Bounce or wrong person. | No. Ask for a new email or phone. |
| `Call needed` | The email cap is used up and the deadline has passed. | No. Call. |
| `Paused` | The client replied, and a person has not read it yet. | No, until the chase is resumed. |

## Lines

Several pieces of one request live in `lines`, not in the notes.

CSV cell, semicolon between lines, pipe between fields:

```
Second Breakfast catering | 2026-08-03 | open; Elevenses Bakery | 2026-08-17 | received
```

Each piece is `label | period | open` or `label | period | received`. A draft lists the open ones only. A pre-check that covers some of them returns PARTIAL and does not close the rest.

## CSV

The header row is exactly the column names, in the order above. UTF-8. One request per data row. Amounts have no currency symbol. Dates have no time.

JSON, for a tool that prefers it, is `{ "schema_version": 1, "firm": { ... }, "items": [ ... ] }` with `lines` as an array of objects. See `schema.json`.

## What not to invent

If the paste is missing a deadline, a client name, a period, an email, or a document type, ask. Leave the field blank in the understood table. Do not guess a name from `info@`, a month from "Mar" alone, or an amount the user did not write.
