# The courses: codes are unique and uppercase, each new one gets its own colour,
# and removing one that still has events has to be asked for.

from .conftest import add_event


def test_add_list_and_change(client):
    created = client.post("/api/courses", json={"code": "abc123", "name": " Fake course "})
    assert created.status_code == 201
    course = created.json()
    assert (course["code"], course["name"], course["event_count"]) == ("ABC123", "Fake course", 0)
    changed = client.patch(f"/api/courses/{course['id']}", json={"color": "#123456", "name": ""}).json()
    assert (changed["color"], changed["name"]) == ("#123456", None)


def test_each_new_course_gets_another_colour(client):
    first = client.post("/api/courses", json={"code": "ABC123"}).json()
    second = client.post("/api/courses", json={"code": "XYZ789"}).json()
    assert first["color"] != second["color"]


def test_codes_are_unique(client):
    client.post("/api/courses", json={"code": "ABC123"})
    assert client.post("/api/courses", json={"code": "abc123"}).status_code == 409
    other = client.post("/api/courses", json={"code": "XYZ789"}).json()
    assert client.patch(f"/api/courses/{other['id']}", json={"code": "ABC123"}).status_code == 409


def test_bad_code_and_colour_are_refused(client):
    assert client.post("/api/courses", json={"code": ""}).status_code == 422
    assert client.post("/api/courses", json={"code": "AB C;"}).status_code == 422
    assert client.post("/api/courses", json={"code": "ABC123", "color": "red;}"}).status_code == 422


def test_renaming_a_code_moves_its_events(client):
    event = add_event(client)
    course_id = event["course_id"]
    client.patch(f"/api/courses/{course_id}", json={"code": "ABC124"})
    assert client.get(f"/api/events/{event['id']}").json()["course_code"] == "ABC124"


def test_remove_an_empty_course(client):
    course = client.post("/api/courses", json={"code": "ABC123"}).json()
    assert client.delete(f"/api/courses/{course['id']}").status_code == 204
    assert client.get("/api/courses").json() == []


def test_removing_a_course_with_events_has_to_be_asked_for(client):
    event = add_event(client)
    kept = add_event(client, course="XYZ789")
    course_id = event["course_id"]
    assert client.delete(f"/api/courses/{course_id}").status_code == 409
    assert client.get(f"/api/events/{event['id']}").status_code == 200
    assert client.delete(f"/api/courses/{course_id}?delete_events=true").status_code == 204
    assert client.get(f"/api/events/{event['id']}").status_code == 404
    assert client.get(f"/api/events/{kept['id']}").status_code == 200


def test_a_dash_is_not_a_course_code(client):
    response = client.post("/api/courses", json={"code": "-"})
    assert response.status_code == 422
    assert "like ABC123" in response.json()["detail"][0]["msg"]
