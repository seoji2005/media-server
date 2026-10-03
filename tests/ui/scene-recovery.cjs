// Controlled deadlines with mocked HTTP/media; this does not prove native playback.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..'),tick=()=>new Promise(resolve=>setImmediate(resolve));
const state={state:'ready',completed:5,total:5};
const candidates=time=>({sampled:5,searched:5,candidates:[{ordinal:2,time,image:'/fixture.jpg'}]});
async function fixture(){
 const dom=new JSDOM(fs.readFileSync(root+'/media_clarity/static/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
 const w=dom.window,d=w.document,el=id=>d.getElementById(id),video=el('video');
 const f={w,el,video,requests:[],held:[],timers:new Map(),status:'normal',search:'headers'};let timer=0;
 w.setTimeout=(fn,ms)=>{f.timers.set(++timer,{fn,ms});return timer;};w.clearTimeout=id=>f.timers.delete(id);
 f.expire=ms=>{for(const [id,t] of [...f.timers])if(t.ms===ms){f.timers.delete(id);t.fn();}};
 const items=['a','b'].map(id=>({id,title:id,duration:50,position:4,width:160,height:90,available:true}));
 const response=(data,ok=true)=>({ok,json:async()=>data});
 function hold(phase,url,options){
  if(phase==='headers')return new Promise(resolve=>f.held.push({url,options,answer:data=>resolve(response(data))}));
  return {ok:true,json:()=>new Promise(resolve=>f.held.push({url,options,answer:resolve}))};
 }
 w.fetch=async(url,options={})=>{
  f.requests.push({url,options});
  if(url==='/api/session')return response({token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}});
  if(url==='/api/library')return response({items});
  if(url.endsWith('/scenes'))return f.status==='normal'?response(state):hold(f.status,url,options);
  if(url.endsWith('/scenes/search')){
   assert.equal(options.method,'POST');assert.equal(url.includes('?'),false,'query stays out of URLs');
   if(f.search==='busy')return response({error:'processing_worker_active'},false);
   if(f.search==='invalid')return response({error:'scene_index_required'},false);
   if(f.search==='normal')return response(candidates(25));
   return hold(f.search,url,options);
  }
  if(url.includes('/subtitles'))return response({tracks:[],jobs:[]});
  if(url.endsWith('/preference'))return response({included:false,preference:'neutral',revision:0});
  if(url.endsWith('/position'))return response({position:JSON.parse(options.body).position});
  const item=items.find(item=>url==='/api/library/'+item.id);assert(item,url);return response(item);
 };
 Object.defineProperty(video,'readyState',{get:()=>2});Object.defineProperty(video,'duration',{get:()=>50});
 video.play=()=>Promise.resolve();video.pause=()=>{};video.load=()=>{};video.scrollIntoView=()=>{};
 el('player-dialog').showModal=()=>el('player-dialog').open=true;el('player-dialog').close=()=>el('player-dialog').open=false;
 w.eval(fs.readFileSync(process.env.MEDIA_SCENE_TEST_SOURCE||root+'/media_clarity/static/app.js','utf8')+'\nglobalThis.qa={openPlayer,closePlayer};');
 await tick();await w.qa.openPlayer('a');await tick();video.currentTime=7;
 f.toggle=async(id,open)=>{
  const panel=el(id);if(panel.open===open)return;
  await new Promise((resolve,reject)=>{
   const timeout=setTimeout(()=>reject(Error('toggle did not fire: '+id)),2000);
   panel.addEventListener('toggle',()=>{clearTimeout(timeout);resolve();},{once:true});panel.open=open;
  });await tick();
 };
 f.open=async()=>{await f.toggle('subtitle-search-panel',true);await f.toggle('scene-panel',true);};
 f.query=text=>{el('scene-query').value=text;el('scene-query').dispatchEvent(new w.Event('input'));};
 f.submit=()=>el('scene-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
 f.searches=()=>f.requests.filter(r=>r.url.endsWith('/scenes/search'));
 f.writes=()=>f.requests.filter(r=>['POST','PUT','DELETE'].includes(r.options.method));
 return f;
}
(async()=>{
 for(const phase of ['headers','body']){
  const f=await fixture();try{
   f.status=phase;await f.open();const old=f.held.at(-1),src=f.video.src;
   f.expire(10000);await tick();
   assert(old.options.signal?.aborted,'scene status '+phase+' has a complete-response deadline');
   assert.match(f.el('scene-state').textContent,/10초/);assert.equal(f.writes().length,0);
   f.status='normal';await f.toggle('scene-panel',false);await f.toggle('scene-panel',true);
   assert(!f.el('scene-search').disabled,'reopening explicitly retries the read');
   const status=f.el('scene-state').textContent;
   old.answer({...state,state:'partial',completed:0});await tick();
   assert.equal(f.el('scene-state').textContent,status);assert(!f.el('scene-search').disabled);
   assert.equal(f.video.src,src);assert.equal(f.video.currentTime,7);assert.equal(f.writes().length,0);
  }finally{f.w.close();}
 }
 for(const phase of ['headers','body']){
  const f=await fixture();try{
   await f.open();f.search=phase;f.query('비공개 테스트 검색어');f.submit();await tick();
   const old=f.held.at(-1),src=f.video.src;f.submit();await tick();assert.equal(f.searches().length,1);
   f.expire(150000);await tick();
   assert(old.options.signal?.aborted,'scene search '+phase+' has a complete-response deadline');
   assert(!f.el('scene-search').disabled);assert.match(f.el('scene-state').textContent,/150초/);
   assert.equal(f.el('scene-query').value,'비공개 테스트 검색어');assert.equal(f.searches().length,1,'timeout never replays a query');
   f.query('새 검색어');f.search='normal';f.submit();await tick();
   assert.equal(f.searches().length,2);assert.equal(JSON.parse(f.searches()[1].options.body).query,'새 검색어');
   const result=f.el('scene-results').textContent;old.answer(candidates(40));await tick();
   assert.equal(f.el('scene-results').textContent,result,'late response cannot replace the explicit retry');
   assert.equal(f.video.src,src);assert.equal(f.video.currentTime,7);
   f.el('scene-results').querySelector('button').click();assert.equal(f.video.currentTime,25);
  }finally{f.w.close();}
 }
 // A close/reopen cycle must not revive the query that was hidden while pending.
 for(const panel of ['scene-panel','subtitle-search-panel']){
  const f=await fixture();try{
   await f.open();f.query('pending');f.submit();await tick();const old=f.held.at(-1);
   await f.toggle(panel,false);await f.toggle(panel,true);old.answer(candidates(40));await tick();
   assert.equal(f.el('scene-results').children.length,0,'closing '+panel+' invalidates the pending result');
   assert(!f.el('scene-search').disabled);assert.match(f.el('scene-state').textContent,/다시/);
   assert.equal(f.searches().length,1);assert.equal(f.video.currentTime,7);
  }finally{f.w.close();}
 }
 {
  const f=await fixture();try{
   await f.open();f.query('first');f.submit();await tick();f.query('edited');
   f.expire(150000);await tick();assert(!f.el('scene-search').disabled);assert.match(f.el('scene-state').textContent,/다시/);
   f.search='busy';f.submit();await tick();assert(!f.el('scene-search').disabled,'server busy allows an explicit retry');
   f.search='invalid';f.submit();await tick();assert(f.el('scene-search').disabled);assert(!f.el('scene-prepare').hidden);
   assert.equal(f.searches().length,3);
  }finally{f.w.close();}
 }
 {
  const f=await fixture();try{
   await f.open();f.query('first');f.submit();await tick();const old=f.held.at(-1);
   await f.w.qa.closePlayer();await f.w.qa.openPlayer('b');await f.open();const current=f.el('scene-state').textContent;
   old.answer(candidates(40));await tick();f.expire(150000);await tick();
   assert.equal(f.el('scene-state').textContent,current);assert.equal(f.el('scene-results').children.length,0);
   assert.equal(f.el('scene-query').value,'');assert.equal(f.el('player-title').textContent,'b');assert.equal(f.searches().length,1);
  }finally{f.w.close();}
 }
 console.log('PASS scene recovery DOM: status/search header and body deadlines, manual retry, private POST, pending guards, late response/query/panel/player isolation and preserved playback (mock HTTP/media).');
})().catch(error=>{console.error(error);process.exitCode=1;});
