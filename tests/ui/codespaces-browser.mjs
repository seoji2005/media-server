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
  async function open(expectRestore=false){
    if(expectRestore){
      const saved=await(await page.request.get(base+`/api/library/${item}`)).json();
      assert(Math.abs(saved.position-18.25)<.05,'stored position must survive before opening');
      // Same observation pattern as browser.mjs: capture the app's real seek
      // before optional autoplay passes the assertion window. Never set a time.
      await video.evaluate(v=>{
        window.cloudResumeObservation=null;
        v.addEventListener('loadedmetadata',()=>{
          v.addEventListener('seeked',()=>{
            window.cloudResumeObservation=v.currentTime;
            v.pause();
          },{once:true});
        },{once:true});
      });
    }
    await page.locator('.card-button').filter({hasText:'보랏빛 산책'}).click();
    await page.waitForFunction(()=>document.querySelector('#video').readyState>=2&&
      document.querySelector('#video track')?.readyState===2);
    assert(await page.locator('#player-dialog .cloud-notice').isVisible());
    assert.equal(await page.locator('#subtitle-preparation').isVisible(),false);
  }
  async function restored(){
    try{
      await page.waitForFunction(()=>window.cloudResumeObservation!==null&&!document.querySelector('#video').seeking);
      const observed=await video.evaluate(v=>({position:window.cloudResumeObservation,paused:v.paused}));
      assert(Math.abs(observed.position-18.25)<.05,'native seek must restore the saved position');
      assert(observed.paused);
      console.log(JSON.stringify({phase,stage:'native-resume-observed',...observed}));
    }catch(error){
      console.log(JSON.stringify({phase,stage:'native-resume-failed',...await video.evaluate(v=>({
        observed:window.cloudResumeObservation,currentTime:v.currentTime,paused:v.paused,
        seeking:v.seeking,readyState:v.readyState,mediaError:v.error?.code??null}))}));
      throw error;
    }
    assert.equal(await select.inputValue(),track);
    assert.match(await page.locator('#video track').getAttribute('src'),/offset_ms=500$/);
  }
  await page.goto(base);await open(phase==='restart');
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
    await page.reload();await open(true);await restored();
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
