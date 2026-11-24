# Stage 02: Assess

Decide what needs a person today.

## Load

| Source | File |
|---|---|
| Rules | `core/safety.md`, `core/follow-up-rules.md` |
| Tracker | `shared/tracker.csv` |

Do not load stages 01 or 03–05.

## Process

1. Read every row. Recompute the next action. Ignore a stored `next_touch` when it disagrees with the rules.
2. Email today: Open, Partial, and Returned items whose next planned email is today or earlier, and today is a business day.
3. Call needed and Bad contact are listed separately. They do not get an email.
4. Received waits for review. Accepted is closed.
5. Group email items by client. One group per client.
6. Show the list and wait for the person to confirm it before drafting.

## Output

`output/follow-up-assessment-[YYYY-MM-DD].md`

Per client due today: the items, the email kind (initial, reminder, or overdue), and the deadline. Then the call list, the bad-contact list, and the items that are waiting.
