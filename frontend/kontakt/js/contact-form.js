// The contact page loads /js/contact-form.js (an absolute path, served from
// frontend/js/contact-form.js). This module only re-exports that one
// implementation for anything that resolves the script relative to the page
// directory; importing it wires the form once, as module instances are shared.
export {
  ALERT_TEXTS,
  INPUT_IDS,
  SENDING_LABEL,
  initContactForm,
  sendContact,
} from "../../js/contact-form.js";
