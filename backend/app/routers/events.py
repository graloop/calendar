# The events themselves: list them for a range of days, add one by hand, change
# it (move, rename, tick a deadline done) and delete it or its whole series.

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import fold, get_db
from ..models import Course, Event
from ..schemas import EventCreate, EventFields, EventOut, EventType, tidy_code
from . import calendars, courses

router = APIRouter(prefix="/api/events", tags=["events"])


def _get_or_404(db: Session, event_id: int) -> Event:
    item = db.get(Event, event_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found.")
    return item


def _check_times(item: Event) -> None:
    """The rules that need several fields at once, checked on the event as it will
    be saved, so a change to one field can't break them either."""
    if item.end_time and not item.start_time:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "An end time needs a start time.")
    if item.type == "deadline" and item.end_time:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A deadline has only a due time, no end time.")
    if item.start_time and item.end_time and item.end_time <= item.start_time:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The end time must be after the start time.")


def _apply(db: Session, item: Event, body: EventFields, always: set[str] = frozenset()) -> None:
    """Copies what the request sent onto the event (plus the `always` fields, which
    a new event takes even when left to their default). A field sent empty clears it."""
    sent = body.model_fields_set | always
    if any(name in sent and getattr(body, name) is None for name in ("title", "type", "date", "done")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The title, type and date can't be empty.")
    for name in ("title", "type", "date", "start_time", "end_time", "location", "details", "source_link", "done"):
        if name in sent:
            setattr(item, name, getattr(body, name))
    if "course" in sent:
        item.course = courses.get_or_create(db, body.course)
    # Sent empty on a change: stays where it is. Left out on a new event: the first calendar.
    if body.calendar_id is not None:
        item.calendar = calendars.get_or_422(db, body.calendar_id)
    elif item.calendar_id is None:
        item.calendar = calendars.first_calendar(db)
    _check_times(item)


@router.get("", response_model=list[EventOut])
def list_events(
    from_: dt.date | None = Query(None, alias="from", description="First day, included."),
    to: dt.date | None = Query(None, description="Last day, included."),
    course: str | None = Query(None, description="A course code."),
    calendar: int | None = Query(None, description="A calendar's id; none for all of them."),
    type: EventType | None = None,
    q: str | None = Query(None, description="Words in the title, details, location or course."),
    done: bool | None = None,
    db: Session = Depends(get_db),
):
    query = select(Event).outerjoin(Event.course)
    if from_:
        query = query.where(Event.date >= from_)
    if to:
        query = query.where(Event.date <= to)
    if course:
        try:
            code = tidy_code(course)  # "abc 123" finds ABC123, as the event form writes it
        except ValueError:
            code = None  # Not a possible code: nothing matches.
        query = query.where(Course.code == (code or ""))
    if calendar is not None:
        query = query.where(Event.calendar_id == calendar)
    if type:
        query = query.where(Event.type == type)
    if done is not None:
        query = query.where(Event.done.is_(done))
    for word in fold(q).split():
        # % and _ are wildcards in LIKE: escaped, so searching "%" finds a "%".
        escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.where(
            or_(
                func.fold(Event.title).like(pattern, escape="\\"),
                func.fold(Event.details).like(pattern, escape="\\"),
                func.fold(Event.location).like(pattern, escape="\\"),
                func.fold(Course.code).like(pattern, escape="\\"),
            )
        )
    # All-day events (no start time) come first in a day: SQLite puts NULL first.
    return db.scalars(query.order_by(Event.date, Event.start_time, Event.id)).unique().all()


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, event_id)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate, db: Session = Depends(get_db)):
    item = Event()
    _apply(db, item, body, always={"title", "type", "date"})
    db.add(item)
    db.commit()
    return item


@router.patch("/{event_id}", response_model=EventOut)
def update_event(event_id: int, body: EventFields, db: Session = Depends(get_db)):
    item = _get_or_404(db, event_id)
    _apply(db, item, body)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    series: bool = Query(False, description="Also delete the other events of its series."),
    db: Session = Depends(get_db),
):
    item = _get_or_404(db, event_id)
    if series and item.series_id:
        for other in db.scalars(select(Event).where(Event.series_id == item.series_id)).unique():
            db.delete(other)
    else:
        db.delete(item)
    db.commit()
