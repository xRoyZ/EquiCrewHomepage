// Behaviour of the mobile navigation (js/nav.js) against a minimal fake DOM:
// the menu button opens and closes #site-nav, Escape closes it and returns
// focus to the button, a link click closes it. Plus a static check that the
// kit's stylesheet folds the navigation and swaps the icons on that state.
import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { initNav } from "../js/nav.js";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");

class FakeElement {
  constructor(tag, attrs = {}) {
    this.tag = tag;
    this.attrs = { ...attrs };
    this.classes = new Set();
    this.listeners = {};
    this.parent = null;
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
  addEventListener(type, fn) {
    (this.listeners[type] ??= []).push(fn);
  }
  dispatch(type, event = {}) {
    for (const fn of this.listeners[type] ?? []) fn({ type, target: this, ...event });
  }
  closest(selector) {
    for (let el = this; el; el = el.parent) {
      if (selector === "a[href]" && el.tag === "a" && el.getAttribute("href") !== null) return el;
    }
    return null;
  }
  focus() {
    globalThis.document.activeElement = this;
  }
}

let nav;
let toggle;
let link;
let mediaListeners;

beforeEach(() => {
  toggle = new FakeElement("button", { "aria-expanded": "false", "aria-controls": "site-nav" });
  nav = new FakeElement("nav", { id: "site-nav" });
  link = new FakeElement("a", { href: "/kontakt/" });
  link.parent = nav;
  const docListeners = {};
  globalThis.document = {
    activeElement: null,
    getElementById: (id) => (id === "site-nav" ? nav : null),
    querySelector: (sel) => (sel === '.nav-toggle[aria-controls="site-nav"]' ? toggle : null),
    addEventListener: (type, fn) => (docListeners[type] ??= []).push(fn),
    dispatch: (type, event) => {
      for (const fn of docListeners[type] ?? []) fn(event);
    },
  };
  mediaListeners = [];
  globalThis.window = {
    matchMedia: () => ({ addEventListener: (_type, fn) => mediaListeners.push(fn) }),
  };
  initNav();
});

afterEach(() => {
  delete globalThis.document;
  delete globalThis.window;
});

const isOpen = () => nav.classList.contains("is-open") && toggle.getAttribute("aria-expanded") === "true";
const isClosed = () => !nav.classList.contains("is-open") && toggle.getAttribute("aria-expanded") === "false";

test("starts closed and the button toggles the open state", () => {
  assert.ok(isClosed());
  toggle.dispatch("click");
  assert.ok(isOpen());
  toggle.dispatch("click");
  assert.ok(isClosed());
});

test("Escape closes the open menu and returns focus to the button", () => {
  toggle.dispatch("click");
  globalThis.document.dispatch("keydown", { key: "Escape" });
  assert.ok(isClosed());
  assert.equal(globalThis.document.activeElement, toggle);
});

test("Escape while closed and other keys change nothing", () => {
  globalThis.document.dispatch("keydown", { key: "Escape" });
  assert.ok(isClosed());
  assert.equal(globalThis.document.activeElement, null);
  toggle.dispatch("click");
  globalThis.document.dispatch("keydown", { key: "Tab" });
  assert.ok(isOpen());
});

test("following a link closes the menu", () => {
  toggle.dispatch("click");
  nav.dispatch("click", { target: link });
  assert.ok(isClosed());
});

test("widening to the desktop layout closes the menu", () => {
  toggle.dispatch("click");
  for (const fn of mediaListeners) fn({ matches: true });
  assert.ok(isClosed());
});

test("does nothing on a page without the header navigation", () => {
  globalThis.document.getElementById = () => null;
  assert.doesNotThrow(() => initNav());
});

test("components.css folds the navigation on the open state the script sets", () => {
  const css = readFileSync(join(SITE, "css/components.css"), "utf8");
  assert.match(css, /@media \(max-width: 900px\) and \(scripting: enabled\)/);
  assert.match(css, /\.site-nav\.is-open \{ display: block; \}/);
  assert.match(css, /\.nav-toggle\[aria-expanded="true"\] \.icon-open \{ display: none; \}/);
  assert.match(css, /\.nav-toggle:not\(\[aria-expanded="true"\]\) \.icon-close \{ display: none; \}/);
});
