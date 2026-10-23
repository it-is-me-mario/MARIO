/* Native matrix links work without JS; enhancement shows one definition. */
document.addEventListener("DOMContentLoaded", () => {
  const legacyLink = Array.from(document.querySelectorAll("[data-format-legacy-links] a"))
    .find((link) => `#${link.id}` === window.location.hash);
  if (legacyLink) {
    window.location.replace(legacyLink.href);
    return;
  }
  document.querySelectorAll("[data-table-map]").forEach((map) => {
    const links = Array.from(map.querySelectorAll("[data-matrix-link]"));
    const definitions = Array.from(map.querySelectorAll("[data-matrix-definition]"));
    if (!links.length || links.some((link) => !definitions.some((node) => node.id === link.dataset.matrixLink))) return;
    const select = (id) => {
      if (!definitions.some((node) => node.id === id)) return;
      definitions.forEach((node) => { node.hidden = node.id !== id; });
      links.forEach((link) => {
        if (link.dataset.matrixLink === id) link.setAttribute("aria-current", "true");
        else link.removeAttribute("aria-current");
      });
    };
    map.classList.add("is-enhanced");
    select(links[0].dataset.matrixLink);
    select(window.location.hash.slice(1));
    links.forEach((link) => link.addEventListener("click", (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      select(link.dataset.matrixLink);
      window.history.replaceState(null, "", link.hash);
    }));
    window.addEventListener("hashchange", () => select(window.location.hash.slice(1)));
  });
});
