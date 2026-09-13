// Real product JS with controlled HTTP/timers; not native browser viewing.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..');
const html=fs.readFileSync(path.join(root,'media_clarity/static/index.html'),'utf8');
const source=fs.readFileSync(path.join(root,'media_clarity/static/app.js'),'utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const item={id:'a'.repeat(32),title:'다시 찾은 영상',duration:20,position:7.25,width:320,height:180,available:true,thumbnail:false};
function fixture(mode){
  const dom=new JSDOM(html,{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
  const w=dom.window,d=w.document,requests=[],timers=new Map();let timerId=0,now=0,release;
  w.setTimeout=(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;};
  w.clearTimeout=id=>timers.delete(id);
  w.performance.now=()=>now;
  const state={mode};
  w.fetch=async(url,options={})=>{
    requests.push({url,...options});
    const data=url==='/api/session'?{token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}}:{items:[item]};
    assert(['/api/session','/api/library'].includes(url),'startup recovery only reads session and library');
    if(state.mode===url+'-fail')throw Error('fixture unavailable');
    if(state.mode===url+'-hold')return new Promise(resolve=>{release=()=>resolve({ok:true,json:async()=>data});});
    if(state.mode===url+'-body')return {ok:true,json:()=>new Promise(resolve=>{release=()=>resolve(data);})};
    if(state.mode===url+'-invalid')return {ok:true,json:async()=>({})};
    if(url==='/api/session')now+=3000; // Library must share the original ten-second budget.
    return {ok:true,json:async()=>data};
  };
  w.eval(source+'\nglobalThis.qa={importFile};');
  return {w,d,requests,timers,state,release:()=>release?.(),close:()=>w.close()};
}
(async()=>{
  const normal=fixture('normal');
  try{
    await tick();assert.match(normal.d.getElementById('library-grid').textContent,/다시 찾은 영상/);
    assert.equal(normal.d.getElementById('loading-state').hidden,true);
    assert.equal(normal.requests.length,2);assert.equal(normal.timers.size,0);
  }finally{normal.close();}
  for(const mode of ['/api/session-fail','/api/library-fail','/api/session-hold','/api/library-body','/api/session-invalid','/api/library-invalid']){
    const f=fixture(mode);const {w,d,requests,timers,state}=f;
    try{
      await tick();
      if(mode.endsWith('-hold')||mode.endsWith('-body')){
        const pending=[...timers.entries()].filter(([,t])=>t.ms<=10000);
        assert.equal(pending.length,1,'startup response/body must have a bounded wait');
        assert.equal(pending[0][1].ms,mode.startsWith('/api/session')?10000:7000);
        timers.delete(pending[0][0]);pending[0][1].fn();await tick();
        assert.equal(requests.at(-1).signal.aborted,true);
      }
      d.getElementById('nav-all').click();
      assert.equal(d.getElementById('empty-state').hidden,true,'an unread library must not be presented as empty');
      assert.equal(d.getElementById('loading-state').hidden,true);
      const notice=d.getElementById('connection-recovery'),retry=d.getElementById('connection-retry');
      assert(notice&&!notice.hidden,'failed startup must offer an explicit recovery action');
      assert.equal(retry.disabled,false);assert.equal(d.getElementById('import-top').disabled,true);
      const before=requests.length;await w.qa.importFile({size:10,name:'sample.mp4'});await tick();
      assert.equal(requests.length,before,'drop/file import must wait for initial connection');
      d.getElementById('search').value='다시';d.getElementById('nav-continue').click();
      state.mode='normal';retry.focus();retry.click();retry.click();await tick();
      assert.equal(requests.length,before+2,'two clicks must start one read-only connection attempt');
      assert.match(d.getElementById('library-grid').textContent,/다시 찾은 영상/);
      assert.equal(d.getElementById('search').value,'다시');
      assert.equal(d.getElementById('nav-continue').getAttribute('aria-current'),'page');
      assert.equal(notice.hidden,true);assert.equal(d.getElementById('import-top').disabled,false);
      f.release();await tick();assert.equal(notice.hidden,true,'expired old response cannot replace recovery');
      assert(!requests.some(r=>r.method&&r.method!=='GET'),'recovery does not import or replay a write');
    }finally{f.close();}
  }
  console.log('PASS startup DOM: normal load, failed/invalid session or library, shared deadline including body, explicit retry, no false empty state, stale completion, filters and no writes (mock HTTP).');
})().catch(e=>{console.error(e);process.exitCode=1;});
