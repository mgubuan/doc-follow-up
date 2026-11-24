# Document types

Use this list when a request is registered and when a draft needs a submission line. Firm-specific types from setup are added to this list. They do not replace it.

`{{DOC_TYPES}}`

Default submission, used when the firm has not set its own:

`{{SUBMISSION_INSTRUCTIONS}}`

The default, if that placeholder is still empty, is: reply to the email with the file attached. Never ask for a password or a login.

If the client does not have the original, add the one alternative sentence for that type. Do not quote an internal note about how it was lost.

## Bank statement

- **Ask for:** bank name, account last 4, month.
- **Check:** bank, account last 4, month, all pages, beginning and ending balances.
- **If the original is not handy:** Download the PDF for that month from the bank's statement page. Do not send a login.

## Credit card statement

- **Ask for:** issuer, account last 4, month.
- **Check:** issuer, last 4, month, all pages.
- **If the original is not handy:** Download the PDF for that month from the card issuer. Do not send a login.

## Loan statement

- **Ask for:** lender, account last 4, statement date.
- **Check:** lender, last 4, the period requested.
- **If the original is not handy:** Download the latest statement from the lender, or ask the lender to resend it.

## Invoice

- **Ask for:** invoice number, vendor, date, amount if known.
- **Check:** invoice number, vendor, date, pages, amounts readable. An approximate amount on the request does not fail an exact total.
- **If the original is not handy:** Ask the vendor to resend the invoice.

## Receipt

- **Ask for:** vendor, date, amount, and each vendor as its own line when there are several.
- **Check:** vendor, date, amount. A stack of vendors is PARTIAL until every open line is in.
- **If the original is not handy:** Ask the vendor to resend or reissue the receipt.

## Purchase order

- **Ask for:** PO number, vendor, what was ordered.
- **Check:** the number and the goods. If the number matches and the goods do not, the outcome is REQUEST_MAY_BE_WRONG. Read the file for a sentence that names the other PO.
- **If the original is not handy:** Ask the vendor, or the person who issued the PO, to resend it.

## Contract

- **Ask for:** the parties, the kind of contract, about when it was signed.
- **Check:** pages, signatures, parties.
- **If the original is not handy:** Ask the other party for a signed copy if the original is missing.

## Forwarded email

- **Ask for:** who it was from, about when, the subject.
- **Check:** the thread is the one requested.
- **If the original is not handy:** Forward the original thread. A screenshot is harder to verify.

## Log

- **Ask for:** what log, the date range, the format.
- **Check:** the date range is covered and the file is readable.
- **If the original is not handy:** Export the log again from the system that created it.

## W-2

- **Ask for:** employer, employee, tax year.
- **Check:** the form is a W-2, the year matches, the employer matches.
- **If the original is not handy:** Download it from the employer or payroll provider, or ask them to reissue it.

## 1099-NEC

- **Ask for:** payer, recipient, tax year.
- **Check:** the form is 1099-NEC, the year matches, the payer matches.
- **If the original is not handy:** Download it from the payer's portal, or ask the payer to resend it.

## K-1

- **Ask for:** the entity, the partner or shareholder, the tax year.
- **Check:** the entity, the year, and that the pages are complete.
- **If the original is not handy:** Ask the partnership or its preparer to resend the K-1.

## Payroll report

- **Ask for:** the period and which report (register, certified payroll, 941).
- **Check:** the period and the report name.
- **If the original is not handy:** Export it again from the payroll provider. Do not send a login.

## Sales tax return

- **Ask for:** the state and the period.
- **Check:** the state, the period, and that it is the return rather than a payment receipt unless a receipt was requested.
- **If the original is not handy:** Download the filed return from the state portal, or the copy saved when it was filed.

## Prior-year return

- **Ask for:** the tax year and the return type.
- **Check:** the year and the taxpayer name.
- **If the original is not handy:** Use the copy that was saved when it was filed, or ask the prior preparer to resend it.

## 1098

- **Ask for:** the lender and the tax year.
- **Check:** the lender, the year, and the borrower.
- **If the original is not handy:** Download it from the lender.
