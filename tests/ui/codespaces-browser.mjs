import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

const [base,phase,item,track]=process.argv.slice(2);
assert.match(base,/^http:\/\/127\.0\.0\.1:\d+$/);
const browser=await chromium.launch({headless:true,channel:process.env.MEDIA_TEST_BROWSER_CHANNEL||'chrome'});
try{
  const page=await browser.newPage({viewport:{width:1280,height:800}});
  page.setDefaultTimeout(15000);
  const errors=[],egress=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{
    if(new URL(route.request().url()).origin!==base){egress.push(true);return route.abort();}
    return route.continue();
  });
  const video=page.locator('#video'),select=page.locator('#subtitle-select');
  async function open(){
    await page.locator('.card-button').filter({hasText:'보랏빛 산책'}).click();
    await page.waitForFunction(()=>document.querySelector('#video').readyState>=2&&
      document.querySelector('#video track')?.readyState===2);
    assert(await page.locator('#player-dialog .cloud-notice').isVisible());
    assert.equal(await page.locator('#subtitle-preparation').isVisible(),false);
  }
  async function restored(){
    await page.waitForFunction(()=>Math.abs(document.querySelector('#video').currentTime-18.25)<.05);
    assert.equal(await select.inputValue(),track);
    assert.match(await page.locator('#video track').getAttribute('src'),/offset_ms=500$/);
  }
  await page.goto(base);await open();
  if(phase==='restart')await restored();
  else{
    const state=await(await page.request.get(base+`/api/library/${item}/subtitles`)).json();
    await select.selectOption(state.tracks.find(t=>t.language==='en').id);
    await page.waitForFunction(()=>!document.querySelector('#subtitle-select').disabled);
    await select.selectOption(track);
    await page.waitForFunction(()=>!document.querySelector('#subtitle-select').disabled&&document.querySelector('#video track')?.readyState===2);
    await page.locator('#caption-view-panel').evaluate(e=>e.open=true);
    await page.locator('#caption-later').click();
    await page.waitForFunction(()=>!document.querySelector('#subtitle-select').disabled&&
      document.querySelector('#video track')?.readyState===2&&document.querySelector('#video track').src.endsWith('offset_ms=500'));
    await page.locator('#subtitle-search-panel').evaluate(e=>e.open=true);
    await page.locator('#subtitle-query').fill('하늘 아래 천천히');
    await page.locator('#subtitle-results button').first().waitFor();
    assert.equal(await page.locator('#subtitle-results button').count(),1);
    await page.locator('#subtitle-results button').click();
    await page.waitForFunction(()=>{const v=document.querySelector('#video');return v.currentTime>=4.45&&v.currentTime<5;});
    await video.evaluate(v=>v.play());
    await page.waitForFunction(()=>document.querySelector('#video').getVideoPlaybackQuality().totalVideoFrames>5);
    await video.evaluate(v=>{v.pause();v.currentTime=18.25;});
    await page.waitForFunction(()=>!document.querySelector('#video').seeking);
    await page.locator('#player-close').click();
    await page.waitForFunction(()=>!document.querySelector('#player-dialog').open);
    await page.reload();await open();await restored();
  }
  if(process.env.MEDIA_TEST_SCREENSHOT_DIR){
    await mkdir(process.env.MEDIA_TEST_SCREENSHOT_DIR,{recursive:true});
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`codespaces-${phase}.png`)});
    await page.setViewportSize({width:390,height:844});
    assert(await page.locator('#player-dialog').evaluate(e=>e.scrollWidth<=e.clientWidth+1));
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`codespaces-${phase}-mobile.png`)});
  }
  assert.deepEqual(errors,[]);assert.equal(egress.length,0);
  console.log(JSON.stringify({phase,chrome:browser.version(),realSyntheticPlayback:true,
    nativeCaptions:true,crossCueSearch:phase==='first',positionAndSettingsRestored:true,
    codespacesEdge:'simulated',externalPageRequests:0}));
}finally{await browser.close();}
