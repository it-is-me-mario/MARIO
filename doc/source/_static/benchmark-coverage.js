/* Coverage catalogue explorer. No database or external API is read in the browser. */
(() => {
  "use strict";
  const root = document.querySelector("[data-coverage]");
  if (!root) return;
  const profiles = JSON.parse(root.querySelector("[data-coverage-data]").textContent);
  const format = root.querySelector("[data-coverage-format]");
  const source = root.querySelector("[data-coverage-source]");
  const year = root.querySelector("[data-coverage-year]");
  const bars = root.querySelector("[data-coverage-bars]");
  const detail = root.querySelector("[data-coverage-profile]");
  const empty = root.querySelector("[data-coverage-empty]");
  let selected = null;
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);

  for (const value of [...new Set(profiles.map(p => p.source))].sort()) {
    source.add(new Option(value, value));
  }
  for (const value of [...new Set(profiles.flatMap(p => p.years))].sort().reverse()) {
    year.add(new Option(value, value));
  }

  function yearLabel(years) {
    if (!years.length) return "Not specified";
    if (!years.every(value => /^\d{4}$/.test(value))) return years.join(", ");
    const ranges = [];
    let start = years[0], end = start;
    const flush = () => ranges.push(start === end ? start : `${start}–${end}`);
    for (const value of years.slice(1)) {
      if (Number(value) === Number(end) + 1) end = value;
      else { flush(); start = end = value; }
    }
    flush();
    return ranges.join(", ");
  }

  function renderProfile(profile) {
    if (!profile) {
      detail.innerHTML = "<p>Select another format, source or year to explore the catalogue.</p>";
      return;
    }
    const geography = profile.geographies;
    const classification = profile.format === "SUT"
      ? "Activities and commodities" : "Sectors";
    detail.innerHTML = `<h3>${escape(profile.source)}</h3>
      <p class="benchmark-profile-version">${escape(profile.version || "Catalogue release")} · ${escape(profile.format)}</p>
      <dl class="benchmark-profile-metrics">
        <div><dt>Listed geographic entries</dt><dd>${geography.length}</dd></div>
        <div><dt>Catalogue years</dt><dd>${escape(yearLabel(profile.years))}</dd></div>
        <div><dt>${classification}</dt><dd>Awaiting parsed release</dd></div>
        <div><dt>Satellite accounts</dt><dd>Awaiting parsed release</dd></div>
      </dl>
      <a class="benchmark-parser-link" href="../notebooks/parsers/${encodeURIComponent(profile.parser_page)}/${profile.parser_page === "exiobase" ? (profile.version === "3.3.18" ? "hybrid" : "monetary") : "walkthrough_" + encodeURIComponent(profile.parser_page)}.html">Open parsing guide <span aria-hidden="true">↗</span></a>
      <details class="benchmark-geographies"><summary>Explore the listed geographies</summary>
        <ul>${geography.map(g => `<li><span>${escape(g.name)}</span><code>${escape(g.code)}</code></li>`).join("")}</ul>
      </details>`;
  }

  function render() {
    const visible = profiles.filter(p =>
      (format.value === "all" || p.format === format.value) &&
      (source.value === "all" || p.source === source.value) &&
      (year.value === "all" || p.years.includes(year.value))
    );
    if (!visible.some(p => p.id === selected)) selected = visible[0]?.id ?? null;
    const max = Math.max(1, ...visible.map(p => p.geographies.length));
    bars.innerHTML = visible.map(p => `<button type="button" class="benchmark-bar" data-profile="${escape(p.id)}" aria-pressed="${p.id === selected}">
      <span class="benchmark-bar-label"><strong>${escape(p.source)}</strong><span>${escape(p.version || "Catalogue release")} · ${escape(p.format)}</span></span>
      <span class="benchmark-bar-track" aria-hidden="true"><span style="width:${(p.geographies.length / max * 100).toFixed(2)}%"></span></span>
      <span class="benchmark-bar-value">${p.geographies.length}</span></button>`).join("");
    empty.hidden = visible.length > 0;
    renderProfile(visible.find(p => p.id === selected));
  }

  for (const control of [format, source, year]) control.addEventListener("change", render);
  bars.addEventListener("click", event => {
    const button = event.target.closest("[data-profile]");
    if (!button) return;
    selected = button.dataset.profile;
    // Retain keyboard focus when rebuilding the controls.
    const restoreFocus = document.activeElement === button;
    render();
    if (restoreFocus) bars.querySelector(`[data-profile="${selected}"]`)?.focus({preventScroll: true});
  });
  render();
})();
