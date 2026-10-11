import fs from 'node:fs/promises';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';
const [input,out]=process.argv.slice(2);
if(!input||!out)throw new Error('Usage: node build_sector_correspondence.mjs sector-sections.json output-directory');
await fs.mkdir(out,{recursive:true});
const {mappings}=JSON.parse(await fs.readFile(input,'utf8'));
// One sheet per distinct native classification, shared across identical years.
const groups=new Map();
for(const [id,main] of Object.entries(mappings))for(const m of [main,...(main.additional_mappings||[])]){
 const key=JSON.stringify([m.family,m.classification_id,m.entries.map(e=>[e.native_code,e.native_label,e.section]).sort((a,b)=>a[1].localeCompare(b[1]))]);
 if(!groups.has(key))groups.set(key,{m,ids:[]});
 groups.get(key).ids.push(id);
}
const wb=Workbook.create();let index=0;
for(const {m,ids} of groups.values()){
 const name=m.family==='EXIOBASE'?(ids[0].includes('hybrid')?(m.classification_id==='cpa-2002'?'EXIOBASE Hybrid products':'EXIOBASE Hybrid activities'):m.classification_id==='cpa-2002'?'EXIOBASE products':'EXIOBASE industries'):m.family==='OECD'?'OECD ICIO':m.family==='FIGARO'?(m.classification_id==='cpa-2.1'?'FIGARO products':'FIGARO activities'):m.family==='WIOD'?(m.dimension==='Activity'?'WIOD activities':'WIOD industries'):m.family;
 const s=wb.worksheets.add(name);s.showGridLines=false;s.tabColor='#245b6a';
 s.getRange('A2').values=[[`${m.family}: ${m.classification} sections`]];
 s.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#202c38'};
 s.getRange('A3').values=[['Sum each native category once into its section; weights are all 1. Readings with identical classifications share this sheet.']];
 s.getRange('A4').values=[['Section letters from different revisions are not a cross-database concordance. Combined categories stay combined.']];
 s.getRange('A5').values=[['Source: '+m.source_url]];
 s.getRange('A6').values=[['Classification: '+m.classification_url]];
 s.getRange('A3:E6').format={font:{name:'Arial',size:10,color:'#566675'},rowHeight:19};
 s.getRange('A2:E2').format.borders={bottom:{style:'thin',color:'#245b6a'}};
 const rows=[['Native code','Native category (unchanged)','Section','Section label (short)','Weight'],...m.entries.map(e=>[e.native_code||'',e.native_label,e.section,m.sections[e.section],1])];
 const last=rows.length+7;s.getRange(`A8:E${last}`).values=rows;
 s.getRange(`A8:E${last}`).format={font:{name:'Arial',size:10,color:'#202c38'},verticalAlignment:'center',rowHeight:28};
 s.getRange(`A9:D${last}`).setNumberFormat('@');s.getRange(`E9:E${last}`).setNumberFormat('0');
 const widths=[16,74,10,48,10];'ABCDE'.split('').forEach((c,i)=>s.getRange(`${c}8:${c}${last}`).format.columnWidth=widths[i]);
 s.getRange(`B9:B${last}`).format.wrapText=true;s.getRange(`D9:D${last}`).format.wrapText=true;s.getRange(`B9:D${last}`).format.autofitRows();
 s.getRange('A8:E8').format={fill:'#245b6a',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',rowHeight:30};
 s.tables.add(`A8:E${last}`,true,'NativeSections'+(++index));s.freezePanes.freezeRows(8);s.freezePanes.freezeColumns(1);
}
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:"'EXIOBASE industries'!A8:E12",include:'values',tableMaxRows:5,tableMaxCols:5,maxChars:1600})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:400})).ndjson);
for(let i=0;i<groups.size;i++){
 const s=wb.worksheets.getItemAt(i);
 const image=await wb.render({sheetName:s.name,range:'A1:E17',scale:1,format:'png'});
 await fs.writeFile(`${out}/${s.name.replaceAll(' ','-')}.png`,new Uint8Array(await image.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(wb)).save(`${out}/sector-correspondence.xlsx`);
console.log('Exported '+groups.size+' distinct native classifications.');
