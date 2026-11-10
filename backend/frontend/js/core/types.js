// The event types: stored as English keys, shown in the page's language, each
// with a small line icon so a lab and an exam can be told apart at a glance.

import { t } from "./i18n.js";
import { el } from "./ui.js";

const LABELS = {
  class: "Class",
  lab: "Lab",
  exam: "Exam",
  deadline: "Deadline",
  meeting: "Meeting",
  work: "Work",
  personal: "Personal",
  other: "Other",
};

// Simple 24×24 line drawings: a book, a flask, a checked sheet, a flag...
const ICONS = {
  class: "M2 4h6a4 4 0 0 1 4 4v12a3 3 0 0 0-3-3H2zM22 4h-6a4 4 0 0 0-4 4v12a3 3 0 0 1 3-3h7z",
  lab: "M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3M7 15h10",
  exam: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 15l2 2 4-4",
  deadline: "M4 22V4M4 4h13l-2.5 4L17 12H4",
  meeting:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 3a4 4 0 1 1 0 8a4 4 0 1 1 0-8M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  work: "M3 7h18v13H3zM8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18",
  personal:
    "M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7z",
  other: "M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18M12 8v5M12 16v.5",
};

export const TYPES = Object.keys(LABELS);

export function typeLabel(key) {
  return t(LABELS[key] ?? "Other");
}

function icon(key) {
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
  path.setAttribute("d", ICONS[key] ?? ICONS.other);
  svg.append(path);
  return svg;
}

// The icon and the word, e.g. [flask] Lab.
export function typeBadge(key) {
  return el(
    "span",
    { class: `type-badge type-${key}` },
    icon(key),
    el("span", { class: "type-label" }, typeLabel(key)),
  );
}

// Fills a <select> with the types.
export function fillTypeSelect(select) {
  select.replaceChildren(...TYPES.map((key) => el("option", { value: key }, typeLabel(key))));
}
