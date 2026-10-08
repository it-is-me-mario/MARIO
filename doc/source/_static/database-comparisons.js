/* Geographic versions share region sets; Excel inventories retain economic variants. */
(() => {
  "use strict";
  const root = document.querySelector("[data-database-comparisons]");
  if (!root) return;
  const profiles = JSON.parse(root.querySelector("[data-comparison-profiles]").textContent);
  const prefix = root.dataset.root;
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
  const name = source => source === "Asian Development Bank" ? "ADB" : source;
  const sources = [...new Set(profiles.map(p => p.source))].sort();
  const downloads = prefix + "resources/material.html#database-set-downloads";
  const rows = profile => profile.geography.regions;
  const direct = (profile, iso3) => rows(profile).some(r => r.kind === "country" && r.iso3 === iso3);
  const aggregate = (profile, iso3) => rows(profile).some(r => r.kind === "aggregate" && (r.members || []).includes(iso3));
  const geographyKey = p => p.coverage_signatures?.geography || JSON.stringify(rows(p).map(r => r.label).sort());
  profiles.sort((a, b) => Number(b.year || 0) - Number(a.year || 0) || a.label.localeCompare(b.label));
  const versions = source => {
    const groups = new Map();
    for (const profile of profiles.filter(p => p.source === source)) {
      const key = geographyKey(profile);
      if (!groups.has(key)) groups.set(key, {key, profiles: []});
      groups.get(key).profiles.push(profile);
    }
    return [...groups.values()].map(group => {
      const releases = [...new Set(group.profiles.map(p => p.release).filter(Boolean))];
      const type = source === "EXIOBASE" ? (group.profiles.every(p => p.guide === "exiobase-hybrid") ? "Hybrid" : "Monetary") : "";
      group.label = [type, source === "FIGARO" ? "Eurostat snapshot" : releases.join(" / ") || name(source)].filter(Boolean).join(" · ");
      return group;
    });
  };
  if (!profiles.length) return;

  fetch(prefix + "_static/data/world-country-map.json").then(response => {
    if (!response.ok) throw new Error("Map asset unavailable");
    return response.json();
  }).then(world => {
    const countries = world.countries.filter(c => c.iso3 !== "ATA");
    const countryById = new Map(countries.map(c => [c.iso3, c]));
    const shapes = world.features.filter(f => countryById.has(f.iso3));
    let selectedCountry = countryById.has("ITA") ? "ITA" : countries[0].iso3;
    let selectedSource = "all";
    let selectedVersion = null;
    let selectedYear = "all";
    let view = "map";
    let query = "";
    const withinYear = p => selectedYear === "all" || String(p.year) === selectedYear;
    const withinVersion = p => selectedSource === "all" || geographyKey(p) === selectedVersion;
    const activeProfiles = () => profiles.filter(p => withinYear(p) && (selectedSource === "all" || p.source === selectedSource && withinVersion(p)));
    const relevantSources = () => [...new Set(activeProfiles().map(p => p.source))];
    const status = (source, iso3, pool = activeProfiles()) => {
      const selected = pool.filter(p => p.source === source);
      return selected.some(p => direct(p, iso3)) ? "direct" : selected.some(p => aggregate(p, iso3)) ? "aggregate" : "unspecified";
    };
    const coverageCount = iso3 => relevantSources().filter(source => status(source, iso3) === "direct").length;
    const coverageColor = count => {
      if (!count) return "var(--coverage-none)";
      const maximum = relevantSources().length;
      const fraction = maximum > 1 ? (count - 1) / (maximum - 1) : 0;
      return `color-mix(in srgb, var(--coverage-low) ${Math.round((1 - fraction) * 100)}%, var(--coverage-high))`;
    };
    root.insertAdjacentHTML("beforeend", `
      <div class="coverage-toolbar">
        <label>Explore a database<select data-coverage-database><option value="all">Compare all databases</option>${sources.map(s => `<option value="${escape(s)}">${escape(name(s))}</option>`).join("")}</select></label>
        <label data-coverage-version-label hidden>Version<select data-coverage-version></select></label>
        <label>Year<select data-coverage-year></select></label>
      </div>
      <div class="coverage-viewbar"><p data-coverage-headline></p><div class="coverage-view-buttons" role="group" aria-label="Coverage view">
        <button type="button" data-coverage-view="map" aria-pressed="true">Map</button><button type="button" data-coverage-view="list" aria-pressed="false">Country list</button>
      </div></div>
      <div data-coverage-map-panel>
        <div class="coverage-map-frame">
          <div class="coverage-map-controls" role="group" aria-label="Map zoom">
            <button type="button" data-map-zoom="in" aria-label="Zoom in" title="Zoom in">+</button>
            <button type="button" data-map-zoom="out" aria-label="Zoom out" title="Zoom out">−</button>
            <button type="button" data-map-zoom="reset" aria-label="Reset map view" title="Reset map view">↺</button>
          </div>
          <span class="coverage-zoom-status" data-map-zoom-status aria-live="polite"></span>
        <svg class="coverage-world-map" viewBox="${escape(world.viewbox)}" aria-label="Interactive country coverage map">
          <rect width="900" height="365" class="coverage-map-ocean"/>
          <g data-map-viewport>
          <path class="coverage-map-land" d="${world.features.map(f => f.path).join("")}"/>
          ${shapes.map(f => `<path d="${f.path}" data-map-country="${escape(f.iso3)}" role="button" tabindex="-1" aria-label="${escape(f.name)}"><title>${escape(f.name)}</title></path>`).join("")}
          <path class="coverage-border-mesh" d="${world.borders || ""}" aria-hidden="true"/>
          </g>
        </svg>
        <small class="coverage-map-credit">Map: <a href="${escape(world.source.url)}" target="_blank" rel="noopener">${escape(world.source.name)}</a></small>
        </div>
        <div class="coverage-map-legend" data-coverage-legend></div>
      </div>
      <div data-coverage-list-panel hidden>
        <label class="coverage-search">Find a country or ISO code<input type="search" data-coverage-search placeholder="e.g. Italy, ITA, Brazil…" autocomplete="off"></label>
        <div class="coverage-country-table" tabindex="0" role="region" aria-label="Country and database comparison"><table><thead data-coverage-table-head></thead><tbody data-coverage-table-body></tbody></table></div>
      </div>
      <div class="coverage-country-detail">
        <label>Which databases include this country as an individual region?<select data-coverage-country>${countries.map(c => `<option value="${escape(c.iso3)}">${escape(c.name)} (${escape(c.iso3)})</option>`).join("")}</select></label>
        <p class="coverage-database-names" data-coverage-country-results aria-live="polite"></p>
      </div>
      <div class="coverage-model-detail" data-coverage-model-detail></div>`);
    root.querySelector("[data-comparison-loading]").remove();
    const databaseControl = root.querySelector("[data-coverage-database]");
    const versionControl = root.querySelector("[data-coverage-version]");
    const yearControl = root.querySelector("[data-coverage-year]");
    const countryControl = root.querySelector("[data-coverage-country]");

    const map = root.querySelector(".coverage-world-map");
    const viewport = map.querySelector("[data-map-viewport]");
    let zoom = 1, panX = 0, panY = 0, drag = null, suppressClick = false;
    const width = 900, height = 365;
    function updateMapView() {
      panX = Math.max(width * (1 - zoom), Math.min(0, panX));
      panY = Math.max(height * (1 - zoom), Math.min(0, panY));
      viewport.setAttribute("transform", `translate(${panX} ${panY}) scale(${zoom})`);
      map.classList.toggle("is-zoomed", zoom > 1);
      root.querySelector('[data-map-zoom="out"]').disabled = zoom <= 1;
      root.querySelector('[data-map-zoom="in"]').disabled = zoom >= 8;
      root.querySelector('[data-map-zoom="reset"]').disabled = zoom === 1;
      root.querySelector("[data-map-zoom-status]").textContent = `Map zoom: ${zoom.toFixed(1)} times. ${zoom > 1 ? "Drag to move the map." : "World view."}`;
    }
    function changeZoom(next) {
      next = Math.max(1, Math.min(8, next));
      panX = width / 2 - (width / 2 - panX) * next / zoom;
      panY = height / 2 - (height / 2 - panY) * next / zoom;
      zoom = next;
      updateMapView();
    }
    for (const button of root.querySelectorAll("[data-map-zoom]")) {
      button.addEventListener("click", () => {
        if (button.dataset.mapZoom === "reset") { zoom = 1; panX = panY = 0; updateMapView(); }
        else changeZoom(zoom * (button.dataset.mapZoom === "in" ? 1.5 : 1 / 1.5));
      });
    }
    map.addEventListener("pointerdown", event => {
      if (zoom <= 1 || event.button !== 0 || !event.isPrimary) return;
      drag = {id: event.pointerId, x: event.clientX, y: event.clientY, panX, panY, moved: false};
    });
    map.addEventListener("pointermove", event => {
      if (!drag || event.pointerId !== drag.id) return;
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 4) return;
      if (!drag.moved) { drag.moved = true; map.setPointerCapture(event.pointerId); map.classList.add("is-dragging"); }
      const bounds = map.getBoundingClientRect();
      panX = drag.panX + dx * width / bounds.width;
      panY = drag.panY + dy * height / bounds.height;
      updateMapView();
    });
    const finishDrag = event => {
      if (!drag || event.pointerId !== drag.id) return;
      suppressClick = drag.moved;
      drag = null;
      if (map.hasPointerCapture(event.pointerId)) map.releasePointerCapture(event.pointerId);
      map.classList.remove("is-dragging");
      window.setTimeout(() => { suppressClick = false; }, 0);
    };
    map.addEventListener("pointerup", finishDrag);
    map.addEventListener("pointercancel", finishDrag);
    map.addEventListener("click", event => {
      if (suppressClick) { event.preventDefault(); event.stopPropagation(); }
    }, true);
    map.addEventListener("keydown", event => {
      if (event.ctrlKey || event.metaKey || !["+", "=", "-", "0"].includes(event.key)) return;
      event.preventDefault();
      if (event.key === "0") { zoom = 1; panX = panY = 0; updateMapView(); }
      else changeZoom(zoom * (event.key === "-" ? 1 / 1.5 : 1.5));
    });
    updateMapView();

    function updateYears() {
      const eligible = profiles.filter(p => selectedSource === "all" || p.source === selectedSource && withinVersion(p));
      const years = [...new Set(eligible.map(p => p.year).filter(y => y != null).map(String))].sort((a, b) => Number(b) - Number(a));
      if (!years.includes(selectedYear)) selectedYear = "all";
      yearControl.innerHTML = '<option value="all">All available years</option>' + years.map(y => `<option value="${escape(y)}">${escape(y)}</option>`).join("");
      yearControl.value = selectedYear;
    }
    function badge(kind) {
      const text = {direct: "Individual region", aggregate: "Aggregate region", unspecified: "—"}[kind];
      return `<span class="coverage-status coverage-status--${kind}">${text}</span>`;
    }
    function renderCountry() {
      countryControl.value = selectedCountry;
      // Compare names across databases; respect the year and the selected database's version.
      const pool = profiles.filter(p => withinYear(p) && (p.source !== selectedSource || withinVersion(p)));
      const included = sources.filter(source => status(source, selectedCountry, pool) === "direct");
      root.querySelector("[data-coverage-country-results]").innerHTML = included.length
        ? included.map(source => {
            const profile = pool.find(p => p.source === source && direct(p, selectedCountry));
            return `<a href="${escape(profile.guide_url)}" title="${escape(profile.label)}" data-coverage-guide="${escape(source)}">${escape(name(source))}</a>`;
          }).join('<span class="coverage-name-separator" aria-hidden="true">·</span>')
        : "No individual region in the selected versions and years.";
      for (const path of root.querySelectorAll("[data-map-country]")) {
        const selected = path.dataset.mapCountry === selectedCountry;
        path.classList.toggle("is-selected", selected);
        path.setAttribute("aria-pressed", String(selected));
        path.setAttribute("tabindex", selected ? "0" : "-1");
      }
      root.querySelector(".coverage-world-map").setAttribute("aria-label", `Country coverage map. Selected: ${countryById.get(selectedCountry).name}.`);
    }
    function renderList() {
      const columns = relevantSources();
      root.querySelector("[data-coverage-table-head]").innerHTML = `<tr><th scope="col">Country</th>${columns.map(s => `<th scope="col">${escape(name(s))}</th>`).join("")}</tr>`;
      const filtered = countries.filter(c => `${c.name} ${c.iso3} ${c.iso2}`.toLowerCase().includes(query.toLowerCase()));
      root.querySelector("[data-coverage-table-body]").innerHTML = filtered.map(c => `<tr><th scope="row"><button type="button" data-list-country="${c.iso3}">${escape(c.name)} <small>${c.iso3}</small></button></th>${columns.map(s => `<td>${badge(status(s, c.iso3))}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${columns.length + 1}">No country matches this search.</td></tr>`;
    }
    function renderModel() {
      const panel = root.querySelector("[data-coverage-model-detail]");
      if (selectedSource === "all") { panel.innerHTML = ""; return; }
      const profile = activeProfiles()[0];
      if (!profile) { panel.innerHTML = "No parsed inventory is available for this year."; return; }
      const aggregates = rows(profile).filter(r => r.kind === "aggregate");
      const missing = aggregates.filter(r => !r.members?.length);
      panel.innerHTML = aggregates.length ? `<p class="coverage-aggregate-title">Aggregate regions</p><ul class="coverage-aggregate-list">${aggregates.map(r => `<li><code>${escape(r.label)}</code> ${escape(r.name)}</li>`).join("")}</ul>${missing.length ? '<p class="coverage-aggregate-note">Country membership is not yet available for these aggregate regions.</p>' : ""}` : "";
    }
    function renderLegend() {
      const legend = root.querySelector("[data-coverage-legend]");
      if (selectedSource !== "all") {
        legend.innerHTML = '<span><i class="coverage-key-individual"></i>Individual region</span><span><i class="coverage-key-aggregate"></i>Aggregate regions</span><span><i class="coverage-key-none"></i>Unspecified</span>';
        return;
      }
      const maximum = relevantSources().length;
      legend.innerHTML = `<span class="coverage-zero-key"><i class="coverage-key-none"></i>No individual region</span><div class="coverage-colorscale" role="img" aria-label="Number of databases with an individual region, from 1 to ${maximum}"><span class="coverage-colorscale-title">Databases with an individual region</span><div class="coverage-colorscale-bar" style="background:${maximum > 1 ? 'linear-gradient(to right, var(--coverage-low), var(--coverage-high))' : 'var(--coverage-low)'}"></div><div class="coverage-colorscale-ticks">${Array.from({length: maximum}, (_, i) => `<span>${i + 1}</span>`).join("")}</div></div>`;
    }
    function render() {
      const pool = activeProfiles();
      const count = relevantSources().length;
      root.querySelector("[data-coverage-headline]").innerHTML = selectedSource === "all"
        ? `<strong>${countries.filter(c => coverageCount(c.iso3) > 0).length}</strong> countries / territories · <strong>${count}</strong> ${count === 1 ? "database" : "databases"}`
        : pool.length ? `<strong>${pool[0].geography.individual_countries}</strong> individual regions · <strong>${pool[0].geography.aggregate_count}</strong> aggregate regions` : "No parsed inventory for this year.";
      renderLegend();
      for (const path of root.querySelectorAll("[data-map-country]")) {
        const iso = path.dataset.mapCountry;
        const kind = selectedSource === "all" ? null : status(selectedSource, iso);
        const number = coverageCount(iso);
        path.dataset.count = number;
        path.dataset.representation = kind || "comparison";
        path.style.fill = selectedSource === "all" ? coverageColor(number) : {direct: "var(--coverage-individual)", aggregate: "var(--coverage-aggregate)", unspecified: "var(--coverage-none)"}[kind];
        path.querySelector("title").textContent = selectedSource === "all"
          ? `${countryById.get(iso).name}: individual region in ${number} ${number === 1 ? "database" : "databases"}`
          : `${countryById.get(iso).name}: ${{direct: "Individual region", aggregate: "Aggregate region", unspecified: "Unspecified"}[kind]}`;
      }
      root.querySelector("[data-coverage-map-panel]").hidden = view !== "map";
      root.querySelector("[data-coverage-list-panel]").hidden = view !== "list";
      for (const button of root.querySelectorAll("[data-coverage-view]")) button.setAttribute("aria-pressed", String(button.dataset.coverageView === view));
      renderCountry(); renderList(); renderModel();
    }
    databaseControl.addEventListener("change", () => {
      selectedSource = databaseControl.value;
      const choices = versions(selectedSource);
      selectedVersion = choices[0]?.key || null;
      versionControl.innerHTML = choices.map(v => `<option value="${escape(v.key)}">${escape(v.label)}</option>`).join("");
      versionControl.value = selectedVersion || "";
      root.querySelector("[data-coverage-version-label]").hidden = selectedSource === "all";
      updateYears(); render();
    });
    versionControl.addEventListener("change", () => { selectedVersion = versionControl.value; updateYears(); render(); });
    yearControl.addEventListener("change", () => { selectedYear = yearControl.value; render(); });
    countryControl.addEventListener("change", () => { selectedCountry = countryControl.value; renderCountry(); });
    root.addEventListener("click", event => {
      const button = event.target.closest("[data-coverage-view], [data-list-country], [data-map-country]");
      if (!button) return;
      if (button.dataset.coverageView) { view = button.dataset.coverageView; render(); }
      if (button.dataset.listCountry || button.dataset.mapCountry) { selectedCountry = button.dataset.listCountry || button.dataset.mapCountry; renderCountry(); }
    });
    root.querySelector("[data-coverage-search]").addEventListener("input", event => { query = event.target.value; renderList(); });
    root.querySelector(".coverage-world-map").addEventListener("keydown", event => {
      const path = event.target.closest("[data-map-country]");
      if (!path) return;
      if (["Enter", " "].includes(event.key)) { event.preventDefault(); selectedCountry = path.dataset.mapCountry; renderCountry(); }
      if (["ArrowLeft", "ArrowRight"].includes(event.key)) {
        event.preventDefault();
        const index = shapes.findIndex(s => s.iso3 === selectedCountry);
        selectedCountry = shapes[(index + (event.key === "ArrowLeft" ? -1 : 1) + shapes.length) % shapes.length].iso3;
        renderCountry(); root.querySelector(`[data-map-country="${selectedCountry}"]`).focus();
      }
    });
    updateYears(); render();
  }).catch(() => {
    const notice = root.querySelector("[data-comparison-loading]") || root.appendChild(document.createElement("p"));
    notice.innerHTML = `The country explorer could not load. Set lists are available in <a href="${escape(downloads)}">Downloadable material</a>.`;
  });
})();
