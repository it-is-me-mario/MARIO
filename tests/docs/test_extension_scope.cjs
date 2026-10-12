const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const E=require('../../doc/source/_static/extension-scope.js');
const data=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../doc/source/_static/data/economy/extension-scope.json'),'utf8'));
test('chips split variants and show account ranges; the detail lists one reading',()=>{
 const html=E.render(data);
 for(const c of data.categories)assert.ok(html.includes(`data-ext-card="${c.id}"`));
 const ghg=E.categoryRows(data,'ghg'),exio=ghg.filter(r=>r.family==='EXIOBASE');
 assert.deepEqual(exio.map(r=>r.variant).sort(),['Hybrid','Monetary']);
 const monetary=exio.find(r=>r.variant==='Monetary');assert.ok(monetary.min<monetary.max);assert.ok(monetary.readings.length>1);
 assert.match(html,/class="ext-gas" data-absent/);
 assert.ok(!html.includes('ext-without'));
 const {reading,labels}=E.readingLabels(data,'EXIOBASE','Monetary','ghg');
 assert.equal(reading.id,monetary.readings[0].id);assert.ok(labels.length>=monetary.min&&labels.length<=monetary.max);
 const other=monetary.readings.at(-1),d=E.detail(data,'EXIOBASE','Monetary','ghg',other.id);
 assert.equal((d.match(/<li>/g)||[]).length,E.readingLabels(data,'EXIOBASE','Monetary','ghg',other.id).labels.length);
 assert.match(d,/data-ext-reading/);
});
