# Stage 01: Register Request

Add a new documentation request to the master tracker.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|--------------|---------------|-----|
| User | (conversation) | Client name, what is needed, deadline, context | The request details |
| Tracker | `../../shared/tracker.csv` | Full file | Check for duplicates, get next ID |
| Reference | `references/document-types.md` | Matching document type | Submission instructions for this doc type |

## Process

1. Ask the user for: client name, document type, specific description of what is needed, why it is needed, deadline, and who on the team owns this request
2. Validate the document type against `references/document-types.md`. If it does not match a known type, confirm with the user
3. Check the tracker for duplicate requests (same client, same doc type, same date range). If a potential duplicate exists, flag it
4. Calculate the follow-up schedule based on the deadline using `../../shared/follow-up-rules.md`
5. Add a new row to `../../shared/tracker.csv` with status "Open", follow-ups sent "0", and the calculated next follow-up date
6. Save a registration summary to output/

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Registration summary | `output/[client-slug]-[doc-type]-registration.md` | Client, request details, deadline, follow-up schedule, assigned team member |
| Updated tracker | `../../shared/tracker.csv` | New row appended |
