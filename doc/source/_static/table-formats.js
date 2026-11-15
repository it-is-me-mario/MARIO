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
      const resolution = fields.resolution.value;
      const detail = fields.detail.value;
      const baseKey = `${fields.scope.value}/${trade}/${imports}/${fields.mode.value}`;
      const key = multi ? baseKey : `${baseKey}/${resolution}/${detail}`;
      const template = Array.from(map.querySelectorAll("[data-config-grid]"))
        .find((node) => node.dataset.configGrid === key);
      if (!template) return;
      scroll.replaceChildren(template.content.cloneNode(true));
      map.classList.toggle("is-multiregional", multi);
      map.querySelectorAll("[data-import-control]").forEach((node) => { node.hidden = multi; });
      const tradeControl = map.querySelector("[data-trade-control]");
      if (tradeControl) tradeControl.hidden = !multi;
      map.querySelector("[data-regional-legend]").hidden = !multi;
      const importLegend = map.querySelector("[data-import-legend]");
      importLegend.hidden = multi;
      const itemNames = { sector: "S1/S2 represent imported sectors.",
        commodity: "C1/C2 represent imported commodities.",
        activity: "A1/A2 represent foreign producing activities." };
      importLegend.textContent = ["Yellow rows identify imports.",
        resolution === "by_region" ? "F1/F2 represent foreign import origins and export partners." : "Foreign partners are aggregated.",
        itemNames[detail] || "Total imports use one row per retained origin."].join(" ") + " ";
      const classifier = detail === "total" ? "" : detail[0].toUpperCase() + detail.slice(1);
      const descriptors = [classifier, resolution === "by_region" ? "Foreign region" : ""].filter(Boolean);
      const importAxis = descriptors.join(" × ") || "One total-import row";
      const factors = new Set(["V", "v", "Va", "va", "Vc", "vc", "VY"]);
      definitions.forEach((definition) => {
        const rows = definition.querySelector("[data-row-indices]");
        const name = definition.id.replace("matrix-", "");
        rows.textContent = rows.dataset.defaultRows;
        if (!multi && /^(IMP|imp)/.test(name)) rows.textContent = importAxis;
        if (!multi && imports === "factor-accounts" && factors.has(name)) {
          rows.textContent = `Factor of production, followed by import rows (${importAxis}).`;
        }
      });
      map.querySelector("[data-config-explanation]").textContent = multi
        ? (trade === "bilateral"
          ? "Sector regions identify suppliers and buyers. Transactions and final demand can cross regional borders."
          : trade === "chenery-moses"
          ? "Commodity regions identify destination markets. Supply carries bilateral trade."
          : "Commodity regions identify origins. Use and final demand can cross regional borders.")
        : "Foreign-origin descriptors identify external suppliers. The model retains one endogenous region. Export partners follow trade_resolution.";
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
