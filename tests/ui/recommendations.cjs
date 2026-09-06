const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const repo=path.resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(path.join(repo,'media_clarity/static/index.html'),'utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,video=d.getElementById('video'),dialog=d.getElementById('player-dialog');
const library=['a','b'].map(id=>({id,title:id==='a'?'여행 기차':'<img src=x onerror=alert(1)> 여행 바다',duration:20,position:0,width:320,height:180,available:true,thumbnail:false}));
const prefs={a:{included:false,preference:'neutral',revision:0},b:{included:true,preference:'neutral',revision:0}};
const requests=[],timers=new Map();let counter=0,delayReadA=false,releaseReadA,delayRecommendations=false,releaseRecommendations,failWrite=false,failRecommendations=false;
w.setTimeout=(fn,ms)=>{timers.set(++counter,{fn,ms});return counter;};w.clearTimeout=id=>timers.delete(id);
const copy=x=>JSON.parse(JSON.stringify(x));
let delayWrite=false,releaseWrite;
w.fetch=async(url,options={})=>{
 requests.push({url,...options}); let result;
 if(url==='/api/session')result={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
 else if(url==='/api/library')result={items:library};
 else if(url==='/api/recommendations'){
  if(failRecommendations)throw new Error('transport');
  result={items:library.filter(i=>prefs[i.id].included&&prefs[i.id].preference==='neutral').map(i=>({...i,recommendation_reason:'liked_title'}))};
  if(delayRecommendations){delayRecommendations=false;await new Promise(resolve=>releaseRecommendations=resolve);}
 } else {
  const id=url.split('/')[3];assert(prefs[id],url);
  if(url.endsWith('/preference')){
   if(options.method==='PUT'){
    assert.equal(options.headers['X-Media-Token'],'fixture');const requested=JSON.parse(options.body);
    if(delayWrite){delayWrite=false;await new Promise(resolve=>releaseWrite=resolve);}
    if(requested.revision!==prefs[id].revision)return {ok:false,json:async()=>({error:'preference_changed'})};
    prefs[id]={...requested,revision:requested.revision+1};if(failWrite){failWrite=false;throw new Error('response lost after commit');}
   }
   result=copy(prefs[id]);
   if(delayReadA&&id==='a'&&!options.method){delayReadA=false;await new Promise(resolve=>releaseReadA=resolve);}
  } else if(url.endsWith('/subtitles'))result={jobs:[],tracks:[]};
  else result=library.find(i=>i.id===id);
 }
 return {ok:true,json:async()=>copy(result)};
};
Object.defineProperty(video,'readyState',{get:()=>0});video.play=()=>Promise.resolve();video.pause=()=>{};video.load=()=>{};
dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
w.eval(fs.readFileSync(path.join(repo,'media_clarity/static/app.js'),'utf8')+'\nglobalThis.qa={openPlayer,closePlayer,refreshRecommendations};');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const control=d.getElementById('preference-controls'),include=d.getElementById('preference-include'),value=d.getElementById('preference-value');
const change=element=>element.dispatchEvent(new w.Event('change'));
(async()=>{
 await settle();assert.equal(d.querySelectorAll('.media-card').length,2,'library unaffected');
 await w.qa.openPlayer('a');await settle();assert.equal(include.checked,false);assert.equal(value.value,'neutral');
 include.checked=true;change(include);assert(control.disabled);await settle();assert.equal(prefs.a.included,true);assert(!control.disabled);
 value.value='like';change(value);await settle();assert.equal(prefs.a.preference,'like');
 include.checked=false;change(include);await settle();assert.equal(value.value,'like','exclusion retains feedback');
 assert.match(d.getElementById('preference-state').textContent,/추천에서 제외/);
 await w.qa.closePlayer();d.getElementById('nav-recommended').click();await settle();
 assert.equal(d.getElementById('nav-recommended').getAttribute('aria-current'),'page');
 assert.equal(d.querySelectorAll('.media-card').length,1);
 assert.equal(d.querySelector('.media-card h3').textContent,library[1].title);assert.equal(d.querySelector('.media-card h3 img'),null);
 assert.match(d.querySelector('.recommendation-reason').textContent,/좋아요/);
 d.querySelector('.media-card button').click();await settle();assert.equal(d.getElementById('player-title').textContent,library[1].title,'recommendation opens existing player');
 // An excluded item must not reappear from an earlier in-flight response.
 delayRecommendations=true;const old=w.qa.refreshRecommendations();await settle();
 include.checked=false;change(include);await settle();assert.equal(prefs.b.included,false);
 assert.equal(d.querySelectorAll('.media-card').length,0);
 releaseRecommendations();await old;assert.equal(d.querySelectorAll('.media-card').length,0,'ignore stale response');
 // Lost successful write: do not let another edit overwrite unknown saved state.
 failWrite=true;include.checked=true;change(include);await settle();assert(control.disabled);
 assert.equal(d.getElementById('preference-retry').hidden,false);assert.match(d.getElementById('preference-state').textContent,/다시 확인/);
 d.getElementById('preference-retry').click();await settle();assert(!control.disabled);assert(include.checked);
 // A late read for another player must never supply the current item's settings.
 await w.qa.closePlayer();delayReadA=true;await w.qa.openPlayer('a');await settle();assert(control.disabled);
 await w.qa.closePlayer();await w.qa.openPlayer('b');await settle();assert.equal(value.value,'neutral');assert(include.checked);
 releaseReadA();await settle();assert.equal(value.value,'neutral');assert(include.checked);
 // Closing/reopening the same item must wait for its in-flight write before reading.
 value.value='like';change(value);await settle();delayWrite=true;
 value.value='neutral';change(value);await settle();
 await w.qa.closePlayer();await w.qa.openPlayer('b');await settle();assert(control.disabled,'wait for previous save after reopen');
 const writesBefore=requests.filter(r=>r.method==='PUT').length;
 include.checked=false;change(include);await settle();
 assert.equal(requests.filter(r=>r.method==='PUT').length,writesBefore,'stale controls cannot start a newer write');
 releaseWrite();await settle();assert(!control.disabled);assert.equal(value.value,'neutral');assert(include.checked);
 include.checked=false;change(include);await settle();assert.equal(prefs.b.included,false);
 assert.equal(d.querySelectorAll('.media-card').length,0);
 // A different window's committed change makes this window's version stale.
 prefs.b={included:false,preference:'like',revision:prefs.b.revision+1};
 include.checked=true;change(include);await settle();assert(control.disabled);assert.equal(prefs.b.included,false);
 d.getElementById('preference-retry').click();await settle();assert(!control.disabled);assert(!include.checked);assert.equal(value.value,'like');
 value.value='neutral';change(value);await settle();include.checked=true;change(include);await settle();
 await w.qa.closePlayer();failRecommendations=true;await w.qa.refreshRecommendations();
 assert.equal(d.querySelectorAll('.media-card').length,0);assert.match(d.getElementById('empty-title').textContent,/못했어요/);
 failRecommendations=false;d.getElementById('nav-recommended').click();await settle();assert.equal(d.querySelectorAll('.media-card').length,1);
 d.getElementById('nav-all').click();assert.equal(d.querySelectorAll('.media-card').length,2);
 assert.equal(w.localStorage.length,0);assert.equal(w.sessionStorage.length,0);
 assert(requests.every(r=>r.url.startsWith('/api/')));
 console.log('PASS recommendation DOM: opt-in/save/exclusion, existing player, literal titles, stale response isolation, uncertain-write recovery, late item read, retry, memory-only UI (mock HTTP/media; not browser playback).');w.close();
})().catch(e=>{console.error(e);process.exitCode=1;w.close();});
