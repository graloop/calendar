// Month: the whole month in weeks starting on Monday, with the days of the
// months around it greyed out to fill the first and last weeks. At the end of
// each week, a small "To do" box shows that week's list: tick items there, or
// bring up what's planned for the week after.

import { api, getOnce, json } from "../core/api.js";
import { chosenCalendar, onlyChosen } from "../core/calendars.js";
import {
  addDays,
  addMonths,
  formatDay,
  formatMonth,
  mondayOf,
  monthOf,
  todayISO,
  weekdayNames,
} from "../core/dates.js";
import { byDay } from "../core/events.js";
import { t } from "../core/i18n.js";
import { screenNumber } from "../core/router.js";
import { el, hideStatus, showStatus, showView } from "../core/ui.js";
import { dayCell } from "./week.js";

const grid = document.getElementById("month-grid");
const status = document.getElementById("month-status");

export async function showMonth(month) {
  const today = todayISO();
  const first = `${month}-01`;
  const last = addDays(`${addMonths(month, 1)}-01`, -1);
  const start = mondayOf(first);
  const end = addDays(mondayOf(last), 6);
  showView("month");
  const title = formatMonth(month);
  document.getElementById("month-title").textContent = title;
  document.title = `${title} · Agenda`;
  document.getElementById("month-earlier").href = `/month/${addMonths(month, -1)}`;
  document.getElementById("month-later").href = `/month/${addMonths(month, 1)}`;
  document.getElementById("month-today").href = `/month/${monthOf(today)}`;
  document.getElementById("tab-month").href = `/month/${month}`;

  showStatus(status, t("Loading..."));
  const asked = screenNumber();
  let events, todos;
  try {
    // The to-dos go one week past the grid, to know if the last week can bring any up.
    [events, todos] = await Promise.all([
      getOnce(`/api/events?from=${start}&to=${end}`),
      getOnce(`/api/todos?from=${start}&to=${addDays(end, 1)}`),
    ]);
    events = onlyChosen(events);
    todos = onlyChosen(todos);
  } finally {
    hideStatus(status);
  }
  if (asked !== screenNumber()) return; // Another screen was asked for meanwhile.
  const days = byDay(events);
  const weeks = {}; // "2026-11-23" -> that week's to-dos
  for (const item of todos) (weeks[item.week] ??= []).push(item);
  const cells = weekdayNames().map((name) => el("div", { class: "grid-head", "aria-hidden": "true" }, name));
  cells.push(el("div", { class: "grid-head", "aria-hidden": "true" }, t("To do")));
  for (let iso = start; iso <= end; iso = addDays(iso, 1)) {
    const extraClass = monthOf(iso) === month ? "" : "other-month";
    cells.push(dayCell(iso, days[iso] ?? [], { today, extraClass }));
    const monday = mondayOf(iso);
    if (iso === addDays(monday, 6)) {
      // A Sunday: the week's to-do box closes the row.
      const nextWeek = (weeks[addDays(monday, 7)] ?? []).filter((item) => !item.done);
      // Only this week and later can bring things up: not back into a week that's over.
      const canBring = iso >= today ? nextWeek.length : 0;
      cells.push(todoCell(month, monday, weeks[monday] ?? [], canBring));
    }
  }
  grid.replaceChildren(...cells);
}

// One week's to-do box: a tick box per item, a link to the full list in Week,
// and "Bring up next week's" when the following week has things not done.
function todoCell(month, monday, items, nextCount) {
  const when = formatDay(monday, { year: true });
  const rows = items.map((item) => {
    const box = el("input", { type: "checkbox", "aria-label": t("Done: {text}", { text: item.text }) });
    box.checked = item.done;
    box.addEventListener("change", async () => {
      try {
        await api(`/api/todos/${item.id}`, json("PATCH", { done: box.checked }));
      } catch (err) {
        box.checked = !box.checked;
        return showStatus(status, err.message, true);
      }
      showMonth(month); // Redraw, so the counts and "bring up" stay right.
    });
    return el(
      "li",
      { class: `month-todo${item.done ? " is-done" : ""}` },
      el("label", {}, box, el("span", {}, item.text)),
    );
  });
  const parts = [
    el(
      "a",
      { class: "month-todo-head", href: `/week/${monday}`, "aria-label": t("To do, week of {date}", { date: when }) },
      t("To do"),
    ),
    rows.length ? el("ul", { class: "month-todos" }, ...rows) : el("p", { class: "status" }, t("Nothing yet.")),
  ];
  if (nextCount) {
    const bring = el(
      "button",
      {
        type: "button",
        class: "btn-ghost month-bring",
        "aria-label": t("Bring next week's {n} unfinished to the week of {date}", { n: nextCount, date: when }),
      },
      t("↑ Next week's ({n})", { n: nextCount }),
    );
    bring.addEventListener("click", async () => {
      const chosen = chosenCalendar();
      try {
        await api(
          "/api/todos/bring-back",
          json("POST", { week: monday, calendar_id: chosen === "all" ? null : chosen }),
        );
      } catch (err) {
        return showStatus(status, err.message, true);
      }
      showMonth(month);
    });
    parts.push(bring);
  }
  return el("section", { class: "todo-cell", "aria-label": t("To do, week of {date}", { date: when }) }, ...parts);
}
