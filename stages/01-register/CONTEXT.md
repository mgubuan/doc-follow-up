# Stage 01: Register

Add requests to `shared/tracker.csv`. For a paste or a CSV the person will not keep in this repo, use `core/flows/one-shot.md` instead and do not write the tracker.

## Load

| Source | File |
|---|---|
| Rules | `core/safety.md`, `core/schema.md`, `core/follow-up-rules.md` |
| Types | `core/document-types.md` and `shared/firm.md` |
| Tracker | `shared/tracker.csv` |

Do not load stages 02–05.

## Process

1. Take one request or a pasted list. Map it onto the schema. Show the understood table from the one-shot flow and ask about blanks. Do not invent a salutation, period, amount, or email.
2. Put private comments in `internal_notes`. Put only what a client may read in `client_reason` and `description`. Several vendors or forms go in `lines`, not in the notes.
3. Check for a duplicate (same client, type, period, and description).
4. Compute the tier and the planned dates from `core/follow-up-rules.md`. The anchor is the registration date. `touches_sent` is 0. `next_touch` is the first planned business day.
5. Append the row. Status is `Open` unless they already know it is a bad contact.
6. Save a short registration note to `output/`.

## Output

`output/[client-slug]-[doc-type]-registration.md` with the client, the client-facing description, the deadline, the tier, the planned dates, and the owner.
