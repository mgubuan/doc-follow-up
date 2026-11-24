# Email templates

Neutral placeholders. A later copy pass will replace the wording. Do not add a touch count, a firm-name prefix, or a `--` separator to the subject.

The `DRAFT` line is for the bookkeeper. Copy from `To:` down when a person is ready to send it themselves. This tool does not send email.

`[client_reason]` is the client-facing reason only. If it is blank, write "Needed for the books on file." Never substitute internal notes.

`[Greeting]` is `Hi [salutation],` or `Hello,` when the salutation is blank.

A first request says "We need the documents below." A later one says "We still need the documents below."

Write dates as `Thursday, September 24, 2026` and periods as `October 2026`. Write amounts as `$14,999`. If the row has no sender, sign with the firm name and tell the bookkeeper setup is incomplete. Never print `[Sender Name]`.

Include `How to send:` with the firm's submission line, or "Reply to this email with the file attached."

## One client, one or more items

Use this shape for an initial request, a reminder, and a mix of the two in the same email. The subject does not say which touch it is.

Subject when nothing in the email is overdue: `Documents needed: [period and type, or "N documents"]`

Subject when any item is overdue: `Deadline passed: [period and type, or "N documents"]`

```
[DRAFT line for the bookkeeper]

To: [contact_email]
Subject: [subject above]

[Greeting]

Hope you are doing well. We still need the documents below.

- [doc_type]: [description]
  Still missing: [open lines only, when the request has lines]
  Why we need it: [client_reason]
  Amount on file: [amount, only if the row has one]
  If the original is not handy: [one sentence from the document-type list]
  Deadline on file: [YYYY-MM-DD]

Please reply to this email with the files attached.

Thank you,

[owner_name]
[owner_title]
[firm name]
[firm phone]
[firm email]
```

When any item is overdue, add one sentence after the list:

`The deadline has passed for: [type] (deadline [date]). Without those files, this work is held up: [client_reason]`

Omit `[owner_title]` when the row has none. Do not leave the bracket in the email.

## After a person rejects a file

```
[Greeting]

Thank you for sending [what arrived].

We still need [what is still needed].

Please reply to this email with the file attached.
```

`[what is still needed]` is the corrected ask. If the check said `REQUEST_MAY_BE_WRONG` and the person agreed, this is the document the file pointed to, not the original number.

## Internal notes, not emails

**Call needed**

```
CALL — do not email [client].
Phone: [contact_phone, or "no phone on file — ask the firm for one before calling"]
Item: [id, type, description]
Deadline on file: [date]
Emails already sent: [touches_sent]
Say which documents are missing, the deadline on file, and where to send the files.
```

**Bad contact**

```
BAD CONTACT — do not email [address].
Ask the firm for a working email or phone.
Item: [id, type, description]
```
