# The database tables: courses, events, the imports that added events, and a
# small key-value table for things to remember (like the import box's text).
# Dates and times are local and stored as they are: one user, one timezone.

import datetime as dt

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)  # always uppercase, e.g. ABC123
    name: Mapped[str | None] = mapped_column(String(200))
    color: Mapped[str] = mapped_column(String(7))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)

    events: Mapped[list["Event"]] = relationship(back_populates="course")


class ImportRun(Base):
    """One press of "Add to calendar" (stage 2): what it did, so it can be undone."""

    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    source: Mapped[str] = mapped_column(String(10), default="other")  # moodle, email, other or manual
    line_count: Mapped[int] = mapped_column(Integer, default=0)
    added: Mapped[int] = mapped_column(Integer, default=0)
    changed: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    undone_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(10), default="other")  # an English key, see schemas.EventType
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    # No start time: all day. A deadline has a start (when it's due) and no end.
    start_time: Mapped[dt.time | None] = mapped_column(Time)
    end_time: Mapped[dt.time | None] = mapped_column(Time)
    location: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[str | None] = mapped_column(Text)
    # Where it came from: the Moodle page, or "Email: subject, date".
    source_link: Mapped[str | None] = mapped_column(String(500))
    # The same id on every event made by one "weekly until" line.
    series_id: Mapped[str | None] = mapped_column(String(32), index=True)
    import_id: Mapped[int | None] = mapped_column(ForeignKey("imports.id"), index=True)
    done: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    course: Mapped[Course | None] = relationship(back_populates="events", lazy="joined")

    @property
    def course_code(self) -> str | None:
        return self.course.code if self.course else None

    @property
    def course_color(self) -> str | None:
        return self.course.color if self.course else None


class AppState(Base):
    """Small things to remember between page loads, like the import box's text."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
