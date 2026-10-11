const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../../doc/source/_static'),S=require(path.join(root,'country-model.js')),M=require(path.join(root,'economy-model.js'));
const data=JSON.parse(fs.readFileSync(path.join(root,'data/economy/country-scope.json')));
const profile=(family,release,system)=>data.profiles.find(p=>p.family===family&&p.release===release&&(!system||p.system===system));
test('licensed GTAP scope is available for Italy without exposing numerical readings',()=>{
 const gtap=data.profiles.filter(p=>p.family==='GTAP');assert.equal(gtap.length,2);
 assert.equal(S.visibleProfiles(gtap,{country:'ITA'}).length,2);assert.equal(S.visibleProfiles([...gtap].reverse(),{country:'ITA'}).length,2);
 assert.deepEqual(gtap.map(p=>p.counts.Sector).sort((a,b)=>a-b),[65,76]);
 for(const p of gtap){
  assert.equal(p.numeric_publication,false);assert.equal(p.counts.Region,163);
  assert.equal(p.regions.filter(r=>r.kind==='country').length,145);assert.equal(p.regions.filter(r=>r.kind==='aggregate').length,18);
  assert.equal(S.counts(p,'ITA').Sector,p.counts.Sector);assert.equal(p.reading_ids.length,0);assert.deepEqual(p.availability,{});
  assert.ok(!('Satellite account' in p.counts));assert.match(p.scope_note,/proprietary licence/);
  const rice=S.query(p,'ITA',data.classifications['nace-2.1'],'01.12',data.mappings);assert.equal(rice.status,'mapped');
  assert.equal(rice.matches[0].native_code.toLowerCase(),'pdr');
  assert.equal(S.query(p,'ITA',data.classifications['cpa-2.2'],'01.12.00',data.mappings).status,'unavailable');
 }
 assert.equal(gtap.find(p=>p.release.endsWith('Power')).parser_supported,true);
 assert.equal(gtap.find(p=>p.release.endsWith('Standard')).parser_supported,false);
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'data/economy/manifest.json')));assert.ok(!manifest.datasets.some(d=>d.source==='GTAP'));
});
test('scope uses individual countries only and respects country-specific native membership',()=>{
 const p={regions:[{kind:'country',iso3:'ITA',label:'IT',name:'Italy'},{kind:'aggregate',iso3:null,label:'ROW',name:'Rest of world'}],sets:{Sector:['A','B','C']},memberships:{IT:{Sector:['A','B']}},counts:{Region:2,Sector:3}};
 assert.equal(S.counts(p,'ITA').Sector,2);assert.equal(S.counts(p,'ITA').Region,2);assert.deepEqual(S.nativeSet(p,'FRA','Sector'),[]);
 assert.deepEqual(S.countries([p]),[{id:'ITA',name:'Italy'}]);
});
test('all public parsed set profiles resolve native regional counts, including SUT axes and restricted numerics',()=>{
 for(const p of data.profiles)for(const r of p.regions.filter(r=>r.kind==='country'))for(const set of ['Sector','Activity','Commodity']){
  const entry=p.region_counts.find(c=>c.region===r.label&&c.set===set);
  if(entry)assert.equal(S.nativeSet(p,r.iso3,set).length,entry.count,`${p.id} ${r.label} ${set}`);
 }
 const eora=profile('EORA','Eora26');assert.equal(eora.reading_ids.length,0);assert.equal(S.counts(eora,'ITA').Sector,26);
 assert.equal(S.counts(profile('BEA','Summary'),'USA').Activity,71);
});
test('country and target year constrain scope; coexisting OECD variants and Hybrid stay accessible',()=>{
 const rows=S.visibleProfiles(data.profiles,{country:'ITA',year:2024});assert.ok(rows.every(p=>p.years.includes(2024)&&S.countryRegions(p,'ITA').length));
 assert.ok(!rows.some(p=>p.family==='BEA'||p.family==='EMERGING'));
 const all=S.visibleProfiles(data.profiles,{country:'USA'});
 assert.equal(all.filter(p=>p.family==='OECD').length,2);assert.ok(all.some(p=>p.family==='EXIOBASE'&&p.units==='Hybrid'));
 assert.ok(S.visibleProfiles(data.profiles,{country:'ITA',older:true}).length>S.visibleProfiles(data.profiles,{country:'ITA'}).length);
});
test('CPA fine lookup preserves leading zeros, deduplicates wheat and records broader aggregation',()=>{
 const p=profile('EXIOBASE','3.11.2','pxp'),c=data.classifications['cpa-2002'];
 for(const code of ['01.11.11','01.11.12']){const result=S.query(p,'ITA',c,code,data.mappings);assert.equal(result.status,'mapped');assert.equal(result.matches.length,1);assert.equal(result.matches[0].native_code,'p01.b');assert.equal(result.matches[0].native_label,'Wheat');assert.equal(result.matches[0].relation,'Included in a broader aggregate');assert.equal(result.complete,false);}
 const branch=S.query(p,'ITA',c,'01.11',data.mappings);assert.equal(new Set(branch.matches.map(e=>e.native_code)).size,branch.matches.length);
 assert.ok(S.ancestors(c,'01.11.11').has('A'));
});
test('classification revisions, partial mappings and cross-section aggregates never become exact matches or zero coverage',()=>{
 const p=profile('EXIOBASE','3.11.2','ixi');
 assert.equal(S.query(p,'ITA',data.classifications['cpa-2002'],'01.11.11',data.mappings).status,'unavailable');
 const coarse=S.query(p,'ITA',data.classifications['nace-1.1'],'01.11',data.mappings);assert.equal(coarse.status,'coarse');assert.equal(coarse.ancestor.code,'A');assert.equal(coarse.complete,false);assert.ok(coarse.matches.length>1);assert.ok(coarse.matches.every(e=>e.relation.includes('unverified')));
 const adb=profile('ADB','74 economies'),a=S.query(adb,'ITA',data.classifications['nace-1.1'],'A',data.mappings);
 assert.equal(a.cross,1);assert.equal(a.within,0);assert.equal(a.matches.length,1);
 const tree=data.classifications['cpa-2002'];assert.ok(data.classifications['nace-1.1'].levels.at(-1)===4&&tree.levels.at(-1)===6);
});
test('every detailed link and taxonomy parent resolves, and country-mode indicators exclude other geographies',()=>{
 for(const c of Object.values(data.classifications)){
  const codes=new Set(c.nodes.map(n=>n.code));assert.equal(codes.size,c.nodes.length);
  for(const n of c.nodes)if(n.parent)assert.ok(codes.has(n.parent),`${c.id} ${n.code}`);
 }
 for(const p of data.profiles){const m=data.mappings[p.mapping];if(!m||m.depth===1)continue;const labels=new Set(Object.values(p.sets).flat());for(const e of m.entries)assert.ok(labels.has(e.native_label));}
 const s=(id,iso)=>({recipe:{id,source:'TEST',release:'1',table:'IOT',year:2024},regions:[{kind:'country',iso3:iso,code:iso}]});
 const state={mode:'country',country:'ITA',families:['TEST'],versions:{},year:'all'};assert.equal(M.selected([s('IT','ITA'),s('US','USA')],state).length,1);
});


test('source-only CEDA uses the supplied vintage and native scope, with no fabricated accounts or numerical reading',()=>{
 const ceda=profile('CEDA','2024');assert.equal(ceda.status,'source_verified');assert.equal(ceda.parser_supported,false);
 assert.deepEqual(ceda.years,[2022]);assert.equal(ceda.regions.filter(r=>r.kind==='country').length,148);
 assert.equal(ceda.regions.filter(r=>r.kind==='aggregate').length,1);assert.equal(S.counts(ceda,'ITA').Sector,400);assert.equal(S.counts(ceda,'ITA').Region,149);
 assert.equal(ceda.counts['Satellite account'],undefined);assert.equal(ceda.counts['Factor of production'],undefined);assert.equal(ceda.counts['Consumption category'],undefined);
 assert.equal(ceda.native_codes['Oilseed farming'],'1111A0');assert.equal(ceda.mapping,null);assert.equal(ceda.guide,null);assert.equal(ceda.reading_ids.length,0);
 assert.ok(S.visibleProfiles(data.profiles,{country:'ITA',year:2022}).some(p=>p.family==='CEDA'));
 assert.ok(!S.visibleProfiles(data.profiles,{country:'ITA',year:2024}).some(p=>p.family==='CEDA'));
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'data/economy/manifest.json')));assert.ok(!manifest.datasets.some(d=>d.source==='CEDA'));
});

test('a finer NACE code reports broader verified scope without claiming a detailed allocation',()=>{
 const c=data.classifications['nace-1.1'];
 const adb=S.query(profile('ADB','74 economies'),'ITA',c,'01.11',data.mappings);
 assert.equal(adb.status,'coarse');assert.equal(adb.ancestor.code,'A');assert.equal(adb.matches.length,1);
 assert.equal(adb.matches[0].official_code,'A+B');assert.equal(adb.complete,false);
 const ceda=S.query(profile('CEDA','2024'),'ITA',c,'01.11',data.mappings);
 assert.equal(ceda.status,'unavailable');assert.deepEqual(ceda.matches,[]);
});


test('SUT activity and commodity classifications are selected independently',()=>{
 const p={regions:[{kind:'country',iso3:'ITA',label:'IT'}],sets:{Activity:['Agriculture'],Commodity:['Crops']},memberships:{},mapping:'activities',mapping_ids:['activities','products']};
 const cls=id=>({id,nodes:[{code:'A',level:1,parent:null}]});
 const mappings={activities:{classification:'nace',dimension:'Activity',depth:1,entries:[{native_code:'A01',native_label:'Agriculture',official_code:'A'}]},products:{classification:'cpa',dimension:'Commodity',depth:1,entries:[{native_code:'CPA_A01',native_label:'Crops',official_code:'A'}]}};
 assert.deepEqual(S.query(p,'ITA',cls('nace'),'A',mappings).matches.map(m=>m.native_code),['A01']);
 assert.deepEqual(S.query(p,'ITA',cls('cpa'),'A',mappings).matches.map(m=>m.native_code),['CPA_A01']);
 assert.equal(S.query(p,'ITA',cls('other'),'A',mappings).status,'unavailable');
 const figaro=data.profiles.find(p=>p.family==='FIGARO'&&p.format==='SUT');
 assert.equal(data.classifications['nace-2'].label,'NACE Rev. 2');
 for(const id of ['nace-2','cpa-2.1']){
  const result=S.query(figaro,'ITA',data.classifications[id],'A',data.mappings);
  assert.equal(result.matches.length,3);assert.equal(result.cross,0);
  assert.ok(result.matches.every(m=>m.native_code.startsWith(id==='cpa-2.1'?'CPA_A':'A')));
 }
});

test('current NACE country lookup shares activity footprints with the heatmap, excluding commodities',()=>{
 const c=data.classifications['nace-2.1'];assert.equal(c.nodes.filter(n=>n.level===4).length,651);
 const g=S.query(profile('GLORIA','060'),'ITA',c,'01.11',data.mappings);
 assert.deepEqual(g.matches.map(m=>m.native_code),['1','2','3','4']);
 assert.ok(g.matches.every(m=>m.mapping_origin==='reviewed_editorial'&&data.mapping_routes[m.route_id].nodes.some(n=>n[0]==='NXB')));
 for(const version of ['Extended','Regular']){
  const r=S.query(profile('OECD',version),'ITA',c,'24.51',data.mappings);
  assert.deepEqual(r.matches.map(m=>m.native_code),['C24A']);
  assert.ok(data.mapping_routes[r.matches[0].route_id].steps.some(id=>data.mapping_route_steps[id].source==='S21'));
 }
 const sx=S.query(profile('EXIOBASE','3.11.2','ixi'),'ITA',c,'35.11',data.mappings);
 assert.ok(sx.matches.length>0);assert.ok(!sx.matches.some(m=>m.native_code.startsWith('p')));
});

test('FIGARO and WIOD country lookup preserves native IOT and SUT activity identities',()=>{
 const c=data.classifications['nace-2.1'];
 for(const family of ['FIGARO','WIOD']){
  const profiles=data.profiles.filter(p=>p.family===family&&(p.format==='SUT'||p.system==='ixi'||family==='WIOD'));
  assert.ok(profiles.some(p=>p.format==='SUT'));assert.ok(profiles.some(p=>p.format==='IOT'));
  for(const p of profiles){
   const result=S.query(p,'ITA',c,'01.11',data.mappings);
   assert.equal(result.status,'mapped');assert.equal(result.matches.length,1);
   const e=result.matches[0];assert.equal(e.native_code,'A01');assert.equal(e.mapping_origin,'published');
   const route=data.mapping_routes[e.route_id];assert.equal(route.nodes.at(-1)[0],'NACE2.1');
   assert.ok(route.steps.some(id=>data.mapping_route_steps[id].source==='S29'));
   assert.equal(S.query(p,'ITA',c,'46.89',data.mappings).status,'unverified');
   if(family==='WIOD'&&p.format==='SUT'){
    assert.equal(e.native_label,'A01');assert.match(e.native_description,/Crop and animal production/);
    assert.equal(route.nodes[0][0],'WIOD2016A');
   }else{
    assert.match(e.native_label,/Crop and animal production/);
    assert.equal(route.nodes[0][0],family==='WIOD'?'WIOD2016':'FIGARO64');
   }
  }
 }
 const product=data.profiles.find(p=>p.family==='FIGARO'&&p.system==='pxp');
 assert.equal(S.query(product,'ITA',c,'01.11',data.mappings).status,'unavailable');
});


test('country query preserves a qualified child route without labelling other classes partial',()=>{
 const c={id:'test',nodes:[{code:'D',parent:null,level:1},{code:'35',parent:'D',level:2},{code:'35.1',parent:'35',level:3},{code:'35.11',parent:'35.1',level:4},{code:'35.12',parent:'35.1',level:4}]};
 const p={mapping:'m',sets:{Activity:['Generation']},memberships:{},regions:[{kind:'country',iso3:'ITA',label:'IT'}]};
 const m={m:{classification:'test',depth:4,dimensions:['Activity'],complete:false,entries:[{native_code:'G',native_label:'Generation',official_code:'35.11',precision:'reviewed'},{native_code:'G',native_label:'Generation',official_code:'35.12',precision:'partial'}]}};
 assert.equal(S.query(p,'ITA',c,'35.11',m).matches[0].precision,'reviewed');
 assert.equal(S.query(p,'ITA',c,'35.1',m).matches[0].precision,'partial');
 assert.equal(S.query(p,'ITA',c,'35.12',m).matches[0].precision,'partial');
});


test('Hybrid country lookup exposes shared activity footprints and its separate electricity paths',()=>{
 const h=data.profiles.find(p=>p.family==='EXIOBASE'&&p.units==='Hybrid'&&p.format==='SUT'),c=data.classifications['nace-2.1'];
 const power=S.query(h,'ITA',c,'35.11',data.mappings);assert.equal(power.matches.length,4);
 assert.ok(power.matches.every(e=>data.mapping_routes[e.route_id].nodes[0][0]==='EXIO3H'));
 assert.ok(power.matches.every(e=>!data.mapping_routes[e.route_id].nodes.some(n=>n[0]==='EXIO3P')));
 const beverage=S.query(h,'ITA',c,'11.01',data.mappings);assert.equal(beverage.status,'mapped');assert.ok(beverage.matches.some(e=>e.native_label==='Manufacture of beverages'));assert.ok(beverage.matches.every(e=>e.precision==='partial'&&e.mapping_origin==='shared_exiobase_activity'));
 assert.ok(data.mapping_routes[beverage.matches[0].route_id].nodes.some(n=>n[0]==='EXIO3I'&&n[1]==='i15.j'));
 assert.deepEqual(beverage.coarse_matches,[]);
 assert.equal(S.query(h,'USA',c,'11.01',data.mappings).status,'mapped');
 assert.equal(S.query(h,'FRA',c,'35.11',data.mappings).matches.length,4);
});
