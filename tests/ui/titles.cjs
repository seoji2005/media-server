const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..'),settle=()=>new Promise(resolve=>setImmediate(resolve));
const dom=new JSDOM(fs.readFileSync(root+'/media_clarity/static/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,el=id=>d.getElementById(id),video=el('video'),dialog=el('player-dialog');
const items=['a','b'].map(id=>({id,title:'original '+id,duration:50,position:3,width:160,height:90,available:true,audio_index:0,audio_tracks:[{index:0},{index:1}]}));
const requests=[],timers=new Map();let defer=false,pending=null,counter=0,loads=0;
w.setTimeout=(fn,ms)=>{timers.set(++counter,{fn,ms});return counter;};w.clearTimeout=id=>timers.delete(id);
w.fetch=async(url,options={})=>{
  requests.push({url,options});let result;
  if(url==='/api/session')result={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
  else if(url==='/api/library')result={items:items.map(item=>({...item}))};
  else if(url==='/api/recommendations')result={items:[]};
  else{
    const item=items.find(item=>item.id===url.split('/')[3]);assert(item,url);
    if(url.endsWith('/title')){
      const body=JSON.parse(options.body);assert.equal(options.method,'PUT');assert.equal(options.headers['X-Media-Token'],'fixture');
      if(body.expected_title!==item.title)return {ok:false,json:async()=>({error:'title_changed'})};
      item.title=body.title.trim();result={id:item.id,title:item.title};
      if(defer)return new Promise(resolve=>pending={resolve,result,options});
    }else if(url.includes('/audio/')){item.audio_index=Number(url.split('/').at(-1));result={...item};}
    else if(url.includes('/subtitles'))result={tracks:[],jobs:[]};
    else if(url.endsWith('/preference'))result={included:false,preference:'neutral',revision:0};
    else if(url.endsWith('/position'))result={position:JSON.parse(options.body).position};
    else result={...item};
  }
  return {ok:true,json:async()=>result};
};
Object.defineProperty(video,'readyState',{get:()=>2});Object.defineProperty(video,'duration',{get:()=>50});
video.pause=()=>{};video.load=()=>loads++;video.play=()=>Promise.resolve();
dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
const submit=async value=>{el('title-input').value=value;el('title-form').dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();};
const saves=()=>requests.filter(r=>r.url.endsWith('/title'));
function search(value){el('search').value=value;el('search').dispatchEvent(new w.Event('input'));}
(async()=>{
  w.eval(fs.readFileSync(root+'/media_clarity/static/app.js','utf8')+'\nglobalThis.qa={openPlayer,closePlayer};');await settle();await w.qa.openPlayer('a');await settle();
  assert.equal(el('title-input').value,'original a');assert.equal(saves().length,0);
  const source=video.src,loaded=loads;video.currentTime=7;
  await submit('<img src=x> ＫＹＯＴＯ 한글');
  assert.equal(el('player-title').textContent,items[0].title);assert.equal(el('player-title').children.length,0);
  assert.equal(video.src,source);assert.equal(video.currentTime,7);assert.equal(loads,loaded,'rename does not restart playback');
  search('kyoto');assert.equal(d.querySelectorAll('.media-card').length,1);
  search('한글');assert.equal(d.querySelectorAll('.media-card').length,1);search('');
  // Audio switching keeps the editor and its pending title save bound to this item.
  defer=true;await submit('title during audio switch');const audioSave=pending;
  el('audio-select').value='1';el('audio-select').dispatchEvent(new w.Event('change'));el('audio-apply').click();await settle();
  assert.match(video.src,/audio_index=1$/);assert(el('title-save').disabled);
  audioSave.resolve({ok:true,json:async()=>audioSave.result});await settle();
  assert(!el('title-save').disabled);assert.equal(el('player-title').textContent,'title during audio switch');
  defer=false;await submit('title after audio switch');assert.equal(el('player-title').textContent,'title after audio switch');
  // A conflicting edit keeps the draft and requires reading the current title.
  items[0].title='other window';await submit('my draft');assert(el('title-save').disabled);assert.equal(el('title-input').value,'my draft');
  el('title-reload').click();await settle();assert.equal(el('player-title').textContent,'other window');assert.equal(el('title-input').value,'my draft');assert(!el('title-save').disabled);
  await submit('my draft');assert.equal(JSON.parse(saves().at(-1).options.body).expected_title,'other window');
  // A committed write with no response does not retry or erase the draft.
  defer=true;await submit('committed without reply');const old=pending;
  const timer=[...timers.values()].find(t=>t.ms===30000);assert(timer);timer.fn();await settle();
  assert(old.options.signal.aborted);assert(el('title-save').disabled);assert(!el('title-reload').disabled);
  const count=saves().length;el('title-reload').click();await settle();assert.equal(saves().length,count);assert.equal(el('title-input').value,'committed without reply');
  defer=false;await submit('new confirmed title');old.resolve({ok:true,json:async()=>old.result});await settle();
  assert.equal(el('player-title').textContent,'new confirmed title','late timed-out result cannot undo a later save');
  // Reopening this item waits for its own pending save, then reads fresh metadata.
  defer=true;await submit('pending reopen');const reopenSave=pending;await w.qa.closePlayer();
  const reads=requests.filter(r=>r.url==='/api/library/a').length;const opening=w.qa.openPlayer('a');await settle();
  assert.equal(requests.filter(r=>r.url==='/api/library/a').length,reads);
  reopenSave.resolve({ok:true,json:async()=>reopenSave.result});await opening;await settle();assert.equal(el('player-title').textContent,'pending reopen');
  // A late save for A cannot replace B's title or B's draft.
  await submit('late A');const late=pending;await w.qa.closePlayer();await w.qa.openPlayer('b');await settle();el('title-input').value='B draft';
  late.resolve({ok:true,json:async()=>late.result});await settle();assert.equal(el('player-title').textContent,'original b');assert.equal(el('title-input').value,'B draft');
  assert.equal(w.localStorage.length,0);assert.equal(w.sessionStorage.length,0);
  assert(!requests.some(r=>r.url.includes('draft')||r.url.includes('ＫＹＯＴＯ')),'titles never enter URLs');
  assert(!requests.some(r=>r.options.method==='PUT'&&r.url.endsWith('/preference')),'rename never changes participation');
  console.log('PASS title DOM: literal Unicode search, playback preservation, conflicts, lost reply/reread, pending reopen and stale item isolation (mock HTTP/media).');
  w.close();
})().catch(error=>{w.close();console.error(error);process.exitCode=1;});
