import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [indexPath,mappingInput,mappingOutput]=process.argv.slice(2);
if(!indexPath)throw new Error('Pass catalogue-build.json');
const jobs=JSON.parse(await fs.readFile(indexPath,'utf8'));
function yearPeriods(years){
 const out=[];let first=years[0],last=first;
 for(const year of [...years.slice(1),null]){
  if(year!==null&&year===last+1){last=year;continue;}
  out.push(first===last?String(first):`${first}–${last}`);first=last=year;
 }
 return out.join(', ');
}
function table(sheet,rows,widths,name){
 const end=rows.length+7,final=String.fromCharCode(64+rows[0].length);
 sheet.showGridLines=false;sheet.tabColor='#245b6a';
 sheet.getRange(`A8:${final}${end}`).values=rows;
 sheet.getRange(`A8:${final}${end}`).format={font:{name:'Arial',size:10,color:'#202c38'},rowHeight:24,verticalAlignment:'center'};
 widths.forEach((width,i)=>sheet.getRange(`${String.fromCharCode(65+i)}8:${String.fromCharCode(65+i)}${end}`).format.columnWidth=width);
 sheet.getRange(`A8:${final}8`).format={fill:'#245b6a',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',rowHeight:36,wrapText:true};
 sheet.tables.add(`A8:${final}${end}`,true,name);sheet.freezePanes.freezeRows(8);
 return end;
}
function intro(sheet,title,notes){
 sheet.getRange('A2').values=[[title]];
 sheet.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#202c38'};
 notes.forEach((text,i)=>sheet.getRange(`A${i+3}`).values=[[text]]);
 sheet.getRange('A3:J6').format={font:{name:'Arial',size:10,color:'#566675'},rowHeight:20};
}
async function verify(wb,folder,sheets){
 wb.recalculate();
 console.log((await wb.inspect({kind:'region',sheetId:sheets[0],range:'A2:G12',maxChars:1000,tableMaxRows:4,tableMaxCols:7})).ndjson);
 console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:10},maxChars:400})).ndjson);
 await fs.mkdir(folder,{recursive:true});
 for(const name of sheets){
  const preview=await wb.render({sheetName:name,range:name==='Regional memberships'?'A1:C17':name==='Readings'?'A1:J17':'A1:G17',scale:1,format:'png'});
  await fs.writeFile(path.join(folder,name.replaceAll(' ','-')+'.png'),new Uint8Array(await preview.arrayBuffer()));
 }
}
for(const item of jobs){
 const p=JSON.parse(await fs.readFile(item.profile,'utf8')),wb=Workbook.create();
 const units=new Map(p.units.map(u=>[u.set+'|'+u.index[0],u.values.unit]));
 const geography=new Map(p.geography.regions.map(r=>[r.label,r]));
 const ee=p.counts['Satellite account']>0;
 const s=wb.worksheets.add('Sets');
 intro(s,`ADB ${p.release}: parsed native sets`,[
  `Verified years: ${yearPeriods(p.years)}. These readings have identical parsed sets and units.`,
  Object.entries(p.counts).map(([set,count])=>`${set}: ${count}`).join('; '),
  'Source: '+item.source_url,
  `Version counts individual economies; the ${p.counts.Region} parsed regions also include ${p.release==='71 economies'?'RoLAC and RoW':'RoW'}. ${ee?'Air-emissions accounts include industry and direct final demand.':'No compatible same-year air-emissions extension.'}`
 ]);
 const rows=[['Set','Position','Native label','Native unit','Country / territory','ISO3','Representation']];
 for(const [set,labels] of Object.entries(p.sets)){
  const excluded=p.set_flags?.[set]?.placeholder_labels||[];
  labels.filter(label=>!excluded.includes(label)).forEach((label,i)=>{
   const region=set==='Region'?geography.get(label):null;
   rows.push([set,i+1,label,units.get(set+'|'+label)||'',region?.name||'',region?.iso3||'',region?.kind||'']);
  });
 }
 const end=table(s,rows,[24,10,70,42,36,10,20],'SetsTable');
 s.getRange(`B9:B${end}`).setNumberFormat('0');s.getRange(`C9:G${end}`).setNumberFormat('@');
 s.getRange(`C9:E${end}`).format.wrapText=true;s.getRange(`C9:E${end}`).format.autofitRows();s.freezePanes.freezeColumns(2);
 const r=wb.worksheets.add('Readings');
 intro(r,`ADB ${p.release}: verified local files`,[
  'Full MARIO MRIO parsing, calc_all=False. GDP and value added reconcile to original country totals.',
  ee?'GHG | Total by substance: published Gg CO2eq, AR5 GWP100, SEEA residence basis, excluding LULUCF. No recharacterisation.':'Economic accounts: nominal million USD. No verified GHG values for these readings.',
  'Source: '+item.source_url,
  ee&&p.release==='62 economies'?'Ten extra economies from the 72-economy emissions extension are folded into RoW; E and EY world totals are conserved.':'SHA-256 identifies each unchanged source workbook. Shared sets do not imply identical indicator values.'
 ]);
 const data=[['Year','Economic workbook','Parsed regions','Industries','Final-demand categories','Satellite accounts','Economic SHA-256','Air-emissions workbook','Air-emissions SHA-256','Economies folded into RoW'],
  ...p.readings.map(x=>[x.year,x.filename,x.counts.Region,x.counts.Sector,x.counts['Consumption category'],x.counts['Satellite account'],x.sha256,x.emissions?.filename||'',x.emissions?.sha256||'',(x.emissions?.regional_remap_to_RoW||[]).join(', ')])];
 const last=table(r,data,[10,58,17,14,24,21,72,46,72,60],'ReadingsTable');
 r.getRange(`A9:A${last}`).setNumberFormat('0');r.getRange(`C9:F${last}`).setNumberFormat('#,##0');r.getRange(`G9:J${last}`).setNumberFormat('@');
 r.getRange(`B9:B${last}`).format.wrapText=true;r.getRange(`H9:J${last}`).format.wrapText=true;r.getRange(`A9:J${last}`).format.autofitRows();
 const m=wb.worksheets.add('Regional memberships');
 intro(m,`ADB ${p.release}: regional set membership`,[
  'Native industry and final-demand labels are listed once for each parsed region.',
  `Each of the ${p.counts.Region} regions has 35 industries and five final-demand categories.`,
  'Source: '+item.source_url
 ]);
 const mlast=table(m,[['Region','Set','Native label'],...p.region_items.map(x=>[x.region,x.set,x.label])],[18,30,70],'MembershipTable');
 m.getRange(`C9:C${mlast}`).format.wrapText=true;m.getRange(`C9:C${mlast}`).format.autofitRows();
 await verify(wb,path.dirname(item.workbook),['Sets','Readings','Regional memberships']);
 await(await SpreadsheetFile.exportXlsx(wb)).save(item.workbook);
 console.log('Exported',item.id,rows.length-1,'labels,',p.readings.length,'source files.');
}
if(mappingInput&&mappingOutput){
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(mappingInput)),s=wb.worksheets.getItem('ADB');
 console.log((await wb.inspect({kind:'region',sheetId:s.name,range:'A2:E12',maxChars:1000})).ndjson);
 const before=await wb.render({sheetName:s.name,range:'A1:E17',scale:1,format:'png'});
 await fs.writeFile(path.join(path.dirname(mappingOutput),'mapping-before.png'),new Uint8Array(await before.arrayBuffer()));
 const mapping=JSON.parse(await fs.readFile(path.join(path.dirname(indexPath),'sections-ready.json'),'utf8'));
 const entries=Object.values(mapping.mappings).find(m=>m.family==='ADB').entries;
 const codes=new Map(entries.map(e=>[e.native_label,e.native_code]));
 const labels=s.getRange('B9:B43').values.flat();
 if(labels.length!==35||labels.some(label=>!codes.has(label)))throw new Error('Existing ADB mapping labels changed');
 s.getRange('A9:A43').values=labels.map(label=>[codes.get(label)]);s.getRange('A9:A43').setNumberFormat('@');
 s.getRange('A2').values=[['ADB 62 / 71 / 72 / 74 economies: NACE Rev. 1.1 (A+B combined) sections']];
 s.getRange('A3').values=[['All 35 native industries match across these versions. Codes c1–c35 verified in every original workbook; sum each category once.']];
 wb.recalculate();
 console.log((await wb.inspect({kind:'region',sheetId:s.name,range:'A2:E12',maxChars:1500})).ndjson);
 console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:10},maxChars:400})).ndjson);
 const after=await wb.render({sheetName:s.name,range:'A1:E17',scale:1,format:'png'});
 await fs.writeFile(path.join(path.dirname(mappingOutput),'mapping-after.png'),new Uint8Array(await after.arrayBuffer()));
 await(await SpreadsheetFile.exportXlsx(wb)).save(mappingOutput);
 console.log('Updated native ADB codes and version taxonomy; other mappings retained.');
}
