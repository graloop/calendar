// The calendars (School, Personal, Work...), loaded once and shared by every
// screen, and which one is chosen in the tabs: "all" or a calendar's id. The
// choice is remembered in this browser, so the phone opens on the same tab.

import { api } from "./api.js";
import { isSingular, t } from "./i18n.js";

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

// The screens load every calendar's events and to-dos once, then keep only
// the chosen tab's here, in the browser: switching tabs needs no request.
export function onlyChosen(items) {
  const chosen = chosenCalendar();
  return chosen === "all" ? items : items.filter((item) => item.calendar_id === chosen);
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

// "3 events", "3 events and 1 to-do", "1 to-do": what removing a calendar takes away.
export function whatGoes(calendar) {
  const parts = [];
  const events = calendar.event_count;
  const todos = calendar.todo_total;
  if (events) parts.push(isSingular(events) ? t("{n} event", { n: events }) : t("{n} events", { n: events }));
  if (todos) parts.push(isSingular(todos) ? t("{n} to-do", { n: todos }) : t("{n} to-dos", { n: todos }));
  return parts.length === 2 ? t("{a} and {b}", { a: parts[0], b: parts[1] }) : (parts[0] ?? "");
}
