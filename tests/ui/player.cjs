const fs = require('node:fs');
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const repo = require('node:path').resolve(__dirname, '../..');
const html = fs.readFileSync(`${repo}/media_clarity/static/index.html`, 'utf8');
const source = fs.readFileSync(`${repo}/media_clarity/static/app.js`, 'utf8');
async function run(js) {
  const dom = new JSDOM(html, {url:'http://127.0.0.1:8765', runScripts:'outside-only'});
  const w=dom.window, d=w.document, timers=new Map(), writes=[];
  let timerId=0, preparationFailed=false;
  const library=[{id:'fixture-a',title:'<img src=x onerror=alert(1)> 영상',duration:25,position:8.25,width:640,height:360,available:true,thumbnail:false}, {id:'fixture-b',title:'다른 영상',duration:25,position:0,width:640,height:360,available:true,thumbnail:false}];
  w.setTimeout=(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;};
  w.clearTimeout=id=>timers.delete(id);
  w.fetch=async (path,opts={})=>{
    let result;
    if(path==='/api/session') result={token:'synthetic-token',diagnostics:{ffprobe:true,ffmpeg:true,recovered_copies:0}};
    else if(path==='/api/library') result={items:library.map(x=>({...x}))};
    else {const id=path.split('/')[3], item=library.find(x=>x.id===id); assert(item,path);
      if(path.split('?')[0].endsWith('/subtitles')) result={jobs:[],tracks:[]};
      else if(path.endsWith('/playback')) {
        assert.equal(opts.method,'POST');assert.equal(opts.headers['X-Media-Token'],'synthetic-token');
        if(!preparationFailed){preparationFailed=true;item.preparation_error='media_timeout';return {ok:false,json:async()=>({error:'media_timeout'})};}
        item.available=true;item.unavailable_reason=null;item.preparation_error=null;result={...item};
      }
      else if(opts.method==='PUT'){const position=JSON.parse(opts.body).position; writes.push({id,position});item.position=position;result={...item};}
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
  w.eval(js+"\nglobalThis.__qa={openPlayer,closePlayer,refresh};"); await settle();
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
  await w.__qa.openPlayer('fixture-b');assert.equal(dialog.open,false);
  assert.match(d.getElementById('toast').textContent,/보관된 원본은 유지/);
  assert.match(d.getElementById('library-grid').textContent,/재생 준비 실패/);
  await w.__qa.openPlayer('fixture-b');assert.equal(dialog.open,true);
  assert.match(d.getElementById('player-meta').textContent,/AAC 스테레오/);
  await w.__qa.closePlayer();
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
