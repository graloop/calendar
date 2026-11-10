// The page's address: /upcoming, /week/2026-11-23, /month/2026-11, /event/5...
// changes without reloading the page. main.js says what each address shows.
// Links inside the page are real links (they can be opened in a new tab, and
// the Claude extension can read where they go); a plain click on one is caught
// here and handled without a reload.

let handler = () => {};
let shown = 0; // goes up by one each time a screen is shown

// Each screen takes this number when it starts and checks it again after
// waiting for the server: if another screen was asked for meanwhile (two quick
// clicks on "Later"), the slower answer is dropped instead of drawn over it.
export function screenNumber() {
  return shown;
}

export function setRouteHandler(fn) {
  handler = fn;
  window.addEventListener("popstate", () => {
    shown++;
    handler();
  });
}

export function go(path) {
  if (location.pathname + location.search !== path) history.pushState({}, "", path);
  window.scrollTo(0, 0);
  shown++;
  handler();
}

// Shows the current address again, after something changed (a course's colour,
// another calendar chosen...). Not on the event form: redrawing it would throw
// away what's being typed. Its course list refreshes by itself.
export function route() {
  if (document.body.dataset.view === "event-view") return;
  shown++;
  handler();
}

// The first screen, when the page loads.
export function start() {
  shown++;
  handler();
}

document.addEventListener("click", (e) => {
  const link = e.target.closest("a[href^='/']");
  if (!link || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  if (link.target === "_blank") return;
  e.preventDefault();
  go(link.getAttribute("href"));
});
