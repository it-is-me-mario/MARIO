import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [input,output]=process.argv.slice(2),p=JSON.parse(await fs.readFile(input,'utf8'));
const wb=Workbook.create();
function table(name,title,headers,records,widths){
 const s=wb.worksheets.add(name);s.showGridLines=false;
 const last=records.length+8,end=String.fromCharCode(64+headers.length);
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#202c38'};
 s.getRange('A2:'+end+'2').format.borders={bottom:{style:'thin',color:'#245b6a'}};
 s.getRange('A4').values=[['CEDA by Watershed. Source: '+p.provenance.source_filename]];
 s.getRange('A5').values=[[p.source_url+' (CC BY-SA 4.0: '+p.license_url+')']];
 s.getRange('A6').values=[['Metadata adapted from the source. No emission-factor values or economic matrices included.']];
 s.getRange('A4:'+end+'6').format={font:{name:'Arial',size:10,color:'#566675'},rowHeight:20};
 s.getRange('A8:'+end+last).values=[headers,...records];
 s.getRange('A8:'+end+last).format={font:{name:'Arial',size:10,color:'#202c38'},verticalAlignment:'center',rowHeight:28};
 s.getRange('A9:'+end+last).setNumberFormat('@');
 s.getRange('A8:'+end+'8').format={fill:'#245b6a',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',rowHeight:30};
 widths.forEach((w,i)=>s.getRange(String.fromCharCode(65+i)+'8:'+String.fromCharCode(65+i)+last).format.columnWidth=w);
 s.tables.add('A8:'+end+last,true,'Source'+name);if(records.length>20){s.freezePanes.freezeRows(8);s.freezePanes.freezeColumns(1);}
 return s;
}
const metadata=table('Scope','Open CEDA scope',['Item','Value'],[
 ['Version',p.release],['Base year',p.year],['Regions',p.counts.Region],['Individual countries',p.geography.individual_countries],['Aggregate regions',p.geography.aggregate_count],['Native sectors',p.counts.Sector],
 ['Data product','Characterized GHG emission factors'],['Native classification','BEA-based CEDA sectors. NAICS and NACE mappings are unverified.'],['MARIO parser','Unavailable'],['MARIO indicators','Unavailable'],
 ['Satellite account classification','Not supplied'],['Factors of production','Not supplied'],['Final-demand categories','Not supplied'],['Source release date',p.provenance.source_release_date],['Source SHA-256',p.provenance.source_sha256]
],[31,91]);
table('Regions','Native reporting regions',['Region code','Native name','Representation'],p.geography.regions.map(r=>[r.label,r.source_name||r.name,r.kind]),[20,50,24]);
const sectors=table('Sectors','Native sector classification',['Native code','Sector name'],p.sets.Sector.map(label=>[p.native_codes[label],label]),[20,100]);
sectors.getRange('B9:B408').format.wrapText=true;sectors.getRange('A9:B408').format.autofitRows();
metadata.getRange('B10:B14').setNumberFormat('#,##0');
metadata.getRange('B10').setNumberFormat('0');
metadata.getRange('B11').formulas=[['=COUNTA(Regions!A9:A157)']];
metadata.getRange('B12').formulas=[['=COUNTIF(Regions!C9:C157,"country")']];
metadata.getRange('B13').formulas=[['=COUNTIF(Regions!C9:C157,"aggregate")']];
metadata.getRange('B14').formulas=[['=COUNTA(Sectors!A9:A408)']];
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Scope!A9:B14',include:'values,formulas',tableMaxRows:6,tableMaxCols:2,maxChars:1400})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:5},maxChars:500})).ndjson);
for(const name of (process.env.CEDA_RENDER_SHEETS?.split(',') || ['Scope','Regions','Sectors'])){
 const preview=await wb.render({sheetName:name,range:name==='Scope'?'A1:B23':name==='Regions'?'A1:C15':'A1:B15',scale:1,format:'png'});
 await fs.writeFile(output+'/'+name+'.png',new Uint8Array(await preview.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(output+'/'+p.id+'-sets.xlsx');
