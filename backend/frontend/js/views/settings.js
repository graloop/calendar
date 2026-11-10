// The settings gear: the language, and the courses (code, name, colour, remove).

import { api, json } from "../core/api.js";
import { getCourses, loadCourses, onCoursesChange } from "../core/courses.js";
import { getLang, isSingular, setLang, t } from "../core/i18n.js";
import { registerMenu } from "../core/menus.js";
import { route } from "../core/router.js";
import { el, hideStatus, showStatus, twoClickButton } from "../core/ui.js";

const list = document.getElementById("settings-courses");
const status = document.getElementById("settings-status");

for (const button of document.querySelectorAll("[data-lang]")) {
  button.setAttribute("aria-pressed", String(button.dataset.lang === getLang()));
  button.addEventListener("click", () => {
    if (button.dataset.lang !== getLang()) setLang(button.dataset.lang);
  });
}

// Sends one change, then redraws the calendar behind (it shows codes and colours).
async function change(course, fields, input, oldValue) {
  hideStatus(status);
  try {
    await api(`/api/courses/${course.id}`, json("PATCH", fields));
    await loadCourses();
    route();
  } catch (err) {
    input.value = oldValue;
    showStatus(status, err.message, true);
  }
}

function countText(n) {
  return isSingular(n) ? t("{n} event", { n }) : t("{n} events", { n });
}

function removeButton(course) {
  const button = el("button", { type: "button", class: "btn-ghost course-remove" });
  const n = course.event_count;
  twoClickButton(button, {
    label: t("Remove"),
    confirmLabel: n ? t("Click again: removes its {count} too", { count: countText(n) }) : t("Click again to remove"),
    onConfirm: async () => {
      hideStatus(status);
      try {
        await api(`/api/courses/${course.id}?delete_events=true`, { method: "DELETE" });
        await loadCourses();
        route();
      } catch (err) {
        showStatus(status, err.message, true);
      }
    },
  });
  button.setAttribute("aria-label", t("Remove the course {code}", { code: course.code }));
  return button;
}

function render() {
  if (!getCourses().length) {
    list.replaceChildren(
      el("li", { class: "status" }, t("No courses yet. Add one here, or add an event with a course code.")),
    );
    return;
  }
  list.replaceChildren(
    ...getCourses().map((course) => {
      const color = el("input", {
        type: "color",
        value: course.color,
        "aria-label": t("{code}: colour", { code: course.code }),
        title: t("Colour"),
      });
      color.addEventListener("change", () => change(course, { color: color.value }, color, course.color));
      const code = el("input", {
        type: "text",
        maxlength: "20",
        value: course.code,
        "aria-label": t("{code}: code", { code: course.code }),
        autocapitalize: "characters",
      });
      code.addEventListener("change", () => change(course, { code: code.value }, code, course.code));
      const name = el("input", {
        type: "text",
        maxlength: "200",
        value: course.name ?? "",
        class: "course-name",
        placeholder: t("Course name (optional)"),
        "aria-label": t("{code}: name", { code: course.code }),
      });
      name.addEventListener("change", () => change(course, { name: name.value }, name, course.name ?? ""));
      const count = el("span", { class: "status course-count" }, countText(course.event_count));
      return el("li", { class: "settings-course" }, color, code, removeButton(course), name, count);
    }),
  );
}

onCoursesChange(render);
registerMenu("settings-btn", "settings-panel", () => {
  hideStatus(status);
  loadCourses().catch((err) => showStatus(status, err.message, true));
});

document.getElementById("settings-add-course").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("settings-new-code");
  hideStatus(status);
  try {
    await api("/api/courses", json("POST", { code: input.value }));
    input.value = "";
    await loadCourses();
  } catch (err) {
    showStatus(status, err.message, true);
  }
});
