// Reviewed native-to-reference concordances, with every intermediate route.
import fs from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const doc=path.resolve(process.env.CLASSIFICATION_DOC_ROOT||path.join(path.dirname(fileURLToPath(import.meta.url)),'..'));
const root=path.join(doc,'source/_static/data/economy');
const data=JSON.parse(await fs.readFile(path.join(root,'sectoral-scope.json'),'utf8'));
const audit=JSON.parse(await fs.readFile(path.join(root,'classification-audit.json'),'utf8'));
const notices=JSON.parse(await fs.readFile(path.join(root,'download-metadata.json'),'utf8'));
const current=Object.entries(data.columns).flatMap(([kind,columns])=>columns.map(c=>({kind,label:c.label,native:c.native.length,linked:c.native.filter(n=>Object.keys(n.links).length).length})));
audit.inventories=current;
const output=process.env.CLASSIFICATION_XLSX_OUTPUT||path.join(root,'classification-concordances.xlsx');
const previews=process.env.CLASSIFICATION_PREVIEWS||'/private/tmp/concordance-review/workbook-previews';
const wb=Workbook.create(),sheets={};
const inventories={};
const names=['Overview','Native categories','Reference matches','Routes','Intermediate links','Reference hierarchy','Sources'];
for(const name of names)sheets[name]=wb.worksheets.add(name);
const pad=(n)=>String(n).padStart(6,'0'),safe=v=>typeof v==='string'&&v.startsWith('=')?"'"+v:v??'';
function table(name,headers,rows,widths,start=1){
 console.log('Writing '+name+': '+rows.length+' rows');
 inventories[name]={headers,rows,start};
 // Author and render the complete layout in Artifact Tool. Its monolithic
 // XLSX export twice exhausted an 8 GiB heap on this >1m-cell inventory.
 // Native OOXML streaming below extends the authored tables with typed rows.
 const sample=rows.slice(0,50);
 const sh=sheets[name],end=start+sample.length;
 sh.showGridLines=false;
 // Keep formatting sparse. Expanding identical cell styles across >1m
 // cells makes the exporter exhaust memory; strings remain typed strings.
 const preview=sh.getRangeByIndexes(start-1,0,sample.length+1,headers.length);
 preview.format.font={name:'Arial',size:10,color:'#302820'};
 preview.format.rowHeight=22;preview.format.verticalAlignment='center';preview.format.wrapText=false;
 preview.setNumberFormat('@');
 sh.getRangeByIndexes(start-1,0,1,headers.length).values=[headers];
 for(let at=0;at<sample.length;at+=4000){
  const block=sample.slice(at,at+4000).map(r=>r.map(safe));
  sh.getRangeByIndexes(start+at,0,block.length,headers.length).values=block;
 }
 const head=sh.getRangeByIndexes(start-1,0,1,headers.length);
 head.format={fill:'#302820',font:{name:'Arial',size:10,color:'#FFFFFF',bold:true},rowHeight:38,wrapText:true,horizontalAlignment:'center',verticalAlignment:'center'};
 for(let c=0;c<headers.length;c++)sh.getRangeByIndexes(start-1,c,1,1).format.columnWidth=widths[c]||24;
 sh.freezePanes.freezeRows(start);
 if(sample.length)sh.tables.add(`A${start}:${String.fromCharCode(64+headers.length)}${end}`,true,name.replaceAll(' ','')+'Table');
 console.log('Written '+name);
 return sh;
}
const nativeRows=[],matchRows=[],routeRows=[],refRows=[],used=new Set();
let count=0,routeCount=0;
for(const [kind,columns] of Object.entries(data.columns)){
 const ref=data.references[kind],nodes=new Map(ref.nodes.map(n=>[n.code,n]));
 for(const n of ref.nodes)refRows.push([ref.label,n.code,n.name,n.level,n.parent||'',n.section]);
 for(const col of columns)for(const native of col.native){
  const key=`${col.id}:${native.code||native.name}`;
  nativeRows.push([key,kind,col.label,native.code,native.name,Object.keys(native.links).length,
   native.mapping_origin||native.link_defaults?.mapping_origin||'',native.review_note||native.link_defaults?.review_note||'',
   native.native_identity?.parent||native.reviewed_parent||'',native.production_review?.basis||'']);
  for(const [code,own] of Object.entries(native.links)){
   const link={...native.link_defaults,...own},id='M'+pad(++count);
   const routes=[link,...(link.alternatives||[]),...(link.alternative_steps||[]).map(steps=>({steps}))];
   matchRows.push([id,kind,col.label,native.code,native.name,ref.label,code,nodes.get(code).name,
    link.status,link.relation||'',link.exclusive_reference===true,routes.length,key]);
   for(const route of routes){
    const rid='R'+pad(++routeCount);
    for(const sid of route.steps)used.add(sid);
    routeRows.push([rid,id,route.steps.join(' > ')]);
   }
  }
 }
}
const steps=[...used].sort().map(id=>{
 const s=data.route_steps[id];
 return [id,s.source_left.join(':'),data.node_names[s.source_left.join(':')]||'',s.source_right.join(':'),
  data.node_names[s.source_right.join(':')]||'',s.relation,s.source,s.location,
  String(s.left_part??''),String(s.right_part??''),s.part_flags_origin||'',s.note||''];
});
const sources=Object.entries(data.sources).sort().map(([id,s])=>[id,s.title||s.filename||id,s.publisher||'',notices.sources[id]?.source_url||s.url,s.filename||'',s.sha256||'',s.role||s.note||'',notices.sources[id]?.license||'',notices.sources[id]?.license_url||'',notices.sources[id]?.usage||'']);
const overview=table('Overview',['Dimension','Database','Reference','Native categories','With fine links','Unverified / pending'],
 audit.inventories.map(n=>[n.kind,n.label,data.references[n.kind].label,n.native,n.linked,null]),[15,42,22,22,20,23],5);
overview.tabColor='#F0783C';
overview.getRange('A2:F3').format={font:{name:'Arial',size:10,color:'#302820'},rowHeight:22};
overview.getRange('A2').values=[['Classification concordances']];overview.getRange('A2').format.font={name:'Arial',size:15,bold:true,color:'#302820'};overview.getRange('A2:F2').format.rowHeight=28;
overview.getRange('A3').values=[['Review: '+audit.as_of+' · intermediate routes and source locations are retained']];overview.getRange('A3').format.font={name:'Arial',size:10,color:'#6D6052'};
overview.getRange(`D6:F${5+audit.inventories.length}`).setNumberFormat('#,##0');
overview.getRange(`F6:F${5+audit.inventories.length}`).formulas=audit.inventories.map((_,i)=>[`=D${i+6}-E${i+6}`]);
let row=8+audit.inventories.length;
overview.getRange(`A${row}`).values=[['How to trace a correspondence']];overview.getRange(`A${row}`).format.font={name:'Arial',size:10,bold:true};
const notes=[
 'Reference matches: find a native category or NACE / CPA code. A partial status is a qualified scope, not an exact equivalence.',
 'Routes: filter Match ID to obtain every primary and alternative route. Follow the ordered step IDs in Intermediate links.',
 'Intermediate links: each edge retains direction, relation, partial flags, source ID and the source row / page / cell.',
 'Sources: source IDs resolve to URLs, checksums and reuse terms. Native parents are lineage context, not membership evidence.',
 'Rights: this lookup combines sources with different terms. Attribute MARIO / nxbase and the upstream sources listed for each route; no universal data licence is assigned.',
 'Only classification facts and reviewed links are included. Economic observations, emission factors and licensed GTAP numerical data are excluded.',
 'Activities and commodities are separate native sets. CEDA and GTAP have activity inventories only; intermediate product classifications do not create a native commodity set.',
 ...audit.notes,
];
for(const note of notes){row++;overview.getRange(`A${row}`).values=[[note]];overview.getRange(`A${row}:F${row}`).merge();overview.getRange(`A${row}:F${row}`).format={font:{name:'Arial',size:10,color:'#302820'},wrapText:true,rowHeight:38,verticalAlignment:'center'};}
table('Native categories',['Native key','Dimension','Database','Native code','Native label','Reference links','Origin','Review note','Workbook parent (context)','Production constraint'],nativeRows,[48,15,38,20,72,18,30,90,70,90]);
table('Reference matches',['Match ID','Dimension','Database','Native code','Native label','Reference','Reference code','Reference label','Status','Relationship','Exclusive leaf','Routes','Native key'],matchRows,[15,15,38,20,65,22,20,70,18,60,18,12,48]);
table('Routes',['Route ID','Match ID','Ordered intermediate step IDs'],routeRows,[15,15,125]);
table('Intermediate links',['Step ID','From','From label','To','To label','Relationship','Source ID','Source location','Left part','Right part','Flag origin','Source note'],steps,[20,32,65,32,65,60,16,65,15,15,60,100]);
table('Reference hierarchy',['Classification','Code','Label','Level','Parent','Section'],refRows,[24,20,100,12,20,12]);
table('Sources',['Source ID','Title','Publisher','Source URL','Filename','SHA-256','Role / precision','Source terms','Terms URL','Reuse note'],sources,[16,65,25,110,65,75,100,46,85,90]);
for(const [name,range] of [['Native categories','F2:F'+Math.min(nativeRows.length+1,51)],['Reference matches','L2:L'+Math.min(matchRows.length+1,51)],['Reference hierarchy','D2:D'+Math.min(refRows.length+1,51)]])sheets[name].getRange(range).setNumberFormat('#,##0');
// All table bodies use the same font and 22-point rows. Avoid preview-only
// autofit: its first ten rows otherwise leak different heights into the export.
wb.recalculate();
await fs.mkdir(previews,{recursive:true});
for(const name of names){
 const range=name==='Overview'?'A1:F12':name==='Routes'?'A1:C10':name==='Reference hierarchy'?'A1:D10':name==='Sources'?'A1:C10':'A1:E10';
 const image=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(path.join(previews,name.replaceAll(' ','-')+'.png'),new Uint8Array(await image.arrayBuffer()));
 console.log('Rendered '+name);
}
console.log((await wb.inspect({kind:'region',sheetId:'Overview',range:'D5:F10',maxChars:1200,tableMaxRows:6,tableMaxCols:3})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
const temporary=await fs.mkdtemp(path.join(tmpdir(),'mario-concordance-export-'));
try{
 const template=path.join(temporary,'layout.xlsx'),payload=path.join(temporary,'rows.json');
 const file=await SpreadsheetFile.exportXlsx(wb);await file.save(template);
 await fs.writeFile(payload,JSON.stringify(inventories));
 const run=promisify(execFile);
 const result=await run(process.env.CLASSIFICATION_PYTHON||'python3',[
  path.join(doc,'scripts/stream_classification_rows.py'),template,payload,output
 ],{maxBuffer:1024*1024});
 console.log(result.stdout.trim());
}finally{await fs.rm(temporary,{recursive:true,force:true});}
console.log(JSON.stringify({output,native:nativeRows.length,matches:matchRows.length,routes:routeRows.length,steps:steps.length,references:refRows.length,sources:sources.length}));
