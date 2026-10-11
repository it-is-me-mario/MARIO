import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [indexPath,mappingInput,mappingOutput]=process.argv.slice(2);
if(!indexPath)throw new Error('Pass catalogue-build.json');
const jobs=JSON.parse(await fs.readFile(indexPath,'utf8'));
function table(sheet,rows,widths,name){
 const end=rows.length+7,final=String.fromCharCode(64+rows[0].length);
 sheet.showGridLines=false;sheet.tabColor='#245b6a';
 sheet.getRange(`A8:${final}${end}`).values=rows;
 sheet.getRange(`A8:${final}${end}`).format={font:{name:'Arial',size:10,color:'#202c38'},rowHeight:24,verticalAlignment:'center'};
 widths.forEach((width,i)=>sheet.getRange(`${String.fromCharCode(65+i)}8:${String.fromCharCode(65+i)}${end}`).format.columnWidth=width);
 sheet.getRange(`A8:${final}8`).format={fill:'#245b6a',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',rowHeight:32,wrapText:true};
 sheet.tables.add(`A8:${final}${end}`,true,name);sheet.freezePanes.freezeRows(8);
 return end;
}
function intro(sheet,title,notes){
 sheet.getRange('A2').values=[[title]];
 sheet.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#202c38'};
 notes.forEach((text,i)=>sheet.getRange(`A${i+3}`).values=[[text]]);
 sheet.getRange('A3:G6').format={font:{name:'Arial',size:10,color:'#566675'},rowHeight:20};
}
async function verify(wb,folder,sheets){
 wb.recalculate();
 console.log((await wb.inspect({kind:'region',sheetId:sheets[0],range:'A2:G12',maxChars:1200,tableMaxRows:4,tableMaxCols:7})).ndjson);
 const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:400});
 console.log(errors.ndjson);
 await fs.mkdir(folder,{recursive:true});
 for(const name of sheets){
  const preview=await wb.render({sheetName:name,range:name==='Regional memberships'?'A1:C17':name==='Readings'?'A1:G17':'A1:G17',scale:1,format:'png'});
  await fs.writeFile(path.join(folder,name.replaceAll(' ','-')+'.png'),new Uint8Array(await preview.arrayBuffer()));
 }
}
for(const item of jobs){
 const p=JSON.parse(await fs.readFile(item.profile,'utf8')),wb=Workbook.create();
 const units=new Map(p.units.map(u=>[u.set+'|'+u.index[0],u.values.unit]));
 const geography=new Map(p.geography.regions.map(r=>[r.label,r]));
 const s=wb.worksheets.add('Sets');
 intro(s,`OECD ICIO ${p.release}: parsed native sets`,[
  `Verified years: ${p.years[0]}–${p.years.at(-1)}. Every year has identical parsed sets and units.`,
  Object.entries(p.counts).map(([set,count])=>`${set}: ${count}`).join('; '),
  'Source: '+item.source_url,
  p.release==='Extended'?'MARIO sums CN1/CN2 into CHN and MX1/MX2 into MEX. Original production regions: 85; parsed regions: 81.':'Original and parsed production regions: 81. Monetary inputs: nominal million USD; no emissions extension.'
 ]);
 const rows=[['Set','Position','Native label','Native unit','Country / territory','ISO3','Representation']];
 for(const [set,labels] of Object.entries(p.sets)){
  const excluded=p.set_flags?.[set]?.placeholder_labels||[];
  labels.filter(label=>!excluded.includes(label)).forEach((label,i)=>{
   const region=set==='Region'?geography.get(label):null;
   rows.push([set,i+1,label,units.get(set+'|'+label)||'',region?.name||'',region?.iso3||'',region?.kind||'']);
  });
 }
 const end=table(s,rows,[24,10,28,27,36,10,20],'SetsTable');
 s.getRange(`B9:B${end}`).setNumberFormat('0');s.getRange(`C9:G${end}`).setNumberFormat('@');
 s.freezePanes.freezeColumns(2);
 const r=wb.worksheets.add('Readings');
 intro(r,`OECD ICIO ${p.release}: verified local files`,[
  'Full MARIO ICIO parsing, calc_all=False. VA and TLS reconcile to original country totals.',
  'GDP = VA plus TLS on intermediate and final uses. No exchange-rate conversion is needed.',
  'Source: '+item.source_url,
  'SHA-256 checksums identify the unchanged local CSVs. Shared sets do not imply identical indicator values.'
 ]);
 const data=[['Year','Original filename','Raw production regions','Parsed regions','Industries','Final-demand categories','SHA-256'],
  ...p.readings.map(x=>[x.year,x.filename,x.raw_region_count,x.counts.Region,x.counts.Sector,x.counts['Consumption category'],x.sha256])];
 const last=table(r,data,[10,24,23,17,16,24,72],'ReadingsTable');
 r.getRange(`A9:A${last}`).setNumberFormat('0');r.getRange(`C9:F${last}`).setNumberFormat('#,##0');
 const m=wb.worksheets.add('Regional memberships');
 intro(m,`OECD ICIO ${p.release}: regional set membership`,[
  'Native industry and final-demand labels are listed once for each parsed region.',
  'Each of the 81 regions has 50 industries and six final-demand categories.',
  'Source: '+item.source_url
 ]);
 table(m,[['Region','Set','Native label'],...p.region_items.map(x=>[x.region,x.set,x.label])],[18,30,36],'MembershipTable');
 await verify(wb,path.dirname(item.workbook),['Sets','Readings','Regional memberships']);
 await(await SpreadsheetFile.exportXlsx(wb)).save(item.workbook);
 console.log('Exported',p.release,rows.length-1,'labels,',p.readings.length,'source files.');
}
if(mappingInput&&mappingOutput){
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(mappingInput));
 let s;try{s=wb.worksheets.getItem('OECD ICIO');}catch{s=wb.worksheets.getItem('OECD ICIO Extended');}
 s.getRange('A2').values=[['OECD ICIO Regular and Extended: ISIC Rev.4 sections']];
 s.getRange('A3').values=[['Applies to both editions, 1995–2022. Sum each native category once; weights are all 1.']];
 wb.recalculate();
 console.log((await wb.inspect({kind:'region',sheetId:s.name,range:'A2:E12',maxChars:1500})).ndjson);
 console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:400})).ndjson);
 const preview=await wb.render({sheetName:s.name,range:'A1:E17',scale:1,format:'png'});
 await fs.writeFile(path.join(path.dirname(mappingOutput),'mapping-after.png'),new Uint8Array(await preview.arrayBuffer()));
 await(await SpreadsheetFile.exportXlsx(wb)).save(mappingOutput);
 console.log('Updated the shared OECD mapping; other sheets retained.');
}
