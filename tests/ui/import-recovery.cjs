// Product JS, injected XHR/media and HTTP responses; not a browser upload test.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(path.join(root,'media_clarity/static/index.html'),'utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,requests=[],uploads=[],timers=new Map();
let timerId=0,library=[],holdRead=false,releaseRead,heldRead;
w.setTimeout=(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;};w.clearTimeout=id=>timers.delete(id);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const item={id:'a'.repeat(32),title:'새 영상',duration:120,position:0,position_revision:0,width:320,height:180,available:true,thumbnail:false,audio_index:0};
w.fetch=async(url,options={})=>{
  requests.push({url,...options});let data={};
  if(url==='/api/session')data={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
  else if(url==='/api/library'){
    data={items:library.map(x=>({...x}))};
    if(holdRead){holdRead=false;heldRead=options;await new Promise(resolve=>{releaseRead=resolve;});}
  }else if(url.endsWith('/playback')){
    const ready=library.find(i=>url.split('/')[3]===i.id);assert(ready);
    ready.available=true;ready.unavailable_reason=null;data={...ready};
  }else throw Error('Unexpected request: '+url);
  return {ok:true,json:async()=>data};
};
class Upload extends w.EventTarget{
  constructor(){super();this.upload=new w.EventTarget();this.headers={};uploads.push(this);}
  open(method,url){this.method=method;this.url=url;}
  setRequestHeader(name,value){this.headers[name]=value;}
  send(file){this.file=file;}
  abort(){this.aborted=true;this.dispatchEvent(new w.Event('abort'));this.dispatchEvent(new w.Event('loadend'));}
  progress(loaded,total){this.upload.dispatchEvent(new w.ProgressEvent('progress',{lengthComputable:true,loaded,total}));}
  complete(){this.upload.dispatchEvent(new w.Event('load'));}
  finish(value,status=201){this.status=status;this.responseText=typeof value==='string'?value:JSON.stringify(value);this.dispatchEvent(new w.Event('load'));this.dispatchEvent(new w.Event('loadend'));}
}
w.XMLHttpRequest=Upload;
w.eval(fs.readFileSync(path.join(root,'media_clarity/static/app.js'),'utf8')+'\nglobalThis.qa={importFile};');
const el=id=>d.getElementById(id),file=new w.File(['x'.repeat(1000)],'한글 영상.mp4');
(async()=>{
  await tick();await w.qa.importFile(file);let xhr=uploads.at(-1);
  assert.equal(xhr.url,'/api/import');assert.equal(xhr.headers['X-Media-Token'],'fixture');assert.equal(decodeURIComponent(xhr.headers['X-Media-Filename']),file.name);
  library=[item];xhr.progress(1000,1000);xhr.complete();xhr.finish({item,duplicate:false});await tick();
  assert.equal(el('upload-status').hidden,true);assert.equal(el('import-top').disabled,false);assert.match(el('library-grid').textContent,/새 영상/);
  assert(!requests.some(r=>r.method==='POST'),'an ordinary playable import needs no preparation or inference');
  await w.qa.importFile(file);xhr=uploads.at(-1);xhr.progress(995,1000);
  assert.equal(el('upload-cancel').hidden,false,'rounding 99.5% cannot remove cancellation before all bytes are sent');
  assert.equal(el('upload-percent').textContent,'99%');
  el('upload-cancel').click();assert(xhr.aborted);await tick();
  const recovery=el('import-recovery'),check=el('import-check');
  assert(recovery&&!recovery.hidden,'an interrupted request needs a durable result-check action');
  assert.equal(el('import-top').disabled,false);
  await w.qa.importFile(file);const waiting=uploads.at(-1);waiting.progress(1000,1000);waiting.complete();
  assert.equal(el('upload-cancel').hidden,false,'response waiting must remain interruptible');
  assert.match(el('upload-cancel').getAttribute('aria-label'),/대기 중단/);
  assert.equal(el('upload-percent').textContent,'확인 중');
  el('upload-cancel').click();await tick();assert(waiting.aborted);
  assert.match(el('import-recovery-message').textContent,/보관.*수도 있습니다/,'client abort must not promise server rollback');
  el('nav-continue').click();el('search').value='숨기는 검색';el('search').dispatchEvent(new w.Event('input'));
  const before=uploads.length;check.click();await tick();
  assert.equal(el('search').value,'');assert.match(el('library-grid').textContent,/새 영상/);
  assert.equal(uploads.length,before,'result confirmation never re-uploads');assert(!requests.some(r=>r.method==='POST'));
  assert.match(el('import-recovery-message').textContent,/목록/);
  holdRead=true;check.click();await tick();check.click();assert.equal(check.disabled,true);
  const timer=[...timers].find(([,t])=>t.ms===10000);assert(timer);timers.delete(timer[0]);timer[1].fn();await tick();
  assert(heldRead.signal.aborted);assert.equal(check.disabled,false);assert.match(el('import-recovery-message').textContent,/확인하지 못/);
  await w.qa.importFile(file);const latest=uploads.at(-1);assert.equal(recovery.hidden,true);
  releaseRead();waiting.finish({item,duplicate:false});xhr.dispatchEvent(new w.Event('loadend'));await tick();
  assert.equal(el('upload-status').hidden,false);assert.equal(el('import-top').disabled,true,'old callbacks cannot release the newer upload');
  latest.finish('not json');await tick();assert.equal(recovery.hidden,false);assert.equal(el('import-top').disabled,false);
  assert.equal(uploads.length,before+1,'malformed or lost responses never retry automatically');
  const needsPreparation={...item,id:'b'.repeat(32),available:false,unavailable_reason:'rendition_required'};
  library=[item,needsPreparation];await w.qa.importFile(file);
  uploads.at(-1).finish({item:needsPreparation,duplicate:false});await tick();await tick();
  assert.equal(requests.filter(r=>r.method==='POST').length,1,'normal successful import still prepares its required playback copy once');
  assert.equal(needsPreparation.available,true);
  const earlier={...item,id:'c'.repeat(32),available:false,unavailable_reason:'rendition_required'};
  library.push(earlier);holdRead=true;await w.qa.importFile(file);
  uploads.at(-1).finish({item:earlier,duplicate:false});await tick();
  await w.qa.importFile(file);const subsequent=uploads.at(-1);
  releaseRead();await tick();await tick();
  assert.equal(requests.filter(r=>r.method==='POST'&&r.url.includes(earlier.id)).length,1,'a newer upload cannot suppress preparation of an already confirmed earlier import');
  assert.equal(el('upload-status').hidden,false);assert.equal(el('import-top').disabled,true);
  subsequent.finish({item,duplicate:true});await tick();
  await w.qa.importFile(file);const expired=uploads.at(-1),count=uploads.length;
  expired.finish({error:'session_required'},403);await tick();
  assert.equal(el('session-recovery').hidden,false,'XHR imports must expose the same session recovery as fetch writes');
  assert.equal(uploads.length,count,'expired upload is not retried');
  console.log('PASS import DOM: normal import, exact upload progress, interruptible response wait, ambiguous completion, explicit read-only result check, timeout and stale callback isolation (mock XHR/HTTP).');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{if(releaseRead)releaseRead();w.close();});
