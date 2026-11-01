// Pure validation of the contact form fields (js/validation.js) against the
// limits of the API contract.
import { test } from "node:test";
import assert from "node:assert/strict";

import { INVALID_EMAIL, isValidEmail, validateContact, validateField } from "../js/validation.js";

const VALID = {
  first_name: "Maria",
  last_name: "Huber",
  email: "maria.huber@example.com",
  message: "Passt der EquiCube in unser Haus?",
};

test("a complete form has no errors", () => {
  assert.deepEqual(validateContact(VALID), {});
});

test("an empty form names every required field in German", () => {
  const errors = validateContact({});
  assert.deepEqual(errors, {
    first_name: "Bitte gib deinen Vornamen ein.",
    last_name: "Bitte gib deinen Nachnamen ein.",
    email: "Bitte gib deine E-Mail-Adresse ein.",
    message: "Bitte schreib uns eine Nachricht.",
  });
});

test("whitespace only counts as empty", () => {
  assert.equal(validateField("first_name", "   "), "Bitte gib deinen Vornamen ein.");
  assert.equal(validateField("message", "\n\t "), "Bitte schreib uns eine Nachricht.");
});

test("names are limited to 100 characters", () => {
  assert.equal(validateField("first_name", "a".repeat(100)), "");
  assert.match(validateField("first_name", "a".repeat(101)), /höchstens 100 Zeichen/);
  assert.match(validateField("last_name", "ä".repeat(101)), /höchstens 100 Zeichen/);
});

test("single-line fields reject CR and LF", () => {
  assert.match(validateField("first_name", "Maria\nBcc: x"), /Zeilenumbruch/);
  assert.match(validateField("last_name", "Huber\r"), /Zeilenumbruch/);
  assert.match(validateField("email", "a@b.at\r\nBcc: c@d.at"), /Zeilenumbruch/);
});

test("the message may hold line breaks and is limited to 5000 characters", () => {
  assert.equal(validateField("message", "Zeile 1\nZeile 2"), "");
  assert.equal(validateField("message", "x".repeat(5000)), "");
  assert.match(validateField("message", "x".repeat(5001)), /höchstens 5000 Zeichen/);
});

test("e-mail addresses are checked for shape and length", () => {
  for (const ok of ["maria.huber@example.com", "a+b@sub.example.at", "office@equicrew.com"]) {
    assert.ok(isValidEmail(ok), ok);
  }
  for (const bad of ["maria.huber@", "@example.com", "maria", "a@b", "a@@b.at", "a b@c.at", "a@-b.at", "a..b@c.at"]) {
    assert.equal(isValidEmail(bad), false, bad);
  }
  assert.equal(validateField("email", "maria.huber@"), INVALID_EMAIL);
  assert.match(validateField("email", `${"a".repeat(60)}@${"b".repeat(200)}.at`), /höchstens 254 Zeichen/);
});

test("unknown fields are never an error", () => {
  assert.equal(validateField("website", ""), "");
});
