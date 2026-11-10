// Week: seven days, Monday to Sunday, side by side (one under the other on a
// phone). Each day lists its events and has a "+" to add one. The week's
// to-do list is above the grid.

import { api } from "../core/api.js";
import { calendarQuery } from "../core/calendars.js";
import { addDays, formatDay, mondayOf, todayISO } from "../core/dates.js";
import { addButton, byDay, eventLink, sortDay } from "../core/events.js";
import { t } from "../core/i18n.js";
import { el, hideStatus, showStatus, showView } from "../core/ui.js";
import { showWeekList } from "./week-list.js";

const grid = document.getElementById("week-grid");
const status = document.getElementById("week-status");

// One day's box: its date, its events, and the "+". Also used by the month grid.
export function dayCell(iso, events, { today, extraClass = "" } = {}) {
  const classes = ["day-cell", extraClass, iso === today ? "today" : ""].filter(Boolean).join(" ");
  return el(
    "div",
    { class: classes },
    el("div", { class: "day-date" }, formatDay(iso)),
    el("div", { class: "events" }, ...sortDay(events).map((event) => eventLink(event, { compact: true }))),
    addButton(iso),
  );
}

export async function showWeek(day) {
  const monday = mondayOf(day);
  const sunday = addDays(monday, 6);
  const today = todayISO();
  showView("week");
  const title = t("Week of {date}", { date: formatDay(monday, { year: true, weekday: "long", month: "long" }) });
  document.getElementById("week-title").textContent = title;
  document.title = `${title} · Agenda`;
  document.getElementById("week-earlier").href = `/week/${addDays(monday, -7)}`;
  document.getElementById("week-later").href = `/week/${addDays(monday, 7)}`;
  document.getElementById("week-today").href = `/week/${mondayOf(today)}`;
  document.getElementById("tab-week").href = `/week/${monday}`; // The tab comes back to this week.

  showWeekList(document.getElementById("week-week-list"), monday);
  showStatus(status, t("Loading..."));
  const days = byDay(await api(`/api/events?from=${monday}&to=${sunday}${calendarQuery()}`));
  hideStatus(status);
  const cells = [0, 1, 2, 3, 4, 5, 6]
    .map((i) => addDays(monday, i))
    .map((iso) => dayCell(iso, days[iso] ?? [], { today }));
  grid.replaceChildren(...cells);
}
