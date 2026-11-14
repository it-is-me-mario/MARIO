/* Links and definitions remain available in the static document. */
document.addEventListener("DOMContentLoaded", () => {
  const legacyLink = Array.from(document.querySelectorAll("[data-format-legacy-links] a"))
    .find((link) => `#${link.id}` === window.location.hash);
  if (legacyLink) {
    window.location.replace(legacyLink.href);
    return;
  }
  document.querySelectorAll("[data-table-map]").forEach((map) => {
    const definitions = Array.from(map.querySelectorAll("[data-matrix-definition]"));
    const controls = map.querySelector(".table-map__controls");
    const scroll = map.querySelector(".table-map__scroll");
    if (!definitions.length || !controls || !scroll) return;
    const fields = Object.fromEntries(Array.from(controls.querySelectorAll("select"))
      .map((select) => [select.dataset.config, select]));
    const links = () => Array.from(scroll.querySelectorAll("[data-matrix-link]"));
    let selected = "";
    const select = (id) => {
      if (!definitions.some((node) => node.id === id)) return;
      selected = id;
      definitions.forEach((node) => { node.hidden = node.id !== id; });
      links().forEach((link) => {
        if (link.dataset.matrixLink === id) link.setAttribute("aria-current", "true");
        else link.removeAttribute("aria-current");
      });
    };
    const draw = () => {
      const multi = fields.scope.value === "multi-region";
      const trade = multi ? (fields.trade?.value || "bilateral") : "external-trade";
      const imports = multi ? "factor-accounts" : fields.imports.value;
      const key = `${fields.scope.value}/${trade}/${imports}/${fields.mode.value}`;
      const template = Array.from(map.querySelectorAll("[data-config-grid]"))
        .find((node) => node.dataset.configGrid === key);
      if (!template) return;
      scroll.replaceChildren(template.content.cloneNode(true));
      map.classList.toggle("is-multiregional", multi);
      map.querySelector("[data-import-control]").hidden = multi;
      const tradeControl = map.querySelector("[data-trade-control]");
      if (tradeControl) tradeControl.hidden = !multi;
      map.querySelector("[data-regional-legend]").hidden = !multi;
      map.querySelector("[data-config-explanation]").textContent = multi
        ? (trade === "bilateral"
          ? "Sector regions identify suppliers and buyers. Transactions and final demand can cross regional borders."
          : trade === "chenery-moses"
          ? "Commodity regions identify destination markets. Supply carries bilateral trade."
          : "Commodity regions identify origins. Use and final demand can cross regional borders.")
        : (imports === "separate"
          ? "Imports have their own blocks and share existing origin and item descriptors."
          : "The factor accounts include external imports.");
      select(links().some((link) => link.dataset.matrixLink === selected)
        ? selected : links()[0].dataset.matrixLink);
    };
    map.classList.add("is-enhanced");
    controls.hidden = false;
    controls.addEventListener("change", draw);
    draw();
    const followHash = () => {
      const id = window.location.hash.slice(1);
      if (/^matrix-(IMP|imp)/.test(id)) {
        fields.scope.value = "single-region";
        fields.imports.value = "separate";
        fields.mode.value = id.startsWith("matrix-imp") ? "coefficients" : "flows";
        draw();
      }
      select(id);
    };
    followHash();
    map.addEventListener("click", (event) => {
      const link = event.target.closest("[data-matrix-link]");
      if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      select(link.dataset.matrixLink);
      window.history.replaceState(null, "", link.hash);
    });
    window.addEventListener("hashchange", followHash);
  });
});
