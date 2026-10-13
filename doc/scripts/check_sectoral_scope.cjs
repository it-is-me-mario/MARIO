const {chromium}=require('playwright');
// Run against the built preview with Playwright installed (Chrome channel).
const fs=require('fs'),assert=require('assert/strict'),path=require('path'),os=require('os');
const base=process.env.MARIO_DOCS_PREVIEW_URL||'http://127.0.0.1:8765/';
const output=process.env.MARIO_DOCS_QA_DIR||path.join(os.tmpdir(),'mario-sectoral-scope-qa');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
 const assets=process.env.MARIO_DOCS_QA_ASSETS;
 if(assets)await page.route('**/_static/**',async route=>{
  const suffix=new URL(route.request().url()).pathname.split('/_static/')[1],file=path.resolve(assets,suffix||'');
  if(file.startsWith(path.resolve(assets)+path.sep)&&fs.existsSync(file))await route.fulfill({path:file});else await route.continue();
 });
 page.setDefaultTimeout(15000);page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE',e.message)});
 await page.goto(new URL('resources/data-explorer/scope.html#sectoral-coverage',base).href,{waitUntil:'networkidle',timeout:60000});
 const root=page.locator('[data-sectoral-scope]');await root.scrollIntoViewIfNeeded();await page.waitForFunction(()=>document.querySelector('[data-sectoral-scope]')?.getAttribute('aria-busy')==='false');
 const chart=page.locator('[data-ss-chart]');
 await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.data?.[1]?.z.length===651);
 assert.equal(await chart.evaluate(n=>n.data[1].z[0].length),8);
 assert.match(await root.locator('[data-ss-count]').innerText(),/651 \/ 651/);
 assert.ok(!(await chart.evaluate(n=>n.layout.xaxis.ticktext.join(' '))).includes('Hybrid'));assert.match(await chart.evaluate(n=>n.layout.xaxis.ticktext.join(' ')),/GTAP/);
 assert.deepEqual(await chart.evaluate(n=>n.data[1].colorscale),[[0,'#6dd0e5'],[.5,'#fdca27'],[1,'#fc6b3c']]);assert.equal(await chart.evaluate(n=>n.data[1].colorbar.ticktext[0]),'0');assert.equal(await chart.evaluate(n=>n.data[1].colorbar.title.text),'Linked classes');assert.equal(await chart.evaluate(n=>n.data[1].colorbar.orientation),'v');assert.equal(await root.locator('.ss-scale').count(),0);assert.match(await root.locator('.ss-key').innerText(),/^Concordance unverified$/);assert.deepEqual(await chart.evaluate(n=>n.layout.annotations.map(a=>a.text)),['Coarser than<br>NACE','Finer than<br>NACE']);assert.equal(await chart.evaluate(n=>n.layout.yaxis.title.text),'NACE Rev. 2.1');await root.screenshot({path:path.join(output,'overview-light.png')});
 assert.ok(await root.locator('.ss-chart-scroll').evaluate(n=>n.scrollWidth<=n.clientWidth+1));
 await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.getAttribute('aria-busy')==='false');await root.screenshot({path:path.join(output,'overview-all-dark.png')});
 await page.evaluate(()=>document.documentElement.setAttribute('data-theme','light'));await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.getAttribute('aria-busy')==='false');
 // Navigate section -> division -> group -> class, without reducing row membership.
 await root.locator('[data-ss-picker] > summary').click();
 await root.locator('[data-ss-options] [data-ss-area="A"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.data?.[1]?.z.length<651);
 const aCount=await chart.evaluate(n=>n.data[1].z.length);assert.ok(aCount>1);
 await root.locator('[data-ss-options] [data-ss-area="01"]').click();
 await root.locator('[data-ss-options] [data-ss-area="01.1"]').click();
 await root.locator('[data-ss-options] [data-ss-area="01.11"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.data?.[1]?.z.length===1);
 assert.match(await root.locator('[data-ss-detail]').innerText(),/01\.11/);
 assert.equal(await root.locator('[data-ss-native-database]').count(),8);
 assert.match(await root.locator('[data-ss-detail]').innerText(),new RegExp('Section A contains '+aCount));
 const adb=root.locator('[data-ss-native-database]').filter({has:page.locator('.ss-native-heading strong',{hasText:'ADB'})});
 assert.match(await adb.innerText(),/c1/);assert.match(await adb.innerText(),new RegExp(aCount+' / '+aCount));
 await adb.locator('.ss-native > summary').first().click();await adb.locator('.ss-intermediates > summary').first().click();
 assert.match(await adb.innerText(),/ISIC3\.1/);assert.match(await adb.innerText(),/NACE2\.1/);
 await root.locator('[data-ss-databases] > summary').click();await root.locator('[data-ss-select="all"]').click();await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.data?.[1]?.z[0]?.length===9);await root.locator('[data-ss-databases] > summary').click();
 const hybrid=root.locator('[data-ss-native-database]').filter({has:page.locator('.ss-native-heading strong',{hasText:'EXIOBASE · Hybrid'})});assert.match(await hybrid.innerText(),/164 native categories/);assert.match(await hybrid.locator('.ss-resolution').innerText(),/1\/3.*3 native sectors/);await hybrid.locator(':scope > .ss-native > summary').first().click();await hybrid.locator(':scope > .ss-native .ss-intermediates > summary').first().click();assert.match(await hybrid.innerText(),/EX3h/);
 const gloria=root.locator('[data-ss-native-database]').filter({has:page.locator('.ss-native-heading strong',{hasText:'GLORIA'})});
 assert.match(await gloria.innerText(),/1\/4/);
 assert.ok(await chart.evaluate(n=>n.data[1].z[0][5]!==null));
 const wheat=gloria.locator('.ss-native').filter({has:page.locator('summary',{hasText:'Growing wheat'})});await wheat.locator('> summary').click();await wheat.locator('.ss-intermediates > summary').first().click();await wheat.locator('.ss-intermediates > summary').last().click();
 assert.match(await wheat.innerText(),/NXB/);assert.match(await wheat.innerText(),/editorial nxbase mapping/);
 await root.screenshot({path:path.join(output,'class-light.png')});
 // CSV carries the displayed code, fixed denominator, provenance and precise relation.
 const downloadPromise=page.waitForEvent('download');await root.locator('[data-ss-csv]').click();const download=await downloadPromise;const csv=await fs.promises.readFile(await download.path(),'utf8');
 assert.match(csv,/original_section_classes/);assert.match(csv,/01\.11/);assert.match(csv,/https:\/\/unstats/);assert.match(csv,/Reviewed native activity scope/);assert.match(csv,/"partial"/);
 assert.match(csv,/GLORIA/);assert.match(csv,/reviewed_editorial/);
 // Published FIGARO and WIOD ranges enter colours and expose their nxbase lineage.
 if(!await root.locator('[data-ss-databases]').evaluate(n=>n.open))await root.locator('[data-ss-databases] > summary').click();await root.locator('[data-ss-select="all"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.data?.[1]?.z[0]?.length===9);
 const figaro=root.locator('[data-ss-native-database]').filter({has:page.locator('.ss-native-heading strong',{hasText:'FIGARO'})});
 assert.match(await figaro.innerText(),/A01/);assert.match(await figaro.innerText(),/Crop and animal production/);
 await figaro.locator(':scope > .ss-native > summary').first().click();await figaro.locator('.ss-intermediates > summary').last().click();assert.match(await figaro.innerText(),/FIGARO.*NACE2.*NACE2\.1/s);
 const wiod=root.locator('[data-ss-native-database]').filter({has:page.locator('.ss-native-heading strong',{hasText:'WIOD'})});
 assert.match(await wiod.innerText(),/A01/);await wiod.locator(':scope > .ss-native > summary').first().click();await wiod.locator('.ss-intermediates > summary').last().click();assert.match(await wiod.innerText(),/WIOD16.*NACE2.*NACE2\.1/s);
 if(assets){assert.equal(JSON.parse(fs.readFileSync(path.join(assets,'data/economy/nxbase-figaro-wiod.json'))).items.length,176);}else{const published=await page.request.get(new URL('_static/data/economy/nxbase-figaro-wiod.json',base).href);assert.equal(published.status(),200);assert.equal((await published.json()).items.length,176);}
 assert.match(csv,/FIGARO/);assert.match(csv,/WIOD/);await root.screenshot({path:path.join(output,'figaro-wiod-class-light.png')});
 if(!await root.locator('[data-ss-databases]').evaluate(n=>n.open))await root.locator('[data-ss-databases] > summary').click();
 await root.locator('[data-ss-select="none"]').click();await page.waitForSelector('[data-ss-chart] .ss-empty');
 await root.locator('[data-ss-column]').first().check();await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.data?.[1]?.z[0]?.length===1);
 // Restore the three initial database routes for the existing interaction checks.
 const dbs=await root.locator('[data-ss-column]').evaluateAll(ns=>ns.map(n=>({id:n.dataset.ssColumn,name:n.closest('label').innerText})));
 for(const d of dbs)if(/^(ADB|CEDA)\b/.test(d.name))await root.locator(`[data-ss-column="${d.id}"]`).check();
 await root.locator('[data-ss-databases] > summary').click();
 await root.locator('[data-ss-path] [data-ss-area=""]').click();await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.data?.[1]?.z.length===651);
 // Actual heatmap hover and click resolve nonuniform row geometry correctly.
 await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.getAttribute('aria-busy')==='false' && document.querySelector('[data-ss-chart]')?._fullLayout?.height===720);await chart.scrollIntoViewIfNeeded();assert.deepEqual(await chart.evaluate(n=>n._fullLayout.xaxis.range),[-.5,2.5]);assert.ok(await chart.evaluate(n=>n._fullLayout._size.w>n.clientWidth*.7));
 const point=await chart.evaluate(n=>{const l=n._fullLayout,r=n.getBoundingClientRect();const row=10;const y=(n.data[1].y[row]+n.data[1].y[row+1])/2;return {x:r.x+l._size.l+l.xaxis.l2p(2),y:r.y+l._size.t+l.yaxis.l2p(y)};});
 await page.mouse.move(point.x,point.y);await page.waitForSelector('.hoverlayer .hovertext');assert.match(await page.locator('.hoverlayer').last().textContent(),/CEDA/);
 const hoverCode=(await page.locator('.hoverlayer').last().textContent()).match(/CEDA · (\d{2}\.\d{2})/)[1];await page.mouse.click(point.x,point.y);await page.waitForFunction(()=>document.querySelector('[data-ss-chart]').layout.shapes.some(s=>s.name==='ss-selection-outline'));assert.match(await root.locator('[data-ss-selection-status]').innerText(),/CEDA/);assert.ok((await root.locator('.ss-detail-heading h3').innerText()).startsWith(hoverCode));
 const initial=await chart.evaluate(n=>n.layout.yaxis.range.slice());await root.locator('[data-ss-zoom="in"]').click();
 await page.waitForFunction(()=>{const n=document.querySelector('[data-ss-chart]');return n.layout.yaxis.range[0]-n.layout.yaxis.range[1]<n.data[0].y.at(-1);});
 await root.locator('[data-ss-zoom="reset"]').click();await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.getAttribute('aria-busy')==='false');assert.deepEqual(await chart.evaluate(n=>n.layout.yaxis.range),initial);
 // Dark palette, mobile layout and row labels separate from row data.
 await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.getAttribute('aria-busy')==='false');
 await page.waitForFunction(()=>getComputedStyle(document.querySelector('[data-sectoral-scope]')).getPropertyValue('--ss-coarse').trim()==='#fc6b3c');
 assert.equal(await chart.locator('.ytick text').count(),22);assert.ok(await chart.locator('.ytick text').first().evaluate(n=>getComputedStyle(n).fill==='rgb(243, 241, 236)'));await root.screenshot({path:path.join(output,'overview-dark.png')});
 await page.setViewportSize({width:390,height:844});await root.scrollIntoViewIfNeeded();
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await root.locator('[data-ss-picker] > summary').click();await root.locator('[data-ss-search]').fill('01.12');await root.locator('[data-ss-options] [data-ss-area="01.12"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.data?.[1]?.z.length===1);
 await root.screenshot({path:path.join(output,'mobile-dark.png')});
 await page.evaluate(()=>document.documentElement.setAttribute('data-theme','light'));assert.ok(await root.locator('[data-ss-labels]').isDisabled());assert.equal(await root.locator('[data-ss-labels]').inputValue(),'4');await root.screenshot({path:path.join(output,'mobile-light.png')});
 // Native refinement: aluminium has two EXIOBASE categories in one NACE class.
 await page.setViewportSize({width:1440,height:1050});
 await root.locator('[data-ss-picker] > summary').click();await root.locator('[data-ss-search]').fill('24.42');await root.locator('[data-ss-options] [data-ss-area="24.42"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.getAttribute('aria-busy')==='false');
 const exio=root.locator('[data-ss-native-database]').filter({has:page.locator('.ss-native-heading strong',{hasText:'EXIOBASE'})});
 assert.match(await exio.locator('.ss-resolution').innerText(),/1\/2.*2 native sectors/);
 assert.equal(await chart.evaluate(n=>n.data[1].z[0][0]),.025);
 await chart.scrollIntoViewIfNeeded();const cell=await chart.evaluate(n=>{const l=n._fullLayout,r=n.getBoundingClientRect();return {x:r.x+l._size.l+l.xaxis.l2p(0),y:r.y+l._size.t+l.yaxis.l2p((n.data[1].y[0]+n.data[1].y[1])/2)};});
 await page.mouse.click(cell.x,cell.y);await page.waitForFunction(()=>document.querySelector('[data-ss-chart]').layout.shapes.some(s=>s.name==='ss-selection-outline'));
 assert.deepEqual(await chart.evaluate(n=>{const s=n.layout.shapes.find(s=>s.name==='ss-selection-outline');return [s.x0,s.x1,s.y0,s.y1];}),[-.5,.5,0,25]);
 assert.match(await root.locator('[data-ss-selection-label]').innerText(),/24\.42.*EXIOBASE/);
 await root.screenshot({path:path.join(output,'refinement-selected-light.png')});
 const refinementDownload=page.waitForEvent('download');await root.locator('[data-ss-csv]').click();const refinedCSV=await fs.promises.readFile(await (await refinementDownload).path(),'utf8');assert.match(refinedCSV,/resolution_index/);assert.match(refinedCSV,/"0\.5","2","exclusive_native_split"/);
 await root.locator('[data-ss-show-details]').click();await page.waitForFunction(()=>{const h=document.querySelector('.ss-detail-heading').getBoundingClientRect();return h.top>=0&&h.top<innerHeight;});
 await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.getAttribute('aria-busy')==='false');assert.equal(await chart.evaluate(n=>n.layout.shapes.find(s=>s.name==='ss-selection-outline').line.color),'#f3f1ec');
 await root.screenshot({path:path.join(output,'refinement-selected-dark.png')});
 await root.locator('[data-ss-close]').click();await page.waitForFunction(()=>!document.querySelector('[data-ss-chart]').layout.shapes.some(s=>s.name==='ss-selection-outline'));assert.ok(await root.locator('[data-ss-show-details]').isHidden());
 // Electricity: reviewed activity containment wins over old producer/revision links.
 await root.locator('[data-ss-picker] > summary').click();await root.locator('[data-ss-search]').fill('35.11');await root.locator('[data-ss-options] [data-ss-area="35.11"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.getAttribute('aria-busy')==='false');
 assert.match(await exio.locator('.ss-resolution').innerText(),/1\/4.*4 native sectors/);
 assert.equal(await exio.locator(':scope > .ss-native').count(),4);
 assert.equal(await chart.evaluate(n=>n.data[1].z[0][0]),.0125);
 const confirmed=await exio.locator(':scope > .ss-native > summary').allTextContents();assert.ok(confirmed.every(t=>!/hydro|wind|solar|Geothermal|biomass| nec/i.test(t)));
 await exio.locator(':scope > .ss-native > summary').first().click();await exio.locator(':scope > .ss-native .ss-intermediates > summary').first().click();
 assert.match(await exio.locator(':scope > .ss-native').first().innerText(),/NXB.*powerCO/s);assert.match(await exio.locator(':scope > .ss-native').first().innerText(),/activity!A1230:H1230/);
 const pending=exio.locator('.ss-pending-categories');assert.match(await pending.locator('> summary').innerText(),/2 additional native categories/);await pending.locator('> summary').click();
 await pending.locator('.ss-native > summary').last().click();assert.match(await pending.innerText(),/editorial hypothesis/);
 const electricityDownload=page.waitForEvent('download');await root.locator('[data-ss-csv]').click();const electricityCSV=await fs.promises.readFile(await (await electricityDownload).path(),'utf8');fs.writeFileSync(path.join(output,'electricity.csv'),electricityCSV);
 assert.match(electricityCSV,/"0\.25","4","exclusive_native_split","true"/);assert.match(electricityCSV,/"pending","false"/);
 const source=await page.request.get(new URL('_static/data/economy/nxbase-activity-refinements.json',base).href);assert.equal(source.status(),200);assert.equal((await source.json()).items.length,12);
 await root.screenshot({path:path.join(output,'electricity-nxbase-dark.png')});
 await page.evaluate(()=>document.documentElement.setAttribute('data-theme','light'));await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.getAttribute('aria-busy')==='false');await root.screenshot({path:path.join(output,'electricity-nxbase-light.png')});
 await root.locator('[data-ss-picker] > summary').click();await root.locator('[data-ss-search]').fill('35.12');await root.locator('[data-ss-options] [data-ss-area="35.12"]').click();
 await page.waitForFunction(()=>document.querySelector('[data-ss-chart]')?.getAttribute('aria-busy')==='false');assert.match(await exio.locator('.ss-resolution').innerText(),/1\/6.*6 native sectors/);assert.equal(await exio.locator(':scope > .ss-native').count(),6);
 assert.deepEqual(errors,[]);console.log(JSON.stringify({classes:651,default_columns:8,available_columns:9,section_A:aCount,csv_bytes:csv.length,errors}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
