document.addEventListener("DOMContentLoaded", function () {
  document
    .querySelectorAll('a[href^="http://"], a[href^="https://"]')
    .forEach(function (link) {
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    });

  if (!document.querySelector(".nbinput, .nboutput")) {
    return;
  }

  document
    .querySelectorAll("main.bd-main article img[src]")
    .forEach(function (image) {
      var src = image.getAttribute("src");

      if (!src || src.startsWith("data:") || image.closest("a")) {
        return;
      }

      var link = document.createElement("a");
      link.setAttribute("href", src);
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
      link.setAttribute("class", "notebook-image-link");

      image.parentNode.insertBefore(link, image);
      link.appendChild(image);
    });
});
