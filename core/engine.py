"""Reference implementation of the doc-follow-up rules.

A chat agent follows the markdown in ``core/``. This module is the
executable copy of those same rules, locked by ``tests/run_tests.py``.
If the markdown and this file disagree, fix both in the same change.

The module uses only the Python standard library.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Optional


SCHEMA_VERSION = 1

COLUMNS = [
    "id",
    "client_name",
    "salutation",
    "contact_email",
    "contact_phone",
    "doc_type",
    "description",
    "period",
    "amount",
    "client_reason",
    "internal_notes",
    "deadline",
    "status",
    "owner_name",
    "owner_title",
    "touches_sent",
    "last_touch",
    "next_touch",
    "registered",
    "schedule_anchor",
    "received",
    "lines",
]

STATUSES = (
    "Open",
    "Partial",
    "Received",
    "Accepted",
    "Returned",
    "Bad contact",
    "Call needed",
)

EMAIL_STATUSES = ("Open", "Partial", "Returned")
CLOSED_STATUSES = ("Accepted",)
REVIEW_STATUSES = ("Received",)

# At most this many chase emails, including the initial request.
MAX_TOUCHES = 4

SAFETY_LINE = (
    "This is operational workflow design for collecting client documents. "
    "It is not tax, legal, or accounting advice."
)

DRAFT_BANNER = (
    "DRAFT — a person must approve this before it goes out. "
    "This tool does not send email."
)

PRIVACY_WARNING = (
    "A Social Security number or account number was masked. "
    "Account numbers keep only the last four digits. "
    "Do not ask the client to paste a full number, password, or login into chat."
)

CLIENT_FACING_FIELDS = (
    "client_name",
    "salutation",
    "doc_type",
    "description",
    "period",
    "amount",
    "client_reason",
    "lines",
    "deadline",
)


class RuleError(ValueError):
    """A tracker row or date breaks a rule the agent must not guess through."""


def parse_iso(value: str) -> date:
    """Parse a stored date. Only YYYY-MM-DD is accepted."""
    value = (value or "").strip()
    if not value:
        raise RuleError("Missing date.")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise RuleError(f"Date {value!r} is not YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RuleError(f"Date {value!r} is not a real calendar date.") from exc


def is_business_day(day: date, holidays: Iterable[date] = ()) -> bool:
    """Monday–Friday, excluding any dates the firm listed as holidays."""
    return day.weekday() < 5 and day not in set(holidays)


def first_business_on_or_after(day: date, holidays: Iterable[date] = ()) -> date:
    holidays = set(holidays)
    while not is_business_day(day, holidays):
        day += timedelta(days=1)
    return day


def add_business_days(day: date, count: int, holidays: Iterable[date] = ()) -> date:
    """Move ``count`` business days forward. ``day`` itself is not counted."""
    if count < 0:
        raise RuleError("add_business_days count must be >= 0.")
    holidays = set(holidays)
    cursor = day
    left = count
    while left:
        cursor += timedelta(days=1)
        if is_business_day(cursor, holidays):
            left -= 1
    return cursor


def snap_strictly_before(
    candidate: date, deadline: date, holidays: Iterable[date] = ()
) -> Optional[date]:
    """Move ``candidate`` onto a business day that is still before ``deadline``.

    A weekday candidate is kept. A weekend or holiday moves forward to the
    next business day when that day is still before the deadline, and
    otherwise backward. Returns None when no such day exists.
    """
    holidays = set(holidays)
    if candidate >= deadline:
        return None
    if is_business_day(candidate, holidays):
        return candidate
    forward = candidate
    while not is_business_day(forward, holidays):
        forward += timedelta(days=1)
    if forward < deadline:
        return forward
    backward = candidate
    while not is_business_day(backward, holidays):
        backward -= timedelta(days=1)
    if backward < deadline:
        return backward
    return None


def tier_for(anchor: date, deadline: date) -> str:
    """Freeze the tier from the schedule anchor. Do not recompute it later.

    ``window`` is the number of calendar days from the anchor to the deadline.
    """
    window = (deadline - anchor).days
    if window < 0:
        return "overdue"
    if window <= 4:
        return "tight"
    if window <= 9:
        return "moderate"
    return "comfortable"


def plan_touches(
    anchor: date, deadline: date, holidays: Iterable[date] = ()
) -> list[date]:
    """Return the planned email dates, at most four, all on business days.

    For an item registered on or before the deadline, the last date is the
    first business day after the deadline (one overdue email). Earlier dates
    stay strictly before the deadline, so the call flag cannot fire first.
    Weekend and holiday candidates move onto a business day. Two anchors
    that land on the same business day become one email.
    """
    holidays = set(holidays)
    window = (deadline - anchor).days
    if window < 0:
        first = first_business_on_or_after(anchor, holidays)
        return [
            first,
            add_business_days(first, 1, holidays),
            add_business_days(first, 3, holidays),
            add_business_days(first, 5, holidays),
        ]

    if window <= 4:
        raw = [anchor, anchor + timedelta(days=1), anchor + timedelta(days=2)]
    elif window <= 9:
        raw = [anchor, anchor + timedelta(days=2), anchor + timedelta(days=4)]
    else:
        raw = [
            anchor,
            anchor + timedelta(days=window // 2),
            deadline - timedelta(days=3),
        ]

    pre: list[date] = []
    for candidate in raw:
        snapped = snap_strictly_before(candidate, deadline, holidays)
        if snapped is not None and snapped not in pre:
            pre.append(snapped)
    pre = sorted(pre)[:3]
    overdue = first_business_on_or_after(deadline + timedelta(days=1), holidays)
    return pre + [overdue]


def _blank(value: Optional[str]) -> str:
    return (value or "").strip()


def parse_lines(raw: str) -> list[dict]:
    """Parse ``Label | period | open`` entries separated by semicolons."""
    raw = _blank(raw)
    if not raw:
        return []
    parsed = []
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        bits = [bit.strip() for bit in part.split("|")]
        if len(bits) != 3:
            raise RuleError(
                f"Line {part!r} must be 'label | period | open-or-received'."
            )
        label, period, status = bits
        status = status.lower()
        if status not in ("open", "received"):
            raise RuleError(f"Line status {status!r} must be open or received.")
        if not label:
            raise RuleError("A line needs a label.")
        parsed.append({"label": label, "period": period, "status": status})
    return parsed


def format_lines(lines: list[dict]) -> str:
    return "; ".join(
        f"{line['label']} | {line['period']} | {line['status']}" for line in lines
    )


def open_lines(lines: list[dict]) -> list[dict]:
    return [line for line in lines if line["status"] == "open"]


@dataclass
class Item:
    id: str
    client_name: str
    salutation: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    doc_type: str = ""
    description: str = ""
    period: str = ""
    amount: str = ""
    client_reason: str = ""
    internal_notes: str = ""
    deadline: Optional[date] = None
    status: str = "Open"
    owner_name: str = ""
    owner_title: str = ""
    touches_sent: int = 0
    last_touch: Optional[date] = None
    next_touch: Optional[date] = None
    registered: Optional[date] = None
    schedule_anchor: Optional[date] = None
    received: Optional[date] = None
    lines: list = field(default_factory=list)
    holidays: tuple = ()

    def anchor(self) -> date:
        return self.schedule_anchor or self.registered

    def tier(self) -> str:
        return tier_for(self.anchor(), self.deadline)

    def plan(self) -> list[date]:
        return plan_touches(self.anchor(), self.deadline, self.holidays)

    def to_row(self) -> dict:
        def fmt(value: Optional[date]) -> str:
            return value.isoformat() if value else ""

        return {
            "id": self.id,
            "client_name": self.client_name,
            "salutation": self.salutation,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "doc_type": self.doc_type,
            "description": self.description,
            "period": self.period,
            "amount": self.amount,
            "client_reason": self.client_reason,
            "internal_notes": self.internal_notes,
            "deadline": fmt(self.deadline),
            "status": self.status,
            "owner_name": self.owner_name,
            "owner_title": self.owner_title,
            "touches_sent": str(self.touches_sent),
            "last_touch": fmt(self.last_touch),
            "next_touch": fmt(self.next_touch),
            "registered": fmt(self.registered),
            "schedule_anchor": fmt(self.schedule_anchor or self.registered),
            "received": fmt(self.received),
            "lines": format_lines(self.lines),
        }


def item_from_row(row: dict, holidays: Iterable[date] = ()) -> Item:
    missing = [name for name in ("id", "client_name", "deadline", "registered") if not _blank(row.get(name))]
    if missing:
        raise RuleError(f"Row {row.get('id') or '?'} is missing {', '.join(missing)}.")
    status = _blank(row.get("status")) or "Open"
    if status not in STATUSES:
        raise RuleError(f"Status {status!r} is not one of {', '.join(STATUSES)}.")
    touches_raw = _blank(row.get("touches_sent")) or "0"
    if not re.fullmatch(r"\d+", touches_raw):
        raise RuleError(f"touches_sent {touches_raw!r} must be a whole number.")
    amount = _blank(row.get("amount"))
    if amount and not re.fullmatch(r"\d+(\.\d+)?", amount):
        raise RuleError(
            f"Amount {amount!r} must be a plain number with no $ sign and no commas."
        )
    registered = parse_iso(row["registered"])
    anchor_raw = _blank(row.get("schedule_anchor"))
    item = Item(
        id=_blank(row["id"]),
        client_name=_blank(row["client_name"]),
        salutation=_blank(row.get("salutation")),
        contact_email=_blank(row.get("contact_email")),
        contact_phone=_blank(row.get("contact_phone")),
        doc_type=_blank(row.get("doc_type")),
        description=_blank(row.get("description")),
        period=_blank(row.get("period")),
        amount=amount,
        client_reason=_blank(row.get("client_reason")),
        internal_notes=_blank(row.get("internal_notes")),
        deadline=parse_iso(row["deadline"]),
        status=status,
        owner_name=_blank(row.get("owner_name")),
        owner_title=_blank(row.get("owner_title")),
        touches_sent=int(touches_raw),
        last_touch=parse_iso(row["last_touch"]) if _blank(row.get("last_touch")) else None,
        next_touch=parse_iso(row["next_touch"]) if _blank(row.get("next_touch")) else None,
        registered=registered,
        schedule_anchor=parse_iso(anchor_raw) if anchor_raw else registered,
        received=parse_iso(row["received"]) if _blank(row.get("received")) else None,
        lines=parse_lines(row.get("lines") or ""),
        holidays=tuple(holidays),
    )
    if item.touches_sent > MAX_TOUCHES:
        # Legacy rows can carry a higher count. The assessor will not email them.
        pass
    return item


def load_tracker(text: str, holidays: Iterable[date] = ()) -> list[Item]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise RuleError("Tracker CSV has no header.")
    fields = [name.strip() for name in reader.fieldnames]
    missing = [name for name in COLUMNS if name not in fields]
    if missing:
        raise RuleError("Tracker is missing columns: " + ", ".join(missing))
    items = []
    for row in reader:
        cleaned = {(key or "").strip(): (value or "").strip() for key, value in row.items()}
        if not cleaned.get("id"):
            continue
        items.append(item_from_row(cleaned, holidays))
    return items


def dump_tracker(items: Iterable[Item]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for item in items:
        writer.writerow(item.to_row())
    return buffer.getvalue()


def greeting(salutation: str) -> str:
    """Build the opening line. Never looks at an email address."""
    name = _blank(salutation)
    if not name or "@" in name:
        return "Hello,"
    return f"Hi {name},"


def mask_sensitive(text: str) -> tuple[str, bool]:
    """Mask SSNs and labeled account or routing numbers. Keep the last 4 of an account."""
    found = False

    def ssn_sub(match: re.Match) -> str:
        nonlocal found
        found = True
        return "***-**-****"

    masked = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", ssn_sub, text)

    def labeled_ssn(match: re.Match) -> str:
        nonlocal found
        found = True
        return f"{match.group(1)} ***-**-****"

    masked = re.sub(
        r"(?i)\b(ssn|social security(?: number)?)\b[:\s#-]*\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
        labeled_ssn,
        masked,
    )

    def account_sub(match: re.Match) -> str:
        nonlocal found
        found = True
        digits = re.sub(r"\D", "", match.group(2))
        last4 = digits[-4:] if len(digits) >= 4 else digits
        return f"{match.group(1)} ending {last4}"

    masked = re.sub(
        r"(?i)\b(account|acct|routing|aba)(?:\s*(?:number|no\.?|#))?\b[:\s#-]*([0-9][0-9\-\s]{7,})",
        account_sub,
        masked,
    )

    def long_sub(match: re.Match) -> str:
        nonlocal found
        found = True
        return f"ending {match.group(0)[-4:]}"

    masked = re.sub(r"\b\d{13,16}\b", long_sub, masked)
    return masked, found


def ngrams(text: str, size: int = 4) -> set[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    if len(words) < size:
        return set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def client_facing_text(item: Item) -> str:
    parts = [
        item.client_name,
        item.salutation,
        item.doc_type,
        item.description,
        item.period,
        item.amount,
        item.client_reason,
        format_lines(item.lines),
        item.deadline.isoformat() if item.deadline else "",
    ]
    return "\n".join(parts)


def internal_leaks(draft: str, item: Item) -> list[str]:
    """Return phrases from internal notes that showed up in a client draft.

    A 4-word sequence counts when it is in the notes and not also in the
    client-facing fields. The full note text counts too. This catches a
    pasted note. It cannot catch every paraphrase, which the draft rule
    still forbids.
    """
    notes = _blank(item.internal_notes)
    if not notes:
        return []
    haystack = draft.lower()
    leaks = []
    if notes.lower() in haystack:
        leaks.append(notes)
    allowed = ngrams(client_facing_text(item))
    for gram in sorted(ngrams(notes)):
        if gram in allowed:
            continue
        if gram in haystack:
            leaks.append(gram)
    return leaks


def draft_is_clean(draft: str, items: Iterable[Item]) -> list[str]:
    problems = []
    for item in items:
        for leak in internal_leaks(draft, item):
            problems.append(f"{item.id}: internal text in draft ({leak})")
    return problems


@dataclass
class Action:
    kind: str  # email, call, bad_contact, review, closed, wait, hold
    next_touch: Optional[date] = None
    email_kind: str = ""  # initial, reminder, overdue
    reason: str = ""


def assess_item(item: Item, today: date) -> Action:
    """Decide the next action. Does not trust a stored next_touch."""
    if item.status == "Accepted":
        return Action("closed", reason="Accepted. No follow-up.")
    if item.status == "Received":
        return Action("review", reason="Received and waiting for a person to review it.")
    if item.status == "Bad contact":
        return Action(
            "bad_contact",
            reason="Do not email. The address bounced or the contact is wrong. Ask for a working email or phone.",
        )
    plan = item.plan()
    past_deadline = today > item.deadline
    ceiling = item.touches_sent >= MAX_TOUCHES or item.touches_sent >= len(plan)
    if item.status == "Call needed" or (ceiling and past_deadline):
        return Action(
            "call",
            reason="Email cap reached after the deadline. Call. Do not send another email.",
        )
    if ceiling and not past_deadline:
        return Action(
            "hold",
            next_touch=first_business_on_or_after(item.deadline + timedelta(days=1), item.holidays),
            reason="Email cap reached before the deadline. Do not email again and do not call until the day after the deadline.",
        )
    if item.status not in EMAIL_STATUSES:
        raise RuleError(f"Unhandled status {item.status!r}.")

    slot = plan[item.touches_sent]
    if item.last_touch == today:
        later = [day for day in plan if day > today]
        return Action(
            "wait",
            next_touch=later[0] if later else None,
            reason="An email already went out today. One email per client per day.",
        )
    if slot > today:
        return Action("wait", next_touch=slot, reason="Next planned email is still ahead.")

    due = today if is_business_day(today, item.holidays) else first_business_on_or_after(today, item.holidays)
    if due != today:
        return Action(
            "wait",
            next_touch=due,
            reason="A follow-up is due, and today is not a business day. Send it on the next business day.",
        )
    if past_deadline:
        kind = "overdue"
    elif item.touches_sent == 0:
        kind = "initial"
    else:
        kind = "reminder"
    return Action("email", next_touch=today, email_kind=kind, reason="Planned email is due today.")


@dataclass
class Assessment:
    as_of: date
    email_groups: list
    call_needed: list
    bad_contact: list
    waiting: list
    hold: list
    review: list
    closed: list


def assess(items: Iterable[Item], today: date) -> Assessment:
    groups: dict[str, list] = {}
    order: list[str] = []
    buckets = {name: [] for name in ("call_needed", "bad_contact", "waiting", "hold", "review", "closed")}
    for item in items:
        action = assess_item(item, today)
        entry = {"item": item, "action": action}
        if action.kind == "email":
            key = item.client_name.casefold()
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(entry)
        elif action.kind == "call":
            buckets["call_needed"].append(entry)
        elif action.kind == "bad_contact":
            buckets["bad_contact"].append(entry)
        elif action.kind == "wait":
            buckets["waiting"].append(entry)
        elif action.kind == "hold":
            buckets["hold"].append(entry)
        elif action.kind == "review":
            buckets["review"].append(entry)
        else:
            buckets["closed"].append(entry)
    email_groups = []
    for key in order:
        entries = groups[key]
        kinds = {entry["action"].email_kind for entry in entries}
        if "overdue" in kinds:
            group_kind = "overdue"
        elif kinds == {"initial"}:
            group_kind = "initial"
        else:
            group_kind = "reminder"
        email_groups.append(
            {
                "client_name": entries[0]["item"].client_name,
                "email_kind": group_kind,
                "entries": entries,
            }
        )
    return Assessment(as_of=today, email_groups=email_groups, **buckets)


def _fmt_amount(amount: str) -> str:
    if not amount:
        return ""
    if "." in amount:
        whole, frac = amount.split(".", 1)
        return f"{int(whole):,}.{frac}"
    return f"{int(amount):,}"


def _item_bullet(item: Item) -> list[str]:
    """Client-facing lines for one item. Uses a field whitelist."""
    lines = open_lines(item.lines)
    label = item.description
    if item.period and item.period not in label:
        label = f"{label} ({item.period})"
    bullets = [f"- {item.doc_type}: {label}.".replace(": :", ":")]
    if lines:
        bullets.append("  Still missing:")
        for line in lines:
            period = f" ({line['period']})" if line["period"] else ""
            bullets.append(f"  - {line['label']}{period}")
    elif item.lines:
        bullets.append("  Every listed line is marked received. A person should confirm that before closing the request.")
    if item.client_reason:
        bullets.append(f"  Why we need it: {item.client_reason}")
    else:
        bullets.append("  Why we need it: needed for the books on file.")
    if item.amount:
        bullets.append(f"  Amount on file: {_fmt_amount(item.amount)}")
    alternative = ALTERNATIVES.get(item.doc_type.lower())
    if alternative:
        bullets.append(f"  If the original is not handy: {alternative}")
    if item.deadline:
        bullets.append(f"  Deadline on file: {item.deadline.isoformat()}")
    return bullets


# Neutral, one-sentence alternatives. Not final client-marketing copy.
ALTERNATIVES = {
    "bank statement": "Download the PDF for that month from the bank's statement page. Do not send a login.",
    "credit card statement": "Download the PDF for that month from the card issuer. Do not send a login.",
    "loan statement": "Download the latest statement from the lender, or ask the lender to resend it.",
    "receipt": "Ask the vendor to resend or reissue the receipt.",
    "invoice": "Ask the vendor to resend the invoice.",
    "purchase order": "Ask the vendor, or the person who issued the PO, to resend it.",
    "contract": "Ask the other party for a signed copy if the original is missing.",
    "log": "Export the log again from the system that created it.",
    "forwarded email": "Forward the original thread. A screenshot is harder to verify.",
    "w-2": "Download it from the employer or payroll provider, or ask them to reissue it.",
    "1099-nec": "Download it from the payer's portal, or ask the payer to resend it.",
    "k-1": "Ask the partnership or its preparer to resend the K-1.",
    "payroll report": "Export it again from the payroll provider. Do not send a login.",
    "sales tax return": "Download the filed return from the state portal, or the copy saved when it was filed.",
    "prior-year return": "Use the copy that was saved when it was filed, or ask the prior preparer to resend it.",
    "1098": "Download it from the lender.",
}


def subject_for(group: dict) -> str:
    """Human subject with no touch count and no bulk-mail prefix."""
    items = [entry["item"] for entry in group["entries"]]
    if len(items) == 1:
        topic = items[0].doc_type
        if items[0].period:
            topic = f"{items[0].period} {topic}"
    else:
        topic = f"{len(items)} documents"
    if group["email_kind"] == "overdue":
        return f"Deadline passed: {topic}"
    return f"Documents needed: {topic}"


def render_draft(group: dict, firm: dict) -> str:
    """Render one client email from client-facing fields only."""
    items = [entry["item"] for entry in group["entries"]]
    primary = items[0]
    for entry in group["entries"]:
        if entry["action"].email_kind == "overdue":
            primary = entry["item"]
            break
    salutation = next((item.salutation for item in items if _blank(item.salutation)), "")
    email = next((item.contact_email for item in items if _blank(item.contact_email)), "")
    lines = [
        DRAFT_BANNER,
        "",
        f"To: {email or '(no email on file)'}",
        f"Subject: {subject_for(group)}",
        "",
        greeting(salutation),
        "",
        "Hope you are doing well. We still need the documents below.",
        "",
    ]
    for item in items:
        lines.extend(_item_bullet(item))
        lines.append("")
    overdue_items = [
        entry["item"]
        for entry in group["entries"]
        if entry["action"].email_kind == "overdue"
    ]
    if overdue_items:
        named = "; ".join(
            f"{item.doc_type} (deadline {item.deadline.isoformat()})" for item in overdue_items
        )
        reason = overdue_items[0].client_reason or "the work that depends on it"
        lines.append(
            f"The deadline has passed for: {named}. Without those files, this work is held up: {reason}"
        )
        lines.append("")
    lines.append("Please reply to this email with the files attached.")
    lines.append("")
    lines.append("Thank you,")
    lines.append("")
    lines.append(primary.owner_name or "[Sender Name]")
    if primary.owner_title:
        lines.append(primary.owner_title)
    if firm.get("firm_name"):
        lines.append(firm["firm_name"])
    if firm.get("firm_phone"):
        lines.append(firm["firm_phone"])
    if firm.get("firm_email"):
        lines.append(firm["firm_email"])
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_client_reply(item: Item, what_arrived: str, what_is_needed: str, firm: dict) -> str:
    """Thank-you reply after a person decides the file is not what was needed.

    ``what_is_needed`` is the corrected ask. For a request that may be wrong,
    pass the corrected document, not the original bad identifier.
    """
    lines = [
        DRAFT_BANNER,
        "",
        f"To: {item.contact_email or '(no email on file)'}",
        "Subject: " + subject_for(
            {"email_kind": "reminder", "entries": [{"item": item, "action": Action("email")}]}
        ),
        "",
        greeting(item.salutation),
        "",
        f"Thank you for sending {what_arrived}.",
        "",
        f"We still need {what_is_needed}.",
        "",
        "Please reply to this email with the file attached.",
        "",
        "Thank you,",
        "",
        item.owner_name or "[Sender Name]",
    ]
    if item.owner_title:
        lines.append(item.owner_title)
    if firm.get("firm_name"):
        lines.append(firm["firm_name"])
    if firm.get("firm_email"):
        lines.append(firm["firm_email"])
    lines.append("")
    return "\n".join(lines)


def render_call_note(item: Item) -> str:
    """Internal note for the firm. Not a client email."""
    phone = item.contact_phone or "(no phone on file — ask the firm for one before calling)"
    return "\n".join(
        [
            f"CALL — do not email {item.client_name}.",
            f"Phone: {phone}",
            f"Item: {item.id} {item.doc_type} — {item.description}",
            f"Deadline on file: {item.deadline.isoformat()}",
            f"Emails already sent: {item.touches_sent}",
            "Say which documents are missing, the deadline on file, and where to send the files.",
            "Do not mention internal notes.",
            "",
        ]
    )


def render_bad_contact_note(item: Item) -> str:
    return "\n".join(
        [
            f"BAD CONTACT — do not email {item.contact_email or '(blank)'} for {item.client_name}.",
            f"Phone on file: {item.contact_phone or '(none)'}",
            f"Item: {item.id} {item.doc_type} — {item.description}",
            "Ask the firm for a working email or phone. A bounce stops email immediately.",
            "Do not mention internal notes to the client.",
            "",
        ]
    )


def apply_next_touch(items: Iterable[Item], today: date) -> None:
    """Write the computed next_touch back onto each item. Clears it when no email remains."""
    for item in items:
        action = assess_item(item, today)
        if action.kind == "email":
            item.next_touch = today
        elif action.kind in ("wait", "hold"):
            item.next_touch = action.next_touch
        else:
            item.next_touch = None
        if action.kind == "call" and item.status in ("Open", "Partial", "Returned"):
            item.status = "Call needed"


# --- received documents -----------------------------------------------------

PRECHECK_OUTCOMES = (
    "MATCH",
    "MISMATCH",
    "PARTIAL",
    "INCOMPLETE",
    "REQUEST_MAY_BE_WRONG",
)


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _number_in(text: str) -> str:
    match = re.search(
        r"\b(?:PO|invoice|inv|receipt|policy)\s*#?\s*([A-Za-z]{0,6}-?\d[\w-]*)",
        text or "",
        re.I,
    )
    return match.group(1).upper() if match else ""


@dataclass
class Precheck:
    outcome: str
    summary: str
    ask_client_for: str
    correct_request_to: str
    line_updates: list = field(default_factory=list)
    needs_confirmation: bool = False


def precheck(item: Item, document: dict, open_item_count: int = 1) -> Precheck:
    """Compare one received document with one request.

    ``document`` keys: doc_type, period, entity, account_last4, doc_number,
    subject, pointer ({number, subject, issued}), complete (bool),
    lines_covered (list of labels).
    """
    confirm = open_item_count >= 2
    doc_type = _norm(document.get("doc_type") or "")
    req_type = _norm(item.doc_type)
    doc_number = (document.get("doc_number") or _number_in(document.get("text") or "")).upper()
    req_number = (
        document.get("requested_number")
        or _number_in(item.description)
        or ""
    ).upper()
    doc_subject = _norm(document.get("subject") or "")
    pointer = document.get("pointer") or {}
    pointer_number = (pointer.get("number") or "").upper()
    pointer_subject = _norm(pointer.get("subject") or "")
    description_norm = _norm(item.description)

    subject_conflict = False
    if doc_subject and description_norm:
        # Conflict when the document's subject words are not what was requested
        # and the request's distinctive subject is absent from the document subject.
        requested_subject = _norm(document.get("requested_subject") or "")
        if requested_subject and requested_subject not in doc_subject and doc_subject not in requested_subject:
            subject_conflict = True
        elif requested_subject == "" and pointer_subject and pointer_subject in description_norm and pointer_subject not in doc_subject:
            subject_conflict = True

    number_match = bool(req_number and doc_number and req_number == doc_number)
    pointer_names_other = bool(
        pointer_number and req_number and pointer_number != req_number and pointer_subject and pointer_subject in description_norm
    )
    if number_match and (subject_conflict or pointer_names_other):
        issued = pointer.get("issued") or ""
        issued_bit = f", issued {issued}" if issued else ""
        corrected = ""
        if pointer_number and pointer.get("subject"):
            corrected = f"{pointer.get('subject')} as {pointer_number}{issued_bit}"
        summary = (
            f"The file is {doc_number or 'the numbered document'} for {document.get('subject') or 'a different subject'}. "
            "The number matches the request, but the contents do not."
        )
        if corrected:
            summary += f" The file points to {corrected}."
        ask = ""
        if corrected:
            ask = (
                "Do not ask the client for the same number again. "
                f"If a person confirms the request was wrong, ask for {corrected}."
            )
        else:
            ask = "Do not ask the client to resend this same document. Ask a person to correct the request first."
        return Precheck(
            outcome="REQUEST_MAY_BE_WRONG",
            summary=summary,
            ask_client_for=ask,
            correct_request_to=corrected,
            needs_confirmation=confirm,
        )

    if req_type and doc_type and req_type not in doc_type and doc_type not in req_type:
        return Precheck(
            outcome="MISMATCH",
            summary=f"Requested a {item.doc_type}, received a {document.get('doc_type')}.",
            ask_client_for=f"Ask for the {item.doc_type} that was requested: {item.description}",
            correct_request_to="",
            needs_confirmation=confirm,
        )

    req_period = _norm(item.period)
    doc_period = _norm(document.get("period") or "")
    if req_period and doc_period and req_period not in doc_period and doc_period not in req_period:
        # A document that covers some lines of a multi-line request is partial, not a hard mismatch.
        if not (item.lines and document.get("lines_covered")):
            return Precheck(
                outcome="MISMATCH",
                summary=f"Requested period {item.period}, received {document.get('period')}.",
                ask_client_for=f"Thank them, and ask for {item.period} only. Do not ask again for {document.get('period')}.",
                correct_request_to="",
                needs_confirmation=confirm,
            )

    req_entity = _norm(item.client_name)
    doc_entity = _norm(document.get("entity") or "")
    if doc_entity and req_entity and doc_entity not in req_entity and req_entity not in doc_entity:
        return Precheck(
            outcome="MISMATCH",
            summary=f"Requested {item.client_name}, received {document.get('entity')}.",
            ask_client_for=f"Ask for the document for {item.client_name}.",
            correct_request_to="",
            needs_confirmation=confirm,
        )

    req_last4 = re.search(r"(?:ending|last\s*4|xx+)\s*(\d{4})", item.description, re.I)
    doc_last4 = (document.get("account_last4") or "").strip()
    if req_last4 and doc_last4 and req_last4.group(1) != doc_last4:
        return Precheck(
            outcome="MISMATCH",
            summary=f"Requested account ending {req_last4.group(1)}, received ending {doc_last4}.",
            ask_client_for=f"Ask for account ending {req_last4.group(1)}.",
            correct_request_to="",
            needs_confirmation=confirm,
        )

    if document.get("complete") is False:
        return Precheck(
            outcome="INCOMPLETE",
            summary="The document looks incomplete (pages missing or amounts cut off).",
            ask_client_for=f"Thank them, and ask for the complete {item.doc_type}.",
            correct_request_to="",
            needs_confirmation=confirm,
        )

    if item.lines:
        covered = [_norm(label) for label in document.get("lines_covered") or []]

        def hit(line: dict) -> bool:
            if line["status"] == "received":
                return True
            label_norm = _norm(line["label"])
            return any(
                label_norm in covered_label or covered_label in label_norm
                for covered_label in covered
            )

        updates = []
        remaining = []
        any_new = False
        for line in item.lines:
            if hit(line):
                if line["status"] != "received":
                    updates.append({**line, "status": "received"})
                    any_new = True
            else:
                remaining.append(line["label"])
        if any_new and remaining:
            return Precheck(
                outcome="PARTIAL",
                summary="The file covers some lines and not the rest. Keep chasing only what is still open.",
                ask_client_for="Thank them for what arrived. Ask only for: " + "; ".join(remaining),
                correct_request_to="",
                line_updates=updates,
                needs_confirmation=confirm,
            )
        if not remaining:
            return Precheck(
                outcome="MATCH",
                summary="Every open line is covered. A person still confirms before the request is accepted.",
                ask_client_for="",
                correct_request_to="",
                line_updates=updates,
                needs_confirmation=confirm,
            )
        return Precheck(
            outcome="MISMATCH",
            summary="The file does not cover any open line on this request.",
            ask_client_for="Thank them, and ask only for: " + "; ".join(remaining),
            correct_request_to="",
            needs_confirmation=confirm,
        )

    return Precheck(
        outcome="MATCH",
        summary="Type, period, entity, and completeness agree. A person still confirms.",
        ask_client_for="",
        correct_request_to="",
        needs_confirmation=confirm,
    )


def apply_precheck(item: Item, result: Precheck, today: date) -> Item:
    """Update one item from a pre-check. Does not email anyone."""
    if result.outcome == "PARTIAL":
        covered = {_norm(line["label"]) for line in result.line_updates}
        new_lines = []
        for line in item.lines:
            if _norm(line["label"]) in covered:
                new_lines.append({**line, "status": "received"})
            else:
                new_lines.append(line)
        item.lines = new_lines
        item.status = "Partial"
        item.received = today
        # The client responded, so the unanswered-email streak starts over.
        # The new anchor freezes a fresh tier for whatever lines are still open.
        item.touches_sent = 0
        item.last_touch = None
        item.schedule_anchor = today
        return item
    if result.outcome == "MATCH":
        item.status = "Received"
        item.received = today
        if result.line_updates:
            covered = {_norm(line["label"]) for line in result.line_updates}
            item.lines = [
                {**line, "status": "received"} if _norm(line["label"]) in covered else line
                for line in item.lines
            ]
        return item
    if result.outcome in ("MISMATCH", "INCOMPLETE", "REQUEST_MAY_BE_WRONG"):
        # Stop chase email until a person reviews. Do not auto-write a client ask.
        item.status = "Received"
        item.received = today
        return item
    raise RuleError(f"Unknown pre-check outcome {result.outcome!r}.")


def return_item(item: Item, today: date) -> Item:
    """Reviewer rejected the file. The rejection email is the new touch 1.

    The client did respond, so the old unanswered count does not carry forward.
    The cadence is re-anchored on the review date and the tier is frozen again.
    """
    item.status = "Returned"
    item.schedule_anchor = today
    item.touches_sent = 0
    item.last_touch = None
    item.received = today
    return item


# --- intake -----------------------------------------------------------------

HEADER_ALIASES = {
    "id": "id",
    "client": "client_name",
    "client name": "client_name",
    "customer": "client_name",
    "company": "client_name",
    "salutation": "salutation",
    "first name": "salutation",
    "contact first name": "salutation",
    "contact name": "salutation",
    "email": "contact_email",
    "contact email": "contact_email",
    "e-mail": "contact_email",
    "phone": "contact_phone",
    "contact phone": "contact_phone",
    "doc type": "doc_type",
    "document type": "doc_type",
    "type": "doc_type",
    "description": "description",
    "item": "description",
    "what we need": "description",
    "period": "period",
    "amount": "amount",
    "client reason": "client_reason",
    "reason": "client_reason",
    "why needed": "client_reason",
    "client-facing reason": "client_reason",
    "internal notes": "internal_notes",
    "notes": "internal_notes",
    "private notes": "internal_notes",
    "deadline": "deadline",
    "due": "deadline",
    "status": "status",
    "owner": "owner_name",
    "owner name": "owner_name",
    "assigned to": "owner_name",
    "owner title": "owner_title",
    "title": "owner_title",
    "touches sent": "touches_sent",
    "touches": "touches_sent",
    "follow-ups sent": "touches_sent",
    "followups sent": "touches_sent",
    "last touch": "last_touch",
    "last follow-up": "last_touch",
    "next touch": "next_touch",
    "next follow-up due": "next_touch",
    "registered": "registered",
    "date registered": "registered",
    "schedule anchor": "schedule_anchor",
    "received": "received",
    "date received": "received",
    "lines": "lines",
}


@dataclass
class Interpretation:
    rows: list
    questions: list
    warnings: list
    assumptions: list
    masked: bool = False


_OFFSET = re.compile(r"^[+-]?\d+d$")
_MDY = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def resolve_token(token: str, today: date) -> tuple[str, Optional[str]]:
    """Resolve one date token to YYYY-MM-DD. Returns (value, assumption or None)."""
    token = token.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        parse_iso(token)
        return token, None
    if _OFFSET.fullmatch(token):
        days = int(token[:-1])
        return (today + timedelta(days=days)).isoformat(), None
    match = _MDY.fullmatch(token)
    if match:
        month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            resolved = date(year, month, day)
        except ValueError as exc:
            raise RuleError(f"{token} is not a real date.") from exc
        return resolved.isoformat(), f"Read {token} as month/day/year → {resolved.isoformat()}."
    if re.fullmatch(r"month:[+-]?\d+", token):
        shift = int(token.split(":")[1])
        month_index = today.year * 12 + (today.month - 1) + shift
        year, month = divmod(month_index, 12)
        return f"{year:04d}-{month + 1:02d}", None
    if re.fullmatch(r"year:[+-]?\d+", token):
        shift = int(token.split(":")[1])
        return f"{today.year + shift:04d}", None
    raise RuleError(f"Cannot read date {token!r}. Use YYYY-MM-DD.")


def resolve_period(token: str, today: date) -> str:
    token = token.strip()
    if token.startswith("month:") or token.startswith("year:"):
        value, _ = resolve_token(token, today)
        return value
    return token


def resolve_tracker_text(text: str, today: date) -> str:
    """Replace relative date tokens in a demo CSV. Leaves the header intact."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise RuleError("Tracker CSV has no header.")
    fields = list(reader.fieldnames)
    date_fields = {
        "deadline",
        "last_touch",
        "next_touch",
        "registered",
        "schedule_anchor",
        "received",
    }
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in reader:
        if not (row.get("id") or "").strip():
            continue
        for key in date_fields:
            raw = (row.get(key) or "").strip()
            if not raw:
                continue
            resolved, _ = resolve_token(raw, today)
            row[key] = resolved
        period = (row.get("period") or "").strip()
        if period:
            row["period"] = resolve_period(period, today)
        description = row.get("description") or ""
        if "{period}" in description:
            row["description"] = description.replace("{period}", row.get("period") or "")
        lines_raw = row.get("lines") or ""
        if lines_raw:
            rebuilt = []
            for part in lines_raw.split(";"):
                bits = [bit.strip() for bit in part.split("|")]
                if len(bits) == 3:
                    token = bits[1]
                    if token.startswith(("month:", "year:")):
                        bits[1] = resolve_period(token, today)
                    elif _OFFSET.fullmatch(token) or _MDY.fullmatch(token):
                        bits[1], _ = resolve_token(token, today)
                rebuilt.append(" | ".join(bits))
            row["lines"] = "; ".join(rebuilt)
        writer.writerow(row)
    return buffer.getvalue()


def _empty_row() -> dict:
    return {column: "" for column in COLUMNS}


def interpret_text(text: str, today: date) -> Interpretation:
    """Normalize a paste or CSV into tracker rows. Ask instead of inventing."""
    raw = text.strip()
    if not raw:
        return Interpretation([], ["The paste was empty. Paste a list or a CSV."], [], [])
    warnings: list[str] = []
    assumptions: list[str] = []
    masked_any = False

    def protect(value: str) -> str:
        nonlocal masked_any
        masked, found = mask_sensitive(value)
        if found:
            masked_any = True
        return masked

    sample = raw.splitlines()[0]
    looks_tabular = "," in sample and any(
        alias in sample.lower() for alias in ("client", "deadline", "email", "description")
    )
    if looks_tabular:
        rows, questions = _interpret_csv(raw, today, protect, assumptions)
    else:
        rows, questions = _interpret_lines(raw, today, protect, assumptions)
    if masked_any:
        warnings.append(PRIVACY_WARNING)
    questions.extend(_duplicate_questions(rows))
    return Interpretation(rows, questions, warnings, assumptions, masked_any)


def _interpret_csv(raw, today, protect, assumptions):
    reader = csv.DictReader(io.StringIO(raw))
    questions = []
    rows = []
    for index, source in enumerate(reader, start=1):
        mapped = _empty_row()
        unknown = []
        for key, value in source.items():
            if key is None:
                continue
            alias = HEADER_ALIASES.get(key.strip().lower())
            value = protect((value or "").strip())
            if alias is None:
                if value:
                    unknown.append(key.strip())
                continue
            if alias in mapped and mapped[alias] and value and mapped[alias] != value:
                questions.append(f"Row {index}: both columns wrote {alias}. I kept the first value.")
                continue
            mapped[alias] = value
        if unknown:
            questions.append(
                "Row {0}: I did not recognize columns {1}. I left them out.".format(
                    index, ", ".join(unknown)
                )
            )
        _finish_row(mapped, index, today, questions, assumptions)
        if mapped["client_name"] or mapped["description"]:
            rows.append(mapped)
    return rows, questions


def _interpret_lines(raw, today, protect, assumptions):
    questions = []
    rows = []
    for index, line in enumerate(raw.splitlines(), start=1):
        line = protect(line.strip())
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s+[–—|-]\s+|\t", line)
        parts = [part.strip(" -") for part in parts if part.strip(" -")]
        mapped = _empty_row()
        if parts:
            mapped["client_name"] = parts[0]
        if len(parts) >= 2:
            mapped["description"] = parts[1]
        if len(parts) >= 3:
            mapped["deadline"] = parts[2]
        mapped["internal_notes"] = ""
        # Phone calls are not email touches. Do not turn "called twice" into a count.
        if re.search(r"\bcalled\b", line, re.I):
            mapped["internal_notes"] = "Paste said the firm had called. Calls are not email touches; touch count left at 0."
            questions.append(
                f"Line {index} ({mapped['client_name'] or 'this line'}): I saw a phone call, not an email. Touch count is 0 until you say emails were sent."
            )
        _finish_row(mapped, index, today, questions, assumptions, from_prose=True)
        rows.append(mapped)
    return rows, questions


def _finish_row(mapped, index, today, questions, assumptions, from_prose=False):
    label = mapped["client_name"] or f"row {index}"
    if not mapped["id"]:
        mapped["id"] = f"NEW-{index:03d}"
    if not mapped["client_name"]:
        questions.append(f"Row {index}: there is no client name. I did not invent one.")
    if not mapped["doc_type"]:
        questions.append(f"{label}: what type of document is this? I did not guess.")
    if not mapped["description"]:
        questions.append(f"{label}: what exactly is missing? I did not invent an item.")
    if not mapped["deadline"]:
        questions.append(f"{label}: what is the deadline? I did not invent a date.")
    else:
        try:
            resolved, assumption = resolve_token(mapped["deadline"], today)
            mapped["deadline"] = resolved
            if assumption:
                assumptions.append(f"{label}: {assumption}")
        except RuleError:
            questions.append(f"{label}: I could not read deadline {mapped['deadline']!r}. Use YYYY-MM-DD.")
            mapped["deadline"] = ""
    if not mapped["registered"]:
        mapped["registered"] = today.isoformat()
        assumptions.append(f"{label}: no registration date in the paste. I used today ({today.isoformat()}) as the registration date.")
    else:
        try:
            resolved, assumption = resolve_token(mapped["registered"], today)
            mapped["registered"] = resolved
            if assumption:
                assumptions.append(f"{label}: {assumption}")
        except RuleError:
            questions.append(f"{label}: I could not read registered date {mapped['registered']!r}.")
            mapped["registered"] = ""
    for key in ("last_touch", "next_touch", "schedule_anchor", "received"):
        if not mapped[key]:
            continue
        try:
            resolved, assumption = resolve_token(mapped[key], today)
            mapped[key] = resolved
            if assumption:
                assumptions.append(f"{label}: {assumption}")
        except RuleError:
            questions.append(f"{label}: I could not read {key} {mapped[key]!r}.")
            mapped[key] = ""
    if mapped["period"]:
        try:
            mapped["period"] = resolve_period(mapped["period"], today)
        except RuleError:
            questions.append(f"{label}: I could not read period {mapped['period']!r}.")
            mapped["period"] = ""
    elif from_prose:
        questions.append(f"{label}: what period does this cover? I did not assume a month or year.")
    if not mapped["contact_email"]:
        questions.append(f"{label}: what email should a draft use? I did not invent one.")
    # Salutation is only what the user typed. Never the mailbox name.
    if not mapped["salutation"]:
        questions.append(
            f"{label}: no first name or salutation. Drafts will say Hello, until you supply one. I did not read it from the email address."
        )
    if mapped["amount"]:
        cleaned = mapped["amount"].replace("$", "").replace(",", "").strip()
        if re.fullmatch(r"\d+(\.\d+)?", cleaned):
            mapped["amount"] = cleaned
        else:
            questions.append(f"{label}: amount {mapped['amount']!r} is not a plain number. I left it blank.")
            mapped["amount"] = ""
    if not mapped["status"]:
        mapped["status"] = "Open"
    if not mapped["touches_sent"]:
        mapped["touches_sent"] = "0"
    if not mapped["schedule_anchor"] and mapped["registered"]:
        mapped["schedule_anchor"] = mapped["registered"]
    if not mapped["client_reason"]:
        mapped["client_reason"] = ""
        questions.append(
            f"{label}: why is this needed, in words a client can read? I left the client-facing reason blank and did not copy internal notes into it."
        )
    else:
        questions.append(
            f"{label}: confirm this reason is safe to show the client, and move anything private into internal notes: {mapped['client_reason']}"
        )
    if mapped["touches_sent"] not in ("", "0"):
        assumptions.append(
            f"{label}: touch count {mapped['touches_sent']} includes the initial email. Say if that number counted reminders only."
        )
    return mapped


def _duplicate_questions(rows: list[dict]) -> list[str]:
    seen = {}
    questions = []
    for row in rows:
        key = (
            row["client_name"].casefold(),
            row["doc_type"].casefold(),
            row["period"].casefold(),
            row["description"].casefold(),
        )
        if not row["client_name"]:
            continue
        if key in seen:
            questions.append(
                f"Possible duplicate: {row['id']} and {seen[key]} are the same client, type, period, and description. I kept both. Say which to drop."
            )
        else:
            seen[key] = row["id"]
    return questions


def understood_table(rows: list[dict]) -> str:
    """Plain-text table of what intake understood. Safe to show the user."""
    headers = ["id", "client_name", "salutation", "contact_email", "doc_type", "description", "period", "deadline", "status"]
    show = []
    for row in rows:
        show.append([mask_sensitive(row.get(column, ""))[0] for column in headers])
    widths = [len(header) for header in headers]
    for values in show:
        for index, value in enumerate(values):
            widths[index] = max(widths[index], len(value))
    def fmt(values):
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(values))
    lines = [fmt(headers), fmt(["-" * width for width in widths])]
    lines.extend(fmt(values) for values in show)
    return "\n".join(lines)


def kit_header() -> str:
    return f"{SAFETY_LINE}\n\n{DRAFT_BANNER}\n"


def weekday_name(day: date) -> str:
    return day.strftime("%A")


def example_plan(anchor: str, deadline: str, holidays: Iterable[date] = ()) -> dict:
    start = parse_iso(anchor)
    end = parse_iso(deadline)
    dates = plan_touches(start, end, holidays)
    return {
        "tier": tier_for(start, end),
        "window_days": (end - start).days,
        "dates": [day.isoformat() for day in dates],
    }
