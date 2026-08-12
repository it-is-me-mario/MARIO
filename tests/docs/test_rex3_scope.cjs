const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../../doc/source/_static');
const D=require(root+'/database-scope.js');
const G=require(root+'/database-comparisons.js');
const native=JSON.parse(fs.readFileSync(root+'/data/database_profiles.json')).profiles;
const external=JSON.parse(fs.readFileSync(root+'/data/external_profiles.json')).profiles;
const licences=JSON.parse(fs.readFileSync(root+'/data/database_licences.json'));
const rex=external.find(p=>p.variant==='REX3');

test('Overview keeps REX3 in EXIOBASE with its own counts, release and CC BY 4.0 terms',()=>{
 const points=D.scopePoints([...native,...external],licences);
 const point=points.find(p=>p.releases.includes('REX3'));
 assert.equal(point.family,'EXIOBASE');assert.equal(point.regions,189);assert.equal(point.sectors,163);
 assert.equal(point.access,'open');assert.equal(point.licences[0].label,'CC BY 4.0');
 assert.ok(!points.some(p=>p.family==='REX3'));
 const standard=points.filter(p=>p.family==='EXIOBASE'&&p.units==='Monetary'&&!p.releases.includes('REX3'));
 assert.ok(standard.every(p=>p.regions===49));
});
test('Geographical scope separates REX3 in Version, including identical region signatures',()=>{
 const choices=G.geographicVersions([...native,...external],'EXIOBASE');
 const rexChoice=choices.find(c=>c.label==='REX3');
 assert.ok(rexChoice);assert.ok(rexChoice.profiles.every(p=>p.guide==='exiobase-rex3'));
 assert.ok(choices.find(c=>c.label==='Monetary - Standard releases').profiles.every(p=>p.guide==='exiobase-monetary'));
 const standard=native.find(p=>p.guide==='exiobase-monetary');
 assert.notEqual(G.geographyKey(standard),G.geographyKey({...standard,guide:'exiobase-rex3',variant:'REX3'}));
 assert.equal(new Set([...native,...external].map(p=>p.source)).has('REX3'),false);
});
test('REX3 metadata never becomes a parsed numerical reading or inherits standard concordances',()=>{
 assert.equal(rex.status,'source_verified');assert.equal(rex.numeric_publication,false);
 const scope=JSON.parse(fs.readFileSync(root+'/data/economy/country-scope.json'));
 const p=scope.profiles.find(p=>p.id===rex.id);
 assert.equal(p.family,'EXIOBASE');assert.equal(p.release,'REX3');assert.equal(p.mapping,null);
 assert.deepEqual(p.mapping_ids,[]);assert.deepEqual(p.reading_ids,[]);
 const sectors=JSON.parse(fs.readFileSync(root+'/data/economy/sectoral-scope.json'));
 const c=sectors.columns.activity.find(c=>c.profile_ids.includes(rex.id));
 assert.equal(c.variant,'REX3');assert.equal(c.status,'unverified');assert.equal(c.namespace,null);
 assert.ok(!c.native.some(n=>Object.keys(n.links||{}).length));
});
