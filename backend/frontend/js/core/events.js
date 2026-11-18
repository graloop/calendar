// How an event is drawn, the same on every screen: a real link to its page,
// whose text says everything about it (date, time, type, course, title), so the
// Claude extension and screen readers can read it without opening it.
// In "All" calendars, the link also says which calendar the event is on.
// A deadline also gets a box to tick it done right there (doneCheckbox).

import { api, json } from "./api.js";
import { chosenCalendar } from "./calendars.js";
import { formatDay, formatWhen } from "./dates.js";
import { t } from "./i18n.js";
import { typeBadge, typeLabel } from "./types.js";
import { el, showStatus } from "./ui.js";

// Deadlines first in a day (the thing to not forget), then all-day events,
// then by start time.
export function sortDay(events) {
  const rank = (e) => (e.type === "deadline" ? 0 : e.start_time ? 2 : 1);
  return [...events].sort((a, b) => rank(a) - rank(b) || (a.start_time ?? "").localeCompare(b.start_time ?? ""));
}

// { "2026-11-24": [events...] }
export function byDay(events) {
  const days = {};
  for (const event of events) (days[event.date] ??= []).push(event);
  return days;
}

// `showDate`: write the date on the link too (otherwise it's still in the
// link's text, just not drawn, because the day's heading already shows it).
// `compact`: the smaller version for the week and month grids.
export function eventLink(event, { showDate = false, compact = false } = {}) {
  const date = formatDay(event.date, { year: true });
  const parts = [
    el("span", { class: showDate ? "ev-date" : "ev-date visually-hidden" }, `${date},`),
    el("span", { class: "ev-time" }, formatWhen(event)),
    typeBadge(event.type),
    event.course_code ? el("span", { class: "ev-course" }, event.course_code) : null,
    el("span", { class: "ev-title" }, event.title),
    event.location && !compact ? el("span", { class: "ev-where" }, `· ${event.location}`) : null,
    event.done ? el("span", { class: "visually-hidden" }, `(${t("done")})`) : null,
    event.calendar_name && chosenCalendar() === "all" ? el("span", { class: "cal-tag" }, event.calendar_name) : null,
  ].filter(Boolean);
  // Spaces between the parts, so the link's text reads as words, not "13:30Lab ABC123".
  const children = parts.flatMap((part, i) => (i ? [" ", part] : [part]));
  const link = el(
    "a",
    {
      class: `event-link${compact ? " compact" : ""}${event.done ? " is-done" : ""}`,
      href: `/event/${event.id}`,
      title: compact ? `${formatWhen(event)} · ${typeLabel(event.type)} · ${event.title}` : null,
    },
    ...children,
  );
  if (event.course_color) link.style.setProperty("--course", event.course_color);
  return link;
}

// The box that ticks a deadline done without opening it (Upcoming and the
// Week and Month grids). The link's look follows at once; if the server
// refuses, the box goes back and `status` says why.
export function doneCheckbox(event, link, status) {
  const box = el("input", { type: "checkbox", "aria-label": t("Done: {title}", { title: event.title }) });
  box.checked = event.done;
  box.addEventListener("change", async () => {
    link.classList.toggle("is-done", box.checked);
    try {
      await api(`/api/events/${event.id}`, json("PATCH", { done: box.checked }));
      event.done = box.checked;
    } catch (err) {
      box.checked = !box.checked;
      link.classList.toggle("is-done", box.checked);
      if (status) showStatus(status, err.message, true);
    }
  });
  return box;
}

// In the grids: the event's link, and for a deadline its box in the bottom-right corner.
export function gridEvent(event, status) {
  const link = eventLink(event, { compact: true });
  if (event.type !== "deadline") return link;
  return el(
    "div",
    { class: "grid-event has-done" },
    link,
    el("label", { class: "grid-done" }, doneCheckbox(event, link, status)),
  );
}

// The "+" in a day's corner. Its label says the day in words and as a date.
export function addButton(iso) {
  const label = t("Add an event on {date} ({iso})", { date: formatDay(iso, { year: true }), iso });
  return el("a", { class: "btn add-btn", href: `/event/new?date=${iso}`, "aria-label": label, title: label });
}
