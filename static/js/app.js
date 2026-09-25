document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-confirm]").forEach((el) => {
    el.addEventListener("submit", (event) => {
      if (!window.confirm(el.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });
});
