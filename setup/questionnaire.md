# Onboarding Questionnaire: Client Documentation Follow-Up

Read this file when the user types "setup". Ask ALL questions below in a single conversational pass. These configure the system, not a specific request.

---

### Q1: What is your firm name?
- Placeholder: `{{FIRM_NAME}}`
- Files: `shared/email-defaults.md`, `stages/03-draft/references/email-templates.md`
- Type: free text

### Q2: What is your firm's email address?
- Placeholder: `{{FIRM_EMAIL}}`
- Files: `shared/email-defaults.md`
- Type: free text

### Q3: What is your firm's phone number?
- Placeholder: `{{FIRM_PHONE}}`
- Files: `shared/email-defaults.md`
- Type: free text

### Q4: Who are your team members? (Name and title for each)
- Placeholder: `{{TEAM_MEMBERS}}`
- Files: `shared/email-defaults.md`
- Type: free text
- Example: "Sarah Chen, Lead Bookkeeper / Mike Torres, Staff Bookkeeper / Lisa Park, Account Manager"

### Q5: What document types do you most commonly request from clients?
- Placeholder: `{{DOC_TYPES}}`
- Files: `stages/01-register/references/document-types.md`
- Type: free text
- Default: Invoice copies, receipt copies, forwarded emails, bank statements, logs, contracts, purchase orders

### Q6: Do your clients have specific submission instructions?
- Placeholder: `{{SUBMISSION_INSTRUCTIONS}}`
- Files: `stages/01-register/references/document-types.md`
- Type: free text
- Default: Reply to the requesting email with attachments

---

## After Onboarding

Replace all placeholders across workspace files. Then tell the user:

"You are set up. Your documentation follow-up system is configured for [firm name] with [N] team members. To get started, type 'register' to add a documentation request, or 'status' to see the current tracker."
