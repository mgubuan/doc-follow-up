#!/usr/bin/env python3
"""Regression suite for the doc-follow-up core.

Run from the repo root:

    python3 tests/run_tests.py

PDF checks need pypdf (see requirements.txt). Everything else is the
standard library. The suite fails if the worked examples in
core/follow-up-rules.md drift from core/engine.py, if the LOTR fixture
assesses wrong on 2026-09-14, or if the demo firm is all overdue.
"""

from __future__ import annotations

import csv
import io
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.engine import (  # noqa: E402
    COLUMNS,
    DRAFT_BANNER,
    SAFETY_LINE,
    Action,
    Item,
    apply_next_touch,
    apply_precheck,
    assess,
    assess_item,
    draft_is_clean,
    example_plan,
    greeting,
    interpret_text,
    load_tracker,
    mask_sensitive,
    parse_iso,
    plan_touches,
    precheck,
    render_call_note,
    render_client_reply,
    render_draft,
    render_partial_reply,
    mark_sent,
    note_client_reply,
    extract_document,
    is_business_day,
    today_for,
    periods_overlap,
    DEFAULT_TIMEZONE,
    resolve_tracker_text,
    return_item,
    tier_for,
    understood_table,
)

AS_OF = date(2026, 9, 14)
FIRM = {
    "firm_name": "Example Bookkeeping",
    "firm_email": "hello@example.com",
    "firm_phone": "555-010-0000",
}
DEMO_FIRM = {
    "firm_name": "Northline Ledger Co.",
    "firm_email": "hello@northline.example",
    "firm_phone": "555-014-2200",
}
FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


def load_lotr():
    return load_tracker((ROOT / "tests/fixtures/lotr/tracker.csv").read_text())


def item_for(anchor: str, deadline: str, touches: int, holidays=()) -> Item:
    start = parse_iso(anchor)
    return Item(
        id="EX",
        client_name="Example Client",
        doc_type="Bank Statement",
        description="Operating account statement",
        client_reason="Needed to close the month.",
        deadline=parse_iso(deadline),
        status="Open",
        touches_sent=touches,
        registered=start,
        schedule_anchor=start,
        holidays=tuple(holidays),
    )


def worked_examples() -> list[dict]:
    text = (ROOT / "core/follow-up-rules.md").read_text()
    match = re.search(r"```examples\n(.*?)```", text, re.S)
    check(match is not None, "follow-up-rules.md is missing the examples block")
    if not match:
        return []
    rows = []
    lines = [line for line in match.group(1).splitlines() if line.strip()]
    header = [part.strip() for part in lines[0].split("|")]
    for line in lines[1:]:
        values = [part.strip() for part in line.split("|")]
        check(len(values) == len(header), f"example row has the wrong width: {line}")
        rows.append(dict(zip(header, values)))
    return rows


def test_worked_examples() -> None:
    rows = worked_examples()
    check(len(rows) >= 12, "expected at least 12 worked examples")
    for row in rows:
        item = item_for(row["anchor"], row["deadline"], int(row["touches"]))
        action = assess_item(item, parse_iso(row["as_of"]))
        check(item.tier() == row["tier"], f"{row['id']} tier {item.tier()} != {row['tier']}")
        check(action.kind == row["kind"], f"{row['id']} kind {action.kind} != {row['kind']}")
        expected_next = row["next"]
        got = action.next_touch.isoformat() if action.next_touch else ""
        check(got == expected_next, f"{row['id']} next {got} != {expected_next}")
        if row["kind"] == "email":
            check(
                action.email_kind == row["email_kind"],
                f"{row['id']} email kind {action.email_kind} != {row['email_kind']}",
            )


def test_date_rules() -> None:
    plan = example_plan("2026-09-06", "2026-09-17")
    check(plan["window_days"] == 11, "11-day window")
    check(plan["dates"][1] == "2026-09-11", "halfway of 11 days is day 5, 2026-09-11, not 2026-09-12")
    overdue_plan = example_plan("2026-09-14", "2026-09-10")
    check(
        overdue_plan["dates"] == ["2026-09-14", "2026-09-16", "2026-09-18", "2026-09-22"],
        f"overdue cadence drifted: {overdue_plan['dates']}",
    )
    # Tier stays comfortable when only 3 days remain. The next date is still the original plan.
    frozen = item_for("2026-09-01", "2026-09-15", 2)
    check(frozen.tier() == "comfortable", "tier is not recomputed down to tight")
    check(
        [day.isoformat() for day in frozen.plan()] == ["2026-09-01", "2026-09-08", "2026-09-14", "2026-09-16"],
        f"frozen plan changed: {frozen.plan()}",
    )
    action = assess_item(frozen, date(2026, 9, 12))
    check(action.kind == "wait" and action.next_touch == date(2026, 9, 14), "frozen next touch is 2026-09-14")
    holiday = plan_touches(date(2026, 9, 6), date(2026, 9, 17), [date(2026, 9, 14)])
    check(
        [day.isoformat() for day in holiday] == ["2026-09-08", "2026-09-11", "2026-09-15", "2026-09-18"],
        f"holiday did not move 2026-09-14 to 2026-09-15: {holiday}",
    )
    merged = plan_touches(date(2026, 9, 6), date(2026, 9, 17), [date(2026, 9, 11)])
    check(date(2026, 9, 11) not in merged, "a holiday is not an email day")
    check(len(merged) == len(set(merged)), "merged anchors are one email")
    # Stored next_touch is not authority.
    misleading = item_for("2026-09-14", "2026-09-28", 0)
    misleading.next_touch = date(2099, 1, 1)
    action = assess_item(misleading, date(2026, 9, 14))
    check(action.kind == "email" and action.next_touch == date(2026, 9, 14), "stored next_touch was trusted")
    # Open + 4 touches + past deadline becomes Call needed. Bad contact does not.
    capped = item_for("2026-08-01", "2026-09-01", 4)
    capped.status = "Open"
    apply_next_touch([capped], date(2026, 9, 14))
    check(capped.status == "Call needed" and capped.next_touch is None, "cap did not become Call needed")
    bounced = item_for("2026-08-01", "2026-09-01", 4)
    bounced.status = "Bad contact"
    apply_next_touch([bounced], date(2026, 9, 14))
    check(bounced.status == "Bad contact", "bad contact was rewritten as a call")
    early = item_for("2026-09-14", "2026-09-24", 4)
    action = assess_item(early, date(2026, 9, 20))
    check(action.kind == "hold", "call flag fired before the deadline")
    check(tier_for(date(2026, 9, 14), date(2026, 9, 24)) == "comfortable", "10-day window is comfortable")


def test_lotr_assess() -> None:
    items = load_lotr()
    by_id = {item.id: item for item in items}
    check(len(items) == 10, "LOTR fixture should have 10 requests")
    result = assess(items, AS_OF)
    groups = {group["client_name"]: group for group in result.email_groups}
    check(set(groups) == {
        "Baggins & Associates LLC",
        "Isengard Technologies",
    }, f"unexpected email groups: {list(groups)}")
    baggins = groups["Baggins & Associates LLC"]
    baggins_ids = [entry["item"].id for entry in baggins["entries"]]
    check(baggins_ids == ["REQ-002"], f"Baggins grouping {baggins_ids}")
    check(baggins["email_kind"] == "initial", "the due-date receipt should be a first request")
    check(groups["Isengard Technologies"]["entries"][0]["action"].email_kind == "initial", "Isengard initial was skipped")
    # REQ-009's planned slot is still Monday, not the old off-by-one Tuesday.
    # The send waits until Tuesday because the last contact was Saturday and
    # the gap is two business days.
    check(by_id["REQ-009"].plan()[1] == date(2026, 9, 14), "Shire plan slot drifted off Monday")
    shire = next(entry for entry in result.waiting if entry["item"].id == "REQ-009")
    check(shire["action"].next_touch == date(2026, 9, 15), "Shire gap did not hold until Tuesday")
    gondor = next(entry for entry in result.waiting if entry["item"].id == "REQ-004")
    check(gondor["action"].next_touch == date(2026, 9, 21), "Gondor was scheduled on Saturday 2026-09-19")
    rohan = next(entry for entry in result.waiting if entry["item"].id == "REQ-003")
    check(rohan["action"].next_touch == date(2026, 9, 15), "Rohan was emailed the day after a Sunday contact")
    check([entry["item"].id for entry in result.call_needed] == ["REQ-005"], "Mordor should be call needed")
    check([entry["item"].id for entry in result.bad_contact] == ["REQ-008"], "Moria should be bad contact")
    check([entry["item"].id for entry in result.review] == ["REQ-006"], "Rivendell should wait for review")
    check([entry["item"].id for entry in result.closed] == ["REQ-010"], "Gondor renewal should be closed")
    weekend = assess(items, date(2026, 9, 12))
    check(weekend.email_groups == [], "Saturday 2026-09-12 produced an email")
    # Drafts.
    forbidden = [
        "Mount Doom",
        "tomato",
        "Nazgul",
        "Westfold",
        "hasty",
        "spam folder",
        "dangerous business",
        "White Tree lives",
        "Follow-Up",
        "Follow-up #",
    ]
    for group in result.email_groups:
        draft = render_draft(group, FIRM)
        leaks = draft_is_clean(draft, [entry["item"] for entry in group["entries"]])
        check(leaks == [], f"leak in {group['client_name']}: {leaks}")
        subject = next(line for line in draft.splitlines() if line.startswith("Subject:"))
        check("--" not in subject, f"bulk subject: {subject}")
        for phrase in forbidden:
            check(phrase.lower() not in draft.lower(), f"{phrase!r} reached {group['client_name']}")
        check(SAFETY_LINE not in draft, "the advice line was pasted into a client email")
        check(DRAFT_BANNER in draft, "draft banner missing")
        check(len(draft.split()) < 200, f"{group['client_name']} draft is over 200 words")
    baggins_draft = render_draft(baggins, FIRM)
    check("Hi Frodo," in baggins_draft, "known salutation missing")
    check("$14,999" in baggins_draft, "amount was not formatted with a dollar sign")
    check("2026-09-24" not in baggins_draft, "an ISO date reached the client draft")
    check("Thursday, September 24, 2026" in baggins_draft, "deadline was not written as a human date")
    check("We still need" not in baggins_draft, "a first request said 'still need'")
    check("How to send:" in baggins_draft, "upload instructions missing")
    check("[Sender Name]" not in baggins_draft, "a bracket placeholder reached the draft")
    check("Samwise Gamgee" in baggins_draft, "known sender was replaced")
    isengard = render_draft(groups["Isengard Technologies"], FIRM)
    check("\nHello,\n" in isengard, "blank salutation did not fall back to Hello")
    check("Hi Saruman" not in isengard and "Hi saruman" not in isengard, "name was guessed from the email")
    shire_item = by_id["REQ-009"]
    shire_draft = render_draft(
        {
            "client_name": shire_item.client_name,
            "email_kind": "reminder",
            "entries": [{"item": shire_item, "action": assess_item(shire_item, date(2026, 9, 15))}],
        },
        FIRM,
    )
    check("Second Breakfast" in shire_draft and "Elevenses" in shire_draft, "a line was left only in the notes")
    check("August 3, 2026" in shire_draft or "August 2026" in shire_draft, "line period stayed ISO")
    call = render_call_note(by_id["REQ-005"])
    check("do not email" in call.lower() and "Nazgul" not in call, "call note quoted the internal suspicion")
    # A planted leak must fail the check.
    dirty = baggins_draft + "\n" + by_id["REQ-002"].internal_notes
    check(draft_is_clean(dirty, [by_id["REQ-002"]]) != [], "planted internal note was not caught")
    check(greeting("") == "Hello,", "empty greeting")
    check(greeting("M.E.") == "Hi M.E.,", "initials were expanded or rejected")
    check(greeting("info@acme.example") == "Hello,", "@ was used as a name")


def test_precheck() -> None:
    items = {item.id: item for item in load_lotr()}
    open_count = sum(1 for item in items.values() if item.client_name == "Baggins & Associates LLC" and item.status in ("Open", "Partial", "Returned"))
    check(open_count >= 2, "Baggins should have two open items for the confirm step")
    may = precheck(
        items["REQ-001"],
        {
            "doc_type": "Bank Statement",
            "period": "2026-05",
            "entity": "Baggins & Associates LLC",
            "account_last4": "1111",
            "complete": True,
        },
        open_item_count=open_count,
    )
    check(may.outcome == "MISMATCH", f"May statement outcome {may.outcome}")
    check("2026-06" in may.ask_client_for and "Do not ask again for 2026-05" in may.ask_client_for, may.ask_client_for)
    check(may.needs_confirmation, "two open items were matched silently")
    june = precheck(
        items["REQ-001"],
        {
            "doc_type": "Bank Statement",
            "period": "2026-06",
            "entity": "Baggins & Associates LLC",
            "account_last4": "1111",
            "complete": True,
        },
        open_item_count=1,
    )
    check(june.outcome == "MATCH" and not june.needs_confirmation, "June statement should match when it is the only candidate")
    po = precheck(
        items["REQ-006"],
        {
            "doc_type": "Purchase Order",
            "doc_number": "ELF-2021",
            "subject": "Miruvor Wine",
            "requested_subject": "Lembas Bread",
            "pointer": {"number": "ELF-2019", "subject": "Lembas Bread", "issued": "2026-08-05"},
            "entity": "Rivendell Consulting Group",
            "complete": True,
        },
    )
    check(po.outcome == "REQUEST_MAY_BE_WRONG", po.outcome)
    check("ELF-2019" in po.ask_client_for and "ELF-2021" not in po.ask_client_for, po.ask_client_for)
    reply = render_client_reply(items["REQ-006"], "PO #ELF-2021 for Miruvor Wine", po.correct_request_to, FIRM)
    check("ELF-2019" in reply and "Lembas" in reply, "corrected ask missing")
    check("ELF-2021" not in reply.split("We still need", 1)[-1], "the reply asked for the wrong PO")
    check("Miruvor" not in items["REQ-006"].client_reason, "the wine mix-up was put in the client reason")
    check(draft_is_clean(reply, [items["REQ-006"]]) == [], "rejection quoted internal notes")
    partial = precheck(
        items["REQ-009"],
        {"doc_type": "Receipt", "period": "2026-08", "entity": "Shire Agricultural Co-op", "lines_covered": ["Second Breakfast catering"], "complete": True},
    )
    check(partial.outcome == "PARTIAL", partial.outcome)
    check("Elevenses" in partial.ask_client_for and "Second Breakfast" not in partial.ask_client_for, partial.ask_client_for)
    updated = apply_precheck(items["REQ-009"], partial, AS_OF)
    check(updated.status == "Partial", "partial was closed as received")
    open_labels = [line["label"] for line in updated.lines if line["status"] == "open"]
    check(open_labels == ["Elevenses Bakery"], open_labels)
    check(updated.touches_sent == 1 and updated.last_touch == AS_OF, "partial did not count the thank-you as today's touch")
    check(assess_item(updated, AS_OF).kind != "email", "partial queued a second email the same day")
    partial_reply = render_partial_reply(updated, FIRM)
    check("Thank you for sending" in partial_reply and "Elevenses" in partial_reply, partial_reply)
    check("Second Breakfast" in partial_reply.split("Thank you for sending", 1)[-1].split("We still need", 1)[0], "the thank-you did not name what arrived")
    invoice = precheck(
        items["REQ-003"],
        {
            "doc_type": "Invoice",
            "period": "2026-08",
            "entity": "Rohan Cavalry Services Inc",
            "doc_number": "RCS-4087",
            "complete": True,
        },
    )
    check(invoice.outcome == "MATCH", "approximate amount must not fail an exact invoice")
    returned = return_item(items["REQ-003"], date(2026, 9, 16))
    check(returned.status == "Returned" and returned.touches_sent == 1, "return did not count the rejection as today's touch")
    check(returned.last_touch == date(2026, 9, 16), "return cleared the last contact")
    check(assess_item(returned, date(2026, 9, 16)).kind != "email", "return queued a second email the same day")
    check(returned.schedule_anchor == date(2026, 9, 16), "return did not re-anchor")


def test_pdfs() -> None:
    try:
        from pypdf import PdfReader
    except ImportError:
        FAILURES.append("pypdf is not installed. Run: python3 -m pip install -r requirements.txt")
        return
    folder = ROOT / "tests/fixtures/lotr/documents"

    def text(name: str) -> str:
        reader = PdfReader(str(folder / name))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    po = text("purchase-order-ELF-2021-miruvor-wine.pdf")
    check("PO #ELF-2021" in po and "Miruvor" in po and "Lembas" in po, "PO PDF lost the trap")
    check("PO #ELF-2019" in po and "August 5, 2026" in po, "PO PDF lost the pointer to ELF-2019")
    may = text("bank-statement-shire-MAY-2026-baggins.pdf")
    june = text("bank-statement-shire-JUNE-2026-baggins.pdf")
    check("May 1" in may and "****1111" in may and "Baggins" in may, "May statement text missing")
    check("June 1" in june and "****1111" in june and "May 1" not in june, "June statement text missing")
    breakfast = text("receipt-second-breakfast-aug3.pdf")
    elevenses = text("receipt-elevenses-bakery-aug17.pdf")
    check("August 3, 2026" in breakfast and "Shire Agricultural" in breakfast, "Second Breakfast receipt")
    check("August 17, 2026" in elevenses and "Shire Agricultural" in elevenses, "Elevenses receipt")
    invoice = text("invoice-RCS-4087-helms-deep-repairs.pdf")
    check("RCS-4087" in invoice and "Rohan" in invoice and "847,229.00" in invoice, "invoice text")
    receipt = text("receipt-one-ring-insurance-renewal.pdf")
    check("14,999.00" in receipt and "July 15, 2026" in receipt and "Baggins" in receipt, "insurance receipt")
    # The engine reads the PDFs. The decision is not fed a hand-built dict.
    items = {item.id: item for item in load_lotr()}
    may_facts = extract_document(str(folder / "bank-statement-shire-MAY-2026-baggins.pdf"))
    check(may_facts.get("period") == "May 2026" and may_facts.get("account_last4") == "1111", may_facts)
    may_result = precheck(items["REQ-001"], may_facts)
    check(may_result.outcome == "MISMATCH", "engine-extracted May statement did not mismatch")
    check("2026-06" in may_result.ask_client_for and "ELF-2021" not in may_result.ask_client_for, may_result.ask_client_for)
    po_facts = extract_document(str(folder / "purchase-order-ELF-2021-miruvor-wine.pdf"))
    check(po_facts.get("doc_number") == "ELF-2021", po_facts)
    check((po_facts.get("pointer") or {}).get("number") == "ELF-2019", po_facts.get("pointer"))
    po_result = precheck(items["REQ-006"], po_facts)
    check(po_result.outcome == "REQUEST_MAY_BE_WRONG", "engine-extracted PO check failed")
    check("ELF-2021" not in po_result.ask_client_for and "ELF-2019" in po_result.ask_client_for, po_result.ask_client_for)
    breakfast_facts = extract_document(str(folder / "receipt-second-breakfast-aug3.pdf"))
    check(breakfast_facts.get("lines_covered") == ["Second Breakfast catering"], breakfast_facts.get("lines_covered"))
    partial = precheck(items["REQ-009"], breakfast_facts)
    check(partial.outcome == "PARTIAL" and "Elevenses" in partial.ask_client_for, partial.ask_client_for)


def test_privacy_and_intake() -> None:
    masked, found = mask_sensitive(
        "Call 555-010-1008 about invoice RCS-4087. SSN 123-45-6789. Account 998877665544. Card 4111111111111111."
    )
    check(found, "mask did not notice the identifiers")
    check("123-45-6789" not in masked and "***-**-****" in masked, masked)
    check("998877665544" not in masked and "ending 5544" in masked, masked)
    check("4111111111111111" not in masked and "ending 1111" in masked, masked)
    check("555-010-1008" in masked and "RCS-4087" in masked, "a phone or invoice number was eaten")
    paste = "\n".join(
        [
            "Client,Email,What we need,Deadline,Notes,Amount",
            'Acme LLC,info@acme.example,"March statement acct 123456789012",04/15/2026,SSN 123-45-6789 on the form,not-a-number',
            'Acme LLC,info@acme.example,"March statement acct 123456789012",2026-04-15,same, ',
        ]
    )
    understood = interpret_text(paste, date(2026, 11, 24))
    check(understood.masked, "intake did not warn on the SSN")
    check(any("masked" in warning.lower() or "Social Security" in warning for warning in understood.warnings), understood.warnings)
    check(understood.rows[0]["salutation"] == "", "salutation was invented from info@")
    check("123456789012" not in understood.rows[0]["description"], understood.rows[0]["description"])
    check("ending 9012" in understood.rows[0]["description"], understood.rows[0]["description"])
    check("123-45-6789" not in understood.rows[0]["internal_notes"], "SSN stored in notes")
    check(understood.rows[0]["amount"] == "", "a bad amount was kept")
    check(understood.rows[0]["deadline"] == "2026-04-15", understood.rows[0]["deadline"])
    check(any("month/day/year" in note for note in understood.assumptions), understood.assumptions)
    check(any("duplicate" in question.lower() for question in understood.questions), understood.questions)
    check("info" not in understood.rows[0]["salutation"].lower(), "Hi Info")
    prose = interpret_text("Jones – still no Mar stmt, called twice", date(2026, 11, 24))
    row = prose.rows[0]
    check(row["client_name"] == "Jones", row["client_name"])
    check(row["touches_sent"] == "0", "a phone call was counted as an email touch")
    check(row["deadline"] == "" and row["period"] == "" and row["contact_email"] == "", "prose intake invented a field")
    check(row["client_reason"] == "", "notes were copied into the client reason")
    check(any("phone call" in question.lower() or "called" in question.lower() for question in prose.questions), prose.questions)
    check(any("period" in question.lower() for question in prose.questions), "missing period was not a question")
    table = understood_table(understood.rows)
    check("123-45-6789" not in table and "123456789012" not in table, table)


def test_demo() -> None:
    raw = (ROOT / "demo/tracker.csv").read_text()
    clients = {row["client_name"] for row in csv.DictReader(io.StringIO(raw))}
    check(len(clients) == 12, f"demo should have 12 clients, has {len(clients)}")
    for name in ("Baggins", "Nazgul", "Mordor", "Gondor"):
        check(name not in raw, f"demo tracker still contains {name}")
    start = date(2026, 1, 1)
    for offset in range(366):
        today = start + timedelta(days=offset)
        items = load_tracker(resolve_tracker_text(raw, today))
        result = assess(items, today)
        emailed = [entry["item"].id for group in result.email_groups for entry in group["entries"]]
        for item in items:
            check((today - item.deadline).days <= 21, f"{today} {item.id} is wildly overdue")
        check(any(item.deadline > today for item in items), f"{today} has no future deadline")
        check("DEMO-007" not in emailed and "DEMO-008" not in emailed, f"{today} emailed a stopped status")
        names = [group["client_name"] for group in result.email_groups]
        check(len(names) == len(set(names)), f"{today} sent two emails to one client")
        if not is_business_day(today):
            check(result.email_groups == [], f"{today} is not a business day and produced email")
        statement_types = {
            "bank statement",
            "credit card statement",
            "loan statement",
            "payroll report",
            "sales tax return",
            "receipt",
        }
        for item in items:
            if item.last_touch:
                check(is_business_day(item.last_touch), f"{item.id} last touch {item.last_touch} is closed")
            if item.registered:
                check(is_business_day(item.registered), f"{item.id} registered {item.registered} is closed")
            if item.doc_type.lower() in statement_types and re.fullmatch(r"\d{4}-\d{2}", item.period or ""):
                year, month = (int(part) for part in item.period.split("-"))
                month_end = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
                check(month_end < today, f"{today} {item.id} asks for {item.period} before that month ends")
        for group in result.email_groups:
            draft = render_draft(group, DEMO_FIRM)
            check("divorce" not in draft.lower() and "parental" not in draft.lower(), f"{today} leaked a note")
            check("[Sender Name]" not in draft and "2026-" not in draft.split("To:", 1)[-1], f"{today} machine formatting")
            if group["client_name"].startswith("Northwind"):
                check("\nHello,\n" in draft and "Hi Books" not in draft and "Samir" not in draft, f"{today} Northwind greeting")
    resolved = resolve_tracker_text(raw, date(2026, 11, 24))
    check("month:" not in resolved and "+10d" not in resolved and "-10d" not in resolved, "relative tokens survived")
    november = {item.id: item for item in load_tracker(resolved)}
    check(november["DEMO-001"].period == "2026-10", november["DEMO-001"].period)
    check(november["DEMO-004"].period == "2025", november["DEMO-004"].period)
    january = load_tracker(resolve_tracker_text(raw, date(2026, 1, 15)))
    by_id = {item.id: item for item in january}
    check(by_id["DEMO-001"].period.startswith("2025-"), "January request did not use a closed prior-year month")
    for closed in (date(2026, 1, 1), date(2026, 9, 7), date(2026, 11, 26), date(2026, 7, 3), date(2027, 1, 1)):
        holiday_board = assess(load_tracker(resolve_tracker_text(raw, closed)), closed)
        check(holiday_board.email_groups == [], f"{closed} still drafted on a federal holiday")
    statuses = {item.status for item in november.values()}
    for status in ("Open", "Partial", "Received", "Accepted", "Bad contact", "Call needed"):
        check(status in statuses, f"demo is missing status {status}")


def test_repo_shape() -> None:
    header = (ROOT / "shared/tracker.template.csv").read_text().strip()
    check(header == ",".join(COLUMNS), "shared/tracker.template.csv is not the empty schema header")
    ignored = (ROOT / ".gitignore").read_text()
    check("shared/tracker.csv" in ignored, "a filled client tracker can be committed")
    check("stages/*/output/*" in ignored or "stages/" in ignored, "stage output with client drafts can be committed")
    for path in (ROOT / "demo/tracker.csv", ROOT / "tests/fixtures/lotr/tracker.csv"):
        first = path.read_text().splitlines()[0]
        check(first == ",".join(COLUMNS), f"{path.name} header drifted")
    check(not list(ROOT.rglob("*.xlsx")), "an xlsx tracker is still in the repo")
    lotr = (ROOT / "tests/fixtures/lotr/tracker.csv").read_text()
    check("09/17/2026" not in lotr and "2026-09-17" in lotr, "LOTR dates are not ISO")
    for row in csv.DictReader(io.StringIO(lotr)):
        for key in ("deadline", "registered", "schedule_anchor"):
            check(re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[key]), f"{row['id']} {key} {row[key]}")
        if row["amount"]:
            check(re.fullmatch(r"\d+(\.\d+)?", row["amount"]), f"{row['id']} amount {row['amount']}")
        if row["last_touch"]:
            check(re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["last_touch"]), row["last_touch"])
    firm = (ROOT / "shared/firm.md").read_text()
    questionnaire = (ROOT / "setup/questionnaire.md").read_text()
    for token in (
        "{{FIRM_NAME}}",
        "{{FIRM_EMAIL}}",
        "{{FIRM_PHONE}}",
        "{{TEAM_MEMBERS}}",
        "{{DOC_TYPES}}",
        "{{SUBMISSION_INSTRUCTIONS}}",
    ):
        check(token in firm, f"firm.md dropped {token}")
        check(token in questionnaire, f"questionnaire dropped {token}")
    check("{{TEAM_MEMBERS}}" not in questionnaire or "{{TEAM_MEMBERS}}" in firm, "team placeholder has nowhere to land")
    defaults = (ROOT / "shared/email-defaults.md").read_text()
    check("shared/firm.md" in defaults, "email defaults do not read firm.md")
    check("Follow-Up #" not in (ROOT / "core/email-templates.md").read_text(), "template subject still counts touches")
    safety = (ROOT / "core/safety.md").read_text()
    check(SAFETY_LINE in safety, "safety.md lost the advice line")
    check("password" in safety.lower() and "initials" in safety.lower(), "safety.md is missing a guardrail")
    check("do not send" in safety.lower() or "Do not send" in safety, "safety.md does not forbid sending")
    types = (ROOT / "core/document-types.md").read_text()
    check("{{DOC_TYPES}}" in types and "{{SUBMISSION_INSTRUCTIONS}}" in types, "doc type placeholders dropped")
    check("your password" not in types.lower() and "send a password" not in types.lower(), "document types ask for a password")
    check("Do not send a login." in types, "document types lost the login warning")
    schema = (ROOT / "core/schema.json").read_text()
    check('"Call needed"' in schema and '"Bad contact"' in schema and '"Partial"' in schema, "schema statuses drifted")
    check((ROOT / "LICENSE").exists(), "MIT license file missing")
    check("Permission is hereby granted" in (ROOT / "LICENSE").read_text(), "LICENSE is not the MIT text")
    rules = (ROOT / "core/follow-up-rules.md").read_text()
    for phrase in ("floor(window / 2)", "Bad contact", "Call needed", "business day", "touch 1"):
        check(phrase in rules, f"rules missing {phrase!r}")


def test_qa_fixes() -> None:
    """Regression tests for the QA must-fix list. Names match the review items."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    # 1. Mark sent, then the same draft is not produced again the next day.
    item = item_for("2026-11-02", "2026-11-20", 0)
    item.id = "GAP-1"
    item.last_touch = None
    tuesday = date(2026, 11, 24)
    first = assess_item(item, tuesday)
    check(first.kind == "email", "catch-up should send once")
    mark_sent([item], tuesday)
    check(item.touches_sent == 1 and item.last_touch == tuesday, "mark sent did not record the email")
    mark_sent([item], tuesday)
    check(item.touches_sent == 1, "mark sent counted the same day twice")
    wednesday = date(2026, 11, 25)
    check(assess_item(item, wednesday).kind != "email", "the same email was drafted again the next day")

    # 2. One catch-up, then a two-business-day gap. Juniper's shape: overdue, last contact several days ago.
    juniper = item_for("2026-11-06", "2026-11-21", 2)
    juniper.last_touch = date(2026, 11, 16)
    juniper.doc_type = "Loan Statement"
    check(assess_item(juniper, tuesday).email_kind == "overdue", "Juniper should get one overdue catch-up")
    mark_sent([juniper], tuesday)
    check(assess_item(juniper, wednesday).kind == "wait", "Juniper was drafted again on the next day")
    check(assess_item(juniper, date(2026, 11, 27)).kind == "email", "the gap never released the next touch")

    # 3. Covered by test_precheck (partial and return set touches to 1 and last_touch to today).

    # 4. A pasted Why Needed column is internal, and copying it into the reason fails the leak check.
    pasted = "\n".join(
        [
            "Client,Email,Description,Deadline,Why Needed",
            "Mordor Industrial,sauron@mordor.example,May 2026 bank statement,2026-09-09,Unusual volume of wire transfers to Nazgul Payroll",
        ]
    )
    understood = interpret_text(pasted, date(2026, 9, 14))
    row = understood.rows[0]
    check(row["client_reason"] == "", "Why Needed was treated as client-facing")
    check("Nazgul Payroll" in row["internal_notes"], row["internal_notes"])
    leaked = Item(
        id="LEAK",
        client_name="Mordor Industrial",
        contact_email="sauron@mordor.example",
        doc_type="Bank Statement",
        description="May 2026 bank statement",
        client_reason="Unusual volume of wire transfers to Nazgul Payroll",
        internal_notes="Unusual volume of wire transfers to Nazgul Payroll",
        deadline=date(2026, 9, 9),
        registered=date(2026, 8, 25),
        schedule_anchor=date(2026, 8, 25),
        owner_name="Gandalf",
        status="Open",
    )
    draft = render_draft(
        {"client_name": leaked.client_name, "email_kind": "overdue", "entries": [{"item": leaked, "action": assess_item(leaked, date(2026, 9, 14))}]},
        FIRM,
    )
    check(draft_is_clean(draft, [leaked]) != [], "leak check accepted a Why Needed sentence in the draft")
    safe = Item(**{**leaked.__dict__, "client_reason": "Needed for the quarterly bank reconciliation.", "id": "SAFE"})
    safe_draft = render_draft(
        {"client_name": safe.client_name, "email_kind": "overdue", "entries": [{"item": safe, "action": assess_item(safe, date(2026, 9, 14))}]},
        FIRM,
    )
    check("Nazgul" not in safe_draft and draft_is_clean(safe_draft, [safe]) == [], safe_draft)

    # 5. An item due today gets a first request, not "Deadline passed".
    due = item_for("2026-09-14", "2026-09-14", 0)
    due.doc_type = "Bank Statement"
    due.period = "2026-08"
    action = assess_item(due, date(2026, 9, 14))
    check(action.kind == "email" and action.email_kind == "initial", f"due-today kind {action}")
    due_draft = render_draft(
        {"client_name": due.client_name, "email_kind": action.email_kind, "entries": [{"item": due, "action": action}]},
        FIRM,
    )
    check("Deadline passed" not in due_draft and "We need the documents below" in due_draft, due_draft)
    sunday = item_for("2026-09-13", "2026-09-14", 0)
    check(assess_item(sunday, date(2026, 9, 14)).email_kind == "initial", "Sunday registration due Monday was overdue")

    # 6. Demo realism is in test_demo, including holidays and closed months.

    # 7. Formatting: human period, dollar amount, no bracket sender, grammatical overdue sentence.
    check("October 2026" in format_period_sample(), "period formatter")
    bare = Item(
        id="BARE",
        client_name="No Owner LLC",
        contact_email="ap@noowner.example",
        doc_type="Invoice",
        description="Vendor invoice",
        client_reason="Large capital expenditure. Needed to decide asset versus expense treatment",
        deadline=date(2026, 9, 12),
        registered=date(2026, 8, 31),
        schedule_anchor=date(2026, 8, 31),
        touches_sent=2,
        last_touch=date(2026, 9, 8),
        amount="847000",
        status="Open",
    )
    bare_action = assess_item(bare, date(2026, 9, 14))
    bare_draft = render_draft(
        {"client_name": bare.client_name, "email_kind": bare_action.email_kind, "entries": [{"item": bare, "action": bare_action}]},
        {"firm_name": "Northline Ledger Co."},
    )
    check("[Sender Name]" not in bare_draft, bare_draft)
    check("Setup is incomplete" in bare_draft and "Northline Ledger Co." in bare_draft, "missing sender was not flagged")
    check("held up:" not in bare_draft, bare_draft)
    check("this work is held up." in bare_draft, bare_draft)
    check("$847,000" in bare_draft, bare_draft)

    # 8. Spaced and dashed cards that pass Luhn are masked. A non-Luhn run is not.
    spaced, found = mask_sensitive("Card 4111 1111 1111 1111 and 4111-1111-1111-1111.")
    check(found and "4111 1111 1111 1111" not in spaced and spaced.count("ending 1111") == 2, spaced)
    untouched, found_bad = mask_sensitive("Not a card 4111 1111 1111 1112.")
    check("4111 1111 1111 1112" in untouched, untouched)

    # Client reply pauses chasing. Month 2026-1 does not match 2026-10. Time zone.
    paused = item_for("2026-11-02", "2026-11-20", 1)
    paused.last_touch = date(2026, 11, 16)
    note_client_reply(paused, tuesday)
    check(paused.status == "Paused", "reply did not pause the item")
    check(assess_item(paused, wednesday).kind == "paused", "a reply did not pause the next day")
    check(not periods_overlap("2026-1", "2026-10"), "January matched October")
    check(periods_overlap("2026-06", "June 2026"), "June did not match 2026-06")
    check(periods_overlap("2026-06 to 2026-08", "2026-07"), "a range missed July")
    moment = datetime(2026, 11, 25, 7, 30, tzinfo=ZoneInfo("UTC"))
    check(today_for(DEFAULT_TIMEZONE, moment) == date(2026, 11, 24), "Los Angeles date was wrong")
    check(today_for("America/New_York", moment) == date(2026, 11, 25), "New York date was wrong")
    check(DEFAULT_TIMEZONE == "America/Los_Angeles", "default zone drifted")


def format_period_sample() -> str:
    from core.engine import format_period
    return format_period("2026-10")


def main() -> int:
    test_worked_examples()
    test_date_rules()
    test_lotr_assess()
    test_precheck()
    test_pdfs()
    test_privacy_and_intake()
    test_demo()
    test_qa_fixes()
    test_repo_shape()
    if FAILURES:
        print(f"{len(FAILURES)} failed")
        for message in FAILURES:
            print(f"  - {message}")
        return 1
    print("All doc-follow-up checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
