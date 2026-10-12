const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../../doc/source/_static'),M=require(path.join(root,'sectoral-model.js'));
const data=JSON.parse(fs.readFileSync(path.join(root,'data/economy/sectoral-scope.json'))),model=M.index(data);
const col=family=>model.columns.find(c=>c.family===family&&c.status==='documented');
test('Hybrid remains selectable but is omitted from the initial documented selection',()=>{
 const initial=model.columns.filter(c=>c.default_visible!==false&&['documented','section_only'].includes(c.status));
 assert.equal(initial.length,8);assert.ok(initial.some(c=>c.family==='GTAP'));
 assert.ok(!initial.some(c=>c.family==='EXIOBASE'&&c.units==='Hybrid'));
 assert.equal(model.columns.find(c=>c.units==='Hybrid').status,'documented');
});
test('the heatmap compares GTAP Standard only; Power routes stay in the country lookup with qualified heat scope',()=>{
 const standard=model.columns.find(c=>c.namespace==='GTAP12I');
 assert.equal(standard.label,'GTAP');assert.ok(!model.columns.some(c=>c.namespace==='GTAP12POWERI'));
 assert.ok(!data.columns.commodity.some(c=>['GTAP','CEDA'].includes(c.family)));
 assert.match(standard.note,/only as activities.*single Sector set/);
 assert.equal(standard.native_count,65);assert.equal(standard.native.length,65);
 const rice=M.cell(model,standard,'01.12');assert.deepEqual(rice.matches.map(m=>m.native.code),['pdr']);
 assert.ok(rice.matches[0].link.nodes.some(n=>n[0]==='GTAP12P'));
 assert.ok(rice.matches[0].link.nodes.some(n=>n[0]==='CPC2.1'));
 assert.ok(rice.matches[0].link.nodes.some(n=>n[0]==='ISIC4'));
 assert.equal(rice.matches[0].link.status,'partial');
 assert.equal(standard.native.find(n=>n.code==='dwe').classes.length,0);
 const scope=JSON.parse(fs.readFileSync(path.join(root,'data/economy/country-scope.json')));
 const power=scope.profiles.find(p=>p.id==='gtap-12-power-scope'),routes=scope.mappings[power.mapping_ids.find(id=>id.startsWith('sectoral-gtap-'))].entries;
 const at=code=>routes.filter(e=>e.official_code===code);
 assert.ok(at('35.11').some(e=>e.native_code==='CoalBL'));assert.ok(!at('35.11').some(e=>/Solar|Wind|Hydro/.test(e.native_code)));
 assert.ok(at('35.11').every(e=>e.precision==='partial'));
 assert.ok(at('35.12').some(e=>e.native_code==='WindBL'));assert.ok(!at('35.12').some(e=>e.native_code==='CoalBL'));
 assert.ok(at('35.30').some(e=>e.native_code==='CoalBL'));assert.ok(at('35.13').some(e=>e.native_code==='TnD'));
});
test('all 651 NACE leaf classes remain rows, including classes without predecessors',()=>{
 assert.equal(model.leaves.length,651);assert.equal(new Set(model.leaves.map(n=>n.code)).size,651);
 assert.ok(model.leaves.some(n=>n.code==='46.89'));
 assert.ok(model.leaves.every(n=>n.level===4&&model.ref.section_counts[n.section]>0));
 assert.equal(Object.values(model.ref.section_counts).reduce((a,b)=>a+b,0),651);
});
test('hierarchy narrows rows, not section denominators or native extents',()=>{
 const db=col('ADB'),leaf='01.11',section=model.nodes.get(leaf).section;
 const full=M.cell(model,db,leaf),filtered=M.rows(model,leaf);
 assert.equal(filtered.length,1);assert.equal(filtered[0].code,leaf);
 assert.equal(full.denominator,M.rows(model,section).length);assert.ok(full.denominator>1);
 assert.equal(full.matches[0].native.code,'c1');assert.equal(full.maximum,full.denominator);
 assert.ok(M.rows(model,'01').length>filtered.length);
 assert.equal(M.matrix(model,filtered,[db])[0][0],M.scaleValue(full.denominator,model.maximum));
});
test('reviewed rice activity excludes unrelated legacy producers and retains its provenance',()=>{
 const db=col('EXIOBASE'),cell=M.cell(model,db,'01.12');
 assert.equal(cell.matches.length,1);assert.equal(cell.matches[0].native.code,'i01.a');
 assert.equal(cell.minimum,1);assert.equal(cell.maximum,1);assert.equal(cell.matches[0].link.status,'reviewed');assert.equal(cell.matches[0].link.mapping_origin,'reviewed_editorial');
 const route=cell.matches[0].link.nodes;assert.equal(route[0][0],'EXIO3I');assert.equal(route.at(-1)[0],'NACE2.1');
 assert.ok(!route.some(n=>n[0]==='EXIO3P'));assert.ok(cell.matches[0].link.steps.some(id=>data.route_steps[id].source==='S42'));
});
test('overlapping native matches expose every category and a range rather than averaging',()=>{
 const c=M.cell(model,col('CEDA'),'01.11');assert.ok(c.matches.length>1);
 assert.equal(c.minimum,Math.min(...c.matches.map(m=>m.count)));assert.equal(c.maximum,Math.max(...c.matches.map(m=>m.count)));
 assert.ok(c.matches.every(m=>m.link.relation!=='Equivalent'));assert.ok(c.matches.every(m=>m.denominator===c.denominator));
});
test('native cross-section memberships survive area selection and are not truncated',()=>{
 const db=col('ADB');let example;
 for(const row of model.leaves){const c=M.cell(model,db,row.code);const m=c.matches.find(m=>m.outside.length);if(m){example={row,c,m};break;}}
 assert.ok(example);const {row,m}=example;
 assert.ok(m.outside.every(code=>model.nodes.get(code).section!==row.section));
 assert.equal(m.native.classes.length,m.inside.length+m.outside.length);
 assert.equal(M.rows(model,row.code).length,1);
});
test('a reference class without a predecessor remains null in published NACE-based inventories',()=>{
 const db=col('FIGARO'),c=M.cell(model,db,'46.89');
 assert.equal(c.status,'unverified');assert.equal(c.maximum,null);assert.deepEqual(c.matches,[]);
 assert.equal(M.matrix(model,M.rows(model,'46.89'),[db])[0][0],null);
});
test('FIGARO and WIOD use their complete published activity partitions and keep annual systems compact',()=>{
 for(const [family,count,source] of [['FIGARO',64,'S26'],['WIOD',56,'S27']]){
  const db=col(family);assert.equal(db.native.length,count);assert.equal(db.native_count,count);
  assert.equal(model.columns.filter(c=>c.family===family).length,1);assert.ok(db.profile_ids.length>1);
  assert.equal(new Set(db.native.flatMap(n=>n.classes)).size,650);
  assert.deepEqual(M.cell(model,db,'01.11').matches.map(m=>m.native.code),['A01']);
  assert.deepEqual(M.cell(model,db,'28.23').matches.map(m=>m.native.code),['C28']);
  assert.deepEqual(M.cell(model,db,'31.00').matches.map(m=>m.native.code).sort(),['C23',family==='FIGARO'?'C31_32':'C31_C32']);
  assert.ok(db.native.every(n=>n.mapping_origin==='published'));
  for(const n of db.native)for(const link of Object.values(n.links)){
   const steps=link.steps.map(id=>data.route_steps[id]);
   assert.equal(steps[0].source,source);assert.equal(steps.at(-1).source,'S29');
   assert.ok(n.lineage);assert.ok(n.lineage.steps.some(id=>data.route_steps[id].source==='S30')||n.code==='R_S');assert.ok(!steps.some(s=>s.source==='S30')); // Context is not membership.
  }
 }
 assert.deepEqual(M.cell(model,col('FIGARO'),'77.11').matches.map(m=>m.native.code),['N77']);
 assert.deepEqual(M.cell(model,col('WIOD'),'77.11').matches.map(m=>m.native.code),['N']);
 for(const code of ['90.11','96.10'])assert.deepEqual(M.cell(model,col('WIOD'),code).matches.map(m=>m.native.code),['R_S']);
 for(const id of ['S27','S29','S30'])assert.match(data.sources[id].sha256,/^[a-f0-9]{64}$/);
 assert.match(data.sources.S26.native_input_sha256,/^[a-f0-9]{64}$/);
});
test('GLORIA has reviewed native footprints with source qualifications and shared annual sets',()=>{
 const db=col('GLORIA');assert.equal(db.native.length,120);assert.equal(db.native_count,120);
 assert.deepEqual(db.years,[2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025]);assert.deepEqual(db.releases,['060']);
 assert.ok(db.native.every(n=>n.classes.length&&n.mapping_origin==='reviewed_editorial'));
 const grain=M.cell(model,db,'01.11');assert.equal(grain.resolution,.25);
 assert.deepEqual(grain.matches.map(m=>m.native.code),['1','2','3','4']);
 assert.ok(grain.matches.every(m=>m.link.nodes.some(n=>n[0]==='NXB')));
 const rice=M.cell(model,db,'01.12');assert.deepEqual(rice.matches.map(m=>m.native.code),['5']);
 assert.ok(!M.cell(model,db,'35.11').matches.some(m=>m.native.code==='94'));
 const wood=M.cell(model,db,'16.21');assert.ok(wood.matches.some(m=>m.native.code==='59'));
 assert.ok(M.cell(model,db,'24.51').matches.some(m=>m.native.code==='77'));
 assert.ok(M.cell(model,db,'24.53').matches.some(m=>m.native.code==='78'));
 assert.ok(M.cell(model,db,'35.21').matches.some(m=>m.native.code==='94'));
 const steam=M.cell(model,db,'35.30');assert.ok(steam.matches.some(m=>m.native.code==='95'&&m.link.status==='partial'));
 assert.equal(M.cell(model,db,'38.21').matches.some(m=>m.native.code==='96'),false);
 assert.ok(M.cell(model,db,'38.21').matches.some(m=>m.native.code==='97'));
 assert.equal(M.cell(model,db,'24.42').matches.some(m=>m.native.code==='84'),false);
 assert.ok(db.native.some(n=>Object.values(n.links).some(l=>l.status==='partial')));
 assert.equal(M.cell(model,db,'99.00').resolution,null);
 assert.match(data.sources.S18.sha256,/^[a-f0-9]{64}$/);assert.match(data.sources.S22.sha256,/^[a-f0-9]{64}$/);
});
test('OECD uses published ISIC ranges, keeping metals and transport-equipment splits distinct',()=>{
 const db=col('OECD');assert.equal(db.native.length,50);assert.deepEqual(db.releases,['Extended','Regular']);
 assert.ok(M.cell(model,db,'24.51').matches.some(m=>m.native.code==='C24A'));
 assert.ok(!M.cell(model,db,'24.51').matches.some(m=>m.native.code==='C24B'));
 assert.ok(M.cell(model,db,'24.53').matches.some(m=>m.native.code==='C24B'));
 assert.deepEqual(M.cell(model,db,'30.11').matches.map(m=>m.native.code),['C301']);
 assert.deepEqual(M.cell(model,db,'30.20').matches.map(m=>m.native.code),['C302T309']);
 assert.equal(M.cell(model,db,'99.00').resolution,null);
 assert.ok(db.native.every(n=>n.mapping_origin==='published'&&Object.values(n.links).every(l=>l.steps.some(id=>data.route_steps[id].source==='S21'))));
});
test('each intermediate step has an attributable source and no proposed nxbase route enters colours',()=>{
 for(const c of model.columns)for(const n of c.native)for(const [code,link] of Object.entries(n.links)){
  assert.ok(model.ref.leaves.includes(code));assert.equal(link.nodes.length,link.steps.length+1);
  if(c.family==='EXIOBASE'&&c.units==='Monetary'&&link.nodes.some(n=>n[0]==='NXB')){
   assert.equal(link.status,'reviewed');assert.match(link.relation,/contained in NACE/);
   assert.ok(link.steps.every(id=>data.route_steps[id].source==='S11'));
  }
  if(c.family==='EXIOBASE'&&c.units==='Hybrid'){
   assert.equal(data.route_steps[link.steps[0]].source,'S23');
   if(link.mapping_origin==='shared_exiobase_activity'){
    assert.ok(['documented','partial','reviewed'].includes(link.status));assert.equal(data.route_steps[link.steps[1]].source,'S25');
    assert.deepEqual(link.nodes[2],['EXIO3I',n.code]);assert.ok(n.shared_activity);
   }else{
    assert.ok(['reviewed','governed'].includes(link.status));assert.equal(link.mapping_origin,'governed_nxbase');
    assert.ok(link.steps.slice(1).every(id=>data.route_steps[id].source==='S24'));
   }
  }
  for(const id of link.steps){const step=data.route_steps[id];assert.ok(step);assert.ok(data.sources[step.source]?.url);assert.ok(step.location);}
 }
});
test('unchanged annual EXIOBASE and ADB classifications share one column',()=>{
 assert.equal(model.columns.filter(c=>c.family==='EXIOBASE'&&c.units==='Monetary').length,1);
 assert.ok(col('EXIOBASE').releases.includes('3.8.2'));assert.ok(col('EXIOBASE').releases.includes('3.11.2'));
 assert.equal(model.columns.filter(c=>c.family==='ADB').length,1);assert.ok(col('ADB').releases.length>1);
 assert.equal(col('CEDA').native_count,400);assert.equal(col('CEDA').guide,null);
});
test('overview coordinates retain every row and make short section labels readable',()=>{
 const g=M.geometry(model.leaves);assert.equal(g.edges.length,652);assert.equal(g.centres.length,651);
 for(let i=0;i<651;i++){assert.ok(g.edges[i+1]>g.edges[i]);assert.equal(M.rowAt(g,g.centres[i]),i);}
 const labels=M.labels(model,model.leaves,1);assert.equal(labels.length,Object.keys(model.ref.section_counts).length);
 for(const label of labels)assert.ok(g.edges[label.end+1]-g.edges[label.start]>=24.99);
});

test('intermediate steps follow the displayed route direction, including reversed containment',()=>{
 const inverse={'Left contains right':'Left within right','Left within right':'Left contains right','Product to producing industry':'Industry to product'};
 for(const c of model.columns)for(const n of c.native)for(const link of Object.values(n.links))for(let i=0;i<link.steps.length;i++){
  const step=data.route_steps[link.steps[i]],from=link.nodes[i],to=link.nodes[i+1];
  const forward=JSON.stringify(from)===JSON.stringify(step.source_left);
  assert.deepEqual(from,forward?step.source_left:step.source_right);
  assert.deepEqual(to,forward?step.source_right:step.source_left);
  assert.equal(step.relation,step.source==='S09'?'Commodity / industry descriptor to producing NAICS activity':forward?step.source_relation:(inverse[step.source_relation]||step.source_relation));
 }
});


test('a database finer than a NACE class gets 1/k using the complete correspondence',()=>{
 const c=M.cell(model,col('EXIOBASE'),'24.42');
 assert.equal(c.matches.length,2);assert.ok(c.matches.every(m=>m.native.classes.length===1));
 assert.equal(c.resolution,.5);assert.equal(c.splitCount,2);assert.equal(M.resolutionLabel(c),'1/2');
 assert.equal(c.resolutionBasis,'exclusive_native_split');
 const leaf=M.rows(model,'24.42');assert.equal(M.matrix(model,leaf,[col('EXIOBASE')])[0][0],M.scaleValue(.5,model.maximum));
 assert.equal(c.denominator,model.ref.section_counts.C);
});
test('multiple cross-class or cross-section overlaps never become 1/k splits',()=>{
 const c=M.cell(model,col('CEDA'),'01.11');assert.ok(c.matches.length>1);
 assert.equal(c.splitCount,0);assert.ok(c.resolution>=1);assert.equal(c.resolution,c.maximum);
 const partial={...col('EXIOBASE'),byReference:new Map(col('EXIOBASE').byReference)};
 partial.byReference.set('24.42',col('EXIOBASE').byReference.get('24.42').map(n=>({...n,links:{...n.links,'24.42':{...n.links['24.42'],status:'partial'}}})));
 assert.equal(M.cell(model,partial,'24.42').splitCount,0);
});
test('zero is the scale origin, fine fractions remain numeric, and missing stays null',()=>{
 assert.equal(M.scaleValue(0,model.maximum),0);assert.equal(M.scaleValue(1,model.maximum),.05);
 assert.equal(M.scaleValue(null,model.maximum),null);assert.equal(M.scaleValue(model.maximum,model.maximum),1);
 const values=[0,.2,.25,.5,1,2,5,10,model.maximum].map(n=>M.scaleValue(n,model.maximum));
 assert.ok(values.every((v,i)=>!i||v>values[i-1]));
});
test('selection uses actual cell borders even with nonuniform section row heights',()=>{
 const visible=M.rows(model),coordinates=M.geometry(visible),cs=[col('EXIOBASE'),col('ADB'),col('CEDA')];
 const s=M.selection(visible,cs,coordinates,'24.42',cs[0].id),row=visible.findIndex(n=>n.code==='24.42');
 assert.deepEqual(s,{x0:-.5,x1:.5,y0:coordinates.edges[row],y1:coordinates.edges[row+1]});
 assert.equal(M.selection(visible,cs,coordinates,'24.42','absent'),null);
 assert.equal(M.selection(M.rows(model,'A'),cs,M.geometry(M.rows(model,'A')),'24.42',cs[0].id),null);
});

test('non-renewable generation uses the reviewed EXIOBASE to nxbase to NACE route',()=>{
 const c=M.cell(model,col('EXIOBASE'),'35.11');
 assert.deepEqual(c.matches.map(m=>m.native.code),['i40.11.a','i40.11.b','i40.11.c','i40.11.f']);
 assert.equal(c.splitCount,4);assert.equal(c.resolution,.25);
 for(const m of c.matches){assert.equal(m.link.status,'reviewed');assert.deepEqual(m.native.classes,['35.11']);assert.ok(m.link.nodes.some(n=>n[0]==='NXB'));assert.ok(!m.link.nodes.some(n=>n[0]==='EXIO3P'));}
 assert.ok(M.matrix(model,M.rows(model,'35.11'),[col('EXIOBASE')])[0][0]<M.scaleValue(.5,model.maximum));
});
test('renewable technologies do not leak into non-renewables or steam via revision bridges',()=>{
 const renewable=M.cell(model,col('EXIOBASE'),'35.12');
 assert.deepEqual(renewable.matches.map(m=>m.native.code),['i40.11.d','i40.11.e','i40.11.h','i40.11.i','i40.11.j','i40.11.k']);
 assert.equal(renewable.splitCount,6);assert.equal(renewable.resolution,1/6);
 assert.ok(M.cell(model,col('EXIOBASE'),'35.30').matches.every(m=>!m.native.code.startsWith('i40.11.')));
});
test('mixed biomass/waste and the editorial nec anchor remain pending, never counted',()=>{
 for(const code of ['35.11','35.12']){
  const c=M.cell(model,col('EXIOBASE'),code);assert.deepEqual(c.pending.map(n=>n.code),['i40.11.g','i40.11.l']);
  assert.ok(c.pending.every(n=>n.classes.length===0&&n.pending.status==='pending'));
  assert.match(c.pending.find(n=>n.code==='i40.11.l').pending.review_note,/editorial hypothesis/);
  assert.match(c.pending.find(n=>n.code==='i40.11.g').pending.review_note,/all waste is renewable/);
  for(const n of c.pending)for(const id of n.pending.steps){assert.ok(data.sources[data.route_steps[id].source]?.url);}
 }
});


test('fixed three-colour anchors keep low counts distinct and saturate only the broad tail',()=>{
 assert.equal(M.scaleValue(0),0);assert.equal(M.scaleValue(10),.5);assert.equal(M.scaleValue(50),1);assert.equal(M.scaleValue(82),1);
 const values=[0,.25,.5,1,2,5,9.99,10,10.01,20,40,50].map(n=>M.scaleValue(n));
 assert.ok(values.every((v,i)=>!i||v>values[i-1]));
 assert.ok(Math.abs(M.scaleValue(9.99999)-M.scaleValue(10.00001))<.000001);
 assert.equal(M.cell(model,col('GLORIA'),'35.30').resolution,1);
 assert.equal(M.cell(model,col('OECD'),'47.11').resolution,82);
 assert.equal(M.scaleValue(M.cell(model,col('OECD'),'47.11').resolution),1);
 assert.equal(M.scaleValue(5,20),M.scaleValue(5,82));
});
test('the palette has exactly three original MARIO colours',()=>{
 assert.deepEqual(M.colourScale('#6dd0e5','#fdca27','#fc6b3c'),[[0,'#6dd0e5'],[.5,'#fdca27'],[1,'#fc6b3c']]);
});
test('CPA keeps the broad tail below saturation and colours remain stable when filtering',()=>{
 const products=M.index(data,'commodity'),db=products.columns.find(c=>c.family==='EXIOBASE');
 assert.equal(M.scaleValue(null,'commodity'),null);
 assert.ok(M.scaleValue(292,'commodity')<1);
 assert.ok(M.scaleValue(10,'commodity')-M.scaleValue(1,'commodity')>.2);
 const row=products.leaves.find(n=>M.cell(products,db,n.code).resolution>50),value=M.cell(products,db,row.code).resolution;
 const full=M.matrix(products,products.leaves,[db]),filtered=M.matrix(products,M.rows(products,row.code),[db]);
 assert.equal(filtered[0][0],full[products.leaves.indexOf(row)][0]);
 assert.equal(filtered[0][0],M.scaleValue(value,'commodity'));
 assert.ok(filtered[0][0]<M.scaleValue(value));
 assert.equal(M.cell(products,db,row.code).resolution,value);
});


test('Hybrid keeps all 164 native activities and fills shared footprints from verified monetary identities',()=>{
 const h=model.columns.find(c=>c.family==='EXIOBASE'&&c.units==='Hybrid');
 assert.equal(h.status,'documented');assert.equal(h.namespace,'EXIO3H');assert.equal(h.native.length,164);assert.equal(new Set(h.native.map(n=>n.code)).size,164);
 assert.equal(h.native.filter(n=>Object.keys(n.links).length).length,162);assert.equal(h.native.filter(n=>n.coarse).length,0);assert.equal(h.native.filter(n=>n.pending).length,2);assert.equal(h.native.filter(n=>n.unresolved).length,0);assert.equal(h.native.filter(n=>n.shared_activity).length,149);
 assert.ok(h.native.some(n=>n.name==='Distribution of gaseous fuels through mains'));assert.ok(h.native.some(n=>n.name==='Manufacture of gas;'));
 assert.ok(h.native.some(n=>n.name==='Re-processing of secondary lead into new lead'));assert.ok(!h.native.some(n=>n.name==='Re-processing of secondary lead into new lead, zinc and tin'));
 for(const n of h.native)for(const link of [...Object.values(n.links),...(n.pending?[n.pending]:[]),...(n.unresolved?[n.unresolved]:[]),...(n.coarse?n.coarse.anchors:[])]){
  assert.equal(link.nodes[0][0],'EXIO3H');assert.equal(link.nodes[1][0],'EX3h');if(!n.shared_activity)assert.ok(!link.nodes.some(node=>['EXIO3I','EXIO3P'].includes(node[0])));
  assert.ok(link.steps.every(id=>data.sources[data.route_steps[id].source]?.url));
 }
});
test('Hybrid retains electricity refinements and maps shared aggregates without expanding their parent',()=>{
 const h=model.columns.find(c=>c.family==='EXIOBASE'&&c.units==='Hybrid');
 assert.equal(M.cell(model,h,'35.11').splitCount,4);assert.equal(M.cell(model,h,'35.12').splitCount,6);
 assert.equal(M.cell(model,h,'35.11').pending.length,2);
 const beverages=M.cell(model,h,'11.01');assert.equal(beverages.resolution,7);assert.ok(beverages.matches.some(m=>m.native.name==='Manufacture of beverages'&&m.link.status==='partial'));assert.ok(beverages.matches.filter(m=>m.native.name!=='Manufacture of beverages').every(m=>m.link.status==='partial')); // Broad legacy revisions remain qualified.
 assert.equal(M.matrix(model,M.rows(model,'11.01'),[h])[0][0],M.scaleValue(7));
 assert.ok(!M.cell(model,h,'01.11').coarse.some(n=>n.name==='Manufacture of beverages'));
 const wheat=M.cell(model,h,'01.11').matches.find(m=>m.native.name==='Cultivation of wheat');assert.ok(wheat.link.nodes.some(n=>n[0]==='NACE2.1'&&n[1]==='01.11'));
});

test('all 161 common activity footprints preserve the monetary classes and overlap flags',()=>{
 const h=model.columns.find(c=>c.family==='EXIOBASE'&&c.units==='Hybrid'),m=col('EXIOBASE'),mon=new Map(m.native.map(n=>[n.code,n]));let shared=0;
 for(const n of h.native){const other=mon.get(n.code);if(!other||other.name!==n.name)continue;shared++;
  assert.deepEqual(Object.keys(n.links).sort(),Object.keys(other.links).sort(),n.code);
  for(const code of Object.keys(n.links))assert.equal(n.links[code].status,other.links[code].status,n.code+' '+code);
  if(n.shared_activity)for(const [code,link] of Object.entries(n.links)){
   assert.deepEqual(link.nodes.slice(2),other.links[code].nodes);
   assert.deepEqual(link.steps.slice(2),other.links[code].steps);
  }
 }
 assert.equal(shared,161);assert.ok(h.byReference.size<651);
 assert.ok(['35.16','35.23','46.89'].every(code=>!h.byReference.has(code)));
 for(const [native,code] of [['i40.2.a','35.21'],['i40.2.b','35.22'],['i27.43.w','24.43']]){
  const n=h.native.find(n=>n.code===native);assert.deepEqual(Object.keys(n.links),[code]);assert.ok(!n.shared_activity);
 }
});
