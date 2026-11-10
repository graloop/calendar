// Month: the whole month in weeks starting on Monday, with the days of the
// months around it greyed out to fill the first and last weeks.

import { api } from "../core/api.js";
import { addDays, addMonths, formatMonth, mondayOf, monthOf, todayISO, weekdayNames } from "../core/dates.js";
import { byDay } from "../core/events.js";
import { t } from "../core/i18n.js";
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
  const days = byDay(await api(`/api/events?from=${start}&to=${end}`));
  hideStatus(status);
  const cells = weekdayNames().map((name) => el("div", { class: "grid-head", "aria-hidden": "true" }, name));
  for (let iso = start; iso <= end; iso = addDays(iso, 1)) {
    const extraClass = monthOf(iso) === month ? "" : "other-month";
    cells.push(dayCell(iso, days[iso] ?? [], { today, extraClass }));
  }
  grid.replaceChildren(...cells);
}
