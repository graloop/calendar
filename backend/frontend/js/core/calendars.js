// The calendars (School, Personal, Work...), loaded once and shared by every
// screen, and which one is chosen in the tabs: "all" or a calendar's id. The
// choice is remembered in this browser, so the phone opens on the same tab.

import { api } from "./api.js";
import { t } from "./i18n.js";

const KEY = "ag_calendar";
let calendars = [];
const listeners = [];

export function getCalendars() {
  return calendars;
}

export async function loadCalendars() {
  calendars = await api("/api/calendars");
  for (const listener of listeners) listener();
  return calendars;
}

// `listener` runs whenever the list changes.
export function onCalendarsChange(listener) {
  listeners.push(listener);
}

export function calendarById(id) {
  return calendars.find((c) => c.id === Number(id)) ?? null;
}

// "all", or the id of a calendar that still exists (a removed one falls back to "all").
export function chosenCalendar() {
  let saved = null;
  try {
    saved = localStorage.getItem(KEY);
  } catch (_) {
    // Private browsing: every visit starts on "All".
  }
  return calendarById(saved) ? Number(saved) : "all";
}

export function chooseCalendar(value) {
  try {
    localStorage.setItem(KEY, String(value));
  } catch (_) {
    // Not remembered, but the page still shows it until the next reload.
  }
}

// Added to the end of an /api/events or /api/todos address: "" for all calendars.
export function calendarQuery() {
  const chosen = chosenCalendar();
  return chosen === "all" ? "" : `&calendar=${chosen}`;
}

// Where something new goes: the chosen calendar, or the first one in "All".
export function defaultCalendarId() {
  const chosen = chosenCalendar();
  return chosen === "all" ? (calendars[0]?.id ?? null) : chosen;
}

// "New calendar", or "New calendar 2", 3... when that name is taken.
export function newCalendarName() {
  const taken = new Set(calendars.map((c) => c.name.toLocaleLowerCase()));
  const base = t("New calendar");
  for (let n = 1; ; n++) {
    const name = n === 1 ? base : `${base} ${n}`;
    if (!taken.has(name.toLocaleLowerCase())) return name;
  }
}

// Fills a <select> with the calendars, `selected` chosen.
export function fillCalendarSelect(select, selected) {
  select.replaceChildren(
    ...calendars.map((c) => {
      const option = document.createElement("option");
      option.value = String(c.id);
      option.textContent = c.name;
      option.selected = c.id === Number(selected);
      return option;
    }),
  );
}
