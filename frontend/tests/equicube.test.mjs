// Static checks of the EquiCube product page (AC-05, AC-12, AC-13, AC-40):
// the hero with the cube rendering, the enquiry button to the contact page,
// the four features with their sublines and all six advantages.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(SITE, "equicube/index.html"), "utf8");

const main = (() => {
  const m = html.match(/<main\b[^>]*>([\s\S]*?)<\/main>/);
  assert.ok(m, "missing <main>");
  return m[1];
})();

const text = (fragment) =>
  fragment
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();

function listItems(className) {
  const m = main.match(new RegExp(`<(ul|ol) class="${className}">([\\s\\S]*?)</\\1>`));
  assert.ok(m, `missing list .${className}`);
  return [...m[2].matchAll(/<li\b[^>]*>([\s\S]*?)<\/li>/g)].map((x) => x[1]);
}

test("hero shows the product description with the cube rendering", () => {
  assert.match(main, /<h1>EquiCube – Heiztechnikanlage für Einfamilienhäuser<\/h1>/);
  assert.match(main, /Luft-Wasser-Wärmepumpe, Batterie, PV, KI- und Server-Technik in einem\./);
  const img = main.match(/<img\b[^>]*>/);
  assert.ok(img, "missing cube image");
  const src = img[0].match(/\bsrc="([^"]+)"/)[1];
  assert.match(src, /equicube-offen-draft\.png$/);
  assert.ok(!/^[a-z]+:|^\/\//i.test(src), "image must come from the own origin");
  assert.ok(existsSync(join(SITE, "equicube", src)), `image file missing: ${src}`);
  const alt = img[0].match(/\balt="([^"]*)"/);
  assert.ok(alt && alt[1].includes("EquiCube"), "cube image needs a German alt text");
});

test("'Jetzt anfragen!' links to the contact page", () => {
  const a = main.match(/<a\b[^>]*href="([^"]*)"[^>]*>\s*Jetzt anfragen!\s*<\/a>/);
  assert.ok(a, "missing 'Jetzt anfragen!' link");
  assert.equal(a[1], "/kontakt/");
  assert.ok(existsSync(join(SITE, "kontakt/index.html")));
});

test("four features with their sublines", () => {
  const items = listItems("features");
  const expected = [
    ["Standardisierter Basis-Cube", "Ein einheitlicher Grundaufbau, auf dem jede Anlage gleich beginnt."],
    ["Modular anpassbar", "Die Komponenten lassen sich auf das jeweilige Haus abstimmen."],
    ["Für Fußboden- & Radiatorenheizung", "Passt zu Flächenheizungen ebenso wie zu Heizkörpern."],
    ["Heizleistung", "Genug Leistung für das ganze Einfamilienhaus."],
  ];
  assert.equal(items.length, 4);
  expected.forEach(([name, sub], i) => {
    assert.equal(text(items[i].match(/<h3>([\s\S]*?)<\/h3>/)[1]), name);
    assert.ok(text(items[i]).includes(sub), `subline missing for ${name}`);
  });
  assert.ok(text(items[3]).includes("bis 40 kW"), "heating output figure missing");
});

test("'Vorteile des EquiCubes' lists all six advantages", () => {
  assert.match(main, /<h2[^>]*>Vorteile des EquiCubes<\/h2>/);
  const items = listItems("advantages").map((li) => text(li.match(/<h3>([\s\S]*?)<\/h3>/)[1]));
  assert.deepEqual(items, [
    "Schnelle Installation",
    "Einfache Wartbarkeit",
    "Einfache Installation & Inbetriebnahme",
    "Abgestimmte Komponenten",
    "Heizungs- & Energiespeichersystem aus einer Hand",
    "Minimierter Platzbedarf",
  ]);
});
