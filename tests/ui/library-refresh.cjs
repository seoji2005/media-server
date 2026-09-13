// Product JS with controlled HTTP completion order; not native browser viewing.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(path.join(root,'media_clarity/static/index.html'),'utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,pending=[],requests=[];
const item=id=>({id,title:'영상 '+id,duration:120,position:7.25,width:320,height:180,available:true,thumbnail:false});
let rows=[item('a')],hold=false;
w.fetch=async(url,options={})=>{
  requests.push({url,...options});let value={};
  if(url==='/api/session')value={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
  else if(url==='/api/library'){
    const snapshot=rows.map(row=>({...row}));
    if(hold)return new Promise((resolve,reject)=>pending.push({resolve,reject,snapshot}));
    value={items:snapshot};
  }else if(url==='/api/recommendations')value={items:[]};
  else throw Error('Unexpected request '+url);
  return {ok:true,json:async()=>value};
};
w.eval(fs.readFileSync(path.join(root,'media_clarity/static/app.js'),'utf8')+'\nglobalThis.qa={refresh,showImportRecovery};');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function answer(request,items=request.snapshot){request.resolve({ok:true,json:async()=>({items})});}
(async()=>{
  await tick();assert.match(d.getElementById('library-grid').textContent,/영상 a/);
  hold=true;const old=w.qa.refresh();const older=pending.shift();
  rows.push(item('b'));const fresh=w.qa.refresh();answer(pending.shift());await fresh;
  assert.match(d.getElementById('library-grid').textContent,/영상 b/);
  answer(older);await old;
  assert.match(d.getElementById('library-grid').textContent,/영상 b/,'a late old list cannot hide a newer successful import');
  // The obsolete request may also finish first, while the new read is pending.
  const first=w.qa.refresh();const firstRequest=pending.shift();
  rows=[...rows,item('c')];const newest=w.qa.refresh();const newestRequest=pending.shift();
  answer(firstRequest,[{...item('a'),title:'오래된 제목'}]);await first;
  assert.doesNotMatch(d.getElementById('library-grid').textContent,/오래된 제목/);
  answer(newestRequest);await newest;assert.match(d.getElementById('library-grid').textContent,/영상 c/);
  // A latest failed read must preserve the last confirmed list, not resurrect
  // an obsolete successful response that happened to arrive afterward.
  const stale=w.qa.refresh();const staleRequest=pending.shift();
  const failing=w.qa.refresh();pending.shift().reject(Error('fixture offline'));
  await assert.rejects(failing,/연결할 수 없습니다/);
  answer(staleRequest,[]);await stale;assert.match(d.getElementById('library-grid').textContent,/영상 c/);
  // A late obsolete failure cannot replace a newer success with an error toast.
  const rejected=w.qa.refresh();const rejectedRequest=pending.shift();
  const good=w.qa.refresh();answer(pending.shift());await good;
  rejectedRequest.reject(Error('fixture late error'));await rejected;
  assert.match(d.getElementById('library-grid').textContent,/영상 c/);
  // User filter/query edits remain local choices while a response is pending.
  const queried=w.qa.refresh();const queriedRequest=pending.shift();
  d.getElementById('nav-continue').click();d.getElementById('search').value='영상 b';d.getElementById('search').dispatchEvent(new w.Event('input'));
  answer(queriedRequest);await queried;
  assert.equal(d.getElementById('search').value,'영상 b');assert.equal(d.getElementById('nav-continue').getAttribute('aria-current'),'page');
  assert.match(d.getElementById('library-grid').textContent,/영상 b/);assert.doesNotMatch(d.getElementById('library-grid').textContent,/영상 a|영상 c/);
  // Import result checks and ordinary refreshes share one ordering boundary.
  w.qa.showImportRecovery('fixture');
  const check=d.getElementById('import-check'),notice=d.getElementById('import-recovery-message');
  const oldRefresh=w.qa.refresh();const oldRefreshRequest=pending.shift();
  rows.push(item('d'));check.click();answer(pending.shift());await tick();
  assert.match(d.getElementById('library-grid').textContent,/영상 d/);
  answer(oldRefreshRequest,[]);await oldRefresh;
  assert.match(d.getElementById('library-grid').textContent,/영상 d/,'an old ordinary read cannot undo a newer explicit import check');
  check.click();const oldCheck=pending.shift();rows.push(item('e'));
  const newRefresh=w.qa.refresh();answer(pending.shift());await newRefresh;
  answer(oldCheck,[]);await tick();assert.match(d.getElementById('library-grid').textContent,/영상 e/);
  assert.match(notice.textContent,/더 최근/);assert.equal(check.disabled,false);
  check.click();const oldError=pending.shift();
  const newSuccess=w.qa.refresh();answer(pending.shift());await newSuccess;
  oldError.reject(Error('fixture stale offline'));await tick();assert.match(notice.textContent,/더 최근/);
  check.click();pending.shift().reject(Error('fixture latest offline'));await tick();
  assert.match(notice.textContent,/연결할 수 없습니다/);assert.match(d.getElementById('library-grid').textContent,/영상 e/);
  assert(!requests.some(r=>r.method&&r.method!=='GET'),'list refresh never changes files or stored history');
  console.log('PASS library DOM: normal list, reversed reads, obsolete success after latest failure, caller errors, preserved filter/query and no writes (mock HTTP).');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>w.close());
