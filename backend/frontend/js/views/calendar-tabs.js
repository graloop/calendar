// The row of calendar tabs under the top bar: "All", then each calendar, then
// "+ New calendar". Choosing one shows the current screen again with only that
// calendar's events. The chosen tab has a small pencil to rename it in place
// (Enter or leaving the box saves, Escape puts the old name back) and a small
// bin to remove it, in two clicks: the second says what goes with it.

import { api, json } from "../core/api.js";
import {
  calendarById,
  chooseCalendar,
  chosenCalendar,
  getCalendars,
  loadCalendars,
  newCalendarName,
  onCalendarsChange,
  whatGoes,
} from "../core/calendars.js";
import { t } from "../core/i18n.js";
import { route } from "../core/router.js";
import { el, hideStatus, showStatus } from "../core/ui.js";

const bar = document.getElementById("calendar-tabs");
const status = document.getElementById("calendar-status");

let renaming = null; // the id of the calendar whose name is being typed

// A small icon drawn as lines like the event type icons: a pencil or a bin.
const ICONS = {
  pencil: "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
  bin: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6",
};

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  for (const [name, value] of Object.entries({
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
  })) {
    svg.setAttribute(name, value);
  }
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICONS[name]);
  svg.append(path);
  return svg;
}

function tabButton(value, label) {
  const button = el(
    "button",
    {
      type: "button",
      class: "cal-tab",
      "aria-pressed": String(chosenCalendar() === value),
      "data-focus": `tab-${value}`,
    },
    label,
  );
  button.addEventListener("click", () => choose(value));
  return button;
}

function renameBox(calendar) {
  const input = el("input", {
    type: "text",
    class: "cal-name-input",
    maxlength: "40",
    value: calendar.name,
    "aria-label": t("Name of the calendar {name}", { name: calendar.name }),
  });
  let finished = false; // Enter saves, then the box disappears and blurs: save only once.
  const finish = (save) => {
    if (finished) return;
    finished = true;
    renaming = null;
    if (save) saveName(calendar, input.value);
    else render(`tab-${calendar.id}`);
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      finish(true);
    } else if (e.key === "Escape") {
      e.preventDefault();
      finish(false);
    }
  });
  input.addEventListener("blur", () => finish(true));
  return input;
}

function calendarTab(calendar) {
  if (renaming === calendar.id) return el("span", { class: "cal-item" }, renameBox(calendar));
  const parts = [tabButton(calendar.id, calendar.name)];
  if (chosenCalendar() === calendar.id) {
    const label = t("Rename the calendar {name}", { name: calendar.name });
    const rename = el(
      "button",
      { type: "button", class: "cal-rename", "aria-label": label, title: t("Rename"), "data-focus": "rename" },
      icon("pencil"),
    );
    rename.addEventListener("click", () => startRename(calendar.id));
    parts.push(rename);
    // There must always be one calendar for new events to go on.
    if (getCalendars().length > 1) parts.push(removeButton(calendar));
  }
  return el("span", { class: "cal-item" }, ...parts);
}

// The bin: the first click turns it into a red "Click again..." button that
// says what goes with the calendar; it goes back to a bin after 4 seconds.
function removeButton(calendar) {
  const label = t("Remove the calendar {name}", { name: calendar.name });
  const count = whatGoes(calendar);
  const confirmLabel = count ? t("Click again: removes its {count} too", { count }) : t("Click again to remove");
  const button = el("button", { type: "button", class: "cal-rename cal-remove", "data-focus": "remove" });
  let timer = null;
  // Same two clicks as twoClickButton in ui.js, but the resting button is an icon, not a word.
  const reset = () => {
    clearTimeout(timer);
    button.classList.remove("confirming");
    button.replaceChildren(icon("bin"));
    button.setAttribute("aria-label", label);
    button.title = t("Remove");
  };
  button.addEventListener("click", () => {
    if (!button.classList.contains("confirming")) {
      button.classList.add("confirming");
      button.textContent = confirmLabel;
      button.setAttribute("aria-label", confirmLabel);
      timer = setTimeout(reset, 4000);
      return;
    }
    reset();
    removeCalendar(calendar);
  });
  reset();
  return button;
}

async function removeCalendar(calendar) {
  hideStatus(status);
  try {
    await api(`/api/calendars/${calendar.id}?delete_events=true`, { method: "DELETE" });
    chooseCalendar("all"); // Its tab is gone: show everything.
    await loadCalendars();
    route();
    bar.querySelector('[data-focus="tab-all"]')?.focus();
  } catch (err) {
    showStatus(status, err.message, true);
  }
}

// `focus`: the data-focus of the element to put the keyboard back on, since redrawing loses it.
function render(focus = null) {
  const add = el("button", { type: "button", class: "cal-tab cal-new" }, t("+ New calendar"));
  add.addEventListener("click", addCalendar);
  bar.replaceChildren(tabButton("all", t("All")), ...getCalendars().map(calendarTab), add);
  if (focus) bar.querySelector(`[data-focus="${focus}"]`)?.focus();
}

function choose(value) {
  hideStatus(status);
  renaming = null;
  chooseCalendar(value);
  render(`tab-${value}`);
  route();
}

export function startRename(id) {
  renaming = id;
  render();
  const input = bar.querySelector(".cal-name-input");
  input.focus();
  input.select();
  input.scrollIntoView({ block: "nearest", inline: "nearest" });
}

async function saveName(calendar, value) {
  const name = value.trim();
  hideStatus(status);
  if (!name || name === calendar.name) return render(`tab-${calendar.id}`);
  try {
    await api(`/api/calendars/${calendar.id}`, json("PATCH", { name }));
    await loadCalendars();
    route(); // Event links in "All" show the calendar's name.
  } catch (err) {
    render();
    showStatus(status, err.message, true);
  }
  bar.querySelector(`[data-focus="tab-${calendar.id}"]`)?.focus();
}

async function addCalendar() {
  hideStatus(status);
  try {
    const created = await api("/api/calendars", json("POST", { name: newCalendarName() }));
    chooseCalendar(created.id);
    await loadCalendars();
    route();
    if (calendarById(created.id)) startRename(created.id);
  } catch (err) {
    showStatus(status, err.message, true);
  }
}

onCalendarsChange(() => render());
