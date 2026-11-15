# The preview and the apply, shared by the Import tab (routers/imports.py) and
# Claude's connector (mcp/server.py), so both read and save lines the same way.
#
# Why a hash: whoever saw the preview sends back its hash. Apply makes the
# preview again from the same text and refuses if anything differs (the
# calendar changed, or it's another day), so nothing is ever saved that
# wasn't seen first.

import datetime as dt
import hashlib
import json

from sqlalchemy.orm import Session

from ..routers import calendars
from ..schemas import ImportApply, ImportRequest
from .matching import PreviewRow, classify, counts
from .parser import guess_source_kind, parse_text
from .saving import save_import


class StalePreview(Exception):
    """The calendar (or the day) changed since the preview: it must be made again."""


def _source(requested: str, rows: list[PreviewRow]) -> str:
    """The import's source: as chosen, or (auto) what every line's source column
    points to. Lines from several kinds, or none: other."""
    if requested != "auto":
        return requested
    kinds = {guess_source_kind(r.event.source_link) for r in rows if r.event and r.event.source_link}
    return kinds.pop() if len(kinds) == 1 else "other"


def build_preview(db: Session, body: ImportRequest, today: dt.date) -> tuple[list[PreviewRow], dict]:
    """(rows, {calendar_id, calendar_name, rows, counts, source, line_count, hash}). Saves nothing."""
    parsed = parse_text(body.text, today)
    rows = classify(db, parsed.items)
    source = _source(body.source, rows)
    # Part of what the preview shows (and of its hash): new events go in this calendar.
    calendar = calendars.get_or_422(db, body.calendar_id) if body.calendar_id else calendars.first_calendar(db)
    out = {
        "calendar_id": calendar.id,
        "calendar_name": calendar.name,
        "rows": [r.to_json() for r in rows],
        "counts": counts(rows),
        "source": source,
        "line_count": parsed.line_count,
    }
    digest = json.dumps(out, sort_keys=True, ensure_ascii=False).encode()
    out["hash"] = hashlib.sha256(digest).hexdigest()
    return rows, out


def apply_preview(db: Session, body: ImportApply, today: dt.date, extra_fields: dict | None = None) -> dict:
    """Saves the previewed rows if the preview is still the same, and commits.
    `extra_fields` go on every new event. Raises StalePreview otherwise."""
    rows, out = build_preview(db, body, today)
    if out["hash"] != body.hash:
        raise StalePreview("The calendar changed since the preview. Press Preview again.")
    fields = {"calendar_id": out["calendar_id"], **(extra_fields or {})}
    run = save_import(db, rows, out["source"], out["line_count"], fields)
    db.commit()
    c = out["counts"]
    return {
        "import_id": run.id if run else None,
        "added": c["new"],
        "changed": c["changed"],
        "skipped": c["already"],
        "errors": c["error"],
    }
