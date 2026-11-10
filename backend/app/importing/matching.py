# Compares each line the parser read with what's already on the calendar, and
# marks it for the preview:
#   new      will be added;
#   already  the same date, course, type and title (ignoring case and accents)
#            is on the calendar, or was on an earlier line of this import: skipped;
#   changed  the same event moved (a different date, time or place): shown as
#            old -> new, and saving updates it;
#   error    the line couldn't be read (from the parser), with how to fix it.
# Reads the database, never writes to it: the preview saves nothing.

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import fold
from ..models import Course, Event
from .parser import LineProblem, ParsedEvent

# How far apart a moved event can be: the matching only looks this far around the import's dates.
_SEARCH_DAYS = 366


@dataclass
class PreviewRow:
    line: int
    text: str
    status: str  # new, already, changed or error
    event: ParsedEvent | None = None
    problem: LineProblem | None = None
    event_id: int | None = None  # the calendar's event, for "already" and "changed"
    in_import: bool = False  # "already": on an earlier line of this same import
    new_course: bool = False  # the course code isn't on the calendar yet: saving adds it
    changes: list[dict] = field(default_factory=list)  # [{field, before, after}] for "changed"

    def to_json(self) -> dict:
        """The row as the page (and the preview's hash) sees it."""
        out = {
            "line": self.line,
            "text": self.text,
            "status": self.status,
            "event_id": self.event_id,
            "in_import": self.in_import,
            "new_course": self.new_course,
            "changes": self.changes,
        }
        if self.problem:
            out |= {"message": self.problem.message, "template": self.problem.template, "params": self.problem.params}
        if self.event:
            e = self.event
            out |= {
                "date": e.date.isoformat(),
                "start_time": _hh_mm(e.start_time),
                "end_time": _hh_mm(e.end_time),
                "type": e.type,
                "course": e.course,
                "title": e.title,
                "details": e.details,
                "location": e.location,
                "source_link": e.source_link,
                "series": e.series,
            }
        return out


def _hh_mm(value: dt.time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def term_of(day: dt.date) -> tuple[int, int]:
    """The school term: winter (Jan-Apr), summer (May-Aug) or fall (Sep-Dec)."""
    return day.year, (day.month - 1) // 4


def _key(course: str | None, event_type: str, title: str) -> tuple:
    return course, event_type, fold(" ".join(title.split()))


def _differences(old: Event, new: ParsedEvent) -> list[dict]:
    """What saving the line would change on the event: date, times, place, and the
    title when it's more than a matter of case or accents. A line without a place
    keeps the event's place, so a room typed by hand isn't wiped."""
    pairs = [
        ("date", old.date.isoformat(), new.date.isoformat()),
        ("start_time", _hh_mm(old.start_time), _hh_mm(new.start_time)),
        ("end_time", _hh_mm(old.end_time), _hh_mm(new.end_time)),
    ]
    if new.location is not None:
        pairs.append(("location", old.location, new.location))
    if fold(old.title) != fold(new.title):
        pairs.append(("title", old.title, new.title))
    return [{"field": name, "before": before, "after": after} for name, before, after in pairs if before != after]


def classify(db: Session, items: list[ParsedEvent | LineProblem]) -> list[PreviewRow]:
    """One preview row per item, in the same order."""
    rows: list[PreviewRow] = []
    for item in items:
        if isinstance(item, LineProblem):
            rows.append(PreviewRow(item.line, item.text, "error", problem=item))
        else:
            rows.append(PreviewRow(item.line, item.text, "new", event=item))
    pending = [r for r in rows if r.event]
    if not pending:
        return rows

    known_courses = set(db.scalars(select(Course.code)))
    for row in pending:
        row.new_course = row.event.course is not None and row.event.course not in known_courses

    first = min(r.event.date for r in pending) - dt.timedelta(days=_SEARCH_DAYS)
    last = max(r.event.date for r in pending) + dt.timedelta(days=_SEARCH_DAYS)
    existing = list(db.scalars(select(Event).where(Event.date >= first, Event.date <= last)).unique())
    claimed: set[int] = set()  # events already matched by a line: one line per event

    # 1. The same event twice in this import: the second is "already there".
    seen = set()
    for row in pending:
        e = row.event
        key = (e.date, *_key(e.course, e.type, e.title))
        if key in seen:
            row.status, row.in_import = "already", True
        seen.add(key)
    pending = [r for r in pending if r.status == "new"]

    # 2. Same date, course, type and title: already there, or changed if its time
    #    or place differ. Done for every line before step 3, so a line that matches
    #    an event exactly always gets it.
    rest = []
    for row in pending:
        e = row.event
        key = _key(e.course, e.type, e.title)
        matches = [
            old
            for old in existing
            if old.id not in claimed and old.date == e.date and _key(old.course_code, old.type, old.title) == key
        ]
        if not matches:
            rest.append(row)
            continue
        # Several (rare): the one with nothing to change, if there is one.
        old = min(matches, key=lambda o: (len(_differences(o, e)), o.id))
        _matched(row, old, claimed)

    # 3. The same event on another date: the same source link (and course and type),
    #    or the same course, type and title in the same term. Only when exactly one
    #    event fits, and never for weekly series: there, "Cours" every week has the
    #    same title, and moving the wrong week would be a silent mistake.
    for row in rest:
        e = row.event
        if e.series:
            continue
        free = [o for o in existing if o.id not in claimed and o.series_id is None]
        candidates = []
        if e.source_link:
            candidates = [
                o for o in free if o.source_link == e.source_link and o.course_code == e.course and o.type == e.type
            ]
        if len(candidates) != 1:
            key = _key(e.course, e.type, e.title)
            candidates = [
                o for o in free if _key(o.course_code, o.type, o.title) == key and term_of(o.date) == term_of(e.date)
            ]
        if len(candidates) == 1:
            _matched(row, candidates[0], claimed)
    return rows


def _matched(row: PreviewRow, old: Event, claimed: set[int]) -> None:
    claimed.add(old.id)
    row.event_id = old.id
    row.changes = _differences(old, row.event)
    row.status = "changed" if row.changes else "already"


def counts(rows: list[PreviewRow]) -> dict[str, int]:
    out = {"new": 0, "already": 0, "changed": 0, "error": 0}
    for row in rows:
        out[row.status] += 1
    return out
