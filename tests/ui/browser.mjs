import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

const [base, source, subtitle, phase] = process.argv.slice(2);
assert.match(base, /^http:\/\/127\.0\.0\.1:\d+$/);
assert(['first', 'restart'].includes(phase));
// Branded Chrome/Edge for proprietary codecs. An explicit executable supports cloud QA.
const executablePath = process.env.MEDIA_TEST_BROWSER_EXECUTABLE;
const channel = process.env.MEDIA_TEST_BROWSER_CHANNEL || 'chrome';
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
    await page.locator('#caption-view-panel').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`${phase}-desktop.png`)});
    await page.setViewportSize({width:390,height:844});
    await page.locator('#caption-view-panel').scrollIntoViewIfNeeded();
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
    if (request.method() === 'PUT' && request.url().endsWith('/position')) writes.push(true);
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
  await video.evaluate(v => v.play());
  await page.waitForFunction(() => document.querySelector('#video').currentTime > 3.3);
  await video.evaluate(v => v.pause());
  await page.locator('#player-close').click();
  await page.waitForFunction(() => !document.querySelector('#player-dialog').open);
  assert(writes.length > 0);
  const played = await (await page.request.get(path)).json();
  assert(played.position > 3.3 && played.position < 6);
  assert.equal(preparations.length, 0);
  page.off('request', observe);
  // Keep the existing first→restart resume fixture at seven seconds.
  assert.equal((await page.request.put(`${path}/position`, {headers, data:{position:7, audio_index:0}})).status(), 200);
}
try {
  await page.goto(base);
  if (phase === 'first') {
    await page.locator('#file-input').setInputFiles(source);
  }
  await page.locator('.card-button').waitFor();
  assert.equal(await page.locator('.card-button').count(), 1);
  await page.locator('.card-button').click();
  await page.waitForFunction(() => document.querySelector('#video').readyState >= 2);
  const selector = page.locator('#subtitle-select');
  if (phase === 'first') {
    await page.locator('#subtitle-preparation > summary').click();
    const provider = page.locator('#subtitle-translator');
    assert.equal(await provider.isVisible(), true);
    assert.equal(await provider.inputValue(), 'gemini');
    assert.equal(await page.locator('#subtitle-cloud-note').isVisible(), true);
    assert.equal(await page.locator('#subtitle-generate').textContent(), 'Gemini로 자막 만들기');
    assert.match(await page.locator('#subtitle-cloud-note').textContent(), /음성 인식은 이 기기/);
    const response = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/subtitle-jobs') && r.request().method() === 'POST');
    await page.locator('#subtitle-generate').click();
    const blocked = await response;
    assert.equal(blocked.status(), 503);
    assert.equal((await blocked.json()).error, 'gemini_key_missing');
    assert.equal(await provider.locator('option').count(), 1);
    await page.locator('#subtitle-preparation > summary').click();
    await page.locator('#subtitle-input').setInputFiles(subtitle);
  } else {
    await page.waitForFunction(() => {
      const v = document.querySelector('#video');
      return !v.seeking && Math.abs(v.currentTime - 7) < .25;
    });
  }
  await page.waitForFunction(count => document.querySelector('#subtitle-select').options.length === count, phase === 'first' ? 2 : 4);
  const trackId = await selector.locator('option').filter({hasText: '가져온 자막'}).getAttribute('value');
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
  if (phase === 'restart') {
    const sourceId = await selector.locator('option').filter({hasText: '원문 · 자동 전사'}).getAttribute('value');
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
    assert.equal(await provider.inputValue(), 'gemini');
    assert.equal(await provider.locator('option').count(), 1);
    const response = page.waitForResponse(r => r.url().endsWith(`/subtitles/${sourceId.split(':')[0]}/retranslate`) && r.request().method() === 'POST');
    await retranslate.click();
    const blocked = await response;
    assert.equal(blocked.status(), 503);
    assert.equal((await blocked.json()).error, 'gemini_key_missing');
    assert.equal(await selector.inputValue(), sourceId);
    assert.equal(await provider.inputValue(), 'gemini');
    const before = await video.evaluate(v => ({src:v.currentSrc, track:v.querySelector('track').getAttribute('src'), time:v.currentTime}));
    await video.evaluate(v => v.play());
    await provider.selectOption('gemini');
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
    await selector.selectOption(sourceId.split(':')[0]);
    await page.waitForFunction(() => [...document.querySelector('#video').textTracks].some(t =>
      t.mode === 'showing' && [...t.activeCues].some(c => c.text.includes('한국어 자동 번역 확인'))));
    await page.waitForFunction(() => document.querySelectorAll('#subtitle-results button').length === 0);
    await selector.selectOption(trackId);
    assert.equal(await retranslate.isVisible(), false);
    await page.waitForFunction(() => document.querySelector('#video track')?.readyState === 2);
  }
  await selector.selectOption('');
  await page.waitForFunction(() => [...document.querySelector('#video').textTracks].every(t => t.mode !== 'showing'));
  await selector.selectOption(trackId);
  await page.waitForFunction(() => [...document.querySelector('#video').textTracks].some(t => t.mode === 'showing'));
  await checkCaptionViewing(trackId);
  await video.evaluate(v => { v.currentTime = 7; });
  await page.waitForFunction(() => !document.querySelector('#video').seeking);
  await page.locator('#player-close').click();
  await page.waitForFunction(() => !document.querySelector('#player-dialog').open);
  await page.locator('.card-button').click();
  await page.waitForFunction(() => {
    const v = document.querySelector('#video');
    return v.readyState >= 2 && !v.seeking && Math.abs(v.currentTime - 7) < .25;
  });
  await page.locator('#player-close').click();
  await page.waitForFunction(() => !document.querySelector('#player-dialog').open);
  await checkMomentEntry();
  assert(ranges.includes(206), 'real browser Range response required');
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  console.log(JSON.stringify({phase, browser: browser.version(), channel: executablePath ? 'explicit executable' : channel,
    nativeCaption: true, captionOffsetAndSearch: true, nativeOffReopen:true, captionSettingsRestart:phase==='restart', freshGeminiSelectionMissingKey: phase === 'first', transcriptSwitchAndSearch: phase === 'restart', retranslationMissingSetup: phase === 'restart', geminiSelectionMissingKey: phase === 'restart', momentPausedEntry: true, momentPositionPreserved: true, decodedFrames: observed.frames, resumeSeconds: 7, range206: true, externalPageRequests: 0}));
} finally {
  await browser.close();
}
