// Pure validation of the contact form, with the limits of the API contract
// (POST /api/contact): first_name / last_name 1-100 characters, email a valid
// address of at most 254 characters, message 1-5000 characters; the three
// single-line fields never contain CR or LF. Every message is German and is
// meant to be shown beside its field.

export const FIELDS = ["first_name", "last_name", "email", "message"];

export const LIMITS = Object.freeze({
  first_name: 100,
  last_name: 100,
  email: 254,
  message: 5000,
});

const REQUIRED = Object.freeze({
  first_name: "Bitte gib deinen Vornamen ein.",
  last_name: "Bitte gib deinen Nachnamen ein.",
  email: "Bitte gib deine E-Mail-Adresse ein.",
  message: "Bitte schreib uns eine Nachricht.",
});

const TOO_LONG = Object.freeze({
  first_name: "Der Vorname darf höchstens 100 Zeichen lang sein.",
  last_name: "Der Nachname darf höchstens 100 Zeichen lang sein.",
  email: "Die E-Mail-Adresse darf höchstens 254 Zeichen lang sein.",
  message: "Die Nachricht darf höchstens 5000 Zeichen lang sein.",
});

const LINE_BREAK = Object.freeze({
  first_name: "Der Vorname darf keinen Zeilenumbruch enthalten.",
  last_name: "Der Nachname darf keinen Zeilenumbruch enthalten.",
  email: "Die E-Mail-Adresse darf keinen Zeilenumbruch enthalten.",
});

export const INVALID_EMAIL = "Bitte gib eine gültige E-Mail-Adresse ein.";

// local@domain.tld: no whitespace, exactly one "@", a dotted domain whose
// labels are letters/digits/hyphens and do not start or end with a hyphen.
const LOCAL_PART = /^[^\s@"(),:;<>[\\\]]+$/;
const DOMAIN_LABEL = /^[\p{L}\p{N}](?:[\p{L}\p{N}-]*[\p{L}\p{N}])?$/u;

/** Length in characters (code points), the way the API counts it. */
export function charCount(value) {
  return [...String(value ?? "")].length;
}

/** True when the value looks like a deliverable e-mail address. */
export function isValidEmail(value) {
  const text = String(value ?? "");
  const at = text.indexOf("@");
  if (at <= 0 || at !== text.lastIndexOf("@")) return false;
  const local = text.slice(0, at);
  const domain = text.slice(at + 1);
  if (charCount(local) > 64 || !LOCAL_PART.test(local)) return false;
  if (local.startsWith(".") || local.endsWith(".") || local.includes("..")) return false;
  const labels = domain.split(".");
  if (labels.length < 2) return false;
  if (!labels.every((label) => DOMAIN_LABEL.test(label))) return false;
  return /^\p{L}{2,}$/u.test(labels[labels.length - 1]) || /^xn--/.test(labels[labels.length - 1]);
}

/** The value as it is sent: single-line fields trimmed, the message trimmed at its ends. */
export function normalize(value) {
  return String(value ?? "").trim();
}

/**
 * Validate one field. Returns the German error message, or "" when valid.
 * Unknown field names are never an error.
 */
export function validateField(name, value) {
  if (!(name in REQUIRED)) return "";
  const raw = String(value ?? "");
  const text = normalize(raw);
  if (text === "") return REQUIRED[name];
  if (name in LINE_BREAK && /[\r\n]/.test(raw)) return LINE_BREAK[name];
  if (charCount(text) > LIMITS[name]) return TOO_LONG[name];
  if (name === "email" && !isValidEmail(text)) return INVALID_EMAIL;
  return "";
}

/**
 * Validate the whole form. `values` maps field names to their raw values.
 * Returns an object with one German message per invalid field; empty when
 * the form may be sent.
 */
export function validateContact(values) {
  const errors = {};
  for (const name of FIELDS) {
    const message = validateField(name, values?.[name]);
    if (message) errors[name] = message;
  }
  return errors;
}
