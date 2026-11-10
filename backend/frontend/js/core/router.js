// The page's address: /upcoming, /week/2026-11-23, /month/2026-11, /event/5...
// changes without reloading the page. main.js says what each address shows.
// Links inside the page are real links (they can be opened in a new tab, and
// the Claude extension can read where they go); a plain click on one is caught
// here and handled without a reload.

let handler = () => {};

export function setRouteHandler(fn) {
  handler = fn;
  window.addEventListener("popstate", () => handler());
}

export function go(path) {
  if (location.pathname + location.search !== path) history.pushState({}, "", path);
  window.scrollTo(0, 0);
  handler();
}

// Shows the current address again, after something changed (a course's colour...).
export function route() {
  handler();
}

document.addEventListener("click", (e) => {
  const link = e.target.closest("a[href^='/']");
  if (!link || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  if (link.target === "_blank") return;
  e.preventDefault();
  go(link.getAttribute("href"));
});
