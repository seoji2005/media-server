const fs = require('node:fs');
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const repo = require('node:path').resolve(__dirname, '../..');
const html = fs.readFileSync(`${repo}/media_clarity/static/index.html`, 'utf8');
const source = fs.readFileSync(`${repo}/media_clarity/static/app.js`, 'utf8');
async function run(js) {
  const dom = new JSDOM(html, {url:'http://127.0.0.1:8765', runScripts:'outside-only'});
  const w=dom.window, d=w.document, timers=new Map(), writes=[];
  let timerId=0, preparationFailed=false, listFailure=false, holdList=false, releaseList;
  let preparationWrites=0;
  const library=[{id:'fixture-a',title:'<img src=x onerror=alert(1)> 영상',duration:25,position:8.25,width:640,height:360,available:true,thumbnail:false}, {id:'fixture-b',title:'다른 영상',duration:25,position:0,width:640,height:360,available:true,thumbnail:false}];
  w.setTimeout=(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;};
  w.clearTimeout=id=>timers.delete(id);
  w.fetch=async (path,opts={})=>{
    let result;
    if(path==='/api/session') result={token:'synthetic-token',diagnostics:{ffprobe:true,ffmpeg:true,recovered_copies:0}};
    else if(path==='/api/library') {
      if(listFailure){listFailure=false;throw Error('fixture list unavailable');}
      result={items:library.map(x=>({...x}))};
      if(holdList){holdList=false;return {ok:true,json:()=>new Promise(resolve=>{releaseList=(value=result)=>resolve(value);})};}
    }
    else {const id=path.split('/')[3], item=library.find(x=>x.id===id); assert(item,path);
      if(path.split('?')[0].endsWith('/subtitles')) result={jobs:[],tracks:[]};
      else if(path.endsWith('/playback')) {
        preparationWrites++;
        assert.equal(opts.method,'POST');assert.equal(opts.headers['X-Media-Token'],'synthetic-token');
        if(!preparationFailed){preparationFailed=true;item.preparation_error='media_timeout';return {ok:false,json:async()=>({error:'media_timeout'})};}
        item.available=true;item.unavailable_reason=null;item.preparation_error=null;result={...item};
      }
      else if(path.endsWith('/title')&&opts.method==='PUT'){item.title=JSON.parse(opts.body).title;result={...item};}
      else if(opts.method==='PUT'){const position=JSON.parse(opts.body).position; writes.push({id,position});item.position=position;item.position_revision=(item.position_revision||0)+1;result={...item};}
      else result={...item};
    }
    return {ok:true,json:async()=>result};
  };
  const video=d.getElementById('video');
  Object.defineProperty(video,'readyState',{get:()=>1});
  Object.defineProperty(video,'duration',{get:()=>25});
  video.play=()=>Promise.resolve(); video.pause=()=>video.dispatchEvent(new w.Event('pause')); video.load=()=>{video.currentTime=0;};
  const dialog=d.getElementById('player-dialog');dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
  const settle=async()=>{await new Promise(resolve=>setImmediate(resolve));};
  w.eval(js+"\nglobalThis.__qa={openPlayer,closePlayer,refresh,showImportRecovery};"); await settle();
  assert.equal(d.querySelectorAll('.media-card').length,2,d.getElementById('diagnostic').textContent);
  assert.equal(d.querySelector('.media-card h3').textContent,library[0].title);
  assert.equal(d.querySelector('.media-card h3 img'),null,'title must render as text');
  d.getElementById('search').value='다른';d.getElementById('search').dispatchEvent(new w.Event('input'));
  assert.equal(d.querySelectorAll('.media-card').length,1);
  d.getElementById('search').value='';d.getElementById('nav-continue').click();
  assert.equal(d.querySelectorAll('.media-card').length,1);
  await w.__qa.openPlayer('fixture-a');video.dispatchEvent(new w.Event('loadedmetadata'));assert.equal(video.currentTime,8.25);
  video.currentTime=10;video.dispatchEvent(new w.Event('timeupdate'));
  assert.equal([...timers.values()].filter(x=>x.ms===4000).length,1);
  await w.__qa.closePlayer(); assert.equal(writes.at(-1).position,10);
  assert.equal([...timers.values()].filter(x=>x.ms===4000).length,0);
  await w.__qa.openPlayer('fixture-a');video.dispatchEvent(new w.Event('loadedmetadata'));assert.equal(video.currentTime,10);
  video.currentTime=12;video.dispatchEvent(new w.Event('timeupdate'));
  const periodic=[...timers.entries()].filter(([,x])=>x.ms===4000);
  assert.equal(periodic.length,1,'reopened player must schedule periodic position saves');
  timers.delete(periodic[0][0]);periodic[0][1].fn(); await settle();
  assert.equal(writes.at(-1).position,12);
  video.currentTime=6;video.dispatchEvent(new w.Event('seeked'));
  video.currentTime=7;video.dispatchEvent(new w.Event('pause'));await settle();
  assert.deepEqual(writes.slice(-2).map(x=>x.position),[6,7]);
  await w.__qa.closePlayer();library[1].available=false;await w.__qa.openPlayer('fixture-b');
  assert.equal(dialog.open,false);assert.match(d.getElementById('toast').textContent,/파일을 찾을 수 없습니다/);
  library[1].unavailable_reason='managed_file_changed';
  await w.__qa.openPlayer('fixture-b');
  assert.equal(dialog.open,false);assert.match(d.getElementById('toast').textContent,/파일이 변경되었습니다/);
  await w.__qa.refresh();d.getElementById('nav-all').click();
  assert.match(d.getElementById('library-grid').textContent,/보관 파일이 변경됨/);
  await w.__qa.openPlayer('fixture-a');video.dispatchEvent(new w.Event('loadedmetadata'));
  library[0].available=false;library[0].unavailable_reason='managed_file_changed';
  video.dispatchEvent(new w.Event('error'));await settle();
  assert.match(d.getElementById('video-error').textContent,/파일이 변경되었습니다/);
  await w.__qa.closePlayer();
  assert.equal(d.querySelectorAll('.media-card .missing').length,2,'media error must update the cached library state');
  library[1].unavailable_reason='rendition_required';library[1].preparation='audio_mp4';
  await w.__qa.openPlayer('fixture-b');await settle();assert.equal(dialog.open,false);
  assert.match(d.getElementById('toast').textContent,/보관된 원본은 유지/);
  assert.match(d.getElementById('library-grid').textContent,/재생 준비 실패/);
  await w.__qa.openPlayer('fixture-b');assert.equal(dialog.open,true);
  assert.match(d.getElementById('player-meta').textContent,/AAC 스테레오/);
  await w.__qa.closePlayer();
  // A completed preparation must open even when its secondary list refresh
  // fails. Reading a list cannot turn a successful POST into failed playback.
  library[1].available=false;library[1].unavailable_reason='rendition_required';
  listFailure=true;const beforePreparation=preparationWrites;
  await w.__qa.openPlayer('fixture-b');
  assert.equal(dialog.open,true,'list failure cannot prevent a successfully prepared video from opening');
  assert.equal(preparationWrites,beforePreparation+1,'list failure must not replay preparation');
  assert.doesNotMatch(d.getElementById('library-grid').textContent,/사본 준비 중/);
  await w.__qa.closePlayer();
  // The response body may hang indefinitely; opening waits only for the bound.
  library[1].available=false;library[1].unavailable_reason='rendition_required';holdList=true;
  let opened=false;const opening=w.__qa.openPlayer('fixture-b').then(()=>{opened=true;});
  await settle();assert.equal(opened,false,'settle the old list before new viewing writes');
  const deadline=[...timers].find(([,t])=>t.ms===10000);assert(deadline,'post-preparation list read is bounded');
  timers.delete(deadline[0]);deadline[1].fn();await settle();
  await opening;assert.equal(dialog.open,true);assert.match(d.getElementById('toast').textContent,/목록/);
  video.currentTime=6;video.dispatchEvent(new w.Event('seeked'));await settle();
  await w.__qa.closePlayer();
  assert.match(d.getElementById('library-grid').textContent,/0:06부터 이어보기/);
  const afterPreparation=preparationWrites;releaseList();await settle();
  assert.equal(preparationWrites,afterPreparation);assert.equal(dialog.open,false);
  assert.match(d.getElementById('library-grid').textContent,/0:06부터 이어보기/,'expired list cannot undo newly saved progress');
  // A successful old list response is different from an expired one. Retain
  // confirmed title/progress edits while still accepting new rows in that list.
  await w.__qa.openPlayer('fixture-b');
  library.push({id:'fixture-c',title:'목록에서 새로 찾은 영상',duration:25,position:0,width:640,height:360,available:true,thumbnail:false});
  holdList=true;const stale=w.__qa.refresh();await settle();
  const rename=async title=>{d.getElementById('title-input').value=title;d.getElementById('title-form').dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();};
  await rename('새로 저장한 제목');
  video.currentTime=11;video.dispatchEvent(new w.Event('seeked'));await settle();
  await w.__qa.closePlayer();
  assert.match(d.getElementById('library-grid').textContent,/새로 저장한 제목/);
  releaseList();await stale;
  assert.match(d.getElementById('library-grid').textContent,/새로 저장한 제목/,'old list cannot replace confirmed title');
  assert.match(d.getElementById('library-grid').textContent,/0:11부터 이어보기/,'old list cannot replace confirmed progress');
  assert.match(d.getElementById('library-grid').textContent,/목록에서 새로 찾은 영상/,'do not discard new rows with the old fields');
  await w.__qa.openPlayer('fixture-b');
  holdList=true;const repeated=w.__qa.refresh();await settle();
  await rename('중간 제목');const intermediate={items:library.map(x=>({...x}))};
  await rename('새로 저장한 제목');releaseList(intermediate);await repeated;
  assert.doesNotMatch(d.getElementById('library-grid').textContent,/중간 제목/,'changing back to the read-start title is still a newer confirmed edit');
  // The explicit import-result read uses the same protection and stays read-only.
  w.__qa.showImportRecovery('fixture');holdList=true;d.getElementById('import-check').click();await settle();
  await rename('확인 중 저장한 제목');video.currentTime=13;video.dispatchEvent(new w.Event('seeked'));await settle();
  const writeCount=writes.length;releaseList();await settle();
  assert.equal(writes.length,writeCount,'list completion sends no write');
  assert.match(d.getElementById('library-grid').textContent,/확인 중 저장한 제목/);
  assert.match(d.getElementById('library-grid').textContent,/0:13부터 이어보기/);
  // A higher server revision wins even if this read began before our save.
  holdList=true;const newerServer=w.__qa.refresh();await settle();
  video.currentTime=14;video.dispatchEvent(new w.Event('seeked'));await settle();
  library[1].position=19;library[1].position_revision++;
  releaseList({items:library.map(x=>({...x}))});await newerServer;
  assert.match(d.getElementById('library-grid').textContent,/0:19부터 이어보기/,'newer server position revision remains authoritative');
  await w.__qa.closePlayer();
  // A read started after the edits remains authoritative for external changes.
  library[1].title='다른 창의 새 제목';library[1].position=15;library[1].position_revision++;
  await w.__qa.refresh();assert.match(d.getElementById('library-grid').textContent,/다른 창의 새 제목/);
  assert.match(d.getElementById('library-grid').textContent,/0:15부터 이어보기/);
  w.close();return {checks:['safe title text','library search','continue filter','metadata resume','close and reopen autosave','ordered seek/pause writes','missing-file feedback','changed-file feedback','media error refreshes library'],writes};
}
(async()=>{
  const result=await run(source);
  await require('./moments.cjs')(html,source);
  await require('./item-entry.cjs')(html,source);
  const faulty=source.replace('clearTimeout(saveTimer); saveTimer=null;', 'clearTimeout(saveTimer);');
  assert.notEqual(faulty,source,'known autosave mutation must apply');
  let detected=false;
  try {await run(faulty);}catch(e){assert.match(e.message,/reopened player must schedule/);detected=true;}
  assert(detected,'test must detect actual reopen regression');
  const report={evidence:'synthetic DOM, mocked media and HTTP; not actual browser playback',...result,known_reopen_regression_detected:detected};
  console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e);process.exit(1);});
