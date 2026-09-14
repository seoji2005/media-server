import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

const [base,phase,item,track,manualSubtitle]=process.argv.slice(2);
assert.match(base,/^http:\/\/127\.0\.0\.1:\d+$/);
assert(manualSubtitle);
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
  const savedPosition=()=>page.waitForFunction(()=>[...positionSaves.values()].every(state=>
    !state.running&&!state.pending&&state.latest?.saved&&!state.latest.failed),null,{timeout:5000});
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
    assert.equal(await page.locator('#subtitle-preparation').isVisible(),true);
    await page.locator('#subtitle-preparation').evaluate(e=>e.open=true);
    for(const id of ['subtitle-generate','subtitle-retranslate','subtitle-pause','subtitle-resume','subtitle-restart'])
      assert.equal(await page.locator('#'+id).isVisible(),false,`${id} stays unavailable in viewing-only mode`);
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
    const imports=[];const observe=request=>{
      const url=new URL(request.url());
      if(request.method()==='POST'&&url.pathname===`/api/library/${item}/subtitles`)imports.push(true);
    };page.on('request',observe);
    const beforeIds=state.tracks.map(t=>t.id);
    const receipt=page.waitForResponse(response=>response.request().method()==='POST'&&
      new URL(response.url()).pathname===`/api/library/${item}/subtitles`);
    await page.locator('#subtitle-input').setInputFiles(manualSubtitle);
    const importedResponse=await receipt;assert.equal(importedResponse.status(),201);
    // The product consumes the POST body and then confirms the saved status. Read
    // the resulting selection instead of asking DevTools to retain a second copy
    // of the response body beside active media requests.
    await page.waitForFunction(ids=>{const select=document.querySelector('#subtitle-select');
      return !select.disabled&&select.value&&!ids.includes(select.value);},beforeIds);
    const imported=await select.inputValue();
    assert.equal(imports.length,1);assert.match(await page.locator('#subtitle-state').textContent(),/자막/);
    assert.match(await(await page.request.get(base+`/api/library/${item}/subtitles/${imported}.vtt`)).text(),/직접 가져온 자막 확인/);
    page.off('request',observe);
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
    // Hold an actual write across close so this checks the pending-save contract
    // deterministically. A hidden dialog is not a commit acknowledgement.
    const positionURL=base+`/api/library/${item}/position`;
    let release;const gate=new Promise(resolve=>release=resolve);
    const hold=async route=>{
      await page.evaluate(()=>window.cloudPositionHeld=true);
      await gate;await route.continue();
    };
    await page.route(positionURL,hold,{times:1});
    try{
      await video.evaluate(v=>{v.pause();v.currentTime=18.25;});
      await page.waitForFunction(()=>!document.querySelector('#video').seeking&&window.cloudPositionHeld===true);
      await page.locator('#player-close').click();
      await page.waitForFunction(()=>!document.querySelector('#player-dialog').open);
      const pending=await(await page.request.get(base+`/api/library/${item}`)).json();
      assert(Math.abs(pending.position-18.25)>=.05,'held final seek must still be uncommitted after close');
      assert.equal(await page.locator('#position-notice').isVisible(),true);
      assert.match(await page.locator('#position-message').textContent(),/저장 중/);
      assert.match(await page.locator('#position-items button').textContent(),/보랏빛 산책/);
      await page.evaluate(()=>window.positionLeaveSentinel=true);
      const warning=page.waitForEvent('dialog',{timeout:2000});
      // Chromium can reject a cancelled reload. The retained document and
      // uncommitted DB state below establish cancellation, not that error text.
      const reload=page.reload({timeout:2000}).catch(()=>null);
      const prompt=await warning;assert.equal(prompt.type(),'beforeunload');await prompt.dismiss();
      // A cancelled Playwright reload can remain pending until its navigation
      // timeout. Do not spend the product's five-second save budget awaiting it.
      assert.equal(await page.evaluate(()=>window.positionLeaveSentinel),true);
      assert.equal(await page.locator('#player-dialog').evaluate(d=>d.open),false);
      const stillPending=await(await page.request.get(base+`/api/library/${item}`)).json();
      assert.equal(stillPending.position_revision,pending.position_revision,'cancelled leaving cannot submit another save');
      await page.setViewportSize({width:390,height:844});
      await page.locator('#position-notice').scrollIntoViewIfNeeded();
      assert(await page.locator('#position-notice').evaluate(e=>e.scrollWidth<=e.clientWidth+1));
      if(process.env.MEDIA_TEST_SCREENSHOT_DIR){
        await mkdir(process.env.MEDIA_TEST_SCREENSHOT_DIR,{recursive:true});
        await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,'pending-position-mobile.png'),timeout:2000});
      }
      await page.setViewportSize({width:1280,height:800});
      release();await savedPosition();
      await reload;assert.equal(await page.evaluate(()=>window.positionLeaveSentinel),true);
      assert.equal(await page.locator('#position-notice').isVisible(),false);
      console.log(JSON.stringify({phase,pendingPositionLeaveCancelled:true,confirmedSaveClearsNotice:true}));
    }finally{release();await page.unroute(positionURL,hold);}
    await page.reload();await open(true);await restored();
  }
  // The parent checks SQLite after this browser exits and restarts the server.
  // Confirm any ordinary resume/pause save before discarding this page too.
  await savedPosition();
  if(phase==='first'){
    const source=await video.evaluate(v=>({src:v.src,track:v.querySelector('track').src}));
    const seeked=async target=>{
      await page.waitForFunction(t=>{const v=document.querySelector('#video');return !v.seeking&&Math.abs(v.currentTime-t)<.05;},target);
      await savedPosition();
      const stored=await(await page.request.get(base+`/api/library/${item}`)).json();
      assert(Math.abs(stored.position-target)<.05,'keyboard seek must persist through the actual API');
      assert(await video.evaluate(v=>v.paused),'seeking cannot start a paused video');
    };
    await page.locator('#player-close').focus();
    await page.keyboard.press('j');await seeked(8.25);
    await page.keyboard.press('l');await seeked(18.25);
    await page.keyboard.press('k');await page.waitForFunction(()=>!document.querySelector('#video').paused&&document.querySelector('#video').currentTime>18.35);
    await page.keyboard.press('k');assert(await video.evaluate(v=>v.paused));await savedPosition();
    const stopped=await video.evaluate(v=>v.currentTime);
    await page.locator('#title-panel').evaluate(e=>e.open=true);
    const title=await page.locator('#title-input').inputValue();
    await page.locator('#title-input').focus();await page.keyboard.type('jkl');
    assert.equal(await video.evaluate(v=>v.currentTime),stopped);assert(await video.evaluate(v=>v.paused));
    await page.locator('#title-input').fill(title);await page.locator('#title-panel').evaluate(e=>e.open=false);
    assert.deepEqual(await video.evaluate(v=>({src:v.src,track:v.querySelector('track').src})),source);
    // Restore the established first/restart fixture after checking actual keys.
    await video.evaluate(v=>v.currentTime=18.25);await seeked(18.25);
    console.log(JSON.stringify({phase,nativePlaybackShortcuts:true,keyboardPositionPersisted:true,inputDoesNotSeek:true}));
  }
  if(process.env.MEDIA_TEST_SCREENSHOT_DIR){
    await mkdir(process.env.MEDIA_TEST_SCREENSHOT_DIR,{recursive:true});
    await page.locator('.playback-shortcuts').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`codespaces-${phase}.png`)});
    await page.setViewportSize({width:390,height:844});
    await page.locator('.playback-shortcuts').scrollIntoViewIfNeeded();
    assert(await page.locator('#player-dialog').evaluate(e=>e.scrollWidth<=e.clientWidth+1));
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`codespaces-${phase}-mobile.png`)});
  }
  assert.deepEqual(errors,[]);assert.equal(egress.length,0);
  console.log(JSON.stringify({phase,chrome:browser.version(),realSyntheticPlayback:true,
    nativeCaptions:true,crossCueSearch:phase==='first',positionAndSettingsRestored:true,
    manualCaptionImported:phase==='first',codespacesEdge:'simulated',externalPageRequests:0}));
}finally{await browser.close();}
