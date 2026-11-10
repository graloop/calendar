# The calendars: the tabs above the views (School, Personal, Work... renamed as
# I like). Every event and every to-do is on one of them. There is always at
# least one, so a new event always has somewhere to go.

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..database import SessionLocal, engine, get_db
from ..models import Calendar, Event, Todo
from ..schemas import CalendarCreate, CalendarOut, CalendarUpdate

router = APIRouter(prefix="/api/calendars", tags=["calendars"])

# What a new database starts with: the three the app was asked for.
STARTING_CALENDARS = ["School", "Personal", "Work"]


def set_up_calendars() -> None:
    """Run at startup. Makes the starting calendars on a new database, and puts any
    event that has no calendar yet (one made before calendars existed) on the first."""
    with engine.begin() as conn:
        # add_missing_columns adds the column to an older table, but not its index.
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_calendar_id ON events (calendar_id)"))
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Calendar)) == 0:
            db.add_all(Calendar(name=name, position=i) for i, name in enumerate(STARTING_CALENDARS))
            db.flush()
        first = first_calendar(db)
        db.execute(Event.__table__.update().where(Event.calendar_id.is_(None)).values(calendar_id=first.id))
        db.commit()


def ordered(db: Session) -> list[Calendar]:
    return list(db.scalars(select(Calendar).order_by(Calendar.position, Calendar.id)))


def first_calendar(db: Session) -> Calendar:
    return db.scalars(select(Calendar).order_by(Calendar.position, Calendar.id)).first()


def get_or_422(db: Session, calendar_id: int) -> Calendar:
    """For an event or a to-do that names a calendar: an unknown one is a bad request, not a missing page."""
    calendar = db.get(Calendar, calendar_id)
    if calendar is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "This calendar doesn't exist.")
    return calendar


def _get_or_404(db: Session, calendar_id: int) -> Calendar:
    calendar = db.get(Calendar, calendar_id)
    if calendar is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calendar not found.")
    return calendar


def _require_free_name(db: Session, name: str, ignore_id: int | None = None) -> None:
    # casefold() in Python rather than lower() in SQLite, which only knows ASCII ("École" / "école").
    for other in ordered(db):
        if other.name.casefold() == name.casefold() and other.id != ignore_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Another calendar already has this name.")


def _renumber(calendars: list[Calendar]) -> None:
    """Positions 0, 1, 2... in this order, so there are never gaps or ties."""
    for i, calendar in enumerate(calendars):
        calendar.position = i


def _counts(db: Session, column, *where) -> dict[int, int]:
    rows = db.execute(select(column, func.count()).where(*where).group_by(column))
    return dict(rows.all())


@router.get("", response_model=list[CalendarOut])
def list_calendars(db: Session = Depends(get_db)):
    # A few grouped counts for all calendars at once, rather than a few per calendar.
    events = _counts(db, Event.calendar_id)
    open_todos = _counts(db, Todo.calendar_id, Todo.done.is_(False))
    all_todos = _counts(db, Todo.calendar_id)
    return [
        CalendarOut(
            id=c.id,
            name=c.name,
            position=c.position,
            event_count=events.get(c.id, 0),
            todo_count=open_todos.get(c.id, 0),
            todo_total=all_todos.get(c.id, 0),
        )
        for c in ordered(db)
    ]


@router.post("", response_model=CalendarOut, status_code=status.HTTP_201_CREATED)
def create_calendar(body: CalendarCreate, db: Session = Depends(get_db)):
    _require_free_name(db, body.name)
    calendar = Calendar(name=body.name, position=len(ordered(db)))  # a new one goes last
    db.add(calendar)
    db.commit()
    return CalendarOut(id=calendar.id, name=calendar.name, position=calendar.position)


@router.patch("/{calendar_id}", response_model=CalendarOut)
def update_calendar(calendar_id: int, body: CalendarUpdate, db: Session = Depends(get_db)):
    calendar = _get_or_404(db, calendar_id)
    if body.name is not None:
        _require_free_name(db, body.name, ignore_id=calendar.id)
        calendar.name = body.name
    if body.position is not None:
        # Moving one tab shifts the others along, like dragging it to that place.
        others = [c for c in ordered(db) if c.id != calendar.id]
        others.insert(min(body.position, len(others)), calendar)
        _renumber(others)
    db.commit()
    return next(c for c in list_calendars(db) if c.id == calendar.id)


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calendar(
    calendar_id: int,
    delete_events: bool = Query(False, description="Required when it still has events or to-dos."),
    db: Session = Depends(get_db),
):
    calendar = _get_or_404(db, calendar_id)
    if len(ordered(db)) == 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "The last calendar can't be removed.")
    events = list(db.scalars(select(Event).where(Event.calendar_id == calendar_id)).unique())
    todos = list(db.scalars(select(Todo).where(Todo.calendar_id == calendar_id)))
    # The page asks first and says how many; this guards against anything that doesn't.
    if (events or todos) and not delete_events:
        raise HTTPException(status.HTTP_409_CONFLICT, "This calendar still has events or to-dos.")
    for item in [*events, *todos]:
        db.delete(item)
    db.delete(calendar)
    db.flush()
    _renumber(ordered(db))
    db.commit()
