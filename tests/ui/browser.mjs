import assert from 'node:assert/strict';
import {chromium} from 'playwright';

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
    await page.locator('#subtitle-input').setInputFiles(subtitle);
  } else {
    await page.waitForFunction(() => {
      const v = document.querySelector('#video');
      return !v.seeking && Math.abs(v.currentTime - 7) < .25;
    });
  }
  await page.waitForFunction(() => document.querySelector('#subtitle-select').options.length === 2);
  const trackId = await selector.locator('option').nth(1).getAttribute('value');
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
  await selector.selectOption('');
  await page.waitForFunction(() => [...document.querySelector('#video').textTracks].every(t => t.mode !== 'showing'));
  await selector.selectOption(trackId);
  await page.waitForFunction(() => [...document.querySelector('#video').textTracks].some(t => t.mode === 'showing'));
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
  assert(ranges.includes(206), 'real browser Range response required');
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  console.log(JSON.stringify({phase, browser: browser.version(), channel: executablePath ? 'explicit executable' : channel,
    nativeCaption: true, decodedFrames: observed.frames, resumeSeconds: 7, range206: true, externalPageRequests: 0}));
} finally {
  await browser.close();
}
