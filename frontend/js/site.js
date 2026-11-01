// Entry script of every page: fills in the current year in the footer and
// starts the mobile navigation. Loaded as a module, so it runs after parsing.
import { initNav } from "./nav.js";

const year = String(new Date().getFullYear());
for (const el of document.querySelectorAll("[data-current-year]")) {
  el.textContent = year;
}

initNav();
