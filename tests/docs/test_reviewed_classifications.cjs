const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../../doc/source/_static');
const M=require(path.join(root,'sectoral-model.js')),S=require(path.join(root,'country-model.js'));
const data=JSON.parse(fs.readFileSync(path.join(root,'data/economy/sectoral-scope.json')));
const act=M.index(data),prod=M.index(data,'commodity');
const column=(model,family,namespace)=>model.columns.find(c=>c.family===family&&(!namespace||c.namespace===namespace));
test('current NACE and CPA references keep all official leaves and explicit hierarchy',()=>{
 assert.equal(act.leaves.length,651);assert.equal(prod.leaves.length,3354);
 assert.equal(prod.ref.nodes.length,5824);assert.equal(prod.ref.leaf_level,6);
 assert.equal(M.rows(prod,'01.11.11').length,1);assert.ok(M.rows(prod,'A').length>100);
 assert.deepEqual(M.ancestors(prod,'35.14.00').map(n=>n.code),['D','35','35.1','35.14','35.14.0','35.14.00']);
 assert.ok(prod.leaves.findIndex(n=>n.code==='35.14.00')<prod.leaves.findIndex(n=>n.code==='36.00.11'));
 const g=M.geometry(prod.leaves),labels=M.labels(prod,prod.leaves,1);
 assert.ok(labels.every(n=>(g.edges[n.end+1]-g.edges[n.start])/g.end>.025));
});
test('activity review removes concrete contradictory native memberships',()=>{
 const ex=column(act,'EXIOBASE','EXIO3I');
 const links=code=>Object.keys(ex.native.find(n=>n.code===code).links).sort();
 assert.deepEqual(links('i01.n'),['01.41','01.45']);assert.deepEqual(links('i99'),['99.00']);
 assert.deepEqual(links('i90.4.a'),['37.00']);assert.deepEqual(links('i15.g'),['10.61']);
 assert.deepEqual(links('i14.3'),['08.91','08.93','08.99']);assert.deepEqual(links('i26.d.w'),['23.51']);
 assert.ok(!links('i01.h').includes('01.12'));
 for(const col of act.columns.filter(c=>['FIGARO','WIOD','OECD','GLORIA'].includes(c.family)))for(const n of col.native){
  assert.ok(n.lineage);
  for(const link of Object.values(n.links))assert.equal(new Set(link.nodes.map(n=>n.join(':'))).size,link.nodes.length);
 }
});
test('Hybrid product sets use the published 200-to-164 aggregation, not activity identities',()=>{
 const sut=column(prod,'EXIOBASE','EXIO3HSUTP'),iot=column(prod,'EXIOBASE','EXIO3HIOTP');
 assert.equal(sut.native_count,200);assert.equal(iot.native_count,164);
 assert.ok(!sut.default_visible&&!iot.default_visible);
 for(const n of iot.native)for(const link of Object.values(n.links)){
  assert.equal(link.nodes[0][0],'EXIO3HIOTP');assert.equal(link.nodes[1][0],'EXIO3HSUTP');
  assert.equal(data.route_steps[link.steps[0]].source,'P17');
 }
});
test('qualified producer exclusion prevents false grain joins and never creates exact splits',()=>{
 const glo=column(prod,'GLORIA'),wheat=glo.native.find(n=>n.code==='1');
 assert.ok(wheat.links['01.11.11']);assert.ok(!wheat.links['01.12.00']);assert.ok(wheat.production_review);
 assert.ok(wheat.discarded_candidate_classes>0);
 const c=M.cell(prod,glo,'01.11.11');assert.equal(c.splitCount,0);
 assert.ok(c.matches.every(m=>m.link.status==='partial'&&m.link.exclusive_reference===false));
});
test('missing CPA producer evidence remains visible as unverified, with independent product routes',()=>{
 const ex=column(prod,'EXIOBASE','EXIO3P');assert.equal(ex.native.filter(n=>!n.classes.length).length,7);
 assert.ok(prod.columns.filter(c=>c.family==='EMERGING').every(c=>c.status==='unverified'));
 const allowed=new Set(['EXIO3P','EXIO3HSUTP','EXIO3HIOTP','USEEIO2017P','CEDA2024P','GLORIA060P','FIGARO64P','WIOD2016P','GTAP12P','CPC2.1','CPA2002','CPA2008','CPA2.1','CPA2.2','BONSAIP','BONSAISUTP']);
 for(const col of prod.columns)for(const n of col.native)for(const link of Object.values(n.links))assert.ok(link.nodes.every(n=>allowed.has(n[0])));
});
test('Italy current CPA lookup is available only to product readings, and exposes intermediate routes',()=>{
 const countries=JSON.parse(fs.readFileSync(path.join(root,'data/economy/country-scope.json')));
 const c=countries.classifications['cpa-2.2'];assert.equal(c.levels.at(-1),6);
 const pxp=countries.profiles.find(p=>p.family==='EXIOBASE'&&p.release==='3.11.2'&&p.system==='pxp');
 const ixi=countries.profiles.find(p=>p.family==='EXIOBASE'&&p.release==='3.11.2'&&p.system==='ixi');
 const result=S.query(pxp,'ITA',c,'01.11.11',countries.mappings);
 assert.equal(result.status,'mapped');assert.ok(result.matches.some(m=>m.native_code==='p01.b'));
 assert.equal(S.query(ixi,'ITA',c,'01.11.11',countries.mappings).status,'unavailable');
});
