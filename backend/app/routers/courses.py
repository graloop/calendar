# The courses: a code like ABC123, an optional name, and the colour its events
# are drawn in. A course is also made by itself when an event names a new code.

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Course, Event
from ..schemas import CourseCreate, CourseOut, CourseUpdate

router = APIRouter(prefix="/api/courses", tags=["courses"])

# New courses take the next colour: all stay readable with white text, by day and at night.
PALETTE = ["#2563eb", "#059669", "#7c3aed", "#db2777", "#0891b2", "#ca8a04", "#4d7c0f", "#9333ea", "#be123c", "#0f766e"]


def next_color(db: Session) -> str:
    count = db.scalar(select(func.count()).select_from(Course))
    return PALETTE[count % len(PALETTE)]


def get_or_create(db: Session, code: str | None) -> Course | None:
    """The course with this code, made now if it's new. No code: no course."""
    if code is None:
        return None
    course = db.scalar(select(Course).where(Course.code == code))
    if course is None:
        course = Course(code=code, color=next_color(db))
        db.add(course)
        db.flush()  # Gives it an id now, so an event can point to it.
    return course


def _event_count(db: Session, course_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Event).where(Event.course_id == course_id))


def _out(db: Session, course: Course) -> CourseOut:
    return CourseOut(
        id=course.id, code=course.code, name=course.name, color=course.color, event_count=_event_count(db, course.id)
    )


def _get_or_404(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found.")
    return course


def _require_free_code(db: Session, code: str, ignore_id: int | None = None) -> None:
    other = db.scalar(select(Course).where(Course.code == code))
    if other is not None and other.id != ignore_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Another course already has this code.")


@router.get("", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db)):
    return [_out(db, c) for c in db.scalars(select(Course).order_by(Course.code))]


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(body: CourseCreate, db: Session = Depends(get_db)):
    _require_free_code(db, body.code)
    course = Course(code=body.code, name=body.name, color=body.color or next_color(db))
    db.add(course)
    db.commit()
    return _out(db, course)


@router.patch("/{course_id}", response_model=CourseOut)
def update_course(course_id: int, body: CourseUpdate, db: Session = Depends(get_db)):
    course = _get_or_404(db, course_id)
    if body.code is not None:
        _require_free_code(db, body.code, ignore_id=course.id)
        course.code = body.code
    if "name" in body.model_fields_set:  # Sending it empty clears it.
        course.name = body.name
    if body.color is not None:
        course.color = body.color
    db.commit()
    return _out(db, course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    delete_events: bool = Query(False, description="Required when the course still has events."),
    db: Session = Depends(get_db),
):
    course = _get_or_404(db, course_id)
    events = list(db.scalars(select(Event).where(Event.course_id == course_id)).unique())
    # The page asks first and says how many; this guards against anything that doesn't.
    if events and not delete_events:
        raise HTTPException(status.HTTP_409_CONFLICT, "This course still has events.")
    for item in events:
        db.delete(item)
    db.delete(course)
    db.commit()
