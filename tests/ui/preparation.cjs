const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..'),settle=()=>new Promise(resolve=>setImmediate(resolve));
const empty={state:'empty',completed:0,total:0,failed:0,frames:[]};
const partial={state:'partial',completed:1,total:3,failed:0,frames:[{ordinal:0,time:5,available:true,image:'/one.jpg'}]};
const ready={...partial,state:'ready',completed:3};
function fixture(){
  const dom=new JSDOM(fs.readFileSync(root+'/media_clarity/static/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
  const w=dom.window,d=w.document,video=d.getElementById('video'),dialog=d.getElementById('player-dialog');
  let now=0,nextTimer=0;
  const timers=new Map(),requests=[],pending=[];
  w.setTimeout=(fn,ms)=>{timers.set(++nextTimer,{fn,ms});return nextTimer;};w.clearTimeout=id=>timers.delete(id);
  Object.defineProperty(w.performance,'now',{value:()=>now});
  const item={id:'a',title:'fixture',duration:50,position:0,width:160,height:90,available:true};
  w.fetch=async(url,options={})=>{
    requests.push({url,options});
    if(options.method==='POST'&&(url.endsWith('/previews')||url.endsWith('/scenes/prepare'))){
      return new Promise(resolve=>pending.push({url,options,resolve}));
    }
    const result=url==='/api/session'?{token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}}:
      url==='/api/library'?{items:[item]}:url.endsWith('/previews')?empty:
      url.endsWith('/scenes')?{state:'partial',completed:0,total:3}:
      url.endsWith('/preference')?{included:false,preference:'neutral',revision:0}:
      url.includes('/subtitles')?{tracks:[],jobs:[]}:url.endsWith('/position')?{position:0}:item;
    return {ok:true,json:async()=>result};
  };
  video.pause=()=>{};video.load=()=>{};video.play=()=>Promise.resolve();
  dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
  w.eval(fs.readFileSync(root+'/media_clarity/static/app.js','utf8')+'\nglobalThis.qa={openPlayer,closePlayer};');
  const el=id=>d.getElementById(id);
  async function open(){await settle();await w.qa.openPlayer('a');await settle();el('subtitle-search-panel').open=true;}
  async function start(mode){
    const panel=el(mode==='preview'?'preview-panel':'scene-panel');
    // Setting open already queues a native toggle. Do not dispatch a second one:
    // that delayed duplicate can reread empty state after a preparation error.
    const toggled=new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{panel.removeEventListener('toggle',onToggle);reject(new Error('panel toggle timed out'));},5000);
      function onToggle(){clearTimeout(timer);resolve();}
      panel.addEventListener('toggle',onToggle,{once:true});
    });
    panel.open=true;await toggled;await settle();
    el(mode==='preview'?'preview-build':'scene-prepare').click();await settle();
  }
  async function answer(value){assert(pending.length,'expected an in-flight request');pending.shift().resolve({ok:true,json:async()=>value});await settle();}
  const posts=()=>requests.filter(r=>r.options.method==='POST'&&(r.url.endsWith('/previews')||r.url.endsWith('/scenes/prepare')));
  return {w,d,el,open,start,answer,posts,pending,timers,setNow:value=>now=value,close:()=>w.close()};
}
(async()=>{
  // Both entry points used to issue a fourth POST after two unchanged responses.
  for(const mode of ['preview','scene']){
    const f=fixture();try{
      await f.open();await f.start(mode);await f.answer(partial);await f.answer(partial);await f.answer(partial);
      assert.equal(f.posts().length,3,mode+' stops after two responses without new completed work');
      assert.equal(f.pending.length,0);assert.match(f.el(mode==='preview'?'preview-state':'scene-state').textContent,/진행되지/);
      assert(!f.el(mode==='preview'?'preview-build':'scene-prepare').disabled);
      if(mode==='preview')assert.equal(f.d.querySelectorAll('.preview-frame').length,1,'completed tiles survive a stop');
      // A new explicit action can finish using the saved progress.
      f.el(mode==='preview'?'preview-build':'scene-prepare').click();await settle();await f.answer(ready);
      if(mode==='scene')await f.answer(ready);
      assert.equal(f.pending.length,0);
    }finally{f.close();}
  }
  // The analysis stage must have its own high-water mark, separate from previews.
  {
    const f=fixture();try{
      await f.open();await f.start('scene');await f.answer(ready);
      await f.answer(partial);await f.answer(partial);await f.answer(partial);
      assert.equal(f.posts().filter(r=>r.url.endsWith('/scenes/prepare')).length,3);
      assert.match(f.el('scene-state').textContent,/진행되지/);assert(!f.el('scene-prepare').disabled);
    }finally{f.close();}
  }
  // One unresolved HTTP response or body cannot strand preparation controls.
  for(const bodyStall of [false,true]){
    const f=fixture();try{
      await f.open();await f.start('preview');const request=f.pending.shift();
      if(bodyStall){request.resolve({ok:true,json:()=>new Promise(()=>{})});await settle();}
      const timer=[...f.timers.values()].find(t=>t.ms===150000);assert(timer,'bounded request timer');timer.fn();await settle();
      assert(request.options.signal.aborted);assert(!f.el('preview-build').disabled);
      assert.match(f.el('preview-state').textContent,/대기 시간/);assert.equal(f.posts().length,1);
      request.resolve({ok:true,json:async()=>ready});await settle();
      assert.equal(f.d.querySelectorAll('.preview-frame').length,0,'late timeout response cannot publish ready tiles');
    }finally{f.close();}
  }
  {
    const f=fixture();try{
      await f.open();await f.start('preview');f.setNow(600001);await f.answer(partial);
      assert.equal(f.posts().length,1,'elapsed limit prevents the next POST even when work advanced');
      assert.match(f.el('preview-state').textContent,/10분/);assert(!f.el('preview-build').disabled);
    }finally{f.close();}
  }
  for(const value of [{...partial,completed:NaN},{...partial,total:121},{...partial,state:'ready'}]){
    const f=fixture();try{
      await f.open();await f.start('preview');await f.answer(value);
      assert.equal(f.posts().length,1,'invalid progress stops without retry');assert.match(f.el('preview-state').textContent,/진행 상태/);
    }finally{f.close();}
  }
  {
    const f=fixture();try{
      await f.open();await f.start('scene');await f.w.qa.closePlayer();await f.answer(ready);
      assert.equal(f.posts().length,1,'closed player cannot start analysis after preview completion');
      assert.equal(f.el('scene-results').children.length,0);
    }finally{f.close();}
  }
  console.log('PASS preparation DOM: stalled progress, explicit resume, request/body/elapsed bounds, late responses and player isolation (mock HTTP/media).');
})().catch(error=>{console.error(error);process.exitCode=1;});
