// Contact form on /kontakt/: validates in the browser, posts JSON to
// `${API_BASE}/api/contact` and shows the thanks or the send-error state of
// the approved mockups (kontakt-validierung, kontakt-versandfehler,
// kontakt-danke). Every text is written with textContent, never as HTML.
import { API_BASE } from "./config.js";
import { FIELDS, normalize, validateField } from "./validation.js";

/** Element ids of the inputs (as in the mockups), keyed by the API field name. */
export const INPUT_IDS = Object.freeze({
  first_name: "firstname",
  last_name: "lastname",
  email: "email",
  message: "message",
});

export const SENDING_LABEL = "Wird gesendet …";

/** First sentence of the send-error alert; the alert then names office@equicrew.com. */
export const ALERT_TEXTS = Object.freeze({
  invalid: "Der Server hat deine Eingaben nicht angenommen.",
  "too-large": "Deine Nachricht ist zu lang für den Versand.",
  "rate-limit": "Du hast gerade sehr viele Nachrichten geschickt. Bitte versuch es später noch einmal.",
  unavailable: "Das hat leider nicht geklappt.",
  network: "Wir konnten den Server gerade nicht erreichen.",
  error: "Das hat leider nicht geklappt.",
});

function reasonFor(status) {
  if (status === 422) return "invalid";
  if (status === 413) return "too-large";
  if (status === 429) return "rate-limit";
  if (status === 503) return "unavailable";
  return "error";
}

/**
 * Send the contact payload to the API.
 * @param {{first_name: string, last_name: string, email: string, message: string, website: string}} payload
 * @param {typeof fetch} [fetchImpl] the fetch implementation (injected in tests)
 * @param {string} [apiBase] base URL of the API, "" = same origin
 * @returns {Promise<{ok: true, status: number} | {ok: false, status: number | null, reason: string}>}
 */
export async function sendContact(payload, fetchImpl = globalThis.fetch, apiBase = API_BASE) {
  let response;
  try {
    response = await fetchImpl(`${apiBase}/api/contact`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    return { ok: false, status: null, reason: "network" };
  }
  if (response.status === 200) return { ok: true, status: 200 };
  return { ok: false, status: response.status, reason: reasonFor(response.status) };
}

/**
 * Wire the contact form of the given document. Returns null when the page has
 * no contact form, else a handle whose `submit()` resolves once a send ends.
 */
export function initContactForm(doc = globalThis.document, options = {}) {
  const form = doc?.getElementById("contact-form");
  if (!form) return null;
  const fetchImpl = options.fetchImpl ?? ((...args) => globalThis.fetch(...args));
  const apiBase = options.apiBase ?? API_BASE;

  const sheet = doc.getElementById("contact-sheet");
  const thanks = doc.getElementById("contact-thanks");
  const alertBox = doc.getElementById("form-alert");
  const alertReason = doc.getElementById("form-alert-reason");
  const status = doc.getElementById("form-status");
  const button = doc.getElementById("form-submit");
  const honeypot = doc.getElementById("website");
  const idleLabel = button.textContent;

  const inputs = {};
  const errors = {};
  for (const name of FIELDS) {
    inputs[name] = doc.getElementById(INPUT_IDS[name]);
    errors[name] = doc.getElementById(`err-${INPUT_IDS[name]}`);
  }
  const touched = new Set();
  let attempted = false;
  let pending = false;

  function show(name, message) {
    const input = inputs[name];
    const error = errors[name];
    if (message) {
      input.setAttribute("aria-invalid", "true");
      error.querySelector(".msg").textContent = message;
      error.hidden = false;
    } else {
      input.removeAttribute("aria-invalid");
      error.querySelector(".msg").textContent = "";
      error.hidden = true;
    }
  }

  function check(name) {
    const message = validateField(name, inputs[name].value);
    show(name, message);
    return message === "";
  }

  for (const name of FIELDS) {
    const input = inputs[name];
    input.addEventListener("input", () => {
      touched.add(name);
      // A shown error is updated while typing; a new one waits for blur.
      if (input.getAttribute("aria-invalid") === "true") check(name);
    });
    input.addEventListener("blur", () => {
      if (touched.has(name) || attempted) check(name);
    });
  }

  function setPending(on) {
    pending = on;
    button.disabled = on;
    button.classList.toggle("is-loading", on);
    if (on) {
      button.setAttribute("aria-busy", "true");
      button.textContent = SENDING_LABEL;
    } else {
      button.removeAttribute("aria-busy");
      button.textContent = idleLabel;
    }
    if (status) status.textContent = on ? "Nachricht wird gesendet …" : "";
  }

  async function submit() {
    if (pending) return;
    attempted = true;
    alertBox.hidden = true;
    let firstInvalid = null;
    for (const name of FIELDS) {
      if (!check(name) && !firstInvalid) firstInvalid = inputs[name];
    }
    if (firstInvalid) {
      firstInvalid.focus();
      return;
    }

    const payload = {};
    for (const name of FIELDS) payload[name] = normalize(inputs[name].value);
    payload.website = honeypot ? honeypot.value : "";

    setPending(true);
    const result = await sendContact(payload, fetchImpl, apiBase);
    setPending(false);

    if (result.ok) {
      sheet.hidden = true;
      thanks.hidden = false;
      const heading = thanks.querySelector("h2");
      if (heading) heading.focus();
      return;
    }
    if (alertReason) alertReason.textContent = ALERT_TEXTS[result.reason] ?? ALERT_TEXTS.error;
    alertBox.hidden = false;
    alertBox.focus();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    return submit();
  });

  return { submit };
}

if (typeof document !== "undefined") initContactForm(document);
