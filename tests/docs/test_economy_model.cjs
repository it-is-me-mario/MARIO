const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname,'../..');
const M = require(path.join(root,'doc/source/_static/economy-model.js'));
const folder = path.join(root,'doc/source/_static/data/economy');
const json = name => JSON.parse(fs.readFileSync(path.join(folder,name+'.json'),'utf8'));
const snapshots = json('manifest').datasets.map(d=>json(d.id));
const wb=json('world-bank'), mappings=json('sector-sections').mappings;
const state = () => ({mode:'focus',families:['EXIOBASE'],versions:{EXIOBASE:'3.11.2 · ixi'},year:2024,metric:'value_added',section:'all',perCapita:false,country:'ITA',reference:true});
test('MRIO browser excludes national BEA and USEEIO but retains international SUTs',()=>{
 const eligible=snapshots.filter(M.isMRIO);
 assert.ok(!eligible.some(s=>['BEA','USEEIO'].includes(s.recipe.source)));
 assert.deepEqual(M.unique(eligible.map(s=>s.recipe.source)).sort(),['ADB','EMERGING','EXIOBASE','FIGARO','GLORIA','OECD','WIOD']);
 assert.ok(eligible.some(s=>s.recipe.source==='WIOD'&&s.recipe.table==='SUT'&&s.recipe.world_total_available===false));
 assert.ok(M.isMRIO({regions:[{kind:'country',iso3:'ITA'},{kind:'country',iso3:'FRA'}]}));
});
test('environmental selection keeps only readings with GHG, including ADB year gaps',()=>{
 const pool=snapshots.filter(M.isMRIO),config={...state(),mode:'compare',families:M.unique(pool.map(s=>s.recipe.source)),versions:{},year:'all',environmentallyExtended:true};
 const selected=M.selected(pool,config);
 assert.deepEqual(M.unique(selected.map(s=>s.recipe.source)).sort(),['ADB','EMERGING','EXIOBASE','GLORIA']);
 assert.ok(selected.length);assert.ok(selected.every(s=>M.metricAvailable([s],'ghg')));
 assert.ok(M.metricAvailableForSelection(pool,config,'ghg'));
 assert.ok(!selected.some(s=>s.recipe.source==='ADB'&&[2000,2016,2024].includes(s.recipe.year)));
 assert.ok(selected.some(s=>s.recipe.source==='EMERGING'&&s.recipe.release==='E'));
 assert.ok(!selected.some(s=>s.recipe.source==='ADB'&&['71 economies','74 economies'].includes(s.recipe.release)));
 assert.ok(M.metricAvailableForSelection(pool,{...config,year:2024},'ghg'));
 assert.ok(!M.metricAvailableForSelection(pool,{...config,environmentallyExtended:false},'ghg'));
});
test('environmental eligibility is consistent before and after lazy snapshot loading',()=>{
 const manifest=json('manifest'),metadata=manifest.datasets.map(d=>({metadata_only:true,recipe:{...manifest.templates[d.template].recipe,...d},regions:manifest.templates[d.template].regions,availability:d.availability})).filter(M.isMRIO);
 const config={...state(),mode:'compare',families:M.unique(metadata.map(s=>s.recipe.source)),versions:{},year:'all',environmentallyExtended:true};
 assert.deepEqual(M.selected(metadata,config).map(s=>s.recipe.id),M.selected(snapshots.filter(M.isMRIO),config).map(s=>s.recipe.id));
 assert.ok(M.metricAvailableForSelection(metadata,config,'ghg'));
});
test('GLORIA keeps native GHG characterisation, observed EY and global aggregates with the verified signed GDP bridge',()=>{
 const s=snapshots.find(s=>s.recipe.source==='GLORIA'),r=s.regions.find(r=>r.iso3==='ITA'),mapping=mappings[s.recipe.id];
 assert.equal(s.regions.length,164);assert.equal(s.recipe.sectors.length,120);
 assert.equal(s.regions.filter(r=>r.kind==='aggregate').length,4);
 assert.equal(s.regions.find(r=>r.code==='SDS').iso3,'SSD');
 assert.equal(s.recipe.ghg_factors["Emissions (EDGAR) | 'GHG_total_EDGAR_consistent'"],1000);
 assert.match(s.recipe.gwp_basis,/AR5 GWP100 verified/);assert.ok(M.isGlobal(s));
 assert.equal(M.value(s,r,{...state(),metric:'gdp'},wb,mapping),r.gdp);
 assert.equal(r.gdp,r.value_added.reduce((a,b)=>a+b,0)+r.net_product_taxes);
 assert.equal(s.recipe.tax_bridge,'gloria_valuations');
 assert.ok(Math.abs(s.provenance.gdp_bridge.validation.relative_residual)<1e-5);
 assert.equal(M.metricAvailable([s],'gdp'),true);assert.equal(M.metricAvailable([s],'ghg'),true);
 const cfg={...state(),metric:'ghg'},native=r.ghg.reduce((a,b)=>a+b,0);
 assert.equal(M.value(s,r,cfg,wb,mapping),(native+r.household_ghg)/1000);
 const expected=s.regions.reduce((sum,r)=>sum+r.ghg.reduce((a,b)=>a+b,0)+r.household_ghg,0)/1e6;
 assert.ok(Math.abs(M.worldValue(s,{...cfg,country:'world'},wb,mapping)-expected)<=expected*1e-12);
 assert.equal(mapping.entries.find(e=>e.native_label==='Other services').section,'S+T');
 assert.equal(new Set(mapping.entries.map(e=>e.index)).size,120);
 assert.equal(s.recipe.license_url,'https://creativecommons.org/licenses/by-nc/3.0/au/');
 assert.match(s.recipe.attribution,/CC BY-NC 3.0/);
});
test('GLORIA annual readings expose all metrics and subsets with one shared native-set profile',()=>{
 const series=snapshots.filter(s=>s.recipe.source==='GLORIA').sort((a,b)=>a.recipe.year-b.recipe.year);
 assert.deepEqual(series.map(s=>s.recipe.year),Array.from({length:36},(_,i)=>1990+i));
 const catalogue=JSON.parse(fs.readFileSync(path.join(root,'doc/source/_static/data/database_profiles.json')));
 const profiles=catalogue.profiles.filter(p=>p.source==='GLORIA');assert.equal(profiles.length,1);assert.deepEqual(profiles[0].years,Array.from({length:36},(_,i)=>1990+i));
 const scope=json('country-scope').profiles.filter(p=>p.family==='GLORIA');assert.equal(scope.length,1);assert.deepEqual(scope[0].years,Array.from({length:36},(_,i)=>1990+i));
 for(const s of series){
  assert.deepEqual(s.recipe.sectors,series[0].recipe.sectors);assert.ok(s.recipe.gdp_bridge_verified);
  const cfg={...state(),families:['GLORIA'],versions:{GLORIA:'all'},year:s.recipe.year,country:'ITA',metric:'gdp'};
  const italy=s.regions.find(r=>r.iso3==='ITA');assert.equal(M.value(s,italy,cfg,wb,mappings[s.recipe.id]),italy.gdp);
  const population=wb.countries.ITA.years[String(s.recipe.year)]?.population;
  assert.equal(M.value(s,italy,{...cfg,perCapita:true},wb,mappings[s.recipe.id]),population>0?italy.gdp/population:null);
  const total=M.worldValue(s,{...cfg,country:'world'},wb,mappings[s.recipe.id]);assert.ok(Number.isFinite(total)&&total>0);assert.ok(Math.abs(total-s.provenance.gdp_bridge.validation.world_gdp_income)<=total*1e-12);
  for(const metric of ['gdp','value_added','ghg'])assert.ok(M.metricAvailable([s],metric));
  assert.equal(mappings[s.recipe.id].entries.length,120);
 }
 const observed=M.observations(series,{...state(),families:['GLORIA'],versions:{GLORIA:'all'},year:[2022,2024],country:'world',metric:'gdp'},wb,mappings).filter(r=>r.database==='GLORIA');
 assert.deepEqual(observed.map(r=>r.year).sort(),[2022,2024]);
 const audited=series.find(s=>s.recipe.year===2023);assert.equal(audited.recipe.gdp_identity_status,'independently_reproduced_source_residual');
 assert.match(audited.recipe.gdp_note,/0\.186% source residual/);assert.ok(audited.provenance.gdp_bridge.source_accounting_audit.V1);
});
test('native sections partition every industry and conserve value added and GHG',()=>{
  for(const s of snapshots){
    const m=mappings[s.recipe.id];
    if(!m) continue; // Unverified concordances expose only whole-economy totals.
    assert.deepEqual(m.entries.map(e=>e.native_label),s.recipe.sectors);
    assert.equal(new Set(m.entries.map(e=>e.index)).size,s.recipe.sectors.length);
    for(const r of s.regions) for(const metric of ['value_added','ghg']) {
      if(!r[metric]||metric==="ghg"&&s.recipe.ghg_usable===false)continue;
      const config={...state(),metric};
      const total=M.value(s,r,config,wb,m);
      const sum=Object.keys(m.sections).reduce((sum,section)=>sum+M.value(s,r,{...config,section},wb,m),0);
      const direct=metric==='ghg'&&s.recipe.final_demand_emissions_loaded!==false?(r.household_ghg||0)/1000:0;
      assert.ok(Math.abs(total-sum-direct)<=Math.max(1,Math.abs(total))*1e-12);
    }
  }
});
test('per capita is not calculated for one sector or a regional aggregate',()=>{
  const s=snapshots[0], m=mappings[s.recipe.id];
  assert.equal(M.value(s,s.regions[0],{...state(),section:'A',perCapita:true},wb,m),null);
  assert.equal(M.value(s,s.regions.find(r=>r.kind!=='country'),{...state(),perCapita:true},wb,m),null);
});
test('comparison never substitutes a different year or treats absent emissions as zero',()=>{
  const config={...state(),mode:'compare',families:['EXIOBASE','OECD'],metric:'gdp'};
  const rows=M.observations(snapshots,config,wb,mappings);
  assert.equal(rows.find(r=>r.database==='OECD').value,null);
  assert.match(rows.find(r=>r.database==='OECD').note,/2022/);
  assert.equal(rows.find(r=>r.database==='World Bank').value,wb.countries.ITA.years['2024'].gdp);
  config.year=2022;config.metric='ghg';
  assert.equal(M.observations(snapshots,config,wb,mappings).find(r=>r.database==='OECD').note,'No verified GHG aggregate');
});
test('automatic views follow the actual number of years and versions',()=>{
  const config=state();
  assert.equal(M.automaticView(snapshots,config),'comparison');
  config.metric='gdp';assert.equal(M.automaticView(snapshots,config),'comparison');
  config.year='all';assert.equal(M.automaticView(snapshots.filter(s=>s.recipe.year===2024),config),'comparison');
  const earlier=structuredClone(snapshots.find(s=>s.recipe.id==='exiobase-3112-2024-ixi'));earlier.recipe.year=2023;
  assert.equal(M.automaticView([...snapshots,earlier],config),'series');
  config.year=2024;config.versions.EXIOBASE='all';
  const edition=structuredClone(earlier);edition.recipe.year=2024;edition.recipe.release='test edition';
  assert.equal(M.automaticView([...snapshots,edition],config),'comparison');
});
test('short examples use only MARIO and retain explicit full GHG characterisation',()=>{
  for(const s of snapshots) for(const metric of ['gdp','value_added',...(Object.keys(s.recipe.ghg_factors).length?['ghg']:[])]) {
    const script=M.pythonStart(s,{...state(),metric},mappings[s.recipe.id]);
    assert.deepEqual(script.split('\n').filter(l=>/^(import |from )/.test(l)),['import mario']);
    assert.ok(script.split('\n').length<55);
    assert.match(script,/calc_all=False/);
    if(metric==='ghg') assert.ok(Object.keys(s.recipe.ghg_factors).every(k=>script.includes(JSON.stringify(k))));
    if(metric==='gdp') assert.match(script,s.recipe.tax_bridge==='sut_supply_product_taxes'?/Supply table/:s.recipe.tax_bridge==='source_activity_taxes'?/no final-use tax row/:s.recipe.tax_bridge==='gloria_valuations'?/valuation="taxes"/:/final-demand tax bridge/);
  }
});

test('World sums all native regions once, including aggregates, and never substitutes a national total',()=>{
 const snapshot=snapshots.find(s=>s.recipe.id==='exiobase-3112-2024-ixi');
 for(const metric of ['gdp','value_added','ghg']){
  const config={...state(),metric,country:'world'};
  const rows=M.observations(snapshots,config,wb,mappings,json('edgar'));
  const model=rows.filter(r=>!M.isReference(r));assert.equal(model.length,1);assert.equal(model[0].country,'world');
  const expected=snapshot.regions.reduce((sum,r)=>sum+M.value(snapshot,r,{...config,perCapita:false},wb,mappings[snapshot.recipe.id]),0);
  assert.equal(model[0].value,expected);
  const onlyCountries=snapshot.regions.filter(r=>r.kind==='country').reduce((sum,r)=>sum+M.value(snapshot,r,config,wb,mappings[snapshot.recipe.id]),0);
  assert.ok(expected>onlyCountries);
  const pc=M.worldValue(snapshot,{...config,perCapita:true},wb,mappings[snapshot.recipe.id]);
  assert.equal(pc,expected*(metric==='ghg'?1e6:1)/wb.aggregates.WLD.years['2024'].population);
 }
 const bea=snapshots.find(s=>s.recipe.source==='BEA');
 assert.equal(M.worldValue(bea,{...state(),country:'world'},wb,null),null);
 const incomplete=structuredClone(snapshot);incomplete.regions[0].ghg=null;
 assert.equal(M.worldValue(incomplete,{...state(),metric:'ghg',country:'world'},wb,mappings[snapshot.recipe.id]),null);
});
test('EDGAR references use unchanged published totals and per-capita cells automatically',()=>{
 const edgar=json('edgar');
 for(const country of ['ITA','world'])for(const perCapita of [false,true]){
  const config={...state(),metric:'ghg',country,perCapita,edgar:false};
  const row=M.observations(snapshots,config,wb,mappings,edgar).find(r=>r.database==='EDGAR');
  const entry=perCapita?edgar.per_capita[country==='world'?'WLD':country]:country==='world'?edgar.world:edgar.countries[country];
  assert.equal(row.value,entry.years['2024']);assert.equal(row.difference_percent,null);
  assert.equal(row.unit,M.unit(config));assert.match(row.basis,/AR5/);assert.match(row.note,/Different boundary/);
 }
 assert.ok(!M.observations(snapshots,{...state(),metric:'ghg',section:'A'},wb,mappings,edgar).some(r=>r.database==='EDGAR'));
});
test('World Bank uses the official WLD aggregate instead of summing country rates',()=>{
 for(const perCapita of [false,true]){
  const rows=M.observations(snapshots,{...state(),metric:'gdp',country:'world',perCapita,reference:false},wb,mappings);
  assert.equal(rows.find(r=>r.database==='World Bank').value,wb.aggregates.WLD.years['2024'][perCapita?'gdp_per_capita':'gdp']);
 }
});
test('aggregate identities distinguish database boundaries while sharing identical monetary EXIOBASE geographies',()=>{
 const exio=snapshots.find(s=>s.recipe.id==='exiobase-3112-2024-ixi'),pxp=snapshots.find(s=>s.recipe.id==='exiobase-3112-2024-pxp'),hybrid=snapshots.find(s=>s.recipe.parser_options.unit==='Hybrid');
 const wa=s=>s.regions.find(r=>r.code==='WA');
 assert.equal(M.regionKey(exio,wa(exio)),M.regionKey(pxp,wa(pxp)));
 assert.notEqual(M.regionKey(exio,wa(exio)),M.regionKey(hybrid,wa(hybrid)));
 const choice=M.regionKey(exio,wa(exio));
 const rows=M.observations(snapshots,{...state(),mode:'compare',families:['EXIOBASE','OECD'],country:choice},wb,mappings,json('edgar'));
 assert.ok(rows.find(r=>r.database==='EXIOBASE').value>0);
 assert.equal(rows.find(r=>r.database==='OECD').value,null);
 assert.ok(!rows.some(M.isReference));
 assert.ok(M.regionChoices(snapshots).some(r=>r.kind==='aggregate'));
});
test('GHG selection requires verified emissions in every selected reading',()=>{
 const exio=snapshots.find(s=>s.recipe.id==='exiobase-3112-2024-ixi'),oecd=snapshots.find(s=>s.recipe.source==='OECD');
 assert.ok(M.metricAvailable([exio],'ghg'));
 assert.equal(M.metricAvailable([exio,oecd],'ghg'),false);
 assert.equal(M.metricAvailable([],'ghg'),false);
});
test('MRIO GHG units match EDGAR Gg totals while per capita uses tonnes',()=>{
  const s=snapshots.find(s=>s.recipe.id==='exiobase-3112-2024-ixi'),r=s.regions.find(r=>r.iso3==='ITA');
  const native=r.ghg.reduce((a,b)=>a+b,0)+(r.household_ghg||0);
  assert.equal(M.value(s,r,{...state(),metric:'ghg'},wb,mappings[s.recipe.id]),native/1000);
  assert.equal(M.value(s,r,{...state(),metric:'ghg',perCapita:true},wb,mappings[s.recipe.id]),native/wb.countries.ITA.years['2024'].population);
});

test('USEEIO sums all commodity emissions independently of its activity value-added axis',()=>{
 const s=snapshots.find(s=>s.recipe.source==='USEEIO'),r=s.regions[0];
 assert.equal(s.recipe.sectors.length,71);assert.equal(s.recipe.ghg_sectors.length,73);
 assert.equal(M.value(s,r,{...state(),metric:'ghg'},wb,null),r.ghg.reduce((a,b)=>a+b,0)/1000);
 assert.match(M.basis(s.recipe,'ghg'),/import-related/);
 assert.match(M.pythonStart(s,{...state(),metric:'ghg'},null),/get_block\("Ec"\)/);
});

test('GDP estimates remain labelled in comparisons',()=>{
 const rows=M.observations(snapshots,{...state(),metric:'gdp'},wb,mappings);
 assert.match(rows.find(r=>r.database==='EXIOBASE').note,/GDP estimate/);
 const reconstructed=M.observations(snapshots,{...state(),year:2022,metric:'gdp'},wb,mappings);
 assert.doesNotMatch(reconstructed.find(r=>r.database==='EXIOBASE').note,/GDP estimate/);
});

test('year and country subsets survive calculation and references without filling skipped years',()=>{
 const config={...state(),country:['ITA','FRA'],year:[2022,2024],metric:'gdp'};
 const rows=M.observations(snapshots,config,wb,mappings);
 assert.deepEqual([...new Set(rows.map(r=>r.country))].sort(),['FRA','ITA']);
 assert.deepEqual([...new Set(rows.map(r=>r.year))].sort(),[2022,2024]);
 assert.equal(rows.filter(r=>r.database==='World Bank').length,4);
 assert.equal(M.automaticView(snapshots,config),'series');
 assert.ok(rows.filter(r=>r.database==='World Bank').every(r=>r.value===wb.countries[r.country].years[r.year].gdp));
});
test('version subsets retain both systems of the latest release and exclude older releases by default',()=>{
 assert.ok(M.latestVersions(snapshots,'EMERGING').every(v=>v.startsWith('2.2')));
 const latest=M.latestVersions(snapshots,'EXIOBASE');
 assert.deepEqual(latest.sort(),['3.11.2 · ixi','3.11.2 · pxp']);
 const config={...state(),versions:{EXIOBASE:latest},year:'all',country:'all'};
 assert.ok(M.selected(snapshots,config).every(s=>s.recipe.release==='3.11.2'));
 assert.equal(M.automaticView(snapshots,config),'series');
 config.versions.EXIOBASE=['3.11.2 · pxp'];
 assert.ok(M.selected(snapshots,config).every(s=>s.recipe.parser_options.system==='pxp'));
 assert.equal(M.selected(snapshots,{...config,families:[]}).length,0);
});


test('pre-1999 euro values require an explicit historical EUR/ECU rate',()=>{
 const snapshot=structuredClone(snapshots.find(s=>s.recipe.id==='exiobase-3112-2024-ixi'));snapshot.recipe.year=1995;
 const data={countries:{DEU:{years:{1995:{local_currency_per_usd:1.4331325}}}}};
 const config={...state(),metric:'value_added'};
 assert.equal(M.value(snapshot,snapshot.regions[0],config,data,null),null);
 data.currency_rates={EUR:{years:{1995:1.308}}};
 assert.equal(M.value(snapshot,snapshot.regions[0],config,data,null),snapshot.regions[0].value_added.reduce((a,b)=>a+b,0)*1.308);
 assert.equal(M.metricAvailable([{metadata_only:true,availability:{ghg:false}}],'ghg'),false);
});


test('Hybrid HIOT and HSUT remain separate versions with independent native axes',()=>{
 const hiot=snapshots.find(s=>s.recipe.id==='exiobase-hybrid-3318-2011-iot');
 const hsut=snapshots.find(s=>s.recipe.id==='exiobase-hybrid-3318-2011-sut');
 assert.equal(M.version(hiot.recipe),'3.3.18 · hybrid IOT');
 assert.equal(M.version(hsut.recipe),'3.3.18 · hybrid SUT');
 const config={...state(),versions:{EXIOBASE:M.version(hiot.recipe)},year:2011};
 assert.deepEqual(M.selected(snapshots,config).map(s=>s.recipe.id),[hiot.recipe.id]);
 assert.equal(M.version(snapshots.find(s=>s.recipe.id==='exiobase-382-1995-sut').recipe),'3.8.2 · SUT');
});


test('EXIOBASE focus separates units, release, table format and system without duplicating releases',()=>{
 const initial=M.focusFacets(snapshots,'EXIOBASE');
 assert.deepEqual(initial.selection,{units:['Monetary'],version:['3.11.2'],format:['IOT'],system:['ixi']});
 assert.deepEqual(initial.fields.map(f=>f.key),['units','version','format','system']);
 assert.equal(initial.fields.find(f=>f.key==='version').options.filter(v=>v==='3.11.2').length,1);
 const two=M.focusFacets(snapshots,'EXIOBASE',{units:['Monetary'],version:['3.11.2','3.10.2'],system:['ixi','pxp']});
 assert.deepEqual(new Set(two.versions),new Set(['3.11.2 · ixi','3.11.2 · pxp','3.10.2 · ixi','3.10.2 · pxp']));
 const hybrid=M.focusFacets(snapshots,'EXIOBASE',{...initial.selection,units:['Hybrid']});
 assert.deepEqual(hybrid.selection.version,['3.3.18']);assert.deepEqual(hybrid.selection.format,['IOT']);assert.deepEqual(hybrid.selection.system,['pxp']);
 assert.deepEqual(hybrid.versions,['3.3.18 · hybrid IOT']);
 const empty=M.focusFacets(snapshots,'EXIOBASE',{...initial.selection,version:[]});
 assert.deepEqual(empty.versions,[]);
 const other=M.focusFacets(snapshots,'OECD');assert.deepEqual(other.fields.map(f=>f.key),['version']);
});


test('temporarily clearing an upstream focus facet preserves downstream choices on recovery',()=>{
 const initial=M.focusFacets(snapshots,'EXIOBASE',{version:['3.11.2'],system:['ixi','pxp']});
 const cleared=M.focusFacets(snapshots,'EXIOBASE',{...initial.selection,version:[]});
 assert.deepEqual(cleared.versions,[]);assert.deepEqual(cleared.selection.system,['ixi','pxp']);
 const restored=M.focusFacets(snapshots,'EXIOBASE',{...cleared.selection,version:['3.11.2']});
 assert.deepEqual(new Set(restored.versions),new Set(initial.versions));
 const noUnits=M.focusFacets(snapshots,'EXIOBASE',{...initial.selection,units:[]});
 assert.deepEqual(noUnits.versions,[]);
 const unitsRestored=M.focusFacets(snapshots,'EXIOBASE',{...noUnits.selection,units:['Monetary']});
 assert.deepEqual(new Set(unitsRestored.versions),new Set(initial.versions));
});


test('focus source facets only offer combinations covering every selected year',()=>{
 const current=M.focusFacets(snapshots,'EXIOBASE',{},2024);
 assert.deepEqual(current.fields.find(f=>f.key==='units').options,['Monetary']);
 assert.deepEqual(M.focusFacets(snapshots,'EXIOBASE',{units:'all'},2024).selection.units,['Monetary']);
 assert.deepEqual(current.fields.find(f=>f.key==='version').options,['3.11.2','3.10.2','3.10.1']);
 assert.deepEqual(current.fields.find(f=>f.key==='system').options,['ixi','pxp']);
 const historical=M.focusFacets(snapshots,'EXIOBASE',{},2011);
 assert.ok(historical.fields.find(f=>f.key==='units').options.includes('Hybrid'));
 const subset=M.focusFacets(snapshots,'EXIOBASE',{},[2011,2024]);
 assert.deepEqual(subset.fields.find(f=>f.key==='units').options,['Monetary']);
 assert.ok(!subset.fields.find(f=>f.key==='version').options.includes('3.8.2'));
 const hybrid=M.focusFacets(snapshots,'EXIOBASE',{units:['Hybrid'],version:['3.3.18'],format:'all',system:'all'},2011);
 assert.deepEqual(hybrid.fields.find(f=>f.key==='version').options,['3.3.18']);
 assert.deepEqual(hybrid.fields.find(f=>f.key==='format').options,['IOT','SUT']);
 assert.deepEqual(hybrid.fields.find(f=>f.key==='system').options,['pxp']);
 const restored=M.focusFacets(snapshots,'EXIOBASE',hybrid.selection,2024);
 assert.deepEqual(restored.selection,{units:['Monetary'],version:['3.11.2'],format:['IOT'],system:['pxp']});
});


test('All available years keeps units selectable and follows the chosen Hybrid reading',()=>{
 const all=M.focusFacets(snapshots,'EXIOBASE',{units:['Monetary'],version:'all',format:'all',system:'all'},'all');
 assert.deepEqual(new Set(all.fields.find(f=>f.key==='units').options),new Set(['Monetary','Hybrid']));
 const hybrid=M.focusFacets(snapshots,'EXIOBASE',{...all.selection,units:['Hybrid']},'all');
 assert.deepEqual(hybrid.selection.version,['3.3.18']);
 assert.deepEqual(new Set(hybrid.versions),new Set(['3.3.18 · hybrid IOT','3.3.18 · hybrid SUT']));
 const years=M.years(snapshots,{families:['EXIOBASE'],versions:{EXIOBASE:hybrid.versions},year:'all'});
 assert.deepEqual(years,[2011]);
 const explicit=M.focusFacets(snapshots,'EXIOBASE',all.selection,2024);
 assert.deepEqual(explicit.fields.find(f=>f.key==='units').options,['Monetary']);
});


test('OECD variants expose all local years with clean version labels and no GHG',()=>{
 const oecd=snapshots.filter(s=>s.recipe.source==='OECD');
 assert.equal(oecd.length,56);
 assert.deepEqual(M.latestVersions(snapshots,'OECD').sort(),['Extended','Regular']);
 for(const variant of ['Extended','Regular']){
  const readings=oecd.filter(s=>s.recipe.release===variant);
  assert.deepEqual(readings.map(s=>s.recipe.year).sort((a,b)=>a-b),Array.from({length:28},(_,i)=>1995+i));
  assert.ok(readings.every(s=>M.version(s.recipe)===variant));
  assert.ok(M.metricAvailable(readings,'gdp'));assert.ok(M.metricAvailable(readings,'value_added'));
  assert.equal(M.metricAvailable(readings,'ghg'),false);
 }
 const config={...state(),families:['OECD'],versions:{OECD:['Regular']},year:[1995,2000,2022],metric:'gdp'};
 const rows=M.observations(snapshots,config,wb,mappings);
 assert.deepEqual(rows.filter(r=>r.database==='OECD').map(r=>r.year),[1995,2000,2022]);
 assert.ok(rows.filter(r=>r.database==='OECD').every(r=>r.version==='Regular'&&r.value>0));
});


test('table formats restrict IOT systems and SUT leaves System inapplicable',()=>{
 const all=M.focusFacets(snapshots,'EXIOBASE',{units:['Monetary'],version:['3.8.2'],format:'all',system:'all'});
 assert.deepEqual(all.fields.find(f=>f.key==='format').options,['IOT','SUT']);
 assert.deepEqual(all.fields.find(f=>f.key==='system').options,['ixi','pxp']);
 assert.deepEqual(new Set(all.versions),new Set(['3.8.2 · ixi','3.8.2 · pxp','3.8.2 · SUT']));
 const sut=M.focusFacets(snapshots,'EXIOBASE',{...all.selection,format:['SUT']});
 assert.deepEqual(sut.versions,['3.8.2 · SUT']);
 assert.deepEqual(sut.fields.find(f=>f.key==='system').options,[]);
 assert.equal(sut.fields.find(f=>f.key==='system').notApplicable,true);
 const current=M.focusFacets(snapshots,'EXIOBASE',sut.selection,2024);
 assert.deepEqual(current.fields.find(f=>f.key==='format').options,['IOT']);
 assert.ok(current.versions.every(v=>v.includes('ixi')||v.includes('pxp')));
 const empty=M.focusFacets(snapshots,'EXIOBASE',{...all.selection,format:[]});
 assert.deepEqual(empty.versions,[]);
 const restored=M.focusFacets(snapshots,'EXIOBASE',{...empty.selection,format:'all'});
 assert.deepEqual(new Set(restored.versions),new Set(all.versions));
});

test('reading identity distinguishes all four facets and stays identical across years',()=>{
 const base=snapshots.find(s=>s.recipe.id==='exiobase-3112-2024-ixi').recipe;
 const earlier={...base,year:2023};
 assert.equal(M.seriesKey(base),M.seriesKey(earlier));
 const variants=[base,{...base,release:'other release'},
  {...base,parser_options:{...base.parser_options,system:'pxp'}},
  {...base,parser_options:{...base.parser_options,unit:'Hybrid'}},
  {...base,table:'SUT',parser_options:{table:'SUT',unit:'Monetary'}}];
 assert.equal(new Set(variants.map(M.seriesKey)).size,variants.length);
 const rows=M.observations(snapshots,{...state(),versions:{EXIOBASE:['3.8.2 · SUT']},year:2011,metric:'value_added'},wb,mappings);
 const sut=rows.find(r=>r.database==='EXIOBASE');assert.equal(sut.format,'SUT');assert.equal(sut.system,null);
});

test('several sector aggregates give one row each, matching the single-aggregate values',()=>{
  const multi=M.observations(snapshots,{...state(),section:['A','D','G']},wb,mappings);
  assert.deepEqual(multi.map(r=>r.sector),['A','D','G']);
  for(const row of multi){
    const single=M.observations(snapshots,{...state(),section:row.sector},wb,mappings);
    assert.equal(single.length,1);assert.equal(row.value,single[0].value);
    assert.match(row.sector_name,new RegExp('^'+row.sector+' · '));assert.ok(row.label.endsWith(row.sector_name));
  }
  const s=snapshots.find(x=>x.recipe.id==='exiobase-3112-2024-ixi');
  const script=M.pythonStart(s,{...state(),section:['A','D']},mappings[s.recipe.id]);
  assert.match(script,/sections A, D, stacked/);
});


test('ADB versions are economies counts; year subsets control GHG availability',()=>{
 const adb=snapshots.filter(s=>s.recipe.source==='ADB');assert.equal(adb.length,31);
 assert.deepEqual(M.latestVersions(snapshots,'ADB'),['74 economies']);
 assert.deepEqual(new Set(adb.map(s=>M.version(s.recipe))),new Set(['62 economies','71 economies','72 economies','74 economies']));
 const config={...state(),families:['ADB'],versions:{ADB:['72 economies']},year:2023,metric:'ghg'};
 assert.ok(M.metricAvailableForSelection(snapshots,config,'ghg'));
 assert.equal(M.metricAvailableForSelection(snapshots,{...config,year:2024},'ghg'),false);
 assert.equal(M.metricAvailableForSelection(snapshots,{...config,year:'all'},'ghg'),false);
 assert.ok(M.metricAvailableForSelection(snapshots,{...config,year:[2017,2020,2023]},'ghg'));
 assert.equal(M.metricAvailableForSelection(snapshots,{...config,versions:{ADB:['71 economies']},year:2017},'ghg'),false);
 assert.equal(M.metricAvailableForSelection(snapshots,{...state(),families:['EXIOBASE','OECD'],year:2024},'ghg'),false);
});

test('ADB smaller geography conserves global industry and final-demand GHG totals',()=>{
 for(let year=2017;year<=2023;year++){
  const a=json('adb-'+year+'-62-economies'),b=json('adb-'+year+'-72-economies');
  for(const metric of ['ghg','household_ghg']){
   const total=s=>s.regions.reduce((sum,r)=>sum+(Array.isArray(r[metric])?r[metric].reduce((a,b)=>a+b,0):r[metric]),0);
   assert.ok(Math.abs(total(a)-total(b))<Math.abs(total(b))*1e-12);
  }
  const common=a.regions.filter(r=>r.kind==='country');
  for(const country of common){
   const match=b.regions.find(r=>r.iso3===country.iso3);assert.deepEqual(country.ghg,match.ghg);
  }
 }
 const config={...state(),families:['ADB'],versions:{ADB:['72 economies']},year:[2017,2020,2023],country:'world',metric:'ghg'};
 const rows=M.observations(snapshots,config,wb,mappings,json('edgar'));
 assert.equal(rows.filter(r=>r.database==='ADB').length,3);assert.equal(rows.filter(r=>r.database==='EDGAR').length,3);
 assert.ok(rows.filter(r=>r.database==='ADB').every(r=>r.value>0&&r.basis.includes('AR5')));
});


test('EMERGING versions use the release and retain distinct yearly availability',()=>{
 const recipes=[['1.0',2010],['1.0',2015],['2.0',2018],['2.2',2015],['2.2',2018],['2.2',2021],['2.2',2023],['E',2018]]
  .map(([release,year])=>({recipe:{source:'EMERGING',release,year,table:'IOT',dimension:'Product / service',parser_options:{variant:release==='E'?'E':'standard'}},metadata_only:true,availability:{gdp:false,ghg:false,value_added:true},regions:[]}));
 assert.deepEqual(recipes.map(s=>M.version(s.recipe)),['1.0','1.0','2.0','2.2','2.2','2.2','2.2','E']);
 const selected={families:['EMERGING'],versions:{EMERGING:['2.0']},year:'all'};
 assert.deepEqual(M.years(recipes,selected),[2018]);
 assert.deepEqual(M.latestVersions(recipes,'EMERGING'),['2.2']);
 assert.equal(M.metricAvailableForSelection(recipes,selected,'ghg'),false);
 assert.equal(M.metricAvailableForSelection(recipes,selected,'gdp'),false);
 assert.equal(M.metricAvailableForSelection(recipes,selected,'value_added'),true);
});


test('USD-only starting examples do not invent a missing sector correspondence or exchange-rate conversion',()=>{
 const s=snapshots.find(s=>s.recipe.source==='EMERGING');
 const script=M.pythonStart(s,{...state(),metric:'value_added',section:'all'},null);
 assert.match(script,/own verified sector mapping/);
 assert.doesNotMatch(script,/downloadable sector correspondence|same-year exchange rate/);
 assert.match(script,/Multiply native values by 1000000 to obtain current USD/);
});


test('country options follow selected families, versions and years without adding reference geography',()=>{
 const country=iso=>({code:iso,iso3:iso,name:iso,kind:'country'});
 const reading=(source,release,year,codes)=>({recipe:{source,release,year,dimension:'Industry',parser_options:{dataset:'ICIO'}},regions:codes.map(country)});
 const pool=[reading('OECD','Regular',2020,['ITA','CHN']),reading('OECD','Regular',2021,['ITA','JPN']),
             reading('OECD','Extended',2021,['ITA','IND']),reading('EMERGING','2.2',2021,['ITA','NPL'])];
 const config={mode:'compare',families:['OECD'],versions:{OECD:['Regular']},year:2021,country:'JPN'};
 const codes=()=>M.countryOptions(pool,config).regions.map(r=>r.iso3).sort();
 assert.deepEqual(codes(),['ITA','JPN']);
 config.year=2020;assert.deepEqual(codes(),['CHN','ITA']);assert.equal(M.countryOptions(pool,config).selection,'world');
 config.year=[2020,2021];assert.deepEqual(codes(),['CHN','ITA','JPN']);
 config.year='all';config.versions.OECD=['Extended'];assert.deepEqual(codes(),['IND','ITA']);
 config.families.push('EMERGING');assert.deepEqual(codes(),['IND','ITA','NPL']);
 config.families=['EMERGING'];assert.deepEqual(codes(),['ITA','NPL']);
});

test('dynamic countries retain valid subsets and aggregates, fall back to World or a national region, and handle empty selections',()=>{
 const snapshot=(source,release,year,regions)=>({recipe:{source,release,year,dimension:'Industry'},regions});
 const ita={code:'IT',iso3:'ITA',name:'Italy',kind:'country'},chn={code:'CN',iso3:'CHN',name:'China',kind:'country'};
 const row={code:'ROW',name:'Rest of the world',kind:'aggregate'};
 const earlier=snapshot('EXIOBASE','1',2020,[ita,row]),later=snapshot('EXIOBASE','1',2021,[ita,chn,row]);
 const us=snapshot('BEA','2024',2021,[{code:'US',iso3:'USA',name:'United States',kind:'country'}]);
 const config={families:['EXIOBASE'],versions:{EXIOBASE:'all'},year:2021,country:['ITA','CHN']};
 assert.deepEqual(M.countryOptions([earlier,later,us],config).selection,['ITA','CHN']);
 config.year=2020;assert.equal(M.countryOptions([earlier,later,us],config).selection,'ITA');
 config.country=M.regionKey(later,row);assert.equal(M.countryOptions([earlier,later,us],config).selection,'world');
 config.country=M.regionKey(earlier,row);assert.equal(M.countryOptions([earlier,later,us],config).selection,config.country);
 config.families=['BEA'];config.year=2021;config.country='world';
 const national=M.countryOptions([earlier,later,us],config);assert.equal(national.hasWorld,false);assert.equal(national.selection,'USA');
 config.families=[];const empty=M.countryOptions([earlier,later,us],config);
 assert.deepEqual(empty.regions,[]);assert.deepEqual(empty.selection,[]);assert.equal(empty.hasWorld,false);
});


test('whole-economy GHG adds observed EY once while sectors and unavailable EY remain separate',()=>{
 const s=json('exiobase-3112-2023-ixi'),region=s.regions.find(r=>r.iso3==='USA');
 const config={...state(),metric:'ghg',year:2023,country:'USA'};
 const industry=region.ghg.reduce((a,b)=>a+b,0);
 assert.equal(M.value(s,region,config,wb,mappings[s.recipe.id]),(industry+region.household_ghg)/1000);
 assert.equal(M.value(s,region,{...config,perCapita:true},wb,mappings[s.recipe.id]),(industry+region.household_ghg)/wb.countries.USA.years['2023'].population);
 const rows=M.observations([s],config,wb,mappings,json('edgar'));
 assert.ok(rows[0].value/rows[1].value>0.99 && rows[0].value/rows[1].value<1.01);
 assert.match(rows[0].note,/Includes direct final-demand/);
 assert.equal(M.value({...s,recipe:{...s.recipe,final_demand_emissions_loaded:false}},region,config,wb,mappings[s.recipe.id]),industry/1000);
 const script=M.pythonStart(s,config,mappings[s.recipe.id]);
 assert.match(script,/get_block\("EY"\)/);assert.match(script,/ONCE per region/);
});

test('EMERGING proxies equal native VA and fossil CO2 and carry caveats; E uses the projected 2.2 companion',()=>{
 const readings=snapshots.filter(s=>s.recipe.source==='EMERGING');
 assert.equal(readings.length,12);assert.ok(M.metricAvailable(readings,'gdp'));
 const standard=readings.filter(s=>s.recipe.release!=='E');
 assert.equal(standard.length,11);assert.ok(M.metricAvailable(standard,'ghg'));
 assert.ok(M.metricAvailable(readings,'ghg'));
 for(const s of readings){
  assert.equal(s.recipe.gdp_proxy,'native_value_added');
  assert.ok(s.regions.every(r=>Math.abs(r.gdp-r.value_added.reduce((a,b)=>a+b,0))<=Math.max(1,Math.abs(r.gdp))*1e-12));
  const config={...state(),families:['EMERGING'],versions:{EMERGING:[s.recipe.release]},year:s.recipe.year,metric:'gdp'};
  assert.match(M.observations([s],config,wb,mappings)[0].note,/value added|native va/i);
  config.metric='ghg';const row=M.observations([s],config,wb,mappings,json('edgar'))[0];
  assert.match(row.note,/CO2-only proxy/);assert.match(row.gwp_basis,/GWP = 1/);
  assert.match(M.pythonStart(s,config,null),/Direct final-demand emissions are unavailable/);
  if(s.recipe.release==='E')assert.match(s.recipe.ghg_method,/EMERGING 2\.2 companion .* projected onto the 146 EMERGING-E sectors/);
 }
});


test('explicit country and year clearing stays empty while invalid nonempty countries still fall back',()=>{
 const s=json('exiobase-3112-2024-ixi'),config={...state(),country:[]};
 assert.deepEqual(M.countryOptions([s],config).selection,[]);
 assert.deepEqual(M.observations([s],config,wb,mappings,json('edgar')),[]);
 assert.deepEqual(M.selectedYears([s],{...config,year:[]}),[]);
 assert.equal(M.selected([s],{...config,year:[]}).length,0);
 assert.equal(M.countryOptions([s],{...config,country:['NOT_A_NATIVE_REGION']}).selection,'world');
 assert.deepEqual(M.observations([s],{...state(),section:[]},wb,mappings),[]);
});

test('WIOD separates prices from release, excludes nominal references for PYP, and has no SUT World',()=>{
 const readings=snapshots.filter(s=>s.recipe.source==='WIOD');assert.equal(readings.length,44);
 const base={...state(),families:['WIOD'],versions:{WIOD:'all'},year:2000,metric:'gdp'};
 const f=M.focusFacets(readings,'WIOD',{},2000);
 assert.deepEqual(f.fields.find(f=>f.key==='price').options,['Current prices']);
 const pyp=M.focusFacets(readings,'WIOD',{price:['Previous year prices']},[2001,2014]);
 assert.deepEqual(pyp.fields.find(f=>f.key==='format').options,['IOT']);
 assert.equal(pyp.versions.length,1);
 const config={...base,year:2014,versions:{WIOD:pyp.versions},priceBasis:'Previous year prices'};
 const rows=M.observations(readings,config,wb,mappings);
 assert.equal(rows.length,1);assert.ok(rows[0].value>0);assert.equal(rows[0].world_bank,null);assert.equal(rows[0].difference_percent,null);
 assert.match(rows[0].unit,/previous-year/);assert.ok(!rows.some(M.isReference));
 const sut=readings.find(s=>s.recipe.table==='SUT'&&s.recipe.year===2014);
 assert.equal(M.isGlobal(sut),false);assert.equal(M.worldValue(sut,{...base,country:'world'},wb,mappings[sut.recipe.id]),null);
 const countries=M.countryOptions([sut],{...base,year:2014,country:'world'});assert.equal(countries.hasWorld,false);assert.notEqual(countries.selection,'world');
 assert.equal(sut.regions.length,43);assert.ok(!sut.regions.some(r=>r.code==='ROW'));
 assert.equal(M.metricAvailable(readings,'gdp'),true);assert.equal(M.metricAvailable(readings,'ghg'),false);
 assert.ok(M.latestVersions(readings,'WIOD').every(v=>!v.includes('Previous')));
});

test('all current FIGARO IOT and SUT years expose GDP, native classifications and optional release facets',()=>{
 const series=snapshots.filter(s=>s.recipe.source==='FIGARO');assert.equal(series.length,45);
 for(const combination of ['pxp','ixi','SUT'])assert.deepEqual(series.filter(s=>M.version(s.recipe)===combination).map(s=>s.recipe.year).sort((a,b)=>a-b),Array.from({length:15},(_,i)=>2010+i));
 assert.ok(series.every(s=>s.recipe.gdp_bridge_verified&&M.metricAvailable([s],'gdp')&&!M.metricAvailable([s],'ghg')&&!s.recipe.release));
 assert.deepEqual(M.unique(series.map(s=>M.version(s.recipe))).sort(),['SUT','ixi','pxp']);
 const s=series.find(s=>s.recipe.year===2024&&M.version(s.recipe)==='pxp'),italy=s.regions.find(r=>r.iso3==='ITA');
 const cfg={...state(),families:['FIGARO'],versions:{FIGARO:['pxp']},year:[2010,2024],metric:'gdp'};
 const rows=M.observations(series,cfg,wb,mappings).filter(r=>!M.isReference(r));assert.equal(rows.length,2);
 const rate=1/wb.countries.DEU.years['2024'].local_currency_per_usd;
 assert.ok(Math.abs(rows.find(r=>r.year===2024).value-italy.gdp*rate)<.01);
 assert.equal(mappings[s.recipe.id].classification_id,'cpa-2.1');assert.ok(mappings[s.recipe.id].entries.every(e=>e.native_code.startsWith('CPA_')));
 const focus=M.focusFacets(series,'FIGARO',{},[2010,2024]);
 assert.ok(!focus.fields.some(field=>field.key==='version'));assert.deepEqual(focus.versions,['ixi']);
 assert.equal(M.selected(series,{...cfg,versions:{FIGARO:focus.versions}}).length,2);
 const sut=M.focusFacets(series,'FIGARO',{format:['SUT']},[2010,2024]);assert.deepEqual(sut.versions,['SUT']);assert.ok(sut.fields.find(f=>f.key==='system').notApplicable);
 assert.deepEqual(M.latestVersions(series,'FIGARO').sort(),['SUT','ixi','pxp']);
 const activity=series.find(s=>s.recipe.year===2024&&M.version(s.recipe)==='ixi');assert.equal(mappings[activity.recipe.id].classification_id,'nace-2');
 const supply=series.find(s=>s.recipe.year===2024&&s.recipe.table==='SUT');assert.equal(supply.recipe.value_added_block,'Va');assert.equal(mappings[supply.recipe.id].additional_mappings[0].classification_id,'cpa-2.1');
});

test('reviewed EXIOBASE source errors are gaps, never totals or replacement readings',()=>{
 const config={...state(),versions:{EXIOBASE:'3.10.1 · ixi'},year:'all',metric:'ghg',country:'world'};
 const bad=snapshots.filter(s=>s.recipe.ghg_usable===false);
 assert.equal(bad.length,10);
 for(const s of bad){
  assert.equal(M.metricAvailable([s],'ghg'),false);
  assert.equal(M.worldValue(s,config,wb,mappings[s.recipe.id]),null);
  assert.ok(M.metricAvailable([s],'gdp'));
 }
 assert.ok(M.metricAvailableForSelection(snapshots,config,'ghg'));
 assert.equal(M.metricAvailableForSelection(snapshots,{...config,year:2023},'ghg'),false);
 const rows=M.observations(snapshots,config,wb,mappings);
 for(const year of [2022,2023,2024]){
  const row=rows.find(r=>r.database==='EXIOBASE'&&r.year===year);
  assert.equal(row.value,null);assert.match(row.note,/withheld/);
 }
 assert.ok(rows.find(r=>r.database==='EXIOBASE'&&r.year===2021).value>40000);
 const good=snapshots.find(s=>s.recipe.id==='exiobase-3102-2022-ixi');
 assert.ok(M.metricAvailable([good],'ghg'));
 const total=M.worldValue(good,{...config,year:2022},wb,mappings[good.recipe.id]);
 assert.ok(Math.abs(total-47384.56217)<1);
 const manifest=json('manifest');
 for(const s of bad){
  const d=manifest.datasets.find(d=>d.id===s.recipe.id);
  const lazy={metadata_only:true,recipe:{...manifest.templates[d.template].recipe,...d},regions:manifest.templates[d.template].regions,availability:d.availability};
  assert.equal(M.metricAvailable([lazy],'ghg'),false);
 }
});

test('GHG rows are grouped by their declared IPCC report and GWP horizon',()=>{
 assert.deepEqual(M.gwpConvention({gwp_basis:'AR5 (EDGAR CH4=28); source HFC/PFC CO2eq retained',gwp_horizon:100}),{key:'AR5-mixed-HFC',label:'AR5 for mass gases; source HFC/PFC basis unverified'});
 assert.deepEqual(M.gwpConvention({gwp_basis:'AR5 (CO2, CH4, N2O only; mixed CH4 origins)',gwp_horizon:100}),{key:'AR5-three-gas',label:'AR5 for CO₂/CH₄/N₂O only'});
 assert.deepEqual(M.gwpConvention({gwp_basis:'IPCC AR5 (source-characterised)',gwp_horizon:100}),{key:'AR5-100',label:'GWP100, IPCC AR5'});
 assert.equal(M.gwpConvention({gwp_basis:'IPCC AR5 GWP100'}).key,'AR5-100');
 assert.equal(M.gwpConvention({gwp_basis:'CO2 only (GWP = 1 under AR5 and AR6)',gwp_horizon:100}).key,'co2');
 assert.equal(M.gwpConvention({gwp_basis:'Source CO2eq; IPCC report/horizon unverified',gwp_horizon:null}).key,'source');
 assert.deepEqual(M.gwpConvention({gwp_basis:'Native CO2eq; IPCC AR5 GWP100 verified for CH4; other F-gases unverified',gwp_horizon:100}),{key:'AR5-core',label:'native CO₂eq; AR5 GWP100 for principal gases'});
});
