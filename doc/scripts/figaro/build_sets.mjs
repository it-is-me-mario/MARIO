import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const jobs=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
function intro(s,title,notes){
 s.showGridLines=false;s.tabColor='#245b6a';s.getRange('A2').values=[[title]];
 s.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#202c38'};
 notes.forEach((text,i)=>s.getRange('A'+(i+3)).values=[[text]]);
 s.getRange('A3:H6').format={font:{name:'Arial',size:10,color:'#566675'},rowHeight:20};
}
function table(s,rows,widths,name){
 const last=rows.length+7,end=String.fromCharCode(64+rows[0].length);
 s.getRange('A8:'+end+last).values=rows;
 s.getRange('A8:'+end+last).format={font:{name:'Arial',size:10,color:'#202c38'},verticalAlignment:'center',rowHeight:26};
 widths.forEach((width,i)=>s.getRange(String.fromCharCode(65+i)+'8:'+String.fromCharCode(65+i)+last).format.columnWidth=width);
 s.getRange('A8:'+end+'8').format={fill:'#245b6a',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',rowHeight:32,wrapText:true};
 s.tables.add('A8:'+end+last,true,name);s.freezePanes.freezeRows(8);return last;
}
for(const job of jobs){
 const p=JSON.parse(await fs.readFile(job.profile,'utf8')),wb=Workbook.create(),sets=wb.worksheets.add('Sets');
 const kind=p.table==='SUT'?'SUT':p.provenance.options.iot_mode==='industry'?'IOT ixi':'IOT pxp',period=p.years[0]+'–'+p.years.at(-1);
 const economic=p.table==='SUT'?'64 activities and 64 products':p.provenance.options.iot_mode==='industry'?'64 industries':'64 products';
 intro(sets,`FIGARO ${kind}: native sets, ${period}`,[
  `Identical sets in all ${p.years.length} verified years. Each of the 50 regions has ${economic} and five final-demand categories.`,
  '49 individual countries + Rest of the world; six factors. No environmental extension is loaded; the MARIO placeholder is omitted.',
  'Source: '+job.source_url,
  'Native values: current million EUR. Activities use NACE Rev.2; products use CPA 2.1. Native labels and codes are preserved.'
 ]);
 const units=new Map(p.units.map(u=>[u.set+'|'+u.index[0],u.values.unit]));
 const geography=new Map(p.geography.regions.map(region=>[region.label,region]));
 const rows=[['Set','Position','Native code','Native label','Native unit','Country / territory','ISO3','Representation']];
 for(const [set,labels] of Object.entries(p.sets)){
  const excluded=p.set_flags?.[set]?.placeholder_labels||[];
  labels.filter(label=>!excluded.includes(label)).forEach((label,i)=>{
   const region=set==='Region'?geography.get(label):null;
   rows.push([set,i+1,p.native_codes?.[set]?.[label]||'',label,units.get(set+'|'+label)||'',region?.name||'',region?.iso3||'',region?.kind||'']);
  });
 }
 const last=table(sets,rows,[25,10,17,90,22,24,10,18],'FigaroSets');
 sets.getRange('B9:B'+last).setNumberFormat('0');sets.getRange('C9:H'+last).setNumberFormat('@');
 sets.getRange('D9:D'+last).format.wrapText=true;sets.getRange('D9:D'+last).format.autofitRows();
 sets.freezePanes.freezeColumns(2);
 const readings=wb.worksheets.add('Readings');
 intro(readings,`FIGARO ${kind}: verified sources, ${period}`,[
  'Official Eurostat API caches parsed with the public MARIO parser, calc_all=False. Each source file is identified below.',
  'GDP = D1 + D29X39 + B2A3G + D21X31 on intermediate AND final uses; source country totals independently reconciled.',
  'FIGARO uses reference year, table format and IOT system filters. No release/version filter is used.',
  'Source: '+job.source_url
 ]);
 const input=[['Year','Dataflow','Original filename','Regions',p.table==='SUT'?'Activities / products':'Economic categories','Final demand','Factors','SHA-256'],
  ...p.readings.flatMap(x=>(x.source_files?.length?x.source_files:[{filename:x.filename,dataflow:x.dataflow,sha256:x.sha256}]).map(file=>[x.year,file.dataflow,file.filename,x.counts.Region,x.counts.Sector??x.counts.Activity,x.counts['Consumption category'],x.counts['Factor of production'],file.sha256]))];
 const end=table(readings,input,[10,23,64,12,12,16,12,72],'FigaroSources');
 readings.getRange('A9:A'+end).setNumberFormat('0');readings.getRange('D9:G'+end).setNumberFormat('0');
 wb.recalculate();
 console.log((await wb.inspect({kind:'region',sheetId:'Sets',range:'A8:H12',maxChars:1400,tableMaxRows:5,tableMaxCols:8})).ndjson);
 console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:400})).ndjson);
 for(const sheet of ['Sets','Readings']){
  const image=await wb.render({sheetName:sheet,range:'A1:H17',scale:1,format:'png'});
  await fs.writeFile(path.join(path.dirname(job.workbook),sheet+'.png'),new Uint8Array(await image.arrayBuffer()));
 }
 await (await SpreadsheetFile.exportXlsx(wb)).save(job.workbook);
 console.log('Exported '+(rows.length-1)+' native labels and '+p.readings.length+' source readings.');
}
