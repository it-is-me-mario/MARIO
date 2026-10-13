const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const C = require(path.resolve(__dirname,'../../doc/source/_static/economy-charts.js'));
const colors={background:'#ffffff',surface:'#ffffff',ink:'#111111',muted:'#888888',grid:'#eeeeee',font:'Arial',palette:['#176d80','#d87530','#886bb2']};
const state={metric:'gdp',perCapita:false};
const row=(series,year,value,country='world')=>({series,database:series==='World Bank'?series:'EXIOBASE',version:series==='World Bank'?'WDI':series,year,value,country,country_name:country==='world'?'World':'Italy',unit:'current US$',note:''});
const options=(years=[2022,2024])=>({state,years,colors,nativeUnit:'current US$',catalogue:['3.11.2 ixi','3.10.2 ixi'],revision:'selection'});

test('monetary scales use a shared magnitude including references, preserve signs and source values',()=>{
 const rows=[row('3.11.2 ixi',2024,-1e9),row('World Bank',2024,2e9)];
 const before=structuredClone(rows), scale=C.scaleFor(rows,state,'current US$');
 assert.equal(scale.factor,1e9);assert.equal(scale.unit,'current US$ billion');
 assert.equal(C.scaled(rows[0].value,scale),-1);assert.deepEqual(rows,before);
 for(const [value,factor] of [[999,1],[1000,1e3],[1e6,1e6],[1e12,1e12]])assert.equal(C.scaleFor([{value}],state,'current US$').factor,factor);
 assert.equal(C.scaled(null,scale),null);
 assert.equal(C.scaleFor([],state,'current US$').factor,1);
});

test('GHG units convert Gg and Mt consistently without changing per-capita tonnes',()=>{
 const ghg={metric:'ghg',perCapita:false};
 const country=C.scaleFor([{value:1e6}],ghg,'Gg CO₂eq');
 const world=C.scaleFor([{value:1000}],ghg,'Mt CO₂eq');
 assert.equal(country.unit,'Gt CO₂eq');assert.equal(world.unit,'Gt CO₂eq');
 assert.equal(C.scaled(1e6,country),1);assert.equal(C.scaled(1000,world),1);
 const perCapita=C.scaleFor([{value:15.3}],{metric:'ghg',perCapita:true},'t CO₂eq/person');
 assert.equal(perCapita.factor,1);assert.equal(perCapita.unit,'t CO₂eq/person');
});

test('annual traces remain separate by version and country, with exact years and a unified tooltip',()=>{
 const rows=[row('3.11.2 ixi',2022,10e12),row('3.11.2 ixi',2024,12e12),row('3.10.2 ixi',2022,11e12),row('3.11.2 ixi',2024,2e12,'ITA'),row('World Bank',2022,10.1e12),row('World Bank',2024,12.1e12)];
 const f=C.figure(rows,options());
 assert.equal(f.data.length,4);assert.equal(f.layout.hovermode,'x unified');
 assert.deepEqual(f.data[0].x,[2022,2024]);assert.deepEqual(f.data[1].x,[2022]);
 assert.deepEqual(f.data[0].y,[10,12]);assert.ok(f.data.every(t=>t.mode==='markers'));
 assert.equal(f.layout.yaxis.title.text,'current US$ trillion');
 assert.equal(f.config.doubleClick,'autosize');assert.equal(f.config.scrollZoom,true);
 assert.equal(f.layout.legend.itemdoubleclick,'toggleothers');
 const ref=f.data.find(t=>t.name.startsWith('World Bank'));assert.equal(ref.marker.symbol,'line-ew');assert.ok(ref.marker.opacity<.7);assert.ok(ref.marker.line.width<2);
});

test('single-year comparisons have a family legend and a full-width reference line',()=>{
 const f=C.figure([row('3.11.2 ixi',2024,10e12),row('3.10.2 ixi',2024,11e12),row('World Bank',2024,12e12)],options([2024]));
 assert.equal(f.data.filter(t=>t.type==='bar').length,2);
 const ref=f.data.find(t=>t.name.startsWith('World Bank'));assert.equal(ref.type,'scatter');assert.equal(ref.marker.opacity,0);
 assert.deepEqual(ref.x,f.data.slice(0,2).flatMap(t=>t.x));assert.deepEqual(ref.y,[12,12]);
 assert.equal(f.layout.xaxis.unifiedhovertitle.text,'<b>2024</b>');
 assert.deepEqual(f.data.filter(t=>t.showlegend).map(t=>t.name),['EXIOBASE']);
 assert.equal(f.layout.legend.groupclick,'togglegroup');
 assert.equal(f.data[0].legendgroup,f.data[1].legendgroup);
 assert.deepEqual(f.layout.shapes.map(s=>[s.name,s.xref,s.x0,s.x1,s.y0,s.y1]),[['World Bank','paper',0,1,12,12]]);
 assert.equal(f.layout.shapes[0].showlegend,true);
 assert.match(f.data[0].hovertemplate[0],/3.11.2 ixi/);
});

test('no zero observations or reference-only chart is invented for unavailable readings',()=>{
 const f=C.figure([row('3.11.2 ixi',2024,null),row('World Bank',2024,2e12)],options([2024]));
 assert.deepEqual(f.data,[]);
});


test('focus keeps one reading as annual bars and switches multiple readings to scatter',()=>{
 const rows=[row('3.11.2 ixi',2022,10e12),row('3.11.2 ixi',2024,12e12),row('World Bank',2024,12.1e12)];
 const opts={...options(),state:state};
 const one=C.figure(rows,opts);assert.equal(one.data[0].type,'bar');assert.equal(one.data[1].marker.symbol,'diamond');
 assert.deepEqual(one.data[0].x,[2022,2024]);assert.equal(one.layout.hovermode,'x unified');
 const two=C.figure([...rows,row('3.10.2 ixi',2022,11e12)],opts);
 assert.ok(two.data.every(t=>t.type==='scatter'));assert.equal(two.data.find(t=>t.name==='World Bank').marker.symbol,'line-ew');
 const singleYear=C.figure([row('3.11.2 ixi',2024,12e12),row('3.10.2 ixi',2024,11e12)],{...opts,years:[2024]});
 assert.equal(singleYear.data.filter(t=>t.type==='bar').length,2);
});

test('focus keeps one colour across releases, system shape and unit fill with safe stable trace identifiers',()=>{
 const rows=[
  {...row('3.11.2 ixi',2024,1e9),release:'3.11.2',system:'ixi',units:'Monetary'},
  {...row('3.11.2 pxp',2024,1e9),release:'3.11.2',system:'pxp',units:'Monetary'},
  {...row('3.3.18 hybrid IOT',2011,1e9),release:'3.3.18',format:'IOT',system:'pxp',units:'Hybrid'}];
 const opts={...options([2011,2024]),state:state};
 const f=C.figure(rows,opts);
 assert.equal(f.data[0].marker.color,f.data[1].marker.color);
 assert.equal(f.data[0].marker.symbol,'circle');assert.equal(f.data[1].marker.symbol,'square');assert.equal(f.data[2].marker.symbol,'square-open');
 assert.equal(f.data[0].marker.color,f.data[2].marker.color);
 assert.ok(f.data.every(t=>/^series-[a-f0-9]+$/.test(t.uid)));
 assert.equal(C.figure(rows,opts).data[0].uid,f.data[0].uid);
});


test('one release with two IOT systems uses scatter and one reference point per year',()=>{
 const rows=[{...row('ixi',2023,1e12),release:'3.11.2',system:'ixi'},
  {...row('ixi',2024,1.1e12),release:'3.11.2',system:'ixi'},
  {...row('pxp',2023,2e12),release:'3.11.2',system:'pxp'},
  {...row('pxp',2024,2.1e12),release:'3.11.2',system:'pxp'},row('World Bank',2024,1.5e12)];
 const f=C.figure(rows,{...options([2023,2024]),state:state});
 assert.ok(f.data.every(t=>t.type==='scatter'));
 assert.equal(f.data[0].marker.symbol,'circle');assert.equal(f.data[1].marker.symbol,'square');
 const ref=f.data[2];assert.equal(ref.marker.symbol,'line-ew');assert.deepEqual(ref.x,[2024]);
 assert.equal(C.figure(rows.filter(r=>r.year===2024),{...options([2024]),state:state}).data.filter(t=>t.type==='bar').length,2);
});

test('formats and units count as distinct readings but multiple countries do not',()=>{
 const base={...row('monetary IOT',2022,1e12),release:'same',units:'Monetary',format:'IOT',system:'pxp'};
 const opts={...options([2021,2022]),state:state};
 const earlier={...base,year:2021};
 assert.equal(C.figure([base,earlier,{...base,country:'ITA'}],opts).data[0].type,'bar');
 const sut={...base,series:'monetary SUT',version:'same SUT',format:'SUT',system:null};
 const hybrid={...base,series:'hybrid IOT',version:'same hybrid IOT',units:'Hybrid'};
 for(const second of [sut,hybrid]){
  const f=C.figure([base,earlier,second],opts);
  assert.ok(f.data.every(t=>t.type==='scatter'));
  assert.equal(f.data[0].marker.color,f.data[1].marker.color);
 }
 const f=C.figure([base,earlier,sut],opts);assert.equal(f.data[1].marker.symbol,'diamond');
});

test('annual hover tolerance adapts to mobile and zoom without borrowing an adjacent year',()=>{
 assert.equal(C.hoverDistance([1995,1996,1997],5),2);
 assert.ok(C.hoverDistance([2020,2022,2024],5)<10);
 assert.equal(C.hoverDistance([2024],20),10);
 assert.equal(C.hoverDistance([1995,1996],50),22);
});


test('comparison colours identify database families rather than releases',()=>{
 const rows=[row('3.11.2 ixi',2024,1e9),row('3.10.2 ixi',2024,2e9),{...row('OECD extended',2024,3e9),database:'OECD'}];
 for(const years of [[2024],[2022,2024]]){
  const f=C.figure(rows,{...options(years),state,databaseFamilies:['EXIOBASE','OECD']});
  assert.equal(f.data[0].marker.color,f.data[1].marker.color);
  assert.notEqual(f.data[0].marker.color,f.data[2].marker.color);
 }
});


test('single-year references retain distinct country totals and legend entries stay at family level',()=>{
 const rows=[row('3.11.2 ixi',2024,1e12,'ITA'),row('3.10.2 ixi',2024,1.1e12,'ITA'),row('3.11.2 ixi',2024,2e12,'FRA'),row('World Bank',2024,1.2e12,'ITA'),row('World Bank',2024,2.1e12,'FRA')];
 const f=C.figure(rows,{...options([2024]),state:state});
 assert.deepEqual(f.layout.shapes.map(s=>s.y0),[1.2,2.1]);
 assert.equal(f.layout.shapes.filter(s=>s.showlegend).length,1);
 assert.equal(f.data.filter(t=>t.showlegend).length,1);
 assert.ok(f.layout.shapes.every(s=>s.legendgroup==='database:World Bank'));
 const many=Array.from({length:12},(_,i)=>row('release-'+i,2024,1e12+i*1e10));
 const large=C.figure([...many,row('World Bank',2024,1.2e12)],{...options([2024]),state:state});
 assert.ok(large.data.filter(t=>t.type==='bar').every(t=>t.orientation==='v'));
 assert.equal(large.layout.shapes.length,1);
});

test('with several countries each single-year reference spans only its own bars',()=>{
 const named=(series,value,country,name)=>({...row(series,2024,value,country),country_name:name});
 const rows=[named('3.11.2 ixi',1e12,'BEL','Belgium'),named('3.10.2 ixi',1.1e12,'BEL','Belgium'),
  named('3.11.2 ixi',2e12,'AUT','Austria'),named('3.10.2 ixi',2.2e12,'AUT','Austria'),
  named('World Bank',1.2e12,'BEL','Belgium'),named('World Bank',2.1e12,'AUT','Austria')];
 const f=C.figure(rows,{...options([2024]),state:state});
 const order=f.layout.xaxis.categoryarray.map(c=>c.split('<br>')[0]);
 const span=name=>{const i=order.flatMap((c,k)=>c===name?[k]:[]);return [Math.min(...i)-.42,Math.max(...i)+.42];};
 const references=f.layout.shapes.filter(s=>s.legendgroup);
 assert.deepEqual(references.map(s=>[s.xref,s.x0,s.x1,s.y0]),[['x',...span('Belgium'),1.2],['x',...span('Austria'),2.1]]);
 assert.equal(references.filter(s=>s.showlegend).length,1);
});

test('single-year bars nest country, release and system groups on the x axis',()=>{
 const bar=(release,system,value,country,name)=>({series:release+' '+system,database:'EXIOBASE',release,system,version:`${release} · ${system}`,
  year:2024,value,country,country_name:name,unit:'current US$',note:''});
 const rows=[];
 for(const [country,name] of [['AUS','Australia'],['AUT','Austria']])for(const release of ['3.10.1','3.11.2'])for(const system of ['ixi','pxp'])rows.push(bar(release,system,1e12,country,name));
 rows.push({...row('World Bank',2024,1.1e12,'AUS'),country_name:'Australia'});
 const f=C.figure(rows,{...options([2024]),state:state});
 assert.deepEqual(f.layout.xaxis.ticktext,Array(4).fill(['ixi','pxp']).flat());
 assert.deepEqual(f.layout.annotations.map(a=>[a.text,a.x]),[['3.10.1',.5],['3.11.2',2.5],['3.10.1',4.5],['3.11.2',6.5],['Australia',1.5],['Austria',5.5]]);
 assert.equal(f.layout.shapes.filter(s=>s.ysizemode==='pixel').length,6);
 assert.deepEqual(f.layout.shapes.filter(s=>s.legendgroup).map(s=>[s.x0,s.x1]),[[-.42,3.42]]);
 const plain=C.figure([bar('3.11.2','ixi',1e12,'AUS','Australia'),bar('3.11.2','pxp',1e12,'AUS','Australia')],{...options([2024]),state:state});
 assert.equal(plain.layout.xaxis.ticktext,undefined);assert.deepEqual(plain.layout.annotations,[]);
});

test('several sector aggregates stack in single-year bars and remain scatter for multiple readings over time',()=>{
 const rows=['A','D'].flatMap(sector=>[
  {...row('3.11.2 ixi',2024,1e12),sector,sector_name:sector+' · name '+sector},
  {...row('3.10.2 ixi',2024,2e12),sector,sector_name:sector+' · name '+sector}]);
 const f=C.figure(rows,{...options([2024]),state:state});
 assert.equal(f.layout.barmode,'stack');
 assert.equal(f.data.length,4);assert.ok(f.data.every(t=>t.type==='bar'));
 assert.deepEqual(f.data.filter(t=>t.showlegend).map(t=>t.name),['A · name A','D · name D']);
 assert.equal(new Set(f.data.map(t=>t.marker.color)).size,2);
 const overTime=C.figure([...rows,...rows.map(r=>({...r,year:2022}))],{...options([2022,2024]),state:state});
 assert.equal(overTime.layout.barmode,'overlay');assert.ok(overTime.data.every(t=>t.type==='scatter'));
});


test('one reading keeps sector breakdowns as annual stacked bars in focus and single-database compare',()=>{
 const sectors=[['A',1e9],['C',2e9]],years=[2021,2022,2023,2024,2025];
 const rows=sectors.flatMap(([sector,value])=>years.map((year,i)=>({...row('060 · SUT',year,value*(i+1)),database:'GLORIA',release:'060',format:'SUT',sector,sector_name:sector+' · name '+sector})));
 {
  const opts={...options(years),state:{metric:'value_added',perCapita:false,families:['GLORIA']}};
  assert.equal(C.usesBars(rows,opts.state,years),true);
  const f=C.figure(rows,opts);
  assert.equal(f.layout.barmode,'stack');assert.equal(f.data.length,2);
  assert.ok(f.data.every(t=>t.type==='bar'));
  assert.deepEqual(f.data.map(t=>t.x),[years,years]);
  assert.deepEqual(f.data.map(t=>t.y),[[1,2,3,4,5],[2,4,6,8,10]]);
  assert.deepEqual(f.data.map(t=>t.name),['A · name A','C · name C']);
  assert.equal(new Set(f.data.map(t=>t.offsetgroup)).size,1);
  const countries=C.figure([...rows,...rows.map(r=>({...r,country:'ITA',country_name:'Italy'}))],opts);
  assert.ok(countries.data.every(t=>t.type==='bar'));
  assert.equal(new Set(countries.data.map(t=>t.offsetgroup)).size,2);
 }
 const extra={...rows[0],database:'EXIOBASE',series:'3.11.2 · ixi',version:'3.11.2 · ixi'};
 const comparison={...options(years),state:{metric:'value_added',perCapita:false,families:['GLORIA','EXIOBASE']}};
 assert.equal(C.usesBars([...rows,extra],comparison.state,years),false);
 assert.ok(C.figure([...rows,extra],comparison).data.every(t=>t.type==='scatter'));
 const older=rows.map(r=>({...r,series:'059 · SUT',version:'059 · SUT',release:'059'}));
 const sameFamily={...comparison,state:{...comparison.state,families:['GLORIA']}};
 assert.equal(C.usesBars([...rows,...older],sameFamily.state,years),false);
 assert.ok(C.figure([...rows,...older],sameFamily).data.every(t=>t.type==='scatter'));
});


const comparisonBar=(database,release,variant='',country='CHN',country_name='China')=>({
 series:JSON.stringify([database,release,variant]), database,release,
 version:release+(variant?' · '+variant:''),year:2024,value:1e12,country,country_name,unit:'current US$',note:''
});
const mixedBars=()=>[
 comparisonBar('ADB','62 economies'),comparisonBar('ADB','72 economies'),
 ...['3.10.1','3.10.2','3.11.2'].flatMap(release=>['ixi','pxp'].map(system=>comparisonBar('EXIOBASE',release,system))),
 comparisonBar('OECD','Extended'),comparisonBar('OECD','Regular'),
 {...row('World Bank',2024,1.2e12,'CHN'),country_name:'China'}
];

test('axis branches stop at each family’s useful depth without duplicate versions',()=>{
 const rows=mixedBars(), before=structuredClone(rows);
 const f=C.figure(rows,{...options([2024]),state});
 assert.deepEqual(f.layout.xaxis.ticktext,['','','ixi','pxp','ixi','pxp','ixi','pxp','','']);
 assert.deepEqual(f.layout.annotations.map(a=>[a.text,a.x]),[
  ['62 economies',0],['72 economies',1],['3.10.1',2.5],['3.10.2',4.5],['3.11.2',6.5],
  ['Extended',8],['Regular',9],['ADB',.5],['EXIOBASE',4.5],['OECD',8.5]
 ]);
 assert.deepEqual(f.layout.shapes.filter(s=>s.legendgroup).map(s=>[s.xref,s.x0,s.x1]),[['paper',0,1]]);
 assert.deepEqual(f.data.filter(t=>t.type==='bar').flatMap(t=>t.y),Array(10).fill(1));
 assert.deepEqual(rows,before);
});

test('a single system merges with its release even alongside families without systems',()=>{
 const rows=mixedBars().filter(r=>!r.version.endsWith(' · pxp'));
 const f=C.figure(rows,{...options([2024]),state});
 assert.deepEqual(f.layout.xaxis.ticktext,['62 economies','72 economies','3.10.1 ixi','3.10.2 ixi','3.11.2 ixi','Extended','Regular']);
 assert.deepEqual(f.layout.annotations.map(a=>[a.text,a.x]),[['ADB',.5],['EXIOBASE',3],['OECD',5.5]]);
 assert.equal(f.layout.shapes.filter(s=>s.ysizemode==='pixel').length,3);
});

test('local branch depth also handles partial releases and table/unit variants across countries',()=>{
 const rows=['CHN','ITA'].flatMap(country=>[
  comparisonBar('ADB','72 economies','',country,country),
  comparisonBar('EXIOBASE','3.11.2','ixi',country,country),
  comparisonBar('EXIOBASE','3.11.2','pxp',country,country),
  comparisonBar('EXIOBASE','3.10.1','ixi',country,country),
  comparisonBar('EXIOBASE','3.8.2','hybrid IOT',country,country),
  comparisonBar('EXIOBASE','3.8.2','hybrid SUT',country,country)
 ]);
 rows.push({...row('World Bank',2024,1.2e12,'CHN'),country_name:'CHN'});
 const f=C.figure(rows,{...options([2024]),state,width:390});
 assert.deepEqual(f.layout.xaxis.ticktext,Array(2).fill(['','ixi','pxp','','hybrid IOT','hybrid SUT']).flat());
 assert.deepEqual(f.layout.annotations.filter(a=>a.text==='3.10.1 ixi').map(a=>a.x),[3,9]);
 assert.deepEqual(f.layout.annotations.filter(a=>a.text==='72 economies').map(a=>a.x),[0,6]);
 assert.deepEqual(f.layout.annotations.filter(a=>['CHN','ITA'].includes(a.text)).map(a=>[a.text,a.x]),[['CHN',2.5],['ITA',8.5]]);
 assert.equal(f.layout.xaxis.tickangle,-90);
 assert.deepEqual(f.layout.shapes.filter(s=>s.legendgroup).map(s=>[s.x0,s.x1]),[[-.42,5.42]]);
});


test('scatter markers adapt to distinct observed years, leaving references subtle and values unchanged',()=>{
 const years=[2018,2020,2022,2024,2025];
 const rows=years.flatMap(y=>[row('3.11.2 ixi',y,10e12),row('3.10.2 ixi',y,11e12),row('World Bank',y,12e12)]);
 const before=structuredClone(rows), f=C.figure(rows,options(years));
 assert.ok(f.data[0].marker.size>13);
 assert.ok(f.data.find(t=>t.name.startsWith('World Bank')).marker.size<f.data[0].marker.size);
 assert.deepEqual(rows,before);
 const denseYears=Array.from({length:30},(_,i)=>1995+i);
 const dense=C.figure(denseYears.flatMap(y=>[row('3.11.2 ixi',y,10e12),row('3.10.2 ixi',y,11e12)]),options(denseYears));
 assert.equal(dense.data[0].marker.size,7.5);
 assert.ok(C.figure(rows,options(denseYears)).data[0].marker.size>13);
 assert.equal(C.scatterMarkerSize(0),15);
});

test('one database family encodes systems and hybrid units; several families keep family colours',()=>{
 const rows=[{...row('3.11.2 ixi',2022,1e9),release:'3.11.2',system:'ixi',units:'Monetary'},{...row('3.11.2 ixi',2024,1.1e9),release:'3.11.2',system:'ixi',units:'Monetary'},
  {...row('3.3.18 hybrid IOT',2022,1e9),release:'3.3.18',format:'IOT',system:'pxp',units:'Hybrid'},{...row('3.3.18 hybrid IOT',2024,1.2e9),release:'3.3.18',format:'IOT',system:'pxp',units:'Hybrid'}];
 const one=C.figure(rows,options([2022,2024]));
 assert.deepEqual(one.data.map(t=>t.marker.symbol),['circle','square-open']);
 const oecd=[{...row('OECD extended',2022,3e9),database:'OECD'},{...row('OECD extended',2024,3e9),database:'OECD'}];
 const two=C.figure([...rows,...oecd],{...options([2022,2024]),databaseFamilies:['EXIOBASE','OECD']});
 assert.ok(two.data.every(t=>!t.marker.symbol.endsWith('-open')));
 assert.notEqual(two.data.find(t=>t.name.startsWith('EXIOBASE')).marker.color,two.data.find(t=>t.name.startsWith('OECD')).marker.color);
});
