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
 intro(s,`WIOD ${p.release} · ${p.table} · ${p.price_basis}: parsed native sets`,[
  `Verified years: ${p.years[0]}–${p.years.at(-1)}. Every year has identical parsed sets and units.`,
  Object.entries(p.counts).map(([set,count])=>`${set}: ${count}`).join('; '),
  'Source: '+item.source_url,
  p.table==='SUT'?'43 endogenous countries; ROW imports are external factor accounts. No complete World total.':p.price_basis==='Previous year prices'?'Previous-year prices and previous-year million USD. SEA not attached; current-price World Bank comparison omitted.':'44 regions including ROW; current million USD. 16 socioeconomic accounts; no local GHG extension.'
 ]);
 const rows=[['Set','Position','Native label','Native unit','Country / territory','ISO3','Representation']];
 for(const [set,labels] of Object.entries(p.sets)){
  const excluded=p.set_flags?.[set]?.placeholder_labels||[];
  labels.filter(label=>!excluded.includes(label)).forEach((label,i)=>{
   const region=set==='Region'?geography.get(label):null;
   rows.push([set,i+1,label,units.get(set+'|'+label)||'',region?.name||'',region?.iso3||'',region?.kind||'']);
  });
 }
 if(p.table==='IOT'&&p.price_basis==='Current prices'){s.getRange('A7').values=[['SEA source covers individual countries; ROW socioeconomic entries are placeholders.']];s.getRange('A7').format.font={name:'Arial',size:10,color:'#566675'};}
 const end=table(s,rows,[24,10,82,20,25,10,20],'SetsTable');
 s.getRange(`B9:B${end}`).setNumberFormat('0');s.getRange(`C9:G${end}`).setNumberFormat('@');
 s.getRange(`C9:C${end}`).format.wrapText=true;s.getRange(`C9:C${end}`).format.autofitRows();
 s.freezePanes.freezeColumns(2);
 const r=wb.worksheets.add('Readings');
 intro(r,`WIOD ${p.release} · ${p.table} · ${p.price_basis}: verified local files`,[
  'Full MARIO WIOD parsing, calc_all=False. Country VA and TXSP reconcile independently to original rows.',
  'GDP = value added at basic prices + net product taxes on intermediate AND final uses.',
  'Source: '+item.source_url,
  'SHA-256 checksums identify the unchanged local XLSB inputs. Shared sets do not imply identical indicator values.'
 ]);
 const data=[['Year','Original filename','Raw production regions','Parsed regions','Sectors / activities','Final-demand categories','SHA-256'],
  ...p.readings.map(x=>[x.year,x.filename,x.raw_region_count,x.counts.Region,x.counts.Sector??x.counts.Activity,x.counts['Consumption category'],x.sha256])];
 const last=table(r,data,[10,24,23,17,16,24,72],'ReadingsTable');
 r.getRange(`A9:A${last}`).setNumberFormat('0');r.getRange(`C9:F${last}`).setNumberFormat('#,##0');
 const m=wb.worksheets.add('Regional memberships');
 intro(m,`WIOD ${p.release} · ${p.table} · ${p.price_basis}: regional set membership`,[
  'Native industry and final-demand labels are listed once for each parsed region.',
  p.table==='SUT'?'Each endogenous country has 56 activities and 56 commodities; ROW imports are outside the native Region set.':'Each parsed region has 56 sectors. Native membership labels are preserved.',
  'Source: '+item.source_url
 ]);
 const membershipEnd=table(m,[['Region','Set','Native label'],...p.region_items.map(x=>[x.region,x.set,x.label])],[18,30,90],'MembershipTable');
 m.getRange(`C9:C${membershipEnd}`).format.wrapText=true;m.getRange(`C9:C${membershipEnd}`).format.autofitRows();
 await verify(wb,path.dirname(item.workbook),['Sets','Readings','Regional memberships']);
 await(await SpreadsheetFile.exportXlsx(wb)).save(item.workbook);
 console.log('Exported',p.release,rows.length-1,'labels,',p.readings.length,'source files.');
}
