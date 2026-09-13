// Product UI with injected native-track events / HTTP fixtures, not browser playback.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(path.join(root,'media_clarity/static/index.html'),'utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,video=d.getElementById('video'),dialog=d.getElementById('player-dialog');
const selection='c'.repeat(32)+':transcript',writes=[];
const views=new Map(['a','b'].map(id=>[id,{selection,offset_ms:1500,revision:4}]));
const item=id=>({id,title:id,duration:120,position:37.25,position_revision:2,width:320,height:180,available:true,thumbnail:false,audio_index:0});
let plays=0,holdSave=false,releaseSave,loseReply=false;
w.fetch=async(url,options={})=>{
  const id=url.split('/')[3];let data={};
  if(options.method&&options.method!=='GET')writes.push({url,...options});
  if(url==='/api/session')data={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
  else if(url==='/api/library')data={items:['a','b'].map(item)};
  else if(url.split('?')[0].endsWith('/subtitles'))data={tracks:[{id:'c'.repeat(32),source:'generated',has_transcript:true,audio_index:0}],jobs:[],view:{...views.get(id)}};
  else if(url.endsWith('/caption-view')){
    if(holdSave)await new Promise(resolve=>{releaseSave=resolve;});
    data={...JSON.parse(options.body),revision:views.get(id).revision+1};views.set(id,data);
    if(loseReply){loseReply=false;throw Error('fixture response lost');}
  }
  else data=item(id);
  return {ok:true,json:async()=>data};
};
Object.defineProperty(video,'readyState',{get:()=>1});Object.defineProperty(video,'duration',{get:()=>120});
Object.defineProperty(video,'textTracks',{value:new w.EventTarget()});
video.play=()=>{plays++;return Promise.resolve();};video.pause=()=>{};video.load=()=>{video.currentTime=0;};
dialog.showModal=()=>{dialog.open=true;};dialog.close=()=>{dialog.open=false;};
w.HTMLElement.prototype.scrollIntoView=function(){};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function native(track){Object.defineProperty(track,'track',{value:{mode:'showing',cues:[]}});return track;}
w.eval(fs.readFileSync(path.join(root,'media_clarity/static/app.js'),'utf8')+'\nglobalThis.qa={openPlayer,closePlayer,refreshSubtitles,owner:()=>activeItem};');
(async()=>{
  await tick();await w.qa.openPlayer('a');await tick();video.dispatchEvent(new w.Event('loadedmetadata'));
  const select=d.getElementById('subtitle-select'),failed=native(video.querySelector('track'));
  assert.equal(select.value,selection);assert.match(failed.src,/transcript=true&offset_ms=1500$/);
  failed.dispatchEvent(new w.Event('load'));assert.notEqual(d.getElementById('subtitle-load-recovery')?.hidden,false,'normal load needs no recovery notice');
  failed.dispatchEvent(new w.Event('error'));await tick();
  const retry=d.getElementById('subtitle-reload'),notice=d.getElementById('subtitle-load-recovery');
  assert(retry&&notice&&!notice.hidden,'failed caption must offer an explicit reload that preserves timing');
  assert.equal(d.getElementById('subtitle-preparation').open,false,'recovery must be outside collapsed preparation');
  await w.qa.refreshSubtitles(w.qa.owner());
  assert.equal(video.querySelector('track'),failed,'status polling must not auto-retry a failed file');
  assert.equal(notice.hidden,false);
  const before={time:video.currentTime,plays,writes:writes.length,view:JSON.stringify(views.get('a'))};
  retry.focus();retry.click();const replacement=native(video.querySelector('track'));
  assert.notEqual(replacement,failed);assert.equal(replacement.src,failed.src);
  assert.equal(d.activeElement,select,'retry returns keyboard focus to caption selection');
  retry.click();assert.equal(video.querySelector('track'),replacement,'double click does not request another copy');
  failed.dispatchEvent(new w.Event('load'));failed.dispatchEvent(new w.Event('error'));
  assert.match(d.getElementById('subtitle-search-status').textContent,/불러오는 중/,'detached same-id events cannot finish the replacement');
  replacement.dispatchEvent(new w.Event('error'));assert.equal(notice.hidden,false,'a repeated failure remains manually recoverable');
  assert.deepEqual({time:video.currentTime,plays,writes:writes.length,view:JSON.stringify(views.get('a'))},before,'reload never changes playback or saved view, creates jobs or saves history');
  retry.click();const recovered=native(video.querySelector('track'));recovered.dispatchEvent(new w.Event('load'));
  assert.equal(notice.hidden,true);assert.equal(select.value,selection);
  holdSave=true;loseReply=true;d.getElementById('caption-later').click();await tick();
  const pending=native(video.querySelector('track'));pending.dispatchEvent(new w.Event('error'));
  assert.equal(retry.disabled,true,'a pending setting save must settle before file reload');
  retry.click();assert.equal(video.querySelector('track'),pending);
  holdSave=false;releaseSave();await tick();assert.equal(retry.disabled,true,'uncertain saved settings require explicit confirmation');
  retry.click();assert.equal(video.querySelector('track'),pending);
  d.getElementById('caption-view-retry').click();await tick();
  const confirmed=native(video.querySelector('track'));assert.match(confirmed.src,/offset_ms=2000$/);
  confirmed.dispatchEvent(new w.Event('error'));assert.equal(retry.disabled,false);
  confirmed.track.mode='disabled';video.textTracks.dispatchEvent(new w.Event('change'));await tick();
  assert.equal(views.get('a').selection,'');assert.equal(notice.hidden,true,'native Off must hide recovery and stay Off');
  assert.match(d.getElementById('subtitle-search-status').textContent,/자막을 켜/,'native Off must not direct users to a hidden reload button');
  retry.click();assert.equal(video.querySelector('track'),confirmed);
  await w.qa.closePlayer();await w.qa.openPlayer('b');await tick();
  const next=native(video.querySelector('track'));next.dispatchEvent(new w.Event('load'));
  confirmed.dispatchEvent(new w.Event('error'));assert.equal(notice.hidden,true,'previous video cannot expose recovery in the new player');
  assert.equal(video.querySelector('track'),next);assert.equal(views.get('b').offset_ms,1500);
  console.log('PASS subtitle reload DOM: explicit retry, preserved transcript/offset/position, no writes or jobs, repeated failure, stale events, native Off and item isolation (mock HTTP/media).');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>w.close());
