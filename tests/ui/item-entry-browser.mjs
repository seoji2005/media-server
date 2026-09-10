import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

export default async function checkItemEntry(page,base,phase,trackId,source){
 const token=(await (await page.request.get(base+'/api/session')).json()).token;
 const headers={'X-Media-Token':token};
 const identity=await (await page.request.get(base+'/api/companion/identity',{headers})).json();
 const item=(await (await page.request.get(base+'/api/library')).json()).items[0];
 const url=base+'/api/library/'+item.id;
 const pref=await (await page.request.get(url+'/preference')).json();
 assert.equal((await page.request.put(url+'/preference',{headers,data:{included:false,preference:pref.preference,revision:pref.revision}})).status(),200);
 const ref=it=>({version:1,server_id:identity.server_id,library_id:identity.library_id,item_id:it.id,file_id:it.file_id,sha256:it.sha256});
 const fragment=it=>'#item='+encodeURIComponent(JSON.stringify(it));
 const before={position:item.position,watched_at:item.watched_at};
 const writes=[],posts=[];
 const observe=r=>{
  if(r.method()==='PUT')writes.push(new URL(r.url()).pathname);
  if(r.method()==='POST')posts.push(new URL(r.url()).pathname);
  assert(!r.url().includes('#item='));
 };
 async function viewing(selection,offset_ms){
  const status=await (await page.request.get(url+'/subtitles?audio_index=0')).json();
  assert.equal((await page.request.put(url+'/caption-view',{headers,data:{audio_index:0,selection,offset_ms,revision:status.view.revision}})).status(),200);
 }
 async function entered(position){
  await page.waitForFunction(t=>{const v=document.querySelector('#video');return document.querySelector('#player-dialog').open&&v.readyState>=2&&!v.seeking&&Math.abs(v.currentTime-t)<.2;},position);
  assert(await page.locator('#video').evaluate(v=>v.paused));
  assert.equal(new URL(page.url()).hash,'');
  await page.waitForFunction(()=>!document.querySelector('#subtitle-select').disabled);
 }
 async function unchanged(){
  const current=await (await page.request.get(url)).json();
  assert.deepEqual({position:current.position,watched_at:current.watched_at},before);
  assert.deepEqual(writes,[]);assert(posts.every(p=>p.endsWith('/item-entry')));
  assert.equal((await (await page.request.get(url+'/preference')).json()).included,false);
 }
 for(const choice of ['',trackId]){
  await viewing(choice,choice?500:0);
  page.on('request',observe);
  await page.goto(base+'/'+fragment(ref(item)));await entered(7);
  assert.equal(await page.locator('#subtitle-select').inputValue(),choice);
  if(choice){await page.waitForFunction(()=>document.querySelector('#video track')?.readyState===2);assert.match(await page.locator('#video track').getAttribute('src'),/offset_ms=500$/);}
  else assert.equal(await page.locator('#video track').count(),0);
  await page.locator('#video').evaluate(v=>{v.currentTime=9;});
  await page.waitForFunction(()=>!document.querySelector('#video').seeking);
  await unchanged();
  const rejected=page.waitForResponse(r=>r.url().endsWith('/item-entry')&&r.status()===409);
  await page.evaluate(h=>location.hash=h,fragment({...ref(item),library_id:'f'.repeat(32)}));await rejected;
  assert(await page.locator('#player-dialog').evaluate(d=>d.open),'bad link must preserve current player');
  await page.locator('#player-close').click();await page.waitForFunction(()=>!document.querySelector('#player-dialog').open);await unchanged();
  page.off('request',observe);
 }
 if(phase==='restart'){
  // A second real container has no playback rendition yet. Importing through the
  // companion HTTP flow must not trigger the browser upload's automatic preparation.
  const raw=await readFile(path.join(path.dirname(source),'pending.mkv'));
  const imported=await page.request.post(base+'/api/import',{headers:{...headers,'Content-Type':'application/octet-stream','X-Media-Filename':encodeURIComponent('준비할 영상.mkv')},data:raw});
  assert.equal(imported.status(),201);const pending=(await imported.json()).item;
  assert.equal(pending.unavailable_reason,'rendition_required');
  const vtt=Buffer.from('WEBVTT\n\n00:00:01.000 --> 00:00:18.000\n함께 가져온 자막\n');
  const params=new URLSearchParams({file_id:pending.file_id,file_sha256:pending.sha256,content_sha256:createHash('sha256').update(vtt).digest('hex'),format:'webvtt',language:'ko',timebase:'original-file'});
  const caption=await page.request.post(base+'/api/companion/library/'+pending.id+'/subtitles?'+params,{headers,data:vtt});
  assert.equal(caption.status(),201);
  const captionId=(await caption.json()).id;
  posts.length=0;page.on('request',observe);
  await page.goto(base+'/'+fragment(ref(pending)));
  await page.locator('#item-entry-prepare').waitFor();
  assert.equal(await page.locator('#player-dialog').evaluate(d=>d.open),false);
  assert(posts.every(p=>p.endsWith('/item-entry')));
  assert.equal((await (await page.request.get(base+'/api/library/'+pending.id)).json()).unavailable_reason,'rendition_required');
  if(process.env.MEDIA_TEST_SCREENSHOT_DIR){
   await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,'item-entry-prepare-desktop.png')});
   await page.setViewportSize({width:390,height:844});
   await page.locator('#item-entry-notice').scrollIntoViewIfNeeded();
   assert(await page.locator('#item-entry-notice').evaluate(e=>e.scrollWidth<=e.clientWidth+1));
   await page.screenshot({path:path.join(process.env.MEDIA_TEST_SCREENSHOT_DIR,'item-entry-prepare-mobile.png')});
   await page.setViewportSize({width:1280,height:720});
  }
  await page.locator('#item-entry-prepare').click();await entered(0);
  await page.waitForFunction(()=>document.querySelector('#video track')?.readyState===2);
  assert.equal(await page.locator('#subtitle-select').inputValue(),captionId);
  assert.equal(posts.filter(p=>p.endsWith('/playback')).length,1);
  assert(posts.every(p=>p.endsWith('/item-entry')||p.endsWith('/playback')));
  assert.deepEqual(writes,[]);
  await page.locator('#video').evaluate(v=>{v.currentTime=5;});await page.waitForFunction(()=>!document.querySelector('#video').seeking);
  assert(await page.locator('#video').evaluate(v=>[...v.textTracks].some(t=>[...t.activeCues||[]].some(c=>c.text==='함께 가져온 자막'))));
  await page.locator('#player-close').click();await page.waitForFunction(()=>!document.querySelector('#player-dialog').open);
  assert.deepEqual(writes,[]);page.off('request',observe);
 }
 console.log(JSON.stringify({itemEntry:true,phase,defaultExcluded:true,restoredOffOffset:true,noPrePlayWrites:true,explicitRealRemuxWithProvidedCaption:phase==='restart'}));
}
