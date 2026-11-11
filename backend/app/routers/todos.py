# This week's list: things to get done during a week, not on a set day ("read
# chapter 4", "book the dentist"). Each week is named by its Monday, each item
# is on one calendar, and what's left at the end of a week can move to the next
# (or what's planned for next week can be brought back to this one).

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Todo
from ..schemas import CarryOver, TodoCreate, TodoOut, TodoUpdate
from . import calendars

router = APIRouter(prefix="/api/todos", tags=["todos"])


def _get_or_404(db: Session, todo_id: int) -> Todo:
    item = db.get(Todo, todo_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "To-do not found.")
    return item


def _next_position(db: Session, week: dt.date) -> int:
    """New items go at the end of the week's list."""
    last = db.scalar(select(func.max(Todo.position)).where(Todo.week == week))
    return 0 if last is None else last + 1


@router.get("", response_model=list[TodoOut])
def list_todos(
    week: dt.date | None = Query(None, description="The week's Monday."),
    start: dt.date | None = Query(None, alias="from", description="With `to`: every week from this Monday..."),
    end: dt.date | None = Query(None, alias="to", description="...to this Monday (the Month view's weeks)."),
    calendar: int | None = Query(None, description="A calendar's id; none for all of them."),
    db: Session = Depends(get_db),
):
    # Either one week, or a range of weeks; each is named by its Monday.
    if week is not None:
        start = end = week
    if start is None or end is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a week, or from and to.")
    if start.weekday() != 0 or end.weekday() != 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A week is given by its Monday.")
    query = select(Todo).where(Todo.week >= start, Todo.week <= end)
    if calendar is not None:
        query = query.where(Todo.calendar_id == calendar)
    return db.scalars(query.order_by(Todo.week, Todo.position, Todo.id)).all()


@router.post("", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
def create_todo(body: TodoCreate, db: Session = Depends(get_db)):
    calendar = calendars.get_or_422(db, body.calendar_id)
    item = Todo(week=body.week, calendar=calendar, text=body.text, position=_next_position(db, body.week))
    db.add(item)
    db.commit()
    return item


@router.patch("/{todo_id}", response_model=TodoOut)
def update_todo(todo_id: int, body: TodoUpdate, db: Session = Depends(get_db)):
    item = _get_or_404(db, todo_id)
    for name in ("text", "done", "position"):
        if getattr(body, name) is not None:
            setattr(item, name, getattr(body, name))
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, todo_id))
    db.commit()


def _move_unfinished(db: Session, from_week: dt.date, to_week: dt.date, calendar_id: int | None) -> int:
    """Moves what isn't done yet from one week's list to the end of another's."""
    query = select(Todo).where(Todo.week == from_week, Todo.done.is_(False))
    if calendar_id is not None:
        query = query.where(Todo.calendar_id == calendars.get_or_422(db, calendar_id).id)
    items = db.scalars(query.order_by(Todo.position, Todo.id)).all()
    position = _next_position(db, to_week)
    for i, item in enumerate(items):
        item.week = to_week
        item.position = position + i
    db.commit()
    return len(items)


@router.post("/carry-over")
def carry_over(body: CarryOver, db: Session = Depends(get_db)):
    """Moves what isn't done yet to the next week's list, after what's already there."""
    return {"moved": _move_unfinished(db, body.week, body.week + dt.timedelta(days=7), body.calendar_id)}


@router.post("/bring-back")
def bring_back(body: CarryOver, db: Session = Depends(get_db)):
    """The other way: brings what isn't done on the next week's list to this week's
    (`week`), after what's already there. For when I get ahead."""
    return {"moved": _move_unfinished(db, body.week + dt.timedelta(days=7), body.week, body.calendar_id)}
