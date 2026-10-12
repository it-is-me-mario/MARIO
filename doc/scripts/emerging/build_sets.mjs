import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [indexPath]=process.argv.slice(2);
const jobs=JSON.parse(await fs.readFile(indexPath,'utf8'));
function periods(years){
 const parts=[];let first=years[0],last=first;
 for(const y of [...years.slice(1),null]){if(y!==null&&y===last+1){last=y;continue;}parts.push(first===last?String(first):`${first}–${last}`);first=last=y;}
 return parts.join(', ');
}
function table(s,rows,widths,name){
 const end=rows.length+7,last=String.fromCharCode(64+rows[0].length);
 s.showGridLines=false;s.tabColor='#245b6a';s.getRange(`A8:${last}${end}`).values=rows;
 s.getRange(`A8:${last}${end}`).format={font:{name:'Arial',size:10,color:'#202c38'},rowHeight:24,verticalAlignment:'center'};
 widths.forEach((width,i)=>s.getRange(`${String.fromCharCode(65+i)}8:${String.fromCharCode(65+i)}${end}`).format.columnWidth=width);
 s.getRange(`A8:${last}8`).format={fill:'#245b6a',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',rowHeight:36,wrapText:true};
 s.tables.add(`A8:${last}${end}`,true,name);s.freezePanes.freezeRows(8);
 return end;
}
function intro(s,title,notes){
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#202c38'};
 notes.forEach((text,i)=>s.getRange(`A${i+3}`).values=[[text]]);
 s.getRange('A3:J6').format={font:{name:'Arial',size:10,color:'#566675'},rowHeight:20};
}
for(const item of jobs){
 const p=JSON.parse(await fs.readFile(item.profile,'utf8')),wb=Workbook.create();
 const name=p.release==='E'?'EMERGING-E':`EMERGING ${p.release}`;
 const units=new Map(p.units.map(u=>[u.set+'|'+u.index[0],u.values.unit]));
 const regions=new Map(p.geography.regions.map(r=>[r.label,r]));
 const s=wb.worksheets.add('Sets');
 intro(s,`${name}: native sets`,[
  `Verified years: ${periods(p.years)}. These readings have identical parsed sets and units.`,
  Object.entries(p.counts).map(([set,n])=>`${set}: ${n}`).join('; '),
  'Source: '+item.source_url,
  p.counts['Satellite account']?'Seven fuel-specific fossil CO2 accounts. Direct final-demand emissions are not supplied.':'Economic accounts only. The MARIO satellite placeholder is excluded.'
 ]);
 const rows=[['Set','Position','Native label','Native unit','Country / territory','ISO3','Representation']];
 for(const [set,labels] of Object.entries(p.sets)){
  const omitted=p.set_flags?.[set]?.placeholder_labels||[];
  labels.filter(label=>!omitted.includes(label)).forEach((label,i)=>{
   const region=set==='Region'?regions.get(label):null;
   rows.push([set,i+1,label,units.get(set+'|'+label)||'',region?.name||'',region?.iso3||'',region?.kind||'']);
  });
 }
 const end=table(s,rows,[24,10,86,30,40,10,22],'SetsTable');
 s.getRange(`B9:B${end}`).setNumberFormat('0');s.getRange(`C9:G${end}`).setNumberFormat('@');
 s.getRange(`C9:G${end}`).format.wrapText=true;s.getRange(`C9:G${end}`).format.autofitRows();s.freezePanes.freezeColumns(2);
 const r=wb.worksheets.add('Readings');
 intro(r,`${name}: verified local readings`,[
  p.counts['Satellite account']?'Full MARIO parsing. Value added and companion CO2 cells reconcile to the original MATLAB inputs.':'Full MARIO parsing. Value added reconciles to the original MATLAB input; no CO2 companion is supplied.',
  'Economic values: current million USD. CO2 fuel accounts do not constitute a complete GHG inventory.',
  'Source: '+item.source_url,
  'SHA-256 identifies the unchanged input files. Shared sets do not imply identical numeric values.'
 ]);
 const data=[['Year','Economic bundle','Regions','Sectors','Final-demand categories','Factors','Satellite accounts','Economic SHA-256','CO2 bundle','CO2 SHA-256'],
 ...p.readings.map(x=>[x.year,x.filename,x.counts.Region,x.counts.Sector,x.counts['Consumption category'],x.counts['Factor of production'],x.counts['Satellite account'],x.sha256,x.emissions?.filename||'',x.emissions?.sha256||''])];
 const last=table(r,data,[10,48,12,12,22,12,20,76,36,76],'ReadingsTable');
 r.getRange(`A9:A${last}`).setNumberFormat('0');r.getRange(`C9:G${last}`).setNumberFormat('#,##0');r.getRange(`H9:J${last}`).setNumberFormat('@');
 r.getRange(`A9:J${last}`).format.wrapText=true;r.getRange(`A9:J${last}`).format.autofitRows();r.freezePanes.freezeColumns(2);
 const m=wb.worksheets.add('Regional memberships');
 intro(m,`${name}: regional memberships`,[
  'Native product / service and final-demand labels are listed for each parsed region.',
  `${p.counts.Region} native regions, ${p.counts.Sector} sectors and ${p.counts['Consumption category']} final-demand categories per region.`,
  'Source: '+item.source_url,
  'ANT and SER are retained as historical groups. TMP maps to TLS. No current aggregate membership is inferred.'
 ]);
 const ml=table(m,[['Region','Set','Native label'],...p.region_items.map(x=>[x.region,x.set,x.label])],[18,30,90],'MembershipsTable');
 m.getRange(`A9:C${ml}`).setNumberFormat('@');m.getRange(`C9:C${ml}`).format.wrapText=true;m.freezePanes.freezeColumns(2);
 wb.recalculate();
 const report=await wb.inspect({kind:'region',sheetId:'Sets',range:'A8:G14',tableMaxRows:7,tableMaxCols:7,maxChars:1600});
 await fs.writeFile(path.join(path.dirname(item.workbook),'inspect.ndjson'),report.ndjson);
 const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:10},maxChars:400});
 console.log(item.id,errors.ndjson);
 for(const sheetName of ['Sets','Readings','Regional memberships']){
  const image=await wb.render({sheetName,range:sheetName==='Regional memberships'?'A1:C17':sheetName==='Readings'?'A1:J17':'A1:G17',scale:1,format:'png'});
  await fs.writeFile(path.join(path.dirname(item.workbook),sheetName.replaceAll(' ','-')+'.png'),new Uint8Array(await image.arrayBuffer()));
 }
 await(await SpreadsheetFile.exportXlsx(wb)).save(item.workbook);
 console.log('Exported',item.id,rows.length-1,'native labels;',p.readings.length,'readings;',p.region_items.length,'memberships.');
}
