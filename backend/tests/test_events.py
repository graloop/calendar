# Adding, listing, changing and deleting events by hand, and the rules every
# event follows whatever changes it (an end after its start, and so on).

from app.database import SessionLocal
from app.models import Event

from .conftest import add_event


def test_add_and_read_back(client):
    event = add_event(client, start_time="13:30", end_time="15:20", location="  D7-2018 ")
    assert event["title"] == "Lab 3"
    assert event["course_code"] == "ABC123"
    assert event["course_color"].startswith("#")
    assert (event["start_time"], event["end_time"]) == ("13:30", "15:20")
    assert event["location"] == "D7-2018"
    assert event["done"] is False
    assert client.get(f"/api/events/{event['id']}").json() == event


def test_a_new_course_code_creates_the_course_once(client):
    add_event(client, course=" abc 123 ")
    add_event(client, course="ABC123")
    courses = client.get("/api/courses").json()
    assert [(c["code"], c["event_count"]) for c in courses] == [("ABC123", 2)]


def test_no_course(client):
    assert add_event(client, course="-")["course_id"] is None
    assert add_event(client, course=None)["course_code"] is None


def test_defaults_to_all_day_and_type_other(client):
    event = client.post("/api/events", json={"title": "Appointment", "date": "2026-11-25"}).json()
    assert event["type"] == "other"
    assert event["start_time"] is None and event["end_time"] is None


def test_listing_is_in_date_and_time_order_with_all_day_first(client):
    add_event(client, title="late", date="2026-11-24", start_time="15:00")
    add_event(client, title="next day", date="2026-11-25", start_time="08:00")
    add_event(client, title="early", date="2026-11-24", start_time="08:30")
    add_event(client, title="all day", date="2026-11-24")
    titles = [e["title"] for e in client.get("/api/events").json()]
    assert titles == ["all day", "early", "late", "next day"]


def test_listing_filters(client):
    add_event(client, title="Rapport d'expérience", type="deadline", date="2026-11-20", start_time="23:59")
    add_event(client, title="Mid-term", type="exam", course="XYZ789", date="2026-11-24", location="Réunion room")
    add_event(client, title="Lab 4", date="2026-12-01")

    def titles(query):
        return [e["title"] for e in client.get(f"/api/events?{query}").json()]

    assert titles("from=2026-11-21&to=2026-11-30") == ["Mid-term"]
    assert titles("from=2026-11-24") == ["Mid-term", "Lab 4"]
    assert titles("course=xyz789") == ["Mid-term"]
    assert titles("type=deadline") == ["Rapport d'expérience"]
    # Accents and case don't matter in a search, and it looks at the location too.
    assert titles("q=EXPERIENCE") == ["Rapport d'expérience"]
    assert titles("q=reunion") == ["Mid-term"]
    assert titles("q=abc123 lab") == ["Lab 4"]


def test_tick_a_deadline_done_and_find_the_ones_not_done(client):
    due = add_event(client, type="deadline", start_time="23:59")
    add_event(client, type="deadline", title="Other", start_time="12:00")
    assert client.patch(f"/api/events/{due['id']}", json={"done": True}).json()["done"] is True
    assert [e["title"] for e in client.get("/api/events?type=deadline&done=false").json()] == ["Other"]


def test_move_and_change_only_what_was_sent(client):
    event = add_event(client, start_time="13:30", end_time="15:20", location="D7")
    moved = client.patch(f"/api/events/{event['id']}", json={"date": "2026-11-26", "start_time": "09:00"}).json()
    assert (moved["date"], moved["start_time"], moved["end_time"]) == ("2026-11-26", "09:00", "15:20")
    assert moved["location"] == "D7"


def test_a_field_sent_empty_is_cleared(client):
    event = add_event(client, location="D7", start_time="10:00", end_time="11:00")
    changed = client.patch(
        f"/api/events/{event['id']}", json={"location": "", "start_time": "", "end_time": None, "course": ""}
    ).json()
    assert changed["location"] is None and changed["start_time"] is None and changed["course_id"] is None


def test_title_and_date_can_not_be_emptied(client):
    event = add_event(client)
    assert client.patch(f"/api/events/{event['id']}", json={"title": None}).status_code == 422
    assert client.patch(f"/api/events/{event['id']}", json={"date": None}).status_code == 422
    assert client.post("/api/events", json={"title": "   ", "date": "2026-11-24"}).status_code == 422


def test_end_before_start_is_refused(client):
    response = client.post(
        "/api/events", json={"title": "x", "date": "2026-11-24", "start_time": "15:00", "end_time": "14:00"}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "The end time must be after the start time."


def test_end_without_start_is_refused(client):
    response = client.post("/api/events", json={"title": "x", "date": "2026-11-24", "end_time": "14:00"})
    assert response.json()["detail"] == "An end time needs a start time."


def test_a_deadline_has_no_end(client):
    response = client.post(
        "/api/events",
        json={"title": "x", "type": "deadline", "date": "2026-11-24", "start_time": "12:00", "end_time": "13:00"},
    )
    assert response.json()["detail"] == "A deadline has only a due time, no end time."
    # Turning a class into a deadline is checked the same way.
    event = add_event(client, start_time="10:00", end_time="11:00")
    assert client.patch(f"/api/events/{event['id']}", json={"type": "deadline"}).status_code == 422


def test_unknown_type_and_bad_course_code_are_refused(client):
    assert client.post("/api/events", json={"title": "x", "date": "2026-11-24", "type": "party"}).status_code == 422
    assert client.post("/api/events", json={"title": "x", "date": "2026-11-24", "course": "AB;C"}).status_code == 422


def test_delete_one(client):
    event = add_event(client)
    assert client.delete(f"/api/events/{event['id']}").status_code == 204
    assert client.get(f"/api/events/{event['id']}").status_code == 404
    assert client.delete(f"/api/events/{event['id']}").status_code == 404


def _make_series(client, dates):
    events = [add_event(client, date=d, type="class", title="Cours") for d in dates]
    with SessionLocal() as db:  # A "weekly until" import line does this in stage 2.
        for e in events:
            db.get(Event, e["id"]).series_id = "series1"
        db.commit()
    return events


def test_delete_one_event_of_a_series_keeps_the_others(client):
    events = _make_series(client, ["2026-11-03", "2026-11-10", "2026-11-17"])
    client.delete(f"/api/events/{events[1]['id']}")
    assert [e["date"] for e in client.get("/api/events").json()] == ["2026-11-03", "2026-11-17"]


def test_delete_a_whole_series(client):
    events = _make_series(client, ["2026-11-03", "2026-11-10", "2026-11-17"])
    other = add_event(client, title="Not in the series")
    assert client.delete(f"/api/events/{events[0]['id']}?series=1").status_code == 204
    assert [e["id"] for e in client.get("/api/events").json()] == [other["id"]]


def test_a_title_of_only_spaces_is_refused_on_change_too(client):
    event = add_event(client)
    assert client.patch(f"/api/events/{event['id']}", json={"title": "   "}).status_code == 422
    assert client.get(f"/api/events/{event['id']}").json()["title"] == "Lab 3"


def test_times_with_a_timezone_are_refused(client):
    for start in ("13:30Z", "13:30+05:00"):
        response = client.post("/api/events", json={"title": "x", "date": "2026-11-24", "start_time": start})
        assert response.status_code == 422, start


def test_search_wildcards_are_plain_characters(client):
    add_event(client, title="Quiz 100%")
    add_event(client, title="Lab 4")
    assert [e["title"] for e in client.get("/api/events?q=%25").json()] == ["Quiz 100%"]
    assert client.get("/api/events?q=_").json() == []


def test_course_filter_reads_codes_like_the_form(client):
    add_event(client)
    assert len(client.get("/api/events?course=abc 123").json()) == 1
    assert client.get("/api/events?course=a;b").json() == []
