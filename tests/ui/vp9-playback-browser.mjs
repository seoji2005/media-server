import assert from 'node:assert/strict';
import {readFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

// Synthetic VP9/AAC input through real import, companion captions, explicit item
// preparation and Chrome playback. No actual Fetch extension or GPU is involved.
export default async function checkVP9Playback(page,base,source){
  const bytes=await readFile(path.join(path.dirname(source),'vp9.mp4'));
  const session=await (await page.request.get(base+'/api/session')).json();
  const headers={'X-Media-Token':session.token};
  const uploaded=await page.request.post(base+'/api/import',{headers:{...headers,'Content-Type':'application/octet-stream','X-Media-Filename':'VP9-playback.mp4'},data:bytes});
  assert.equal(uploaded.status(),201);const item=(await uploaded.json()).item;
  assert.equal(item.preparation,'audio_webm');assert.equal(item.unavailable_reason,'rendition_required');
  assert.equal(item.sha256,createHash('sha256').update(bytes).digest('hex'));
  const vtt=Buffer.from('WEBVTT\n\n00:00:00.500 --> 00:00:03.500\nVP9 재생과 자막 확인\n');
  const params=new URLSearchParams({file_id:item.file_id,file_sha256:item.sha256,content_sha256:createHash('sha256').update(vtt).digest('hex'),format:'webvtt',language:'ko',timebase:'original-file'});
  const caption=await page.request.post(base+'/api/companion/library/'+item.id+'/subtitles?'+params,{headers,data:vtt});
  assert.equal(caption.status(),201);const captionId=(await caption.json()).id;
  const identity=await (await page.request.get(base+'/api/companion/identity',{headers})).json();
  const reference={version:1,server_id:identity.server_id,library_id:identity.library_id,item_id:item.id,file_id:item.file_id,sha256:item.sha256};
  const fragment='#item='+encodeURIComponent(JSON.stringify(reference));
  const posts=[],writes=[];
  const observe=r=>{if(r.method()==='POST')posts.push(new URL(r.url()).pathname);if(r.method()==='PUT'&&r.url().endsWith('/position'))writes.push(true);};
  page.on('request',observe);
  await page.goto(base+'/'+fragment);await page.locator('#item-entry-prepare').waitFor();
  assert(posts.every(p=>p.endsWith('/item-entry')),'opening the item does not prepare or infer');
  assert.equal(await page.locator('#player-dialog').evaluate(el=>el.open),false);
  // Fail only the card-list refresh after actual preparation. It cannot block
  // the ready video's entry, native decoding or imported captions.
  const failedList=page.waitForResponse(r=>r.url()===base+'/api/library'&&r.status()===503);
  await page.route(base+'/api/library',route=>route.fulfill({status:503,
    contentType:'application/json',body:JSON.stringify({error:'storage_unavailable'})}),{times:1});
  await page.locator('#item-entry-prepare').click();
  const video=page.locator('#video');
  await page.waitForFunction(()=>{const v=document.querySelector('#video');return document.querySelector('#player-dialog').open&&v.readyState>=2&&!v.seeking&&v.querySelector('track')?.readyState===2;});
  await failedList;
  assert(await video.evaluate(v=>v.paused));assert.deepEqual(writes,[]);
  assert.equal(posts.filter(p=>p.endsWith('/playback')).length,1);
  assert(posts.every(p=>p.endsWith('/playback')||p.endsWith('/item-entry')));
  assert.match(await page.locator('#player-meta').textContent(),/WebM.*Opus/);
  assert.equal(await page.locator('#subtitle-select').inputValue(),captionId);
  const ready=await (await page.request.get(base+'/api/library/'+item.id)).json();
  assert.equal(ready.preparation,'audio_webm');assert.equal(ready.mime,'video/webm');
  assert.equal(ready.file_id,item.file_id);assert.equal(ready.sha256,item.sha256);
  await video.evaluate(v=>{v.currentTime=.7;});await page.waitForFunction(()=>!document.querySelector('#video').seeking);
  assert.deepEqual(writes,[],'paused item entry never writes position');
  await video.evaluate(v=>v.play());await page.waitForFunction(()=>document.querySelector('#video').currentTime>1.1);
  await video.evaluate(v=>v.pause());
  const viewed=await video.evaluate(v=>({time:v.currentTime,frames:v.getVideoPlaybackQuality().totalVideoFrames,error:v.error?.code??null,captions:[...v.textTracks].flatMap(t=>[...t.activeCues||[]].map(c=>c.text))}));
  assert(viewed.frames>0);assert.equal(viewed.error,null);assert(viewed.captions.includes('VP9 재생과 자막 확인'));
  if(process.env.MEDIA_TEST_SCREENSHOT_DIR){
    await mkdir(process.env.MEDIA_TEST_SCREENSHOT_DIR,{recursive:true});
    for(const [size,label] of [[{width:1280,height:720},'desktop'],[{width:390,height:844},'mobile']]){
      await page.setViewportSize(size);await video.scrollIntoViewIfNeeded();
      assert(await page.locator('#player-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
      await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,`vp9-playback-${label}.png`)});
    }
  }
  await page.locator('#player-close').click();await page.waitForFunction(()=>!document.querySelector('#player-dialog').open);
  assert(writes.length>0);posts.length=0;
  await page.goto(base+'/'+fragment);
  await page.waitForFunction(time=>{const v=document.querySelector('#video');return v.readyState>=2&&!v.seeking&&Math.abs(v.currentTime-time)<.2;},viewed.time);
  assert(await video.evaluate(v=>v.paused));assert(posts.every(p=>p.endsWith('/item-entry')),'reopen reuses the completed rendition');
  assert.equal((await (await page.request.get(base+'/api/library/'+item.id+'/preference')).json()).included,false);
  await page.locator('#player-close').click();await page.setViewportSize({width:1280,height:720});
  page.off('request',observe);
  console.log(JSON.stringify({vp9MP4ToWebM:true,explicitPreparation:true,failedListDoesNotBlockPlayback:true,nativeCaption:true,decodedFrames:viewed.frames,pausedResume:true,originalIdentityPreserved:true}));
}
