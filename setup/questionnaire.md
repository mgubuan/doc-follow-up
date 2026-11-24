# Setup

Run this when the user types `setup`. Setup is optional. `demo` and `one-shot` work before any answer is saved. Ask these questions when they want a signature and a firm profile, not as a gate in front of the first result.

Write every answer into `shared/firm.md` and nowhere else. That file is the only setup store. After writing, read it back. If any `{{...}}` placeholder is still there, say which question was not saved and ask it again.

## Questions

### Q1. What is the firm name?
- Placeholder: `{{FIRM_NAME}}`
- Store: `shared/firm.md`

### Q2. What email should clients reply to?
- Placeholder: `{{FIRM_EMAIL}}`
- Store: `shared/firm.md`

### Q3. What phone number should the signature show?
- Placeholder: `{{FIRM_PHONE}}`
- Store: `shared/firm.md`

### Q4. Who on the team sends these, and what is each person's title?
- Placeholder: `{{TEAM_MEMBERS}}`
- Store: `shared/firm.md`, one `Name | Title` line per person
- Example: `Avery Chen | Senior Bookkeeper`

### Q5. Which document types should be added to the standard list?
- Placeholder: `{{DOC_TYPES}}`
- Store: `shared/firm.md`
- The standard list is `core/document-types.md`. This answer is added to it. It does not replace it.

### Q6. How should clients send files?
- Placeholder: `{{SUBMISSION_INSTRUCTIONS}}`
- Store: `shared/firm.md`
- Default, if they have no preference: reply to the email with the file attached. Do not record an instruction that asks for a password or a login.

## After the answers are stored

Tell them the profile is saved, how many people are on the team, and that the next step is `demo`, a paste of their list, or `register` if they are working in the local tracker.
