import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [indexPath]=process.argv.slice(2);
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
function table(sheet,rows,columns){
 const last=rows.length+7,final=String.fromCharCode(64+rows[0].length);
 sheet.getRange(`A8:${final}${last}`).values=rows;
 sheet.getRange(`A8:${final}${last}`).format={font:{name:'Arial',size:10,color:'#202c38'},rowHeight:24,verticalAlignment:'center'};
 columns.forEach((width,i)=>sheet.getRange(`${String.fromCharCode(65+i)}8:${String.fromCharCode(65+i)}${last}`).format.columnWidth=width);
 sheet.getRange(`A8:${final}8`).format={fill:'#245b6a',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',rowHeight:32,wrapText:true};
 sheet.tables.add(`A8:${final}${last}`,true,sheet.name+'Table');sheet.freezePanes.freezeRows(8);
 return last;
}
for(const item of jobs){
 const p=JSON.parse(await fs.readFile(item.profile,'utf8')), w=Workbook.create();
 const units=new Map(p.units.map(u=>[u.set+'|'+u.index[0],u.values.unit]));
 const geography=new Map(p.geography.regions.map(r=>[r.label,r]));
 const rows=[['Set','Position','Native label','Native unit','Country / territory','ISO3','Representation']];
 for(const [set,labels] of Object.entries(p.sets)){
  const skipped=p.set_flags?.[set]?.placeholder_labels||[];
  labels.filter(label=>!skipped.includes(label)).forEach((label,index)=>{
   const region=set==='Region'?geography.get(label):null;
   rows.push([set,index+1,label,units.get(set+'|'+label)||'',region?.name||'',region?.iso3||'',region?.kind||'']);
  });
 }
 const s=w.worksheets.add('Sets');s.showGridLines=false;s.tabColor='#245b6a';
 s.getRange('A2').values=[[`EXIOBASE ${p.release}: ${p.table} ${p.provenance.options.system||''} native sets`]];
 s.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#202c38'};
 s.getRange('A3').values=[[`Verified years: ${yearPeriods(p.years)}. These readings have identical native sets and units.`]];
 s.getRange('A4').values=[[Object.entries(p.counts).map(([name,count])=>`${name}: ${count}`).join('; ')]];
 s.getRange('A5').values=[['Source: '+item.source_url]];
 s.getRange('A6').values=[['Native labels and units retained. Empty placeholders omitted. Source matrices are excluded.']];
 s.getRange('A3:G6').format={font:{name:'Arial',size:10,color:'#566675'},rowHeight:20};
 const last=table(s,rows,[24,10,78,19,32,10,20]);
 s.getRange(`A9:A${last}`).setNumberFormat('@');s.getRange(`B9:B${last}`).setNumberFormat('0');s.getRange(`C9:G${last}`).setNumberFormat('@');
 s.getRange(`C9:C${last}`).format.wrapText=true;s.getRange(`C9:C${last}`).format.autofitRows();s.getRange(`E9:E${last}`).format.wrapText=true;s.freezePanes.freezeColumns(2);
 const r=w.worksheets.add('Readings');r.showGridLines=false;r.tabColor='#6a8591';
 r.getRange('A2').values=[['Verified source readings']];r.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#202c38'};
 r.getRange('A3').values=[['Each reading was checked separately. A shared set inventory does not imply equal indicator values.']];
 r.getRange('A4').values=[['Published archive checksums identify source files; extracted members use independent CRC and SHA-256 checks.']];
 r.getRange('A5').values=[['Source: '+item.source_url]];
 r.getRange('A3:H5').format={font:{name:'Arial',size:10,color:'#566675'},rowHeight:20};
 const data=[['Year','Format','Regions','Activities / sectors','Commodities','Satellite accounts','Published archive checksum','Original archive URL'],...p.readings.map(reading=>[reading.year,p.table+(p.provenance.options.system?' '+p.provenance.options.system:''),reading.counts.Region,reading.counts.Activity??reading.counts.Sector??'',reading.counts.Commodity??'',reading.counts['Satellite account'],reading.archive_checksum||'',reading.archive_url||reading.source_url])];
 const end=table(r,data,[10,16,12,22,17,21,42,78]);
 r.getRange(`A9:A${end}`).setNumberFormat('0');r.getRange(`C9:F${end}`).setNumberFormat('#,##0');r.getRange(`G9:H${end}`).setNumberFormat('@');r.getRange(`H9:H${end}`).format.wrapText=true;r.getRange(`H9:H${end}`).format.autofitRows();
 w.recalculate();
 const errors=await w.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:600});
 const previewFolder=path.dirname(item.workbook);await fs.mkdir(previewFolder,{recursive:true});
 for(const name of ['Sets','Readings']){
  const image=await w.render({sheetName:name,range:name==='Sets'?'A1:G17':'A1:H17',scale:1,format:'png'});
  await fs.writeFile(path.join(previewFolder,name+'.png'),new Uint8Array(await image.arrayBuffer()));
 }
 await(await SpreadsheetFile.exportXlsx(w)).save(item.workbook);
 console.log(item.id,rows.length-1,'labels',p.years.length,'verified years',errors.ndjson);
}
