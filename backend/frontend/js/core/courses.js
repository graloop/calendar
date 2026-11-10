// The list of courses, loaded once and shared by every screen (colours in the
// calendar, codes in the event form, the list in Settings).

import { api } from "./api.js";

let courses = [];
const listeners = [];

export function getCourses() {
  return courses;
}

export async function loadCourses() {
  courses = await api("/api/courses");
  for (const listener of listeners) listener();
  return courses;
}

// `listener` runs whenever the list changes.
export function onCoursesChange(listener) {
  listeners.push(listener);
}
