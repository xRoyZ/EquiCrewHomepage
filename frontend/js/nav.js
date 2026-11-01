// Mobile navigation (menu button) of the site header.
//
// Open state: class "is-open" on #site-nav plus aria-expanded="true" on the
// .nav-toggle (aria-controls="site-nav"). components.css folds the navigation
// behind the button up to 900 px and swaps icon-open/icon-close from
// aria-expanded. The button is a <button>, so Enter and Space operate it.
// Escape closes the open menu and returns focus to the button; following a
// link closes it as well. Widening the window to the desktop layout closes it.

const OPEN_CLASS = "is-open";
const DESKTOP_QUERY = "(min-width: 901px)";

export function initNav() {
  if (typeof document === "undefined") return;
  const nav = document.getElementById("site-nav");
  const toggle = document.querySelector('.nav-toggle[aria-controls="site-nav"]');
  if (!nav || !toggle) return;

  const isOpen = () => toggle.getAttribute("aria-expanded") === "true";
  const setOpen = (open) => {
    nav.classList.toggle(OPEN_CLASS, open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  };

  // Start from one consistent, closed state whatever the markup says.
  setOpen(false);

  toggle.addEventListener("click", () => {
    setOpen(!isOpen());
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !isOpen()) return;
    setOpen(false);
    toggle.focus();
  });

  nav.addEventListener("click", (event) => {
    const target = event.target;
    const link = target && typeof target.closest === "function" ? target.closest("a[href]") : null;
    if (link && isOpen()) setOpen(false);
  });

  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    const desktop = window.matchMedia(DESKTOP_QUERY);
    if (typeof desktop.addEventListener === "function") {
      desktop.addEventListener("change", (event) => {
        if (event.matches) setOpen(false);
      });
    }
  }
}
