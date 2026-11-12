// "This week's list": things to get done during a week, not on a set day. Shown
// above the Week grid (for the week shown) and above Upcoming (for this week).
// Each item has a box to tick, its text in a field to reword it, and a delete
// that takes two clicks. In "All", each item says its calendar and the add form
// asks which calendar a new one goes on. Under the list: move what's left to
// next week, or bring next week's unfinished items to this one. Done items sit
// at the bottom (the server sorts them there). The dots at the start of a row
// drag it up or down, with a mouse, a finger or the arrow keys.

import { api, getOnce, json } from "../core/api.js";
import { chosenCalendar, defaultCalendarId, fillCalendarSelect, onlyChosen } from "../core/calendars.js";
import { addDays } from "../core/dates.js";
import { t } from "../core/i18n.js";
import { el, hideStatus, showStatus, twoClickButton } from "../core/ui.js";

// One panel per container (Week and Upcoming each have theirs), redrawn from the server after each change.
const panels = new Map(); // container -> { monday, items, nextCount, request }

function panelFor(container) {
  if (!panels.has(container)) panels.set(container, { monday: null, items: [], nextCount: 0, request: 0 });
  return panels.get(container);
}

// `monday`: "2026-11-23". Draws the panel for that week and the chosen calendar.
export async function showWeekList(container, monday) {
  const panel = panelFor(container);
  panel.monday = monday;
  await refresh(container);
}

async function refresh(container, { focus = null, message = null } = {}) {
  const panel = panelFor(container);
  const request = ++panel.request; // Moving on fast: only the last answer is drawn.
  try {
    // Next week's list too, only to know whether there's anything to bring back.
    const [items, next] = await Promise.all([
      getOnce(`/api/todos?week=${panel.monday}`),
      getOnce(`/api/todos?week=${addDays(panel.monday, 7)}`),
    ]);
    if (request !== panel.request) return;
    panel.items = onlyChosen(items);
    panel.nextCount = onlyChosen(next).filter((item) => !item.done).length;
    render(container, { focus, message });
  } catch (err) {
    if (request !== panel.request) return;
    render(container, { message: err.message, isError: true });
  }
}

// Sends a change, then redraws; a failure shows in the panel's status line.
async function send(container, path, options, redraw = {}) {
  try {
    const answer = await api(path, options);
    await refresh(container, redraw);
    return answer;
  } catch (err) {
    await refresh(container, { ...redraw, message: err.message, isError: true });
    return null;
  }
}

// The six dots at the start of a row: a grip to drag it.
function gripIcon() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 10 16");
  svg.setAttribute("aria-hidden", "true");
  for (const [x, y] of [
    [2, 3],
    [8, 3],
    [2, 8],
    [8, 8],
    [2, 13],
    [8, 13],
  ]) {
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", x);
    dot.setAttribute("cy", y);
    dot.setAttribute("r", "1.5");
    dot.setAttribute("fill", "currentColor");
    svg.append(dot);
  }
  return svg;
}

// Rows can only move among rows like them: done ones stay at the bottom.
function sameGroup(a, b) {
  return a && b && a.classList.contains("is-done") === b.classList.contains("is-done");
}

// Sends the order the rows are in now, if it changed, then redraws.
function saveOrder(container, focus) {
  const panel = panelFor(container);
  const ids = [...container.querySelectorAll(".week-item")].map((row) => Number(row.dataset.id));
  if (ids.join() === panel.items.map((item) => item.id).join()) return;
  send(container, "/api/todos/order", json("PUT", { week: panel.monday, ids }), { focus });
}

// Pointer events rather than the browser's drag and drop, which doesn't work on a phone:
// the row follows the finger, swapping places with a neighbour when it passes its middle.
function makeDraggable(container, row, grip) {
  grip.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    row.classList.add("dragging");
    // Listened to on the whole page: moving the row in the list makes the browser
    // forget which element had the pointer, so the grip alone would stop hearing it.
    const move = (e) => {
      if (e.pointerId !== id) return;
      // A fast move can pass several rows at once: keep swapping while it's past them.
      let prev, next;
      while (sameGroup(row, (prev = row.previousElementSibling)) && e.clientY < middle(prev)) prev.before(row);
      while (sameGroup(row, (next = row.nextElementSibling)) && e.clientY > middle(next)) next.after(row);
    };
    const end = (e) => {
      if (e.pointerId !== id) return;
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", end);
      document.removeEventListener("pointercancel", end);
      row.classList.remove("dragging");
      saveOrder(container, grip.dataset.focus);
    };
    const id = e.pointerId;
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", end);
    document.addEventListener("pointercancel", end);
  });
  // The keyboard (and the Claude extension): up and down arrows move the row one place.
  grip.addEventListener("keydown", (e) => {
    const prev = row.previousElementSibling;
    const next = row.nextElementSibling;
    if (e.key === "ArrowUp" && sameGroup(row, prev)) prev.before(row);
    else if (e.key === "ArrowDown" && sameGroup(row, next)) next.after(row);
    else return;
    e.preventDefault();
    grip.focus();
    saveOrder(container, grip.dataset.focus);
  });
}

function middle(element) {
  const box = element.getBoundingClientRect();
  return box.top + box.height / 2;
}

function itemRow(container, item, showCalendar) {
  const grip = el(
    "button",
    {
      type: "button",
      class: "week-item-grip",
      "aria-label": t("Drag to move: {text}. Or use the up and down arrow keys.", { text: item.text }),
      "data-focus": `grip-${item.id}`,
    },
    gripIcon(),
  );
  const box = el("input", {
    type: "checkbox",
    "aria-label": t("Done: {text}", { text: item.text }),
    "data-focus": `done-${item.id}`,
  });
  box.checked = item.done;
  box.addEventListener("change", () =>
    send(container, `/api/todos/${item.id}`, json("PATCH", { done: box.checked }), { focus: `done-${item.id}` }),
  );

  const text = el("input", {
    type: "text",
    class: "week-item-text",
    maxlength: "300",
    value: item.text,
    "aria-label": t("To-do: {text}", { text: item.text }),
  });
  // Not redrawn after a reword, so the keyboard stays where it went next.
  text.addEventListener("change", async () => {
    const status = container.querySelector(".week-list-status");
    try {
      const saved = await api(`/api/todos/${item.id}`, json("PATCH", { text: text.value }));
      Object.assign(item, saved);
      text.value = saved.text;
      text.setAttribute("aria-label", t("To-do: {text}", { text: saved.text }));
      box.setAttribute("aria-label", t("Done: {text}", { text: saved.text }));
      grip.setAttribute(
        "aria-label",
        t("Drag to move: {text}. Or use the up and down arrow keys.", { text: saved.text }),
      );
      hideStatus(status);
    } catch (err) {
      text.value = item.text;
      showStatus(status, err.message, true);
    }
  });

  const remove = el("button", { type: "button", class: "btn-ghost week-item-delete" });
  twoClickButton(remove, {
    label: t("Delete"),
    confirmLabel: t("Click again to delete"),
    onConfirm: () => send(container, `/api/todos/${item.id}`, { method: "DELETE" }),
  });
  remove.setAttribute("aria-label", t("Delete: {text}", { text: item.text }));

  const row = el(
    "li",
    { class: `week-item${item.done ? " is-done" : ""}`, "data-id": item.id },
    grip,
    el("label", { class: "week-item-check" }, box),
    text,
    showCalendar ? el("span", { class: "cal-tag" }, item.calendar_name) : null,
    remove,
  );
  makeDraggable(container, row, grip);
  return row;
}

function addForm(container, showCalendar) {
  const panel = panelFor(container);
  const id = `${container.id}-new`;
  const input = el("input", { id, type: "text", maxlength: "300", required: "", autocomplete: "off" });
  const fields = [el("label", { for: id }, t("Something to do this week")), input];
  let select = null;
  if (showCalendar) {
    select = el("select", { id: `${container.id}-calendar` });
    fillCalendarSelect(select, defaultCalendarId());
    fields.push(el("label", { for: select.id }, t("Calendar")), select);
  }
  const form = el(
    "form",
    { class: "week-add", "aria-label": t("Add to this week's list") },
    ...fields,
    el("button", { type: "submit" }, t("Add")),
  );
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!input.value.trim()) return input.focus();
    const body = {
      week: panel.monday,
      calendar_id: select ? Number(select.value) : defaultCalendarId(),
      text: input.value,
    };
    try {
      await api("/api/todos", json("POST", body));
    } catch (err) {
      // Not redrawn, so what was typed is still there to fix.
      return showStatus(container.querySelector(".week-list-status"), err.message, true);
    }
    // The keyboard goes back to the box, ready for the next item.
    refresh(container, { focus: "new" });
  });
  input.dataset.focus = "new";
  return form;
}

function render(container, { focus = null, message = null, isError = false } = {}) {
  const panel = panelFor(container);
  const items = panel.items;
  const showCalendar = chosenCalendar() === "all";
  const done = items.filter((item) => item.done).length;
  const headingId = `${container.id}-heading`;

  const head = el(
    "div",
    { class: "week-list-head" },
    el("h3", { id: headingId }, t("This week's list")),
    items.length ? el("span", { class: "status" }, t("{done} of {total} done", { done, total: items.length })) : null,
  );
  const list = items.length
    ? el("ul", { class: "week-items" }, ...items.map((item) => itemRow(container, item, showCalendar)))
    : el("p", { class: "status" }, t("Nothing on the list yet."));

  let carry = null;
  if (done < items.length) {
    carry = el("button", { type: "button", class: "btn-ghost week-carry" }, t("Move unfinished to next week"));
    carry.addEventListener("click", async () => {
      const chosen = chosenCalendar();
      const body = { week: panel.monday, calendar_id: chosen === "all" ? null : chosen };
      const answer = await api("/api/todos/carry-over", json("POST", body)).catch((err) => {
        refresh(container, { message: err.message, isError: true });
        return null;
      });
      if (answer) refresh(container, { message: t("Moved {n} to next week.", { n: answer.moved }) });
    });
  }

  let bring = null;
  if (panel.nextCount) {
    bring = el(
      "button",
      { type: "button", class: "btn-ghost week-carry" },
      t("Bring next week's {n} unfinished here", { n: panel.nextCount }),
    );
    bring.addEventListener("click", async () => {
      const chosen = chosenCalendar();
      const body = { week: panel.monday, calendar_id: chosen === "all" ? null : chosen };
      const answer = await api("/api/todos/bring-back", json("POST", body)).catch((err) => {
        refresh(container, { message: err.message, isError: true });
        return null;
      });
      if (answer) refresh(container, { message: t("Brought {n} from next week.", { n: answer.moved }) });
    });
  }

  const status = el("p", { class: "status week-list-status hidden", "aria-live": "polite" });
  container.replaceChildren(
    el(
      "section",
      { class: "panel week-list", "aria-labelledby": headingId },
      head,
      list,
      addForm(container, showCalendar),
      carry || bring ? el("div", { class: "week-moves" }, carry, bring) : null,
      status,
    ),
  );
  if (message) showStatus(status, message, isError);
  if (focus) container.querySelector(`[data-focus="${focus}"]`)?.focus();
}
