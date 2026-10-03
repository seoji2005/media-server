// Controlled HTTP/body deadlines; media is mocked, not native playback evidence.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..'),tick=()=>new Promise(resolve=>setImmediate(resolve));
async function fixture(kind,phase){
 const dom=new JSDOM(fs.readFileSync(root+'/media_clarity/static/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
 const w=dom.window,d=w.document,el=id=>d.getElementById(id),video=el('video');
 const f={w,el,video,requests:[],held:[],timers:new Map(),busy:false,read:'normal'};let timer=0;
 w.setTimeout=(fn,ms)=>{f.timers.set(++timer,{fn,ms});return timer;};w.clearTimeout=id=>f.timers.delete(id);
 f.fire=ms=>{for(const [id,t] of [...f.timers])if(t.ms===ms){f.timers.delete(id);t.fn();}};
 const items=['a','b'].map(id=>({id,title:id,duration:20,position:4,width:320,height:180,available:true,audio_index:0,audio_tracks:[{index:0},{index:1}],preparation:'original'}));
 f.items=items;const response=value=>({ok:true,json:async()=>structuredClone(value)});
 w.fetch=async(url,options={})=>{
  f.requests.push({url,options});const item=items.find(i=>i.id===url.split('/')[3]);
  if(url==='/api/session')return response({token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}});
  if(url==='/api/library')return response({items});
  if(options.method==='POST'&&(url.endsWith('/playback')||url.includes('/audio/'))){
   const value={...item,available:true,unavailable_reason:null,audio_index:kind==='audio'?1:0};
   if(phase==='headers')return new Promise(resolve=>f.held.push({resolve,value:response(value),options}));
   return {ok:true,json:()=>new Promise(resolve=>f.held.push({resolve,value,options}))};
  }
  if(url.endsWith('/playback-status')){
   if(f.read==='error')throw Error('offline');
   const value={busy:f.busy,item:{...item}};
   if(f.read==='hold')return new Promise(resolve=>f.held.push({resolve,value:response(value),options}));
   return response(value);
  }
  if(url.includes('/subtitles'))return response({tracks:[],jobs:[]});
  if(url.endsWith('/preference'))return response({included:false,preference:'neutral',revision:0});
  if(url.endsWith('/position'))return response({position:JSON.parse(options.body).position});
  assert(item,url);return response(item);
 };
 Object.defineProperty(video,'readyState',{get:()=>2});Object.defineProperty(video,'duration',{get:()=>20});
 video.play=()=>Promise.resolve();video.pause=()=>{};video.load=()=>video.currentTime=0;
 el('player-dialog').showModal=()=>el('player-dialog').open=true;el('player-dialog').close=()=>el('player-dialog').open=false;
 w.eval(fs.readFileSync(process.env.MEDIA_PLAYBACK_TEST_SOURCE||root+'/media_clarity/static/app.js','utf8')+'\nglobalThis.qa={openPlayer,closePlayer,preparePlayback};');
 await tick();await w.qa.openPlayer('a');await tick();video.currentTime=7;
 f.posts=()=>f.requests.filter(r=>r.options.method==='POST');
 f.start=()=>{if(kind==='playback')return w.qa.preparePlayback('a');el('audio-select').value='1';el('audio-select').dispatchEvent(new w.Event('change'));el('audio-apply').click();};
 return f;
}
(async()=>{
 for(const kind of ['audio','playback'])for(const phase of ['headers','body']){
  const f=await fixture(kind,phase);try{
   const src=f.video.src;f.start();await tick();f.start();await tick();assert.equal(f.posts().length,1);
   f.fire(150000);await tick();await tick();
   assert(f.held[0].options.signal?.aborted,'stalled '+kind+' '+phase+' must have a bounded wait');
   assert.equal(f.video.src,src);assert.equal(f.video.currentTime,7);
   assert(!f.el('playback-recovery').hidden);assert.equal(f.posts().length,1);
   const check=()=>kind==='audio'?f.el('audio-check'):f.el('playback-recovery-items').querySelector('button');
   f.busy=true;check().click();await tick();assert(!f.el('playback-recovery').hidden);assert.equal(f.posts().length,1);
   f.busy=false;f.read='error';check().click();await tick();assert(!f.el('playback-recovery').hidden);
   f.read='normal';f.items[0].audio_index=kind==='audio'?1:0;check().click();await tick();await tick();
   assert(f.el('playback-recovery').hidden);assert.equal(f.posts().length,1,'confirmation must not repeat preparation');
   if(kind==='audio'){f.video.dispatchEvent(new f.w.Event('loadedmetadata'));await tick();assert.match(f.video.src,/audio_index=1$/);assert.equal(f.video.currentTime,7);}
   const finalSrc=f.video.src;f.held[0].resolve(f.held[0].value);await tick();assert.equal(f.video.src,finalSrc,'late original response is ignored');
  }finally{f.w.close();}
 }
 {
  const f=await fixture('audio','headers');try{
   f.start();await tick();await f.w.qa.closePlayer();await f.w.qa.openPlayer('a');await tick();
   assert(f.el('audio-apply').disabled,'same-item reopen retains pending command guard');
   f.fire(150000);await tick();await tick();assert(!f.el('audio-check').hidden);
   f.read='hold';f.items[0].audio_index=1;f.el('audio-check').click();await tick();const read=f.held.at(-1);
   await f.w.qa.closePlayer();await f.w.qa.openPlayer('b');await tick();const src=f.video.src;
   read.resolve(read.value);await tick();await tick();assert.equal(f.video.src,src);assert.equal(f.el('player-title').textContent,'b');
   assert.equal(f.posts().length,1);
  }finally{f.w.close();}
 }
 {
  const f=await fixture('playback','headers');try{
   f.start();await tick();f.fire(150000);await tick();await tick();f.read='hold';
   f.el('playback-recovery-items').querySelector('button').click();await tick();f.fire(10000);await tick();await tick();
   assert(!f.el('playback-recovery').hidden);assert(!f.el('playback-recovery-items').querySelector('button').disabled);
   assert.equal(f.posts().length,1);
  }finally{f.w.close();}
 }
 console.log('PASS playback recovery DOM: audio/preparation header and body bounds, one command, read-only busy/error recovery, pinned current playback, late response and reopen isolation.');
})().catch(e=>{console.error(e);process.exitCode=1;});
