const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const D=require('../../doc/source/_static/database-scope.js');
const profiles=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../doc/source/_static/data/database_profiles.json'),'utf8')).profiles;
test('BONSAI displays the Global count and retains heterogeneous native counts',()=>{
 const profile=profiles.find(p=>p.source==='BONSAI');
 assert.equal(profile.counts.Sector,1707);
 assert.equal(profile.region_counts.find(r=>r.region==='Global'&&r.set==='Sector').count,355);
 const [point]=D.scopePoints([profile]);assert.equal(point.sectors,355);assert.equal(point.regions,50);
 assert.match(point.countNotes[0],/varies by region/);assert.match(point.countNotes[0],/355–1,332/);
 assert.ok(point.environmental);assert.equal(point.units,'Hybrid');
});
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
 assert.equal(ceda.sectors,400);assert.equal(ceda.regions,149);assert.equal(ceda.environmental,true);assert.deepEqual(ceda.years,[2023]);assert.deepEqual(ceda.releases,['2025']);assert.deepEqual(ceda.statuses,['source_verified']);
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
 assert.deepEqual(point.dimensions,['Activity','Commodity']);assert.deepEqual(point.years,Array.from({length:40},(_,i)=>1990+i));
 assert.deepEqual(point.sourceCoverage,['1990–2029 · 2024–2029 forecasts']);
});


test('source licences distinguish access conditions from licences of the metadata extract',()=>{
 const external=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../doc/source/_static/data/external_profiles.json'),'utf8')).profiles;
 const licences=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../doc/source/_static/data/database_licences.json'),'utf8'));
 const points=D.scopePoints([...profiles,...external],licences);
 assert.ok(points.filter(p=>p.family!=='BONSAI').every(p=>['open','noncommercial','restricted'].includes(p.access)));
 assert.equal(points.find(p=>p.family==='BONSAI').access,'unverified');
 assert.ok(points.filter(p=>['EORA','GTAP'].includes(p.family)).every(p=>p.access==='restricted'));
 assert.equal(points.find(p=>p.family==='CEDA').access,'restricted');
 assert.equal(points.find(p=>p.family==='CEDA').licences[0].metadata.label,'Open CEDA · CC BY-SA 4.0');
 assert.equal(points.find(p=>p.family==='GLORIA').access,'noncommercial');
 const exio=points.filter(p=>p.family==='EXIOBASE'&&p.units==='Monetary');assert.equal(exio.length,2);
 assert.ok(exio.every(p=>p.access==='noncommercial'&&p.licences.some(l=>l.category==='open'&&l.releases.includes('3.8.2'))));
 assert.ok(points.filter(p=>p.family==='EXIOBASE'&&p.units==='Hybrid').every(p=>p.access==='open'));
 const colors={background:'#fff',surface:'#fff',ink:'#222',grid:'#ddd',extended:'#178',base:'#978',font:'Arial'};
 const f=D.figure(points,colors),markers=f.data.filter(t=>!t.showlegend&&t.mode==='markers');
 assert.ok(markers.every(t=>t.marker.line.color.length===t.x.length));
 for(const p of points) {
  const t=markers.find(t=>t.name===p.family),i=points.filter(q=>q.family===p.family).indexOf(p);
  assert.equal(t.marker.line.width[i],p.access==='open'?0:2);
  assert.equal(t.marker.line.color[i],colors.ink);
  assert.equal(t.marker.line.dash[i],p.access==='noncommercial'?'3px,2px':p.access==='unverified'?'dot':'solid');
 }
 assert.match(markers.find(t=>t.name==='CEDA').customdata[0][7],/Proprietary \/ restricted.*Scope metadata:.*Open CEDA/);
 assert.ok(markers.find(t=>t.name==='EXIOBASE').customdata.filter(r=>r[1]==='Monetary').every(r=>r[7].includes('Licences vary by release')&&r[7].includes('3.8.2')&&r[7].includes('3.11.2')));
 const future={...profiles.find(p=>p.guide==='exiobase-monetary'),release:'9.0'};
 assert.equal(D.scopePoints([future],licences)[0].access,'unverified');
 assert.equal(D.scopePoints([{...future,guide:'new-source',numeric_publication:false}],licences)[0].access,'unverified');
});


test('each family has one cluster label which follows its legend group',()=>{
 const external=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../doc/source/_static/data/external_profiles.json'),'utf8')).profiles;
 const points=D.scopePoints([...profiles,...external]);
 const figure=D.figure(points,{background:'#fff',surface:'#eee',ink:'#222',grid:'#aaa',font:'Arial',extended:'#0aa',base:'#a0a'});
 const labels=figure.data.filter(t=>t.mode==='text');
 const families=[...new Set(points.map(p=>p.family))];
 assert.equal(labels.length,families.length);
 for(const family of families){
  const label=labels.find(t=>t.name===family);
  assert.deepEqual(label.text,[family]);assert.equal(label.legendgroup,family);assert.equal(label.showlegend,false);
  assert.ok(Number.isFinite(label.x[0])&&Number.isFinite(label.y[0]));
 }
});

test('the Overview year filter keeps covering readings and narrows their years',()=>{
 const a={id:'a',status:'parsed',source:'A',counts:{Region:10,Sector:20},year:2020,years:[2018,2019,2020]};
 const b={id:'b',status:'source_verified',source:'B',counts:{Region:5,Sector:9},year:2016};
 const national={id:'n',status:'parsed',source:'N',counts:{Region:1,Sector:9},year:2030,years:[2030]};
 assert.deepEqual(D.profileYears([a,b,national]),[2020,2019,2018,2016]);
 assert.equal(D.profilesForYear([a,b],'all').length,2);
 const only=D.profilesForYear([a,b],'2019');
 assert.deepEqual(only.map(p=>p.id),['a']);assert.deepEqual(only[0].years,[2019]);
 assert.deepEqual(D.profilesForYear([a,b],'2016').map(p=>p.id),['b']);
});

test('the year timeline has one row per family, marks source base years and the selected year',()=>{
 const a={id:'a',status:'parsed',source:'A',release:'1',counts:{Region:10,Sector:20},years:[2018,2019]};
 const a2={id:'a2',status:'parsed',source:'A',release:'2',counts:{Region:10,Sector:30},years:[2019]};
 const b={id:'b',status:'source_verified',parser_supported:false,environmental:true,source:'B',release:'2025',counts:{Region:5,Sector:9},year:2023};
 const cells=D.timelinePoints([a,a2,b]);
 assert.deepEqual(cells.map(c=>[c.family,c.year]),[['A',2018],['A',2019],['B',2023]]);
 assert.deepEqual(cells.find(c=>c.family==='A'&&c.year===2019).versions,['1','2']);
 assert.equal(cells.find(c=>c.family==='B').sourceOnly,true);assert.equal(cells.find(c=>c.family==='A').sourceOnly,false);
 const colors={background:'#fff',surface:'#fff',ink:'#222',grid:'#ddd',extended:'#178',base:'#978',font:'Arial'};
 const all=D.timelineFigure(cells,colors),picked=D.timelineFigure(cells,colors,{year:'2023'});
 assert.equal(all.layout.shapes.length,0);assert.equal(picked.layout.shapes[0].x0,2023);
 assert.deepEqual(picked.data.map(t=>t.opacity),[.28,1]);
 assert.ok(!String(picked.data[1].marker.symbol).endsWith('-open'));
 // A family keeps its symbol when a year filter hides other families.
 const order=['A','B'],scatter=D.figure(D.scopePoints([b]),colors,900,order);
 assert.equal(scatter.data.find(t=>t.name==='B'&&t.mode==='markers').marker.symbol,picked.data[1].marker.symbol);
});

test('publisher-documented years appear faded and do not count as parsed coverage',()=>{
 const g={id:'g',status:'parsed',source:'G',release:'060',counts:{Region:164,Sector:120},years:[2020,2021],source_coverage:{first_year:2018,last_year:2023,forecast_from:2022}};
 const cells=D.timelinePoints([g]);
 assert.deepEqual(cells.map(c=>c.year),[2018,2019,2020,2021,2022,2023]);
 assert.deepEqual(cells.filter(c=>c.publisher).map(c=>c.year),[2018,2019,2022,2023]);
 assert.deepEqual(cells.filter(c=>c.forecast).map(c=>c.year),[2022,2023]);
 const colors={background:'#fff',surface:'#fff',ink:'#222',grid:'#ddd',extended:'#178',base:'#978',font:'Arial'};
 assert.equal(D.timelineFigure(cells,colors,{year:'2019'}).data[0].opacity,.28);
 assert.equal(D.timelineFigure(cells,colors,{year:'2020'}).data[0].opacity,1);
 assert.deepEqual(D.timelineFigure(cells,colors).data[0].marker.opacity,[.3,.3,1,1,.3,.3]);
});

test('source-only reference years can be explicitly unavailable without losing classifications',()=>{
 const profile={id:'closed',status:'source_verified',parser_supported:true,source:'Closed',release:'1',counts:{Region:10,Sector:20},years:[2020,2021],website_years:[]};
 const cells=D.timelinePoints([profile]);
 assert.ok(cells.every(c=>!c.available));
 assert.equal(D.scopePoints([profile]).length,1);
 const colors={background:'#fff',surface:'#fff',ink:'#222',grid:'#ddd',extended:'#178',base:'#978',font:'Arial'};
 const figure=D.timelineFigure(cells,colors);
 assert.deepEqual(figure.data[0].marker.color,['#222','#222']);
 assert.deepEqual(figure.data[0].marker.opacity,[.3,.3]);
 assert.ok(figure.data[0].customdata.every(d=>d[3]==='Not available on this website'));
 // Availability is combined per family and year, rather than per database name.
 const shared=D.timelinePoints([profile,{...profile,id:'open',website_years:[2021]}]);
 assert.deepEqual(shared.map(c=>c.available),[false,true]);
});

test('Eora1 adds publisher years through 2023 while Eora2 and GTAP years remain grey',()=>{
 const parsed=JSON.parse(fs.readFileSync(path.join(__dirname,'../../doc/source/_static/data/database_profiles.json'))).profiles;
 const external=JSON.parse(fs.readFileSync(path.join(__dirname,'../../doc/source/_static/data/external_profiles.json'))).profiles;
 const cells=D.timelinePoints([...parsed,...external]);
 const eora=cells.filter(c=>c.family==='EORA');
 assert.deepEqual(eora.map(c=>c.year),Array.from({length:35},(_,i)=>1990+i));
 assert.ok(eora.filter(c=>c.year>=2018||c.year===2004).every(c=>!c.available));
 assert.ok(eora.filter(c=>c.year<2018&&c.year!==2004).every(c=>c.available));
 assert.deepEqual(eora.find(c=>c.year===1990).evidence,['Source structure checked']);
 assert.deepEqual(eora.find(c=>c.year===2017).evidence,['Verified MARIO parse']);
 assert.ok(cells.filter(c=>c.family==='GTAP').every(c=>!c.available));
});
