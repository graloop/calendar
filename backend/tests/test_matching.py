# How the preview marks each line against the calendar: new, already there
# (also when a line repeats an earlier one of the same import), changed (old ->
# new) or error. Events are added by hand first, the way they'd already be there.

import datetime as dt

from app.database import SessionLocal
from app.importing.matching import classify, term_of
from app.importing.parser import parse_text

from .conftest import add_event

TODAY = dt.date(2026, 11, 10)


def preview(text):
    with SessionLocal() as db:
        return [r.to_json() for r in classify(db, parse_text(text, TODAY).items)]


def statuses(text):
    return [r["status"] for r in preview(text)]


def test_new_when_nothing_matches(client):
    rows = preview("2026-11-24 | 13:30-15:20 | lab | ABC123 | Lab 3")
    assert rows[0]["status"] == "new"
    assert rows[0]["new_course"] is True  # ABC123 isn't on the calendar yet
    assert rows[0]["event_id"] is None


def test_already_there_ignores_case_accents_and_spaces(client):
    event = add_event(client, title="Rapport d'expérience", type="deadline", start_time="23:59")
    rows = preview("Tue Nov 24 | 23:59 | remise | abc123 | RAPPORT  D'EXPERIENCE")
    assert rows[0]["status"] == "already"
    assert rows[0]["event_id"] == event["id"]
    assert rows[0]["new_course"] is False


def test_another_course_or_type_is_new(client):
    add_event(client, start_time="13:30", end_time="15:20")
    assert statuses("2026-11-24 | 13:30-15:20 | lab | XYZ789 | Lab 3") == ["new"]
    assert statuses("2026-11-24 | 13:30-15:20 | exam | ABC123 | Lab 3") == ["new"]


def test_same_day_but_another_time_is_changed(client):
    add_event(client, start_time="13:30", end_time="15:20", location="D7-2018")
    rows = preview("2026-11-24 | 14:00-16:00 | lab | ABC123 | Lab 3")
    assert rows[0]["status"] == "changed"
    assert rows[0]["changes"] == [
        {"field": "start_time", "before": "13:30", "after": "14:00"},
        {"field": "end_time", "before": "15:20", "after": "16:00"},
    ]  # no place on the line: the event keeps its own


def test_a_new_place_is_a_change(client):
    add_event(client, start_time="13:30", end_time="15:20", location="D7-2018")
    rows = preview("2026-11-24 | 13:30-15:20 | lab | ABC123 | Lab 3 | room: D7-3021")
    assert rows[0]["changes"] == [{"field": "location", "before": "D7-2018", "after": "D7-3021"}]


def test_a_moved_deadline_in_the_same_term_is_changed(client):
    event = add_event(client, title="Lab report 2", type="deadline", date="2026-11-20", start_time="23:59")
    rows = preview("Fri Nov 27 | 17:00 | deadline | ABC123 | Lab report 2 | | Email: Report 2 postponed, 2026-11-18")
    assert rows[0]["status"] == "changed"
    assert rows[0]["event_id"] == event["id"]
    assert rows[0]["changes"] == [
        {"field": "date", "before": "2026-11-20", "after": "2026-11-27"},
        {"field": "start_time", "before": "23:59", "after": "17:00"},
    ]


def test_same_title_in_another_term_is_new(client):
    add_event(client, title="Final exam", type="exam", date="2026-04-20")
    assert statuses("2026-12-15 | 9:00-12:00 | exam | ABC123 | Final exam") == ["new"]


def test_same_source_link_is_changed_even_with_a_new_title(client):
    link = "https://moodle.example.org/mod/assign/view.php?id=7"
    event = add_event(client, title="TP 2", type="deadline", date="2026-11-20", source_link=link)
    rows = preview(f"2026-11-27 | 23:59 | deadline | ABC123 | TP 2 (revised) | | {link}")
    assert rows[0]["status"] == "changed"
    assert rows[0]["event_id"] == event["id"]
    assert {c["field"] for c in rows[0]["changes"]} == {"date", "start_time", "title"}


def test_two_candidates_is_new_rather_than_a_guess(client):
    add_event(client, title="Quiz", type="exam", date="2026-11-17")
    add_event(client, title="Quiz", type="exam", date="2026-11-24")
    assert statuses("2026-12-01 | 9:00 | exam | ABC123 | Quiz") == ["new"]


def test_weekly_series_are_matched_week_by_week_only(client):
    text = "2026-11-10 | 13:30-15:20 | class | ABC123 | Lecture | weekly until 2026-11-24"
    add_event(client, title="Lecture", type="class", date="2026-11-03", start_time="13:30", end_time="15:20")
    # The Nov 3 lecture isn't "moved" to Nov 10: all three weeks are new.
    assert statuses(text) == ["new", "new", "new"]


def test_the_same_line_twice_in_one_import(client):
    rows = preview("2026-11-24 | 23:59 | deadline | ABC123 | TP 3\n- 2026-11-24 | 23:59 | Remise | abc123 | tp 3")
    assert [r["status"] for r in rows] == ["new", "already"]
    assert rows[1]["in_import"] is True


def test_one_event_is_matched_by_one_line_only(client):
    add_event(client, title="Lab report 2", type="deadline", date="2026-11-20", start_time="23:59")
    text = (
        "2026-11-20 | 23:59 | deadline | ABC123 | Lab report 2\n2026-11-27 | 23:59 | deadline | ABC123 | Lab report 2"
    )
    # The exact line gets the event; the other date can't also claim it.
    assert statuses(text) == ["already", "new"]


def test_errors_stay_in_their_place(client):
    rows = preview("2026-11-24 | 23:59 | deadline | ABC123 | TP\nMon Nov 24 | 23:59 | deadline | ABC123 | TP 2")
    assert [r["status"] for r in rows] == ["new", "error"]
    assert rows[1]["message"].startswith("2026-11-24 is a Tuesday")
    assert rows[1]["template"] and rows[1]["params"]["written"] == "Monday"


def test_terms():
    assert term_of(dt.date(2026, 1, 5)) == term_of(dt.date(2026, 4, 30))
    assert term_of(dt.date(2026, 5, 1)) == term_of(dt.date(2026, 8, 31))
    assert term_of(dt.date(2026, 9, 1)) == term_of(dt.date(2026, 12, 31))
    assert term_of(dt.date(2026, 4, 30)) != term_of(dt.date(2026, 5, 1))
    assert term_of(dt.date(2026, 12, 31)) != term_of(dt.date(2027, 1, 1))
