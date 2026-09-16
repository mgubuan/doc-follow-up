# Stage 03: Draft Follow-Up Emails

Write contextual follow-up emails for each client with items due today.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|--------------|---------------|-----|
| Assessment | `../02-assess/output/follow-up-assessment-*.md` | Most recent file | Which clients need follow-up and what items |
| Tracker | `../../shared/tracker.csv` | Rows matching assessed items | Full context for each request |
| Defaults | `../../shared/email-defaults.md` | Full file | Firm name, sender info, signature |
| Reference | `references/email-templates.md` | Template matching follow-up number | Email structure |
| Reference | `references/tone-guide.md` | Full file | Voice and tone rules |
| Doc types | `../01-register/references/document-types.md` | Matching types | Submission instructions to include |

## Process

1. Read the most recent assessment from Stage 02
2. For each client group, draft ONE email that covers all their open items
3. For each item in the email: reference the specific document by name and date range, include submission instructions, acknowledge overdue items if applicable, reference previous submissions if this is a re-request after a Returned item
4. Include the follow-up number in the subject line
5. Use the sender name and signature from the assigned team member
6. Run the audit checks below
7. Save each draft email to output/

## Checkpoint

| After Step | Agent Presents | Human Decides |
|------------|---------------|---------------|
| 5 | Draft emails for each client | Edit tone, add details, approve for sending, or hold |

## Audit

| Check | Pass Condition |
|-------|---------------|
| Tone | Friendly and professional throughout. No passive aggression, guilt, or punitive language |
| Specificity | Every requested document is named with its exact type, date range, and any special instructions |
| Overdue acknowledgment | Any overdue item is acknowledged with impact explanation |
| Submission instructions | Clear instructions for how to send each document |
| Length | Under 200 words per email (excluding checklists) |
| Grouping | One email per client, never multiple emails to the same client on the same day |

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Draft emails | `output/[client-slug]-follow-up-[date].md` | Complete email ready to send: subject, body, signature |
