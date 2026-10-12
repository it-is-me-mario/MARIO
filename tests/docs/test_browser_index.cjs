/* Every compact regional total must agree with the full snapshot calculation. */
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const root=path.resolve(__dirname,'../..'),data=path.join(root,'doc/source/_static/data/economy');
const M=require(path.join(root,'doc/source/_static/economy-model.js'));
const wb=JSON.parse(fs.readFileSync(path.join(data,'world-bank.json')));
const python=process.env.MARIO_DOCS_PYTHON||'python';
const run=cp.spawnSync(python,['-c',"import json,sys;from pathlib import Path;sys.path.insert(0,str(Path(sys.argv[1])/'doc/source/_ext'));from mario_browser_assets import build_browser_index;print(json.dumps(build_browser_index(sys.argv[2]),separators=(',',':')))",root,data],{encoding:'utf8',maxBuffer:12*1024*1024});
assert.equal(run.status,0,run.stderr);
const index=JSON.parse(run.stdout),{snapshots,mappings}=M.unpackBrowserIndex(index);
function equal(a,b,label){if(a===null||b===null)assert.equal(a,b,label);else assert.ok(Math.abs(a-b)<=Math.max(1,Math.abs(b))*1e-12,label);}
test('whole-economy summaries preserve GDP, value added and GHG in all regions and years',()=>{
 for(const summary of snapshots){
  const full=JSON.parse(fs.readFileSync(path.join(data,summary.recipe.id+'.json'))),mapping=mappings[summary.recipe.id];
  for(const metric of ['gdp','value_added','ghg'])for(const perCapita of [false,true]){
   const config={metric,perCapita,section:'all',country:'ITA'};
   assert.equal(M.metricAvailable([summary],metric),M.metricAvailable([full],metric),summary.recipe.id+' '+metric);
   for(let i=0;i<full.regions.length;i++)equal(M.value(summary,summary.regions[i],config,wb,mapping),M.value(full,full.regions[i],config,wb,mapping),summary.recipe.id+' '+metric+' '+full.regions[i].code);
   equal(M.worldValue(summary,{...config,country:'world'},wb,mapping),M.worldValue(full,{...config,country:'world'},wb,mapping),summary.recipe.id+' world '+metric);
  }
 }
});
test('only a sector selection requests full vectors and never substitutes an economy total',()=>{
 for(const s of snapshots){
  assert.equal(M.needsDetailedReading(s,{section:'all'}),false);
  assert.equal(M.needsDetailedReading(s,{section:'A'}),true);
  assert.equal(M.needsDetailedReading(s,{section:['A','B']}),true);
  assert.equal(M.needsDetailedReading(s,{section:[]}),false);
  assert.equal(M.needsDetailedReading(s,{section:'A',country:[]}),false);
  assert.equal(M.value(s,s.regions[0],{metric:'value_added',section:'A',country:'ITA'},wb,mappings[s.recipe.id]),null);
 }
 assert.equal(M.needsDetailedReading({metadata_only:true},{section:'all'}),true);
 assert.equal(M.needsDetailedReading({regions:[]},{section:'A'}),false);
});
