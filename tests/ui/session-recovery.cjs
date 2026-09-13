// Product JS with mocked HTTP/media; actual restart/identity checks are separate.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..'),tick=()=>new Promise(r=>setImmediate(r));
const dom=new JSDOM(fs.readFileSync(path.join(root,'media_clarity/static/index.html'),'utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,v=d.getElementById('video'),dialog=d.getElementById('player-dialog');
const timers=new Map(),requests=[],native=new WeakMap();let timerId=0,token='first-fixture',hold=false,release;
let identity={version:1,product:'media-server',server_id:'a'.repeat(32),library_id:'b'.repeat(32)};
const item={id:'c'.repeat(32),title:'영상',duration:120,position:8.25,position_revision:0,width:320,height:180,available:true,thumbnail:false,audio_index:0};
const track={id:'d'.repeat(32),source:'supplied',language:'ko',audio_index:0};
let view={selection:track.id,offset_ms:500,revision:1},loads=0,plays=0,pauses=0;
w.setTimeout=(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;};w.clearTimeout=id=>timers.delete(id);
w.fetch=async(url,options={})=>{
  requests.push({url,...options});let data={};
  if(url==='/api/session'){
    data={token,identity:{...identity},diagnostics:{ffmpeg:true,ffprobe:true}};
    if(hold){hold=false;return new Promise(resolve=>{release=()=>resolve({ok:true,json:async()=>data});});}
  }else if(url==='/api/library')data={items:[{...item}]};
  else if(options.method&&options.method!=='GET'&&options.headers['X-Media-Token']!==token)return {ok:false,json:async()=>({error:'session_required'})};
  else if(url.endsWith('/position')){const body=JSON.parse(options.body);item.position=body.position;item.position_revision++;data={...item};}
  else if(url.endsWith('/caption-view')){view={...JSON.parse(options.body),revision:view.revision+1};data=view;}
  else if(url.split('?')[0].endsWith('/subtitles'))data={tracks:[track],jobs:[],view:{...view}};
  else if(url.endsWith('/preference'))data={included:false,preference:'neutral',revision:0};
  else data={...item};
  return {ok:true,json:async()=>data};
};
Object.defineProperty(w.HTMLTrackElement.prototype,'track',{get(){if(!native.has(this))native.set(this,{mode:'showing',cues:[]});return native.get(this);}});
Object.defineProperty(v,'textTracks',{value:new w.EventTarget()});
Object.defineProperty(v,'readyState',{get:()=>2});Object.defineProperty(v,'duration',{get:()=>120});
v.load=()=>loads++;v.play=()=>{plays++;return Promise.resolve();};v.pause=()=>pauses++;
for(const el of [dialog,d.getElementById('settings-dialog')]){el.showModal=()=>el.open=true;el.close=()=>{el.open=false;el.dispatchEvent(new w.Event('close'));};}
w.eval(fs.readFileSync(path.join(root,'media_clarity/static/app.js'),'utf8')+'\nglobalThis.qa={openPlayer,savePosition,api};');
const snapshot=()=>({time:v.currentTime,src:v.src,track:v.querySelector('track')?.src,selection:d.getElementById('subtitle-select').value,
  offset:d.getElementById('caption-offset-brief').textContent,title:d.getElementById('title-input').value,loads,plays,pauses});
(async()=>{
  await tick();await w.qa.openPlayer(item.id);await tick();v.dispatchEvent(new w.Event('loadedmetadata'));
  v.currentTime=10;await w.qa.savePosition();assert.equal(item.position,10);
  token='restarted-fixture';v.currentTime=24;d.getElementById('title-input').value='아직 저장하지 않은 제목';
  await w.qa.savePosition();await tick();assert.equal(item.position,10);
  const notice=d.getElementById('session-recovery'),button=d.getElementById('session-reconnect');
  assert(notice&&!notice.hidden,'expired session must offer recovery without a page reload');
  assert(dialog.contains(notice),'recovery must be usable in the open modal');
  d.getElementById('caption-later').click();await tick();
  assert.match(d.getElementById('caption-view-state').textContent,/저장 여부/);
  const before=snapshot(),writes=requests.filter(r=>r.method&&r.method!=='GET').length;
  // Unknown or different library identity must never authorize this page's edits.
  identity={...identity,library_id:'e'.repeat(32)};button.click();await tick();
  assert.equal(notice.hidden,false);assert.match(d.getElementById('session-message').textContent,/다른 보관함|확인할 수 없/);
  await assert.rejects(w.qa.api('/api/library/'+item.id+'/position',{method:'PUT',body:'{}'}),/다시 연결|재시작/);
  identity={...identity,library_id:'b'.repeat(32)};hold=true;button.click();button.click();await tick();
  const timer=[...timers.entries()].find(([,t])=>t.ms===10000);assert(timer);timers.delete(timer[0]);timer[1].fn();await tick();
  assert.equal(requests.at(-1).signal.aborted,true);assert.equal(button.disabled,false);
  const count=requests.length;button.click();button.click();await tick();
  assert.equal(requests.length,count+1,'reconnect is one GET with no replay');
  assert.equal(notice.hidden,true);assert.deepEqual(snapshot(),before,'current viewing and unsaved draft must stay intact');
  assert.equal(requests.filter(r=>r.method&&r.method!=='GET').length,writes+1);
  release();await tick();assert.equal(notice.hidden,true);
  // A subsequent explicit save uses the refreshed token and retained position.
  await w.qa.savePosition();assert.equal(item.position,24);
  assert.equal(requests.at(-1).headers['X-Media-Token'],token);
  await assert.rejects(w.qa.api('/api/library/'+item.id+'/position',{method:'PUT',headers:{'X-Media-Token':'first-fixture'},body:'{}'}));
  assert.equal(notice.hidden,true,'an old credential failure cannot reopen a recovered session notice');
  token='another-restart';v.currentTime=25;await w.qa.savePosition();
  d.getElementById('settings-open').click();assert(d.getElementById('settings-dialog').contains(notice));
  d.getElementById('settings-close').click();assert(dialog.contains(notice));
  d.getElementById('player-close').click();await tick();
  assert(d.querySelector('.page-content').contains(notice),'closing a modal must not hide its recovery control');
  console.log('PASS session DOM: normal save, expired-token recovery, same-library check, bounded explicit retry, unchanged viewing/drafts and no write replay (mock HTTP/media).');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>w.close());
