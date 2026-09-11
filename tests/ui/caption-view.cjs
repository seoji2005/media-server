const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const repo=path.resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(path.join(repo,'media_clarity/static/index.html'),'utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,video=d.getElementById('video'),dialog=d.getElementById('player-dialog');
const items=['a','b'].map(id=>({id,title:id,duration:20,position:0,width:320,height:180,available:true,audio_index:0,thumbnail:false}));
const views=new Map(),writes=[],native=new WeakMap();
let pending=null,delay=false,loseResponse=false;
let importDelay=null,importPending=null;
const tracks=[{id:'first',source:'generated',has_transcript:true,audio_index:0},{id:'second',source:'supplied',audio_index:1}];
w.setTimeout=()=>1;w.clearTimeout=()=>{};
w.fetch=async(url,options={})=>{
 const uri=new URL(url,w.location.href),id=uri.pathname.split('/')[3];let value;
 if(url==='/api/session')value={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
 else if(url==='/api/library')value={items};
 else if(uri.pathname.endsWith('/caption-view')){
  const body=JSON.parse(options.body),key=id+':'+body.audio_index;
  writes.push({key,...body});if(delay)await new Promise(resolve=>pending=resolve);
  const current=views.get(key)||{revision:0};
  if(body.revision!==current.revision)return {ok:false,json:async()=>({error:'caption_view_changed'})};
  value={selection:body.selection,offset_ms:body.offset_ms,revision:body.revision+1};views.set(key,value);
  if(loseResponse){loseResponse=false;throw Error('response lost');}
 }else if(uri.pathname.endsWith('/subtitles')){
  if(options.method==='POST'){
   if(importDelay==='post'){importDelay=null;await new Promise(resolve=>importPending=resolve);}
   value={id:'manual'};
  }else{
   value={tracks,jobs:[],view:views.get(id+':'+(uri.searchParams.get('audio_index')||0))||{selection:null,offset_ms:0,revision:0}};
   if(importDelay==='read'){importDelay=null;await new Promise(resolve=>importPending=resolve);}
  }
 }
 else if(uri.pathname.endsWith('/preference'))value={included:false,preference:'neutral',revision:0};
 else value={...items.find(i=>i.id===id)};
 return {ok:true,json:async()=>JSON.parse(JSON.stringify(value))};
};
Object.defineProperty(w.HTMLTrackElement.prototype,'track',{get(){if(!native.has(this))native.set(this,{mode:'showing',cues:[]});return native.get(this);}});
Object.defineProperty(video,'textTracks',{value:new w.EventTarget()});
Object.defineProperty(video,'readyState',{get:()=>2});Object.defineProperty(video,'duration',{get:()=>20});
video.play=()=>Promise.resolve();video.pause=()=>{};video.load=()=>{};dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
w.eval(fs.readFileSync(path.join(repo,'media_clarity/static/app.js'),'utf8')+'\nglobalThis.qa={openPlayer,closePlayer,refreshSubtitles,owner:()=>activeItem};');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const select=d.getElementById('subtitle-select'),state=d.getElementById('caption-view-state');
async function choose(value){select.value=value;select.dispatchEvent(new w.Event('change'));await settle();}
async function reopen(id='a'){await w.qa.closePlayer();await w.qa.openPlayer(id);await settle();}
async function nativeMode(mode){video.querySelector('track').track.mode=mode;video.textTracks.dispatchEvent(new w.Event('change'));await settle();}
(async()=>{
 await settle();await w.qa.openPlayer('a');await settle();video.currentTime=7;
 assert.equal(select.value,'first');assert.equal(writes.length,0,'opening/default selection never writes');
 await choose('first:transcript');d.getElementById('caption-later').click();await settle();
 assert.match(video.querySelector('track').src,/transcript=true&offset_ms=500$/);assert.equal(video.currentTime,7);
 await reopen();assert.equal(select.value,'first:transcript');assert.match(video.querySelector('track').src,/offset_ms=500$/);
 const element=video.querySelector('track');await nativeMode('disabled');assert.equal(select.value,'');assert.equal(views.get('a:0').selection,'');
 assert.equal(video.querySelector('track'),element,'native Off retains the track for native On');
 await nativeMode('showing');assert.equal(select.value,'first:transcript');assert.equal(views.get('a:0').offset_ms,500);
 await nativeMode('disabled');await reopen();assert.equal(select.value,'');assert.equal(video.querySelector('track'),null);
 items[0].audio_index=1;await reopen();assert.equal(select.value,'second');assert.equal(views.has('a:1'),false);
 d.getElementById('caption-earlier').click();await settle();assert.equal(views.get('a:1').offset_ms,-500);
 items[0].audio_index=0;await reopen();assert.equal(select.value,'');
 await choose('first');loseResponse=true;d.getElementById('caption-later').click();await settle();
 assert.equal(select.disabled,true);assert.match(state.textContent,/저장 여부를 확인하지 못/);
 const written=writes.length;d.getElementById('caption-later').click();assert.equal(writes.length,written,'ambiguous saves do not auto-retry');
 d.getElementById('caption-view-retry').click();await settle();assert.equal(select.disabled,false);assert.match(video.querySelector('track').src,/offset_ms=500$/);
 views.set('a:0',{selection:'',offset_ms:0,revision:views.get('a:0').revision+1});
 d.getElementById('caption-later').click();await settle();assert.match(state.textContent,/다른 창/);
 d.getElementById('caption-view-retry').click();await settle();assert.equal(select.value,'');
 delay=true;const saving=choose('first:transcript');await saving;
 await w.qa.closePlayer();await w.qa.openPlayer('b');await settle();assert.equal(select.value,'first');
 pending();delay=false;await settle();assert.equal(select.value,'first','old response cannot change another video');
 await reopen();assert.equal(select.value,'first:transcript');
 delay=true;d.getElementById('caption-later').click();await settle();
 await w.qa.closePlayer();await w.qa.openPlayer('a');await settle();assert.equal(select.disabled,true,'same-item reopen waits for pending save');
 delay=false;pending();await settle();assert.equal(select.value,'first:transcript');assert.match(video.querySelector('track').src,/offset_ms=500$/);
 await choose('');tracks.unshift({id:'new',source:'supplied',audio_index:0});await w.qa.refreshSubtitles(w.qa.owner());assert.equal(select.value,'');
 d.getElementById('caption-auto').click();await settle();assert.equal(select.value,'new');assert.equal(views.get('a:0').selection,null);
 await choose('first:transcript');d.getElementById('caption-later').click();await settle();
 tracks[1].has_transcript=false;await w.qa.refreshSubtitles(w.qa.owner());assert.equal(select.value,'');assert.equal(video.querySelector('track'),null);assert.match(state.textContent,/저장한 자막을 찾을 수/);
 assert.equal(d.getElementById('caption-reset').disabled,true,'missing saved version cannot offer a timing action with no target');
 assert.equal(video.currentTime,7,'view settings never seek or reload the media source');
 assert(writes.every(r=>r.key==='a:0'||r.key==='a:1'));
 // Import completion must not replace a newer audio owner or a newer sync choice,
 // whether its POST response or its following subtitle refresh arrives late.
 const input=d.getElementById('subtitle-input');
 for(const stage of ['post','read'])for(const change of ['audio','sync']){
  items[0].audio_index=0;await reopen();await choose('first');
  d.getElementById('caption-later').click();await settle();
  importDelay=stage;importPending=null;
  Object.defineProperty(input,'files',{configurable:true,value:[new w.File(['captions'],'captions.srt')]});
  input.dispatchEvent(new w.Event('change'));await settle();assert(importPending);
  if(change==='audio'){items[0].audio_index=1;await reopen();}
  else{d.getElementById('caption-later').click();await settle();}
  const count=writes.length,chosen=select.value,src=video.querySelector('track').src;
  const saved=JSON.stringify([...views]);
  importPending();await settle();await settle();
  assert.equal(writes.length,count,stage+'/'+change+' must not write stale import choice');
  assert.equal(select.value,chosen);assert.equal(video.querySelector('track').src,src);
  assert.equal(JSON.stringify([...views]),saved);
 }
 console.log('PASS caption viewing DOM: audio-specific choice/offset, native Off/On, stale write isolation, reopen waits, lost response/conflict recovery, missing track, automatic reset (mocked HTTP/media).');
 dom.window.close();
})().catch(e=>{console.error(e);process.exitCode=1;dom.window.close();});
