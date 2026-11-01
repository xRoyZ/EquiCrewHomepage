(function () {
  var form = document.getElementById("contact-form");
  if (!form) return;

  var sheet = document.getElementById("contact-sheet");
  var thanks = document.getElementById("contact-thanks");
  var alertBox = document.getElementById("form-alert");
  var submitBtn = document.getElementById("form-submit");
  var idleLabel = submitBtn.textContent;
  var fields = ["firstname", "lastname", "email", "message"];
  var messages = {
    firstname: "Bitte gib deinen Vornamen ein.",
    lastname: "Bitte gib deinen Nachnamen ein.",
    email: "Bitte gib eine gültige E-Mail-Adresse ein.",
    message: "Bitte schreib uns eine Nachricht."
  };
  var touched = {};
  var emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function valid(name) {
    var value = form.elements[name].value.trim();
    if (!value) return false;
    if (name === "email") return emailPattern.test(value);
    return true;
  }

  function show(name, isError) {
    var input = form.elements[name];
    var err = document.getElementById("err-" + name);
    if (isError) {
      input.setAttribute("aria-invalid", "true");
      err.hidden = false;
      err.querySelector(".msg").textContent = messages[name];
    } else {
      input.removeAttribute("aria-invalid");
      err.hidden = true;
    }
  }

  fields.forEach(function (name) {
    var input = form.elements[name];
    input.addEventListener("input", function () {
      touched[name] = true;
      if (input.getAttribute("aria-invalid") === "true" && valid(name)) show(name, false);
    });
    input.addEventListener("blur", function () {
      if (touched[name]) show(name, !valid(name));
    });
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    alertBox.hidden = true;
    var firstInvalid = null;
    fields.forEach(function (name) {
      var bad = !valid(name);
      show(name, bad);
      if (bad && !firstInvalid) firstInvalid = form.elements[name];
    });
    if (firstInvalid) {
      firstInvalid.focus();
      return;
    }
    if (form.elements.website.value) {
      // honeypot filled: the server answers success silently
      sheet.hidden = true;
      thanks.hidden = false;
      return;
    }

    submitBtn.disabled = true;
    submitBtn.setAttribute("aria-busy", "true");
    submitBtn.textContent = "Wird gesendet …";

    var payload = {
      firstname: form.elements.firstname.value.trim(),
      lastname: form.elements.lastname.value.trim(),
      email: form.elements.email.value.trim(),
      message: form.elements.message.value.trim(),
      website: form.elements.website.value
    };

    fetch("/api/contact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (res) {
        if (!res.ok) throw new Error("send failed");
        sheet.hidden = true;
        thanks.hidden = false;
      })
      .catch(function () {
        alertBox.hidden = false;
        submitBtn.disabled = false;
        submitBtn.removeAttribute("aria-busy");
        submitBtn.textContent = idleLabel;
        alertBox.focus();
      });
  });
})();
