# The import box's parser with messy lines, the way the Claude extension (or a
# person in a hurry) writes them: bullets, markdown tables, French words, 14h30,
# "75 min"... and the mistakes it must catch rather than guess: a wrong weekday,
# an end before the start, a date too far away. "Today" is fixed so the tests
# don't depend on the day they run. Only fake courses (ABC123, XYZ789).

import datetime as dt

import pytest

from app.importing.parser import (
    LineError,
    LineProblem,
    ParsedEvent,
    guess_source_kind,
    parse_course,
    parse_date,
    parse_text,
    parse_time,
    parse_type,
)

TODAY = dt.date(2026, 11, 10)  # a Tuesday


def events(text):
    return [i for i in parse_text(text, TODAY).items if isinstance(i, ParsedEvent)]


def problems(text):
    return [i for i in parse_text(text, TODAY).items if isinstance(i, LineProblem)]


def only_event(text):
    items = parse_text(text, TODAY).items
    assert len(items) == 1 and isinstance(items[0], ParsedEvent), items
    return items[0]


def only_problem(text):
    items = parse_text(text, TODAY).items
    assert len(items) == 1 and isinstance(items[0], LineProblem), items
    return items[0]


# --- Dates ---


@pytest.mark.parametrize(
    "written",
    [
        "2026-11-24",
        "Tue Nov 24",
        "Tue, Nov 24",
        "tuesday november 24",
        "Nov 24",
        "24 nov.",
        "mardi 24 novembre",
        "mar. 24 nov.",
        "Mardi le 24 Novembre 2026",
        "Nov 24th, 2026",
        "Tue 2026-11-24",
        "  TUE   NOV   24  ",
    ],
)
def test_dates_written_many_ways(written):
    assert parse_date(written, TODAY) == dt.date(2026, 11, 24)


def test_french_first_of_the_month_and_accents():
    assert parse_date("mardi 1er décembre", TODAY) == dt.date(2026, 12, 1)
    assert parse_date("3 févr.", TODAY) == dt.date(2027, 2, 3)
    assert parse_date("17 août", TODAY) == dt.date(2026, 8, 17)


def test_mar_is_march_alone_and_tuesday_next_to_a_month():
    assert parse_date("Mar 3", TODAY) == dt.date(2027, 3, 3)
    assert parse_date("mar 3 nov", TODAY) == dt.date(2026, 11, 3)


def test_a_date_without_a_year_takes_the_nearest_one():
    assert parse_date("Jan 12", TODAY) == dt.date(2027, 1, 12)  # two months ahead, not ten back
    assert parse_date("Sep 3", TODAY) == dt.date(2026, 9, 3)  # two months back, not ten ahead
    assert parse_date("May 1", TODAY) == dt.date(2027, 5, 1)
    assert parse_date("May 20", TODAY) == dt.date(2026, 5, 20)


def test_a_wrong_weekday_is_an_error_not_a_guess():
    with pytest.raises(LineError) as caught:
        parse_date("Mon Nov 24", TODAY)
    assert str(caught.value) == "2026-11-24 is a Tuesday, not a Monday. Check the date or the weekday."
    with pytest.raises(LineError):
        parse_date("lundi 2026-11-24", TODAY)


@pytest.mark.parametrize(
    "written, starts",
    [
        ("Nov", "'Nov' has no day of the month."),
        ("24", "'24' has no month."),
        ("24/11/2026", "'24/11/2026' isn't a date I can read."),
        ("next tuesday", "'next tuesday' isn't a date I can read."),
        ("Feb 30", "'Feb 30' isn't a real date."),
        ("2026-02-30", "'2026-02-30' isn't a real date."),
        ("", "The date is empty."),
        ("Nov 24 Dec", "'Nov 24 Dec' isn't a date I can read."),
    ],
)
def test_unreadable_dates_say_how_to_write_them(written, starts):
    with pytest.raises(LineError) as caught:
        parse_date(written, TODAY)
    assert str(caught.value).startswith(starts)


def test_more_than_a_year_away_is_an_error_both_ways():
    assert parse_date("2027-11-10", TODAY) == dt.date(2027, 11, 10)
    for far in ("2027-11-11", "2025-11-09", "Nov 24, 2028"):
        with pytest.raises(LineError, match="more than a year from today"):
            parse_date(far, TODAY)


# --- Times ---


@pytest.mark.parametrize(
    "written, start, end",
    [
        ("13:30-15:20", "13:30", "15:20"),
        ("13:30 - 15:20", "13:30", "15:20"),
        ("13:30–15:20", "13:30", "15:20"),
        ("13h30 à 15h20", "13:30", "15:20"),
        ("de 13h30 à 15h20", "13:30", "15:20"),
        ("13h-15h", "13:00", "15:00"),
        ("1:30 pm to 3:20 pm", "13:30", "15:20"),
        ("9am-11am", "09:00", "11:00"),
        ("13:30 75 min", "13:30", "14:45"),
        ("13:30 (75 min)", "13:30", "14:45"),
        ("13:30, 1h15", "13:30", "14:45"),
        ("14h30 pendant 2 h", "14:30", "16:30"),
        ("8:30 for 1.5 hours", "08:30", "10:00"),
        ("14h30", "14:30", None),
        ("9:05", "09:05", None),
    ],
)
def test_times_written_many_ways(written, start, end):
    got = parse_time(written, "class")
    assert tuple(t.strftime("%H:%M") if t else None for t in got) == (start, end)


@pytest.mark.parametrize("written", ["all day", "All Day", "toute la journée", "Toute la journee", "", "-"])
def test_all_day(written):
    assert parse_time(written, "exam") == (None, None)


def test_a_deadline_has_only_a_due_time():
    assert parse_time("23:59", "deadline") == (dt.time(23, 59), None)
    with pytest.raises(LineError, match="A deadline has only a due time"):
        parse_time("13:00-23:59", "deadline")
    with pytest.raises(LineError, match="A deadline has only a due time"):
        parse_time("13:00 30 min", "deadline")


def test_an_end_before_the_start_is_an_error():
    with pytest.raises(LineError) as caught:
        parse_time("15:20-13:30", "lab")
    assert str(caught.value) == "The end (13:30) isn't after the start (15:20). Write it like 13:30-15:20."
    with pytest.raises(LineError, match="isn't after the start"):
        parse_time("13:30-13:30", "lab")


def test_past_midnight_is_an_error():
    with pytest.raises(LineError, match="goes past midnight"):
        parse_time("23:00 90 min", "work")


@pytest.mark.parametrize("written", ["14", "25:00", "13:75", "soon", "13:30 75", "13:30 then 15:00", "13pm"])
def test_unreadable_times(written):
    with pytest.raises(LineError, match="isn't a time I can read"):
        parse_time(written, "class")


# --- Types and courses ---


@pytest.mark.parametrize(
    "written, key",
    [
        ("lab", "lab"),
        ("Labo", "lab"),
        ("laboratoire", "lab"),
        ("cours", "class"),
        ("Class", "class"),
        ("examen", "exam"),
        ("Examens", "exam"),
        ("intra", "exam"),
        ("remise", "deadline"),
        ("Devoir", "deadline"),
        ("due", "deadline"),
        ("réunion", "meeting"),
        ("Rencontre", "meeting"),
        ("travail", "work"),
        ("personnel", "personal"),
        ("autre", "other"),
        (" LAB. ", "lab"),
    ],
)
def test_type_words_english_and_french(written, key):
    assert parse_type(written) == key


def test_an_unknown_type_lists_the_types():
    with pytest.raises(LineError, match="Use one of: class, lab, exam, deadline"):
        parse_type("party")


def test_course_codes():
    assert parse_course("ABC123") == "ABC123"
    assert parse_course(" abc 123 ") == "ABC123"
    assert parse_course("xyz789") == "XYZ789"
    for none in ("-", "", "none", "aucun"):
        assert parse_course(none) is None
    for wrong in ("ABC123 - Intro to things", "ABC123 Intro", "AB C", "!!"):
        with pytest.raises(LineError, match="isn't a course code"):
            parse_course(wrong)


def test_source_kinds():
    assert guess_source_kind("https://moodle.example.org/mod/assign/view.php?id=4") == "moodle"
    assert guess_source_kind("Email: Exam room, 2026-11-20") == "email"
    assert guess_source_kind("courriel : Local de l'examen, 20 nov.") == "email"
    assert guess_source_kind("https://example.org/syllabus") == "other"
    assert guess_source_kind(None) is None


# --- Whole lines and the whole box ---


def test_a_plain_line():
    e = only_event(
        "Tue Nov 24 | 23:59 | deadline | ABC123 | Lab report 3 | Upload the PDF | https://moodle.example.org/a/1"
    )
    assert (e.date, e.start_time, e.end_time) == (dt.date(2026, 11, 24), dt.time(23, 59), None)
    assert (e.type, e.course, e.title) == ("deadline", "ABC123", "Lab report 3")
    assert e.details == "Upload the PDF"
    assert e.source_link == "https://moodle.example.org/a/1"
    assert e.series is False
    assert e.line == 1


def test_details_and_source_are_optional():
    e = only_event("2026-11-24 | all day | personal | - | Day off")
    assert e.course is None and e.details is None and e.source_link is None
    assert e.start_time is None


def test_bullets_numbers_bold_and_extra_spaces():
    text = """
    - Tue Nov 24  |  13:30-15:20 | lab |  ABC123 |   Lab   3  |
    * 2026-11-25 | 9:00 | exam | XYZ789 | **Midterm** |
    • 2026-11-26 | all day | other | - | `Something` |
    1. 2026-11-27 | 23:59 | deadline | ABC123 | Report |
    2) 2026-11-28 | all day | personal | - | Rest |
    """
    got = events(text)
    assert [e.title for e in got] == ["Lab 3", "Midterm", "Something", "Report", "Rest"]
    assert not problems(text)


def test_a_markdown_table():
    text = """
| Date | Time | Type | Course | Title | Details | Source |
|------|------|------|--------|-------|---------|--------|
| Tue Nov 24 | 13:30-15:20 | lab | ABC123 | Lab 3 | room: D7-2018 | https://moodle.example.org/c/1 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Wed Nov 25 | 23:59 | remise | ABC123 | Rapport |  |  |
"""
    got = events(text)
    assert [(e.date.day, e.title) for e in got] == [(24, "Lab 3"), (25, "Rapport")]
    assert got[0].location == "D7-2018"
    assert parse_text(text, TODAY).line_count == 2


def test_a_whole_line_in_french():
    e = only_event(
        "mercredi 25 novembre | 14h30 à 16h20 | labo | abc 123 | Laboratoire 4 | salle : D7-2018; apporter le sarrau"
    )
    assert e.date == dt.date(2026, 11, 25)
    assert (e.start_time, e.end_time) == (dt.time(14, 30), dt.time(16, 20))
    assert (e.type, e.course) == ("lab", "ABC123")
    assert e.location == "D7-2018"
    assert e.details == "apporter le sarrau"


def test_blank_lines_comments_fences_and_headers_are_skipped():
    text = "\n\n# Fall term\n```\nDate | Time | Type | Course | Title\n2026-11-24 | all day | other | - | X\n```\n"
    result = parse_text(text, TODAY)
    assert [i.title for i in result.items] == ["X"]
    assert result.line_count == 1


def test_one_clear_error_per_line_and_the_others_still_read():
    text = """2026-11-24 | 13:30-15:20 | lab | ABC123 | Lab 3
Mon Nov 24 | 13:30-15:20 | lab | ABC123 | Wrong weekday
2026-11-25 | 15:20-13:30 | lab | ABC123 | Backwards
2028-11-25 | 10:00 | exam | ABC123 | Too far
Here are your events:
2026-11-26 | 10:00 | exam
2026-11-26 | 10:00 | party | ABC123 | Unknown type
2026-11-26 | 10:00 | exam | ABC123 |   | room: D7-2018
2026-11-27 | 10:00 | exam | XYZ789 | Final"""
    items = parse_text(text, TODAY).items
    assert [type(i).__name__ for i in items] == ["ParsedEvent"] + ["LineProblem"] * 7 + ["ParsedEvent"]
    messages = [i.message for i in items if isinstance(i, LineProblem)]
    assert messages[0] == "2026-11-24 is a Tuesday, not a Monday. Check the date or the weekday."
    assert "isn't after the start" in messages[1]
    assert "more than a year from today" in messages[2]
    assert messages[3].startswith("There's no | between the fields.")
    assert messages[4].startswith("Only 3 fields.")
    assert "isn't a type" in messages[5]
    assert messages[6].startswith("The title is empty.")
    # The line number and the line as written, to show next to the message.
    assert (items[1].line, items[1].text) == (2, "Mon Nov 24 | 13:30-15:20 | lab | ABC123 | Wrong weekday")


def test_problem_templates_keep_the_values_apart_for_translation():
    problem = only_problem("Mon Nov 24 | 10:00 | exam | ABC123 | X")
    assert problem.template == "{date} is a {weekday}, not a {written}. Check the date or the weekday."
    assert problem.params == {"date": "2026-11-24", "weekday": "Tuesday", "written": "Monday"}


def test_a_markdown_link_as_source_keeps_the_address():
    e = only_event("2026-11-24 | 23:59 | deadline | ABC123 | TP | | [Moodle](https://moodle.example.org/a/2)")
    assert e.source_link == "https://moodle.example.org/a/2"
    e = only_event("2026-11-24 | 23:59 | deadline | ABC123 | TP | | <https://moodle.example.org/a/3>")
    assert e.source_link == "https://moodle.example.org/a/3"


def test_a_pipe_inside_the_source_stays_in_it():
    e = only_event("2026-11-24 | 23:59 | deadline | ABC123 | TP | | Email: A | B, 2026-11-01")
    assert e.source_link == "Email: A | B, 2026-11-01"


# --- Weekly series ---


def test_weekly_until_makes_one_event_per_week():
    got = events("Tue Nov 10 | 13:30-15:20 | class | ABC123 | Lecture | weekly until 2026-12-08; room: D3-2030")
    assert [e.date.isoformat() for e in got] == ["2026-11-10", "2026-11-17", "2026-11-24", "2026-12-01", "2026-12-08"]
    assert all(e.series and e.location == "D3-2030" and e.details is None for e in got)
    assert {e.line for e in got} == {1}


def test_except_skips_weeks_and_may_repeat():
    line = (
        "2026-09-08 | 13:30 75 min | cours | XYZ789 | Théorie | "
        "weekly until 2026-10-27 except 2026-10-13 except 2026-10-20; bring the book"
    )
    got = events(line)
    assert [e.date.day for e in got] == [8, 15, 22, 29, 6, 27]
    assert got[0].end_time == dt.time(14, 45)
    assert got[0].details == "bring the book"


def test_except_with_a_list_and_in_french():
    got = events(
        "2026-09-08 | 13:30-15:20 | cours | XYZ789 | Cours | chaque semaine jusqu'au 2026-10-06 sauf 2026-09-15, 2026-09-22"
    )
    assert [e.date.day for e in got] == [8, 29, 6]


def test_series_mistakes_are_errors():
    cases = {
        "weekly until 2026-11-01": "weekly until 2026-11-01 is before the first date (2026-11-10).",
        "weekly until Dec 12": "Write the end of the series like weekly until 2026-12-12",
        "weekly until 2026-12-08 except 2026-11-18": "except 2026-11-18 isn't one of this series' days (every Tuesday",
        "except 2026-11-17": "except 2026-11-17 only works with weekly until on the same line.",
        "weekly until 2027-12-01": "2027-12-01 is more than a year from today.",
    }
    for details, message in cases.items():
        problem = only_problem(f"2026-11-10 | 13:30-15:20 | class | ABC123 | Lecture | {details}")
        assert problem.message.startswith(message), (details, problem.message)


def test_except_in_plain_words_is_just_details():
    e = only_event("2026-11-24 | 23:59 | deadline | ABC123 | TP | everything except the appendix")
    assert e.details == "everything except the appendix"
