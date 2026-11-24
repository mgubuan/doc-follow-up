# Received-document check

Compare the file with the request. Read the file when one is attached. Take the type, the period, the entity, the account last 4, the document number, and any sentence that names a different document. Do not rely only on a description the user typed from memory. The check is advice. A person accepts, rejects, or overrides it.

If that client has two or more open items (Open, Partial, or Returned), show which request you matched and the other open items. Do not update the tracker until the person confirms the match.

## Outcomes

| Outcome | When | What happens to the request | What a later client email may ask for |
|---|---|---|---|
| `MATCH` | Type, period, entity, account last 4, and completeness agree. Every open line is covered. | Status `Received`. Chase email stops. | Nothing, until a person accepts or returns it. |
| `PARTIAL` | The file covers some lines and leaves others open. | Status `Partial`. Covered lines become `received`. Touch count resets to 0 and the schedule anchor becomes today. Chase continues for the open lines only. | Only the lines still open. Thank them for what arrived. |
| `MISMATCH` | Wrong type, wrong period, wrong entity, or wrong account. | Status `Received` so chase email stops until a person reviews. | The document that was actually requested. Do not ask again for the period or the account they just sent. |
| `INCOMPLETE` | Right document, pages missing or amounts cut off. | Status `Received` until a person reviews. | The complete file. |
| `REQUEST_MAY_BE_WRONG` | The document number matches the request, but the contents are a different thing, or the file names a different number for the thing you actually need. | Status `Received`. Do not draft a chase email. | Nothing until a person decides. If they agree the request was wrong, ask for the document the file points to. Do not ask the client to send the same number for the subject that does not exist. |

An approximate amount on the request (`about 847000`) does not fail a match against the exact total on the invoice. Amount is not one of the checks.

## How to tell REQUEST_MAY_BE_WRONG from a plain mismatch

A plain mismatch is "you sent May, we need June." The request is still right. Ask for June.

`REQUEST_MAY_BE_WRONG` is "the number we asked for is real, and it is the wrong document." The purchase-order fixture is the pattern:

- The request says PO #ELF-2021 for Lembas Bread.
- The file is PO #ELF-2021, and it is for Miruvor Wine.
- The file says the Lembas Bread PO is #ELF-2019, issued 2026-08-05.

The client email must not say "please send PO #ELF-2021 for Lembas Bread." That document is not the Lembas order. Show the person this, and let them correct the request to ELF-2019 before any client draft goes out. If they override and say the request really is ELF-2021 for Lembas, then a normal mismatch reply asks for that, because a person made the call.

## Partial lines

A request for "all of August, several vendors" is not one blob. The vendors are lines. When the August 3 receipt arrives and the August 17 receipt does not:

- Outcome `PARTIAL`.
- The August 3 line is `received`.
- The draft names the August 17 vendor only.
- The request does not become `Received`, and it does not stay a vague "send everything" chase.

## After the check

Do not email the client as part of the check. Save the outcome where the person will see it. Stage 05 (or the one-shot review step) is where a person accepts, rejects, or corrects the request. A rejection email thanks the client, says what arrived, and asks only for what is still needed. It does not quote internal notes.
