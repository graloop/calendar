// The "Calendars" part of the settings gear: rename each calendar, or remove it
// with two clicks (the second one says how many events and to-dos go with it).

import { api, json } from "../core/api.js";
import { getCalendars, loadCalendars, onCalendarsChange, whatGoes } from "../core/calendars.js";
import { isSingular, t } from "../core/i18n.js";
import { route } from "../core/router.js";
import { el, hideStatus, showStatus, twoClickButton } from "../core/ui.js";

const list = document.getElementById("settings-calendars");
const status = document.getElementById("settings-status");

async function rename(calendar, input) {
  hideStatus(status);
  try {
    await api(`/api/calendars/${calendar.id}`, json("PATCH", { name: input.value }));
    await loadCalendars();
    route();
  } catch (err) {
    input.value = calendar.name;
    showStatus(status, err.message, true);
  }
}

function removeButton(calendar, isLast) {
  const button = el("button", { type: "button", class: "btn-ghost course-remove" });
  const count = whatGoes(calendar);
  twoClickButton(button, {
    label: t("Remove"),
    confirmLabel: count ? t("Click again: removes its {count} too", { count }) : t("Click again to remove"),
    onConfirm: async () => {
      hideStatus(status);
      try {
        await api(`/api/calendars/${calendar.id}?delete_events=true`, { method: "DELETE" });
        await loadCalendars();
        route();
      } catch (err) {
        showStatus(status, err.message, true);
      }
    },
  });
  button.setAttribute("aria-label", t("Remove the calendar {name}", { name: calendar.name }));
  // There must always be one calendar for new events to go on.
  if (isLast) {
    button.disabled = true;
    button.title = t("The last calendar can't be removed.");
  }
  return button;
}

function render() {
  const calendars = getCalendars();
  list.replaceChildren(
    ...calendars.map((calendar) => {
      const name = el("input", {
        type: "text",
        maxlength: "40",
        value: calendar.name,
        "aria-label": t("Name of the calendar {name}", { name: calendar.name }),
      });
      name.addEventListener("change", () => rename(calendar, name));
      const counts = [
        isSingular(calendar.event_count)
          ? t("{n} event", { n: calendar.event_count })
          : t("{n} events", { n: calendar.event_count }),
      ];
      if (calendar.todo_count) {
        counts.push(t("{n} not done on the weekly lists", { n: calendar.todo_count }));
      }
      return el(
        "li",
        { class: "settings-calendar" },
        name,
        removeButton(calendar, calendars.length === 1),
        el("span", { class: "status calendar-count" }, counts.join(" · ")),
      );
    }),
  );
}

onCalendarsChange(render);
