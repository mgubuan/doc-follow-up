# Follow-up rules

One variable sets the cadence: how many calendar days sit between the schedule anchor and the deadline. There is no subjective priority label. These rules are the source of truth for every surface. `core/engine.py` computes the same dates, and `tests/run_tests.py` fails if the worked examples below drift.

## Stored dates

Every stored date is `YYYY-MM-DD`. Do not write `MM/DD/YYYY`. A pasted `04/15/2026` is read as month/day/year and shown back as `2026-04-15` before anything is saved, so the user can correct it.

"Today" is the date the person is working. A demo file may store offsets (`+6d`, `-9d`, `0d`) and period tokens (`month:-1`, `year:-1`). Resolve those against today before applying the rules. `month:-1` is the previous calendar month. `year:-1` is the previous calendar year.

## Business days

A business day is Monday through Friday, excluding US federal holidays (New Year's Day, Martin Luther King Jr. Day, Washington's Birthday, Memorial Day, Juneteenth, Independence Day, Labor Day, Columbus Day, Veterans Day, Thanksgiving, and Christmas, with the usual Saturday-to-Friday and Sunday-to-Monday observation). A firm may add more dates. It cannot turn a federal holiday into a send day.

"Today" is the date in the firm's time zone. The default is `America/Los_Angeles`. A firm can set another IANA zone. A clock time with no zone is read as UTC, then converted.

When a computed date is not a business day, move it forward to the next business day if that day is still strictly before the deadline. Otherwise move it backward to the previous business day. If it still cannot land strictly before the deadline, drop that touch. Two anchors that land on the same business day become one email.

The day after the deadline follows the same weekend rule, forward only: if the deadline is Saturday, the overdue email is Monday.

## What a touch is

A touch is one outbound email that asks the client for this item.

- The initial request is touch 1. It is not free, and it is not skipped.
- A later reminder is the next touch.
- One email that lists several items counts as one touch on each item it includes.
- A phone call, a text, a bounce, an internal note, and a document the client sends are not touches.

`touches_sent` is how many of those emails have already gone out since the schedule anchor. The cap is 4. Do not send a fifth chase email. Some calendars fit fewer than 4 because weekend dates merge. The call flag follows the last planned email. It does not wait around for a fourth email that the calendar cannot fit, and it does not fire early to "use up" the cap.

## Tier, frozen once

`window` = deadline minus schedule anchor, in calendar days. The schedule anchor is the registration date, or the date a returned or partial item was re-anchored.

| window | tier |
|---|---|
| 10 or more | comfortable |
| 5 to 9 | moderate |
| 0 to 4 | tight |
| below 0 | overdue |

Freeze the tier. Do not recompute it when the window shrinks. A 12-day item is still comfortable when 3 days remain. Its dates were chosen at the anchor.

## Planned dates

Build the plan once from the anchor, the deadline, and the frozen tier. Ignore any `next_touch` already stored in the tracker. Recompute it.

**Comfortable.** Three candidate dates, then one overdue date:

1. The anchor.
2. The anchor plus `floor(window / 2)` calendar days. An 11-day window uses day 5, not day 6. Do not round to the nearest day.
3. The deadline minus 3 calendar days.
4. The first business day after the deadline.

**Moderate.** Anchor, anchor plus 2 calendar days, anchor plus 4 calendar days, then the first business day after the deadline.

**Tight.** Anchor, anchor plus 1 calendar day, anchor plus 2 calendar days, then the first business day after the deadline. Do not add a further email on every remaining day. That daily series is what used to burn the cap before the deadline.

**Overdue** (the deadline is already before the anchor). All four emails acknowledge that the deadline has passed, and each is two business days after the one before it. The first is the first business day on or after the anchor.

The first request may land on the deadline. Later reminders stay strictly before the deadline. An item registered on its due date, or registered the day before a Monday deadline, gets that request on the due date. The words "Deadline passed" are for a day after the deadline, not for the due date itself.

Snap every candidate onto a business day, drop the ones that cannot fit, and collapse duplicates. Keep at most three dates on or before the deadline. The overdue date is the first business day after the deadline, so the plan does not tell you to call before the item is due.

## What to do today

Walk the statuses in this order.

1. **Accepted.** Closed. No email.
2. **Received.** A person still has to review it. No chase email.
3. **Bad contact.** The address bounced or the contact is the wrong person. Do not email. Ask the firm for a working email or a phone number. Do not keep writing until the cap. A phone number on the row is for a call, not a reason to try the dead address again.
4. **Paused.** The client replied, and the reply was not a file you have logged. Do not email again until a person has read it and resumed the chase.
5. **Cap reached.** `touches_sent` is 4 or more, or every planned date has already been used.
   - If today is after the deadline, the status is **Call needed**. Do not draft another email. The internal note names the items, the phone on file, and the deadline. It does not quote internal notes to the client, because it is not sent to the client.
   - If today is on or before the deadline, hold. Do not email and do not call yet. The call starts on the first business day after the deadline.
6. **Open, Partial, or Returned.** Look at `plan[touches_sent]`, the next unsent date. The next email is the later of that date and two business days after `last_touch`.
   - If `last_touch` is today, send nothing else today. One email per client per day.
   - If the next email is after today, wait.
   - If it is today or earlier, and today is a business day, send one email today. Every missed date is caught up in that single email. Do not send one email per missed day, and do not email again the next business day. The gap is two business days: a Tuesday send is not followed by a Wednesday send.
   - If today is not a business day, wait until the next one.

## Mark sent

Drafting does not record a send. After a person sends the email, mark it sent: add 1 to `touches_sent` and set `last_touch` to today. Doing that twice the same day does not count two emails. The next run then waits for the gap instead of drafting the same message again.

A partial file and a rejection each count as that send. Set `touches_sent` to 1 and `last_touch` to today when they happen, and draft the thank-you in the same step. Do not also queue a chase email that day. The partial thank-you names what arrived and asks only for what is still open.

Email kind, for the one email you do send:

- **overdue** when today is after the deadline. Say the deadline has passed and one factual sentence about what is held up, using the client-facing reason.
- **initial** when `touches_sent` is 0 and today is on or before the deadline. Say "we need", not "we still need".
- **reminder** otherwise.

## Grouping

A client with several items due the same day gets one email. The group's kind is overdue if any item is overdue, initial if every item is initial, and reminder otherwise. The subject names the document. It does not say "Follow-up #3", it does not count the touch, and it does not start with the firm name and a double hyphen.

List every due item. On a Partial item, list only the lines still marked open.

## Call flag

The call flag applies only after the planned emails are used up (or the stored count is already 4) and today is after the deadline. It does not apply on the deadline day. It does not apply while a pre-deadline email is still unsent. Bad contact wins over the call flag: a bounce stops email immediately, even at touch 1.

## Returned and partial

A file coming back from the client is a response. The old silence streak does not carry forward.

- **Partial** (some lines arrived, some did not). Status becomes Partial. Mark the covered lines received. The thank-you is today's touch: `touches_sent` is 1 and `last_touch` is today. Keep chasing the open lines only, after the gap. Do not mark the whole request received.
- **Returned** (a person rejected the file). Status becomes Returned. The rejection is today's touch: `touches_sent` is 1 and `last_touch` is today. The schedule anchor is the review date, and the tier freezes again from that anchor. It is still a draft a person approves. It is not a second chase email the same day.

## Client-facing text

A draft may use the description, the period, the amount, the client-facing reason, the document type, the deadline, the salutation, the open lines, and the sender's name and title.

A draft must not quote or paraphrase `internal_notes`. If the client-facing reason is blank, do not fill it from the notes. Say the item is needed for the books on file. A column named Reason, Why Needed, or Context is an internal note until the person writes a separate client-facing reason. Before a draft is shown, check that no four-word run from the internal notes appears in it. Copying that run into the client-facing reason does not make it safe.

Dates in a client email are written as `Thursday, September 24, 2026`. A period `2026-10` is written as `October 2026`. Amounts use a dollar sign and thousands separators. If the row has no sender name, use the firm name and say setup is incomplete. Never leave a `[Sender Name]` bracket. The first request says "we need". A later one says "we still need". Include a "How to send" line.

## Salutation

If `salutation` has a name, open with `Hi {salutation},`. If it is blank or contains `@`, open with `Hello,`. Never build a name from the mailbox (`info@`, `ap@`, `books@`).

## Worked examples

Absolute dates, so they do not move with the clock. `tests/run_tests.py` reads the `examples` block and recomputes every row.

```examples
id | anchor | deadline | touches | as_of | kind | next | tier | email_kind
comfortable-initial | 2026-09-06 | 2026-09-17 | 0 | 2026-09-08 | email | 2026-09-08 | comfortable | initial
comfortable-reminder | 2026-09-06 | 2026-09-17 | 2 | 2026-09-14 | email | 2026-09-14 | comfortable | reminder
cap-before-deadline | 2026-09-06 | 2026-09-17 | 4 | 2026-09-17 | hold | 2026-09-18 | comfortable |
cap-after-deadline | 2026-09-06 | 2026-09-17 | 4 | 2026-09-18 | call |  | comfortable |
moderate-not-saturday | 2026-09-10 | 2026-09-19 | 1 | 2026-09-12 | wait | 2026-09-14 | moderate |
moderate-monday | 2026-09-10 | 2026-09-19 | 1 | 2026-09-14 | email | 2026-09-14 | moderate | reminder
weekend-catchup | 2026-09-04 | 2026-10-05 | 0 | 2026-09-05 | wait | 2026-09-08 | comfortable |
tight-no-early-call | 2026-09-14 | 2026-09-18 | 3 | 2026-09-18 | wait | 2026-09-21 | tight |
tight-overdue-email | 2026-09-14 | 2026-09-18 | 3 | 2026-09-21 | email | 2026-09-21 | tight | overdue
ten-day-no-early-call | 2026-09-14 | 2026-09-24 | 2 | 2026-09-24 | wait | 2026-09-25 | comfortable |
registered-already-overdue | 2026-09-14 | 2026-09-10 | 0 | 2026-09-14 | email | 2026-09-14 | overdue | overdue
initial-not-skipped | 2026-09-14 | 2026-09-28 | 0 | 2026-09-14 | email | 2026-09-14 | comfortable | initial
```

Reading the rows:

- `comfortable-initial` is registered on Sunday 2026-09-06. Monday 2026-09-07 is Labor Day, so the initial goes Tuesday 2026-09-08. The window is 11 days, so halfway is day 5, which is Friday 2026-09-11, not Saturday. US federal holidays are not email days.
- `moderate-not-saturday` is the day-2 reminder. Day 2 falls on Saturday 2026-09-12, so the email is Monday 2026-09-14. It is not sent on Saturday, and it is not delayed to Tuesday 2026-09-15.
- `tight-no-early-call` has already used its three pre-deadline emails by the deadline. The fourth email is the overdue notice on Monday 2026-09-21. Nobody is told to call on Friday 2026-09-18.
- `ten-day-no-early-call` has a 10-day window. Halfway and the three-days-before date land on the same Monday, so the plan has three emails. The last of them is the day after the deadline. There is no call on the deadline.
- `initial-not-skipped` is registered the same day you are assessing it. Touch count 0 means the initial is due today. Do not jump to the halfway date.
