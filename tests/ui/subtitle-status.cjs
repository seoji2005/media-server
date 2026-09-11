const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..'),settle=()=>new Promise(resolve=>setImmediate(resolve));
const source=fs.readFileSync(process.env.MEDIA_STATUS_TEST_SOURCE||root+'/media_clarity/static/app.js','utf8');
async function fixture({initialReadError=false}={}){
  const dom=new JSDOM(fs.readFileSync(root+'/media_clarity/static/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
  const w=dom.window,d=w.document,el=id=>d.getElementById(id),video=el('video');
  const f={w,d,el,video,requests:[],timers:new Map(),clock:0,getMode:initialReadError?'error':'normal',commandMode:'normal',captionMode:'normal',held:[],jobs:[]};
  let counter=0;
  Object.defineProperty(w.performance,'now',{value:()=>f.clock});
  w.setTimeout=(fn,ms)=>{f.timers.set(++counter,{fn,ms});return counter;};w.clearTimeout=id=>f.timers.delete(id);
  f.fire=ms=>{for(const [id,t] of [...f.timers])if(t.ms===ms){f.timers.delete(id);t.fn();}};
  const items=['a','b'].map(id=>({id,title:'video '+id,duration:30,position:4,width:320,height:180,available:true,audio_index:0,audio_tracks:[{index:0},{index:1}]}));
  const views={a:{selection:'ready-a',offset_ms:500,revision:1},b:{selection:'ready-b',offset_ms:0,revision:1}};
  const response=data=>({ok:true,json:async()=>data});
  w.fetch=async(url,options={})=>{
    f.requests.push({url,options});const item=items.find(i=>i.id===url.split('/')[3]);
    if(url==='/api/session')return response({token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}});
    if(url==='/api/library')return response({items:items.map(i=>({...i}))});
    if(url.endsWith('/caption-view')){
      const body=JSON.parse(options.body);views[item.id]={...body,revision:body.revision+1};
      if(f.captionMode==='hold')return new Promise(resolve=>f.held.push({resolve,value:response({...views[item.id]}),options,kind:'caption'}));
      return response({...views[item.id]});
    }
    if(options.method==='POST'&&(url.includes('/subtitle-jobs')||url.endsWith('/retranslate'))){
      if(f.commandMode==='hold')return new Promise(resolve=>f.held.push({resolve,value:response({id:'job'}),options,kind:'command'}));
      if(f.commandMode==='reject')return {ok:false,json:async()=>({error:'gemini_key_missing'})};
      if(url.endsWith('/pause'))f.jobs[0].state='paused';
      return response({id:'job'});
    }
    if(url.split('?')[0].endsWith('/subtitles')){
      const data={tracks:[{id:'ready-'+item.id,source:'supplied',language:'ja',audio_index:0,can_retranslate:true}],jobs:JSON.parse(JSON.stringify(f.jobs)),view:{...views[item.id]}};
      if(f.getMode==='headers')return new Promise(resolve=>f.held.push({resolve,value:response(data),options,kind:'read'}));
      if(f.getMode==='body')return {ok:true,json:()=>new Promise(resolve=>f.held.push({resolve,value:data,options,kind:'read'}))};
      if(f.getMode==='error')return {ok:false,json:async()=>({error:'storage_unavailable'})};
      return response(data);
    }
    if(url.includes('/audio/')){item.audio_index=Number(url.split('/').at(-1));return response({...item});}
    if(url.endsWith('/position'))return response({position:JSON.parse(options.body).position});
    if(url.endsWith('/preference'))return response({included:false,preference:'neutral',revision:0});
    assert(item,url);return response({...item});
  };
  Object.defineProperty(video,'readyState',{get:()=>2});Object.defineProperty(video,'duration',{get:()=>30});
  video.pause=()=>{};video.load=()=>{};video.play=()=>Promise.resolve();
  el('player-dialog').showModal=()=>el('player-dialog').open=true;el('player-dialog').close=()=>el('player-dialog').open=false;
  w.eval(source+'\nglobalThis.qa={openPlayer,closePlayer,refreshSubtitles,get owner(){return activeItem;}};');
  await settle();await w.qa.openPlayer('a');await settle();video.currentTime=7;
  f.read=options=>w.qa.refreshSubtitles(w.qa.owner,options);
  f.commands=()=>f.requests.filter(r=>r.options.method==='POST'&&(r.url.includes('/subtitle-jobs')||r.url.endsWith('/retranslate')));
  f.snapshot=()=>({src:video.src,time:video.currentTime,track:video.querySelector('track')?.src});
  f.close=()=>w.close();return f;
}
(async()=>{
  let f=await fixture();
  try{
    const before=f.snapshot();f.commandMode='hold';
    f.el('subtitle-generate').click();f.el('subtitle-generate').click();await settle();
    assert.equal(f.commands().length,1,'an in-flight generation cannot be submitted twice');
    assert(f.el('subtitle-retranslate').disabled);assert.deepEqual(f.snapshot(),before);
    const held=f.held.find(x=>x.kind==='command');f.fire(30000);await settle();
    assert(held.options.signal.aborted);assert(f.el('subtitle-generate').disabled);assert(!f.el('subtitle-refresh').hidden);
    assert.equal(f.commands().length,1,'timeout never retries the command');
    // A failed confirmation must keep the unresolved command blocked.
    f.getMode='error';f.el('subtitle-refresh').click();await settle();assert(f.el('subtitle-generate').disabled);
    f.getMode='normal';f.el('subtitle-refresh').click();await settle();assert(!f.el('subtitle-generate').disabled);
    held.resolve(held.value);await settle();assert.deepEqual(f.snapshot(),before,'late command acknowledgement does not touch playback');
    assert.equal(f.commands().length,1,'confirmation is read-only');
    f.commandMode='reject';f.el('subtitle-retranslate').click();await settle();assert(!f.el('subtitle-retranslate').disabled,'definite missing-key rejection permits explicit correction');
  }finally{f.close();}
  f=await fixture();try{
    f.getMode='error';await f.read();f.getMode='headers';f.el('subtitle-refresh').click();await settle();
    const held=f.held.find(x=>x.kind==='read');assert(held);
    assert(!f.el('subtitle-refresh').hidden,'recovery remains visible until the status response completes');
    assert(f.el('subtitle-refresh').disabled);assert(f.el('subtitle-generate').disabled,'recovery cannot enable commands before a response');
    held.resolve(held.value);await settle();assert(f.el('subtitle-refresh').hidden);assert(!f.el('subtitle-generate').disabled);
  }finally{f.close();}
  f=await fixture({initialReadError:true});try{
    assert(f.el('subtitle-select').disabled);assert(f.el('subtitle-generate').disabled);
    f.getMode='normal';f.el('subtitle-refresh').click();await settle();
    assert(!f.el('subtitle-select').disabled);assert(!f.el('subtitle-generate').disabled,'first-read recovery also clears unknown caption state');
  }finally{f.close();}
  for(const mode of ['headers','body']){
    f=await fixture();try{
      const before=f.snapshot();f.getMode=mode;const reading=f.read();await settle();
      const held=f.held.find(x=>x.kind==='read');f.fire(30000);await reading;await settle();
      assert(held.options.signal.aborted);assert(!f.el('subtitle-refresh').hidden);assert(!f.el('subtitle-refresh').disabled);
      assert(![...f.timers.values()].some(t=>t.ms===1500),'failed read stops polling');assert.deepEqual(f.snapshot(),before);
      f.getMode='normal';f.el('subtitle-refresh').click();await settle();assert(f.el('subtitle-refresh').hidden);
      held.resolve(held.value);await settle();assert.deepEqual(f.snapshot(),before,'late response cannot replace loaded caption');
    }finally{f.close();}
  }
  f=await fixture();try{
    f.jobs=[{id:'j',state:'running',stage:'asr',attempt:1,asr_completed:2,asr_until:9}];await f.read();
    f.clock=299999;f.jobs[0].asr_completed=1;await f.read();assert(f.el('subtitle-refresh').hidden);
    f.clock=300000;await f.read();assert(!f.el('subtitle-refresh').hidden);assert(!f.el('subtitle-pause').disabled);
    assert.match(f.el('subtitle-state').textContent,/5분/);assert(![...f.timers.values()].some(t=>t.ms===1500));
    f.el('subtitle-pause').click();await settle();assert(f.commands().at(-1).url.endsWith('/pause'),'manual pause remains usable after polling stops');
    f.jobs[0].state='running';await f.read();f.clock+=600000;f.jobs[0].asr_completed=10;await f.read();
    assert.match(f.el('subtitle-state').textContent,/10분/,'ongoing progress cannot extend the total monitoring budget');
    f.el('subtitle-refresh').click();await settle();assert(f.el('subtitle-refresh').hidden);assert([...f.timers.values()].some(t=>t.ms===1500));
  }finally{f.close();}
  f=await fixture();try{
    f.jobs=[{id:'j',state:'running',stage:'translation',attempt:1,completed:0,total:1000}];
    for(let i=0;i<399;i++){f.jobs[0].completed=i;await f.read();}
    assert.match(f.el('subtitle-state').textContent,/400회/,'successful changing snapshots still have a request budget');
    assert(![...f.timers.values()].some(t=>t.ms===1500));
  }finally{f.close();}
  f=await fixture();try{
    f.captionMode='hold';f.el('caption-later').click();await settle();const held=f.held.find(x=>x.kind==='caption');
    assert(held);f.fire(30000);await settle();assert(held.options.signal.aborted);
    assert(!f.el('caption-view-retry').hidden);assert(!f.el('subtitle-refresh').disabled,'pending caption save no longer holds the read forever');
    f.el('caption-view-retry').click();await settle();assert(!f.el('subtitle-select').disabled);
    const snapshot=f.snapshot();held.resolve(held.value);await settle();assert.deepEqual(f.snapshot(),snapshot);
  }finally{f.close();}
  f=await fixture();try{
    f.commandMode='hold';f.el('subtitle-generate').click();await settle();const held=f.held.find(x=>x.kind==='command');
    await f.w.qa.closePlayer();const reads=f.requests.filter(r=>r.url.split('?')[0].endsWith('/subtitles')).length;
    await f.w.qa.openPlayer('a');await settle();assert(f.el('subtitle-generate').disabled);
    assert.equal(f.requests.filter(r=>r.url.split('?')[0].endsWith('/subtitles')).length,reads,'same-item reopen waits for pending command');
    held.resolve(held.value);await settle();await settle();assert(!f.el('subtitle-generate').disabled);
  }finally{f.close();}
  f=await fixture();try{
    f.commandMode='hold';f.el('subtitle-generate').click();await settle();const held=f.held.find(x=>x.kind==='command');
    f.el('audio-select').value='1';f.el('audio-select').dispatchEvent(new f.w.Event('change'));f.el('audio-apply').click();await settle();
    assert.match(f.video.src,/audio_index=1$/);assert(f.el('subtitle-generate').disabled);
    held.resolve(held.value);await settle();await settle();assert(!f.el('subtitle-generate').disabled);
    f.el('subtitle-generate').click();await settle();const late=f.held.at(-1);
    await f.w.qa.closePlayer();await f.w.qa.openPlayer('b');await settle();const before=f.snapshot();
    late.resolve(late.value);await settle();assert.equal(f.el('player-title').textContent,'video b');assert.deepEqual(f.snapshot(),before);
    assert.equal(f.w.localStorage.length,0);assert.equal(f.w.sessionStorage.length,0);
  }finally{f.close();}
  console.log('PASS subtitle status DOM: bounded headers/body/commands/caption saves, duplicate clicks, explicit read-only recovery, no-progress/elapsed stops, pause, audio/item isolation (mock HTTP/media).');
})().catch(error=>{console.error(error);process.exitCode=1;});
