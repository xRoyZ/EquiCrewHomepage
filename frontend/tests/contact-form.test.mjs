// Behaviour of the contact form (js/contact-form.js): the network call with an
// injected fetch, and the page states driven against a minimal fake DOM —
// no errors on an untouched form, errors after leaving a touched field or on
// a submit attempt, the pending button, the thanks state on 200 and the
// send-error alert (with the input kept) on 422/429/503/network failure.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { ALERT_TEXTS, SENDING_LABEL, initContactForm, sendContact } from "../js/contact-form.js";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");

class FakeElement {
  constructor(id, attrs = {}) {
    this.id = id;
    this.attrs = { ...attrs };
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.textContent = "";
    this.listeners = {};
    this.children = {};
    this.classes = new Set();
    this.classList = {
      toggle: (name, force) => {
        const on = force === undefined ? !this.classes.has(name) : Boolean(force);
        if (on) this.classes.add(name);
        else this.classes.delete(name);
        return on;
      },
      contains: (name) => this.classes.has(name),
    };
  }
  getAttribute(name) {
    return name in this.attrs ? this.attrs[name] : null;
  }
  setAttribute(name, value) {
    this.attrs[name] = String(value);
  }
  removeAttribute(name) {
    delete this.attrs[name];
  }
  addEventListener(type, fn) {
    (this.listeners[type] ??= []).push(fn);
  }
  dispatch(type, event = {}) {
    return (this.listeners[type] ?? []).map((fn) => fn({ type, target: this, ...event }));
  }
  querySelector(selector) {
    return this.children[selector] ?? null;
  }
  focus() {
    this.doc.activeElement = this;
  }
}

function makePage() {
  const els = {};
  const doc = { activeElement: null, getElementById: (id) => els[id] ?? null };
  const add = (id, attrs) => {
    const el = new FakeElement(id, attrs);
    el.doc = doc;
    els[id] = el;
    return el;
  };
  add("contact-form");
  add("contact-sheet");
  const thanks = add("contact-thanks");
  thanks.hidden = true;
  const heading = new FakeElement("thanks-heading");
  heading.doc = doc;
  thanks.children.h2 = heading;
  add("form-alert").hidden = true;
  add("form-alert-reason").textContent = "Das hat leider nicht geklappt.";
  add("form-status");
  add("form-submit").textContent = "Senden";
  add("website");
  for (const id of ["firstname", "lastname", "email", "message"]) {
    add(id);
    const err = add(`err-${id}`);
    err.hidden = true;
    err.children[".msg"] = new FakeElement(`msg-${id}`);
  }
  return { els, doc, heading };
}

function fill(els, values) {
  for (const [id, value] of Object.entries(values)) els[id].value = value;
}

const VALID = {
  firstname: "Maria",
  lastname: "Huber",
  email: "maria.huber@example.com",
  message: "Passt der EquiCube in unser Haus?",
};

const respond = (status) => async () => ({ status, ok: status >= 200 && status < 300 });

function errorShown(els, id) {
  return !els[`err-${id}`].hidden && els[id].getAttribute("aria-invalid") === "true";
}

// ---------- sendContact ----------

test("sendContact posts the payload as JSON to API_BASE/api/contact", async () => {
  const calls = [];
  const payload = { first_name: "M", last_name: "H", email: "m@h.at", message: "Hi", website: "" };
  const result = await sendContact(
    payload,
    async (url, init) => {
      calls.push({ url, init });
      return { status: 200, ok: true };
    },
    "http://api.test",
  );
  assert.deepEqual(result, { ok: true, status: 200 });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://api.test/api/contact");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(calls[0].init.body), payload);
});

test("sendContact uses the same origin when API_BASE is empty", async () => {
  let seen;
  await sendContact({}, async (url) => {
    seen = url;
    return { status: 200 };
  }, "");
  assert.equal(seen, "/api/contact");
});

for (const [status, reason] of [
  [422, "invalid"],
  [413, "too-large"],
  [429, "rate-limit"],
  [503, "unavailable"],
  [500, "error"],
]) {
  test(`sendContact maps ${status} to "${reason}"`, async () => {
    assert.deepEqual(await sendContact({}, respond(status), ""), { ok: false, status, reason });
  });
}

test("sendContact reports a network failure instead of throwing", async () => {
  const result = await sendContact({}, async () => {
    throw new TypeError("Failed to fetch");
  }, "");
  assert.deepEqual(result, { ok: false, status: null, reason: "network" });
});

// ---------- page behaviour ----------

test("returns null on a page without the contact form", () => {
  assert.equal(initContactForm({ getElementById: () => null }), null);
});

test("an untouched form shows no errors, even after a blur", () => {
  const { els, doc } = makePage();
  initContactForm(doc, { fetchImpl: respond(200), apiBase: "" });
  for (const id of ["firstname", "lastname", "email", "message"]) {
    els[id].dispatch("blur");
    assert.equal(els[`err-${id}`].hidden, true, id);
    assert.equal(els[id].getAttribute("aria-invalid"), null, id);
  }
});

test("a touched field left invalid shows its German error; fixing it clears it", () => {
  const { els, doc } = makePage();
  initContactForm(doc, { fetchImpl: respond(200), apiBase: "" });
  els.email.value = "maria.huber@";
  els.email.dispatch("input");
  assert.equal(errorShown(els, "email"), false, "no error while typing");
  els.email.dispatch("blur");
  assert.ok(errorShown(els, "email"));
  assert.equal(els["err-email"].children[".msg"].textContent, "Bitte gib eine gültige E-Mail-Adresse ein.");
  els.email.value = "maria.huber@example.com";
  els.email.dispatch("input");
  assert.equal(errorShown(els, "email"), false);
});

test("submitting the empty form shows every error and sends nothing", async () => {
  const { els, doc } = makePage();
  let calls = 0;
  const handle = initContactForm(doc, {
    fetchImpl: async () => {
      calls += 1;
      return { status: 200 };
    },
    apiBase: "",
  });
  let prevented = false;
  await Promise.all(els["contact-form"].dispatch("submit", { preventDefault: () => (prevented = true) }));
  assert.ok(prevented);
  assert.equal(calls, 0);
  for (const id of ["firstname", "lastname", "email", "message"]) assert.ok(errorShown(els, id), id);
  assert.equal(els["err-firstname"].children[".msg"].textContent, "Bitte gib deinen Vornamen ein.");
  assert.equal(doc.activeElement, els.firstname);
  assert.ok(handle);
});

test("pending: the button is disabled with is-loading while the request runs", async () => {
  const { els, doc } = makePage();
  let release;
  const handle = initContactForm(doc, {
    fetchImpl: () => new Promise((resolve) => (release = () => resolve({ status: 200 }))),
    apiBase: "",
  });
  fill(els, VALID);
  const done = handle.submit();
  const button = els["form-submit"];
  assert.equal(button.disabled, true);
  assert.ok(button.classList.contains("is-loading"));
  assert.equal(button.getAttribute("aria-busy"), "true");
  assert.equal(button.textContent, SENDING_LABEL);
  assert.notEqual(els["form-status"].textContent, "");
  await handle.submit(); // a second press while pending sends nothing more
  release();
  await done;
  assert.equal(button.disabled, false);
  assert.equal(button.classList.contains("is-loading"), false);
  assert.equal(button.textContent, "Senden");
});

test("200: the thanks state replaces the sheet, with the trimmed contract payload sent", async () => {
  const { els, doc, heading } = makePage();
  let body;
  const handle = initContactForm(doc, {
    fetchImpl: async (_url, init) => {
      body = JSON.parse(init.body);
      return { status: 200 };
    },
    apiBase: "",
  });
  fill(els, { ...VALID, firstname: "  Maria " });
  await handle.submit();
  assert.deepEqual(body, {
    first_name: "Maria",
    last_name: "Huber",
    email: "maria.huber@example.com",
    message: "Passt der EquiCube in unser Haus?",
    website: "",
  });
  assert.equal(els["contact-sheet"].hidden, true);
  assert.equal(els["contact-thanks"].hidden, false);
  assert.equal(doc.activeElement, heading);
});

for (const [label, fetchImpl, reason] of [
  ["422", respond(422), "invalid"],
  ["429", respond(429), "rate-limit"],
  ["503", respond(503), "unavailable"],
  [
    "network failure",
    async () => {
      throw new TypeError("Failed to fetch");
    },
    "network",
  ],
]) {
  test(`${label}: the alert names the reason, the input stays, the button is usable again`, async () => {
    const { els, doc } = makePage();
    const handle = initContactForm(doc, { fetchImpl, apiBase: "" });
    fill(els, VALID);
    await handle.submit();
    assert.equal(els["form-alert"].hidden, false);
    assert.equal(els["form-alert-reason"].textContent, ALERT_TEXTS[reason]);
    assert.equal(doc.activeElement, els["form-alert"]);
    assert.equal(els["contact-sheet"].hidden, false);
    assert.equal(els["contact-thanks"].hidden, true);
    for (const [id, value] of Object.entries(VALID)) assert.equal(els[id].value, value, id);
    assert.equal(els["form-submit"].disabled, false);
    // A new attempt hides the old alert first.
    els.message.value = "";
    await handle.submit();
    assert.equal(els["form-alert"].hidden, true);
  });
}

// ---------- the page document ----------

test("kontakt/index.html carries the form the script drives", () => {
  const html = readFileSync(join(SITE, "kontakt/index.html"), "utf8");
  for (const id of [
    "contact-form", "contact-sheet", "contact-thanks", "form-alert", "form-alert-reason",
    "form-status", "form-submit", "website", "firstname", "lastname", "email", "message",
    "err-firstname", "err-lastname", "err-email", "err-message",
  ]) {
    assert.ok(html.includes(`id="${id}"`), `missing #${id}`);
  }
  for (const name of ["first_name", "last_name", "email", "message"]) {
    assert.ok(html.includes(`name="${name}"`), `missing field ${name}`);
  }
  assert.match(html, /<a class="value" href="mailto:office@equicrew\.com">/);
  assert.match(html, /<a class="value tnum" href="tel:\+436504593129">\+43 650 4593 129<\/a>/);
  assert.match(html, /<div class="hp" aria-hidden="true">[\s\S]*name="website"/);
  assert.match(html, /aria-live="polite"/);
  assert.match(html, /<script type="module" src="\/js\/contact-form\.js"><\/script>/);
  // The form-alert names the address to write to.
  assert.match(html, /id="form-alert"[\s\S]*?mailto:office@equicrew\.com[\s\S]*?<\/div>/);
  // The privacy note with its link to /datenschutz/ comes right before the send button.
  const note = html.indexOf('class="privacy-note"');
  const button = html.indexOf('id="form-submit"');
  assert.ok(note > 0 && note < button);
  assert.match(html.slice(note, button), /href="\/datenschutz\/"/);
  assert.equal(html.slice(note, button).match(/<(input|textarea)\b/), null);
  assert.match(html, /<h2 tabindex="-1">Danke für deine Nachricht!<\/h2>/);
});

test("the contact scripts never write HTML", () => {
  for (const file of ["js/contact-form.js", "js/validation.js"]) {
    const src = readFileSync(join(SITE, file), "utf8");
    assert.doesNotMatch(src, /innerHTML|outerHTML|insertAdjacentHTML|document\.write/, file);
  }
});
