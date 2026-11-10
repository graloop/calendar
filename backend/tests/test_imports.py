# The import API from start to end: the draft, the preview (which saves
# nothing), apply (only exactly what was previewed, and never twice), and undo
# (removes what was added, puts back what was changed, only once).

import datetime as dt
import pathlib
import re

import pytest

from app.database import SessionLocal
from app.models import Event, ImportChange
from app.routers import imports
from app.routers.imports import apply_import
from app.schemas import ImportApply

from .conftest import add_event

LINES = """Tue Nov 24 | 23:59 | deadline | ABC123 | Lab report 3 | | https://moodle.example.org/mod/assign/view.php?id=3
2026-11-26 | 13:30-15:20 | lab | XYZ789 | Lab 4 | room: D7-2018 | https://moodle.example.org/course/view.php?id=9
Mon Nov 24 | 10:00 | exam | ABC123 | Wrong weekday"""


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(imports, "today", lambda: dt.date(2026, 11, 10))


def preview(client, text=LINES, source="auto"):
    response = client.post("/api/import/preview", json={"text": text, "source": source})
    assert response.status_code == 200, response.text
    return response.json()


def apply(client, text=LINES, source="auto"):
    shown = preview(client, text, source)
    response = client.post("/api/import/apply", json={"text": text, "source": source, "hash": shown["hash"]})
    assert response.status_code == 200, response.text
    return response.json()


def all_events(client):
    return client.get("/api/events").json()


def test_draft_round_trip(client):
    assert client.get("/api/import/draft").json() == {"text": ""}
    assert client.put("/api/import/draft", json={"text": "2026-11-24 | ..."}).status_code == 200
    assert client.get("/api/import/draft").json() == {"text": "2026-11-24 | ..."}
    client.put("/api/import/draft", json={"text": "changed"})
    assert client.get("/api/import/draft").json() == {"text": "changed"}


def test_preview_saves_nothing(client):
    shown = preview(client)
    assert shown["counts"] == {"new": 2, "already": 0, "changed": 0, "error": 1}
    assert shown["source"] == "moodle"  # every source column is a Moodle address
    assert shown["line_count"] == 3
    assert [r["status"] for r in shown["rows"]] == ["new", "new", "error"]
    assert shown["rows"][1]["location"] == "D7-2018"
    assert all_events(client) == []
    assert client.get("/api/courses").json() == []  # a new course waits for the save too
    assert client.get("/api/imports").json() == []


def test_apply_saves_new_rows_as_one_import(client):
    result = apply(client)
    assert result == {"import_id": result["import_id"], "added": 2, "changed": 0, "skipped": 0, "errors": 1}
    events = all_events(client)
    assert [(e["title"], e["import_id"]) for e in events] == [
        ("Lab report 3", result["import_id"]),
        ("Lab 4", result["import_id"]),
    ]
    assert {c["code"] for c in client.get("/api/courses").json()} == {"ABC123", "XYZ789"}
    [run] = client.get("/api/imports").json()
    assert (run["source"], run["line_count"], run["added"], run["changed"], run["skipped"]) == ("moodle", 3, 2, 0, 0)
    assert run["undone_at"] is None


def test_apply_with_a_wrong_hash_is_refused(client):
    response = client.post("/api/import/apply", json={"text": LINES, "hash": "0" * 64})
    assert response.status_code == 409
    assert response.json()["detail"] == "The calendar changed since the preview. Press Preview again."
    assert all_events(client) == []


def test_apply_is_refused_when_the_calendar_changed_since_the_preview(client):
    shown = preview(client)
    add_event(client, title="Lab report 3", type="deadline", start_time="23:59")  # added meanwhile
    response = client.post("/api/import/apply", json={"text": LINES, "hash": shown["hash"]})
    assert response.status_code == 409
    assert len(all_events(client)) == 1


def test_apply_twice_adds_nothing_the_second_time(client):
    apply(client)
    second = preview(client)
    assert second["counts"] == {"new": 0, "already": 2, "changed": 0, "error": 1}
    result = apply(client)
    assert result == {"import_id": None, "added": 0, "changed": 0, "skipped": 2, "errors": 1}
    assert len(all_events(client)) == 2
    assert len(client.get("/api/imports").json()) == 1


def test_weekly_lines_share_a_series(client):
    text = "2026-11-10 | 13:30-15:20 | class | ABC123 | Lecture | weekly until 2026-12-08 except 2026-11-24\n"
    text += "2026-11-11 | 9:00-10:00 | class | XYZ789 | Tutorial | weekly until 2026-11-25"
    assert apply(client, text)["added"] == 7
    events = all_events(client)
    lectures = {e["series_id"] for e in events if e["title"] == "Lecture"}
    tutorials = {e["series_id"] for e in events if e["title"] == "Tutorial"}
    assert len(lectures) == 1 and len(tutorials) == 1 and lectures != tutorials and None not in lectures


def test_changed_rows_update_and_undo_restores_them(client):
    old = add_event(
        client, title="Lab report 2", type="deadline", date="2026-11-20", start_time="23:59", location="Online"
    )
    text = "Fri Nov 27 | 17:00 | deadline | ABC123 | Lab report 2 | | Email: Report 2 postponed, 2026-11-18\n"
    text += "2026-12-01 | 9:00 | exam | ABC123 | Quiz 3"
    shown = preview(client, text)
    assert [r["status"] for r in shown["rows"]] == ["changed", "new"]
    assert shown["source"] == "email"
    result = apply(client, text)
    assert (result["added"], result["changed"]) == (1, 1)

    moved = client.get(f"/api/events/{old['id']}").json()
    assert (moved["date"], moved["start_time"], moved["location"]) == ("2026-11-27", "17:00", "Online")
    assert moved["import_id"] is None  # a changed event isn't the import's: undo mustn't delete it

    response = client.post(f"/api/imports/{result['import_id']}/undo")
    assert response.status_code == 200
    assert (response.json()["removed"], response.json()["restored"]) == (1, 1)
    assert response.json()["import"]["undone_at"] is not None
    back = client.get(f"/api/events/{old['id']}").json()
    assert (back["date"], back["start_time"], back["title"], back["location"]) == (
        "2026-11-20",
        "23:59",
        "Lab report 2",
        "Online",
    )
    assert [e["id"] for e in all_events(client)] == [old["id"]]


def test_undo_twice_is_refused(client):
    run_id = apply(client)["import_id"]
    assert client.post(f"/api/imports/{run_id}/undo").status_code == 200
    again = client.post(f"/api/imports/{run_id}/undo")
    assert again.status_code == 409
    assert again.json()["detail"] == "This import was already undone."
    assert client.post("/api/imports/999/undo").status_code == 404


def test_undo_skips_an_event_deleted_by_hand(client):
    old = add_event(client, title="Exam", type="exam", date="2026-12-01", start_time="09:00")
    run_id = apply(client, "2026-12-02 | 9:00 | exam | ABC123 | Exam")["import_id"]
    client.delete(f"/api/events/{old['id']}")
    response = client.post(f"/api/imports/{run_id}/undo")
    assert response.status_code == 200 and response.json()["restored"] == 0


def test_imports_are_listed_newest_first(client):
    first = apply(client, "2026-11-24 | all day | other | - | One")["import_id"]
    second = apply(client, "2026-11-25 | all day | other | - | Two", source="manual")["import_id"]
    runs = client.get("/api/imports").json()
    assert [r["id"] for r in runs] == [second, first]
    assert [r["source"] for r in runs] == ["manual", "other"]


def test_a_preview_with_only_errors_has_nothing_to_add(client):
    shown = preview(client, "nonsense\nMon Nov 24 | 10:00 | exam | ABC123 | X")
    assert shown["counts"] == {"new": 0, "already": 0, "changed": 0, "error": 2}


def test_extra_fields_go_on_every_new_event(client):
    # The way a caller passes more to set on new events (stage 2b: which calendar).
    text = "2026-11-24 | all day | other | - | One"
    shown = preview(client, text)
    with SessionLocal() as db:
        result = apply_import(db, ImportApply(text=text, hash=shown["hash"]), extra_fields={"details": "from a caller"})
        assert result["added"] == 1
        assert [e.details for e in db.query(Event).all()] == ["from a caller"]
        assert db.query(ImportChange).count() == 0


# --- The fake Moodle and email pages (tests/fixtures/moodle/), for a real trial ---

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "moodle"
MOODLE = "file:///agenda/backend/tests/fixtures/moodle/abc123.html"

# What the Claude extension would write from abc123.html, then from email.html.
FROM_MOODLE = f"""Thu Nov 19 | 13:30-16:20 | lab | ABC123 | Lab 3 | room: D7-2018; bring your lab notebook | {MOODLE}
Fri Nov 20 | 23:59 | deadline | ABC123 | Lab report 2 | Upload one PDF | {MOODLE}#assign-201
Mon Nov 16 | 23:59 | deadline | ABC123 | Project proposal | | {MOODLE}#assign-202
Thu Nov 26 | 13:30-16:20 | lab | ABC123 | Lab 4 | room: D7-2018 | {MOODLE}
Tue Dec 1 | 10:30-11:20 | exam | ABC123 | Quiz 2 | room: D3-2030 | {MOODLE}
Fri Dec 4 | 23:59 | deadline | ABC123 | Lab report 3 | | {MOODLE}#assign-203
Mon Dec 14 | 9:00-12:00 | exam | ABC123 | Final exam | Room to be announced | {MOODLE}"""
FROM_EMAIL = """Fri Nov 27 | 17:00 | deadline | ABC123 | Lab report 2 | Postponed | Email: ABC123 – Lab report 2 postponed, 2026-11-18
Thu Nov 26 | 13:30-16:20 | lab | ABC123 | Lab 4 | room: D7-3021 | Email: ABC123 – Lab report 2 postponed, 2026-11-18"""


def test_a_trial_with_the_fake_pages(client):
    assert apply(client, FROM_MOODLE)["added"] == 7
    shown = preview(client, FROM_EMAIL)
    assert shown["source"] == "email"
    assert [r["status"] for r in shown["rows"]] == ["changed", "changed"]
    assert shown["rows"][0]["changes"][0] == {"field": "date", "before": "2026-11-20", "after": "2026-11-27"}
    assert shown["rows"][1]["changes"] == [{"field": "location", "before": "D7-2018", "after": "D7-3021"}]
    assert apply(client, FROM_EMAIL)["changed"] == 2
    assert preview(client, FROM_EMAIL)["counts"] == {"new": 0, "already": 2, "changed": 0, "error": 0}
    # Moodle not updated yet: its old date shows as a change back, in the preview, never silently.
    again = preview(client, FROM_MOODLE)["counts"]
    assert (again["new"], again["changed"]) == (0, 2)


def test_the_fake_pages_are_fake_and_open_without_a_server():
    pages = sorted(FIXTURES.glob("*.html"))
    assert len(pages) >= 4
    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert "<script" not in html  # plain pages: nothing runs when opened with file://
        assert 'src="http' not in html and 'href="http' not in html  # no outside links
        assert set(re.findall(r"\b[A-Z]{3}\d{3}\b", html)) <= {"ABC123", "XYZ789"}, page.name
        assert "made up" in html


def test_new_events_go_in_the_chosen_calendar(client):
    work = next(c for c in client.get("/api/calendars").json() if c["name"] == "Work")
    text = "2026-11-24 | 10:00-16:00 | work | - | Shift"
    preview = client.post("/api/import/preview", json={"text": text, "calendar_id": work["id"]}).json()
    assert preview["calendar_name"] == "Work"
    body = {"text": text, "calendar_id": work["id"], "hash": preview["hash"]}
    assert client.post("/api/import/apply", json=body).json()["added"] == 1
    assert [e["calendar_name"] for e in client.get("/api/events").json()] == ["Work"]


def test_without_a_calendar_new_events_go_in_the_first_one(client):
    text = "2026-11-24 | 13:30-15:20 | lab | ABC123 | Lab 3"
    preview = client.post("/api/import/preview", json={"text": text}).json()
    client.post("/api/import/apply", json={"text": text, "hash": preview["hash"]})
    assert [e["calendar_name"] for e in client.get("/api/events").json()] == ["School"]


def test_choosing_another_calendar_after_the_preview_is_refused(client):
    work = next(c for c in client.get("/api/calendars").json() if c["name"] == "Work")
    text = "2026-11-24 | 10:00-16:00 | work | - | Shift"
    preview = client.post("/api/import/preview", json={"text": text}).json()
    body = {"text": text, "calendar_id": work["id"], "hash": preview["hash"]}
    assert client.post("/api/import/apply", json=body).status_code == 409


def test_an_unknown_calendar_is_refused(client):
    response = client.post("/api/import/preview", json={"text": "x", "calendar_id": 999})
    assert response.status_code == 422
