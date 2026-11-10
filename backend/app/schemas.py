# The shapes of what the API accepts and answers. FastAPI checks every request
# against these and answers 422 when something doesn't fit. The rules that
# involve several fields at once (an end after the start...) are in
# routers/events.py, so they also apply to a partial change.

import datetime as dt
import re
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

EventType = Literal["class", "lab", "exam", "deadline", "meeting", "work", "personal", "other"]
EVENT_TYPES: tuple[str, ...] = get_args(EventType)

Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
COURSE_CODE = re.compile(r"[A-Z0-9][A-Z0-9_-]{0,19}")


def tidy_code(value):
    """ " abc 123 " -> "ABC123". Empty or "-" means no course."""
    if not isinstance(value, str):
        return value
    code = "".join(value.split()).upper()
    if code in ("", "-"):
        return None
    if not COURSE_CODE.fullmatch(code):
        raise ValueError("A course code is letters and digits, like ABC123.")
    return code


def tidy_text(value):
    """Extra spaces and empty strings out: an empty field is no value."""
    if not isinstance(value, str):
        return value
    return value.strip() or None


# --- Courses ---


class CourseCreate(BaseModel):
    # str | None: "-" or "" tidy to None, and _required below then says what a code looks like.
    code: str | None = Field(max_length=40)
    name: str | None = Field(default=None, max_length=200)
    color: Color | None = None

    _code = field_validator("code", mode="before")(tidy_code)
    _name = field_validator("name", mode="before")(tidy_text)

    @field_validator("code")
    @classmethod
    def _required(cls, value):
        if value is None:
            raise ValueError("A course code is letters and digits, like ABC123.")
        return value


class CourseUpdate(CourseCreate):
    code: str | None = Field(default=None, max_length=40)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str | None
    color: str
    event_count: int = 0


# --- Events ---


class EventFields(BaseModel):
    """What can be set on an event, all optional: a change sends only what changed."""

    title: str | None = Field(default=None, max_length=200)
    type: EventType | None = None
    course: str | None = Field(default=None, max_length=40)  # a course code; unknown creates it
    date: dt.date | None = None
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    location: str | None = Field(default=None, max_length=200)
    details: str | None = Field(default=None, max_length=5000)
    source_link: str | None = Field(default=None, max_length=500)
    done: bool | None = None
    calendar_id: int | None = None  # left out on a new event: the first calendar

    _code = field_validator("course", mode="before")(tidy_code)
    _texts = field_validator("location", "details", "source_link", mode="before")(tidy_text)

    @field_validator("title", mode="before")
    @classmethod
    def _tidy_title(cls, value):
        # A title of only spaces becomes no title, so "can't be empty" catches it.
        return (" ".join(value.split()) or None) if isinstance(value, str) else value

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _empty_time(cls, value):
        return None if value == "" else value

    @field_validator("start_time", "end_time")
    @classmethod
    def _whole_minutes(cls, value: dt.time | None) -> dt.time | None:
        # Times are local, as on the wall clock: "13:30Z" or "13:30+05:00" would
        # be silently shifted or crash a comparison, so they're refused.
        if value and value.tzinfo is not None:
            raise ValueError("Write a local time like 13:30.")
        return value.replace(second=0, microsecond=0) if value else value


class EventCreate(EventFields):
    title: str = Field(min_length=1, max_length=200)
    type: EventType = "other"
    date: dt.date


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    type: EventType
    course_id: int | None
    course_code: str | None
    course_color: str | None
    calendar_id: int | None
    calendar_name: str | None
    date: dt.date
    start_time: dt.time | None
    end_time: dt.time | None
    location: str | None
    details: str | None
    source_link: str | None
    series_id: str | None
    import_id: int | None
    done: bool
    created_at: dt.datetime
    updated_at: dt.datetime

    # "13:30", the way a time field and a person write it, not "13:30:00".
    @field_serializer("start_time", "end_time")
    def _hh_mm(self, value: dt.time | None) -> str | None:
        return value.strftime("%H:%M") if value else None


# --- Calendars and this week's list ---


def tidy_line(value):
    """One line of text: spaces at the ends out, runs of spaces made one."""
    return " ".join(value.split()) if isinstance(value, str) else value


class CalendarCreate(BaseModel):
    name: str = Field(max_length=40)

    _name = field_validator("name", mode="before")(tidy_line)

    @field_validator("name")
    @classmethod
    def _required(cls, value):
        if not value:
            raise ValueError("Give the calendar a name.")
        return value


class CalendarUpdate(CalendarCreate):
    name: str | None = Field(default=None, max_length=40)
    position: int | None = Field(default=None, ge=0)


class CalendarOut(BaseModel):
    id: int
    name: str
    position: int
    event_count: int = 0
    todo_count: int = 0  # the to-dos not done yet, all weeks together
    todo_total: int = 0  # done or not: what removing the calendar would remove


def check_monday(value: dt.date) -> dt.date:
    if value.weekday() != 0:
        raise ValueError("A week is given by its Monday.")
    return value


def required_text(value):
    if not value:
        raise ValueError("Write what there is to do.")
    return value


class TodoCreate(BaseModel):
    week: dt.date
    calendar_id: int
    text: str = Field(max_length=300)

    _week = field_validator("week")(check_monday)
    _tidy = field_validator("text", mode="before")(tidy_line)
    _text = field_validator("text")(required_text)


class TodoUpdate(BaseModel):
    """A change sends only what changed. Sending the text empty is refused."""

    text: str | None = Field(default=None, max_length=300)
    done: bool | None = None
    position: int | None = Field(default=None, ge=0)

    _tidy = field_validator("text", mode="before")(tidy_line)
    _text = field_validator("text")(required_text)


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    week: dt.date
    calendar_id: int
    calendar_name: str
    text: str
    done: bool
    position: int
    created_at: dt.datetime
    updated_at: dt.datetime


class CarryOver(BaseModel):
    week: dt.date
    calendar_id: int | None = None  # none: every calendar

    _week = field_validator("week")(check_monday)
