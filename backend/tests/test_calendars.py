# The calendars (the tabs above the views): the three a new database starts
# with, renaming and moving them, unique names, and the rules for removing one.
# Events always end up on a calendar, even the ones made before calendars existed.

import datetime as dt

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Event, Todo

from .conftest import add_event


def calendars(client):
    return client.get("/api/calendars").json()


def ids(client):
    return {c["name"]: c["id"] for c in calendars(client)}


def test_a_new_database_starts_with_three_calendars(client):
    assert [(c["name"], c["position"]) for c in calendars(client)] == [("School", 0), ("Personal", 1), ("Work", 2)]


def test_starting_calendars_are_made_only_once(client):
    client.patch(f"/api/calendars/{ids(client)['Work']}", json={"name": "Job"})
    with TestClient(app) as again:  # A restart of the app.
        assert [c["name"] for c in calendars(again)] == ["School", "Personal", "Job"]


def test_add_rename_and_move(client):
    created = client.post("/api/calendars", json={"name": "  Side   project "})
    assert created.status_code == 201
    new = created.json()
    assert (new["name"], new["position"]) == ("Side project", 3)
    renamed = client.patch(f"/api/calendars/{new['id']}", json={"name": "Club"}).json()
    assert renamed["name"] == "Club"
    client.patch(f"/api/calendars/{new['id']}", json={"position": 0})
    assert [c["name"] for c in calendars(client)] == ["Club", "School", "Personal", "Work"]
    assert [c["position"] for c in calendars(client)] == [0, 1, 2, 3]


def test_names_are_unique_whatever_the_case(client):
    assert client.post("/api/calendars", json={"name": "school"}).status_code == 409
    response = client.patch(f"/api/calendars/{ids(client)['Work']}", json={"name": "PERSONAL"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Another calendar already has this name."
    # Changing only the case of its own name is fine.
    assert client.patch(f"/api/calendars/{ids(client)['Work']}", json={"name": "WORK"}).status_code == 200


def test_a_name_is_required_and_short(client):
    assert client.post("/api/calendars", json={"name": "   "}).status_code == 422
    assert client.post("/api/calendars", json={"name": "x" * 41}).status_code == 422
    assert client.patch(f"/api/calendars/{ids(client)['Work']}", json={"name": ""}).status_code == 422


def test_counts(client):
    work = ids(client)["Work"]
    add_event(client, calendar_id=work)
    client.post("/api/todos", json={"week": "2026-11-23", "calendar_id": work, "text": "a"})
    done = client.post("/api/todos", json={"week": "2026-11-23", "calendar_id": work, "text": "b"}).json()
    client.patch(f"/api/todos/{done['id']}", json={"done": True})
    row = next(c for c in calendars(client) if c["id"] == work)
    assert (row["event_count"], row["todo_count"], row["todo_total"]) == (1, 1, 2)


def test_remove_an_empty_calendar(client):
    assert client.delete(f"/api/calendars/{ids(client)['Personal']}").status_code == 204
    assert [(c["name"], c["position"]) for c in calendars(client)] == [("School", 0), ("Work", 1)]
    assert client.delete("/api/calendars/999").status_code == 404


def test_removing_a_calendar_with_events_or_todos_has_to_be_asked_for(client):
    work, school = ids(client)["Work"], ids(client)["School"]
    event = add_event(client, calendar_id=work)
    kept = add_event(client, calendar_id=school)
    client.post("/api/todos", json={"week": "2026-11-23", "calendar_id": work, "text": "Report"})
    assert client.delete(f"/api/calendars/{work}").status_code == 409
    assert client.delete(f"/api/calendars/{work}?delete_events=true").status_code == 204
    assert client.get(f"/api/events/{event['id']}").status_code == 404
    assert client.get(f"/api/events/{kept['id']}").status_code == 200
    with SessionLocal() as db:
        assert db.query(Todo).count() == 0


def test_a_todo_alone_also_has_to_be_asked_for(client):
    work = ids(client)["Work"]
    client.post("/api/todos", json={"week": "2026-11-23", "calendar_id": work, "text": "Report"})
    assert client.delete(f"/api/calendars/{work}").status_code == 409


def test_the_last_calendar_can_not_be_removed(client):
    names = ids(client)
    client.delete(f"/api/calendars/{names['Personal']}")
    client.delete(f"/api/calendars/{names['Work']}")
    response = client.delete(f"/api/calendars/{names['School']}?delete_events=true")
    assert response.status_code == 409
    assert response.json()["detail"] == "The last calendar can't be removed."


def test_a_new_event_goes_on_the_first_calendar_unless_told(client):
    client.patch(f"/api/calendars/{ids(client)['Personal']}", json={"position": 0})
    event = add_event(client)
    assert event["calendar_name"] == "Personal"
    work = add_event(client, calendar_id=ids(client)["Work"])
    assert (work["calendar_id"], work["calendar_name"]) == (ids(client)["Work"], "Work")


def test_move_an_event_to_another_calendar(client):
    event = add_event(client)
    moved = client.patch(f"/api/events/{event['id']}", json={"calendar_id": ids(client)["Work"]}).json()
    assert moved["calendar_name"] == "Work"
    # Sent empty, it stays where it is: an event is always on a calendar.
    assert client.patch(f"/api/events/{event['id']}", json={"calendar_id": None}).json()["calendar_name"] == "Work"


def test_an_unknown_calendar_is_refused(client):
    response = client.post("/api/events", json={"title": "x", "date": "2026-11-24", "calendar_id": 999})
    assert response.status_code == 422
    assert response.json()["detail"] == "This calendar doesn't exist."
    event = add_event(client)
    assert client.patch(f"/api/events/{event['id']}", json={"calendar_id": 999}).status_code == 422


def test_filter_events_by_calendar(client):
    add_event(client, title="School lab")
    add_event(client, title="Shift", type="work", calendar_id=ids(client)["Work"])
    titles = [e["title"] for e in client.get(f"/api/events?calendar={ids(client)['Work']}").json()]
    assert titles == ["Shift"]
    assert len(client.get("/api/events").json()) == 2


def test_events_from_before_calendars_go_on_the_first_one(client):
    # An event saved by an older version has no calendar; the next startup gives it one.
    add_event(client)
    with SessionLocal() as db:
        db.add(Event(title="Old event", type="other", date=dt.date(2026, 11, 25)))
        db.commit()
        db.query(Event).update({Event.calendar_id: None})
        db.commit()
    with TestClient(app) as restarted:
        events = restarted.get("/api/events").json()
        assert {e["calendar_name"] for e in events} == {"School"}
