import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile,FileBlob} from '@oai/artifact-tool';
const stage=process.argv[2];
if(!stage)throw new Error('Usage: node build_sets.mjs /path/to/stage');
const dir=path.join(stage,'gloria-060-2024-sut');
const input=process.env.MARIO_GLORIA_SETS_INPUT;
const inspectOnly=process.argv.includes('--inspect');
const p=JSON.parse(await fs.readFile(path.join(dir,'profile.json'),'utf8'));
const units=new Map(p.units.map(u=>[u.set+'|'+u.index[0],u.values.unit]));
const geography=new Map(p.geography.regions.map(r=>[r.label,r]));
const rows=[['Set','Position','Native label (unchanged)','Native unit','Country / territory','ISO3','Region type']];
for(const [name,labels] of Object.entries(p.sets)) {
 const omitted=p.set_flags?.[name]?.placeholder_labels||[];
 labels.filter(label=>!omitted.includes(label)).forEach((label,i)=>{
  const r=name==='Region'?geography.get(label):null;
  rows.push([name,i+1,label,units.get(name+'|'+label)||'',r?.name||'',r?.iso3||'',r?.kind||'']);
 });
}
const w=input?await SpreadsheetFile.importXlsx(await FileBlob.load(input)):Workbook.create();
const s=input?w.worksheets.getItem('Sets'):w.worksheets.add('Sets');
const before=input?JSON.stringify(s.getRange(`A8:G${rows.length+7}`).values):null;
if(inspectOnly){
 const preview=await w.render({sheetName:'Sets',range:'A1:G17',scale:1,format:'png'});
 await fs.writeFile(path.join(dir,'before.png'),new Uint8Array(await preview.arrayBuffer()));
 console.log((await w.inspect({kind:'table',range:'Sets!A8:G12',include:'values',tableMaxRows:5,tableMaxCols:7,maxChars:1000})).ndjson);
 process.exit(0);
}
if(!input){
s.showGridLines=false;
s.getRange('A2').values=[['GLORIA v060 / 2024 native sets']];
s.getRange('A2:G2').format={font:{name:'Arial',size:14,bold:true,color:'#202c38'},rowHeight:25,borders:{bottom:{style:'thin',color:'#245b6a'}}};
s.getRange('A3').values=[[Object.entries(p.counts).map(([k,v])=>k+': '+v).join('; ')]];
s.getRange('A4').values=[['Source: University of Sydney / UNEP International Resource Panel. https://ielab.info/resources/gloria']];
s.getRange('A5').values=[['CC BY-NC 3.0 Australia. '+p.license_url]];
s.getRange('A6').values=[['Extracted with MARIO. Native labels and units retained. Economic vintage January 2026; satellites April 2024.']];
s.getRange('A3:G6').format={font:{name:'Arial',size:10,color:'#566675'},rowHeight:20};
const last=rows.length+7;
s.getRange(`A8:G${last}`).values=rows;
s.getRange(`A8:G${last}`).format={font:{name:'Arial',size:10,color:'#202c38'},rowHeight:23,verticalAlignment:'center'};
const widths=[24,10,96,22,32,10,18];
'ABCDEFG'.split('').forEach((c,i)=>s.getRange(`${c}8:${c}${last}`).format.columnWidth=widths[i]);
s.getRange(`A9:A${last}`).setNumberFormat('@');s.getRange(`B9:B${last}`).setNumberFormat('0');s.getRange(`C9:G${last}`).setNumberFormat('@');
s.getRange(`C9:C${last}`).format.wrapText=true;s.getRange(`C9:C${last}`).format.autofitRows();
s.tables.add(`A8:G${last}`,true,'NativeSets');
s.getRange('A8:G8').format={fill:'#245b6a',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',rowHeight:30};
s.freezePanes.freezeRows(8);s.freezePanes.freezeColumns(2);
}
const years=p.years||[p.year];
const yearLabel=years.length>1&&years.every((year,index)=>year===years[0]+index)?`${years[0]}–${years.at(-1)}`:years.join(', ');
s.getRange('A2').values=[['GLORIA v060 / '+yearLabel+' native sets']];
s.getRange('A6').values=[['Extracted with MARIO. Native labels and units retained and verified across these years. Source archive vintages accompany each reading.']];
if(input&&w.worksheets.items.some(sheet=>sheet.name==='Read me')){
 const readme=w.worksheets.getItem('Read me');
 readme.getRange('B3').values=[[yearLabel]];
 readme.getRange('B4').values=[['Use Sets for native labels and units. These years share the same inventory; numerical results vary by year.'+(p.source_coverage?.forecast_from?` ${p.source_coverage.forecast_from}–${p.source_coverage.last_year} are forecast tables.`:'')]];
 readme.getRange('B4').format.autofitRows();
}
if(input&&before!==JSON.stringify(s.getRange(`A8:G${rows.length+7}`).values))throw new Error('Unintended set-table change');
w.recalculate();
console.log((await w.inspect({kind:'table',range:'Sets!A8:G12',include:'values',tableMaxRows:5,tableMaxCols:7,maxChars:1200})).ndjson);
console.log((await w.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:500})).ndjson);
const image=await w.render({sheetName:'Sets',range:'A1:G17',scale:1,format:'png'});
await fs.writeFile(path.join(dir,'preview.png'),new Uint8Array(await image.arrayBuffer()));
if(input&&w.worksheets.items.some(sheet=>sheet.name==='Read me')){
 const readmeImage=await w.render({sheetName:'Read me',range:'A1:B8',scale:1,format:'png'});
 await fs.writeFile(path.join(dir,'readme-preview.png'),new Uint8Array(await readmeImage.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(w)).save(path.join(dir,'sets.xlsx'));
console.log(JSON.stringify({rows:rows.length-1,counts:p.counts}));
