// Small page helpers every view uses: which screen is shown, status lines, and
// building elements. Text always goes in as text, never as HTML, so what an
// email or a Moodle page says can't turn into code on the page.

import { closeMenus } from "./menus.js";

const VIEWS = ["upcoming-view", "week-view", "month-view", "event-view"];

// Also marks the matching tab as the current one ("event" has no tab).
export function showView(name) {
  const id = `${name}-view`;
  // Refreshing the same screen keeps a menu open: changing a colour in Settings shouldn't close Settings.
  if (document.body.dataset.view !== id) closeMenus();
  for (const view of VIEWS) document.getElementById(view).classList.toggle("hidden", view !== id);
  document.body.dataset.view = id;
  for (const tab of ["upcoming", "week", "month"]) {
    const link = document.getElementById(`tab-${tab}`);
    if (tab === name) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

export function showStatus(element, text, isError = false) {
  element.textContent = text;
  element.classList.remove("hidden", "ok");
  element.classList.toggle("error", isError);
  element.classList.toggle("status", !isError);
}

export function hideStatus(element) {
  element.classList.add("hidden");
}

// el("a", { class: "x", href: "/" }, "text", otherElement)
export function el(tag, attributes = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value !== null && value !== undefined) element.setAttribute(name, value);
  }
  element.append(...children.filter((child) => child !== null && child !== undefined));
  return element;
}

// Two clicks instead of the browser's "are you sure" pop-up, which would block the Claude
// extension. The first click turns the button red and asks again; after 4
// seconds without a second click it goes back to normal.
export function twoClickButton(button, { label, confirmLabel, onConfirm }) {
  let timer = null;
  const reset = () => {
    clearTimeout(timer);
    button.classList.remove("confirming");
    button.textContent = label;
  };
  reset();
  button.onclick = () => {
    if (!button.classList.contains("confirming")) {
      button.classList.add("confirming");
      button.textContent = confirmLabel;
      timer = setTimeout(reset, 4000);
      return;
    }
    reset();
    onConfirm();
  };
}
