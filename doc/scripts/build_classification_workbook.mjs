import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [input,output]=process.argv.slice(2);
const data=JSON.parse(await fs.readFile(input,'utf8'));
const wb=Workbook.create();
const applicable=new Map();
for(const p of data.profiles)for(const id of p.mapping_ids || [p.mapping])if(id){
 const title=[p.family,p.release,p.units,p.price_basis,p.format,p.system].filter(Boolean).join(' ');
 if(!applicable.has(id))applicable.set(id,[]);
 if(!applicable.get(id).includes(title))applicable.get(id).push(title);
}
const rows=[['Native classification','Official classification','Official code','Native code','Native category','Relation','Mapping depth','Source']];
// Identical native codes share workbook rows, even when the browser uses
// separate Sector / Activity / Commodity mappings to filter the correct axis.
const groups=new Map();
for(const [id,m] of Object.entries(data.mappings)){
 if(!applicable.has(id))continue;
 const key=JSON.stringify([m.classification,m.depth,m.entries,m.section_entries,m.source_url]);
 if(!groups.has(key))groups.set(key,{mapping:m,titles:new Set()});
 for(const title of applicable.get(id))groups.get(key).titles.add(title);
}
for(const {mapping:m,titles} of groups.values()){
 const title=[...titles].join('; ');
 for(const e of m.entries)rows.push([title,data.classifications[m.classification].label,e.official_code,e.native_code,e.native_label,e.relation,m.depth,m.source_url]);
 if(m.section_entries)for(const e of m.section_entries)rows.push([title,data.classifications[m.classification].label,e.official_code,e.native_code,e.native_label,e.relation,1,m.source_url]);
}
const tree=[['Classification','Code','Name','Level','Parent code','Source']];
for(const c of Object.values(data.classifications))for(const n of c.nodes)tree.push([c.label,n.code,n.name,n.level,n.parent||'',c.source_url]);
function sheet(name,title,table,widths){
 const s=wb.worksheets.add(name);s.showGridLines=false;
 const end=String.fromCharCode(64+table[0].length),last=table.length+7;
 s.getRange('A2').values=[[title]];
 s.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#202c38'};
 s.getRange('A2:'+end+'2').format.borders={bottom:{style:'thin',color:'#245b6a'}};
 s.getRange('A3').values=[['Codes retain their source revision and leading zeros. Unknown mappings are not zero coverage.']];
 s.getRange('A4').values=[['CPA source links use the supplied CPA 2002 to EXIOBASE 2.0 correspondence and the explicit EXIOBASE 2 to 3 product bridge.']];
 s.getRange('A5').values=[['Detailed correspondence is incomplete. Links do not provide numerical allocation weights or assert exact equivalence.']];
 s.getRange('A6').values=[['Source files: CPA2002_6digit_EXIOBASE_FINAL.xlsx; EXIOBASE2 products comparison with EXIOBASE3 products.xlsx.']];
 s.getRange('A3:'+end+'6').format={font:{name:'Arial',size:10,color:'#566675'},rowHeight:19};
 s.getRange('A8:'+end+last).values=table;
 s.getRange('A8:'+end+last).format={font:{name:'Arial',size:10,color:'#202c38'},verticalAlignment:'center',rowHeight:30};
 s.getRange('A9:'+end+last).setNumberFormat('@');
 s.getRange('A8:'+end+'8').format={fill:'#245b6a',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',rowHeight:30};
 widths.forEach((width,i)=>s.getRange(String.fromCharCode(65+i)+'8:'+String.fromCharCode(65+i)+last).format.columnWidth=width);
 const wrap=name==='Correspondences'?['A','E']:['C'];
 for(const col of wrap)s.getRange(col+'9:'+col+last).format.wrapText=true;
 s.getRange('A9:'+end+last).format.autofitRows();
 s.tables.add('A8:'+end+last,true,name==='Correspondences'?'NativeOfficialLinks':'OfficialHierarchy');
 s.freezePanes.freezeRows(8);s.freezePanes.freezeColumns(name==='Correspondences'?2:1);
 return s;
}
sheet('Correspondences','Native and official classification correspondence',rows,[55,22,16,16,66,25,17,55]);
sheet('Classification tree','Official classification hierarchy',tree,[24,17,74,10,16,55]);
wb.worksheets.getItem('Correspondences').getRange('G9:G'+(rows.length+7)).setNumberFormat('0');
wb.worksheets.getItem('Classification tree').getRange('D9:D'+(tree.length+7)).setNumberFormat('0');
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Correspondences!B8:G12',include:'values',tableMaxRows:5,tableMaxCols:6,maxChars:1200})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:5},maxChars:500})).ndjson);
for(const name of ['Correspondences','Classification tree']){
 const preview=await wb.render({sheetName:name,range:name==='Correspondences'?'B8:G14':'A8:E14',scale:1,format:'png'});
 await fs.writeFile(output+'/'+name.replaceAll(' ','-')+'.png',new Uint8Array(await preview.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(output+'/classification-correspondence.xlsx');
console.log(JSON.stringify({links:rows.length-1,nodes:tree.length-1}));
