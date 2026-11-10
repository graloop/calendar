// The page's entry point (loaded by index.html). Each screen's code is in
// views/; what they share is in core/. This file only decides which screen an
// address opens:
//   /upcoming (and /)       the next 14 days
//   /week/2026-11-23        the week holding that day
//   /month/2026-11          that month
//   /event/5, /event/new    one event, or a new one (?date=2026-11-24)
//   /import                 the import box, its preview and Add to calendar

import { loadCalendars } from "./core/calendars.js";
import { loadCourses } from "./core/courses.js";
import { isValidDay, monthOf, todayISO } from "./core/dates.js";
import { translatePage } from "./core/i18n.js";
import "./core/theme.js";
import { setRouteHandler, start } from "./core/router.js";
import { hideStatus, showStatus } from "./core/ui.js";
import "./views/calendar-tabs.js";
import { setReturnTo, showEvent } from "./views/event.js";
import { showImport } from "./views/import.js";
import { showMonth } from "./views/month.js";
import "./views/settings.js";
import "./views/settings-calendars.js";
import { showUpcoming } from "./views/upcoming.js";
import { showWeek } from "./views/week.js";

translatePage();

const appError = document.getElementById("app-error");

function show(path) {
  let match;
  if ((match = path.match(/^\/week(?:\/(\d{4}-\d{2}-\d{2}))?$/))) {
    return showWeek(match[1] && isValidDay(match[1]) ? match[1] : todayISO());
  }
  if ((match = path.match(/^\/month(?:\/(\d{4}-\d{2}))?$/))) {
    return showMonth(match[1] && isValidDay(`${match[1]}-01`) ? match[1] : monthOf(todayISO()));
  }
  if (path === "/event/new") return showEvent(null, new URLSearchParams(location.search).get("date"));
  if ((match = path.match(/^\/event\/(\d+)$/))) return showEvent(match[1]);
  if (path === "/import") return showImport();
  return showUpcoming();
}

async function handleRoute() {
  const path = location.pathname;
  // The event screen goes back to the calendar screen it was opened from.
  if (!path.startsWith("/event/")) setReturnTo(path + location.search);
  // Each screen starts without the last one's message. ("Saved..." is shown
  // just after this, by the event screen, so it stays until the next screen.)
  hideStatus(appError);
  try {
    await show(path);
  } catch (err) {
    showStatus(appError, err.message, true);
  }
}

setRouteHandler(handleRoute);

try {
  await Promise.all([loadCourses(), loadCalendars()]);
} catch (err) {
  showStatus(appError, err.message, true);
}
start();
