// Starts frontend/dev_server.py on a free port and checks what it serves:
// pages as directory index.html, /js/config.js generated from API_BASE_URL,
// real 404s for tooling paths and for folders without index.html.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
const PYTHON = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");

let server;
let base;

function startServer(env) {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON, ["dev_server.py", "--port", "0"], {
      cwd: SITE,
      env: { ...process.env, ...env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let out = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`dev_server.py did not report its port: ${out}`));
    }, 15000);
    child.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`dev_server.py exited with ${code}: ${out}`));
    });
    child.stdout.on("data", (chunk) => {
      out += chunk;
      const m = out.match(/http:\/\/127\.0\.0\.1:(\d+)\//);
      if (m) {
        clearTimeout(timer);
        resolve({ child, base: `http://127.0.0.1:${m[1]}` });
      }
    });
    child.stderr.on("data", () => {}); // request log, not needed here
  });
}

before(async () => {
  ({ child: server, base } = await startServer({ API_BASE_URL: "http://127.0.0.1:8123/" }));
});

after(() => {
  if (server) {
    server.removeAllListeners("exit");
    server.kill();
  }
});

const get = (path) => fetch(base + path, { redirect: "manual" });

test("a page directory answers with its index.html", async () => {
  for (const path of ["/", "/kontakt/", "/datenschutz/"]) {
    const res = await get(path);
    assert.equal(res.status, 200, path);
    assert.match(res.headers.get("content-type"), /^text\/html/);
    assert.match(await res.text(), /<title>[^<]+<\/title>/);
  }
});

test("/js/config.js is generated from API_BASE_URL", async () => {
  const res = await get("/js/config.js");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /^text\/javascript/);
  const body = await res.text();
  assert.match(body, /export const API_BASE = "http:\/\/127\.0\.0\.1:8123";/);
});

test("tooling paths answer 404", async () => {
  for (const path of ["/dev_server.py", "/package.json", "/tests/site.test.mjs", "/.gitignore"]) {
    const res = await get(path);
    assert.equal(res.status, 404, path);
    await res.arrayBuffer();
  }
});

test("a folder without index.html is a real 404, not a listing", async () => {
  for (const path of ["/assets/", "/css/", "/js/"]) {
    const res = await get(path);
    assert.equal(res.status, 404, path);
    assert.doesNotMatch(await res.text(), /Directory listing/i, path);
  }
});

test("an unknown page is a 404 without fallback", async () => {
  const res = await get("/gibt-es-nicht/");
  assert.equal(res.status, 404);
  assert.doesNotMatch(await res.text(), /site-header/);
});

test("site files are served with their content type", async () => {
  const css = await get("/css/tokens.css");
  assert.equal(css.status, 200);
  assert.match(css.headers.get("content-type"), /^text\/css/);
  await css.arrayBuffer();
  const font = await get("/fonts/public-sans/public-sans-latin-wght-normal.woff2");
  assert.equal(font.status, 200);
  assert.equal(font.headers.get("content-type"), "font/woff2");
  await font.arrayBuffer();
});
