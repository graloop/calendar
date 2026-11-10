// The event screen (/event/5, or /event/new?date=2026-11-24): add an event by
// hand, or change, move (change its date) or delete one. Deleting takes two
// clicks, never a browser pop-up.

import { api, json } from "../core/api.js";
import { getCourses, loadCourses, onCoursesChange } from "../core/courses.js";
import { formatDay, isValidDay, todayISO } from "../core/dates.js";
import { t } from "../core/i18n.js";
import { go } from "../core/router.js";
import { fillTypeSelect } from "../core/types.js";
import { el, hideStatus, showStatus, showView, twoClickButton } from "../core/ui.js";

const form = document.getElementById("event-form");
const status = document.getElementById("event-status");
const field = (name) => document.getElementById(`field-${name}`);
const deleteBtn = document.getElementById("event-delete");
const deleteSeriesBtn = document.getElementById("event-delete-series");

let current = null; // the event being changed; null for a new one
let returnTo = "/upcoming"; // where Save, Delete and Back go: the screen it was opened from

fillTypeSelect(field("type"));

function fillCourseCodes() {
  document
    .getElementById("course-codes")
    .replaceChildren(...getCourses().map((c) => el("option", { value: c.code }, c.name ?? c.code)));
}
onCoursesChange(fillCourseCodes);

// A deadline has a due time and no end, and a "done" box.
function showTypeFields() {
  const deadline = field("type").value === "deadline";
  document.getElementById("end-box").classList.toggle("hidden", deadline);
  document.getElementById("done-box").classList.toggle("hidden", !deadline);
  document.getElementById("label-start").textContent = deadline ? t("Due time") : t("Start time");
  document.getElementById("time-hint").textContent = deadline
    ? t("A deadline has a due time, like 23:59. Leave it empty if it's due some time that day.")
    : t("Leave the times empty for an all-day event.");
}
field("type").addEventListener("change", showTypeFields);

export function setReturnTo(path) {
  returnTo = path;
}

function fill(event) {
  field("title").value = event.title ?? "";
  field("type").value = event.type ?? "other";
  field("course").value = event.course_code ?? "";
  field("date").value = event.date ?? "";
  field("start").value = event.start_time ?? "";
  field("end").value = event.end_time ?? "";
  field("done").checked = Boolean(event.done);
  field("location").value = event.location ?? "";
  field("details").value = event.details ?? "";
  field("source").value = event.source_link ?? "";
  showTypeFields();
}

// `id` is null for a new event, on `date` (today if none or not a real day).
export async function showEvent(id, date = null) {
  showView("event");
  hideStatus(status);
  document.getElementById("event-back").href = returnTo;
  current = id ? await api(`/api/events/${id}`) : null;
  const heading = current ? t("Edit event") : t("New event");
  document.getElementById("event-heading").textContent = heading;
  document.title = `${current ? current.title : heading} · Agenda`;
  fill(current ?? { date: date && isValidDay(date) ? date : todayISO() });

  deleteBtn.classList.toggle("hidden", !current);
  deleteSeriesBtn.classList.toggle("hidden", !current?.series_id);
  document.getElementById("event-series").classList.toggle("hidden", !current?.series_id);
  if (current) {
    twoClickButton(deleteBtn, {
      label: t("Delete"),
      confirmLabel: t("Click again to delete"),
      onConfirm: () => remove(false),
    });
    twoClickButton(deleteSeriesBtn, {
      label: t("Delete the whole series"),
      confirmLabel: t("Click again to delete every event of the series"),
      onConfirm: () => remove(true),
    });
  }
  field("title").focus();
}

async function remove(series) {
  try {
    await api(`/api/events/${current.id}${series ? "?series=1" : ""}`, { method: "DELETE" });
    await loadCourses(); // Their event counts changed.
    go(returnTo);
  } catch (err) {
    showStatus(status, err.message, true);
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideStatus(status);
  const title = field("title").value.trim();
  const date = field("date").value;
  if (!title) return showStatus(status, t("Give the event a title."), true);
  if (!isValidDay(date)) return showStatus(status, t("Choose a date."), true);
  const deadline = field("type").value === "deadline";
  const body = {
    title,
    type: field("type").value,
    course: field("course").value,
    date,
    start_time: field("start").value || null,
    end_time: deadline ? null : field("end").value || null,
    done: deadline && field("done").checked,
    location: field("location").value,
    details: field("details").value,
    source_link: field("source").value,
  };
  try {
    const saved = current
      ? await api(`/api/events/${current.id}`, json("PATCH", body))
      : await api("/api/events", json("POST", body));
    await loadCourses(); // A new course code makes a new course.
    go(returnTo);
    showStatus(
      document.getElementById("app-error"),
      t("Saved: {title}, {date}", { title: saved.title, date: formatDay(saved.date) }),
    );
  } catch (err) {
    showStatus(status, err.message, true);
  }
});
