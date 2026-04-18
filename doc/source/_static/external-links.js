document.addEventListener("DOMContentLoaded", function () {
  document
    .querySelectorAll('a[href^="http://"], a[href^="https://"]')
    .forEach(function (link) {
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    });
});
