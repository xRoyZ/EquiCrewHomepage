// Static checks of the six page documents: each is a real page with its own
// title and meta description, the shared header navigation with the current
// page marked, the shared footer, and only same-origin resources.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");

const PAGES = [
  { file: "index.html", path: "/", css: "home", nav: "/" },
  { file: "ueber-uns/index.html", path: "/ueber-uns/", css: "ueber-uns", nav: "/ueber-uns/" },
  { file: "equicube/index.html", path: "/equicube/", css: "equicube", nav: "/equicube/" },
  { file: "kontakt/index.html", path: "/kontakt/", css: "kontakt", nav: "/kontakt/" },
  { file: "impressum/index.html", path: "/impressum/", css: "impressum", nav: "/impressum/" },
  { file: "datenschutz/index.html", path: "/datenschutz/", css: "datenschutz", nav: null },
];

const NAV_LINKS = ["/", "/ueber-uns/", "/equicube/", "/kontakt/", "/impressum/"];
const FOOTER_LINKS = ["/kontakt/", "/datenschutz/", "/impressum/"];

const read = (file) => readFileSync(join(SITE, file), "utf8");

function region(html, tag, className) {
  const re = new RegExp(`<${tag}[^>]*class="${className}"[^>]*>([\\s\\S]*?)</${tag}>`);
  const m = html.match(re);
  assert.ok(m, `missing <${tag} class="${className}">`);
  return m[1];
}

function hrefs(fragment) {
  return [...fragment.matchAll(/<a\b[^>]*\bhref="([^"]*)"/g)].map((m) => m[1]);
}

function title(html) {
  const m = html.match(/<title>([^<]+)<\/title>/);
  return m ? m[1].trim() : "";
}

test("every page has its own non-empty title", () => {
  const titles = PAGES.map((p) => title(read(p.file)));
  for (const [i, t] of titles.entries()) assert.ok(t.length > 0, `${PAGES[i].file} has no title`);
  assert.equal(new Set(titles).size, PAGES.length, "titles must differ between pages");
});

for (const page of PAGES) {
  test(`${page.file}: head is German and describes the page`, () => {
    const html = read(page.file);
    assert.match(html, /<html lang="de">/);
    assert.match(html, /<meta name="description" content="[^"]{20,}">/);
    assert.ok(html.includes(`<link rel="canonical" href="https://www.equicrew.com${page.path}">`));
    assert.ok(html.includes(`<meta property="og:url" content="https://www.equicrew.com${page.path}">`));
    assert.match(html, /<meta property="og:title" content="[^"]+">/);
  });

  test(`${page.file}: header has the five nav links, own link marked`, () => {
    const nav = region(read(page.file), "nav", "site-nav");
    assert.deepEqual(hrefs(nav), NAV_LINKS);
    const current = [...nav.matchAll(/<a\b[^>]*aria-current="page"[^>]*>/g)].map(
      (m) => m[0].match(/href="([^"]*)"/)[1],
    );
    assert.deepEqual(current, page.nav ? [page.nav] : []);
  });

  test(`${page.file}: footer has year, address, mail and legal links`, () => {
    const html = read(page.file);
    const footer = region(html, "footer", "site-footer");
    assert.match(footer, /© <span data-current-year>\d{4}<\/span> EquiCrew FlexCo/);
    assert.ok(footer.includes("Marktplatz 14, 4310 Mauthausen"));
    assert.ok(footer.includes('href="mailto:office@equicrew.com"'));
    const links = hrefs(region(footer, "nav", "footer-links"));
    assert.deepEqual(links, FOOTER_LINKS);
  });

  test(`${page.file}: loads only same-origin resources that exist`, () => {
    const html = read(page.file);
    const refs = [
      ...[...html.matchAll(/<link\b[^>]*rel="stylesheet"[^>]*href="([^"]+)"/g)].map((m) => m[1]),
      ...[...html.matchAll(/<(?:script|img|source|iframe)\b[^>]*\bsrc="([^"]+)"/g)].map((m) => m[1]),
    ];
    // Resolve every reference the way the browser does, against the page URL.
    const origin = "https://www.equicrew.com";
    const urls = refs.map((ref) => new URL(ref, origin + page.path));
    const paths = urls.map((u) => u.pathname);
    assert.ok(paths.includes(`/css/pages/${page.css}.css`));
    assert.ok(paths.includes("/js/site.js"));
    for (const [i, url] of urls.entries()) {
      assert.equal(url.origin, origin, `${refs[i]} is not same-origin`);
      assert.ok(existsSync(join(SITE, url.pathname)), `${refs[i]} does not exist`);
    }
    assert.match(html, /<main id="main"/);
    assert.match(html, /<a class="skip-link" href="#main">/);
  });
}

test("font stylesheets only reference their own files", () => {
  for (const family of ["bricolage-grotesque", "public-sans", "azeret-mono"]) {
    const css = read(`fonts/${family}/font.css`);
    for (const m of css.matchAll(/url\("([^"]+)"\)/g)) {
      assert.ok(!/^[a-z]+:|^\/\//i.test(m[1]), `${m[1]} points to another host`);
      assert.ok(existsSync(join(SITE, "fonts", family, m[1])), `${m[1]} missing`);
    }
  }
});

test("site.js writes the current year into every [data-current-year]", async () => {
  const yearEls = [{ textContent: "2000" }, { textContent: "2000" }];
  const previous = globalThis.document;
  // Minimal document: only the footer year spans exist; header lookups find nothing.
  globalThis.document = {
    querySelectorAll: (sel) => (sel === "[data-current-year]" ? yearEls : []),
    querySelector: () => null,
    getElementById: () => null,
    addEventListener: () => {},
    removeEventListener: () => {},
  };
  try {
    await import("../js/site.js");
  } finally {
    globalThis.document = previous;
  }
  const year = String(new Date().getFullYear());
  for (const el of yearEls) assert.equal(el.textContent, year);
});
