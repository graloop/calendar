// Every call to the server goes through api(): it turns an error answer into a
// thrown Error with a readable message and the HTTP status (err.status).
// getOnce() remembers what the current screen loaded, so choosing another
// calendar tab redraws from memory, with no request at all.

import { t } from "./i18n.js";

// Answers kept for the current screen: address -> promise of its JSON.
const answers = new Map();

// Asks the server only the first time; later calls get the same answer from memory.
export function getOnce(path) {
  if (!answers.has(path)) {
    // A failed request isn't kept, so the next try asks again.
    const answer = api(path).catch((err) => {
      if (answers.get(path) === answer) answers.delete(path);
      throw err;
    });
    answers.set(path, answer);
  }
  return answers.get(path);
}

// Called when another screen opens (router.js), and after any change sent to
// the server, so what's in memory is never older than the last save. A to-do
// change only touches to-dos; anything else (an event, a course's colour, a
// calendar's name, an import...) can change what events show, so all goes.
export function forgetAnswers(changed = "") {
  const prefix = changed.startsWith("/api/todos") ? "/api/todos" : "";
  for (const path of [...answers.keys()]) if (path.startsWith(prefix)) answers.delete(path);
}

export async function api(path, options = {}) {
  const changes = options.method && options.method !== "GET";
  // Before and after: a screen that loads while the change is on its way mustn't keep the old answer.
  if (changes) forgetAnswers(path);
  try {
    return await send(path, options);
  } finally {
    if (changes) forgetAnswers(path);
  }
}

async function send(path, options) {
  const headers = { ...options.headers };
  if (options.body) headers["Content-Type"] = "application/json";

  let res;
  try {
    res = await fetch(path, { ...options, headers });
  } catch (_) {
    throw new Error(t("Can't reach the app. Check that it's running."));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {
      if (res.status >= 500)
        detail = t("The server didn't answer (error {status}). Try again in a minute.", { status: res.status });
    }
    if (!detail) detail = t("Error {status}", { status: res.status });
    // A field the server refused: its message, without pydantic's "Value error, " in front.
    if (typeof detail !== "string") detail = detail.map((d) => d.msg.replace(/^Value error, /, "")).join("; ");
    const error = new Error(t(detail));
    error.status = res.status;
    throw error;
  }
  if (res.status === 204) return null;
  return res.json();
}

export function json(method, body) {
  return { method, body: JSON.stringify(body) };
}
