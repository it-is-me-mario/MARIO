// Validate the completed annual GLORIA browser and shared scope/downloads.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict'),path=require('path'),os=require('os');
const base=process.env.MARIO_DOCS_PREVIEW_URL||'http://127.0.0.1:8765/';
const output=process.env.MARIO_DOCS_QA_DIR||path.join(os.tmpdir(),'mario-gloria-years-qa');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
 page.setDefaultTimeout(20000);page.on('pageerror',e=>errors.push(e.message));
 await page.goto(new URL('resources/data-explorer/browsers.html',base).href,{waitUntil:'networkidle',timeout:60000});
 const root=page.locator('[data-economy-browser]'),ready=()=>page.waitForFunction(()=>document.querySelector('[data-economy-browser]')?.getAttribute('aria-busy')==='false',{},{timeout:60000});await ready();
 await root.locator('[data-mode="focus"]').click();await ready();await root.locator('[data-family]').selectOption('GLORIA');await ready();
 await root.locator('[data-picker="year"] > summary').click();
 assert.deepEqual(await root.locator('[data-subset="year"]').evaluateAll(ns=>ns.map(n=>Number(n.value)).sort()),[2022,2023,2024]);
 await root.locator('[data-bulk-filter="year"][data-bulk-action="select"]').click();await ready();await root.locator('[data-picker="year"] > summary').click();
 await root.locator('[data-metric]').selectOption('gdp');await ready();
 const chart=root.locator('[data-chart]');
 const years=()=>chart.evaluate(n=>[...new Set(n.data.filter(t=>t.type==='bar').flatMap(t=>t.x))].sort());
 assert.deepEqual(await years(),[2022,2023,2024]);
 assert.ok(await chart.evaluate(n=>n.data.some(t=>t.type==='bar'&&t.y.length===3)));
 assert.match(await root.locator('[data-indicator-note]').innerText(),/0\.186% source residual/);
 await root.screenshot({path:output+'/world-gdp-light.png'});
 await root.locator('[data-picker="year"] > summary').click();await root.locator('[data-subset="year"][value="2023"]').uncheck();await ready();await root.locator('[data-picker="year"] > summary').click();
 assert.deepEqual(await years(),[2022,2024]);
 await root.locator('[data-picker="country"] > summary').click();await root.locator('[data-country-search]').fill('Italy');await root.locator('[data-subset="country"][value="ITA"]').check();await ready();await root.locator('[data-picker="country"] > summary').click();
 await root.locator('[data-measure]').selectOption('per-capita');await ready();assert.match(await root.locator('[data-heading]').innerText(),/Italy/);
 const promise=page.waitForEvent('download');await root.locator('[data-export]').click();const csv=await fs.promises.readFile(await(await promise).path(),'utf8');fs.writeFileSync(output+'/italy-per-capita.csv',csv);
 assert.match(csv,/GLORIA/);assert.match(csv,/2022/);assert.match(csv,/2024/);assert.ok(!/"2023"/.test(csv));assert.match(csv,/CC BY-NC 3\.0/);
 await root.locator('[data-measure]').selectOption('total');await root.locator('[data-metric]').selectOption('ghg');await ready();assert.deepEqual(await years(),[2022,2024]);
 await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));await ready();await root.screenshot({path:output+'/italy-ghg-dark.png'});
 await root.locator('[data-picker="year"] > summary').click();await root.locator('[data-subset="year"][value="2024"]').uncheck();await ready();await root.locator('[data-picker="year"] > summary').click();
 await root.locator('[data-view="map"]').click();await ready();assert.ok(await root.locator('path[data-iso="ITA"]').count());await root.screenshot({path:output+'/ghg-map-2022-dark.png'});
 for(const route of ['notebooks/parsers/gloria/walkthrough_gloria.html','resources/material.html']){
  await page.goto(new URL(route,base).href,{waitUntil:'networkidle'});
  const links=page.locator('a[href*="gloria-060-2024-sut.xlsx"]');assert.equal(await links.count(),1);assert.match(await links.first().innerText(),/2022–2024/);
  const file=await page.request.get(await links.first().evaluate(n=>n.href));assert.equal(file.status(),200);
 }
 await page.goto(new URL('resources/data-explorer/scope.html',base).href,{waitUntil:'networkidle'});
 const data=await(await page.request.get(new URL('_static/data/economy/sectoral-scope.json',base).href)).json();const gloria=data.columns.activity.filter(c=>c.family==='GLORIA');assert.equal(gloria.length,1);assert.deepEqual(gloria[0].years,[2022,2023,2024]);assert.equal(gloria[0].native.length,120);
 assert.deepEqual(errors,[]);console.log(JSON.stringify({years:[2022,2023,2024],world_bar:true,subsets:true,italy_per_capita:true,ghg_map_2022:true,shared_downloads:true,sectoral_native:120,errors}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
