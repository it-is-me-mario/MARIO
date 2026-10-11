// Export public GTAP classification metadata, never licensed observations.
import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [profilesDir,outputDir]=process.argv.slice(2);
await fs.mkdir(outputDir,{recursive:true});
for(const variant of ['standard','power']){
 const p=JSON.parse(await fs.readFile(`${profilesDir}/gtap-12-${variant}-scope.json`,'utf8'));
 const wb=Workbook.create();
 function table(name,title,headers,rows,widths){
  const s=wb.worksheets.add(name),end=String.fromCharCode(64+headers.length),last=rows.length+7;
  s.showGridLines=false;s.getRange('A2').values=[[title]];
  s.getRange(`A2:${end}2`).format={font:{name:'Arial',size:14,bold:true,color:'#231b17'},borders:{bottom:{style:'thin',color:'#fc6b3c'}}};
  s.getRange('A4').values=[['Public classification metadata. Licensed numerical observations are excluded.']];
  s.getRange('A4').format.font={name:'Arial',size:10,italic:true,color:'#6a594b'};
  s.getRange(`A7:${end}${last}`).values=[headers,...rows];
  s.getRange(`A7:${end}${last}`).format={font:{name:'Arial',size:10,color:'#231b17'},rowHeight:24,verticalAlignment:'center'};
  s.getRange(`A7:${end}7`).format={fill:'#49372b',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',rowHeight:28};
  widths.forEach((w,i)=>s.getRange(`${String.fromCharCode(65+i)}7:${String.fromCharCode(65+i)}${last}`).format.columnWidth=w);
  s.tables.add(`A7:${end}${last}`,true,'GTAP'+variant+name).style='TableStyleLight1';
  if(rows.length>20){s.freezePanes.freezeRows(7);s.freezePanes.freezeColumns(1);}
  return s;
 }
 const scope=table('Scope',p.label+' scope',['Item','Value'],[
  ['Reference years',p.years.join(', ')],['Regions',p.counts.Region],['Individual countries',p.geography.individual_countries],['Aggregate regions',p.geography.aggregate_count],['Native sectors',p.counts.Sector],
  ['MARIO parser',p.parser_supported?'Power MRIO supported':'Standard distribution unsupported'],['Numerical indicators','Not published: proprietary GTAP licence'],
  ['Satellite / factor / final-demand sets','Not loaded in this metadata-only inventory'],
  ['Scope source',p.source_url],['Licence',p.license_url],['Classification routes','Public concordances and qualified nxbase reviews in Data explorer'],
  ['Reference years source','https://jgea.org/ojs/index.php/jgea/article/view/344']
 ],[40,105]);
 const regions=table('Regions','GTAP 12 reporting regions',['Native code','Native name','Representation'],p.geography.regions.map(r=>[r.label,r.source_name||r.name,r.kind]),[19,51,24]);
 regions.getRange('A5').values=[['Source: https://www.gtap.agecon.purdue.edu/databases/regions.aspx?Version=12.211']];
 regions.getRange('A8:A170').setNumberFormat('@');
 const sectors=table('Sectors',p.label+' sector classification',['Native code','Sector name'],p.sets.Sector.map(label=>[p.native_codes.Sector[label],label]),[20,100]);
 sectors.getRange('A5').values=[['Source: '+(variant==='power'?'https://www.gtap.agecon.purdue.edu/databases/Utilities/v12.aspx':'https://www.gtap.agecon.purdue.edu/databases/v12/v12_sectors.aspx')]];
 const sectorEnd=p.counts.Sector+7;sectors.getRange(`A8:A${sectorEnd}`).setNumberFormat('@');
 sectors.getRange(`B8:B${sectorEnd}`).format.wrapText=true;sectors.getRange(`A8:B${sectorEnd}`).format.autofitRows();
 scope.getRange('B9:B12').setNumberFormat('#,##0');
 scope.getRange('B9').formulas=[['=COUNTA(Regions!A8:A170)']];
 scope.getRange('B10').formulas=[['=COUNTIFS(Regions!C8:C170,"country")']];
 scope.getRange('B11').formulas=[['=COUNTIFS(Regions!C8:C170,"aggregate")']];
 scope.getRange('B12').formulas=[['=COUNTA(Sectors!A8:A'+sectorEnd+')']];
 wb.recalculate();
 console.log((await wb.inspect({kind:'table',range:'Scope!A8:B12',include:'values,formulas',tableMaxRows:5,tableMaxCols:2,maxChars:1100})).ndjson);
 console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:5},maxChars:300})).ndjson);
 for(const name of ['Scope','Regions','Sectors']){
  const preview=await wb.render({sheetName:name,range:name==='Regions'?'A1:C14':name==='Scope'?'A1:B19':'A1:B14',scale:1,format:'png'});
  await fs.writeFile(`${outputDir}/${variant}-${name}.png`,new Uint8Array(await preview.arrayBuffer()));
 }
 await(await SpreadsheetFile.exportXlsx(wb)).save(`${outputDir}/${p.id}-sets.xlsx`);
}
