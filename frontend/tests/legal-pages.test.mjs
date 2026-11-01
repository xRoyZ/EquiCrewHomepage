// Static checks of the imprint and privacy pages: the legally required facts
// are in the HTML documents themselves (readable without JavaScript).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");

function mainOf(page) {
  const html = readFileSync(join(SITE, page, "index.html"), "utf8");
  const match = html.match(/<main\b[^>]*>([\s\S]*?)<\/main>/);
  assert.ok(match, `${page} has a <main>`);
  return match[1];
}

test("Impressum lists the ECG/UGB/MedienG details", () => {
  const main = mainOf("impressum");
  for (const fact of [
    "EquiCrew FlexCo",
    "Flexible Kapitalgesellschaft",
    "Marktplatz 14",
    "4310 Mauthausen",
    'href="tel:+436504593129"',
    'href="mailto:office@equicrew.com"',
    "FN 648043 f",
    "Firmenbuchgericht",
    "Wien",
    "ATU82132979",
    "Unternehmensgegenstand",
    "Michael Hochstöger",
    "Christian Hinterdorfer",
    "Christian Hinterreiter",
    "Bezirkshauptmannschaft Perg",
    "Wirtschaftskammer Oberösterreich",
    "§ 25 MedienG",
    "Medieninhaber",
    "Grundlegende Richtung",
  ]) {
    assert.ok(main.includes(fact), `Impressum names ${fact}`);
  }
});

test("Datenschutz covers Art. 13 DSGVO as the product is built", () => {
  const main = mainOf("datenschutz");
  for (const fact of [
    "Verantwortlicher",
    "EquiCrew FlexCo",
    'href="mailto:office@equicrew.com"',
    "Vorname, Nachname, E-Mail und Nachricht",
    "Art. 6 Abs. 1 lit. b/f DSGVO",
    "Postfach",
    "E-Mail-/SMTP-Anbieter",
    "Server-Logs",
    "Arbeitsspeicher",
    "Drittland",
    "Art. 15–21 DSGVO",
    "Datenschutzbehörde",
  ]) {
    assert.ok(main.includes(fact), `Datenschutz names ${fact}`);
  }
});

test("every page's footer links the privacy page", () => {
  for (const page of ["impressum", "datenschutz"]) {
    const html = readFileSync(join(SITE, page, "index.html"), "utf8");
    assert.match(html, /class="footer-links"[\s\S]*href="\/datenschutz\/"/);
  }
});
