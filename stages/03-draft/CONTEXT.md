# Stage 03: Draft

Write one email per client who is due today. Drafts only.

## Load

| Source | File |
|---|---|
| Assessment | `stages/02-assess/output/` (the latest file) |
| Rules | `core/safety.md`, `core/tone-guide.md`, `core/email-templates.md`, `core/document-types.md` |
| Tracker | `shared/tracker.csv` (client-facing columns and the owner) |
| Firm | `shared/firm.md`, `shared/email-defaults.md` |

Do not load stages 01, 04, or 05. Do not put `internal_notes` into the prompt you draft from. If you have already read them, they still must not appear in the email.

## Process

1. One email per client. A mix of an initial and a reminder is still one email. The subject does not say which touch number it is.
2. List open lines only. Use `client_reason` as the only "why".
3. Overdue items get one factual sentence. Warmth stays the same.
4. Salutation from the field, or `Hello,`.
5. Run the internal-notes check. Fix a draft that fails it before showing it.
6. Show the drafts. A person edits and sends them. Do not send.
7. When they say a draft was sent, mark those items sent (`touches_sent` + 1, `last_touch` = today in the firm time zone, default America/Los_Angeles). Do not mark them sent just because you drafted them. Marking the same item again today does not count another email.

## Output

`output/[client-slug]-follow-up-[YYYY-MM-DD].md`

The `DRAFT` line stays above `To:`. Also write a call note or a bad-contact note for those lists. Those are internal. They are not emails.
