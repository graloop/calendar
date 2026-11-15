# The compact text the connector's tools answer with (server.py): one line per
# event, per preview row, per import. Written for Claude to read and repeat to
# the user, never JSON. Text that came from an email or Moodle is copied as it
# is: it's data, and Claude is told so (server.INSTRUCTIONS).

import datetime as dt

from ..models import Event, ImportRun
from ..schemas import EVENT_TYPES

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def day(value: dt.date) -> str:
    """ "Tue 2026-11-24": the weekday helps Claude (and the user) check a date at a glance."""
    return f"{WEEKDAYS[value.weekday()]} {value.isoformat()}"


def hh_mm(value: dt.time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def when(start: dt.time | None, end: dt.time | None) -> str:
    """ "13:30-15:20", "23:59" or "all day"."""
    if start is None:
        return "all day"
    return f"{hh_mm(start)}-{hh_mm(end)}" if end else hh_mm(start)


def event_line(e: Event) -> str:
    """#123 · Tue 2026-11-24 23:59 · deadline · ABC123 · Lab report 3 · done: no"""
    parts = [f"#{e.id}", f"{day(e.date)} {when(e.start_time, e.end_time)}", e.type, e.course_code or "-", e.title]
    if e.location:
        parts.append(f"room {e.location}")
    if e.type == "deadline":
        parts.append(f"done: {'yes' if e.done else 'no'}")
    if e.calendar_name:
        parts.append(f"calendar {e.calendar_name}")
    return " · ".join(parts)


def sort_day(events: list[Event]) -> list[Event]:
    """Within a day, like the page: deadlines first, then all-day, then by start time."""

    def rank(e: Event) -> tuple:
        return (0 if e.type == "deadline" else 2 if e.start_time else 1, hh_mm(e.start_time) or "")

    return sorted(events, key=rank)


def event_detail(e: Event) -> str:
    """Every field of one event, one per line."""
    lines = [
        event_line(e),
        f"title: {e.title}",
        f"type: {e.type}",
        f"course: {e.course_code or '-'}",
        f"date: {day(e.date)}",
        f"start_time: {hh_mm(e.start_time) or '-'}",
        f"end_time: {hh_mm(e.end_time) or '-'}",
        f"location: {e.location or '-'}",
        f"calendar: {e.calendar_name or '-'} (id {e.calendar_id})",
        f"done: {'yes' if e.done else 'no'}",
        f"source: {e.source_link or '-'}",
        f"series: {e.series_id or 'none'}"
        + (" (delete_event with series=true removes every week)" if e.series_id else ""),
        f"from import: {f'#{e.import_id}' if e.import_id else 'no (added by hand)'}",
        f"details: {e.details or '-'}",
    ]
    return "\n".join(lines)


def import_line(run: ImportRun) -> str:
    """#7 · 2026-11-10 14:02 · moodle · 12 lines · added 5, changed 1, skipped 3 · undone 2026-11-11 09:00"""
    state = f"undone {run.undone_at:%Y-%m-%d %H:%M}" if run.undone_at else "can be undone"
    return (
        f"#{run.id} · {run.created_at:%Y-%m-%d %H:%M} · {run.source} · {run.line_count} lines · "
        f"added {run.added}, changed {run.changed}, skipped {run.skipped} · {state}"
    )


# --- The preview ---


def _parsed(row: dict) -> str:
    """The event a preview row would make, from the row's JSON."""
    parts = [
        f"{day(dt.date.fromisoformat(row['date']))} {when_text(row)}",
        row["type"],
        row["course"] or "-",
        row["title"],
    ]
    if row.get("location"):
        parts.append(f"room {row['location']}")
    return " · ".join(parts)


def when_text(row: dict) -> str:
    start, end = row.get("start_time"), row.get("end_time")
    if not start:
        return "all day"
    return f"{start}-{end}" if end else start


def _change(change: dict) -> str:
    return f"{change['field']} {change['before'] or '-'} → {change['after'] or '-'}"


def preview_text(out: dict, preview_id: str) -> str:
    """The preview as the Import tab shows it: counts, then one line per row.
    A weekly line's events are folded into one row per status."""
    c = out["counts"]
    lines = [
        f"PREVIEW {preview_id} · new events go in calendar {out['calendar_name']} · source {out['source']}",
        f"{c['new']} new, {c['changed']} changed, {c['already']} already there, {c['error']} with an error. Nothing is saved yet.",
        "",
    ]
    shown: dict[tuple, list[dict]] = {}
    for row in out["rows"]:
        # The events of one weekly line with the same status are told as one row.
        key = (row["line"], row["status"]) if row.get("series") else (row["line"], row["status"], id(row))
        shown.setdefault(key, []).append(row)
    for group in shown.values():
        row = group[0]
        head = f"line {row['line']}"
        if row["status"] == "error":
            lines.append(f'{head} · ERROR · "{row["text"]}" · {row["message"]}')
            continue
        event = _parsed(row)
        if len(group) > 1:
            last = dt.date.fromisoformat(group[-1]["date"])
            event += f" · ×{len(group)}, weekly until {day(last)}"
        if row["status"] == "new":
            extra = f" · adds the new course {row['course']}" if row.get("new_course") else ""
            lines.append(f"{head} · NEW · {event}{extra}")
        elif row["status"] == "already":
            where = "an earlier line" if row.get("in_import") else f"#{row['event_id']}"
            lines.append(f"{head} · already there ({where}), skipped · {event}")
        else:
            changes = "; ".join(_change(ch) for ch in row["changes"])
            lines.append(f"{head} · CHANGED #{row['event_id']} · {row['title']} · {changes}")
    if c["new"] or c["changed"]:
        lines += [
            "",
            "Show the user the NEW and CHANGED rows. Call apply_import with this preview_id only after they say yes.",
        ]
    if c["error"]:
        lines.append("Lines with an ERROR are left out; fix them and preview again if they matter.")
    return "\n".join(lines)


# --- How to write the lines ---

IMPORT_FORMAT = f"""HOW TO WRITE IMPORT LINES (for preview_import)

One event per line, fields in this order, separated by |:
date | time | type | course | title | details | source

- date: 2026-11-24 or Tue Nov 24 (French works too: mardi 24 novembre). If you write the weekday it must
  match the date, or the line is refused. Without a year, the nearest one is used. At most a year away.
- time: 13:30-15:20, or a start and a length: 13:30 75 min (14h30 works too). A deadline has only its due
  time: 23:59. Write all day when there is no time.
- type: one of {", ".join(EVENT_TYPES)}. French words work too: cours, labo, examen, remise, réunion.
- course: the course code, like ABC123, or - for none. A code the calendar doesn't know yet adds the course.
- title: short, like Lab report 3 or Final exam. Keep the title the course uses: matching uses it.
- details (optional): free text. room: D7-2018 sets the place. weekly until 2026-12-12 repeats the event
  every week up to that date (one series); except 2026-10-13 skips a week (write except again for each).
- source (optional): the Moodle page's address, or Email: <subject>, <date> for an email. With it, a moved
  deadline is recognised even when its title changed a little.

Examples (made-up course):
Tue Nov 24 | 23:59 | deadline | ABC123 | Lab report 3 | Upload one PDF | https://moodle.example.org/mod/assign/view.php?id=301
2026-12-08 | 9:00-12:00 | exam | ABC123 | Final exam | room: D7-2018 | Email: Final exam room, 2026-11-20
2026-09-08 | 13:30-15:20 | class | ABC123 | Lecture | weekly until 2026-12-08; except 2026-10-13; room: D3-2030 |

The preview marks each line NEW, already there (skipped), CHANGED (old → new: the same event moved) or
ERROR (with how to fix it). Running the same lines twice adds nothing. Nothing is saved until apply_import."""
