# Pre-Check Rules

When a document is received, compare it against the original request.

## Check 1: Document Type Match
Does the received document match the requested type?
- Requested bank statement, received credit card statement = MISMATCH
- Requested invoice, received receipt = MISMATCH

## Check 2: Date Range Match
Does the document cover the requested period?
- Requested June statement, received May = MISMATCH
- Requested Q2, received only April = PARTIAL MISMATCH

## Check 3: Entity Match
Is the document for the correct business entity or account?
- Requested Business Account 4521, received Personal Account 7890 = MISMATCH

## Check 4: Completeness
Does the document appear complete?
- Statement missing pages = INCOMPLETE
- Invoice with amounts cut off = INCOMPLETE

## Flagging
- ALL checks pass: flag as MATCH
- ANY check fails: flag as MISMATCH with specific discrepancy
- Only completeness fails: flag as INCOMPLETE

## Important
The pre-check is advisory. The human reviewer in Stage 05 makes the final call.
