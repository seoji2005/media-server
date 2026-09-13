import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';
import checkItemEntry from './item-entry-browser.mjs';
import checkSubtitleSearchPages from './subtitle-search-browser.mjs';
import checkVP9Playback from './vp9-playback-browser.mjs';

const [base, source, subtitle, phase] = process.argv.slice(2);
assert.match(base, /^http:\/\/127\.0\.0\.1:\d+$/);
assert(['first', 'restart'].includes(phase));
// Fixed labels only: a hard timeout must identify its stage without logging paths,
// requests, dialogue or credentials. This adds no retry or timeout extension.
const mark=stage=>console.log(JSON.stringify({phase,stage}));
// Branded Chrome/Edge for proprietary codecs. An explicit executable supports cloud QA.
const executablePath = process.env.MEDIA_TEST_BROWSER_EXECUTABLE;
const channel = process.env.MEDIA_TEST_BROWSER_CHANNEL || 'chrome';
mark('browser-launch');
const browser = await chromium.launch({headless: true,
  ...(executablePath ? {executablePath} : {channel})});
const page = await browser.newPage();
page.setDefaultTimeout(15000);
const errors = [], external = [], ranges = [];
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => {
  if (new URL(response.url()).pathname.endsWith('/content')) ranges.push(response.status());
});
// Fail before any unexpected page egress; record only a count, not private URLs.
await page.route('**/*', route => {
  if (new URL(route.request().url()).origin !== base) {
    external.push(true);
    return route.abort();
  }
  return route.continue();
});
const video = page.locator('#video');
async function checkSessionRecovery(){
  await video.evaluate(v=>v.pause());
  await page.locator('#title-panel > summary').click();
  const title=await page.locator('#title-input').inputValue();
  await page.locator('#title-input').fill('연결 복구 확인용 입력');
  const snapshot=()=>page.evaluate(()=>({time:document.querySelector('#video').currentTime,
    src:document.querySelector('#video').src,track:document.querySelector('#video track')?.src,
    selection:document.querySelector('#subtitle-select').value,
    offset:document.querySelector('#caption-offset-brief').textContent,
    draft:document.querySelector('#title-input').value}));
  const before=await snapshot();
  // Only this browser request carries an expired credential. The real server
  // rejects it; reconnect reads the genuine session and never replays the title.
  await page.route(base+'/api/library/*/title',route=>route.continue({
    headers:{...route.request().headers(),'x-media-token':'expired-fixture'}}),{times:1});
  await page.locator('#title-save').click();
  await page.locator('#session-reconnect').waitFor();
  assert.equal(await page.locator('#player-dialog #session-recovery').isVisible(),true);
  const writes=[];const observe=request=>{if(!['GET','HEAD'].includes(request.method()))writes.push(true);};
  page.on('request',observe);
  await page.locator('#session-reconnect').click();
  await page.locator('#session-recovery').waitFor({state:'hidden'});
  assert.deepEqual(await snapshot(),before,'reconnect preserves viewing and unsaved draft');
  assert.deepEqual(writes,[],'reconnect cannot replay any write');page.off('request',observe);
  assert.equal(await page.locator('#title-save').isDisabled(),true);
  // The feature's own explicit state check remains required before editing.
  await page.locator('#title-reload').click();
  await page.waitForFunction(()=>!document.querySelector('#title-save').disabled);
  await page.locator('#title-input').fill(title);
  await page.locator('#title-panel > summary').click();
}
async function armResumeObservation() {
  const items = (await (await page.request.get(`${base}/api/library`)).json()).items;
  assert.equal(items.length, 1);
  assert(Math.abs(items[0].position - 7) < .25, 'stored resume fixture must remain seven seconds');
  await video.evaluate(v => {
    window.resumeObservation = null;
    // Observe the app's seek before autoplay can leave the narrow assertion
    // window. Never assign currentTime here: a wrong restore must still fail.
    v.addEventListener('loadedmetadata', () => {
      v.addEventListener('seeked', () => {
        window.resumeObservation = v.currentTime;
        v.pause();
      }, {once: true});
    }, {once: true});
  });
}
async function checkPreferenceRecovery(){
  const id=await video.evaluate(v=>new URL(v.src).pathname.split('/')[3]);
  const url=`${base}/api/library/${id}/preference`;
  const saved=await (await page.request.get(url)).json(),writes=[];
  const snapshot=()=>video.evaluate(v=>({src:v.src,time:v.currentTime,paused:v.paused,track:v.querySelector('track')?.src}));
  const before=await snapshot();let committed;
  const observe=request=>{if(request.method()==='PUT'&&request.url()===url)writes.push(request);};
  // Commit the real SQLite write and lose only its reply. Recovery must read
  // that version, without replaying a write or disturbing native playback.
  const handler=async route=>{
    if(route.request().method()!=='PUT')return route.continue();
    const response=await route.fetch();assert.equal(response.status(),200);
    committed=await response.json();await route.abort('failed');
  };
  await page.locator('#preference-panel').evaluate(el=>el.open=true);
  await page.waitForFunction(()=>!document.querySelector('#preference-controls').disabled);
  await page.route(url,handler);page.on('request',observe);
  try{
    await page.locator('#preference-include').setChecked(!saved.included);
    await page.locator('#preference-retry').waitFor();
    assert.equal(await page.locator('#preference-controls').isDisabled(),true);
    assert.equal(committed.revision,saved.revision+1);
    await page.locator('#preference-retry').click();
    await page.waitForFunction(()=>!document.querySelector('#preference-controls').disabled);
    assert.equal(await page.locator('#preference-include').isChecked(),!saved.included);
    assert.deepEqual(await (await page.request.get(url)).json(),committed);
    assert.equal(writes.length,1);assert.deepEqual(await snapshot(),before);
    console.log(JSON.stringify({phase,preferenceLostReceiptRecovery:true,preferenceWrites:writes.length}));
  }finally{
    await page.unroute(url,handler);page.off('request',observe);
    await page.locator('#preference-panel').evaluate(el=>el.open=false);
  }
}
async function checkObservedResume() {
  try {
    await page.waitForFunction(() => {
      const v = document.querySelector('#video');
      return window.resumeObservation !== null && v.readyState >= 2 && !v.seeking;
    });
    const restored = await video.evaluate(v => ({time: window.resumeObservation, paused: v.paused}));
    assert(Math.abs(restored.time - 7) < .25, 'native seek must restore seven seconds');
    assert.equal(restored.paused, true);
  } catch (error) {
    console.log(JSON.stringify({phase, stage: 'resume-observation-failed', ...await video.evaluate(v => ({
      observedTime: window.resumeObservation, currentTime: v.currentTime,
      paused: v.paused, seeking: v.seeking, readyState: v.readyState, mediaError: v.error?.code ?? null
    }))}));
    throw error;
  }
}
async function checkSubtitleStatusRecovery(){
  const snapshot=()=>video.evaluate(v=>({src:v.src,time:v.currentTime,paused:v.paused,track:v.querySelector('track').src}));
  const before=await snapshot(),commands=[];
  const observe=request=>{if(request.method()==='POST'&&(/\/subtitle-jobs(?:\/|\?|$)/.test(request.url())||request.url().endsWith('/retranslate')))commands.push(true);};
  page.on('request',observe);
  // Inject one failed status read; recovery uses the real server and loaded captions.
  await page.route(/\/api\/library\/[^/]+\/subtitles(?:\?.*)?$/,route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'storage_unavailable'})}),{times:1});
  await page.evaluate(()=>refreshSubtitles(activeItem));
  await page.locator('#subtitle-preparation').evaluate(el=>el.open=true);
  const retry=page.locator('#subtitle-refresh');
  assert.equal(await retry.isVisible(),true);assert.equal(await retry.isEnabled(),true);
  assert.deepEqual(await snapshot(),before,'a status failure keeps the loaded caption and paused playback');
  assert.equal(await page.locator('#subtitle-generate').isEnabled(),false);
  if(process.env.MEDIA_TEST_SCREENSHOT_DIR){
    await mkdir(process.env.MEDIA_TEST_SCREENSHOT_DIR,{recursive:true});
    await retry.scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`${phase}-status-recovery-desktop.png`)});
    await page.setViewportSize({width:390,height:844});await retry.scrollIntoViewIfNeeded();
    assert(await page.locator('#player-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`${phase}-status-recovery-mobile.png`)});
    await page.setViewportSize({width:1280,height:720});
  }
  const recovered=page.waitForResponse(r=>r.request().method()==='GET'&&/\/api\/library\/[^/]+\/subtitles(?:\?.*)?$/.test(r.url())&&r.status()===200);
  await retry.click();await recovered;await retry.waitFor({state:'hidden'});
  assert.equal(await page.locator('#subtitle-select').isEnabled(),true);
  assert.deepEqual(await snapshot(),before,'explicit status recovery preserves playback/caption state');
  assert.equal(commands.length,0,'status recovery never starts or resumes inference');
  page.off('request',observe);await page.locator('#subtitle-preparation').evaluate(el=>el.open=false);
}
async function checkCaptionViewing(trackId){
  const selector=page.locator('#subtitle-select');
  await selector.selectOption(trackId);
  await page.locator('#caption-view-panel').evaluate(el=>el.open=true);
  await page.locator('#caption-later').click();
  await page.waitForFunction(()=>{
    const el=document.querySelector('#video track');
    return !document.querySelector('#subtitle-select').disabled&&el?.readyState===2&&el.src.endsWith('offset_ms=500');
  });
  const cue=await video.evaluate(v=>{const c=[...v.textTracks].find(t=>t.mode==='showing').cues[0];return [c.startTime,c.endTime];});
  assert.deepEqual(cue,[1.5,18.5]);
  await video.evaluate(v=>{v.pause();v.currentTime=1.2;});
  await page.waitForFunction(()=>{const v=document.querySelector('#video');return !v.seeking&&[...v.textTracks].every(t=>!t.activeCues?.length);});
  await page.locator('#subtitle-search-panel').evaluate(el=>el.open=true);
  await page.locator('#subtitle-query').fill('자막 재생 확인');
  await page.locator('#subtitle-results button').click();
  await page.waitForFunction(()=>document.querySelector('#video').currentTime>=1.5);
  await video.evaluate(v=>v.pause());
  assert((await video.evaluate(v=>v.currentTime))<2.5,'search seeks to shifted cue');
  assert(await video.evaluate(v=>[...v.textTracks].some(t=>t.mode==='showing'&&[...t.activeCues].some(c=>c.text.includes('자막 재생 확인')))));
  await page.locator('#subtitle-search-panel').evaluate(el=>el.open=false);
  if(process.env.MEDIA_TEST_SCREENSHOT_DIR){
    await mkdir(process.env.MEDIA_TEST_SCREENSHOT_DIR,{recursive:true});
    await page.locator('#subtitle-preparation').evaluate(el=>el.open=false);
    await page.locator('#toast').evaluate(el=>el.hidden=true);
    const frameSettings=()=>page.locator('#caption-view-panel').evaluate(el=>{
      const dialog=document.querySelector('#player-dialog'),header=dialog.querySelector('header');
      dialog.scrollTop+=el.getBoundingClientRect().top-dialog.getBoundingClientRect().top-header.getBoundingClientRect().height-16;
    });
    await frameSettings();
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`${phase}-desktop.png`)});
    await page.setViewportSize({width:390,height:844});
    await frameSettings();
    assert(await page.locator('#player-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'mobile controls must fit without horizontal scroll');
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`${phase}-mobile.png`)});
    await page.setViewportSize({width:1280,height:720});
  }
  // Native Off is persisted while the native track remains available for On.
  await video.evaluate(v=>[...v.textTracks].forEach(t=>t.mode='disabled'));
  await page.waitForFunction(()=>!document.querySelector('#subtitle-select').disabled&&document.querySelector('#subtitle-select').value==='');
  await page.locator('#player-close').click();
  await page.waitForFunction(()=>!document.querySelector('#player-dialog').open);
  await page.locator('.card-button').click();
  await page.waitForFunction(()=>!document.querySelector('#subtitle-select').disabled);
  assert.equal(await selector.inputValue(),'');
  assert.equal(await video.locator('track').count(),0,'Off survives reopen');
  await video.evaluate(v=>v.pause());
  await selector.selectOption(trackId);
  await page.locator('#caption-view-panel').evaluate(el=>el.open=true);
  await page.locator('#caption-later').click();
  await page.waitForFunction(()=>!document.querySelector('#subtitle-select').disabled&&document.querySelector('#video track')?.readyState===2);
  assert.match(await video.locator('track').getAttribute('src'),/offset_ms=500$/);
}
async function checkCaptionImportRecovery(trackId){
  const itemId=await video.evaluate(v=>new URL(v.src).pathname.split('/')[3]);
  const statusURL=`${base}/api/library/${itemId}/subtitles?audio_index=0`;
  const beforeStatus=await (await page.request.get(statusURL)).json();
  const snapshot=()=>video.evaluate(v=>({src:v.src,time:v.currentTime,paused:v.paused,track:v.querySelector('track')?.src}));
  const before=await snapshot(),posts=[];
  const observe=request=>{if(request.method()==='POST')posts.push(new URL(request.url()).pathname);};
  const importURL=url=>url.pathname===`/api/library/${itemId}/subtitles`&&url.searchParams.get('format')==='srt';
  let release,committed,importRequest,receiptFailed=false;const gate=new Promise(resolve=>release=resolve);
  const failed=request=>{if(request===importRequest)receiptFailed=true;};
  const handler=async route=>{
    importRequest=route.request();
    const result=await route.fetch();committed={status:result.status(),...(await result.json())};
    await page.evaluate(()=>window.captionImportCommitted=true);
    await gate;await route.abort('failed');
  };
  await page.locator('#subtitle-preparation').evaluate(el=>el.open=true);
  await page.locator('#subtitle-input').evaluate(el=>{
    window.captionPickerCancelled=false;
    el.addEventListener('cancel',()=>window.captionPickerCancelled=true,{once:true});
  });
  await page.route(importURL,handler);page.on('request',observe);page.on('requestfailed',failed);
  try{
    // Deliver the actual file to the server, then lose only its receipt. Sending
    // it twice through the UI while pending must still deliver one POST.
    await page.locator('#subtitle-input').setInputFiles(subtitle);
    await page.waitForFunction(()=>window.captionImportCommitted===true,null,{timeout:5000});
    assert.equal(committed.status,201);assert.notEqual(committed.id,trackId,'ordinary imports preserve a new caption version');
    assert.equal(await page.locator('#subtitle-import').isDisabled(),true);
    await page.locator('#subtitle-input').setInputFiles(subtitle);
    assert.equal(await page.locator('#player-dialog').evaluate(el=>el.open),true,'same-file picker cancellation keeps playback open');
    // Selecting the same native file can emit cancel rather than change. Also
    // deliver the duplicate change explicitly to exercise the pending guard.
    await page.locator('#subtitle-input').dispatchEvent('change');assert.equal(posts.length,1);
    const failure=page.waitForEvent('requestfailed',{predicate:request=>request===importRequest,timeout:5000});
    release();await failure;await page.locator('#subtitle-refresh').waitFor();
    assert.equal(await page.locator('#subtitle-import').isDisabled(),true);assert.deepEqual(await snapshot(),before);
    await page.locator('#subtitle-refresh').click();
    await page.waitForFunction(()=>!document.querySelector('#subtitle-import').disabled);
    assert.match(await page.locator('#subtitle-state').textContent(),/자막 목록/);
    assert.deepEqual(await snapshot(),before);
    const afterStatus=await (await page.request.get(statusURL)).json();
    assert.equal(afterStatus.tracks.length,beforeStatus.tracks.length+1,'only one new version is published');
    assert.deepEqual(afterStatus.tracks.filter(t=>t.id!==committed.id),beforeStatus.tracks);
    assert.deepEqual({...afterStatus,tracks:beforeStatus.tracks},beforeStatus,'old captions, jobs and viewing settings are unchanged');
    const canonical=async id=>(await page.request.get(`${base}/api/library/${itemId}/subtitles/${id}.vtt`)).text();
    assert.equal(await canonical(committed.id),await canonical(trackId));
    assert.deepEqual(posts,[`/api/library/${itemId}/subtitles`],'recovery neither reimports nor starts translation');
    console.log(JSON.stringify({phase,captionImportRecovery:true,pickerCancelled:await page.evaluate(()=>window.captionPickerCancelled)}));
  }catch(error){
    const state=await page.evaluate(()=>{
      const command=subtitleCommands.get(activeItem?.id);
      return {command:!!command,pending:!!command?.pending,uncertain:!!command?.uncertain,
        importKind:command?.kind==='import',commandError:!!command?.error,
        stopped:!!subtitleMonitor?.stopped,confirming:!!subtitleMonitor?.confirming,
        reading:!!subtitleMonitor?.reading,refreshHidden:document.querySelector('#subtitle-refresh').hidden,
        playerOpen:document.querySelector('#player-dialog').open,activeOwner:!!activeItem,
        pickerCancelled:!!window.captionPickerCancelled,
        preparationOpen:document.querySelector('#subtitle-preparation').open};
    });
    console.log(JSON.stringify({phase,stage:'caption-import-failure',receiptFailed,pageErrors:errors.length,...state}));
    throw error;
  }finally{
    release();await page.unroute(importURL,handler);page.off('request',observe);page.off('requestfailed',failed);
    await page.locator('#subtitle-preparation').evaluate(el=>el.open=false);
  }
}
async function checkMomentEntry() {
  const session = await (await page.request.get(`${base}/api/session`)).json();
  const headers = {'X-Media-Token': session.token};
  const items = (await (await page.request.get(`${base}/api/library`)).json()).items;
  const item = items[0], path = `${base}/api/library/${item.id}`;
  const before = {position: item.position, watched_at: item.watched_at};
  const preference = await (await page.request.get(`${path}/preference`)).json();
  assert.equal((await page.request.put(`${path}/preference`, {headers,
    data: {included: true, preference: preference.preference, revision: preference.revision}})).status(), 200);
  const response = await page.request.get(`${path}/moment-reference`, {headers});
  assert.equal(response.status(), 200);
  const reference = await response.json();
  const entry = {...reference, start_ms: 3000, end_ms: 4500};
  const writes = [], preparations = [];
  const observe = request => {
    if (request.method() === 'PUT' && request.url() === path + '/position') writes.push(request);
    if (request.method() === 'POST' && request.url().endsWith('/playback')) preparations.push(true);
    assert(!request.url().includes('#moment='), 'fragment must never reach HTTP');
  };
  page.on('request', observe);
  const fragment = value => '#moment=' + encodeURIComponent(JSON.stringify(value));
  const entered = async start => {
    await page.waitForFunction(t => {
      const v = document.querySelector('#video');
      return document.querySelector('#player-dialog').open && v.readyState >= 2 && !v.seeking && Math.abs(v.currentTime - t) < .2;
    }, start);
    assert.equal(await video.evaluate(v => v.paused), true);
    assert.equal(new URL(page.url()).hash, '');
  };
  const unchanged = async () => {
    const current = await (await page.request.get(path)).json();
    assert.deepEqual({position: current.position, watched_at: current.watched_at}, before);
    assert.equal(writes.length, 0);
    assert.equal(preparations.length, 0);
  };
  // Initial navigation and subsequent fragment entry use the same stopped player.
  await page.goto(base + '/' + fragment(entry));
  await entered(3);
  await video.evaluate(v => { v.currentTime = 4; });
  await page.waitForFunction(() => !document.querySelector('#video').seeking);
  await unchanged();
  await page.locator('#player-close').click();
  await page.waitForFunction(() => !document.querySelector('#player-dialog').open);
  await unchanged();
  // A valid foreign-library reference is refused, without opening or preparing.
  const rejected = page.waitForResponse(r => r.url().endsWith('/moment-entry') && r.status() === 409);
  await page.evaluate(hash => { location.hash = hash; }, fragment({...entry, library_id:'f'.repeat(32)}));
  await rejected;
  assert.equal(await page.locator('#player-dialog').evaluate(d => d.open), false);
  await unchanged();
  await page.evaluate(hash => { location.hash = hash; }, fragment(entry));
  await entered(3);
  // Playing explicitly releases position saving; opening/seek/close did not.
  // Hold the first write until close to exercise the app's immediate-close
  // contract. A sent request or a hidden dialog does not acknowledge a commit.
  let releasePosition;
  const positionGate = new Promise(resolve => { releasePosition = resolve; });
  const holdPosition = async route => { await positionGate; await route.continue(); };
  await page.route(path + '/position', holdPosition, {times: 1});
  try {
    await video.evaluate(v => {
      window.momentPausedAt = null;
      const stop = () => {
        if(v.currentTime <= 3.3) return;
        v.removeEventListener('timeupdate', stop);v.pause();window.momentPausedAt = v.currentTime;
      };
      v.addEventListener('timeupdate', stop);
      return v.play();
    });
    await page.waitForFunction(() => window.momentPausedAt !== null);
    const pausedAt = await video.evaluate(v => { if(!v.paused) throw Error('moment must pause'); return window.momentPausedAt; });
    assert(pausedAt > 3.3 && pausedAt < 6, `moment pause outside expected range: ${pausedAt}`);
    await page.locator('#player-close').click();
    await page.waitForFunction(() => !document.querySelector('#player-dialog').open);
    assert(writes.length > 0);
    const beforeCommit = await (await page.request.get(path)).json();
    assert.equal(beforeCommit.position, before.position, 'closed player can still have an uncommitted write');
    releasePosition();
    const matchesPause = request => request.method() === 'PUT' && request.url() === path + '/position'
      && request.postDataJSON()?.position === pausedAt;
    const request = writes.find(matchesPause) || await page.waitForRequest(matchesPause, {timeout: 5000});
    const committed = await request.response();
    assert.equal(committed?.status(), 200, 'paused position write must succeed');
    const saved = await committed.json();
    assert.equal(saved.position, pausedAt, 'write response must confirm the actual pause');
    const played = await (await page.request.get(path)).json();
    assert.equal(played.position, pausedAt, 'read after the commit must retain the actual pause');
    assert.equal(played.position_revision, saved.position_revision);
    console.log(JSON.stringify({phase,momentPositionCommit:true}));
  } finally {
    releasePosition();await page.unroute(path + '/position', holdPosition);
  }
  assert.equal(preparations.length, 0);
  page.off('request', observe);
  // Keep the existing first→restart resume fixture at seven seconds.
  assert.equal((await page.request.put(`${path}/position`, {headers, data:{position:7, audio_index:0}})).status(), 200);
}
try {
  mark('initial-navigation');
  await page.goto(base);
  if (phase === 'first') {
    // First confirm normal initial loading, then fail only this browser's
    // session read once. The retry must return to the actual HTTP library.
    await page.locator('#empty-state').waitFor();
    mark('startup-recovery');
    await page.route(base+'/api/session', route=>route.fulfill({status:503,
      contentType:'application/json',body:JSON.stringify({error:'storage_unavailable'})}), {times:1});
    await page.reload();
    await page.locator('#connection-retry').waitFor();
    assert.equal(await page.locator('#empty-state').isVisible(),false);
    assert.equal(await page.locator('#import-top').isDisabled(),true);
    await page.locator('#connection-retry').click();
    mark('source-import');
    // Use the enabled product control, not injection into its hidden input.
    const chooser=page.waitForEvent('filechooser');
    await page.locator('#import-top').click();
    await (await chooser).setFiles(source);
    assert.equal(await page.locator('#connection-recovery').isVisible(),false);
  }
  await page.locator('.card-button').waitFor();
  assert.equal(await page.locator('.card-button').count(), 1);
  mark('player-open');
  if (phase === 'restart') await armResumeObservation();
  await page.locator('.card-button').click();
  await page.waitForFunction(() => document.querySelector('#video').readyState >= 2);
  const selector = page.locator('#subtitle-select');
  if (phase === 'first') {
    await page.locator('#subtitle-preparation > summary').click();
    const provider = page.locator('#subtitle-translator');
    assert.equal(await provider.isVisible(), true);
    assert.match(await provider.textContent(), /Gemini 3\.8 Flash/);
    assert.equal(await page.locator('#subtitle-cloud-note').isVisible(), true);
    assert.equal(await page.locator('#subtitle-generate').textContent(), 'Gemini로 자막 만들기');
    assert.match(await page.locator('#subtitle-cloud-note').textContent(), /음성 인식은 이 기기/);
    const response = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/subtitle-jobs') && r.request().method() === 'POST');
    await page.locator('#subtitle-generate').click();
    const blocked = await response;
    assert.equal(blocked.status(), 503);
    assert.equal((await blocked.json()).error, 'gemini_key_missing');
    assert.equal(await provider.evaluate(e => e.tagName), 'P');
    await page.locator('#subtitle-preparation > summary').click();
    await page.locator('#subtitle-input').setInputFiles(subtitle);
  } else {
    await checkObservedResume();
  }
  mark('caption-load');
  await page.waitForFunction(count => document.querySelector('#subtitle-select').options.length === count, phase === 'first' ? 2 : 5);
  // The first phase's lost receipt published a second supplied version. Reopen
  // must still restore the oldest explicitly selected version and its offset.
  const trackId = await selector.locator('option').filter({hasText: '가져온 자막'}).last().getAttribute('value');
  if(phase==='restart'){
    await page.waitForFunction(()=>!document.querySelector('#subtitle-select').disabled&&document.querySelector('#video track')?.readyState===2);
    assert.equal(await selector.inputValue(),trackId,'server restart preserves chosen older version instead of newest generated track');
    assert.match(await video.locator('track').getAttribute('src'),/offset_ms=500$/);
  }
  await selector.selectOption(trackId);
  await page.waitForFunction(() => document.querySelector('#video track')?.readyState === 2);
  await video.evaluate(v => { v.pause(); v.currentTime = 5; });
  await page.waitForFunction(() => {
    const v = document.querySelector('#video');
    return !v.seeking && v.readyState >= 2 && Math.abs(v.currentTime - 5) < .2;
  });
  await video.evaluate(v => v.play());
  await page.waitForFunction(() => document.querySelector('#video').currentTime > 5.35);
  await video.evaluate(v => v.pause());
  const observed = await video.evaluate(v => ({
    time: v.currentTime, frames: v.getVideoPlaybackQuality().totalVideoFrames,
    cues: [...v.textTracks[0].activeCues].map(c => c.text),
    error: v.error?.code ?? null,
  }));
  assert(observed.frames > 0, 'decoded video frames required');
  assert.equal(observed.error, null);
  assert(observed.cues.includes('한국어 자막 재생 확인'), 'active native Korean cue required');
  mark('subtitle-status-recovery');
  await checkSubtitleStatusRecovery();
  if(phase==='first'){mark('preference-recovery');await checkPreferenceRecovery();}
  const displayTitle='ＣＩ 한글 <literal>';
  if(phase==='restart')assert.equal(await page.locator('#player-title').textContent(),displayTitle,'display title survives server restart');
  await page.locator('#title-panel > summary').click();
  const beforeTitle=await video.evaluate(v=>({src:v.src,time:v.currentTime,paused:v.paused,track:v.querySelector('track').src}));
  if(phase==='first'){
    await page.locator('#title-input').fill(displayTitle);
    await page.locator('#title-save').click();
    await page.waitForFunction(()=>document.querySelector('#title-state').textContent==='제목을 저장했습니다.');
  }
  assert.equal(await page.locator('#title-input').inputValue(),displayTitle);
  assert.equal(await page.locator('#player-title').textContent(),displayTitle);
  assert.equal(await page.locator('#player-title').evaluate(el=>el.children.length),0,'title is literal text');
  assert.deepEqual(await video.evaluate(v=>({src:v.src,time:v.currentTime,paused:v.paused,track:v.querySelector('track').src})),beforeTitle,'rename preserves loaded playback and caption');
  // Repeated saved-title reads preserve the draft and never send a title write.
  const titleWrites=[],observeTitle=request=>{if(request.method()==='PUT'&&request.url().endsWith('/title'))titleWrites.push(true);};
  page.on('request',observeTitle);
  await page.locator('#title-input').fill('아직 저장하지 않은 제목');
  for(let read=0;read<2;read++){
    const response=page.waitForResponse(r=>r.request().method()==='GET'&&/\/api\/library\/[a-f0-9]{32}$/.test(r.url()));
    await page.locator('#title-reload').click();await response;
    await page.waitForFunction(()=>!document.querySelector('#title-reload').disabled);
    assert.equal(await page.locator('#title-input').inputValue(),'아직 저장하지 않은 제목');
    assert.equal(await page.locator('#player-title').textContent(),displayTitle);
  }
  assert.deepEqual(titleWrites,[]);page.off('request',observeTitle);
  assert.deepEqual(await video.evaluate(v=>({src:v.src,time:v.currentTime,paused:v.paused,track:v.querySelector('track').src})),beforeTitle,'saved-title reads preserve playback and caption');
  await page.locator('#title-input').fill(displayTitle);
  console.log(JSON.stringify({phase,titleDraftReread:true}));
  if(process.env.MEDIA_TEST_SCREENSHOT_DIR){
    await mkdir(process.env.MEDIA_TEST_SCREENSHOT_DIR,{recursive:true});
    await page.locator('#title-input').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`${phase}-title-desktop.png`)});
    await page.setViewportSize({width:390,height:844});
    await page.locator('#title-input').scrollIntoViewIfNeeded();
    assert(await page.locator('#player-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`${phase}-title-mobile.png`)});
    await page.setViewportSize({width:1280,height:720});
  }
  await page.locator('#title-panel > summary').click();
  if (phase === 'restart') {
    const sourceId = await selector.locator('option').filter({hasText: '원문 자막'}).getAttribute('value');
    const position = await video.evaluate(v => v.currentTime);
    await selector.selectOption(sourceId);
    await page.waitForFunction(() => [...document.querySelector('#video').textTracks].some(t =>
      t.mode === 'showing' && [...t.activeCues].some(c => c.getCueAsHTML().textContent === 'Original <voice> & text.')));
    assert.equal(await video.evaluate(v => v.currentTime), position);
    assert.equal(await video.evaluate(v => v.paused), true);
    const retranslate = page.locator('#subtitle-retranslate');
    await page.locator('#subtitle-preparation > summary').click();
    assert.equal(await retranslate.isVisible(), true);
    const provider = page.locator('#subtitle-translator');
    assert.match(await provider.textContent(), /Gemini 3\.8 Flash/);
    assert.equal(await provider.evaluate(e => e.tagName), 'P');
    const response = page.waitForResponse(r => r.url().endsWith(`/subtitles/${sourceId.split(':')[0]}/retranslate`) && r.request().method() === 'POST');
    await retranslate.click();
    const blocked = await response;
    assert.equal(blocked.status(), 503);
    assert.equal((await blocked.json()).error, 'gemini_key_missing');
    assert.equal(await selector.inputValue(), sourceId);
    assert.match(await provider.textContent(), /Gemini 3\.8 Flash/);
    const before = await video.evaluate(v => ({src:v.currentSrc, track:v.querySelector('track').getAttribute('src'), time:v.currentTime}));
    await video.evaluate(v => v.play());
    const disclosure = page.locator('#subtitle-cloud-note');
    assert.equal(await disclosure.isVisible(), true);
    assert.match(await disclosure.textContent(), /텍스트를 Google로/);
    assert.match(await disclosure.textContent(), /영상·음성 파일은 보내지 않습니다/);
    const cloudResponse = page.waitForResponse(r => r.url().endsWith(`/subtitles/${sourceId.split(':')[0]}/retranslate`) && r.request().method() === 'POST');
    await retranslate.click();
    const cloudBlocked = await cloudResponse;
    assert.equal(cloudBlocked.status(), 503);
    assert.equal((await cloudBlocked.json()).error, 'gemini_key_missing');
    await page.waitForFunction(() => document.querySelector('#subtitle-state').textContent.includes('Gemini API 키'));
    assert.equal(await selector.inputValue(), sourceId);
    await page.waitForFunction(t => {
      const v=document.querySelector('#video');return !v.paused&&!v.seeking&&v.currentTime>t+.25;
    }, before.time);
    assert.deepEqual(await video.evaluate(v => ({src:v.currentSrc, track:v.querySelector('track').getAttribute('src')})), {src:before.src,track:before.track});
    await video.evaluate((v,t) => {v.pause();v.currentTime=t;}, before.time);
    await page.waitForFunction(() => !document.querySelector('#video').seeking);
    await page.locator('#subtitle-search-panel > summary').click();
    await page.locator('#subtitle-query').fill('Original');
    await page.locator('#subtitle-results button').waitFor();
    assert.equal(await page.locator('#subtitle-results button').count(), 1);
    // The prepared Korean result can be used without reopening preparation or
    // starting processing. The source remains selected until this explicit click.
    await page.locator('#subtitle-preparation').evaluate(el=>el.open=false);
    const ready=page.locator('#subtitle-ready'),commands=[];
    const observeReady=request=>{if(request.method()==='POST')commands.push(true);};
    page.on('request',observeReady);
    assert.equal(await ready.isVisible(),true);assert.equal(await selector.inputValue(),sourceId);
    const readyBefore=await video.evaluate(v=>({src:v.src,time:v.currentTime,paused:v.paused}));
    const readySaved=page.waitForResponse(r=>r.request().method()==='PUT'&&r.url().endsWith('/caption-view'));
    await ready.click();const savedResponse=await readySaved;assert.equal(savedResponse.status(),200);
    const savedReady=await savedResponse.json();assert.equal(savedReady.selection,sourceId.split(':')[0]);assert.equal(savedReady.offset_ms,0);
    await page.waitForFunction(() => [...document.querySelector('#video').textTracks].some(t =>
      t.mode === 'showing' && [...t.activeCues].some(c => c.text.includes('한국어 자동 번역 확인'))));
    await page.waitForFunction(() => document.querySelectorAll('#subtitle-results button').length === 0);
    assert.equal(await ready.isVisible(),false);assert.deepEqual(commands,[]);page.off('request',observeReady);
    assert.deepEqual(await video.evaluate(v=>({src:v.src,time:v.currentTime,paused:v.paused})),readyBefore);
    console.log(JSON.stringify({phase,readyKoreanCaption:true}));
    await selector.selectOption(trackId);
    assert.equal(await retranslate.evaluate(el=>el.hidden), true);
    await page.waitForFunction(() => document.querySelector('#video track')?.readyState === 2);
  }
  await selector.selectOption('');
  await page.waitForFunction(() => [...document.querySelector('#video').textTracks].every(t => t.mode !== 'showing'));
  await selector.selectOption(trackId);
  await page.waitForFunction(() => [...document.querySelector('#video').textTracks].some(t => t.mode === 'showing'));
  mark('caption-viewing');
  if(phase==='first'){mark('session-recovery');await checkSessionRecovery();}
  await checkCaptionViewing(trackId);
  if(phase==='first')await checkCaptionImportRecovery(trackId);
  if(phase==='restart')await checkSubtitleSearchPages(page,trackId);
  await video.evaluate(v => { v.currentTime = 7; });
  await page.waitForFunction(() => !document.querySelector('#video').seeking);
  await page.locator('#player-close').click();
  await page.waitForFunction(() => !document.querySelector('#player-dialog').open);
  await page.locator('#search').fill('ci 한글');
  assert.equal(await page.locator('.card-button').count(),1,'NFKC title search handles width and Hangul composition');
  await page.locator('#search').fill('');
  await armResumeObservation();
  await page.locator('.card-button').click();
  await checkObservedResume();
  await page.locator('#player-close').click();
  await page.waitForFunction(() => !document.querySelector('#player-dialog').open);
  mark('moment-entry');
  await checkMomentEntry();
  mark('item-entry');
  await checkItemEntry(page,base,phase,trackId,source);
  if(phase==='restart'){mark('vp9-playback');await checkVP9Playback(page,base,source);}
  assert(ranges.includes(206), 'real browser Range response required');
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  mark('checks-complete');
  console.log(JSON.stringify({phase, browser: browser.version(), channel: executablePath ? 'explicit executable' : channel,
    startupConnectionRecovery:phase==='first',
    expiredSessionRecovery:phase==='first',
    subtitleSearch115NativeCues:phase==='restart', statusRecoveryWithExistingCaption: true, displayTitleAndNormalizedSearch: true, nativeCaption: true, captionOffsetAndSearch: true, nativeOffReopen:true, captionSettingsRestart:phase==='restart', freshGeminiSelectionMissingKey: phase === 'first', transcriptSwitchAndSearch: phase === 'restart', retranslationMissingSetup: phase === 'restart', geminiSelectionMissingKey: phase === 'restart', momentPausedEntry: true, momentPositionPreserved: true, decodedFrames: observed.frames, resumeSeconds: 7, range206: true, externalPageRequests: 0}));
} finally {
  mark('browser-close');
  await browser.close();
  mark('browser-closed');
}
