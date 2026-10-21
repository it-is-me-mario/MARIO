/* Pure selection and calculation helpers, shared by the browser and its tests. */
((global) => {
  "use strict";
  // Build-generated summaries share recipes, geography and correspondences.
  // They retain whole-economy totals; sector vectors are loaded on demand.
  function unpackBrowserIndex(index) {
    if (index.schema_version !== 1) throw new Error("Unsupported browser data format");
    const snapshots = index.readings.map(reading => ({
      metadata_only: true, summary_only: true, availability: reading.availability,
      recipe: Object.fromEntries(Object.entries(reading.recipe).map(([key, i]) => [key, index.recipe_values[key][i]])),
      regions: index.geographies[reading.geography].map((region, i) => ({...region,
        gdp: reading.totals[i][0], value_added_total: reading.totals[i][1],
        ghg_total: reading.totals[i][2], household_ghg: reading.totals[i][3]})),
      ...(reading.gdp_validation ? {provenance: {gdp_bridge: {validation: reading.gdp_validation}}} : {})
    }));
    const mappings = Object.fromEntries(Object.entries(index.mappings).map(([id, i]) => [id, index.mapping_values[i]]));
    return {snapshots, mappings};
  }
  const needsDetailedReading = (snapshot, state) => snapshot.metadata_only === true &&
    !(Array.isArray(state.section) && !state.section.length) &&
    !(Array.isArray(state.country) && !state.country.length) &&
    !(snapshot.summary_only === true && state.section === "all");
  const version = r => r.source === "WIOD" ? [r.release,r.price_basis || "Current prices",r.table || r.parser_options?.table || "IOT"].join(" · ") : (r.source === "ADB" || r.source === "EMERGING" || r.source === "EORA" || r.source === "OECD" && r.parser_options?.dataset === "ICIO") ? String(r.release) : [r.release, r.parser_options?.unit === "Hybrid" ? `hybrid ${r.parser_options?.table || r.table || "SUT"}` : r.table==="SUT" || r.parser_options?.table==="SUT" ? "SUT" : r.parser_options?.system || (r.parser_options?.iot_mode==="product"?"pxp":r.parser_options?.iot_mode==="industry"?"ixi":null) || (r.source==="EXIOBASE"&&r.parser_options?.table==="SUT"?"SUT":r.dimension)].filter(Boolean).join(" · ");
  const seriesKey = r => JSON.stringify([r.source, ...Object.values(recipeFacets(r))]);
  const key = r => r.iso3 || r.code;
  const unique = xs => [...new Set(xs)];
  const recentYears = (available, count, currentYear = new Date().getFullYear()) =>
    unique(available.map(Number)).filter(year => year < currentYear).sort((a,b)=>a-b).slice(-count);
  // Browser scope is international: at least two individually represented
  // countries, independently of whether a complete World total is available.
  const isMRIO = snapshot => unique(snapshot.regions.filter(r=>r.kind==='country').map(r=>r.iso3||r.code||r.label)).length>1;
  const reference = (wb, iso, year) => (wb.countries[iso] || wb.aggregates?.[iso])?.years[String(year)] || {};
  const isWorld = country => country === "world" || country === "all";
  const isGlobal = snapshot => snapshot.recipe.world_total_available !== false && (snapshot.recipe.world_total_available === true || ["EXIOBASE","ADB","Asian Development Bank","OECD","FIGARO","WIOD","EMERGING"].includes(snapshot.recipe.source));
  function regionKey(snapshot, region) {
    if (region.kind === "country") return key(region);
    const geography=snapshot.regions.map(key).sort().join("|");
    let hash=2166136261;for(const c of geography)hash=Math.imul(hash^c.charCodeAt(0),16777619);
    return `aggregate:${snapshot.recipe.source}:${(hash>>>0).toString(16)}:${key(region)}`;
  }
  const findRegion = (snapshot, selection) => snapshot?.regions.find(r=>regionKey(snapshot,r)===selection);
  function regionChoices(snapshots) {
    const choices=new Map();
    for(const s of snapshots)for(const r of s.regions){
      const id=regionKey(s,r);
      if(!choices.has(id)) choices.set(id,{...r,id,source:s.recipe.source,versions:[]});
      const item=choices.get(id);item.versions=unique([...item.versions,version(s.recipe)]);
    }
    return [...choices.values()].sort((a,b)=>a.name.localeCompare(b.name));
  }
  const metricAvailable = (snapshots, metric) => snapshots.length>0 && snapshots.every(s=>metric==="ghg"&&s.recipe?.ghg_usable===false ? false : s.metadata_only ? s.availability?.[metric] === true : s.regions.length>0 && s.regions.every(r=>metric==="gdp"?r.gdp!=null:Array.isArray(r[metric])));
  const includes = (selection, value) => selection === "all" || (Array.isArray(selection) ? selection.map(String).includes(String(value)) : String(selection) === String(value));
  const selectedYears = (snapshots, state) => state.year === "all" ? years(snapshots, state) : (Array.isArray(state.year) ? state.year : [state.year]).map(Number).sort((a,b)=>a-b);
  // A reading is one combination of units, release, table format and IOT system.
  function recipeFacets(recipe) {
    const p=recipe.parser_options || {}, format=recipe.table || p.table || "IOT";
    // The Hybrid HIOT parser maps its columns onto the product axis.
    const system=format === "SUT" ? null : p.system || (p.iot_mode === "product" || recipe.source === "EXIOBASE" && p.unit === "Hybrid" ? "pxp" : p.iot_mode === "industry" ? "ixi" : recipe.dimension || null);
    return {units:recipe.native_units || p.unit || "Monetary", version:String(recipe.release ?? ""), format, system, price:recipe.price_basis || "Current prices"};
  }
  function focusFacets(snapshots, family, requested={}, selectedYears="all") {
    const recipes=snapshots.filter(s=>s.recipe.source===family).map(s=>s.recipe);
    const period=selectedYears==="all"?[]:(Array.isArray(selectedYears)?selectedYears:[selectedYears]).map(Number);
    // Every explicitly selected year must have a reading for an offered option.
    const eligible=(pool,key)=>unique(pool.map(r=>recipeFacets(r)[key])).filter(value=>value!=null &&
      period.every(year=>pool.some(r=>Number(r.year)===year&&recipeFacets(r)[key]===value)));
    const familyUnits=unique(recipes.map(r=>recipeFacets(r).units));
    const allUnits=eligible(recipes,"units");
    function keep(selection, available, fallback) {
      // An empty upstream facet must not erase a still-valid downstream preference.
      if(!available.length)return selection ?? [];
      if(selection==="all")return available.length===1?[available[0]]:"all";
      const kept=(selection==null?[]:Array.isArray(selection)?selection:[selection]).filter(v=>available.includes(v));
      return kept.length?kept:selection!=null&&Array.isArray(selection)&&!selection.length?[]:fallback?[fallback]:[];
    }
    const units=keep(requested.units,allUnits,allUnits.includes("Monetary")?"Monetary":allUnits[0]);
    const unitRecipes=recipes.filter(r=>includes(units,recipeFacets(r).units));
    const releases=eligible(unitRecipes,"version").sort((a,b)=>b.localeCompare(a,undefined,{numeric:true}));
    const hasVersions=recipes.some(r=>r.release);
    const selectedVersion=hasVersions?keep(requested.version,releases,releases[0]):"all";
    const versionRecipes=unitRecipes.filter(r=>includes(selectedVersion,recipeFacets(r).version));
    const prices=eligible(versionRecipes,"price").sort();
    const price=keep(requested.price,prices,prices.includes("Current prices")?"Current prices":prices[0]);
    const priceRecipes=versionRecipes.filter(r=>includes(price,recipeFacets(r).price));
    const formats=eligible(priceRecipes,"format").sort();
    const format=keep(requested.format,formats,formats.includes("IOT")?"IOT":formats[0]);
    const formatRecipes=priceRecipes.filter(r=>includes(format,recipeFacets(r).format));
    const systems=eligible(formatRecipes,"system").sort();
    const system=keep(requested.system,systems,systems.includes("ixi")?"ixi":systems[0]);
    // SUTs have no IOT system; a System selection only filters applicable IOTs.
    const versions=unique(formatRecipes.filter(r=>recipeFacets(r).system==null || includes(system,recipeFacets(r).system)).map(version));
    const fields=[...(family==="EXIOBASE"||familyUnits.length>1?[{key:"units",label:"Units",options:allUnits}]:[]),
      ...(hasVersions?[{key:"version",label:"Version",options:releases}]:[]),
      ...(unique(recipes.map(r=>recipeFacets(r).price)).length>1?[{key:"price",label:"Price basis",options:prices}]:[]),
      ...(family==="EXIOBASE"||unique(recipes.map(r=>recipeFacets(r).format)).length>1?[{key:"format",label:"Table format",options:formats}]:[]),
      ...(family==="EXIOBASE"||unique(recipes.map(r=>recipeFacets(r).system).filter(v=>v!=null)).length>1?[{key:"system",label:"System",options:systems,
        notApplicable:formatRecipes.length>0&&formatRecipes.every(r=>recipeFacets(r).system==null)}]:[])];
    return {selection:{units,version:selectedVersion,format,system,...(prices.length>1?{price}: {})}, fields, versions};
  }
  function latestVersions(snapshots, family) {
    const recipes=snapshots.filter(s=>s.recipe.source===family).map(s=>s.recipe);
    // Regular and Extended are coexisting ICIO variants, not successive releases.
    if(family === "OECD" && recipes.every(r=>r.parser_options?.dataset === "ICIO")) {
      const latestYear=Math.max(...recipes.map(r=>r.year));
      return unique(recipes.filter(r=>r.year===latestYear).map(version));
    }
    if(family === "WIOD") return unique(recipes.filter(r=>r.price_basis!=="Previous year prices").map(version));
    if(family === "ADB") {
      const largest=Math.max(...recipes.map(r=>Number.parseInt(r.release,10)));
      return unique(recipes.filter(r=>Number.parseInt(r.release,10)===largest).map(version));
    }
    if(recipes.every(r=>!r.release))return unique(recipes.map(version));
    const releases=unique(recipes.map(r=>r.release));
    const numeric=releases.every(r=>/^\d+(\.\d+)*$/.test(String(r)));
    releases.sort((a,b)=>numeric?String(b).localeCompare(String(a),undefined,{numeric:true}):
      Math.max(...recipes.filter(r=>r.release===b).map(r=>r.year))-Math.max(...recipes.filter(r=>r.release===a).map(r=>r.year)));
    return unique(recipes.filter(r=>r.release===releases[0]).map(version));
  }
  function selected(snapshots, state, includeYear = true) {
    return snapshots.filter(s => state.families.includes(s.recipe.source) &&
      (!state.environmentallyExtended || metricAvailable([s], 'ghg')) &&
      (!state.versions[s.recipe.source] || includes(state.versions[s.recipe.source], version(s.recipe))) &&
      (!includeYear || includes(state.year, s.recipe.year)));
  }
  function countryOptions(snapshots, state) {
    const readings=selected(snapshots,state), regions=regionChoices(readings);
    const hasWorld=readings.some(isGlobal), requested=state.country;
    const kept=(Array.isArray(requested)?requested:[requested]).filter(id=>regions.some(r=>r.id===id));
    const selection=Array.isArray(requested)&&!requested.length?[]:isWorld(requested)&&hasWorld?"world":kept.length===1?kept[0]:kept.length?kept:
      hasWorld?"world":regions[0]?.id || [];
    return {regions,hasWorld,selection};
  }
  function metricAvailableForSelection(snapshots, state, metric) {
    // Explicitly reviewed source errors create gaps in an otherwise available
    // time series. Ordinary missing extensions still disable the indicator.
    const readings=selected(snapshots,state);
    const eligible=metric==="ghg"?readings.filter(s=>s.recipe.ghg_usable!==false):readings;
    if(!metricAvailable(eligible,metric))return false;
    // A selected family/version without this indicator cannot become eligible
    // merely because its readings are absent in the requested year.
    const combinations=new Map();
    for(const s of selected(snapshots,state,false)) {
      const id=seriesKey(s.recipe);
      combinations.set(id,(combinations.get(id)||false)||metricAvailable([s],metric));
    }
    return [...combinations.values()].every(Boolean);
  }
  const years = (snapshots, state) => unique(selected(snapshots, state, false).map(s => s.recipe.year)).sort((a,b) => a-b);
  const HOUSEHOLDS = "households", HOUSEHOLDS_LABEL = "Households · direct emissions";
  const householdEmissions = (snapshot, region) => snapshot.recipe.final_demand_emissions_loaded === false ? null : region.household_ghg ?? null;
  function sectorIndices(snapshot, mapping, section, metric = "value_added") {
    if (section === "all") return (metric === "ghg" ? snapshot.recipe.ghg_sectors || snapshot.recipe.sectors : snapshot.recipe.sectors).map((_,i) => i);
    if (metric === "ghg" && snapshot.recipe.ghg_sectors) return [];
    return mapping?.entries.filter(e => e.section === section).map(e => e.index) || [];
  }
  function value(snapshot, region, state, wb, mapping) {
    if (!snapshot || !region || state.metric==="ghg"&&snapshot.recipe.ghg_usable===false) return null;
    const r = snapshot.recipe;
    let result;
    if (state.section === HOUSEHOLDS) result = state.metric === "ghg" ? householdEmissions(snapshot, region) : null;
    else if (state.metric === "gdp") result = region.gdp ?? null;
    else if (snapshot.summary_only) {
      // Never substitute a whole-economy total for a requested sector.
      result = state.section === "all" ? region[state.metric + "_total"] ?? null : null;
    }
    else {
      const indices = sectorIndices(snapshot, mapping, state.section, state.metric);
      result = region[state.metric] && indices.length ? indices.reduce((sum,i) => sum + region[state.metric][i], 0) : null;
    }
    if (result == null) return null;
    if (state.metric === "ghg" && state.section === "all" && r.final_demand_emissions_loaded !== false && region.household_ghg != null) result += region.household_ghg;
    if (state.metric !== "ghg") {
      const exchange = r.year >= 1999 ? reference(wb, "DEU", r.year).local_currency_per_usd : null;
      const euroRate = wb.currency_rates?.EUR?.years[String(r.year)] ?? (exchange > 0 ? 1 / exchange : null);
      const rate = r.currency === "USD" ? 1 : r.currency === "EUR" ? euroRate : null;
      if (rate == null) return null;
      result *= rate;
    }
    if (state.perCapita) {
      if (state.section !== "all" || region.kind !== "country") return null;
      const population = reference(wb, region.iso3, r.year).population;
      if (!(population > 0)) return null;
      result /= population;
    }
    else if (state.metric === "ghg") result /= isWorld(state.country) ? 1e6 : 1000; // Match native EDGAR Mt (world) or Gg (country).
    return Number.isFinite(result) ? result : null;
  }
  const basis = (recipe, metric) => metric === "gdp" ? recipe.gdp_basis : metric === "ghg" ? recipe.ghg_basis || "Industry production accounts" : recipe.value_added_basis || "Industry production accounts";
  const unit = state => (state.metric === "ghg" ? (state.perCapita ? "t CO₂eq" : isWorld(state.country) ? "Mt CO₂eq" : "Gg CO₂eq") : state.priceBasis === "Previous year prices" ? "previous-year US$" : state.priceBasis === "mixed" ? "US$ (mixed price bases)" : "current US$") + (state.perCapita ? " / person" : "");
  function worldValue(snapshot, state, wb, mapping) {
    if(!snapshot || !isGlobal(snapshot)) return null;
    const values=snapshot.regions.map(r=>value(snapshot,r,{...state,country:"world",perCapita:false},wb,mapping));
    if(!values.length||values.some(v=>v==null))return null;
    const total=values.reduce((a,b)=>a+b,0);
    if(!state.perCapita)return total;
    const population=reference(wb,"WLD",snapshot.recipe.year).population;
    return state.section==="all"&&population>0?total*(state.metric==="ghg"?1e6:1)/population:null;
  }
  const isReference = row => ["World Bank","EDGAR"].includes(row.database);
  const sectionName = (mapping, section) => section === "all" ? "Whole economy" : section === HOUSEHOLDS ? HOUSEHOLDS_LABEL : mapping?.sections?.[section] ? `${section} · ${mapping.sections[section]}` : String(section);
  function observations(snapshots, state, wb, mappings, edgar = {countries:{}}) {
    if(Array.isArray(state.country))return state.country.flatMap(country=>observations(snapshots,{...state,country},wb,mappings,edgar));
    // Several sector aggregates: one row per aggregate (charts stack them; whole-economy references are not repeated).
    if(Array.isArray(state.section))return state.section.flatMap(section=>observations(snapshots,{...state,section},wb,mappings,edgar));
    const world=isWorld(state.country), country=world?"world":state.country, referenceCode=world?"WLD":country;
    const available=selected(snapshots,state,false), templates=[...new Map(available.map(s=>[seriesKey(s.recipe),s])).values()];
    const period=selectedYears(snapshots,state), rows=[];
    for(const template of templates) for(const year of period) {
      const s=available.find(s=>seriesKey(s.recipe)===seriesKey(template.recipe)&&s.recipe.year===year);
      const region=findRegion(s,country), mapping=s&&mappings[s.recipe.id];
      const val=world?worldValue(s,state,wb,mapping):value(s,region,state,wb,mapping);
      const name=world?"World":region?.name || regionChoices(available).find(r=>r.id===country)?.name || country;
      let note=!s?`Available years: ${available.filter(x=>seriesKey(x.recipe)===seriesKey(template.recipe)).map(x=>x.recipe.year).join(", ")}`:
        world&&!isGlobal(s)?s.recipe.scope_note || "National model; a World total is not available":
        !world&&!region?"Region is not represented with this definition in this reading":
        state.metric==="ghg"&&!metricAvailable([s],"ghg")?s.recipe.ghg_unavailable_reason||"No verified GHG aggregate":
        state.section===HOUSEHOLDS&&val==null?"Direct household emissions are not available in this reading":
        ["gdp","value_added"].includes(state.metric)&&s.recipe.value_added_available===false?"GDP and value added are not supplied by this reading":
        state.metric==="gdp"&&val==null?"GDP tax bridge not verified; value added is available":val==null?"No matching population or exchange rate":"";
      if(val!=null&&state.metric==="gdp"&&s.recipe.gdp_bridge_verified===false)note=s.recipe.gdp_proxy?s.recipe.gdp_note:"GDP estimate; market-price bridge unverified";
      if(val!=null&&state.metric==="gdp"&&s.recipe.gdp_quality_note)note=[note,s.recipe.gdp_quality_note].filter(Boolean).join(" ");
      if(val!=null&&state.metric==="ghg") note=[s.recipe.ghg_note, state.section==="all" ? s.recipe.final_demand_emissions_loaded===false ? "Direct final-demand emissions unavailable; industry/commodity accounts only." : "Includes direct final-demand emissions where supplied." : state.section===HOUSEHOLDS ? "Direct final-demand emissions of households, not allocated to producer sectors." : "Producer accounts only; direct final-demand emissions are not allocated to sectors."].filter(Boolean).join(" ");
      const wbVal=state.metric==="gdp"&&template.recipe.price_basis!=="Previous year prices"?reference(wb,referenceCode,year)[state.perCapita?"gdp_per_capita":"gdp"]??null:null;
      rows.push({series:seriesKey(template.recipe),database:template.recipe.source,...recipeFacets(template.recipe),release:String(template.recipe.release ?? ""),version:version(template.recipe),year,country,country_name:name,
        label:`${name} · ${template.recipe.source} · ${version(template.recipe)}`+(state.section==="all"?"":` · ${sectionName(mapping,state.section)}`),indicator:state.metric,sector:state.section,sector_name:sectionName(mapping,state.section),classification:mapping?.classification||"",
        unit:unit(state),value:val,gwp_basis:state.metric==="ghg"?template.recipe.gwp_basis||"":"",gwp_horizon:state.metric==="ghg"?template.recipe.gwp_horizon??null:null,world_bank:wbVal,difference_percent:val!=null&&wbVal>0?(val/wbVal-1)*100:null,basis:basis(template.recipe,state.metric),note});
    }
    if(state.metric==="gdp"&&!available.some(s=>s.recipe.price_basis==="Previous year prices"))for(const year of period) {
      const v=reference(wb,referenceCode,year)[state.perCapita?"gdp_per_capita":"gdp"];
      if(v!=null)rows.push({series:"World Bank",database:"World Bank",version:"WDI",year,country,country_name:world?"World":wb.countries[country]?.name||country,
        indicator:"gdp",sector:"all",classification:"",unit:unit(state),value:v,world_bank:null,difference_percent:null,basis:"GDP at market prices",note:"External reference; published World Bank value"});
    }
    if(state.metric==="ghg"&&state.section==="all")for(const year of period){
      const entry=state.perCapita?edgar.per_capita?.[referenceCode]:world?edgar.world:edgar.countries[country];
      const v=entry?.years[String(year)];
      const report=world||state.perCapita;
      if(v!=null)rows.push({series:"EDGAR",database:"EDGAR",version:"2026 · AR5",year,country,country_name:world?"World":entry.name,
        indicator:"ghg",sector:"all",classification:"",unit:unit(state),value:v,gwp_basis:edgar.gwp||"",world_bank:null,difference_percent:null,
        source_url:report?edgar.report.source_url:edgar.source_url,download_url:report?edgar.report.download_url:edgar.download_url,
        gwp_basis:"IPCC AR5",gwp_horizon:100,basis:"Territorial GHG; excludes LULUCF; AR5 GWP100",note:"Published reference, unchanged; household emissions included. Different boundary from MRIO accounts; some source territories are grouped."});
    }
    return rows;
  }
  function automaticView(snapshots, state) {
    return selectedYears(snapshots,state).length>1?"series":"comparison";
  }
  function exportRows(rows,snapshots,state,scale,charts) {
    // References remain in the chart. Export only selected MRIO observations;
    // in particular, do not redistribute re-scaled IEA-EDGAR reference cells.
    const result=rows.filter(r=>!isReference(r)).map(r=>{
      const recipe=snapshots.find(s=>s.recipe.source===r.database&&version(s.recipe)===r.version&&s.recipe.year===r.year)?.recipe;
      const fx=state.metric!=="ghg"&&recipe?.currency&&recipe.currency!=="USD";
      const ecu=fx&&recipe.currency==="EUR"&&r.year<1999;
      const wbInputs=[...(fx&&!ecu?["official exchange rates (PA.NUS.FCRF)"]:[]),...(state.perCapita?["population (SP.POP.TOTL)"]:[])];
      const inputSources=[...(wbInputs.length?["World Bank, World Development Indicators: "+wbInputs.join("; ")+". CC BY 4.0."]:[]),...(ecu?["Eurostat annual EUR/ECU exchange rates; Eurostat data reuse policy."]:[])];
      return {database:r.database,version:r.version,units:r.units||"",table_format:r.format||"",system:r.system||"",price_basis:r.price||"",year:r.year,country:r.country||state.country,
        indicator:state.metric,sector:Array.isArray(r.sector)?r.sector.join("; "):r.sector||state.section,
        classification:r.classification||"",value:charts.scaled(r.value,scale),unit:scale.unit,
        basis:r.basis||"",gwp_basis:r.gwp_basis||"",gwp_horizon:r.gwp_horizon??"",note:r.note||"",
        source_url:recipe?.source_url||"",source_license_url:recipe?.license_url||"",attribution:recipe?.attribution||recipe?.label||"",
        additional_inputs:inputSources.join(" "),additional_input_terms:[...(wbInputs.length?["https://datacatalog.worldbank.org/public-licenses"]:[]),...(ecu?["https://ec.europa.eu/eurostat/help/copyright-notice"]:[])].join("; "),
        changes:"MARIO-derived aggregate; see accounting basis and method. Monetary conversion and per-capita adjustment apply where selected; any additional input providers are credited. Reference observations are not included."};
    });
    if(result.length)for(const key of Object.keys(result[0])) {
      if(result.every(row=>row[key]===""))for(const row of result)delete row[key];
    }
    return result;
  }
  function sectionSummary(mapping, section) {
    const list = Array.isArray(section) ? section : [section], codes = list.filter(code => code !== HOUSEHOLDS);
    const parts = [...(codes.length ? [`${mapping?.classification || "sector"} ${codes.length > 1 ? "sections " + codes.join(", ") : "section " + codes[0]}`] : []),
      ...(list.includes(HOUSEHOLDS) ? ["Households (EY)"] : [])];
    return parts.join(" and ") + (list.length > 1 ? ", stacked" : "");
  }
  function pythonStart(snapshot, state, mapping) {
    const r = snapshot.recipe;
    const py = x => x === true ? "True" : x === false ? "False" : x == null ? "None" : JSON.stringify(x);
    const options = Object.entries(r.parser_options).map(([k,v]) => `${k}=${py(k.endsWith("path") ? "/path/to/"+k : v)}`).join(", ");
    const country = isWorld(state.country)?"World (sum every native region once, including RoW)":findRegion(snapshot,state.country)?.code || state.country;
    const lines = [
      "# MARIO example · GPL-3.0: https://github.com/it-is-me-mario/MARIO/blob/main/LICENSE",
      "# This is a native-data starting point, not an exact reproduction of the browser CSV.",
      `# Source: ${r.source_url || "consult the selected publisher release"}`,
      `# Source data terms: ${r.license_url || "consult the selected publisher release"}`,
      `# Attribution: ${r.attribution || r.label}`,
      "# Obtain your own source files under their licence; no source data are embedded here.",
      "", "import mario", "", `# ${r.label}, ${r.year}. Set the path to your local source file/folder.`,
      `db = mario.${r.parser}(path="/path/to/database", ${options ? options+", " : ""}calc_all=False)`, ""];
    if (state.metric === "ghg") {
      lines.push("# "+r.ghg_method, "# Factors include the conversion from native units to tonnes CO2eq.", "gwp = {");
      Object.entries(r.ghg_factors).forEach(([name,factor]) => lines.push(`    ${py(name)}: ${factor},`));
      lines.push("}", "# Characterise the native MARIO rows with the reviewed unit conversions.",
        `values = db.get_block(${py(r.emissions_block || "E")}).loc[list(gwp)].T.mul(gwp).sum(axis=1)`, r.emissions_block === "Ec" ? "# Ec includes import-related commodity flows; it is not a territorial inventory." : "# values retains the producer/sector axis.");
      const chosenSections = state.section === "all" ? [] : Array.isArray(state.section) ? state.section : [state.section];
      if (state.section === "all" && r.final_demand_emissions_loaded !== false) lines.push(
        '# Whole economy: add the directly emitted final-demand accounts ONCE per region.',
        'direct_final_demand = db.get_block("EY").loc[list(gwp)].T.mul(gwp).sum(axis=1)',
        'totals = values.groupby(level="Region").sum() + direct_final_demand.groupby(level="Region").sum()');
      else if(r.final_demand_emissions_loaded === false) lines.push('# Direct final-demand emissions are unavailable; zero-filled EY is not an observation.');
      else if(chosenSections.includes(HOUSEHOLDS)) lines.push(
        '# Households: the directly emitted final-demand accounts (EY), not allocated to producer sectors.',
        'households = db.get_block("EY").loc[list(gwp)].T.mul(gwp).sum(axis=1).groupby(level="Region").sum()',
        ...(chosenSections.length > 1 ? ['# Sector totals exclude EY; keep households as their own aggregate.'] : []));
      else lines.push('# Sector totals exclude EY; do not allocate direct household emissions to producers.');
    } else {
      const excluded = Object.keys(r.expected_units?.["Factor of production"] || {}).filter(row => !r.value_added_rows.includes(row));
      lines.push("# Sum the value-added components, retaining region/industry detail.",
        r.value_added_factors ? `values = db.get_block(${py(r.value_added_block || "V")}).loc[${py(r.value_added_rows)}].T.mul(${py(r.value_added_factors)}).sum(axis=1)` :
        r.table === "SUT" ? `values = db.get_block(${py(r.value_added_block || "Va")}).loc[${py(r.value_added_rows)}].sum(axis=0)` : `values = db.GDP(exclude=${py(excluded)}, total=False)`,
        `# Native units: ${r.currency_scale === 1e6 ? "million " : r.currency_scale === 1e3 ? "thousand " : ""}${r.currency}.`);
      if (state.metric === "gdp" && r.tax_bridge === "sut_supply_product_taxes") lines.push(
        `# The whole-economy product-tax bridge is in db.get_block("Vc"), rows ${py(r.product_tax_rows)}.`,
        "# It is a total from the Supply table: do not add final-demand taxes again.");
      else if (state.metric === "gdp" && r.tax_bridge === "source_activity_taxes") lines.push(
        `# Net product taxes are only the ${py(r.product_tax_rows)} row of ${py(r.value_added_block || "V")}: add it to value added.`,
        "# This release has no final-use tax row, so there is nothing else to add.");
      else if (state.metric === "gdp" && r.tax_bridge === "gloria_valuations") lines.push(
        '# Parse the same GLORIA year with valuation="taxes" and valuation="subsidies", separately.',
        '# For each, sum U and Yc by the destination Region; add the source-signed sums to basic-price value added.',
        '# Subsidies are already negative: do not subtract them twice.');
      else if (state.metric === "gdp" && r.gdp_proxy) lines.push("# GDP proxy = native va sum. The final-demand tax bridge is unverified; no adjustment is invented.");
      else if (state.metric === "gdp") lines.push("# For GDP at market prices, add net product taxes on intermediate AND final uses.",
        "# MARIO's GDP() alone does not restore the final-demand tax bridge from the source.");
    }
    lines.push("", `# Selection on the website: ${country}; ${state.section === "all" ? "all industries" : sectionSummary(mapping, state.section)}.`,
      mapping?.entries?.length ? "# Next: aggregate industries using the downloadable sector correspondence," : "# Next: use your own verified sector mapping if you need industry aggregates,",
      "# then filter the region and the relevant rows/columns of values.");
    if (state.metric !== "ghg") lines.push(r.currency === "USD" ? `# Multiply native values by ${r.currency_scale} to obtain current USD; no currency conversion is needed.` : "# Scale to currency units and convert to current USD with the same-year exchange rate.");
    if (state.perCapita) lines.push("# For a national per-capita total, divide by World Bank population for the same year.");
    lines.push("# This is a MARIO starting point; the CSV contains the finished browser selection.", "");
    return lines.join("\n");
  }
  // Characterisation convention of one GHG row, from its declared GWP basis.
  function gwpConvention(row){
    const text=row.gwp_basis||"",horizon=row.gwp_horizon??(Number(text.match(/GWP\s*(\d+)/i)?.[1])||null),report=text.match(/AR(\d)/)?.[1];
    if(/CO2 only/i.test(text))return {key:"co2",label:"fossil CO2 only, GWP = 1"};
    if(/CO2, CH4, N2O only/i.test(text))return {key:"AR5-three-gas",label:"AR5 for CO₂/CH₄/N₂O only"};
    if(/source HFC\/PFC CO2eq retained/i.test(text))return {key:"AR5-mixed-HFC",label:"AR5 for mass gases; source HFC/PFC basis unverified"};
    if(/other F-gases unverified/i.test(text))return {key:"AR5-core",label:"native CO₂eq; AR5 GWP100 for principal gases"};
    if(report&&horizon)return {key:`AR${report}-${horizon}`,label:`GWP${horizon}, IPCC AR${report}`};
    return {key:"source",label:"source CO2eq; IPCC report and horizon unverified"};
  }
  const api = {HOUSEHOLDS, HOUSEHOLDS_LABEL, unpackBrowserIndex, gwpConvention, needsDetailedReading, isMRIO, countryOptions, metricAvailableForSelection, recipeFacets, focusFacets, isWorld, isGlobal, regionKey, findRegion, regionChoices, metricAvailable, worldValue, isReference, includes, selectedYears, latestVersions, version, seriesKey, key, unique, recentYears, reference, selected, years, sectorIndices, value, basis, unit, observations, automaticView, exportRows, pythonStart};
  if (typeof module !== "undefined") module.exports = api;
  else global.MarioEconomy = api;
})(globalThis);
