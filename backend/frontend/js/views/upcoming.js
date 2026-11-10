// Upcoming: the next 14 days as a list, grouped by day, deadlines first with a
// "done" box, then the deadlines that slipped by without being ticked.
// The screen to open on the phone. This week's list sits above the days.

import { api, json } from "../core/api.js";
import { calendarQuery } from "../core/calendars.js";
import { addDays, formatDay, mondayOf, todayISO } from "../core/dates.js";
import { byDay, eventLink, sortDay } from "../core/events.js";
import { t } from "../core/i18n.js";
import { el, hideStatus, showStatus, showView } from "../core/ui.js";
import { showWeekList } from "./week-list.js";

const DAYS = 14;
const list = document.getElementById("upcoming-list");
const status = document.getElementById("upcoming-status");

function dayHeading(iso, today) {
  if (iso === today) return t("Today");
  if (iso === addDays(today, 1)) return t("Tomorrow");
  return formatDay(iso, { weekday: "long", month: "long" });
}

// A deadline gets a box to tick; other events a blank of the same width, so titles line up.
function doneBox(event, link) {
  if (event.type !== "deadline") return el("span", { class: "done-check", "aria-hidden": "true" });
  const box = el("input", {
    type: "checkbox",
    "aria-label": t("Done: {title}", { title: event.title }),
  });
  box.checked = event.done;
  box.addEventListener("change", async () => {
    try {
      await api(`/api/events/${event.id}`, json("PATCH", { done: box.checked }));
      link.classList.toggle("is-done", box.checked);
    } catch (err) {
      box.checked = !box.checked;
      showStatus(status, err.message, true);
    }
  });
  return el("label", { class: "done-check" }, box);
}

function group(heading, events, { showDate = false, className = "day-group" } = {}) {
  const rows = events.map((event) => {
    const link = eventLink(event, { showDate });
    return el("li", { class: "event-row" }, doneBox(event, link), link);
  });
  return el("section", { class: className }, el("h3", {}, heading), el("ul", { class: "event-rows" }, ...rows));
}

export async function showUpcoming() {
  showView("upcoming");
  document.title = `${t("Upcoming")} · Agenda`;
  const today = todayISO();
  showWeekList(document.getElementById("upcoming-week-list"), mondayOf(today));
  showStatus(status, t("Loading..."));
  const only = calendarQuery(); // "" in "All", "&calendar=2" otherwise
  const [events, overdue] = await Promise.all([
    api(`/api/events?from=${today}&to=${addDays(today, DAYS - 1)}${only}`),
    api(`/api/events?type=deadline&done=false&to=${addDays(today, -1)}${only}`),
  ]);
  hideStatus(status);
  const days = byDay(events);
  const groups = Object.keys(days)
    .sort()
    .map((iso) => group(dayHeading(iso, today), sortDay(days[iso])));
  if (overdue.length) {
    groups.push(group(t("Overdue"), overdue, { showDate: true, className: "day-group overdue" }));
  }
  if (!events.length) showStatus(status, t("Nothing in the next 14 days."));
  list.replaceChildren(...groups);
}
