const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../../doc/source/_static');
const M=require(path.join(root,'sectoral-model.js')),C=require(path.join(root,'country-model.js'));
const data=JSON.parse(fs.readFileSync(path.join(root,'data/economy/sectoral-scope.json')));
const countries=JSON.parse(fs.readFileSync(path.join(root,'data/economy/country-scope.json')));
const activity=M.index(data),commodity=M.index(data,'commodity');
const col=model=>model.columns.find(c=>c.family==='BONSAI');
const item=(model,code)=>col(model).native.find(n=>n.code===code);

test('BONSAI exposes the complete regional vocabulary, keeping Global counts separate',()=>{
 for(const model of [activity,commodity]){
  const c=col(model);assert.equal(c.label,'BONSAI');assert.equal(c.native_count,1707);
  assert.equal(c.native.length,1707);assert.equal(c.status,'documented');assert.ok(c.default_visible);
  assert.match(c.note,/355.*1,332/);assert.match(c.note,/Global nodes are markets/);
 }
 assert.ok(col(activity).native.filter(n=>n.classes.length).length>1000);
 assert.ok(col(commodity).native.filter(n=>n.classes.length).length>700);
 assert.deepEqual(Object.keys(item(activity,'A_Wheat').links),['01.11']);
 assert.ok(item(commodity,'C_Wheat').links['01.11.11']);
 assert.equal(countries.profiles.find(p=>p.family==='BONSAI').scope_counts.Sector.count,355);
});

test('historical electricity revisions do not misclassify explicit technologies or storage services',()=>{
 assert.deepEqual(Object.keys(item(activity,'A_POWG').links),['35.11']);
 assert.deepEqual(Object.keys(item(activity,'A_POWN').links),['35.11']);
 assert.deepEqual(Object.keys(item(activity,'A_POWW').links),['35.12']);
 assert.deepEqual(Object.keys(item(activity,'A_CHP').links),['35.30']);
 assert.deepEqual(Object.keys(item(commodity,'C_elec_POWG').links),['35.11.00']);
 assert.deepEqual(Object.keys(item(commodity,'C_elec_POWW').links),['35.12.00']);
 assert.deepEqual(Object.keys(item(commodity,'M_electricity').links).sort(),['35.11.00','35.12.00']);
 assert.equal(item(activity,'A_POWG').links['35.11'].mapping_origin,'reviewed_editorial');
 assert.ok(item(activity,'A_POWG').links['35.11'].evidence.includes('B11'));
});

test('market footprints retain explicit product routes and cannot become exclusive subdivisions',()=>{
 const wheat=item(commodity,'M_Wheat').links['01.11.11'];
 assert.deepEqual(wheat.nodes.slice(0,2),[['BONSAIP','M_Wheat'],['BONSAISUTP','C_Wheat']]);
 assert.equal(data.route_steps[wheat.steps[0]].source,'B09');
 assert.equal(wheat.status,'partial');assert.equal(wheat.exclusive_reference,false);
 assert.equal(M.cell(activity,col(activity),'01.11').splitCount,0);
 const capital=col(commodity).native.find(n=>n.code.startsWith('KCAP'));
 assert.ok(capital);assert.equal(capital.classes.length,0);
});

test('a detailed process with only a broad source anchor remains outside the fine index',()=>{
 const cement=item(activity,'A_CMNT');assert.equal(cement.classes.length,0);
 assert.equal(cement.coarse.classification_label,'NACE Rev. 2');
 assert.ok(cement.coarse.reference_candidates.includes('23.51'));
 const cell=M.cell(activity,col(activity),'23.51');
 assert.ok(cell.coarse.some(n=>n.code==='A_CMNT'));
 assert.ok(!cell.matches.some(m=>m.native.code==='A_CMNT'));
});

test('country lookups use supplied reference-process pairs and observed regional sector memberships',()=>{
 const profile=countries.profiles.find(p=>p.family==='BONSAI');
 const result=C.query(profile,'ITA',countries.classifications['nace-2.1'],'35.11',countries.mappings);
 const gas=result.matches.find(n=>n.native_code==='C_elec_POWG');assert.ok(gas);
 const route=countries.mapping_routes[gas.route_id];
 assert.deepEqual(route.nodes.slice(0,2),[['BONSAIHIOT','C_elec_POWG'],['BONSAIA','A_POWG']]);
 assert.equal(countries.mapping_route_steps[route.steps[0]].source,'B02');
 const native=new Set(C.nativeSet(profile,'ITA','Sector'));
 assert.ok(result.matches.every(n=>native.has(n.native_label)));
 const wheat=C.query(profile,'ITA',countries.classifications['cpa-2.2'],'01.11.11',countries.mappings);
 assert.ok(wheat.matches.some(n=>n.native_code==='C_Wheat'));
 assert.ok(wheat.matches.every(n=>native.has(n.native_label)));
 const cement=C.query(profile,'ITA',countries.classifications['nace-2.1'],'23.51',countries.mappings);
 assert.equal(cement.status,'coarse');
 assert.ok(cement.matches.some(n=>n.native_code==='C_CMNT' && n.precision==='coarse'));
 assert.ok(cement.matches.every(n=>n.precision==='coarse'));
});
