// The Import tab (/import): the text box (one event per line, kept as a draft
// while typing so a reload doesn't lose it), Preview, the preview table, Add to
// calendar, and the result with Undo this import.
// The server reads the lines and compares them with the calendar
// (backend/app/importing/): this file never reads a line itself.
// API: GET/PUT /api/import/draft, POST /api/import/preview, POST /api/import/apply.
//
// Why the hash: Add to calendar sends back the hash of the preview on the
// screen, and the server refuses if its own preview differs, so what's saved is
// exactly what was seen. Typing after a preview turns Add to calendar off until
// the next Preview, for the same reason.
//
// Everything in the table came from an email or a Moodle page: it only ever
// goes in as text (el() and textContent), never as HTML.

import { api, json } from "../core/api.js";
import { loadCourses } from "../core/courses.js";
import { formatDay, formatWhen } from "../core/dates.js";
import { t } from "../core/i18n.js";
import { typeBadge } from "../core/types.js";
import { el, hideStatus, showStatus, showView } from "../core/ui.js";
import { countsText, undoImport, undoneText } from "./past-imports.js";

const box = document.getElementById("import-text");
const sourceSelect = document.getElementById("import-source");
const draftStatus = document.getElementById("import-draft-status");
const previewPanel = document.getElementById("import-preview");
const summary = document.getElementById("import-summary");
const rowsBody = document.getElementById("import-rows");
const applyBtn = document.getElementById("import-apply");
const applyHint = document.getElementById("import-apply-hint");
const resultPanel = document.getElementById("import-result");
const resultText = document.getElementById("import-result-text");
const undoBtn = document.getElementById("import-undo");
const status = document.getElementById("import-status");

const DRAFT_DELAY = 700; // ms after the last key before the draft is saved

let draftLoaded = false;
let saveTimer = null;
let shown = null; // the preview on screen: { text, source, hash, counts }
let lastImportId = null; // what Undo this import undoes

// --- How to write the lines ---
// Written for a person and for the Claude extension: it should be able to
// follow this without being told the format. The examples stay in English in
// both languages: they're what to type, and the app reads them in either.

const EXAMPLE = [
  "Tue Nov 24 | 23:59 | deadline | ABC123 | Lab report 3 | Upload one PDF | https://moodle.example.org/mod/assign/view.php?id=301",
  "2026-12-08 | 9:00-12:00 | exam | XYZ789 | Final exam | room: D7-2018 | Email: Final exam room, 2026-11-20",
  "2026-09-08 | 13:30-15:20 | class | ABC123 | Lecture | weekly until 2026-12-08; except 2026-10-13; room: D3-2030 |",
  "mercredi 25 novembre | 14h30 75 min | réunion | - | Team meeting | |",
].join("\n");

function code(text) {
  return el("code", {}, text);
}

function buildHelp() {
  const fields = [
    [
      "date",
      t(
        "The day: 2026-11-24 or Tue Nov 24 (French works too: mardi 24 novembre). If you write the weekday, it must match the date, or the line is refused. Without a year, the nearest one is used.",
      ),
    ],
    [
      "time",
      t(
        "13:30-15:20, or a start and a length: 13:30 75 min. For a deadline, only the due time: 23:59. Write all day when there is no time.",
      ),
    ],
    [
      "type",
      t(
        "One of class, lab, exam, deadline, meeting, work, personal, other. French words work too: cours, labo, examen, remise, réunion.",
      ),
    ],
    [
      "course",
      t("The course code, like ABC123, or - for no course. A code the calendar doesn't know yet adds the course."),
    ],
    ["title", t("Short, like Lab report 3 or Final exam.")],
    [
      "details",
      t(
        "Optional free text. room: D7-2018 gives the place. weekly until 2026-12-12 repeats the event every week up to that date, and except 2026-10-13 skips one of those weeks (write except again for each week to skip).",
      ),
    ],
    ["source", t("Optional: the Moodle page's address, or Email: subject, date for an email.")],
  ];
  document
    .getElementById("import-help")
    .replaceChildren(
      el("h3", {}, t("How to write the lines")),
      el("p", {}, t("One event per line, with the fields in this order, separated by |:")),
      el("pre", { class: "import-format" }, "date | time | type | course | title | details | source"),
      el(
        "dl",
        { class: "import-fields" },
        ...fields.flatMap(([name, text]) => [el("dt", {}, code(name)), el("dd", {}, text)]),
      ),
      el("p", {}, t("Example:")),
      el("pre", { class: "import-example" }, EXAMPLE),
      el(
        "p",
        { class: "status" },
        t(
          "Press Preview to check the lines: nothing is saved until you press Add to calendar. A line with a mistake says how to fix it, and the other lines still go in. Lines already on the calendar are skipped, and an event that moved shows its old and new date.",
        ),
      ),
    );
}
buildHelp();

// --- The draft ---

async function saveDraft() {
  clearTimeout(saveTimer);
  saveTimer = null;
  try {
    await api("/api/import/draft", json("PUT", { text: box.value }));
    showStatus(draftStatus, t("Draft saved."));
  } catch (err) {
    showStatus(draftStatus, err.message, true);
  }
}

box.addEventListener("input", () => {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveDraft, DRAFT_DELAY);
  if (shown && box.value !== shown.text) markStale();
});

// Leaving the page with a save still waiting: send it anyway (keepalive outlives the page).
window.addEventListener("pagehide", () => {
  if (!saveTimer) return;
  fetch("/api/import/draft", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: box.value }),
    keepalive: true,
  });
});

// --- The preview ---

function markStale() {
  applyBtn.disabled = true;
  applyHint.textContent = t("The lines changed since the preview. Press Preview again.");
}

const STATUS_LABELS = { new: "New", already: "Already there", changed: "Changed", error: "Error" };

// The "{weekday}" in a message is an English day name: shown in the page's language.
function problemText(row) {
  const params = { ...row.params };
  for (const name of ["weekday", "written"]) if (params[name]) params[name] = t(params[name]);
  return t(row.template, params);
}

function statusCell(row) {
  let label = t(STATUS_LABELS[row.status]);
  if (row.in_import) label = t("Already there (earlier line)");
  const cell = el("td", {}, el("span", { class: `import-status status-${row.status}` }, label));
  if (row.new_course && row.status === "new") cell.append(" ", el("span", { class: "status" }, t("new course")));
  return cell;
}

// A cell, or "old → new" when the change touches it.
function cell(after, before, className = "") {
  if (before === undefined || before === after) return el("td", { class: className }, after ?? "");
  return el(
    "td",
    { class: `${className} changed-cell` },
    el("span", { class: "change-before" }, before || "–"),
    " → ",
    el("strong", {}, after || "–"),
  );
}

function detailsText(event) {
  const parts = [];
  if (event.location) parts.push(event.location);
  if (event.details) parts.push(event.details);
  if (event.series) parts.push(t("weekly"));
  if (event.source_link) parts.push(event.source_link);
  return parts.join(" · ");
}

function tableRow(row) {
  if (row.status === "error") {
    return el(
      "tr",
      { class: "row-error" },
      el("td", {}, String(row.line)),
      statusCell(row),
      el(
        "td",
        { colspan: "6" },
        el("code", { class: "import-line" }, row.text),
        el("span", { class: "import-fix" }, problemText(row)),
      ),
    );
  }
  // The event as it was, for "changed": its values from before over the new ones.
  const old = { ...row };
  for (const change of row.changes) old[change.field] = change.before;
  const changed = row.status === "changed";
  const date = formatDay(row.date, { year: true });
  const oldDate = formatDay(old.date, { year: true });
  return el(
    "tr",
    { class: `row-${row.status}`, title: row.text },
    el("td", {}, String(row.line)),
    statusCell(row),
    cell(date, changed ? oldDate : undefined, "nowrap"),
    cell(formatWhen(row), changed ? formatWhen(old) : undefined, "nowrap"),
    el("td", {}, typeBadge(row.type)),
    el("td", {}, row.course ?? "–"),
    cell(row.title, changed ? old.title : undefined),
    cell(detailsText(row), changed ? detailsText(old) : undefined, "import-details"),
  );
}

function renderPreview(preview) {
  const c = preview.counts;
  summary.textContent = t("{new} new, {changed} changed, {already} already there, {error} with an error.", c);
  rowsBody.replaceChildren(...preview.rows.map(tableRow));
  if (!preview.rows.length) {
    rowsBody.append(el("tr", {}, el("td", { colspan: "8", class: "status" }, t("No event lines yet."))));
  }
  previewPanel.classList.remove("hidden");
  const toSave = c.new + c.changed;
  applyBtn.disabled = toSave === 0;
  applyHint.textContent = toSave ? "" : t("Nothing new or changed to add.");
}

async function runPreview() {
  hideStatus(status);
  const body = { text: box.value, source: sourceSelect.value };
  const preview = await api("/api/import/preview", json("POST", body));
  shown = { ...body, hash: preview.hash };
  renderPreview(preview);
  return preview;
}

document.getElementById("import-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (saveTimer) saveDraft();
  hideStatus(resultPanel);
  try {
    await runPreview();
  } catch (err) {
    showStatus(status, err.message, true);
  }
});

// The chosen source is part of what the preview showed.
sourceSelect.addEventListener("change", () => {
  if (shown) markStale();
});

// --- Add to calendar, and undo ---

applyBtn.addEventListener("click", async () => {
  if (!shown) return;
  applyBtn.disabled = true;
  hideStatus(status);
  try {
    const { text, source, hash } = shown;
    const result = await api("/api/import/apply", json("POST", { text, source, hash }));
    lastImportId = result.import_id;
    let said = countsText(result);
    if (result.errors) said += " " + t("Lines with an error, not added: {errors}.", result);
    resultText.textContent = said;
    resultText.className = "status ok";
    undoBtn.classList.toggle("hidden", !lastImportId);
    undoBtn.disabled = false;
    resultPanel.classList.remove("hidden");
    await loadCourses(); // a new course code made a course, with its colour
    await runPreview(); // now every saved line shows as already there
  } catch (err) {
    showStatus(status, err.message, true);
    if (err.status !== 409) applyBtn.disabled = false;
  }
});

undoBtn.addEventListener("click", async () => {
  if (!lastImportId) return;
  undoBtn.disabled = true;
  hideStatus(status);
  try {
    await undoImport(lastImportId);
  } catch (err) {
    showStatus(status, err.message, true);
    undoBtn.disabled = false;
  }
});

// Undone here or from Settings: say so, and preview again so the lines show as new.
document.addEventListener("import-undone", async (e) => {
  if (e.detail.import.id !== lastImportId) return;
  lastImportId = null;
  resultText.textContent = undoneText(e.detail);
  undoBtn.classList.add("hidden");
  if (shown && box.value === shown.text) {
    try {
      await runPreview();
    } catch (err) {
      showStatus(status, err.message, true);
    }
  }
});

export async function showImport() {
  showView("import");
  document.title = `${t("Import")} · Agenda`;
  if (draftLoaded) return;
  const draft = await api("/api/import/draft");
  draftLoaded = true;
  // Something typed while the draft was loading wins over the saved one.
  if (!box.value) box.value = draft.text;
}
