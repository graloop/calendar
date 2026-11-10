# Reads the import box: one event per line,
#   date | time | type | course | title | details | source
# Each line becomes one event (or one per week for "weekly until"), or an error
# saying what to fix on that line. Nothing here touches the database, and
# "today" is passed in, so the tests can say which day it is.
#
# The lines are usually written by the Claude extension, so the parser is
# forgiving about form (markdown bullets and tables, extra spaces, 14h30,
# "75 min", French month, day and type words) and strict about meaning: a
# weekday that doesn't match the date, an end before the start or a date more
# than a year away is an error, never a guess. Started from the training app's
# Plan tab parser (planning/draft_parser.py).
#
# Error messages are LineError(template, **params): the page shows them next
# to the line, translated by their template (js/core/fr.js), so each one says
# how to fix the line.

import datetime as dt
import re
from dataclasses import dataclass, field

from ..database import fold
from ..schemas import tidy_code

FORMAT = "date | time | type | course | title | details | source"
MAX_DAYS_AWAY = 365

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Folded (lowercase, no accents) words for each weekday and month, English and French.
# "mar" is both Tuesday (mardi) and March: see _read_words().
_WEEKDAYS = {
    word: i
    for i, words in enumerate(
        [
            ("mon", "monday", "lun", "lundi"),
            ("tue", "tues", "tuesday", "mar", "mardi"),
            ("wed", "wednesday", "mer", "mercredi"),
            ("thu", "thur", "thurs", "thursday", "jeu", "jeudi"),
            ("fri", "friday", "ven", "vendredi"),
            ("sat", "saturday", "sam", "samedi"),
            ("sun", "sunday", "dim", "dimanche"),
        ]
    )
    for word in words
}
_MONTHS = {
    word: i + 1
    for i, words in enumerate(
        [
            ("jan", "janv", "january", "janvier"),
            ("feb", "fev", "fevr", "february", "fevrier"),
            ("mar", "march", "mars"),
            ("apr", "avr", "april", "avril"),
            ("may", "mai"),
            ("jun", "june", "juin"),
            ("jul", "july", "juil", "juillet"),
            ("aug", "august", "aout"),
            ("sep", "sept", "september", "septembre"),
            ("oct", "october", "octobre"),
            ("nov", "november", "novembre"),
            ("dec", "december", "decembre"),
        ]
    )
    for word in words
}
# Little words that can sit in a written date: "le mardi 24 novembre", "the 24th of November".
_DATE_FILLERS = {"le", "the", "of", "de", "du", "on"}

# Event types (the English keys stored on events) and the folded words that mean them.
_TYPE_WORDS = {
    "class": ("class", "cours", "course", "lecture", "lecon", "theorie", "seminar", "seminaire", "tutorial", "td"),
    "lab": ("lab", "labo", "laboratoire", "laboratory", "tp", "practical"),
    "exam": ("exam", "examen", "intra", "final", "midterm", "quiz", "test", "examen final", "examen intra"),
    "deadline": (
        "deadline",
        "due",
        "remise",
        "devoir",
        "assignment",
        "homework",
        "submission",
        "date limite",
        "echeance",
        "a remettre",
    ),
    "meeting": ("meeting", "reunion", "rencontre", "rdv", "rendez-vous", "appointment"),
    "work": ("work", "travail", "job", "shift", "emploi", "quart"),
    "personal": ("personal", "personnel", "personnelle", "perso"),
    "other": ("other", "autre", "event", "evenement"),
}
_TYPES = {word: key for key, words in _TYPE_WORDS.items() for word in words}

_ALL_DAY = {"", "-", "all day", "allday", "all-day", "toute la journee", "journee", "jour entier"}
_NO_COURSE = {"", "-", "none", "aucun", "aucune", "n/a", "na"}
# A details part that gives the place: "room: D7-2018", "salle D7-2018".
_PLACE = re.compile(r"^(?:room|location|place|salle|local|lieu)\s*:?\s+(.+)$", re.I)
_ISO_DAY = r"\d{4}-\d{1,2}-\d{1,2}"
_WEEKLY = re.compile(
    r"\b(?:weekly|every\s+week|chaque\s+semaine|hebdo(?:madaire)?)\s+(?:until|till|through|jusqu'?(?:au|a|à))\b\s*(\S*)",
    re.I,
)
_EXCEPT = re.compile(
    rf"\b(?:except|sauf|skip|but\s+not)\s+({_ISO_DAY}(?:\s*(?:,|and|et|&)\s*{_ISO_DAY})*)",
    re.I,
)


class LineError(Exception):
    """What's wrong with one line, and how to fix it. The template is kept apart
    from the values so the page can show it in French."""

    def __init__(self, template: str, **params):
        self.template = template
        self.params = {name: str(value) for name, value in params.items()}
        super().__init__(template.format(**self.params))


@dataclass
class ParsedEvent:
    line: int
    text: str  # the line as written, to show next to it in the preview
    date: dt.date
    start_time: dt.time | None
    end_time: dt.time | None
    type: str
    course: str | None
    title: str
    details: str | None = None
    location: str | None = None
    source_link: str | None = None
    series: bool = False  # one of the events of a "weekly until" line


@dataclass
class LineProblem:
    line: int
    text: str
    template: str
    params: dict[str, str]

    @property
    def message(self) -> str:
        return self.template.format(**self.params)


@dataclass
class ParsedText:
    items: list[ParsedEvent | LineProblem] = field(default_factory=list)  # in line order
    line_count: int = 0  # lines that held something to read (not blank, comments or table decoration)


# --- One field at a time ---


def _unreadable_date(value: str) -> LineError:
    return LineError("'{value}' isn't a date I can read. Write it like Tue Nov 24 or 2026-11-24.", value=value)


def _real_date(year: int, month: int, day: int, value: str) -> dt.date:
    try:
        return dt.date(year, month, day)
    except ValueError:
        raise LineError("'{value}' isn't a real date. Check the day and the month.", value=value) from None


def parse_date(text: str, today: dt.date) -> dt.date:
    """2026-11-24, "Tue Nov 24", "mardi 24 novembre", "24 nov." or "Nov 24th, 2026".

    Without a year, the date takes the year that puts it nearest to today (so in
    November, "Jan 12" is next January and "Sep 3" is this September). A weekday
    that doesn't match the date is an error: a typo must never move an event."""
    value = " ".join(text.split())
    if not value:
        raise LineError("The date is empty. Write it like Tue Nov 24 or 2026-11-24.")
    folded = fold(value)
    day = None
    if iso := re.search(rf"\b({_ISO_DAY})\b", folded):
        year, month, number = (int(part) for part in iso[1].split("-"))
        day = _real_date(year, month, number, value)
        folded = folded[: iso.start()] + " " + folded[iso.end() :]

    weekday = month = number = year = None
    words = []
    for token in re.split(r"[\s,.]+", folded):
        token = re.sub(r"^(\d{1,2})(?:st|nd|rd|th|er|e)$", r"\1", token)
        if not token or token in _DATE_FILLERS:
            continue
        if token.isdigit() and day is None and len(token) == 4 and year is None:
            year = int(token)
        elif token.isdigit() and day is None and number is None and 1 <= int(token) <= 31:
            number = int(token)
        elif token.isalpha():
            words.append(token)
        else:
            raise _unreadable_date(value)
    # "mar" is Tuesday in French ("mar. 24 nov.") and March in English ("Mar 24"):
    # it's the weekday when another word already gives the month.
    other_month = any(w in _MONTHS and w != "mar" for w in words)
    for word in words:
        if word in _MONTHS and not (word == "mar" and other_month) and month is None and day is None:
            month = _MONTHS[word]
        elif word in _WEEKDAYS and weekday is None:
            weekday = _WEEKDAYS[word]
        else:
            raise _unreadable_date(value)

    if day is None:
        if number is None:
            raise LineError("'{value}' has no day of the month. Write it like Tue Nov 24 or 2026-11-24.", value=value)
        if month is None:
            raise LineError("'{value}' has no month. Write it like Tue Nov 24 or 2026-11-24.", value=value)
        if year is not None:
            day = _real_date(year, month, number, value)
        else:
            options = []
            for candidate_year in (today.year - 1, today.year, today.year + 1):
                try:
                    options.append(dt.date(candidate_year, month, number))
                except ValueError:  # Feb 29 outside a leap year
                    pass
            if not options:
                raise LineError("'{value}' isn't a real date. Check the day and the month.", value=value)
            day = min(options, key=lambda d: abs((d - today).days))

    if weekday is not None and day.weekday() != weekday:
        raise LineError(
            "{date} is a {weekday}, not a {written}. Check the date or the weekday.",
            date=day.isoformat(),
            weekday=WEEKDAY_NAMES[day.weekday()],
            written=WEEKDAY_NAMES[weekday],
        )
    check_not_too_far(day, today)
    return day


def check_not_too_far(day: dt.date, today: dt.date) -> None:
    if abs((day - today).days) > MAX_DAYS_AWAY:
        raise LineError("{date} is more than a year from today. Check the year.", date=day.isoformat())


def _clock(text: str) -> dt.time | None:
    """13:30, 13h30, 14h, 9am, 1:30 pm. A bare number isn't a time: "14" could be anything."""
    value = text.strip().replace(".", "")
    m = re.fullmatch(r"(\d{1,2})\s*(?:[:h]\s*(\d{2})?)?\s*([ap])m", value)
    if m:
        hour, minute = int(m[1]), int(m[2] or 0)
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if m[3] == "p" else 0)
    elif m := re.fullmatch(r"(\d{1,2})\s*(?::\s*(\d{2})|h\s*(\d{2})?)", value):
        hour, minute = int(m[1]), int(m[2] or m[3] or 0)
    else:
        return None
    if hour > 23 or minute > 59:
        return None
    return dt.time(hour, minute)


def _minutes(text: str) -> int | None:
    """A length: "75 min", "1h15", "1 h 15", "1.5 h", "2 hours", "90 minutes"."""
    value = text.strip().replace(",", ".")
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*h(?:ours?|rs?|eures?)?\s*(?:(\d{1,2})\s*(?:m|min|mins|minutes)?)?", value):
        return round(float(m[1]) * 60) + int(m[2] or 0)
    if m := re.fullmatch(r"(\d+)\s*(?:m|min|mins|minutes)", value):
        return int(m[1])
    return None


_CLOCK_AT_START = re.compile(r"^(\d{1,2}(?:\s*[:h]\s*\d{2}|\s*h)?(?:\s*[ap]\.?m\.?)?)(?=\s|[,+(]|$)")


def parse_time(text: str, event_type: str) -> tuple[dt.time | None, dt.time | None]:
    """(start, end) from "13:30-15:20", "13h30 à 15h20", "13:30 75 min", "23:59"
    or "all day" ((None, None)). A deadline takes one time: when it's due."""
    value = " ".join(fold(text).replace("–", "-").replace("—", "-").split())
    if value in _ALL_DAY:
        return None, None
    unreadable = LineError(
        "'{value}' isn't a time I can read. Write it like 13:30-15:20, 13:30 75 min, 23:59 or all day.",
        value=text.strip(),
    )
    value = re.sub(r"^(?:de|from|at|a|@)\s+", "", value)
    parts = re.split(r"\s*-\s*|\s+(?:to|a|au|until|jusqu'a)\s+", value)
    if len(parts) == 2:
        start, end = _clock(parts[0]), _clock(parts[1])
        if start is None or end is None:
            raise unreadable
    elif len(parts) == 1 and (m := _CLOCK_AT_START.match(value)):
        start, end = _clock(m[1]), None
        if start is None:
            raise unreadable
        rest = value[m.end() :].strip(" ,+()")
        rest = re.sub(r"^(?:for|pendant|duree|duration)\s+", "", rest)
        if rest:
            length = _minutes(rest)
            if length is None:
                raise unreadable
            if length <= 0:
                raise LineError("The length has to be more than 0 minutes. Write it like 13:30 75 min.")
            total = start.hour * 60 + start.minute + length
            if total >= 24 * 60:
                raise LineError(
                    "'{value}' goes past midnight. End it at 23:59 or split it in two lines.", value=text.strip()
                )
            end = dt.time(total // 60, total % 60)
    else:
        raise unreadable
    if event_type == "deadline" and end is not None:
        raise LineError("A deadline has only a due time. Write just that, like 23:59.")
    if end is not None and end <= start:
        raise LineError(
            "The end ({end}) isn't after the start ({start}). Write it like 13:30-15:20.",
            start=start.strftime("%H:%M"),
            end=end.strftime("%H:%M"),
        )
    return start, end


def parse_type(text: str) -> str:
    value = " ".join(fold(text).strip(" .:").split())
    if value in _TYPES:
        return _TYPES[value]
    if value.endswith("s") and value[:-1] in _TYPES:  # "labs", "examens", "remises"
        return _TYPES[value[:-1]]
    raise LineError(
        "'{value}' isn't a type. Use one of: class, lab, exam, deadline, meeting, work, personal, other.",
        value=text.strip(),
    )


def parse_course(text: str) -> str | None:
    """A course code (ABC123, "abc 123"), or None for "-". Only the code: a
    course name after it would make a different course."""
    value = text.strip()
    if fold(value) in _NO_COURSE:
        return None
    words = value.split()
    if len(words) == 2 and words[0].isalpha() and words[1][:1].isdigit():
        value = "".join(words)  # "ABC 123"
    elif len(words) != 1:
        value = None
    try:
        code = tidy_code(value) if value else None
    except ValueError:
        code = None
    if code is None or len(code) > 20:
        raise LineError(
            "'{value}' isn't a course code. Write a code like ABC123, or - for no course.", value=text.strip()
        )
    return code


def parse_source(text: str) -> str | None:
    """The Moodle address or "Email: subject, date". A markdown link keeps its address."""
    value = text.strip()
    if m := re.fullmatch(r"\[[^\]]*\]\(([^)\s]+)\)", value):
        value = m[1]
    value = value.strip("<>").strip()
    if len(value) > 500:
        raise LineError("The source is longer than 500 characters. Use the page's address, or Email: subject, date.")
    return value or None


def guess_source_kind(source_link: str | None) -> str | None:
    """What kind of import a source column points to: moodle, email or other."""
    if not source_link:
        return None
    folded = fold(source_link)
    if re.match(r"(?:e-?mail|courriel|mail)\s*:", folded):
        return "email"
    if "moodle" in folded:
        return "moodle"
    return "other"


@dataclass
class _Repeat:
    until: dt.date | None = None
    excepted: list[dt.date] = field(default_factory=list)


def parse_details(text: str, today: dt.date) -> tuple[str | None, str | None, _Repeat]:
    """(details, location, repeat): "weekly until", "except" and "room:" are taken
    out of the free text, and what's left is the details."""
    value = " ".join(text.split())
    repeat = _Repeat()
    if m := _WEEKLY.search(value):
        written = m[1].strip(".,;)")
        if not re.fullmatch(_ISO_DAY, written):
            raise LineError("Write the end of the series like weekly until 2026-12-12 (year-month-day).")
        year, month, number = (int(part) for part in written.split("-"))
        repeat.until = _real_date(year, month, number, written)
        check_not_too_far(repeat.until, today)
        value = value[: m.start()] + " " + value[m.end() :]
    for m in _EXCEPT.finditer(value):
        for written in re.findall(_ISO_DAY, m[1]):
            year, month, number = (int(part) for part in written.split("-"))
            repeat.excepted.append(_real_date(year, month, number, written))
    value = _EXCEPT.sub("", value)
    location = None
    kept = []
    for part in re.split(r"\s*;\s*", value):
        if (m := _PLACE.match(part.strip())) and location is None:
            location = m[1].strip(" .,")[:200] or None
        elif part.strip(" ,.;"):
            kept.append(part.strip(" ,;"))
    details = "; ".join(kept) or None
    if details and len(details) > 5000:
        raise LineError("The details are longer than 5000 characters. Keep only what matters.")
    return details, location, repeat


def _tidy_cell(cell: str) -> str:
    """Markdown around a cell: **bold**, `code`, _italic_."""
    value = cell.strip()
    for mark in ("**", "__", "`", "*", "_"):
        if len(value) > 2 * len(mark) and value.startswith(mark) and value.endswith(mark):
            value = value[len(mark) : -len(mark)].strip()
    return value


def _series_dates(first: dt.date, repeat: _Repeat) -> list[dt.date]:
    if repeat.until is None:
        if repeat.excepted:
            raise LineError(
                "except {date} only works with weekly until on the same line.", date=repeat.excepted[0].isoformat()
            )
        return [first]
    if repeat.until < first:
        raise LineError(
            "weekly until {until} is before the first date ({date}). Check both dates.",
            until=repeat.until.isoformat(),
            date=first.isoformat(),
        )
    dates = []
    day = first
    while day <= repeat.until:
        dates.append(day)
        day += dt.timedelta(days=7)
    for skipped in repeat.excepted:
        if skipped not in dates:
            raise LineError(
                "except {date} isn't one of this series' days (every {weekday} from {first} to {until}). Check the date.",
                date=skipped.isoformat(),
                weekday=WEEKDAY_NAMES[first.weekday()],
                first=first.isoformat(),
                until=repeat.until.isoformat(),
            )
    return [d for d in dates if d not in repeat.excepted]


# --- A whole line, then the whole box ---


def _is_skipped(line: str) -> bool:
    """Blank lines, # comments, code fences and markdown table rulers (|---|:--|)."""
    return not line or line.startswith(("#", "```", "//")) or set(line) <= set("-|: =+")


def parse_line(line: str, number: int, raw: str, today: dt.date) -> list[ParsedEvent]:
    cells = [_tidy_cell(c) for c in line.split("|", 6)]
    if len(cells) == 1:
        raise LineError(
            "There's no | between the fields. Write: date | time | type | course | title | details | source."
        )
    if len(cells) < 5:
        raise LineError(
            "Only {count} fields. Write: date | time | type | course | title, then details and source if you have them.",
            count=len(cells),
        )
    event_type = parse_type(cells[2])
    first = parse_date(cells[0], today)
    start, end = parse_time(cells[1], event_type)
    course = parse_course(cells[3])
    title = " ".join(cells[4].split())
    if not title:
        raise LineError("The title is empty. Write a short title, like Lab 3.")
    if len(title) > 200:
        raise LineError("The title is longer than 200 characters. Make it shorter and put the rest in the details.")
    details, location, repeat = parse_details(cells[5] if len(cells) > 5 else "", today)
    source_link = parse_source(cells[6]) if len(cells) > 6 else None
    dates = _series_dates(first, repeat)
    return [
        ParsedEvent(
            line=number,
            text=raw.strip(),
            date=day,
            start_time=start,
            end_time=end,
            type=event_type,
            course=course,
            title=title,
            details=details,
            location=location,
            source_link=source_link,
            series=repeat.until is not None,
        )
        for day in dates
    ]


def parse_text(text: str, today: dt.date) -> ParsedText:
    """The whole import box. A line with a problem becomes a LineProblem in its
    place; the other lines are read anyway."""
    result = ParsedText()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        line = re.sub(r"^(?:[-*•+]|\d{1,3}[.)])\s+", "", line)  # bullets and numbered lists
        line = line.removeprefix("- [ ] ").removeprefix("[ ] ")
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        line = line.strip()
        if _is_skipped(line):
            continue
        first_cell = fold(line.split("|", 1)[0]).strip(" *")
        if "|" in line and first_cell in ("date", "jour", "day"):  # a table's header row
            continue
        result.line_count += 1
        try:
            result.items.extend(parse_line(line, number, raw, today))
        except LineError as problem:
            result.items.append(LineProblem(number, raw.strip(), problem.template, problem.params))
    return result
