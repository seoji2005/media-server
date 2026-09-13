// Actual product JS; virtual clock and mocked media/HTTP, not browser durability.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..');
async function check(commitBeforeResponse){
  const dom=new JSDOM(fs.readFileSync(path.join(root,'media_clarity/static/index.html'),'utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
  const w=dom.window,d=w.document,video=d.getElementById('video'),dialog=d.getElementById('player-dialog');
  const timers=new Map(),requests=[],held=[];
  const library=['a','b'].map(id=>({id,title:id,duration:120,position:8.25,position_revision:0,width:320,height:180,available:true,thumbnail:false,audio_index:0}));
  let clock=0,timerId=0,holdNext=false,blockRead=false;
  w.setTimeout=(fn,ms)=>{timers.set(++timerId,{fn,at:clock+ms});return timerId;};
  w.clearTimeout=id=>timers.delete(id);
  const tick=()=>new Promise(resolve=>setImmediate(resolve));
  async function advance(ms){
    const end=clock+ms;
    for(;;){
      const next=[...timers.entries()].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];
      if(!next)break;
      clock=next[1].at;timers.delete(next[0]);next[1].fn();await tick();
    }
    clock=end;await tick();
  }
  const response=(value,status=200)=>({ok:status===200,json:async()=>value});
  w.fetch=async(url,options={})=>{
    if(url==='/api/session')return response({token:'synthetic',diagnostics:{ffmpeg:true,ffprobe:true,recovered_copies:0}});
    if(url==='/api/library')return response({items:library.map(x=>({...x}))});
    const item=library.find(x=>x.id===url.split('/')[3]);assert(item,url);
    if(url.split('?')[0].endsWith('/subtitles'))return response({jobs:[],tracks:[]});
    if(url.endsWith('/position')){
      const body=JSON.parse(options.body);requests.push({id:item.id,...body,options});
      assert.equal(options.headers['X-Media-Token'],'synthetic');
      assert.equal(options.keepalive,true);
      assert(Number.isInteger(body.expected_revision),'every new UI write must carry its read revision');
      const commit=()=>{
        if(body.expected_revision!==item.position_revision)return response({error:'position_changed'},409);
        item.position=body.position;item.position_revision++;
        return response({position:item.position,position_revision:item.position_revision});
      };
      if(holdNext){
        holdNext=false;
        const early=commitBeforeResponse?commit():null;
        // Deliberately ignore client abort: the server may still finish its write.
        await new Promise(resolve=>held.push(resolve));
        return early||commit();
      }
      return commit();
    }
    if(blockRead&&item.id==='a')return new Promise(()=>{});
    return response({...item});
  };
  Object.defineProperty(video,'readyState',{get:()=>1});Object.defineProperty(video,'duration',{get:()=>120});
  video.play=()=>Promise.resolve();video.pause=()=>video.dispatchEvent(new w.Event('pause'));video.load=()=>{video.currentTime=0;};
  dialog.showModal=()=>{dialog.open=true;};dialog.close=()=>{dialog.open=false;};
  w.eval(fs.readFileSync(path.join(root,'media_clarity/static/app.js'),'utf8')+'\nglobalThis.qa={openPlayer,closePlayer,savePosition};');
  try{
    await tick();await w.qa.openPlayer('a');video.dispatchEvent(new w.Event('loadedmetadata'));
    video.currentTime=10;await w.qa.closePlayer();assert.equal(library[0].position,10);
    await w.qa.openPlayer('a');video.dispatchEvent(new w.Event('loadedmetadata'));assert.equal(video.currentTime,10);
    holdNext=true;video.currentTime=20;video.dispatchEvent(new w.Event('seeked'));await tick();
    for(const value of [21,22,25]){video.currentTime=value;video.dispatchEvent(new w.Event('seeked'));}
    let closeDone=false;w.qa.closePlayer().then(()=>{closeDone=true;});
    assert.equal(dialog.open,false,'closing must not wait for the network');
    await advance(1000);assert(closeDone,'close caller must settle within one second');
    await w.qa.openPlayer('a');video.dispatchEvent(new w.Event('loadedmetadata'));
    assert.equal(video.currentTime,25,'same-page reopen retains newest unsaved intent');
    w.qa.closePlayer();await advance(1000);
    await w.qa.openPlayer('b');video.dispatchEvent(new w.Event('loadedmetadata'));
    video.currentTime=3;await w.qa.savePosition();assert.equal(library[1].position,3,'another item saves while A is stalled');
    await advance(3000);
    assert.equal(library[0].position,25,'latest queued seek saves after uncertain response');
    assert.deepEqual(requests.filter(r=>r.id==='a').map(r=>r.position),[10,20,25],'intermediate seeks are coalesced');
    const revision=library[0].position_revision;
    held.shift()();await tick();
    assert.equal(library[0].position,25,'late server completion cannot overwrite newer position');
    assert.equal(library[0].position_revision,revision);
    assert.match(d.getElementById('save-state').textContent,/0:03 저장됨/,'late response cannot change the newer player');
    await w.qa.closePlayer();await w.qa.openPlayer('a');video.dispatchEvent(new w.Event('loadedmetadata'));
    holdNext=true;video.currentTime=30;video.dispatchEvent(new w.Event('seeked'));await tick();
    blockRead=true;video.currentTime=35;video.dispatchEvent(new w.Event('seeked'));
    await advance(10000);
    assert.match(d.getElementById('save-state').textContent,/저장 미확인/);
    assert.equal(library[0].position,commitBeforeResponse?30:25);
    assert.equal(requests.filter(r=>r.id==='a'&&r.position===35).length,0,'failed read cannot become an unguarded write');
    blockRead=false;held.shift()();await tick();
    video.currentTime=36;await w.qa.savePosition();assert.equal(library[0].position,36);
    w.dispatchEvent(new w.Event('pagehide'));await tick();
    assert.equal(requests.at(-1).position,36);
  }finally{for(const release of held)release();w.close();}
}
(async()=>{for(const mode of [false,true])await check(mode);console.log('PASS position DOM: bounded close, per-item isolation, coalescing, uncertain pre/post-commit response, late-write guard, retained intent and failure recovery (mock HTTP/media).');})().catch(e=>{console.error(e);process.exitCode=1;});
