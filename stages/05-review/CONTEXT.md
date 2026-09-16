# Stage 05: Review and Resolve

Review a received document and either accept it or reject it back to the client with specifics.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|--------------|---------------|-----|
| Receive log | `../04-receive/output/[matching file]` | Full file | Pre-check result and details |
| Tracker | `../../shared/tracker.csv` | Row matching this item | Full request context |
| Reference | `references/rejection-templates.md` | Full file | Friendly rejection email templates |
| Defaults | `../../shared/email-defaults.md` | Full file | Firm info and signature for rejection emails |

## Process

1. Present the receive log from Stage 04, including the pre-check result
2. Ask the reviewer for their decision: Accept, Reject (specify what is wrong), or Override (pre-check flagged it but it is actually correct)
3. Based on the decision:

**If Accept or Override:**
- Update tracker status to "Accepted"
- Record the acceptance date
- Item is closed. No further follow-ups

**If Reject:**
- Update tracker status to "Returned" (Open with history)
- Record what was wrong and what is still needed
- Auto-draft a friendly rejection email that thanks the client, explains what does not match, and restates what is needed
- Reset the follow-up schedule with updated context
- Save the rejection draft to output/

## Checkpoint

| After Step | Agent Presents | Human Decides |
|------------|---------------|---------------|
| 3 (Reject path only) | Draft rejection email | Edit, approve, or change decision to Accept |

## Audit (Reject path only)

| Check | Pass Condition |
|-------|---------------|
| Tone | Friendly and professional. Thanks the client. No blame |
| Specificity | States exactly what was wrong and exactly what is still needed |
| Instructions | Includes submission instructions |

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Review decision | `output/[client-slug]-review-[date].md` | Decision, reasoning, any rejection email draft |
| Updated tracker | `../../shared/tracker.csv` | Status changed to "Accepted" or "Returned" |
