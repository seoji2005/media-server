const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const root=require('node:path').resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(root+'/media_clarity/static/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,v=d.getElementById('video'),dialog=d.getElementById('player-dialog');
const item={id:'a',title:'fixture',duration:50,position:0,width:160,height:90,available:true};
const empty={state:'empty',completed:0,total:0,failed:0,frames:[]};
const first={state:'partial',completed:1,total:2,failed:0,frames:[{ordinal:0,time:5,available:true,image:'/preview-0.jpg'}]};
const ready={state:'ready',completed:2,total:2,failed:1,frames:[...first.frames,{ordinal:1,time:15,available:false,image:null}]};
let read=null,build=null,builds=0,writes=[],retryPath,returnsToVideo=0;
w.setTimeout=()=>1;w.clearTimeout=()=>{};
w.fetch=async(path,opts={})=>{
 let result;
 if(path==='/api/session')result={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
 else if(path==='/api/library')result={items:[item]};
 else if(path==='/api/library/a'||path==='/api/library/b')result={...item,id:path.split('/').at(-1)};
 else if(path.endsWith('/subtitles'))result={tracks:[],jobs:[]};
 else if(path.endsWith('/preference'))result={included:false,preference:'neutral',revision:0};
 else if(path.endsWith('/position')){writes.push(JSON.parse(opts.body).position);result={position:writes.at(-1)};}
 else if(path.endsWith('/previews')&&opts.method!=='POST')return new Promise(r=>read=r);
 else if(path.includes('/previews')&&opts.method==='POST'){builds++;retryPath=path;return new Promise(r=>build=r);}
 else throw Error(path);
 return {ok:true,json:async()=>result};
};
Object.defineProperty(v,'readyState',{get:()=>2});Object.defineProperty(v,'duration',{get:()=>50});
v.play=()=>Promise.resolve();v.pause=()=>{};v.load=()=>{};v.scrollIntoView=()=>returnsToVideo++;dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
const settle=()=>new Promise(r=>setImmediate(r));const answer=(resolve,value)=>resolve({ok:true,json:async()=>value});
function openPanel(){d.getElementById('subtitle-search-panel').open=true;d.getElementById('preview-panel').open=true;d.getElementById('preview-panel').dispatchEvent(new w.Event('toggle'));}
(async()=>{
 w.eval(fs.readFileSync(root+'/media_clarity/static/app.js','utf8')+'\nglobalThis.qa={openPlayer,closePlayer,buildPreviews};');await settle();await w.qa.openPlayer('a');await settle();
 assert.equal(builds,0,'opening player does not generate previews');assert.equal(d.getElementById('preview-panel').open,false);
 openPanel();await settle();d.getElementById('preview-build').click();await settle();d.getElementById('preview-pause').click();answer(build,first);await settle();
 answer(read,empty);await settle();assert.match(d.getElementById('preview-state').textContent,/1\/2/,'late GET must not erase newly built progress');
 assert.equal(builds,1,'pause stops after the current batch');
 const oldButton=d.querySelector('.preview-frame');oldButton.click();await settle();assert.equal(v.currentTime,5);assert.equal(returnsToVideo,1);assert.equal(writes.length,0,'only completed seek writes history');v.dispatchEvent(new w.Event('seeked'));await settle();assert.equal(writes.at(-1),5);
 d.getElementById('preview-build').click();await settle();answer(build,ready);await settle();assert.equal(d.querySelectorAll('.preview-frame').length,2);assert.strictEqual(d.querySelector('.preview-frame'),oldButton,'earlier tiles retain identity/focus');
 d.querySelector('.preview-retry').click();await settle();assert.match(retryPath,/previews\/1\/retry$/);
 const repaired={...ready,failed:0,frames:[...first.frames,{ordinal:1,time:15,available:true,image:'/preview-1.jpg'}]};answer(build,repaired);await settle();assert.equal(d.querySelectorAll('.preview-retry').length,0);
 d.querySelector('.preview-frame img').dispatchEvent(new w.Event('error'));assert(d.querySelector('.preview-retry'));d.querySelector('.preview-retry').click();await settle();answer(build,repaired);await settle();assert.equal(d.querySelectorAll('.preview-retry').length,0,'image-load failure has a working regeneration path');
 d.querySelector('.preview-frame img').dispatchEvent(new w.Event('error'));const oldRetry=d.querySelector('.preview-retry');
 const before=v.currentTime;await w.qa.closePlayer();oldButton.click();assert.equal(v.currentTime,before,'retained tile cannot seek another player');
 await w.qa.openPlayer('b');openPanel();await settle();answer(read,empty);await settle();const beforeBuilds=builds;oldRetry.click();oldButton.click();await settle();assert.equal(builds,beforeBuilds,'retained retry cannot regenerate a different item');assert.equal(v.currentTime,before);await w.qa.closePlayer();
 await w.qa.openPlayer('a');openPanel();await settle();answer(read,empty);await settle();d.getElementById('preview-build').click();await settle();await w.qa.closePlayer();answer(build,ready);await settle();assert.equal(d.querySelectorAll('.preview-frame').length,0);assert.equal(dialog.open,false,'late build cannot repopulate/reopen a closed player');
 w.close();console.log('PASS preview DOM: explicit generation, batch pause/resume, stale read/write isolation, seek persistence, stable tiles, failed-image retry (mock HTTP/media).');
})().catch(e=>{w.close();console.error(e);process.exit(1);});
