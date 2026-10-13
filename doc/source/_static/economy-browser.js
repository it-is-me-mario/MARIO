/* Pinned local observations, rendered with the documentation Plotly runtime. */
(() => {
  "use strict";
  const root = document.querySelector("[data-economy-browser]");
  if (!root) return;
  const M = window.MarioEconomy;
  const C = window.MarioEconomyCharts;
  const base = new URL(root.dataset.root || "../../", location.href);
  const asset = path => new URL("_static/" + path, base).href;
  const esc = x => String(x ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const compact = x => x == null ? "Unavailable" : new Intl.NumberFormat("en", {notation:"compact",maximumFractionDigits:2}).format(x);
  const exact = x => x == null ? "—" : new Intl.NumberFormat("en", {maximumFractionDigits:2}).format(x);
  const getJSON = async path => {const r=await fetch(asset(path),{cache:"no-cache"}); if(!r.ok) throw new Error(`Could not load ${path}`); return r.json();};
  const save = (text,name,mime) => {const url=URL.createObjectURL(new Blob([text],{type:mime})); const a=document.createElement("a"); a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  const csv = rows => {
    const cell = x => '"'+String(x??"").replace(/^[=+@\t\r]/,m=>"'"+m).replace(/"/g,'""')+'"';
    return "\ufeff"+[M.unique(rows.flatMap(Object.keys)),...rows.map(row=>M.unique(rows.flatMap(Object.keys)).map(key=>row[key]))].map(row=>row.map(cell).join(",")).join("\r\n");
  };
  Promise.all([getJSON("data/economy/browser-index.json"),getJSON("data/economy/world-bank.json"),getJSON("data/world-country-map.json"),getJSON("data/economy/edgar.json")])
    .then(async ([index,wb,world,edgar]) => {
      const {snapshots, mappings} = M.unpackBrowserIndex(index);
      // Keep international MRIO readings; retain national snapshots outside this UI.
      for (let i = snapshots.length - 1; i >= 0; i--) if (!M.isMRIO(snapshots[i]) || snapshots[i].recipe.price_basis === "Previous year prices") snapshots.splice(i, 1);
      const pendingSnapshots = new Map();
      let renderSequence = 0;
      const ensureLoaded = async snapshot => {
        if (!M.needsDetailedReading(snapshot, state)) return;
        const id = snapshot.recipe.id;
        if (!pendingSnapshots.has(id)) pendingSnapshots.set(id, getJSON(`data/economy/${id}.json`).then(loaded=>{
          const index = snapshots.findIndex(s=>s.recipe.id===id);
          snapshots[index] = loaded;
        }).catch(error=>{pendingSnapshots.delete(id);throw error;}));
        await pendingSnapshots.get(id);
      };
      const families=M.unique(snapshots.map(s=>s.recipe.source)).sort((a,b)=>a==="EXIOBASE"?-1:b==="EXIOBASE"?1:a.localeCompare(b));
      const state = {families:families.filter(f=>snapshots.some(s=>s.recipe.source===f&&M.metricAvailable([s],"gdp"))),versions:{},year:"all",metric:"gdp",section:"all",perCapita:false,country:"world",environmentallyExtended:false};
      const versionChoices={}, compareFacets={}, openFamilies=new Set();
      const DEFAULT_YEARS=20;
      let defaultYears=true;
      let manualView=null, zoom=1, panX=0, panY=0, drag=null, dragged=false, chartRows=[], displayScale={factor:1,unit:M.unit(state)};
      const $ = selector=>root.querySelector(selector);
      const title = ()=>((state.metric==="gdp"&&active().length===1&&active()[0].recipe.gdp_bridge_verified===false)?"GDP estimate":({gdp:"GDP",value_added:"Value added",ghg:"GHG emissions"}[state.metric]))+(state.perCapita?" per capita":"");
      const availableReadings = ()=>state.environmentallyExtended?snapshots.filter(s=>M.metricAvailable([s],"ghg")):snapshots;
      const active = ()=>M.selected(snapshots,state);
      const candidates = ()=>M.selected(snapshots,state,false);
      const autoView = ()=>M.automaticView(snapshots,state);
      const view = ()=>manualView || autoView();
      const mapping = s=>s&&mappings[s.recipe.id];
      const val = (s,r,overrides={})=>M.value(s,r,{...state,...overrides},wb,mapping(s));
      const singleCountry = ()=>Array.isArray(state.country)?state.country.length===1?state.country[0]:null:state.country;
      // Sector part of the heading; the map shows one aggregate, the first selected.
      const sectionText = ()=>{
        if(state.section==="all")return "";
        const list=Array.isArray(state.section)?state.section:[state.section], labels=mapping(candidates()[0])?.sections||{};
        const one=code=>code===M.HOUSEHOLDS?M.HOUSEHOLDS_LABEL:`${code} · ${labels[code]||code}`;
        return list.length===1?` · ${one(list[0])}`:view()==="map"?` · ${one(list[0])} (map: first selected aggregate)`:` · ${list.length} sector aggregates`;
      };
      const countryName = ()=>!M.countryOptions(snapshots,state).regions.length?"No country / region":Array.isArray(state.country)?state.country.length?`${state.country.length} countries / regions`:"No country / region":M.isWorld(state.country)?"World":M.countryOptions(snapshots,state).regions.find(r=>r.id===state.country)?.name || wb.countries[state.country]?.name || state.country;
      const heading = ()=>`${title()} · ${countryName()}${sectionText()}`;
      const period = ys=>{const sorted=M.unique(ys.map(Number)).sort((a,b)=>a-b),parts=[];let first=sorted[0],last=first;for(const y of [...sorted.slice(1),null]){if(y===last+1){last=y;continue;}parts.push(first===last?String(first):`${first}–${last}`);first=last=y;}return parts.join(", ");};
      // Databases, years and unit under the heading; long database lists collapse to names and a count.
      const subheading = ()=>{
        const selected=active();
        if(!selected.length)return "";
        const versions=new Map();
        for(const s of selected){const f=s.recipe.source;if(!versions.has(f))versions.set(f,new Set());versions.get(f).add(M.version(s.recipe));}
        const names=[...versions.keys()], detailed=[...versions].map(([f,vs])=>vs.size===1?`${f} ${[...vs][0]}`.trim():`${f} (${vs.size} versions)`).join(", ");
        const databases=names.length>1?`${names.length} databases`:detailed.length>35?names[0]:detailed;
        return [databases,period(selected.map(s=>s.recipe.year))].filter(Boolean).join(" · ");
      };
      // The subtitle names the prevailing IPCC report and horizon; an asterisk flags any variant, explained in Other notes.
      // The chart footnote identifies every non-standard basis, including CO2-only proxies and source-characterised gases.
      const gwpSummary = rows=>{
        if(state.metric!=="ghg")return null;
        const groups=new Map();
        for(const row of rows.filter(r=>r.database!=="World Bank")){
          const c=M.gwpConvention(row);
          if(!groups.has(c.key))groups.set(c.key,{...c,databases:new Set()});
          groups.get(c.key).databases.add(row.database==="OECD"?"OECD ICIO":row.database);
        }
        if(!groups.size)return null;
        const conventions=[...groups.values()];
        const family=c=>{const m=c.key.match(/^AR(\d)(?:-(\d+))?/);return m?`AR${m[1]} GWP${m[2]&&!isNaN(m[2])?m[2]:100}`:null;};
        const counts=new Map();
        for(const c of conventions){const f=family(c);if(f)counts.set(f,(counts.get(f)||0)+c.databases.size);}
        if(!counts.size)return {main:conventions.map(c=>c.label).join("; "),footnote:""};
        const main=[...counts].sort((a,b)=>b[1]-a[1])[0][0];
        const plain=c=>family(c)===main&&/^AR\d-\d+$/.test(c.key);
        const qualified=conventions.filter(c=>!plain(c));
        return {main:main+(qualified.length?"*":""),
          footnote:qualified.length?`* ${qualified.map(g=>`${[...g.databases].join(", ")}: ${g.label}`).join("; ")}.`:""};
      };
      const wrapText = (text,width)=>{const lines=[];let line="";for(const word of text.split(" ")){if(line&&(line+" "+word).length>width){lines.push(line);line=word;}else line=line?line+" "+word:word;}if(line)lines.push(line);return lines;};
      const option = (value,label,selected)=>`<option value="${esc(value)}"${value===selected?" selected":""}>${esc(label)}</option>`;
      root.innerHTML=`
        <div class="eb-filter-panel">
          <div class="eb-filters eb-filters--source"><fieldset class="eb-family-choices" data-families><legend><span>Databases and versions</span><span class="eb-filter-actions" role="group" aria-label="Select databases and versions"><button type="button" data-bulk-filter="databases" data-bulk-action="select">Select all</button><button type="button" data-bulk-filter="databases" data-bulk-action="clear">Unselect all</button><button type="button" data-bulk-filter="databases" data-bulk-action="env-extended">Environmentally extended</button></span></legend><div data-family-tree></div><small data-version-default></small></fieldset><div class="eb-multi-field"><span>Years</span><details class="eb-picker" data-picker="year"><summary data-picker-label="year"></summary><div class="eb-picker-options" data-options="year"></div></details></div></div>
          <div class="eb-filters eb-filters--indicator"><div class="eb-multi-field"><span>Country / region</span><details class="eb-picker" data-picker="country"><summary data-picker-label="country"></summary><input type="search" data-country-search aria-label="Find a country or region" placeholder="Search name or ISO code…"><div class="eb-picker-options" data-options="country"></div></details></div><label>Indicator<select data-metric><option value="gdp">GDP</option><option value="value_added">Value added</option><option value="ghg">GHG emissions</option></select></label><div class="eb-multi-field"><span>Sector aggregate</span><details class="eb-picker" data-picker="section"><summary data-picker-label="section"></summary><div class="eb-picker-options" data-options="section"></div></details></div><label>Measure<select data-measure><option value="total">Total</option><option value="per-capita">Per capita</option></select></label></div>
          <div class="eb-filter-foot"><span data-filter-note></span><a href="${asset("data/economy/sector-correspondence.xlsx")}" data-sector-download download>Sector correspondence · Excel ↗</a></div>
        </div>
        <div class="eb-viewbar"><div><h3 data-heading></h3><p class="eb-subheading" data-subheading></p><p class="eb-note" data-view-note></p></div><div class="eb-toggle" role="group" aria-label="Visualisation"><button data-view="auto" aria-label="Chart" title="Chart"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 3v17h17M8 16v-5m5 5V6m5 10V9"/></svg></button><button data-view="map" aria-label="Map" title="Map"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3ZM9 3v15M15 6v15"/></svg></button><button data-view="table" aria-label="Table" title="Table"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 10h18M3 15h18M10 4v16"/></svg></button></div></div>
        <div class="eb-layout"><div class="eb-visual"><div data-chart></div><div data-map-panel hidden><div class="eb-map-wrap"><svg class="eb-map" data-map viewBox="${esc(world.viewbox)}" role="group" aria-label="Country indicator map"><g data-map-layer></g></svg><div class="eb-zoom" role="group" aria-label="Map zoom"><button data-zoom="in" aria-label="Zoom in">+</button><button data-zoom="out" aria-label="Zoom out">−</button><button data-zoom="reset">Reset</button></div><a class="eb-credit" href="https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/">Natural Earth · 1:110m</a></div><div class="eb-legend" data-legend></div></div><div data-table-panel hidden></div></div><p class="eb-note eb-gwp-note" data-gwp-note hidden></p>
</div>
        <p class="eb-note eb-indicator-note" data-indicator-note hidden></p><p class="eb-note eb-reference-caption" data-reference-caption></p><p class="eb-note" data-availability role="status"></p>
        <div class="eb-actions"><button class="eb-primary" data-export>Download MRIO data · CSV</button><button data-script aria-describedby="eb-script-hint">MARIO example · Python</button><span data-export-label></span><span class="eb-script-hint" id="eb-script-hint" data-script-hint hidden></span></div>
        <p class="eb-source" data-source></p><details class="eb-other-notes" data-source-details hidden><summary>Sources</summary><div data-source-list></div></details><details class="eb-other-notes"><summary>Other notes</summary><p class="eb-note eb-chart-help" data-chart-help></p><p class="eb-context" data-indicator-details></p><p class="eb-context" data-context></p><p class="eb-context" data-households hidden></p><div data-reading-notes></div><div data-methods-slot></div></details><p class="eb-note" data-message role="status" aria-live="polite"></p>`;
      const methods=document.querySelector("[data-browser-methods]");
      if(methods) {$("[data-methods-slot]").append(methods);methods.hidden=false;}
      function controls() {
        const pool=availableReadings();
        const versionsFor=f=>M.unique(pool.filter(s=>s.recipe.source===f).map(s=>M.version(s.recipe))).sort((a,b)=>b.split(" · ")[0].localeCompare(a.split(" · ")[0],undefined,{numeric:true})||a.localeCompare(b));
        // Resolve stored facet choices of selected families; unselected ones keep theirs untouched.
        for(const f of families) {
          if(compareFacets[f]&&state.families.includes(f)) {
            const def=M.focusFacets(pool,f,compareFacets[f],"all");
            compareFacets[f]=def.selection;
            versionChoices[f]=def.versions;
          }
          state.versions[f]=versionChoices[f] || (manualView==="table"?"all":M.latestVersions(pool,f));
        }
        // Prepare the facet panel for the one expanded database (accordion).
        const expanded=[...openFamilies][0];
        let panelHTML="";
        if(expanded && families.includes(expanded)) {
          if(!compareFacets[expanded]) {
            // Opening an accordion must describe the active readings,
            // including an explicit all-versions preset, without changing it.
            const chosen=pool.filter(s=>s.recipe.source===expanded&&M.includes(state.versions[expanded]||"all",M.version(s.recipe))).map(s=>M.recipeFacets(s.recipe));
            const all=pool.filter(s=>s.recipe.source===expanded).map(s=>M.recipeFacets(s.recipe));
            compareFacets[expanded]=chosen.length?Object.fromEntries(["units","version","format","system","price"].map(key=>{
              const values=M.unique(chosen.map(f=>f[key]).filter(v=>v!=null)),available=M.unique(all.map(f=>f[key]).filter(v=>v!=null));
              return [key,values.length===available.length?"all":values];
            })):{};
          }
          const def=M.focusFacets(pool,expanded,compareFacets[expanded],"all");
          // An unselected database shows no ticked facet (its count reads 0/x); ticking one selects it again.
          const live=state.families.includes(expanded);
          if(live){
            compareFacets[expanded]=def.selection;
            versionChoices[expanded]=def.versions;
            state.versions[expanded]=def.versions;
          }
          if(def.fields.length) panelHTML=`<div class="eb-compare-panel">${def.fields.map(field=>{
            const sel=def.selection[field.key];
            const bulk=field.options.length>1?`<span class="eb-filter-actions eb-facet-actions" role="group" aria-label="Select ${esc(field.label)}"><button type="button" data-facet-bulk="select" data-facet-family="${esc(expanded)}" data-facet-key="${field.key}">Select all</button><button type="button" data-facet-bulk="clear" data-facet-family="${esc(expanded)}" data-facet-key="${field.key}">Unselect all</button></span>`:"";
            return `<div class="eb-compare-facet"><span>${esc(field.label)}</span>${bulk}${field.options.map(opt=>
              `<label><input type="checkbox" data-compare-facet="${esc(expanded)}" data-facet-key="${field.key}" value="${esc(opt)}" ${live&&M.includes(sel,opt)?"checked":""}>${esc(opt)}</label>`
            ).join("")}</div>`;
          }).join("")}</div>`;
        }
        // Family headings — panel inserted right after the expanded node.
        $("[data-family-tree]").innerHTML=families.map((f,i)=>{
          const versions=versionsFor(f), enabled=state.families.includes(f), chosen=versions.filter(v=>enabled&&M.includes(state.versions[f],v));
          const expandable=versions.length>1;
          let html=`<div class="eb-family-node"><div class="eb-family-head">${expandable?`<button type="button" data-expand-family="${esc(f)}" aria-expanded="${openFamilies.has(f)}" aria-label="Configure versions of ${esc(f)}">${openFamilies.has(f)?"▾":"▸"}</button>`:""}<label><input type="checkbox" data-compare-family value="${esc(f)}" ${enabled?"checked":""} ${versions.length?"":"disabled"}>${esc(f==="OECD"?"OECD ICIO":f)}${expandable?`<small>${chosen.length}/${versions.length}</small>`:""}</label></div></div>`;
          if(f===expanded && panelHTML) html+=panelHTML;
          return html;
        }).join("");
        root.querySelectorAll("[data-compare-family]").forEach(el=>{
          const versions=versionsFor(el.value), chosen=versions.filter(v=>el.checked&&M.includes(state.versions[el.value],v));
          el.indeterminate=chosen.length>0&&chosen.length<versions.length;
          if(versions.length&&!chosen.length)el.checked=false;
        });
        $("[data-version-default]").textContent=state.environmentallyExtended?"Loaded GHG accounts only.":manualView==="table"?"All versions by default.":"Latest versions by default.";
        $('[data-bulk-action="env-extended"]').setAttribute("aria-pressed",String(state.environmentallyExtended));
        const years=M.years(pool,state);
        // Default: the 20 most recent years before the current calendar year; later years are publisher forecasts.
        if(defaultYears&&years.length){
          defaultYears=false;
          const recent=M.recentYears(years,DEFAULT_YEARS);
          if(state.year==="all"&&recent.length&&recent.length<years.length)state.year=recent;
        }
        if(state.year!=="all"&&years.length) {
          const kept=(Array.isArray(state.year)?state.year:[state.year]).filter(y=>years.includes(Number(y)));
          state.year=kept.length===1?Number(kept[0]):kept.length?kept:Array.isArray(state.year)&&!state.year.length?[]:years.length?years.at(-1):[];
        }
        const countries=M.countryOptions(pool,state);
        const allRegions=countries.regions, hasWorld=countries.hasWorld;
        // Preserve the country preference while an upstream filter is empty.
        // Explicit [] remains empty; missing years/versions can later recover.
        if(allRegions.length||hasWorld)state.country=countries.selection;
        function picker(kind,items,label) {
          const selection=(kind==="country"&&!items.length&&!hasWorld||kind==="year"&&!items.length)?[]:state[kind], choices=Array.isArray(selection)?selection:[selection], special=kind==="country"?"world":"all";
          const specialLabel=kind==="country"?"World":kind==="section"?(items.length?"All sector aggregates":"Whole economy"):"All years";
          $(`[data-picker-label="${kind}"]`).textContent=selection===special?specialLabel:!choices.length?"None":choices.length===1?items.find(x=>String(x[0])===String(choices[0]))?.[1]||"None":kind==="year"&&period(choices).length<=24?period(choices):`${choices.length} selected`;
          let group="";
          const allTitle=kind==="country"&&hasWorld?"World: sum every native region once, including aggregates":`Select all ${label}`;
          const yearActions=kind==="year"?`<button type="button" data-bulk-filter="${kind}" data-bulk-action="last5">Last 5</button><button type="button" data-bulk-filter="${kind}" data-bulk-action="last10">Last 10</button><button type="button" data-bulk-filter="${kind}" data-bulk-action="last20">Last 20</button>`:"";
          const actions=`<div class="eb-filter-actions" role="group" aria-label="Select ${esc(label)}"><button type="button" data-bulk-filter="${kind}" data-bulk-action="select" title="${esc(allTitle)}">Select all</button><button type="button" data-bulk-filter="${kind}" data-bulk-action="clear" title="Unselect all ${esc(label)}">Unselect all</button>${yearActions}</div>`;
          const showSpecial=kind==="country"&&hasWorld;
          $(`[data-options="${kind}"]`).innerHTML=actions+(showSpecial?`<label><input type="checkbox" data-subset="${kind}" value="${special}" ${selection===special?"checked":""}>${specialLabel}</label>`:"")+items.map(([value,name,category])=>{
            const heading=category&&group!==category?`<div class="eb-picker-group">${esc(category)}</div>`:"";group=category;
            return heading+`<label data-choice-search="${esc(`${name} ${value}`.toLowerCase())}"><input type="checkbox" data-subset="${kind}" value="${esc(value)}" ${(kind!=="country"||selection!==special)&&M.includes(selection,value)?"checked":""}>${esc(name)}</label>`;
          }).join("");
          const canRestore=Array.isArray(selection)&&!selection.length&&items.length>0;
          const disabled=items.length+(kind==="country"&&hasWorld?1:0)<=1&&!canRestore;
          $(`[data-picker="${kind}"]`).classList.toggle("is-disabled",disabled);
          $(`[data-picker="${kind}"] summary`).setAttribute("aria-disabled",disabled);
          // A disabled picker cannot be opened by pointer or keyboard, and closes if it was open.
          if(disabled)$(`[data-picker="${kind}"]`).open=false;
          $(`[data-picker="${kind}"] summary`).tabIndex=disabled?-1:0;
          $(`[data-options="${kind}"]`).querySelectorAll("input,button").forEach(el=>el.disabled=disabled);
        }
        picker("year",[...years].reverse().map(y=>[y,String(y)]),"available years");
        const regionItems=allRegions.filter(r=>r.kind==="country").map(r=>[r.id,r.name,"Countries / territories"]);
        regionItems.push(...allRegions.filter(r=>r.kind!=="country").map(r=>[r.id,`${r.name}${state.families.length===1?"":" · "+r.source+" · "+r.versions.join(" / ")}`,"Aggregate regions"]));
        picker("country",regionItems,"countries / regions");
        const gdpOK=M.metricAvailableForSelection(pool,state,"gdp");
        $("[data-metric] option[value=gdp]").disabled=!gdpOK;
        if(state.metric==="gdp"&&!gdpOK&&active().length)state.metric="value_added";
        const ghgOK=M.metricAvailableForSelection(pool,state,"ghg");
        $("[data-metric] option[value=ghg]").disabled=!ghgOK;
        $("[data-metric] option[value=ghg]").title=ghgOK?"":"All selected versions and years must include verified GHG accounts";
        if(state.metric==="ghg"&&!ghgOK&&active().length)state.metric="value_added";
        filterCountries();
        const maps=candidates().map(mapping), compatible=maps.length&&maps.every(m=>m?.entries.length&&m.classification_id===maps[0]?.classification_id);
        // Sector aggregates apply to value added and GHG; GHG also offers direct household emissions, which need no sector mapping.
        const sectorsOK=state.metric!=="gdp"&&compatible;
        const householdsOK=state.metric==="ghg"&&candidates().some(s=>s.recipe.final_demand_emissions_loaded!==false&&s.regions.some(r=>r.household_ghg!=null));
        const correspondences=maps.filter(m=>m?.entries.length);
        $("[data-sector-download]").hidden=!correspondences.length;
        $("[data-sector-download]").title=correspondences.length?`Verified sector mappings for ${M.unique(correspondences.map(m=>m.family)).join(", ")}`:"";
        const sectionLabels={...(sectorsOK?maps[0].sections:{}),...(householdsOK?{[M.HOUSEHOLDS]:M.HOUSEHOLDS_LABEL}:{})};
        if(!Object.keys(sectionLabels).length) state.section="all";
        if(state.section!=="all"){const kept=(Array.isArray(state.section)?state.section:[state.section]).filter(code=>code in sectionLabels);state.section=kept.length===1?kept[0]:kept.length?kept:Array.isArray(state.section)&&!state.section.length?[]:"all";}
        picker("section",Object.entries(sectionLabels).map(([code,name])=>code===M.HOUSEHOLDS?[code,name,"Final demand"]:[code,`${code} · ${name}`,householdsOK?"Producer sectors":undefined]),"sector aggregates");
        const chosenRegions=allRegions.filter(r=>M.includes(state.country,r.id));
        const perCapitaOK=state.section==="all"&&(M.isWorld(state.country)&&hasWorld||chosenRegions.length>0&&chosenRegions.every(r=>r.kind==="country"));
        if(!perCapitaOK) state.perCapita=false;
        $("[data-measure]").value=state.perCapita?"per-capita":"total";
        $("[data-measure] option[value='per-capita']").disabled=!perCapitaOK;
        $("[data-measure]").disabled=!perCapitaOK;
        $("[data-metric]").value=state.metric;
        $("[data-filter-note]").textContent=state.metric==="gdp"?"":!compatible?(householdsOK?"No common sector mapping; households are available.":"No common sector mapping."):`${maps[0].classification} sections.`;
        const mapOK=active().length===1;
        root.querySelectorAll(".eb-filter-panel select").forEach(el=>{if(el.options.length===1)el.disabled=true;el.closest("label")?.classList.toggle("is-disabled",el.disabled);});
        $("[data-view='map']").disabled=!mapOK;
        $("[data-view='map']").title=mapOK?"Compare countries on a map":"Choose one database version and one year to use the map";
        if(manualView==="map"&&!mapOK) manualView=null;
        root.querySelectorAll("[data-view]").forEach(b=>b.setAttribute("aria-pressed",b.dataset.view===(manualView||"auto")));
      }
      function table(rows) {
        return `<div class="eb-scroll"><table class="eb-table"><thead><tr><th scope="col">Source / group</th><th scope="col">Year</th><th scope="col">${esc(displayScale.unit)}</th><th scope="col">Notes</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.label||r.database+" · "+r.version)}</td><td>${r.year}</td><td>${exact(C.scaled(r.value,displayScale))}</td><td>${esc(r.note||r.basis||"")}</td></tr>`).join("")}</tbody></table></div>`;
      }
      function chartColors() {
        const style=getComputedStyle(root);
        const color=name=>style.getPropertyValue(name).trim();
        return {background:color("--surface-2"),surface:color("--surface"),ink:color("--ink"),muted:color("--ink-muted"),grid:color("--line"),font:style.fontFamily,reference:color("--eb-reference"),
          palette:[color("--eb-accent"),color("--eb-series-orange"),"#886bb2","#459b79","#c46187","#527fbe",color("--eb-series-yellow"),"#6a9090"]};
      }
      let chartOperation=Promise.resolve();
      async function updateHoverDistance() {
        const node=$("[data-chart]"), axis=node._fullLayout?.xaxis;
        if(!axis || !node._marioYears || node._marioYears.length<2 || node.hidden)return;
        const distance=C.hoverDistance(node._marioYears,axis.l2p(2001)-axis.l2p(2000));
        const tick=Math.max(1,Math.ceil(Math.abs(axis.range[1]-axis.range[0])/7));
        const changes={};
        if(node._fullLayout.hoverdistance!==distance)changes.hoverdistance=distance;
        if(axis.dtick!==tick)changes["xaxis.dtick"]=tick;
        if(Object.keys(changes).length)await window.Plotly.relayout(node,changes);
      }
      async function drawChart(rows) {
        const node=$("[data-chart]"), years=M.selectedYears(snapshots,state);
        const figure=C.figure(rows,{state,years,nativeUnit:M.unit(state),colors:chartColors(),catalogue:M.unique(snapshots.map(s=>M.seriesKey(s.recipe))),
          databaseFamilies:families, width:node.clientWidth,
          revision:JSON.stringify([state.families,state.versions,state.year,state.metric,state.section,state.perCapita,state.country])});
        displayScale=figure.scale;
        // Title inside the figure so the PNG export carries it; the plot area keeps its height.
        const gwp=gwpSummary(rows), modebarClearance=node.clientWidth<480?34:0;
        // Long headings wrap on narrow charts instead of running past the plot.
        const titleLines=wrapText(heading(),Math.max(24,Math.floor((node.clientWidth-40)/9.5)));
        const titleSpace=(gwp?80:62)+modebarClearance+(titleLines.length-1)*20, colors=chartColors();
        figure.layout.height+=titleSpace;figure.layout.margin={...figure.layout.margin,t:figure.layout.margin.t+titleSpace};
        figure.layout.title={text:`<b>${titleLines.map(esc).join("<br>")}</b>`,font:{size:16,color:colors.ink},subtitle:{text:esc(subheading())+(gwp?"<br>"+esc(gwp.main):""),font:{size:12,color:colors.muted}},xref:"container",x:0,xanchor:"left",yref:"container",y:1,yanchor:"top",pad:{l:18,t:18+modebarClearance}};
        if(gwp?.footnote){
          // The footnote is the legend title: it always sits right above the legend items and is part of the PNG export.
          const lines=wrapText(gwp.footnote,Math.max(40,Math.floor((node.clientWidth-40)/6.2)));
          figure.layout.height+=lines.length*15+8;
          figure.layout.legend={...figure.layout.legend,title:{text:lines.map(esc).join("<br>"),side:"top",font:{size:11,color:colors.muted}}};
        }
        const label=`${title()} · ${countryName()}. Interactive chart; values in ${figure.scale.unit}.`;
        const operation=chartOperation.then(async()=>{
          if(!figure.data.length) {
            if(node.data)window.Plotly.purge(node);
            node._marioHoverBound=false;
            node.style.height="";
            node.innerHTML='<p class="eb-empty">No database observations for this selection. See availability below.</p>';
            return;
          }
          if(!window.Plotly)throw new Error("The Plotly runtime could not load; select the table to view the data.");
          if(!node.data)node.innerHTML="";
          node.style.height=figure.layout.height+"px";
          node.setAttribute("aria-label",label);
          node._marioYears=years;
          await window.Plotly.react(node,figure.data,figure.layout,window.MarioFigureDownload.withCredit(figure.config,[heading()+' · MARIO-derived results; reference accounting boundaries can differ.',...M.unique(active().map(s=>s.recipe.attribution||s.recipe.label)),...(rows.some(r=>r.database==='World Bank')||state.perCapita||state.metric!=='ghg'&&active().some(s=>s.recipe.currency&&s.recipe.currency!=='USD')?['World Bank WDI: CC BY 4.0. Historical EUR/ECU rates: Eurostat, where used.']:[]),...(rows.some(r=>r.database==='EDGAR')?['EDGAR references: European Union / JRC; IEA component terms apply.']:[]), 'Sources and terms: https://www.marioproject.com/en/latest/resources/data-explorer/compare.html']));
          await updateHoverDistance();
          if(!node._marioHoverBound) {
            node._marioHoverBound=true;
            node.on("plotly_afterplot",()=>{chartOperation=chartOperation.then(updateHoverDistance).catch(()=>{});});

          }
        });
        chartOperation=operation.catch(()=>{});
        await operation;
      }
      function geographicRows(s) {
        return s.regions.filter(r=>M.isWorld(state.country)||M.includes(state.country,M.regionKey(s,r))).map(r=>({label:r.name,pick:M.regionKey(s,r),country:M.regionKey(s,r),database:s.recipe.source,version:M.version(s.recipe),year:s.recipe.year,value:val(s,r,{section:Array.isArray(state.section)?state.section[0]:state.section}),country_name:r.name,note:"",basis:M.basis(s.recipe,state.metric),unit:M.unit(state)})).sort((a,b)=>(b.value??-Infinity)-(a.value??-Infinity));
      }
      function transform(){ $("[data-map-layer]").setAttribute("transform",`translate(${panX} ${panY}) scale(${zoom})`); }
      function map(s) {
        const rows=geographicRows(s),byISO=new Map(rows.map(r=>[r.country,r])),vs=rows.filter(r=>r.value!=null).map(r=>r.value);
        displayScale=C.scaleFor(rows,state,M.unit(state));
        const min=Math.min(0,...vs),max=Math.max(0,...vs);
        $("[data-map-layer]").innerHTML=world.features.map(f=>{
          const r=byISO.get(f.iso3),native=s.regions.find(r=>r.iso3===f.iso3),v=r?.value??null;
          const fill=v==null?"var(--line)":`color-mix(in srgb,var(--eb-high) ${max===min?0:Math.round((v-min)/(max-min)*100)}%,var(--eb-low))`;
          return `<path d="${esc(f.path)}" fill="${fill}"${native?` data-iso="${esc(f.iso3)}" data-selected="${!M.isWorld(state.country)&&M.includes(state.country,f.iso3)}" role="button" tabindex="0" aria-label="${esc(native.name+': '+compact(C.scaled(v,displayScale))+' '+displayScale.unit)}"`:""}><title>${esc(f.name+": "+compact(C.scaled(v,displayScale))+" "+displayScale.unit)}</title></path>`;
        }).join("")+`<path class="eb-borders" d="${esc(world.borders)}"/>`+world.features.filter(f=>!M.isWorld(state.country)&&M.includes(state.country,f.iso3)).map(f=>`<path class="eb-selected-halo" d="${esc(f.path)}"/><path class="eb-selected-outline" d="${esc(f.path)}"/>`).join("");
        transform();$("[data-legend]").innerHTML=`<span>${compact(C.scaled(min,displayScale))}</span><span class="eb-gradient"></span><span>${compact(C.scaled(max,displayScale))} ${esc(displayScale.unit)}</span><span><i class="eb-none"></i> No observation</span>`;
      }
      async function render() {
        const sequence = ++renderSequence;
        root.setAttribute("aria-busy", "true");
        controls();
        $("[data-export]").disabled=true;$("[data-script]").disabled=true;
        $("[data-availability]").textContent="Loading selected readings…";
        try { await Promise.all(active().map(ensureLoaded)); }
        catch (error) {
          if (sequence===renderSequence) {$("[data-availability]").textContent="The selected data could not load. Change the selection to retry.";root.setAttribute("aria-busy","false");}
          return;
        }
        if (sequence!==renderSequence) return;
        const priceBases=M.unique(active().map(s=>s.recipe.price_basis || "Current prices"));
        state.priceBasis=priceBases.length>1?"mixed":priceBases[0];
        const selected=active(), s=selected[0], r=M.findRegion(s,singleCountry()), rows=candidates().length?M.observations(snapshots,state,wb,mappings,edgar):[], actualView=view();
        const barView=C.usesBars(rows,state,M.selectedYears(snapshots,state));
        root.dataset.view=actualView;root.dataset.country=state.country;root.dataset.multiple=String(!singleCountry());
        $("[data-heading]").textContent=heading();
        $("[data-view-note]").hidden=true;
        $("[data-chart-help]").hidden=["map","table"].includes(actualView);
        $("[data-chart-help]").textContent=(M.unique(selected.map(s=>s.recipe.source)).join()==="EXIOBASE"?(barView?"Filled: monetary / Open: hybrid. ":"Marker: IOT system; diamond: SUT · Filled: monetary / Open: hybrid. "):"")+"Drag to zoom · Double-click to rescale · Click / double-click a legend entry to hide or isolate a series.";
        const multiple=!singleCountry()||rows.filter(row=>!["World Bank","EDGAR"].includes(row.database)).length>1;
        let display=rows;
        chartRows=display;
        $("[data-chart]").hidden=["map","table"].includes(actualView);$("[data-map-panel]").hidden=actualView!=="map";$("[data-table-panel]").hidden=actualView!=="table";
        displayScale=C.scaleFor(display,state,M.unit(state));
        if(actualView==="map") {map(s);chartRows=geographicRows(s);} else if(actualView==="table") $("[data-table-panel]").innerHTML=table(display); else {
          try { await drawChart(rows); }
          catch(error) {try{if($("[data-chart]").data)window.Plotly.purge($("[data-chart]"));}catch{}$("[data-chart]").innerHTML=`<p class="eb-empty">${esc(error.message)}</p>`;}
          if(sequence!==renderSequence)return;
        }
        const gwp=gwpSummary(rows);
        $("[data-subheading]").textContent=subheading()+(gwp?" · "+gwp.main:"");
        $("[data-gwp-note]").textContent=gwp?.footnote||"";$("[data-gwp-note]").hidden=!gwp?.footnote||!["map","table"].includes(actualView);
        $("[data-heading]").hidden=$("[data-subheading]").hidden=!["map","table"].includes(actualView)&&!!$("[data-chart]").data?.length;
        $("[data-context]").textContent=multiple?(state.metric==="gdp"?`Values in ${M.unit(state)}. Readings with an unverified product-tax bridge are labelled as estimates; World Bank is an external reference, not an accuracy score.`:"Values keep each database's production-account boundary. Missing extensions are shown as unavailable."):state.metric==="gdp"?s?.recipe.gdp_note:state.metric==="ghg"?s?.recipe.ghg_method:s?.recipe.value_added_note;
        $("[data-context]").textContent+=" "+M.unique(selected.map(s=>s.recipe.attribution).filter(Boolean)).join(" ");
        const indicatorNotes=M.unique(selected.map(s=>state.metric==="gdp"&&s.recipe.gdp_proxy?s.recipe.gdp_note:state.metric==="ghg"&&s.recipe.ghg_proxy?s.recipe.ghg_note:state.metric==="ghg"&&s.recipe.source==="USEEIO"?"USEEIO includes import-related commodity emissions; it is not a US territorial inventory. Direct final-demand accounts are unavailable.":null).filter(Boolean));
        if(state.metric==="gdp")for(const family of M.unique(selected.filter(s=>s.recipe.gdp_quality_note).map(s=>s.recipe.source))){
          const checks=selected.filter(s=>s.recipe.source===family&&s.recipe.gdp_quality_note).sort((a,b)=>a.recipe.year-b.recipe.year);
          const concise=checks.every(s=>s.provenance?.gdp_bridge?.validation);
          indicatorNotes.push(concise?`${family} GDP · ${checks.map(s=>`${s.recipe.year}: ${(Math.abs(s.provenance.gdp_bridge.validation.relative_residual)*100).toFixed(3)}% source residual`).join("; ")}. Original income-side values retained; details in Other notes.`:M.unique(checks.map(s=>s.recipe.gdp_quality_note)).join(" "));
        }
        for(const release of M.unique(selected.filter(s=>s.recipe.ghg_usable===false).map(s=>s.recipe.release))) {
          const years=M.unique(selected.filter(s=>s.recipe.release===release&&s.recipe.ghg_usable===false).map(s=>s.recipe.year)).sort();
          indicatorNotes.push(`EXIOBASE ${release}: GHG totals unavailable for ${years.join(", ")} because of verified errors in the source extensions. Other indicators remain available; details and source reports are in Other notes.`);
        }
        indicatorNotes.push(...M.unique(selected.flatMap(s=>[s.recipe.price_note,s.recipe.source==="GLORIA"?null:s.recipe.scope_note]).filter(Boolean)));
        if(state.metric==="ghg") {
          const methods=M.unique(selected.map(s=>s.recipe.gwp_basis).filter(Boolean));
          if(methods.length) {
            const methodLabel=r=>r.source==="EXIOBASE"?r.parser_options?.unit==="Hybrid"?"AR5; three gases only":"AR5 + native HFC/PFC (basis unverified)":r.source==="ADB"?"AR5":r.source==="EMERGING"?"CO2 only, GWP 1":r.source==="USEEIO"?"source factors":r.gwp_basis;
            indicatorNotes.push((gwp?.main.endsWith("*")?"* ":"")+"GHG characterisation · "+M.unique(selected.filter(s=>s.recipe.gwp_basis).map(s=>`${s.recipe.source}: ${methodLabel(s.recipe)}`)).join("; ")+" · EDGAR: AR5 GWP100.");
            if(selected.some(s=>s.recipe.source!=="EMERGING"))indicatorNotes.push("Values are not harmonised to one IPCC report.");
          }
          if(state.section!=="all"){
            const chosen=Array.isArray(state.section)?state.section:[state.section], households=chosen.includes(M.HOUSEHOLDS);
            indicatorNotes.push(!households?"Sector totals exclude direct household emissions; select Households to show them.":chosen.length>1?"Producer sectors exclude direct household emissions, shown separately as Households.":"Households: direct final-demand emissions, not allocated to producer sectors.");
          }
          else if(selected.some(s=>s.recipe.final_demand_emissions_loaded!==false))indicatorNotes.push("Totals include direct final-demand emissions where supplied.");
        }
        $("[data-indicator-details]").textContent=indicatorNotes.join(" ");
        const cautions=[];
        if(selected.some(s=>state.metric==="gdp"&&s.recipe.gdp_proxy))cautions.push("EMERGING: GDP uses value added as a proxy.");
        if(state.metric==="gdp"&&selected.some(s=>s.recipe.gdp_quality_note))cautions.push(M.unique(selected.filter(s=>s.recipe.gdp_quality_note).map(s=>s.recipe.source)).join(" / ")+": source accounting residuals retained.");
        if(state.metric==="ghg"&&selected.some(s=>s.recipe.ghg_usable===false))cautions.push("Some EXIOBASE GHG totals withheld: source errors.");
        if(selected.some(s=>s.recipe.price_basis==="Previous year prices"))cautions.push("WIOD PYP: previous-year prices.");
        $("[data-indicator-note]").textContent=cautions.join(" ");
        $("[data-indicator-note]").hidden=!cautions.length;
        $("[data-households]").hidden=multiple||state.metric!=="ghg"||r?.household_ghg==null;
        const population=s&&M.reference(wb,r?.iso3,s.recipe.year).population;
        const household=state.perCapita?(population>0?r?.household_ghg/population:null):r?.household_ghg/1000;
        $("[data-households]").textContent=`Direct final-demand emissions, included once in Whole economy and excluded from sector totals: ${compact(household)} ${M.unit(state)}.`;
        const missing=rows.filter(r=>!["World Bank","EDGAR"].includes(r.database)&&r.value==null);
        $("[data-availability]").textContent=missing.length?"Some observations unavailable; see Other notes.":"";
        const referenceNames=M.unique(rows.filter(row=>M.isReference(row)&&row.value!=null).map(row=>row.database));
        const referenceSymbol=M.selectedYears(snapshots,state).length===1?"—":barView?"◆":"−";
        $("[data-reference-caption]").textContent=referenceNames.length?`${referenceSymbol} ${referenceNames.join(" / ")}: same region and year.${state.metric==="ghg"?" EDGAR: territorial, AR5 GWP100.":""}`:state.metric==="ghg"&&state.section!=="all"?"EDGAR covers whole-economy totals only.":state.metric==="ghg"||state.metric==="gdp"?"No matching reference.":"";
        // The example covers one reading; a visible hint explains how to enable it.
        const scriptReady=selected.length===1&&rows.some(row=>!["World Bank","EDGAR"].includes(row.database)&&row.value!=null);
        $("[data-script]").disabled=!scriptReady;
        $("[data-script]").title=scriptReady?"A short MARIO starting point for the selected database":"";
        $("[data-script-hint]").textContent=scriptReady?"":selected.length!==1?"To enable the MARIO example, keep one database version and one year selected (use ▸ beside a database to pick its version).":"The MARIO example needs at least one available value: change the country, indicator or sector.";
        $("[data-script-hint]").hidden=scriptReady;
        $("[data-export]").disabled=!chartRows.some(r=>r.value!=null);
        $("[data-export-label]").textContent="";
        // Prefer a selected-year recipe: availability/methods can change
        // within one coverage version (e.g. ADB emissions stop before 2024).
        const noteRecipes=new Map();
        for(const snapshot of [...selected,...candidates()]) {
          const id=M.seriesKey(snapshot.recipe);
          if(!noteRecipes.has(id))noteRecipes.set(id,snapshot.recipe);
        }
        const recipes=[...noteRecipes.values()];
        $("[data-reading-notes]").innerHTML=recipes.map(recipe=>{
          const selectedGroup=selected.filter(s=>M.seriesKey(s.recipe)===M.seriesKey(recipe));
          const group=selectedGroup.length?selectedGroup:candidates().filter(s=>M.seriesKey(s.recipe)===M.seriesKey(recipe));
          const indicators=["Value added",group.some(s=>M.metricAvailable([s],"gdp"))?"GDP":"GDP unavailable",group.some(s=>M.metricAvailable([s],"ghg"))?"GHG":"GHG unavailable"];
          const qualitySources=M.unique(group.flatMap(s=>s.recipe.ghg_quality_sources||[]));
          const gaps=M.unique(missing.filter(r=>r.series===M.seriesKey(recipe)).map(r=>r.note));
          const scopeNotes=recipe.source==="GLORIA"?M.unique(group.map(s=>s.recipe.scope_note).filter(Boolean)).join(" "):"";
          const accountingNotes=state.metric==="gdp"?M.unique(group.map(s=>s.recipe.gdp_note).filter(Boolean)).join(" "):"";
          return `<p><strong>${esc(recipe.label)}</strong> · ${esc(group.map(s=>s.recipe.year).join(", "))}. ${esc(indicators.join("; "))}. ${esc(recipe.ghg_method)} ${esc(recipe.ghg_note||"")} ${esc(scopeNotes)} ${esc(accountingNotes)} ${esc(gaps.join(". "))} ${qualitySources.map((url,i)=>`<a href="${esc(url)}">${i===0?"Release correction":"Source issue report"}</a>`).join(" · ")}</p>`;
        }).join("");
        $("[data-source]").innerHTML=recipes.map(r=>`<a href="${esc(r.source_url)}">${esc(r.label)}</a> · <a href="${new URL(r.parser_guide,base).href}">Parsing guide</a> · <a href="${esc(r.license_url)}">Source licence</a>`).join("<br>")+`<br><a href="https://data.worldbank.org/indicator/NY.GDP.PCAP.CD">World Bank · WDI</a> · retrieved ${esc(wb.retrieved_at.slice(0,10))} · <a href="${esc(wb.license_url)}">CC BY 4.0</a>. Monetary values use same-year exchange rates; <a href="https://ec.europa.eu/eurostat/databrowser/view/ert_bil_eur_a/default/table?lang=en">Eurostat EUR/ECU</a> is used before 1999. Aggregate regions are not assigned a population.`;
        const edgarSource=M.isWorld(state.country)||state.perCapita?edgar.report:edgar;
        if(state.metric==="ghg") $("[data-source]").innerHTML+=`<br><a href="${esc(edgarSource.source_url)}">EDGAR · 2026</a> · <a href="${esc(edgarSource.download_url)}">Published reference values</a> · <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/">IEA–EDGAR CO₂: CC BY-NC-ND 4.0</a>. © European Union 2026 / JRC / IEA; values unchanged.`;
        const sourceDetails=$("[data-source-details]");
        sourceDetails.hidden=false;
        $("[data-source-list]").innerHTML=$("[data-source]").innerHTML;
        if(recipes.length>1) {
          $("[data-source]").innerHTML="";
        } else if(recipes.length===1) {
          const r=recipes[0];
          $("[data-source]").innerHTML=`<a href="${esc(r.source_url)}">${esc(r.label)}</a> · <a href="${new URL(r.parser_guide,base).href}">Parsing guide</a> · <a href="${esc(r.license_url)}">Licence</a>`;
        }
        $("[data-message]").textContent="";
        root.setAttribute("aria-busy", "false");
      }
      const refreshAppearance=()=>{if(root.getAttribute("aria-busy")!=="true"&&!$("[data-chart]").hidden&&$("[data-chart]").data)drawChart(chartRows).catch(()=>{});};
      new MutationObserver(refreshAppearance).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
      matchMedia("(prefers-color-scheme: dark)").addEventListener("change",refreshAppearance);
      let lastChartWidth=0;
      new ResizeObserver(entries=>{
        const width=Math.round(entries[0].contentRect.width);
        if(width!==lastChartWidth){lastChartWidth=width;refreshAppearance();}
      }).observe($("[data-chart]"));
      function filterCountries() {
        const query=$("[data-country-search]").value.toLowerCase();
        root.querySelectorAll('[data-options="country"] [data-choice-search]').forEach(el=>el.hidden=!el.dataset.choiceSearch.includes(query));
      }
      root.addEventListener("input",e=>{if(e.target.matches("[data-country-search]"))filterCountries();});
      root.addEventListener("change", e=>{
        const el=e.target;
        if(el.matches("[data-compare-family]")){
          state.families=el.checked?M.unique([...state.families,el.value]):state.families.filter(f=>f!==el.value);
          // Re-checking a family whose facets select nothing restores every version.
          if(el.checked && (!compareFacets[el.value] || Array.isArray(versionChoices[el.value])&&!versionChoices[el.value].length)){delete compareFacets[el.value];versionChoices[el.value]="all";}
          state.section="all";
        }
        if(el.matches("[data-compare-facet]")){
          const family=el.dataset.compareFacet, key=el.dataset.facetKey;
          const all=[...root.querySelectorAll(`[data-compare-facet="${family}"][data-facet-key="${key}"]`)];
          const checked=all.filter(x=>x.checked).map(x=>x.value);
          if(!compareFacets[family]) compareFacets[family]={};
          compareFacets[family][key]=checked.length===all.length&&checked.length>1?"all":checked.length===1?checked[0]:checked;
          if(!state.families.includes(family)) state.families=M.unique([...state.families,family]);
          state.section="all";
        }
                if(el.matches("[data-subset]")) {
          const kind=el.dataset.subset;
          const special=kind==="country"?"world":"all";
          const current=state[kind];
          let selection;
          if(el.value===special)selection=el.checked?special:[];
          else {
            const previous=current===special?(kind==="country"?[]:[...root.querySelectorAll(`[data-subset="${kind}"]`)].filter(x=>x.value!==special).map(x=>x.value)):Array.isArray(current)?current:[current];
            const chosen=el.checked?M.unique([...previous.map(String),el.value]):previous.map(String).filter(v=>v!==el.value);
            selection=chosen.length===1?(kind==="year"?Number(chosen[0]):chosen[0]):chosen.length?(kind==="year"?chosen.map(Number):chosen):[];
          }
          state[kind]=selection;
        }
        if(el.matches("[data-metric]")) state.metric=el.value;
        if(el.matches("[data-measure]")) state.perCapita=el.value==="per-capita";

        render();
      });
      // Keyboard activation of a summary also arrives as a click: never toggle a disabled picker.
      root.addEventListener("click",e=>{if(e.target.closest(".eb-picker.is-disabled > summary"))e.preventDefault();},true);
      root.addEventListener("click",e=>{
        const b=e.target.closest("button"),p=e.target.closest("path[data-iso]");
        if(p&&!dragged){state.country=p.dataset.iso;render();return;}
        if(!b)return;
        if(b.dataset.bulkFilter){
          if(b.disabled)return;
          e.stopPropagation(); // Keep an open picker open while its options refresh.
          const kind=b.dataset.bulkFilter, action=b.dataset.bulkAction, select=action==="select";
          if(kind==="databases"){
            if(action==="env-extended"){
              state.environmentallyExtended=!state.environmentallyExtended;
              const pool=availableReadings();
              const envFamilies=families.filter(f=>pool.some(s=>s.recipe.source===f));
              state.families=[...envFamilies];
              for(const family of families){versionChoices[family]=envFamilies.includes(family)?M.unique(pool.filter(s=>s.recipe.source===family).map(s=>M.version(s.recipe))):[];delete compareFacets[family];}
            }else{
              state.environmentallyExtended=false;
              state.families=select?[...families]:[];
              for(const family of families){versionChoices[family]=select?"all":[];delete compareFacets[family];}
            }
            state.section="all";
          }else if(/^last\d+$/.test(action)){
            const n=Number(action.slice(4));
            const values=[...root.querySelectorAll(`[data-subset="${kind}"]`)].filter(el=>!el.disabled&&!["all","world"].includes(el.value)).map(el=>Number(el.value)).sort((a,b)=>a-b);
            const recent=M.recentYears(values,n).map(String);
            state[kind]=recent;
          }else{
            const world=kind==="country"&&!!$('[data-options="country"] input[value="world"]');
            const values=[...root.querySelectorAll(`[data-subset="${kind}"]`)].filter(el=>!el.disabled&&!["all","world"].includes(el.value)).map(el=>el.value);
            const selection=!select?[]:kind==="country"?world?"world":values:"all";
            state[kind]=selection;
          }
          render();
          const next=$(`[data-bulk-filter="${kind}"][data-bulk-action="${b.dataset.bulkAction}"]`);
          if(next&&!next.disabled&&(!next.closest("details")||next.closest("details").open))next.focus({preventScroll:true});
          return;
        }
        if(b.dataset.facetBulk){
          e.stopPropagation();
          const family=b.dataset.facetFamily, key=b.dataset.facetKey, action=b.dataset.facetBulk;
          if(!compareFacets[family]) compareFacets[family]={};
          compareFacets[family][key]=action==="select"?"all":[];
          if(action==="select"&&!state.families.includes(family)) state.families=M.unique([...state.families,family]);
          state.section="all";
          render();
          $(`[data-facet-bulk="${action}"][data-facet-family="${CSS.escape(family)}"][data-facet-key="${key}"]`)?.focus({preventScroll:true});
          return;
        }
        if(b.dataset.expandFamily){const f=b.dataset.expandFamily;if(openFamilies.has(f)){openFamilies.delete(f);}else{openFamilies.clear();openFamilies.add(f);}controls();return;}
        if(b.dataset.view){manualView=b.dataset.view==="auto"?null:b.dataset.view;render();}
        if(b.dataset.zoom){if(b.dataset.zoom==="reset"){zoom=1;panX=panY=0;}else{const next=Math.max(1,Math.min(8,zoom*(b.dataset.zoom==="in"?1.5:1/1.5))),ratio=next/zoom;panX=450-(450-panX)*ratio;panY=182.5-(182.5-panY)*ratio;zoom=next;}transform();}
        if(b.hasAttribute("data-export")){
          const rows=M.exportRows(chartRows,snapshots,state,displayScale,C);
          save(csv(rows),`mario-compare-${state.country}-${Array.isArray(state.year)?state.year.length?`${Math.min(...state.year.map(Number))}-${Math.max(...state.year.map(Number))}`:"none":state.year}-${state.metric}.csv`,"text/csv;charset=utf-8");
        }
        if(b.hasAttribute("data-script")){const s=active()[0];save(M.pythonStart(s,state,mapping(s)),`mario-${s.recipe.id}-${state.country}.py`,"text/x-python;charset=utf-8");$("[data-message]").textContent="Set your local database path. The example calculates native MARIO values. Comments describe the remaining steps; it does not reproduce the finished CSV by itself.";}
      });
      root.addEventListener("keydown",e=>{if(e.target.matches("path[data-iso]")&&["Enter"," "].includes(e.key)){e.preventDefault();state.country=e.target.dataset.iso;render();}});
      document.addEventListener("click",e=>root.querySelectorAll(".eb-picker[open]").forEach(el=>{if(!el.contains(e.target))el.open=false;}));
      document.addEventListener("keydown",e=>{if(e.key==="Escape"){root.querySelectorAll(".eb-picker[open]").forEach(el=>{el.open=false;el.querySelector("summary").focus();});if($("[data-chart]").data)window.Plotly.Fx.unhover($("[data-chart]"));}});
      const svg=$("[data-map]");
      svg.addEventListener("pointerdown",e=>{if(e.button!==0)return;dragged=false;drag={x:e.clientX,y:e.clientY,px:panX,py:panY};});
      svg.addEventListener("pointermove",e=>{if(!drag||zoom===1)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>3)dragged=true;const scale=900/svg.getBoundingClientRect().width;panX=drag.px+dx*scale;panY=drag.py+dy*scale;transform();});
      window.addEventListener("pointerup",()=>{drag=null;});svg.addEventListener("pointercancel",()=>{drag=null;});
      await render();
    }).catch(error=>{root.innerHTML=`<p class="eb-error">The browser could not load its data. ${esc(error.message)}</p>`;root.setAttribute("aria-busy","false");});
})();
