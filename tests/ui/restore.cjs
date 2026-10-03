// Product upload/recovery controls with mock XHR/HTTP, not a native file picker.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'../..'),tick=()=>new Promise(resolve=>setImmediate(resolve));
const dom=new JSDOM(fs.readFileSync(root+'/media_clarity/static/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,el=id=>d.getElementById(id),uploads=[],requests=[];
let busy=false;
const rows=['a','b'].map(id=>({id:id.repeat(32),title:id,duration:20,position:7,width:320,height:180,available:false,unavailable_reason:'managed_file_missing',original_missing:id==='a'}));
w.setTimeout=()=>1;w.clearTimeout=()=>{};
w.fetch=async(url,options={})=>{
 requests.push({url,...options});let value;
 if(url==='/api/session')value={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
 else if(url==='/api/library')value={items:rows};
 else if(url.endsWith('/playback-status'))value={busy,item:rows.find(i=>i.id===url.split('/')[3])};
 else throw Error(url);
 return {ok:true,json:async()=>structuredClone(value)};
};
class Upload extends w.EventTarget{
 constructor(){super();this.upload=new w.EventTarget();uploads.push(this);}
 open(method,url){this.method=method;this.url=url;}
 setRequestHeader(){} send(file){this.file=file;}
 abort(){this.dispatchEvent(new w.Event('abort'));this.dispatchEvent(new w.Event('loadend'));}
 finish(value,status=200){this.status=status;this.responseText=JSON.stringify(value);this.dispatchEvent(new w.Event('load'));this.dispatchEvent(new w.Event('loadend'));}
}
w.XMLHttpRequest=Upload;
w.eval(fs.readFileSync(root+'/media_clarity/static/app.js','utf8')+'\nglobalThis.qa={importFile,refresh};');
const file=new w.File(['fixture bytes'],'original.mp4'),action=()=>d.querySelector('.restore-controls button');
function pick(){Object.defineProperty(el('restore-input'),'files',{configurable:true,value:[file]});el('restore-input').dispatchEvent(new w.Event('change'));}
(async()=>{
 await tick();assert.equal(d.querySelectorAll('.restore-controls').length,1,'missing rendition alone does not offer original restore');
 assert.equal(d.querySelector('.card-button .restore-controls'),null,'restore is a separate keyboard action');
 action().click();el('restore-input').dispatchEvent(new w.Event('cancel'));pick();await tick();
 assert.equal(uploads.length,0,'cancelled picker cannot become an import or stale restore');
 action().click();pick();await tick();let xhr=uploads.at(-1);
 assert.equal(xhr.url,`/api/library/${rows[0].id}/restore`);assert(action().disabled);
 pick();assert.equal(uploads.length,1);xhr.finish({error:'restore_mismatch'},422);await tick();
 assert.match(el('toast').textContent,/동일한 원본/);assert.match(action().textContent,/원본 사본 복원/);
 action().click();pick();await tick();xhr=uploads.at(-1);xhr.abort();await tick();
 assert.match(action().textContent,/복원 상태 확인/);
 await w.qa.importFile(file,rows[0].id);assert.equal(uploads.length,2,'uncertain restore requires confirmation first');
 busy=true;action().click();await tick();assert.match(action().textContent,/복원 상태 확인/);
 busy=false;rows[0].original_missing=false;rows[0].unavailable_reason='rendition_required';action().click();await tick();await tick();
 assert.equal(action(),null);assert.equal(uploads.length,2);assert(!requests.some(r=>r.method==='POST'),'status reads cannot prepare or resend');
 rows[0].original_missing=true;await w.qa.refresh();action().click();pick();await tick();const latest=uploads.at(-1);
 xhr.finish({item:rows[0]});await tick();assert(!el('upload-status').hidden,'old completion cannot release a newer restore');
 rows[0].original_missing=false;latest.finish({item:rows[0]});await tick();await tick();
 assert.equal(action(),null);assert.equal(rows[0].position,7);assert(!requests.some(r=>r.method==='POST'),'successful restore never prepares playback automatically');
 await w.qa.importFile(file);assert.equal(uploads.at(-1).url,'/api/import','ordinary import keeps its own picker/action');
 uploads.at(-1).abort();await tick();
 console.log('PASS restore DOM: original-only eligibility, separate action, picker cancellation, mismatch, one upload, uncertain/busy read-only recovery, stale receipt and no automatic preparation.');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>w.close());
