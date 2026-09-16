# Stage 04: Receive and Pre-Check

Log an incoming document from a client and automatically compare it against the original request.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|--------------|---------------|-----|
| User | (conversation) | What was received, from which client | The incoming document details |
| Tracker | `../../shared/tracker.csv` | Rows matching this client with status "Open" or "Returned" | Find the original request to compare against |
| Reference | `references/pre-check-rules.md` | Full file | What to verify in the comparison |

## Process

1. Ask the user: which client sent something, and what did they send (document type, date range, any details visible)
2. Look up the client's open requests in the tracker
3. Match the received document to the most likely open request
4. Run the pre-check comparison: document type match, date range match, entity match, completeness
5. Update the tracker: set status to "Received" and record the received date. Follow-ups stop immediately
6. Flag the pre-check result: MATCH ("This appears to match the request -- please confirm") or MISMATCH (describe the specific discrepancy)
7. Save the receive log to output/

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Receive log | `output/[client-slug]-received-[date].md` | What was received, pre-check result (match/mismatch with details), assigned reviewer |
| Updated tracker | `../../shared/tracker.csv` | Status changed to "Received", received date recorded |
