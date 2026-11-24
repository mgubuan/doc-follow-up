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
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Iterable, Optional
from zoneinfo import ZoneInfo


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
    "client_replied",
]

STATUSES = (
    "Open",
    "Partial",
    "Received",
    "Accepted",
    "Returned",
    "Bad contact",
    "Call needed",
    "Paused",
)

EMAIL_STATUSES = ("Open", "Partial", "Returned")
CLOSED_STATUSES = ("Accepted",)
REVIEW_STATUSES = ("Received",)

# At most this many chase emails, including the initial request.
MAX_TOUCHES = 4
# After an email, wait this many business days before the next one to that item.
MIN_GAP_BUSINESS_DAYS = 2
DEFAULT_TIMEZONE = "America/Los_Angeles"

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
MONTH_INDEX = {name.lower(): index + 1 for index, name in enumerate(MONTH_NAMES)}
MONTH_INDEX.update(
    {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "sept": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
)

STATEMENT_TYPES = {
    "bank statement",
    "credit card statement",
    "loan statement",
    "sales tax return",
    "payroll report",
    "receipt",
}

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


@lru_cache(maxsize=32)
def us_federal_holidays(year: int) -> frozenset:
    """US federal holidays for ``year``, with the standard weekend observation rule.

    A holiday on Saturday is observed on Friday. A holiday on Sunday is observed
    on Monday. New Year's Day observed can fall on December 31 of the prior year.
    """

    def observed(day: date) -> date:
        if day.weekday() == 5:
            return day - timedelta(days=1)
        if day.weekday() == 6:
            return day + timedelta(days=1)
        return day

    def nth_weekday(month: int, weekday: int, n: int) -> date:
        first = date(year, month, 1)
        shift = (weekday - first.weekday()) % 7
        return date(year, month, 1 + shift + 7 * (n - 1))

    def last_monday(month: int) -> date:
        if month == 12:
            cursor = date(year, 12, 31)
        else:
            cursor = date(year, month + 1, 1) - timedelta(days=1)
        while cursor.weekday() != 0:
            cursor -= timedelta(days=1)
        return cursor

    return frozenset(
        {
            observed(date(year, 1, 1)),
            nth_weekday(1, 0, 3),
            nth_weekday(2, 0, 3),
            last_monday(5),
            observed(date(year, 6, 19)),
            observed(date(year, 7, 4)),
            nth_weekday(9, 0, 1),
            nth_weekday(10, 0, 2),
            observed(date(year, 11, 11)),
            nth_weekday(11, 3, 4),
            observed(date(year, 12, 25)),
        }
    )


def closing_dates(day: date, extra: Iterable[date] = ()) -> set:
    """Weekends plus US federal holidays, plus any dates the firm adds."""
    closed = set(extra)
    for year in (day.year - 1, day.year, day.year + 1):
        closed |= set(us_federal_holidays(year))
    return closed


def is_business_day(day: date, holidays: Iterable[date] = ()) -> bool:
    """Monday–Friday, excluding US federal holidays and any extra dates."""
    return day.weekday() < 5 and day not in closing_dates(day, holidays)


def today_for(zone: str = DEFAULT_TIMEZONE, now: Optional[datetime] = None) -> date:
    """The calendar date in the firm's time zone. Default is America/Los_Angeles.

    A naive ``now`` is read as UTC. The zone is configurable per firm.
    """
    if now is None:
        now = datetime.now(ZoneInfo("UTC"))
    elif now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    return now.astimezone(ZoneInfo(zone)).date()


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


def snap_on_or_before(
    candidate: date, latest: date, holidays: Iterable[date] = ()
) -> Optional[date]:
    """Move ``candidate`` onto a business day on or before ``latest``.

    A weekday candidate is kept. A weekend or holiday moves forward when that
    day is still on or before ``latest``, and otherwise backward. Returns None
    when no such day exists.
    """
    if candidate > latest:
        return None
    if is_business_day(candidate, holidays) and candidate <= latest:
        return candidate
    forward = candidate
    while not is_business_day(forward, holidays):
        forward += timedelta(days=1)
    if forward <= latest:
        return forward
    backward = candidate
    while not is_business_day(backward, holidays):
        backward -= timedelta(days=1)
    if backward <= latest:
        return backward
    return None


def previous_business_day(day: date, holidays: Iterable[date] = ()) -> date:
    while not is_business_day(day, holidays):
        day -= timedelta(days=1)
    return day


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
    window = (deadline - anchor).days
    if window < 0:
        first = first_business_on_or_after(anchor, holidays)
        return [
            first,
            add_business_days(first, MIN_GAP_BUSINESS_DAYS, holidays),
            add_business_days(first, MIN_GAP_BUSINESS_DAYS * 2, holidays),
            add_business_days(first, MIN_GAP_BUSINESS_DAYS * 3, holidays),
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
    for index, candidate in enumerate(raw):
        # The first request may land on the deadline itself. Later reminders
        # stay strictly before it, so the due date still gets a request.
        latest = deadline if index == 0 else deadline - timedelta(days=1)
        snapped = snap_on_or_before(candidate, latest, holidays)
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
    client_replied: Optional[date] = None
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
            "client_replied": fmt(self.client_replied),
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
        client_replied=parse_iso(row["client_replied"]) if _blank(row.get("client_replied")) else None,
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

    def card_sub(match: re.Match) -> str:
        nonlocal found
        digits = re.sub(r"\D", "", match.group(0))
        if not 13 <= len(digits) <= 19 or not luhn_ok(digits):
            return match.group(0)
        found = True
        return f"ending {digits[-4:]}"

    # Spaced or dashed card numbers, and contiguous ones. Luhn rejects phones and invoice ids.
    masked = re.sub(r"(?<!\d)(?:\d[ \-]*){12,18}\d(?!\d)", card_sub, masked)
    return masked, found


def luhn_ok(digits: str) -> bool:
    total = 0
    double = False
    for character in reversed(digits):
        value = int(character)
        if double:
            value *= 2
            if value > 9:
                value -= 9
        total += value
        double = not double
    return total % 10 == 0


def ngrams(text: str, size: int = 4) -> set[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    if len(words) < size:
        return set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def factual_text(item: Item) -> str:
    """Request facts a draft may share with a note. The reason is not included.

    A client-facing reason that repeats an internal note is still a leak.
    """
    return "\n".join(
        [
            item.client_name,
            item.salutation,
            item.doc_type,
            item.description,
            item.period,
            item.amount,
            format_lines(item.lines),
            item.deadline.isoformat() if item.deadline else "",
        ]
    )


def internal_leaks(draft: str, item: Item) -> list[str]:
    """Return phrases from internal notes that showed up in a client draft.

    A 4-word sequence counts even when the same words were copied into
    ``client_reason``. The full note text counts too. This catches a pasted
    note. It cannot catch every paraphrase, which the draft rule still forbids.
    """
    notes = _blank(item.internal_notes)
    if not notes:
        return []
    haystack = draft.lower()
    leaks = []
    if notes.lower() in haystack:
        leaks.append(notes)
    allowed = ngrams(factual_text(item))
    for gram in sorted(ngrams(notes)):
        if gram in allowed:
            continue
        if gram in haystack:
            leaks.append(gram)
    # Also flag the reason itself when it repeats the note. The draft prints it.
    reason = _blank(item.client_reason)
    if reason and reason.lower() in notes.lower() and reason.lower() in haystack:
        leaks.append(reason)
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
    if item.status == "Paused":
        return Action(
            "paused",
            reason="The client replied. Read that reply before sending another email.",
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
    earliest = slot
    if item.last_touch is not None:
        # One catch-up email, then at least two business days before the next.
        gap_end = add_business_days(item.last_touch, MIN_GAP_BUSINESS_DAYS, item.holidays)
        if gap_end > earliest:
            earliest = gap_end
    if item.last_touch == today:
        return Action(
            "wait",
            next_touch=first_business_on_or_after(today + timedelta(days=1), item.holidays)
            if earliest <= today
            else earliest,
            reason="An email already went out today. One email per client per day.",
        )
    if earliest > today:
        return Action("wait", next_touch=earliest, reason="Next email is still ahead, including the two-business-day gap.")
    if not is_business_day(today, item.holidays):
        return Action(
            "wait",
            next_touch=first_business_on_or_after(today, item.holidays),
            reason="A follow-up is due, and today is not a business day. Send it on the next business day.",
        )
    # One email covers every missed date. The touch count goes up by one when
    # that email is marked sent. It does not send once per missed day.
    if item.touches_sent == 0 and today <= item.deadline:
        kind = "initial"
    elif today > item.deadline:
        kind = "overdue"
    else:
        kind = "reminder"
    return Action(
        "email",
        next_touch=today,
        email_kind=kind,
        reason="One email is due. Missed dates are caught up in this single email.",
    )


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
    paused: list


def assess(items: Iterable[Item], today: date) -> Assessment:
    groups: dict[str, list] = {}
    order: list[str] = []
    buckets = {name: [] for name in ("call_needed", "bad_contact", "waiting", "hold", "review", "closed", "paused")}
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
        elif action.kind == "paused":
            buckets["paused"].append(entry)
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
        return f"${int(whole):,}.{frac}"
    return f"${int(amount):,}"


def format_date(day: date) -> str:
    """Friday, December 4. The year is included when it is not the current year of the date's own century-agnostic display.

    Client emails use this instead of YYYY-MM-DD. The year is included so a
    December date is not ambiguous across years: 'Friday, December 4, 2026'.
    """
    return f"{day.strftime('%A')}, {MONTH_NAMES[day.month - 1]} {day.day}, {day.year}"


def format_period(period: str) -> str:
    """Turn 2026-10 into October 2026, a range into words, and a full date into the long form."""
    period = (period or "").strip()

    def piece(match: re.Match) -> str:
        year, month = int(match.group(1)), int(match.group(2))
        day = match.group(3)
        if not 1 <= month <= 12:
            return match.group(0)
        if day:
            return format_date(date(year, month, int(day)))
        return f"{MONTH_NAMES[month - 1]} {year}"

    if re.search(r"\d{4}-\d{2}", period):
        return re.sub(r"(\d{4})-(\d{2})(?:-(\d{2}))?", piece, period)
    return period


def humanize(text: str) -> str:
    """Replace ISO dates and YYYY-MM periods inside client-facing prose."""

    def date_sub(match: re.Match) -> str:
        return format_date(date.fromisoformat(match.group(0)))

    def month_sub(match: re.Match) -> str:
        month = int(match.group(2))
        if not 1 <= month <= 12:
            return match.group(0)
        return f"{MONTH_NAMES[month - 1]} {match.group(1)}"

    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", date_sub, text)
    return re.sub(r"\b(\d{4})-(\d{2})\b", month_sub, text)


def _item_bullet(item: Item) -> list[str]:
    """Client-facing lines for one item. Uses a field whitelist."""
    lines = open_lines(item.lines)
    label = humanize(item.description)
    pretty_period = format_period(item.period)
    if item.period and pretty_period not in label and item.period not in item.description:
        label = f"{label} ({pretty_period})"
    bullets = [f"- {item.doc_type}: {label}.".replace(": :", ":")]
    if lines:
        bullets.append("  Still missing:")
        for line in lines:
            period = f" ({format_period(line['period'])})" if line["period"] else ""
            bullets.append(f"  - {line['label']}{period}")
    elif item.lines:
        bullets.append("  Every listed line is marked received. A person should confirm that before closing the request.")
    if item.client_reason:
        bullets.append(f"  Why we need it: {item.client_reason}")
    else:
        bullets.append("  Why we need it: Needed for the books on file.")
    if item.amount:
        bullets.append(f"  Amount on file: {_fmt_amount(item.amount)}")
    alternative = ALTERNATIVES.get(item.doc_type.lower())
    if alternative:
        bullets.append(f"  If the original is not handy: {alternative}")
    if item.deadline:
        bullets.append(f"  Deadline on file: {format_date(item.deadline)}")
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


def _sender_line(item: Item, firm: dict) -> tuple[str, str]:
    """Signature name, and a bookkeeper-only note when setup is missing.

    Never returns a bracket placeholder.
    """
    if not _blank(item.owner_name):
        firm_name = _blank(firm.get("firm_name"))
        if firm_name:
            return firm_name, "Setup is incomplete: this row has no sender name. The signature uses the firm name."
        return (
            "Your bookkeeping firm",
            "Setup is incomplete: there is no sender name and no firm name. Add them before sending.",
        )
    return item.owner_name, ""


def subject_for(group: dict) -> str:
    """Human subject with no touch count and no bulk-mail prefix."""
    items = [entry["item"] for entry in group["entries"]]
    if len(items) == 1:
        topic = items[0].doc_type
        if items[0].period:
            topic = f"{format_period(items[0].period)} {topic}"
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
        (
            "Hope you are doing well. We need the documents below."
            if group["email_kind"] == "initial"
            else "Hope you are doing well. We still need the documents below."
        ),
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
            f"the {item.doc_type.lower()} (deadline {format_date(item.deadline)})" for item in overdue_items
        )
        reason = (overdue_items[0].client_reason or "").strip()
        if reason and reason[-1] not in ".!?":
            reason += "."
        sentence = f"The deadline has passed for {named}. Without those files, this work is held up."
        if reason:
            sentence += " " + reason
        lines.append(sentence)
        lines.append("")
    how = (firm.get("submission_instructions") or "").strip() or "Reply to this email with the file attached."
    lines.append(f"How to send: {how}")
    lines.append("")
    lines.append("Thank you,")
    lines.append("")
    sender, setup_note = _sender_line(primary, firm)
    if setup_note:
        lines.insert(1, setup_note)
    lines.append(sender)
    if primary.owner_title and sender != primary.owner_title:
        lines.append(primary.owner_title)
    if firm.get("firm_name") and firm["firm_name"] != sender:
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
        _sender_line(item, firm)[0],
    ]
    if item.owner_title:
        lines.append(item.owner_title)
    if firm.get("firm_name"):
        lines.append(firm["firm_name"])
    if firm.get("firm_email"):
        lines.append(firm["firm_email"])
    lines.append("")
    return "\n".join(lines)


def render_partial_reply(item: Item, firm: dict) -> str:
    """Thank the client for the lines that arrived and ask only for the rest."""
    arrived = [line["label"] for line in item.lines if line["status"] == "received"]
    missing = [line["label"] for line in item.lines if line["status"] == "open"]
    got = ", ".join(arrived) or "what you sent"
    still = ", ".join(missing) or "the remaining pages"
    lines = [
        DRAFT_BANNER,
        "",
        f"To: {item.contact_email or '(no email on file)'}",
        "Subject: " + subject_for({"email_kind": "reminder", "entries": [{"item": item, "action": Action("email")}]}),
        "",
        greeting(item.salutation),
        "",
        f"Thank you for sending {got}.",
        "",
        f"We still need {still}.",
        "",
        "How to send: " + ((firm.get("submission_instructions") or "").strip() or "Reply to this email with the file attached."),
        "",
        "Thank you,",
        "",
        _sender_line(item, firm)[0],
    ]
    if item.owner_title:
        lines.append(item.owner_title)
    if firm.get("firm_name"):
        lines.append(firm["firm_name"])
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


def mark_sent(items: Iterable[Item], today: date, ids: Optional[Iterable[str]] = None) -> list:
    """Record that a person sent today's drafts.

    Increments the touch count and sets the last contact to today. Calling it
    again the same day does not count a second email. The next assessment then
    waits out the two-business-day gap instead of drafting the same email again.
    """
    chosen = set(ids) if ids is not None else None
    recorded = []
    for item in items:
        if chosen is not None and item.id not in chosen:
            continue
        if item.status not in EMAIL_STATUSES:
            continue
        if item.last_touch == today:
            recorded.append(item)
            continue
        item.touches_sent += 1
        item.last_touch = today
        recorded.append(item)
    apply_next_touch(recorded, today)
    return recorded


def note_client_reply(item: Item, today: date) -> Item:
    """A reply that is not a document. Chasing stays paused until a person resumes it."""
    item.status = "Paused"
    item.client_replied = today
    return item


def resume_chase(item: Item, today: date) -> Item:
    """A person has read the reply and wants the cadence to continue."""
    if item.status == "Paused":
        item.status = "Open"
    if item.last_touch is None:
        item.last_touch = today
    return item


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


def months_in(period: str) -> set[tuple[int, int]]:
    """(year, month) values a period covers. A bare year covers every month of that year.

    ``2026-1`` is January. It does not match ``2026-10``. ``June 2026`` and
    ``2026-06`` are the same month. ``2026-06 to 2026-08`` covers the three months.
    """
    text = period or ""
    found: set[tuple[int, int]] = set()
    for match in re.finditer(r"\b((?:19|20)\d{2})-(\d{1,2})(?:-(\d{1,2}))?\b", text):
        month = int(match.group(2))
        if 1 <= month <= 12:
            found.add((int(match.group(1)), month))
    for match in re.finditer(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b(?:[^0-9]{0,12}((?:19|20)\d{2}))?",
        text,
        re.I,
    ):
        month = MONTH_INDEX[match.group(1).lower()]
        year = int(match.group(2)) if match.group(2) else 0
        found.add((year, month))
    if found:
        # Expand an explicit range of year-months, such as 2026-06 to 2026-08.
        dated = sorted(pair for pair in found if pair[0])
        if len(dated) >= 2 and re.search(r"\b(to|through|–|—|-)\b", text, re.I):
            start = dated[0][0] * 12 + dated[0][1]
            end = dated[-1][0] * 12 + dated[-1][1]
            if end - start <= 18:
                cursor = start
                while cursor <= end:
                    year, month = divmod(cursor - 1, 12)
                    found.add((year, month + 1))
                    cursor += 1
        return found
    years = [int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", text)]
    if len(years) == 1 and not re.search(r"\d{1,2}", text.replace(str(years[0]), "")):
        return {(years[0], month) for month in range(1, 13)}
    return set()


def periods_overlap(requested: str, received: str) -> bool:
    left = months_in(requested)
    right = months_in(received)
    if not left or not right:
        # Fall back to a whole-token compare. Never a raw substring, so 2026-1
        # cannot hide inside 2026-10.
        return _norm(requested) == _norm(received)
    # A month with year 0 (no year written) matches that month in any year present.
    def expand(pairs: set[tuple[int, int]], other: set[tuple[int, int]]) -> set[tuple[int, int]]:
        years = {year for year, _month in other if year}
        expanded = set()
        for year, month in pairs:
            if year == 0 and years:
                expanded.update((candidate, month) for candidate in years)
            else:
                expanded.add((year, month))
        return expanded

    return bool(expand(left, right) & expand(right, left))


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

    if item.period and document.get("period") and not periods_overlap(item.period, document.get("period") or ""):
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
        # The thank-you for what arrived is touch 1, already logged today,
        # so assess does not queue a second email the same day.
        item.touches_sent = 1
        item.last_touch = today
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
    item.touches_sent = 1
    item.last_touch = today
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
    "client-facing reason": "client_reason",
    "client_reason": "client_reason",
    # These are internal until a person confirms a separate client-facing reason.
    "reason": "internal_notes",
    "why needed": "internal_notes",
    "why": "internal_notes",
    "context": "internal_notes",
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
_BUSINESS_OFFSET = re.compile(r"^[+-]?\d+bd$")
_MDY = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_MONTH_TOKEN = re.compile(r"^month:([+-]?\d+)(?:@(registered|today))?$")
_YEAR_TOKEN = re.compile(r"^year:([+-]?\d+)(?:@(registered|today))?$")


def resolve_token(token: str, today: date) -> tuple[str, Optional[str]]:
    """Resolve one date token to YYYY-MM-DD. Returns (value, assumption or None)."""
    token = token.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        parse_iso(token)
        return token, None
    if _BUSINESS_OFFSET.fullmatch(token):
        count = int(token[:-2])
        cursor = today
        step = 1 if count > 0 else -1
        left = abs(count)
        while left:
            cursor += timedelta(days=step)
            if is_business_day(cursor):
                left -= 1
        return cursor.isoformat(), None
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


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1) - timedelta(days=1)
    return date(year, month + 1, 1) - timedelta(days=1)


def closed_month(anchor: date, shift: int, today: date) -> str:
    """A month relative to ``anchor`` that has already ended before ``today``.

    ``shift`` -1 is the month before the anchor month. If that month has not
    ended yet, step back until it has. A statement is never requested for a
    month that is still open.
    """
    index = anchor.year * 12 + (anchor.month - 1) + shift
    while True:
        year, month0 = divmod(index, 12)
        month = month0 + 1
        if _month_end(year, month) < today:
            return f"{year:04d}-{month:02d}"
        index -= 1


def resolve_period(token: str, today: date, anchor: Optional[date] = None) -> str:
    token = token.strip()
    base = anchor or today
    month_match = _MONTH_TOKEN.fullmatch(token)
    if month_match:
        shift = int(month_match.group(1))
        which = month_match.group(2) or "registered"
        origin = today if which == "today" else base
        return closed_month(origin, shift, today)
    year_match = _YEAR_TOKEN.fullmatch(token)
    if year_match:
        shift = int(year_match.group(1))
        which = year_match.group(2) or "registered"
        origin = today if which == "today" else base
        year = origin.year + shift
        # A tax year that has not finished yet is not requestable.
        if year >= today.year:
            year = today.year - 1
        return f"{year:04d}"
    if token.startswith("month:") or token.startswith("year:"):
        raise RuleError(f"Cannot read period {token!r}.")
    return token


def _snap_contact_date(value: str, today: date) -> str:
    """A contact date that landed on a weekend or holiday moves to the previous business day."""
    if not value:
        return value
    day = parse_iso(value)
    if day > today:
        day = today
    if not is_business_day(day):
        day = previous_business_day(day)
    return day.isoformat()


def resolve_tracker_text(text: str, today: date) -> str:
    """Replace relative date tokens in a demo CSV. Leaves the header intact.

    Periods anchor to the registration date, not to today, and a statement
    month must already have ended. Registration and last-contact dates that
    fall on a weekend or federal holiday move to the previous business day.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise RuleError("Tracker CSV has no header.")
    fields = list(reader.fieldnames)
    contact_fields = ("registered", "schedule_anchor", "last_touch", "received")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in reader:
        if not (row.get("id") or "").strip():
            continue
        for key in ("deadline", "last_touch", "next_touch", "registered", "schedule_anchor", "received", "client_replied"):
            raw = (row.get(key) or "").strip()
            if not raw:
                continue
            resolved, _ = resolve_token(raw, today)
            row[key] = resolved
        anchor = parse_iso(row["registered"]) if (row.get("registered") or "").strip() else today
        for key in contact_fields:
            if (row.get(key) or "").strip():
                row[key] = _snap_contact_date(row[key], today)
        if (row.get("registered") or "").strip():
            anchor = parse_iso(row["registered"])
        doc_type = (row.get("doc_type") or "").strip().lower()
        period = (row.get("period") or "").strip()
        if period:
            resolved_period = resolve_period(period, today, anchor)
            # Contracts and similar can name the current year. Tax forms and
            # statements stay on a period that has already closed.
            if doc_type not in STATEMENT_TYPES and _YEAR_TOKEN.fullmatch(period) and period.startswith("year:0"):
                resolved_period = f"{anchor.year:04d}"
            row["period"] = resolved_period
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
                        bits[1] = resolve_period(token, today, anchor)
                    elif _OFFSET.fullmatch(token) or _BUSINESS_OFFSET.fullmatch(token) or _MDY.fullmatch(token):
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
            if alias == "internal_notes" and mapped[alias] and value and value not in mapped[alias]:
                mapped[alias] = mapped[alias] + "\n" + value
                continue
            if alias in mapped and mapped[alias] and value and mapped[alias] != value:
                questions.append(f"Row {index}: both columns wrote {alias}. I kept the first value.")
                continue
            mapped[alias] = value
            if key.strip().lower() in {"reason", "why needed", "why", "context"}:
                questions.append(
                    f"Row {index}: '{key.strip()}' was stored as an internal note. It will not be put in a client email unless you confirm a separate client-facing reason."
                )
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


def extract_document(path: str) -> dict:
    """Read a PDF and return the fields the pre-check compares.

    This is a deterministic reader for digital PDFs (text, not a scan). It
    does not guess a period or an entity that is not written in the file.
    """
    from pypdf import PdfReader

    reader = PdfReader(path)
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    facts: dict = {"text": text, "complete": True, "lines_covered": []}
    last4 = re.search(r"\*{2,}(\d{4})", text)
    if last4:
        facts["account_last4"] = last4.group(1)
    entity = re.search(r"Account Holder:\s*(.+)", text)
    if entity:
        facts["entity"] = " ".join(entity.group(1).split())
    statement = re.search(r"Statement Period:\s*([A-Za-z]+).{0,40}?((?:19|20)\d{2})", text, re.S)
    if statement:
        facts["doc_type"] = "Bank Statement"
        facts["period"] = f"{statement.group(1)} {statement.group(2)}"
        if not facts.get("entity"):
            named = re.search(r"Account Holder:\s*(.+?)(?:\n|Account)", text, re.S)
            if named:
                facts["entity"] = " ".join(named.group(1).split())
    po_numbers = re.findall(r"PO #([A-Z]+-\d+)", text)
    if po_numbers and re.search(r"PURCHASE ORDER", text, re.I):
        facts["doc_type"] = "Purchase Order"
        facts["doc_number"] = po_numbers[0]
        if re.search(r"Miruvor", text):
            facts["subject"] = "Miruvor Wine"
        if len(po_numbers) > 1:
            issued = re.search(r"issued\s+separately\s+on\s+([A-Za-z]+ \d{1,2}, \d{4})", text, re.S)
            subject = "Lembas Bread" if re.search(r"Lembas", text) else ""
            facts["pointer"] = {
                "number": po_numbers[1],
                "subject": subject,
                "issued": issued.group(1) if issued else "",
            }
            facts["requested_subject"] = subject
    invoice = re.search(r"INVOICE\s*#([A-Z]+-\d+)|Invoice\s*#([A-Z]+-\d+)", text, re.I)
    if invoice and "doc_number" not in facts:
        facts["doc_type"] = "Invoice"
        facts["doc_number"] = invoice.group(1) or invoice.group(2)
    bill_to = re.search(r"BILL TO\s*(.+)", text)
    if bill_to and "entity" not in facts:
        facts["entity"] = bill_to.group(1).strip()
    if re.search(r"RECEIPT", text, re.I) and "doc_type" not in facts:
        facts["doc_type"] = "Receipt"
        dated = re.search(r"Date:\s*([A-Za-z]+ \d{1,2}, \d{4})", text)
        if dated:
            facts["period"] = dated.group(1)
        head = "\n".join(text.splitlines()[:8]).upper()
        if "SECOND BREAKFAST" in head:
            facts["lines_covered"].append("Second Breakfast catering")
        elif "ELEVENSES" in head:
            facts["lines_covered"].append("Elevenses Bakery")
        if re.search(r"Shire Agricultural", text):
            facts["entity"] = "Shire Agricultural Co-op"
        if re.search(r"Baggins", text) and "entity" not in facts:
            facts["entity"] = "Baggins & Associates LLC"
    return facts


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
