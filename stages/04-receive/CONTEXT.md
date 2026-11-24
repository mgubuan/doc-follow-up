# Stage 04: Receive

Log a file a client sent and compare it with the request.

## Load

| Source | File |
|---|---|
| Rules | `core/safety.md`, `core/pre-check-rules.md`, `core/schema.md` |
| Tracker | `shared/tracker.csv` |
| The file | the attachment, when there is one |

Do not load stages 01–03 or 05.

## Process

1. If a file is attached, read it. A digital PDF with a text layer can be read by `extract_document` in `core/engine.py` (it uses pypdf). A scan with no text still has to be read by a person. Take the type, period, entity, account last 4, document number, and any sentence that names a different document. Do not invent a field the file does not show.
2. If the client has two or more open items, show the match and the other open items. Wait for confirmation before changing the tracker.
3. Run the check in `core/pre-check-rules.md`. The outcomes are MATCH, PARTIAL, MISMATCH, INCOMPLETE, and REQUEST_MAY_BE_WRONG.
4. Update the row the way that file says. A partial stays open for the remaining lines. A request that may be wrong is not turned into "please send the same number again."
5. On a partial, draft the thank-you for what arrived and ask only for the open lines. That thank-you is today's touch (`touches_sent` 1, `last_touch` today). Do not also queue a chase email.
6. On any other outcome, do not draft a client email. Review does that after a person decides. A reply that is not a file sets the item to Paused.

## Output

`output/[client-slug]-received-[YYYY-MM-DD].md` with the outcome, the evidence from the file, and whether a person still needs to confirm the match.
