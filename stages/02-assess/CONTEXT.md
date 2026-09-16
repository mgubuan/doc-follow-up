# Stage 02: Assess Open Items

Scan the tracker and determine which items need follow-up today.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|--------------|---------------|-----|
| Tracker | `../../shared/tracker.csv` | All rows with status "Open" or "Returned" | The items to evaluate |
| Rules | `../../shared/follow-up-rules.md` | Full file | Follow-up schedule logic |

## Process

1. Read the tracker and filter to items with status "Open" or "Returned"
2. For each open item, calculate: days remaining until deadline, number of follow-ups already sent, date of last follow-up, whether a follow-up is due today based on the schedule
3. Check the hard ceiling: if any item has 4+ follow-ups with no response, flag it for phone call instead of email
4. Group items due for follow-up by client (one email per client)
5. For each client group, note which items are overdue vs. upcoming
6. Save the assessment to output/

## Checkpoint

| After Step | Agent Presents | Human Decides |
|------------|---------------|---------------|
| 5 | List of clients needing follow-up today, with item details and overdue/phone-call flags | Confirm the list, remove items, or add notes before drafting |

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Follow-up assessment | `output/follow-up-assessment-[date].md` | Grouped by client: items due, days remaining, overdue flags, phone call flags |
