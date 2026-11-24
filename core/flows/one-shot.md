# One-shot chase

Use this when the person pastes a list, uploads a CSV, or says `demo`, and they are not editing `shared/tracker.csv` by hand. Do the whole pass in the conversation. Do not write their client list into the repo. Hand the tracker back as a CSV they can download and paste in next time.

Read `core/safety.md`, `core/schema.md`, and `core/follow-up-rules.md` before you produce a draft.

## 1. Intake

Accept a paste, a CSV, or a short note per line (`Jones – still no March statement`). Tell them they can use initials instead of legal names.

Normalize every row onto the schema. Then show a table of what you understood, with these columns: id, client, salutation, email, document type, description, period, deadline, status.

In the same reply, list:

- questions for anything you did not know (missing deadline, missing email, missing period, unclear document type, a possible duplicate)
- assumptions you did make (`04/15/2026` read as month/day/year; a missing registration date set to today)
- a warning if you masked an SSN or an account number

Do not invent a client, a salutation, a period, an amount, or an email. A phone call mentioned in the paste is not an email touch. Leave `touches_sent` at 0 unless they said emails were sent, and tell them that.

`client_reason` is shown in the clear so they can see it. Ask them to confirm it is safe to send, and to move anything private into `internal_notes`. A column called Notes goes to `internal_notes`, not into the email.

Stop and wait for that confirmation when anything was ambiguous or masked. If they said the demo, the demo file is already confirmed. Skip the wait.

## 2. Resolve and assess

Resolve relative dates against today. Recompute the next touch from the follow-up rules. Do not trust a next-touch column that came in with the paste.

Group the result:

- email today (one group per client)
- call needed
- bad contact
- waiting
- received, waiting for review
- accepted

Say which rule fired, in one line per item ("initial is due today", "next email is Monday because Saturday is not a business day", "cap reached after the deadline").

## 3. Drafts

Draft one email per client who is due today, from `core/email-templates.md`. Run the internal-notes check. Drop any draft that fails it and fix it before showing it.

Do not draft an email for Call needed, Bad contact, Received, or Accepted. Show the internal call note or the bad-contact note instead.

## 4. Hand back the tracker

Return the full tracker as CSV in the schema column order, with computed `next_touch` values and ISO dates. Remind them this is the file to paste next time.

Print this line once, above the kit, not inside a client email:

This is operational workflow design for collecting client documents. It is not tax, legal, or accounting advice.

## Demo

When they say `demo`, resolve `demo/tracker.csv` against today and run steps 2 through 4 for Northline Ledger Co. Do not ask them to set the firm up first. The understood table is the resolved demo, and you may say it is the sample firm rather than their clients.
