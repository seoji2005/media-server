import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

// Real imported VTT/native cues on the existing 20-second synthetic video.
// Run after restart's existing caption checks, so their original fixture stays fixed.
export default async function checkSubtitleSearchPages(page,trackId){
  const video=page.locator('#video'),selector=page.locator('#subtitle-select');
  const before=await video.evaluate(v=>({src:v.src,time:v.currentTime,paused:v.paused,track:v.querySelector('track').src}));
  assert(before.paused);assert.match(before.track,/offset_ms=500$/);
  const captionBytes=await (await page.request.get(before.track)).body();
  const stamp=ms=>`00:00:${String(Math.floor(ms/1000)).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`;
  const vtt='WEBVTT\n\n'+Array.from({length:115},(_,i)=>`${stamp(1000+i*150)} --> ${stamp(1140+i*150)}\n탐색\n장면 ${String(i+1).padStart(3,'0')}\n`).join('\n');
  const imported=page.waitForResponse(r=>r.request().method()==='POST'&&/\/subtitles\?/.test(r.url()));
  await page.locator('#subtitle-input').setInputFiles({name:'search-pages.vtt',mimeType:'text/vtt',buffer:Buffer.from(vtt)});
  const response=await imported;assert.equal(response.status(),201);const {id}=await response.json();
  await page.waitForFunction(id=>document.querySelector('#subtitle-select').value===id&&!document.querySelector('#subtitle-select').disabled&&document.querySelector('#video track')?.readyState===2,id);
  await page.locator('#caption-view-panel').evaluate(el=>el.open=true);
  await page.locator('#caption-later').click();
  await page.waitForFunction(()=>!document.querySelector('#subtitle-select').disabled&&document.querySelector('#video track')?.readyState===2&&document.querySelector('#video track').src.endsWith('offset_ms=500'));
  assert.equal(await video.evaluate(v=>[...v.textTracks].find(t=>t.mode==='showing').cues.length),115);
  const commands=[],queryRequests=[],positionWrites=[];
  const observe=r=>{
    if(r.method()==='POST'&&(/\/subtitle-jobs(?:\/|\?|$)/.test(r.url())||r.url().endsWith('/retranslate')))commands.push(true);
    if((r.url()+(r.postData()||'')).includes('탐색'))queryRequests.push(true);
    if(r.method()==='PUT'&&r.url().endsWith('/position'))positionWrites.push(true);
  };
  page.on('request',observe);
  const query=page.locator('#subtitle-query'),results=page.locator('#subtitle-results button'),next=page.locator('#subtitle-page-next');
  await page.locator('#subtitle-search-panel').evaluate(el=>el.open=true);
  await query.fill('탐색　장면');
  await page.waitForFunction(()=>document.querySelector('#subtitle-search-status').textContent.includes('115개'));
  assert.equal(await results.count(),50);assert.equal(await page.locator('#subtitle-page-previous').isEnabled(),false);
  await next.focus();await page.keyboard.press('Enter');
  assert.match(await page.locator('#subtitle-search-status').textContent(),/51–100/);
  assert(await results.first().evaluate(el=>el===document.activeElement));
  await next.click();assert.equal(await results.count(),15);
  assert.match(await page.locator('#subtitle-search-status').textContent(),/101–115/);
  assert.equal(await next.isEnabled(),false);
  assert.deepEqual(await video.evaluate(v=>({src:v.src,time:v.currentTime,paused:v.paused})),{src:before.src,time:before.time,paused:before.paused});
  assert.equal(positionWrites.length,0,'paging never saves a speculative watch position');
  if(process.env.MEDIA_TEST_SCREENSHOT_DIR){
    await mkdir(process.env.MEDIA_TEST_SCREENSHOT_DIR,{recursive:true});
    for(const [size,label] of [[{width:1280,height:720},'desktop'],[{width:390,height:844},'mobile']]){
      await page.setViewportSize(size);await query.scrollIntoViewIfNeeded();
      assert(await page.locator('#player-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
      await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`restart-search-pages-${label}.png`)});
    }
  }
  // The last cue starts at 18.1 s plus the saved +0.5 s offset.
  const saved=page.waitForResponse(r=>r.request().method()==='PUT'&&r.url().endsWith('/position')&&r.request().postDataJSON().position>=18.6&&r.status()===200);
  await results.last().click();await saved;await video.evaluate(v=>v.pause());
  const sought=await video.evaluate(v=>({time:v.currentTime,error:v.error?.code??null,top:v.getBoundingClientRect().top,bottom:v.getBoundingClientRect().bottom}));
  assert(sought.time>=18.6&&sought.time<19.5);assert.equal(sought.error,null);
  assert(sought.top<844&&sought.bottom>0,'late result brings the player back into view');
  // Same native VTT fixture: phrase starts in cue 114 and ends in cue 115.
  // Keep the existing +500 ms offset and completed-seek persistence route.
  await query.fill('장면 114 탐색 장면 115');
  await page.waitForFunction(()=>document.querySelector('#subtitle-search-status').textContent.includes('1개 일치'));
  assert.equal(await results.count(),1);
  assert.match(await results.first().textContent(),/114[\s\S]*115/);
  const joinedSaved=page.waitForResponse(r=>r.request().method()==='PUT'&&r.url().endsWith('/position')&&r.request().postDataJSON().position>=18.45&&r.request().postDataJSON().position<18.6&&r.status()===200);
  await results.first().click();await joinedSaved;await video.evaluate(v=>v.pause());
  const joinedTime=await video.evaluate(v=>v.currentTime);
  assert(joinedTime>=18.45&&joinedTime<19.5);
  assert.equal(commands.length,0);assert.equal(queryRequests.length,0);
  page.off('request',observe);
  await page.setViewportSize({width:1280,height:720});
  await page.locator('#caption-view-panel').evaluate(el=>el.open=true);
  await selector.selectOption(trackId);await page.locator('#caption-later').click();
  await page.waitForFunction(src=>!document.querySelector('#subtitle-select').disabled&&document.querySelector('#video track')?.readyState===2&&document.querySelector('#video track').src===src,before.track);
  assert.equal(await results.count(),0,'changing captions removes the old result page');
  assert.equal(await page.locator('#subtitle-pages').isVisible(),false);
  assert((await (await page.request.get(before.track)).body()).equals(captionBytes),'existing caption output is byte-identical');
  await query.fill('');await page.locator('#subtitle-search-panel').evaluate(el=>el.open=false);
}
