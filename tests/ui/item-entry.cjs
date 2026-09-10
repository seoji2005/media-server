const assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');

module.exports=async function checkItemEntry(html,source){
 const reference=id=>({version:1,server_id:'1'.repeat(32),library_id:'2'.repeat(32),item_id:id.repeat(32),file_id:id.repeat(32),sha256:id.repeat(64)});
 const fragment=value=>'#item='+encodeURIComponent(JSON.stringify(value));
 for(const delayed of ['session','entry']){
  const a=reference('a'),b=reference('b');
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8765/'+fragment(a),runScripts:'outside-only'});
  const w=dom.window,d=w.document,v=d.getElementById('video'),dialog=d.getElementById('player-dialog');
  const tick=()=>new Promise(resolve=>setTimeout(resolve,10));
  const items=[a,b].map(r=>({id:r.item_id,file_id:r.file_id,sha256:r.sha256,title:'<private> 영상',duration:20,position:8.25,
    audio_index:1,audio_tracks:[{index:0},{index:1}],available:true,preparation:'audio_mp4',thumbnail:false}));
  let release,held=true,holdNext=false,releaseNext,failNext=false,plays=0;
  const gate=new Promise(resolve=>release=resolve),writes=[],posts=[],native=new WeakMap();
  const track={id:'c'.repeat(32),source:'supplied',language:'ja',audio_index:1};
  const view={selection:'',offset_ms:0,revision:1};
  w.fetch=async(url,options={})=>{
   assert.equal(w.location.hash,'','fragment must be consumed before HTTP');
   let data;
   if(url==='/api/session'){
    if(delayed==='session'&&held){held=false;await gate;}
    data={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
   }else if(url==='/api/library')data={items};
   else{
    const item=items.find(i=>i.id===url.split('/')[3]);assert(item,url);
    if(options.method==='POST')posts.push(url);
    if(options.method==='PUT')writes.push(url);
    if(url.endsWith('/item-entry')){
     assert.equal(options.headers['X-Media-Token'],'fixture');
     if(delayed==='entry'&&held){held=false;await gate;}
     if(holdNext){holdNext=false;await new Promise(resolve=>releaseNext=resolve);if(failNext)return {ok:false,json:async()=>({error:'item_reference_changed'})};}
     if(JSON.parse(options.body).library_id!==a.library_id)return {ok:false,json:async()=>({error:'item_reference_changed'})};
     data={version:1,server_id:a.server_id,library_id:a.library_id,item};
    }else if(url.endsWith('/playback')){item.available=true;item.unavailable_reason=null;data=item;}
    else if(url.split('?')[0].endsWith('/subtitles'))data={tracks:[track],jobs:[],view};
    else if(url.endsWith('/preference'))data={included:false,preference:'neutral',revision:0};
    else data=item;
   }
   return {ok:true,json:async()=>JSON.parse(JSON.stringify(data))};
  };
  Object.defineProperty(w.HTMLTrackElement.prototype,'track',{get(){if(!native.has(this))native.set(this,{mode:'showing',cues:[]});return native.get(this);}});
  Object.defineProperty(v,'textTracks',{value:new w.EventTarget()});
  Object.defineProperty(v,'readyState',{get:()=>2});Object.defineProperty(v,'duration',{get:()=>20});
  v.play=()=>{plays++;v.dispatchEvent(new w.Event('play'));return Promise.resolve();};
  v.pause=()=>v.dispatchEvent(new w.Event('pause'));v.load=()=>{};
  dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
  try{
   w.eval(source+'\nglobalThis.qa={openPlayer,closePlayer,owner:()=>activeItem};');
   await tick();w.location.hash=fragment(b);await tick();release();await tick();
   assert.equal(w.qa.owner().id,b.item_id,'latest entry wins over slow startup/read');
   w.location.hash=fragment({...a,library_id:'f'.repeat(32)});await tick();
   v.dispatchEvent(new w.Event('loadedmetadata'));assert.equal(v.currentTime,8.25);
   assert.equal(plays,0);assert.equal(d.getElementById('subtitle-select').value,'');assert.equal(v.querySelector('track'),null);
   assert.match(v.src,/audio_index=1$/);assert.equal(d.getElementById('player-title').textContent,'<private> 영상');
   v.currentTime=10;v.dispatchEvent(new w.Event('seeked'));v.dispatchEvent(new w.Event('pause'));w.dispatchEvent(new w.Event('pagehide'));await tick();
   assert.equal(writes.length,0);assert(posts.every(p=>p.endsWith('/item-entry')));
   w.location.hash=fragment({...a,library_id:'f'.repeat(32)});await tick();
   assert.equal(w.qa.owner().id,b.item_id,'invalid incoming link must not close existing player');assert.equal(dialog.open,true);assert.equal(writes.length,0);
   // A stale error cannot overwrite the newest player's status or selection.
   holdNext=true;w.location.hash=fragment(a);await tick();
   w.location.hash=fragment(b);await tick();failNext=true;releaseNext();await tick();failNext=false;
   assert.equal(w.qa.owner().id,b.item_id);assert.equal(d.getElementById('item-entry-notice').hidden,true);
   await w.qa.closePlayer();assert.equal(writes.length,0);
   view.selection=track.id;view.offset_ms=500;view.revision=2;
   w.location.hash=fragment(a);await tick();
   assert.equal(d.getElementById('subtitle-select').value,track.id);assert.match(v.querySelector('track').src,/offset_ms=500$/);
   await w.qa.closePlayer();
   await w.qa.openPlayer(b.item_id,b,'item');await tick();
   items[0].available=false;items[0].unavailable_reason='rendition_required';
   w.location.hash=fragment(a);await tick();
   assert.equal(dialog.open,true);assert.equal(w.qa.owner().id,b.item_id);
   await w.qa.closePlayer();
   assert.equal(d.getElementById('item-entry-notice').hidden,false);
   assert.equal(posts.filter(p=>p.endsWith('/playback')).length,0,'navigation cannot prepare a rendition');
   d.getElementById('item-entry-prepare').click();await tick();
   assert.equal(posts.filter(p=>p.endsWith('/playback')).length,1);assert.equal(dialog.open,true);assert.equal(plays,0);assert.equal(writes.length,0);
   v.dispatchEvent(new w.Event('loadedmetadata'));await v.play();v.currentTime=9;v.pause();await tick();assert.equal(writes.length,1);
   await w.qa.closePlayer();const count=posts.length;
   for(const bad of [{...a,position:0},{...a,version:true},{...a,sha256:'bad'}]){w.location.hash=fragment(bad);await tick();}
   w.location.hash='#item=%ZZ';await tick();w.location.hash='#item='+'x'.repeat(2049);await tick();
   assert.equal(posts.length,count,'invalid fragments never reach entry API');assert.equal(dialog.open,false);
  }finally{release();releaseNext?.();w.close();}
 }
 console.log('PASS item entry DOM: consumed identity, stale success/error, current-player preservation, selected audio/Off/offset, explicit preparation, no pre-play writes (mock HTTP/media).');
};
