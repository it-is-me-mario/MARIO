const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const D=require('../../doc/source/_static/database-scope.js');
const profiles=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../doc/source/_static/data/database_profiles.json'),'utf8')).profiles;
test('GTAP standard and Power are licensed scope metadata with truthful parser status',()=>{
 const external=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../doc/source/_static/data/external_profiles.json'),'utf8')).profiles;
 const points=D.scopePoints(external).filter(p=>p.family==='GTAP');assert.equal(points.length,2);
 assert.deepEqual(points.map(p=>[p.sectors,p.regions]),[[65,163],[76,163]]);
 assert.ok(points.every(p=>p.environmental&&p.licensed&&p.statuses.includes('source_verified')));
 assert.deepEqual(points[0].parser_supported,[false]);assert.deepEqual(points[1].parser_supported,[true]);
});

test('MRIO scope merges repeated annual counts, separates units and retains SUT classifications',()=>{
 const points=D.scopePoints(profiles);
 assert.ok(points.every(p=>p.regions>1));assert.ok(!points.some(p=>['BEA','USEEIO'].includes(p.family)));
 const monetary=points.filter(p=>p.family==='EXIOBASE'&&p.units==='Monetary');
 assert.deepEqual(monetary.map(p=>[p.sectors,p.regions]),[[163,49],[200,49]]);
 assert.ok(monetary.every(p=>p.environmental&&p.releases.includes('3.11.2')&&p.releases.includes('3.8.2')));
 assert.ok(monetary[0].dimensions.includes('Activity'));assert.ok(monetary[1].dimensions.includes('Commodity'));
 const hybrid=points.filter(p=>p.family==='EXIOBASE'&&p.units==='Hybrid');
 assert.deepEqual(hybrid.map(p=>[p.sectors,p.regions]),[[164,48],[200,48]]);
});

test('environmental status reflects actual loaded extensions, not dummy rows or GDP availability',()=>{
 const p={id:'test',status:'parsed',source:'Test',counts:{Region:10,Sector:20,'Satellite account':1},year:2024,release:'1',set_flags:{'Satellite account':{status:'not_loaded'}}};
 assert.equal(D.scopePoints([p])[0].environmental,false);
 const ee={...p,set_flags:{},id:'ee'};assert.equal(D.scopePoints([ee])[0].environmental,true);
 const emerging=D.scopePoints(profiles).filter(p=>p.family==='EMERGING');assert.ok(emerging.find(p=>p.releases.includes('E')));assert.ok(emerging.every(p=>p.environmental)); // EMERGING-E loads the projected EMERGING 2.2 CO2 companion.
});

test('scope figure keeps counts on numeric axes, family symbols and extension colours independent',()=>{
 const colors={background:'#fff',surface:'#fff',ink:'#222',grid:'#ddd',extended:'#178',base:'#978',font:'Arial'};
 const points=D.scopePoints(profiles),f=D.figure(points,colors),actual=f.data.filter(t=>!t.showlegend&&t.mode==='markers');
 assert.equal(f.layout.xaxis.title.text,'N. sectors');assert.equal(f.layout.yaxis.title.text,'N. regions');
 assert.equal(new Set(actual.map(t=>t.marker.symbol)).size,actual.length);
 const exio=actual.find(t=>t.name==='EXIOBASE');assert.ok(exio.marker.color.every(c=>c===colors.extended));
 const emerging=actual.find(t=>t.name==='EMERGING');assert.deepEqual(emerging.marker.color,points.filter(p=>p.family==='EMERGING').map(p=>p.environmental?colors.extended:colors.base));
 assert.equal(actual.reduce((n,t)=>n+t.x.length,0),points.length);
});


test('scope hover preserves gaps in the verified EMERGING years',()=>{
 const points=D.scopePoints(profiles).filter(p=>p.family==='EMERGING');
 const f=D.figure(points,{background:'#fff',surface:'#fff',ink:'#222',grid:'#ddd',extended:'#178',base:'#978',font:'Arial'});
 const rows=f.data.filter(t=>!t.showlegend&&t.mode==='markers').flatMap(t=>t.customdata);
 assert.equal(rows.find(r=>r[3].includes('1.0'))[4],'2010, 2015–2019');
 assert.equal(rows.find(r=>r[3].includes('2.0 · 2.2'))[4],'2015, 2018, 2021, 2023');
 assert.equal(rows.find(r=>r[3].includes('Versions: E<'))[4],'2018');
});


test('source-verified CEDA participates in scope without pretending to be parsed or counting its factors as satellite accounts',()=>{
 const external=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../doc/source/_static/data/external_profiles.json'),'utf8')).profiles;
 const points=D.scopePoints([...profiles,...external]);const ceda=points.find(p=>p.family==='CEDA');
 assert.equal(ceda.sectors,400);assert.equal(ceda.regions,149);assert.equal(ceda.environmental,true);assert.deepEqual(ceda.years,[2022]);assert.deepEqual(ceda.releases,['2024']);assert.deepEqual(ceda.statuses,['source_verified']);
 const f=D.figure([ceda],{background:'#fff',surface:'#fff',ink:'#222',grid:'#ddd',extended:'#178',base:'#978',font:'Arial'});assert.match(f.data.find(t=>!t.showlegend).customdata[0][6],/parser unavailable/);
 assert.equal(D.scopePoints([{...external[0],status:'unverified'}]).length,0);
});

test('explicit socioeconomic-only status overrides a nonzero satellite count',()=>{
 const wiod=profiles.filter(p=>p.source==='WIOD');
 assert.equal(wiod.length,3);assert.ok(wiod.some(p=>p.counts['Satellite account']===16));
 assert.ok(wiod.every(p=>p.environmental===false));assert.ok(D.scopePoints(wiod).every(p=>p.environmental===false));
});


test('GLORIA native scope retains the full emissions set and both SUT dimensions',()=>{
 const point=D.scopePoints(profiles).find(p=>p.family==='GLORIA');
 assert.equal(point.regions,164);assert.equal(point.sectors,120);assert.equal(point.environmental,true);
 assert.deepEqual(point.dimensions,['Activity','Commodity']);assert.deepEqual(point.years,[2022,2023,2024]);
});
