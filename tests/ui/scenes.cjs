const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const root=require('node:path').resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(root+'/media_clarity/static/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,v=d.getElementById('video'),dialog=d.getElementById('player-dialog');
const item={id:'a',title:'fixture',duration:50,position:0,width:160,height:90,available:true};
let search=null,prepare=null,reads=null,searches=0,prepares=0;
w.setTimeout=()=>1;w.clearTimeout=()=>{};
w.fetch=async(path,opts={})=>{
 let result;
 if(path==='/api/session')result={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
 else if(path==='/api/library')result={items:[item]};
 else if(path==='/api/library/a'||path==='/api/library/b')result={...item,id:path.split('/').at(-1)};
 else if(path.split('?')[0].endsWith('/subtitles'))result={tracks:[],jobs:[]};
 else if(path.endsWith('/preference'))result={included:false,preference:'neutral',revision:0};
 else if(path.endsWith('/position'))result={position:0};
 else if(path.endsWith('/scenes'))return new Promise(r=>reads=r);
 else if(path.endsWith('/previews'))result={state:'ready',completed:5,total:5};
 else if(path.endsWith('/scenes/prepare')){prepares++;return new Promise(r=>prepare=r);}
 else if(path.endsWith('/scenes/search')){assert.equal(opts.method,'POST');assert(!path.includes('query'));searches++;return new Promise(r=>search=r);}
 else throw Error(path);
 return {ok:true,json:async()=>result};
};
Object.defineProperty(v,'readyState',{get:()=>2});Object.defineProperty(v,'duration',{get:()=>50});
v.play=()=>Promise.resolve();v.pause=()=>{};v.load=()=>{};v.scrollIntoView=()=>{};dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
const settle=()=>new Promise(r=>setImmediate(r));const answer=(resolve,value)=>resolve({ok:true,json:async()=>value});
const state={state:'ready',completed:5,total:5,sampled:5};const results={sampled:5,searched:5,candidates:[{ordinal:2,time:25,image:'/a.jpg'}]};
function open(){d.getElementById('subtitle-search-panel').open=true;d.getElementById('scene-panel').open=true;d.getElementById('scene-panel').dispatchEvent(new w.Event('toggle'));}
function query(text){d.getElementById('scene-query').value=text;d.getElementById('scene-query').dispatchEvent(new w.Event('input'));}
function submit(){d.getElementById('scene-form').dispatchEvent(new w.Event('submit',{cancelable:true}));}
(async()=>{
 w.eval(fs.readFileSync(root+'/media_clarity/static/app.js','utf8')+'\nglobalThis.qa={openPlayer,closePlayer};');await settle();await w.qa.openPlayer('a');await settle();
 assert.equal(prepares,0);assert.equal(searches,0);open();await settle();query('다리');answer(reads,state);await settle();assert(!d.getElementById('scene-search').disabled,'typing while status loads does not strand the search');
 submit();await settle();query('다른 장면');answer(search,results);await settle();assert.equal(d.querySelectorAll('#scene-results button').length,0,'changed query invalidates a late result');
 submit();await settle();answer(search,results);await settle();const old=d.querySelector('#scene-results button');assert(old);old.click();assert.equal(v.currentTime,25);
 query('changed');v.currentTime=3;old.click();assert.equal(v.currentTime,3,'old result callback cannot seek after query edit');
 submit();await settle();await w.qa.closePlayer();answer(search,results);await settle();assert.equal(d.querySelectorAll('#scene-results button').length,0);assert.equal(d.getElementById('scene-query').value,'');
 await w.qa.openPlayer('b');open();await settle();answer(reads,{...state,state:'partial',completed:0});await settle();old.click();assert.equal(v.currentTime,3);
 d.getElementById('scene-prepare').click();await settle();answer(reads,{...state,state:'partial',completed:0});await settle();d.getElementById('scene-pause').click();answer(prepare,{...state,state:'partial',completed:4});await settle();assert.equal(prepares,1,'pause prevents another indexing batch');assert(!d.getElementById('scene-prepare').disabled);
 w.close();console.log('PASS scenes DOM: explicit preparation, pause, private POST, stale query/player isolation and candidate seeking (mock HTTP/media).');
})().catch(e=>{w.close();console.error(e);process.exit(1);});
