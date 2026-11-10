// Calendar days, written "2026-11-24" everywhere (as the server stores them).
// new Date("2026-11-24") would read it as UTC midnight, which is still the 23rd
// in Montreal, so a day is always built from its parts instead.

import { locale, t } from "./i18n.js";

export function parseDay(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function toISO(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function todayISO() {
  return toISO(new Date());
}

// A real day? (2026-02-30 isn't: the Date would roll over to March.)
export function isValidDay(iso) {
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) && toISO(parseDay(iso)) === iso;
}

export function addDays(iso, n) {
  const date = parseDay(iso);
  date.setDate(date.getDate() + n);
  return toISO(date);
}

// Weeks start on Monday.
export function mondayOf(iso) {
  const shift = (parseDay(iso).getDay() + 6) % 7;
  return addDays(iso, -shift);
}

// "2026-11" months.
export function monthOf(iso) {
  return iso.slice(0, 7);
}

export function addMonths(month, n) {
  const [year, m] = month.split("-").map(Number);
  return toISO(new Date(year, m - 1 + n, 1)).slice(0, 7);
}

// "Tue, Nov 24" ("mar. 24 nov." in French); with year: "Tue, Nov 24, 2026".
export function formatDay(iso, { year = false, weekday = "short", month = "short" } = {}) {
  return parseDay(iso).toLocaleDateString(locale(), {
    weekday,
    month,
    day: "numeric",
    year: year ? "numeric" : undefined,
  });
}

// "November 2026" ("novembre 2026").
export function formatMonth(month) {
  return parseDay(`${month}-01`).toLocaleDateString(locale(), { month: "long", year: "numeric" });
}

// "Mon".."Sun" in the page's language, for the month grid's header.
export function weekdayNames() {
  const monday = "2026-11-23";
  return [0, 1, 2, 3, 4, 5, 6].map((i) =>
    parseDay(addDays(monday, i)).toLocaleDateString(locale(), { weekday: "short" }),
  );
}

// When an event happens, in words: "13:30–15:20", "Due 23:59", "All day".
export function formatWhen(event) {
  if (!event.start_time) return t("All day");
  if (event.type === "deadline") return t("Due {time}", { time: event.start_time });
  if (!event.end_time) return event.start_time;
  return `${event.start_time}–${event.end_time}`;
}
