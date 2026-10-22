// Run against a built documentation preview with Playwright and Chrome.
const {chromium}=require('playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const base=process.env.MARIO_DOCS_PREVIEW_URL||'http://127.0.0.1:8765/';
const out=process.env.MARIO_DOCS_QA_DIR||'/private/tmp/bonsai-explorer-qa';
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(new URL('resources/data-explorer/electricity_carbon_footprint.html',base).href,{waitUntil:'networkidle'});
  const tech=page.locator('.fig1'),note=tech.locator('[data-f1-source-note]');
  assert.match(await note.innerText(),/reference year 2016.*21 Oct 2026.*AR5/);
  assert.match(await note.innerText(),/Accelerated CO2 is excluded/);
  assert.equal(await page.locator('.fig2 [data-src="BONSAI"]').count(),0);
  await tech.locator('[data-src="BONSAI"]').dblclick();
  assert.equal(await tech.locator('[data-src][aria-pressed="true"]').count(),1);
  await tech.screenshot({path:path.join(out,'electricity-bonsai-ar5.png')});
  await tech.locator('[data-view="table"]').click();
  assert.ok(await tech.locator('#f1-tablewrap table').isVisible());
  const lifecycle=await tech.locator('#f1-tablewrap').innerText();
  await tech.locator('[data-flow="direct"]').click();
  const direct=await tech.locator('#f1-tablewrap').innerText();
  assert.notEqual(direct,lifecycle);
  await tech.screenshot({path:path.join(out,'electricity-direct-table.png')});
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));
  await tech.screenshot({path:path.join(out,'electricity-mobile-dark.png')});
  assert.deepEqual(errors,[]);
  console.log('BONSAI AR5 browser QA passed: source note, technology-only placement, source filter, direct/lifecycle table and mobile.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
