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

1. If a file is attached, read it. Take the type, period, entity, account last 4, document number, and any sentence that names a different document. Do not ask the user to retype what the file already says. They can correct a misread.
2. If the client has two or more open items, show the match and the other open items. Wait for confirmation before changing the tracker.
3. Run the check in `core/pre-check-rules.md`. The outcomes are MATCH, PARTIAL, MISMATCH, INCOMPLETE, and REQUEST_MAY_BE_WRONG.
4. Update the row the way that file says. A partial stays open for the remaining lines. A request that may be wrong is not turned into "please send the same number again."
5. Do not draft a client email here. Review does that after a person decides.

## Output

`output/[client-slug]-received-[YYYY-MM-DD].md` with the outcome, the evidence from the file, and whether a person still needs to confirm the match.
