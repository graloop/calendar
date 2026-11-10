# Saving a preview as one import, and undoing an import. The router has already
# checked that these rows are exactly the ones shown in the preview.
#   save_import(): adds the "new" rows, updates the "changed" ones (keeping their
#     old values in import_changes), and records it all as one ImportRun.
#   undo_import(): removes what the import added and puts back what it changed.
# Neither commits: the router does, so a failure halfway leaves nothing behind.

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Event, ImportChange, ImportRun
from ..routers import courses
from .matching import PreviewRow

# The fields an import can change on an existing event, and so the ones undo puts back.
CHANGEABLE = ("date", "start_time", "end_time", "location", "title")


def _snapshot(item: Event) -> dict:
    """The changeable fields as JSON (dates and times as text)."""
    return {
        "date": item.date.isoformat(),
        "start_time": item.start_time.strftime("%H:%M") if item.start_time else None,
        "end_time": item.end_time.strftime("%H:%M") if item.end_time else None,
        "location": item.location,
        "title": item.title,
    }


def _restore(item: Event, before: dict) -> None:
    item.date = dt.date.fromisoformat(before["date"])
    item.start_time = dt.time.fromisoformat(before["start_time"]) if before["start_time"] else None
    item.end_time = dt.time.fromisoformat(before["end_time"]) if before["end_time"] else None
    item.location = before["location"]
    item.title = before["title"]


def save_import(
    db: Session,
    rows: list[PreviewRow],
    source: str,
    line_count: int,
    extra_fields: dict | None = None,
) -> ImportRun | None:
    """Saves the new and changed rows as one import. `extra_fields` are set on
    every new event (e.g. which calendar it goes in). Nothing to save: no import
    is recorded, and None comes back."""
    to_add = [r for r in rows if r.status == "new"]
    to_change = [r for r in rows if r.status == "changed"]
    if not to_add and not to_change:
        return None
    run = ImportRun(
        source=source,
        line_count=line_count,
        added=len(to_add),
        changed=len(to_change),
        skipped=sum(r.status == "already" for r in rows),
    )
    db.add(run)
    db.flush()  # Gives the import its id, for the events to point to.

    series_ids: dict[int, str] = {}  # one series per "weekly until" line
    for row in to_add:
        e = row.event
        item = Event(
            title=e.title,
            type=e.type,
            course=courses.get_or_create(db, e.course),  # An unknown code makes the course now, not at preview.
            date=e.date,
            start_time=e.start_time,
            end_time=e.end_time,
            location=e.location,
            details=e.details,
            source_link=e.source_link,
            series_id=series_ids.setdefault(row.line, uuid.uuid4().hex) if e.series else None,
            import_id=run.id,
        )
        for name, value in (extra_fields or {}).items():
            setattr(item, name, value)
        db.add(item)

    for row in to_change:
        item = db.get(Event, row.event_id)
        db.add(ImportChange(import_id=run.id, event_id=item.id, before=_snapshot(item)))
        e = row.event
        item.date, item.start_time, item.end_time = e.date, e.start_time, e.end_time
        if e.location is not None:
            item.location = e.location
        item.title = e.title
    db.flush()
    return run


def undo_import(db: Session, run: ImportRun) -> tuple[int, int]:
    """(removed, restored). A changed event goes back to how it was just before
    this import, even if it was edited again since: undo means "as before"."""
    removed = 0
    for item in db.scalars(select(Event).where(Event.import_id == run.id)).unique():
        db.delete(item)
        removed += 1
    restored = 0
    changes = db.scalars(select(ImportChange).where(ImportChange.import_id == run.id).order_by(ImportChange.id.desc()))
    for change in changes:
        item = db.get(Event, change.event_id)
        if item is not None:  # deleted by hand since: nothing to put back
            _restore(item, change.before)
            restored += 1
    run.undone_at = dt.datetime.now().replace(microsecond=0)
    return removed, restored
