// "Past imports" in the settings gear: each press of Add to calendar, newest
// first, with what it did and an Undo button. Also the bits the Import tab
// shares with it: undoing an import and saying what an import did.
// Undo isn't two-click: it can't lose anything a new import can't bring back,
// and the button's label says exactly what it will do.

import { api } from "../core/api.js";
import { loadCourses } from "../core/courses.js";
import { formatDay } from "../core/dates.js";
import { t } from "../core/i18n.js";
import { route } from "../core/router.js";
import { el, hideStatus, showStatus } from "../core/ui.js";

const list = document.getElementById("settings-imports");
const status = document.getElementById("settings-imports-status");

const SOURCES = { moodle: "Moodle", email: "Email", other: "Other", manual: "Typed by hand" };

export function sourceLabel(key) {
  return t(SOURCES[key] ?? "Other");
}

export function countsText(run) {
  return t("Added {added}, changed {changed}, skipped {skipped}.", run);
}

// "2026-11-10T14:05:00" -> "Tue, Nov 10, 2026, 14:05"
function when(stamp) {
  return `${formatDay(stamp.slice(0, 10), { year: true })}, ${stamp.slice(11, 16)}`;
}

// Undoes an import, then tells every screen (the Import tab's result, this list) and redraws the calendar.
export async function undoImport(id) {
  const result = await api(`/api/imports/${id}/undo`, { method: "POST" });
  document.dispatchEvent(new CustomEvent("import-undone", { detail: result }));
  await loadCourses();
  route();
  return result;
}

export function undoneText(result) {
  return t("Import undone: removed {removed}, put back {restored}.", result);
}

function row(run) {
  const date = when(run.created_at);
  const parts = [
    el("span", { class: "import-when" }, `${date} · ${sourceLabel(run.source)}`),
    el("span", { class: "status" }, countsText(run)),
  ];
  if (run.undone_at) {
    parts.push(el("span", { class: "status" }, t("Undone on {date}", { date: when(run.undone_at) })));
  } else {
    const button = el(
      "button",
      {
        type: "button",
        class: "btn-ghost import-undo",
        "aria-label": t(
          "Undo the import of {date}: removes the {added} events it added and puts back the {changed} it changed",
          {
            date,
            added: run.added,
            changed: run.changed,
          },
        ),
      },
      t("Undo"),
    );
    button.addEventListener("click", async () => {
      button.disabled = true;
      hideStatus(status);
      try {
        await undoImport(run.id);
      } catch (err) {
        showStatus(status, err.message, true);
        button.disabled = false;
      }
    });
    parts.push(button);
  }
  return el("li", { class: "settings-import" }, ...parts);
}

export async function renderPastImports() {
  hideStatus(status);
  try {
    const runs = await api("/api/imports");
    list.replaceChildren(...(runs.length ? runs.map(row) : [el("li", { class: "status" }, t("No imports yet."))]));
  } catch (err) {
    showStatus(status, err.message, true);
  }
}

document.addEventListener("import-undone", () => {
  if (!list.closest(".menu-panel").classList.contains("hidden")) renderPastImports();
});
