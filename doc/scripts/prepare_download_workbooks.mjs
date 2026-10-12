// Add self-contained scope/source notices without changing inventory records.
// Usage: node prepare_download_workbooks.mjs jobs.json output-directory [job-index]
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [manifest,out,only]=process.argv.slice(2);
const jobs=JSON.parse(await fs.readFile(manifest,'utf8'));
await fs.mkdir(out,{recursive:true});
if(only===undefined){
 for(let i=0;i<jobs.length;i++){
  // A separate process releases the native rendering/export heap between files.
  const run=spawnSync(process.execPath,[process.argv[1],manifest,out,String(i)],{stdio:'inherit'});
  if(run.status!==0)process.exit(run.status||1);
 }
}else{
 const job=jobs[Number(only)],book=Workbook.create();
 const sheet=book.worksheets.add('Read me');sheet.showGridLines=false;sheet.tabColor='#F0783C';
 const rows=[['Read me',job.title],...job.rows];
 const range=sheet.getRange(`A1:B${rows.length}`);range.values=rows;
 range.format={font:{name:'Arial',size:10,color:'#302820'},wrapText:true,verticalAlignment:'center',rowHeight:42};
 sheet.getRange(`A1:A${rows.length}`).format.columnWidth=22;
 sheet.getRange(`B1:B${rows.length}`).format.columnWidth=100;
 sheet.getRange(`A2:A${rows.length}`).format.font.bold=true;
 sheet.getRange('A1:B1').format={fill:'#302820',font:{name:'Arial',size:14,bold:true,color:'#FFFFFF'},rowHeight:38};
 sheet.getRange(`B2:B${rows.length}`).setNumberFormat('@');
 range.format.autofitRows();
 book.recalculate();
 const errors=await book.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:5},maxChars:800});
 const after=await book.render({sheetName:'Read me',range:`A1:B${rows.length}`,scale:1,format:'png'});
 await fs.writeFile(path.join(out,job.name+'-readme.png'),new Uint8Array(await after.arrayBuffer()));
 const notice=path.join(out,job.name+'-notice.xlsx');
 await(await SpreadsheetFile.exportXlsx(book)).save(notice);
 const run=spawnSync(process.env.DOWNLOAD_PYTHON||'python3',[path.join(path.dirname(process.argv[1]),'append_workbook_notice.py'),job.path,notice,path.join(out,job.name)],{stdio:'inherit'});
 if(run.status!==0)process.exit(run.status||1);
 console.log(JSON.stringify({name:job.name,sheets:book.worksheets.items.map(s=>s.name),errors:errors.ndjson}));
}
