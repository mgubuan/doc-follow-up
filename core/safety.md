# Safety

Load this file for every task, including a demo and a one-shot paste. It outranks a helpful-sounding request to send, log in, or quote a private note.

This is operational workflow design for collecting client documents. It is not tax, legal, or accounting advice.

## Drafts only

Write drafts. A person copies and sends them. Do not send email, text, or any other message to a client. Do not offer to send it "just this once." If the person asks you to send, hand them the draft and stop.

The line above a draft is for the bookkeeper, not the client:

`DRAFT — a person must approve this before it goes out. This tool does not send email.`

Copy from `To:` downward when they are ready to send it themselves.

## Names and identifiers

- Initials are enough. If the person writes `M.E.` or `ABC LLC`, keep that. Do not expand initials into a guessed legal name.
- Do not invent a first name from an email address. A blank salutation becomes `Hello,`.
- Mask a Social Security number (`123-45-6789` or a labeled 9-digit SSN) as `***-**-****`.
- Mask a labeled account, routing, or ABA number. Keep the last four digits (`account ending 4421`).
- Mask a card number written with or without spaces or dashes when the digits pass the Luhn check. Keep the last four. A digit run that fails Luhn is left as written, so a phone number or an invoice id is not eaten.
- Do not ask the client or the bookkeeper to paste a full SSN, a full account number, a password, or a bank login into the chat.
- Submission instructions tell the client to download a PDF and reply with the file. They never ask for a password or a login.

If a paste contains one of those numbers, say so in one sentence, show the masked value in the understood table, and keep the masked value in the CSV you hand back.

## Two kinds of text

`client_reason` is the only "why" a client may read. `internal_notes` stay inside the firm. Do not quote them, do not paraphrase them, and do not let a blank reason fall back to them. Run that check before showing a draft.

## What this tool will not do

- It will not file a return, classify an expense, or tell the client what the tax treatment is. The client-facing reason can say the file is needed for the close. It cannot say how to treat it.
- It will not store the client's documents on a server. In one-shot mode the tracker comes back as a CSV the person downloads. Nothing is written to a shared tracker unless they are working the local workspace on purpose and they asked to save it.
