const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../../doc/source/_static');
const D=require(root+'/database-scope.js');
const G=require(root+'/database-comparisons.js');
const profiles=JSON.parse(fs.readFileSync(root+'/data/database_profiles.json')).profiles;
const licences=JSON.parse(fs.readFileSync(root+'/data/database_licences.json'));
const e3=profiles.filter(p=>p.guide==='figaro-e3');

test('E3 stays in the FIGARO family with its own parsed axes and CC BY 4.0',()=>{
 assert.equal(e3.length,3);assert.ok(e3.every(p=>p.source==='FIGARO'&&p.status==='parsed'));
 const sut=e3.find(p=>p.table==='SUT');
 assert.equal(sut.counts.Region,46);assert.equal(sut.counts.Activity,176);assert.equal(sut.counts.Commodity,213);
 const points=D.scopePoints(profiles,licences).filter(p=>p.releases.includes('E3'));
 assert.ok(points.length);assert.ok(points.every(p=>p.family==='FIGARO'&&p.regions===46&&p.access==='open'));
 assert.ok(points.every(p=>p.licences.some(l=>l.label==='CC BY 4.0')));
});
test('Geographical Version E3 stays distinct even for the same country signature',()=>{
 const groups=G.geographicVersions(profiles,'FIGARO');
 const group=groups.find(g=>g.label==='E3');
 assert.ok(group);assert.equal(group.profiles.length,3);
 assert.ok(group.profiles.every(p=>p.guide==='figaro-e3'));
 const standard=profiles.find(p=>p.guide==='figaro');
 assert.notEqual(G.geographyKey(standard),G.geographyKey({...standard,guide:'figaro-e3'}));
});
test('E3 native scope never inherits the standard 64-sector mappings or numerical readings',()=>{
 const scope=JSON.parse(fs.readFileSync(root+'/data/economy/country-scope.json'));
 for(const profile of scope.profiles.filter(p=>p.variant==='E3')){
  assert.equal(profile.family,'FIGARO');assert.equal(profile.mapping,null);
  assert.deepEqual(profile.mapping_ids,[]);assert.deepEqual(profile.reading_ids,[]);
  assert.equal(profile.regions.filter(r=>r.kind==='country').length,45);
  assert.equal(profile.regions.find(r=>r.label==='FIGW1').kind,'aggregate');
 }
 const sectors=JSON.parse(fs.readFileSync(root+'/data/economy/sectoral-scope.json'));
 for(const kind of ['activity','commodity']){
  const column=sectors.columns[kind].find(c=>c.variant==='E3');
  assert.ok(column);assert.equal(column.namespace,null);assert.equal(column.status,'unverified');
  assert.ok(column.native.every(n=>!Object.keys(n.links).length));
 }
});
