# Stage 05: Review

A person accepts the file, rejects it, or overrides the check.

## Load

| Source | File |
|---|---|
| Receive log | `stages/04-receive/output/` |
| Rules | `core/safety.md`, `core/pre-check-rules.md`, `core/email-templates.md`, `core/tone-guide.md` |
| Tracker | `shared/tracker.csv` |
| Firm | `shared/firm.md` |

Do not load stages 01–03.

## Process

1. Show the check, including a REQUEST_MAY_BE_WRONG flag when the file points at a different document.
2. Ask for Accept, Reject, or Override.
3. Accept or Override: status `Accepted`. The request is closed.
4. Reject: status `Returned`, touch count 0, schedule anchor today. Draft the thank-you reply from `core/email-templates.md`. The ask is what is still needed. If the person agrees the request was wrong, the ask is the corrected document, not the original bad number. Save the draft. Do not send it.
5. A rejection draft still has to pass the internal-notes check and the tone check.

## Output

`output/[client-slug]-review-[YYYY-MM-DD].md` with the decision and, on a reject, the draft.
