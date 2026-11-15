/* Native home links remain available while matching pages are resolved. */
(function () {
  function updateLinks(menu, catalogue, location) {
    const page = menu.dataset.document;
    let anchor = location.hash.slice(1);
    try { anchor = decodeURIComponent(anchor); } catch (error) { /* Keep literal fragments. */ }
    menu.querySelectorAll("a[data-docs-version]").forEach((link) => {
      const version = catalogue.versions[link.dataset.docsVersion];
      const anchors = version.documents[page];
      const target = new URL(anchors ? page + ".html" : "index.html", version.url);
      if (anchors && anchors.includes(anchor)) target.hash = location.hash;
      link.href = target.href;
      link.target = "_self";
    });
  }

  if (typeof module === "object") module.exports = {updateLinks};
  if (typeof document === "undefined") return;
  const menu = document.querySelector("[data-docs-versions]");
  if (!menu) return;
  fetch(menu.dataset.catalogue)
    .then((response) => {
      if (!response.ok) throw new Error("Version catalogue unavailable");
      return response.json();
    })
    .then((catalogue) => {
      const refresh = () => updateLinks(menu, catalogue, window.location);
      refresh();
      window.addEventListener("hashchange", refresh);
    })
    .catch(() => { /* The native links continue to open each version's home. */ });
  document.addEventListener("click", (event) => {
    if (!menu.contains(event.target)) menu.open = false;
  });
  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      menu.open = false;
      menu.querySelector("summary").focus();
    }
  });
})();
