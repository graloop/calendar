# This week's list: weeks are named by their Monday, items can be added,
# ticked, reworded and removed, filtered by calendar, and what's left moves to
# the next week in one go.

MONDAY = "2026-11-23"
NEXT_MONDAY = "2026-11-30"


def calendar_ids(client):
    return {c["name"]: c["id"] for c in client.get("/api/calendars").json()}


def add_todo(client, text="Read chapter 4", week=MONDAY, calendar="School"):
    body = {"week": week, "calendar_id": calendar_ids(client)[calendar], "text": text}
    response = client.post("/api/todos", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def texts(client, query):
    return [t["text"] for t in client.get(f"/api/todos?{query}").json()]


def test_add_and_list(client):
    first = add_todo(client, text="  Read   chapter 4 ")
    add_todo(client, text="Book the dentist", calendar="Personal")
    add_todo(client, text="Next week's thing", week=NEXT_MONDAY)
    assert (first["text"], first["done"], first["calendar_name"], first["week"]) == (
        "Read chapter 4",
        False,
        "School",
        MONDAY,
    )
    assert texts(client, f"week={MONDAY}") == ["Read chapter 4", "Book the dentist"]


def test_filter_by_calendar(client):
    add_todo(client, text="Study")
    add_todo(client, text="Groceries", calendar="Personal")
    personal = calendar_ids(client)["Personal"]
    assert texts(client, f"week={MONDAY}&calendar={personal}") == ["Groceries"]


def test_a_week_is_given_by_its_monday(client):
    school = calendar_ids(client)["School"]
    response = client.post("/api/todos", json={"week": "2026-11-24", "calendar_id": school, "text": "x"})
    assert response.status_code == 422
    assert "A week is given by its Monday." in response.text
    assert client.get("/api/todos?week=2026-11-25").status_code == 422
    assert client.get("/api/todos").status_code == 422
    assert client.post("/api/todos/carry-over", json={"week": "2026-11-29"}).status_code == 422


def test_text_and_calendar_are_required(client):
    school = calendar_ids(client)["School"]
    assert client.post("/api/todos", json={"week": MONDAY, "calendar_id": school, "text": "   "}).status_code == 422
    assert client.post("/api/todos", json={"week": MONDAY, "calendar_id": school, "text": "x" * 301}).status_code == 422
    response = client.post("/api/todos", json={"week": MONDAY, "calendar_id": 999, "text": "x"})
    assert response.json()["detail"] == "This calendar doesn't exist."


def test_tick_reword_and_reorder(client):
    item = add_todo(client)
    other = add_todo(client, text="Second")
    changed = client.patch(f"/api/todos/{item['id']}", json={"done": True, "text": "Read chapter 5"}).json()
    assert (changed["done"], changed["text"]) == (True, "Read chapter 5")
    assert client.patch(f"/api/todos/{item['id']}", json={"text": ""}).status_code == 422
    client.patch(f"/api/todos/{item['id']}", json={"position": 5})
    assert texts(client, f"week={MONDAY}") == [other["text"], "Read chapter 5"]
    assert client.patch("/api/todos/999", json={"done": True}).status_code == 404


def test_delete(client):
    item = add_todo(client)
    assert client.delete(f"/api/todos/{item['id']}").status_code == 204
    assert client.delete(f"/api/todos/{item['id']}").status_code == 404
    assert texts(client, f"week={MONDAY}") == []


def test_carry_over_moves_what_is_not_done(client):
    add_todo(client, text="Already next week", week=NEXT_MONDAY)
    done = add_todo(client, text="Finished")
    client.patch(f"/api/todos/{done['id']}", json={"done": True})
    add_todo(client, text="Unfinished 1")
    add_todo(client, text="Unfinished 2", calendar="Work")
    response = client.post("/api/todos/carry-over", json={"week": MONDAY})
    assert response.json() == {"moved": 2}
    assert texts(client, f"week={MONDAY}") == ["Finished"]
    assert texts(client, f"week={NEXT_MONDAY}") == ["Already next week", "Unfinished 1", "Unfinished 2"]


def test_carry_over_for_one_calendar(client):
    add_todo(client, text="School thing")
    add_todo(client, text="Work thing", calendar="Work")
    work = calendar_ids(client)["Work"]
    assert client.post("/api/todos/carry-over", json={"week": MONDAY, "calendar_id": work}).json() == {"moved": 1}
    assert texts(client, f"week={MONDAY}") == ["School thing"]
    assert texts(client, f"week={NEXT_MONDAY}") == ["Work thing"]


def test_bring_back_next_weeks_unfinished(client):
    add_todo(client, text="Already this week")
    add_todo(client, text="Next 1", week=NEXT_MONDAY)
    done = add_todo(client, text="Next done", week=NEXT_MONDAY)
    client.patch(f"/api/todos/{done['id']}", json={"done": True})
    add_todo(client, text="Next work", week=NEXT_MONDAY, calendar="Work")
    work = calendar_ids(client)["Work"]
    assert client.post("/api/todos/bring-back", json={"week": MONDAY, "calendar_id": work}).json() == {"moved": 1}
    assert client.post("/api/todos/bring-back", json={"week": MONDAY}).json() == {"moved": 1}
    assert texts(client, f"week={MONDAY}") == ["Already this week", "Next work", "Next 1"]
    assert texts(client, f"week={NEXT_MONDAY}") == ["Next done"]
    assert client.post("/api/todos/bring-back", json={"week": "2026-11-25"}).status_code == 422


def test_list_a_range_of_weeks(client):
    add_todo(client, text="Next", week=NEXT_MONDAY)
    add_todo(client, text="This")
    assert texts(client, f"from={MONDAY}&to={NEXT_MONDAY}") == ["This", "Next"]
    assert texts(client, f"from={NEXT_MONDAY}&to={NEXT_MONDAY}") == ["Next"]
    assert client.get(f"/api/todos?from={MONDAY}").status_code == 422
    assert client.get(f"/api/todos?from={MONDAY}&to=2026-12-01").status_code == 422
