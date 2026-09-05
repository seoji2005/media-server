const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const repo=path.resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(path.join(repo,'media_clarity/static/index.html'),'utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,video=d.getElementById('video'),dialog=d.getElementById('player-dialog');
const items=['a','b'].map(id=>({id,title:id,duration:20,position:0,width:320,height:180,available:true,thumbnail:false}));
let data={tracks:[],jobs:[]}, pendingA=null, delayA=false;
const timers=new Map();let counter=0;
w.setTimeout=(fn,ms)=>{timers.set(++counter,{fn,ms});return counter;};w.clearTimeout=id=>timers.delete(id);
w.fetch=async (url,options={})=>{
 if(url==='/api/session')return {ok:true,json:async()=>({token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}})};
 if(url==='/api/library')return {ok:true,json:async()=>({items})};
 if(url.endsWith('/subtitles')){
  if(delayA&&url.includes('/a/'))await new Promise(resolve=>pendingA=resolve);
  return {ok:true,json:async()=>JSON.parse(JSON.stringify(data))};
 }
 return {ok:true,json:async()=>({...items.find(i=>url.split('/')[3]===i.id)})};
};
Object.defineProperty(video,'readyState',{get:()=>1});Object.defineProperty(video,'duration',{get:()=>20});
video.play=()=>Promise.resolve();video.pause=()=>{};video.load=()=>{};dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
w.eval(fs.readFileSync(path.join(repo,'media_clarity/static/app.js'),'utf8')+'\nglobalThis.qa={openPlayer,closePlayer,refreshSubtitles,owner:()=>activeItem};');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await settle();await w.qa.openPlayer('a');await settle();
 assert.equal(video.querySelectorAll('track').length,0);
 data={tracks:[{id:'first',source:'supplied'}],jobs:[]};await w.qa.refreshSubtitles(w.qa.owner());
 assert.equal(video.querySelector('track').getAttribute('src'),'/api/library/a/subtitles/first.vtt');
 const select=d.getElementById('subtitle-select');select.value='';select.dispatchEvent(new w.Event('change'));
 assert.equal(video.querySelectorAll('track').length,0);
 await w.qa.refreshSubtitles(w.qa.owner());assert.equal(video.querySelectorAll('track').length,0,'poll must preserve user opting out');
 select.value='first';select.dispatchEvent(new w.Event('change'));assert.equal(video.querySelectorAll('track').length,1);
 data={tracks:[{id:'second',source:'generated'},{id:'first',source:'supplied'}],jobs:[{id:'j',state:'running',stage:'translation',completed:1,total:2}]};
 await w.qa.refreshSubtitles(w.qa.owner());assert.equal(select.value,'first','keep chosen version');
 assert.equal(d.getElementById('subtitle-progress').value,50);assert.equal(d.getElementById('subtitle-pause').hidden,false);
 data.jobs[0].state='paused';await w.qa.refreshSubtitles(w.qa.owner());assert.equal(d.getElementById('subtitle-resume').hidden,false);assert.equal(d.getElementById('subtitle-pause').hidden,true);
 delayA=true;const old=w.qa.refreshSubtitles(w.qa.owner());await settle();await w.qa.closePlayer();await w.qa.openPlayer('b');await settle();
 const before=video.querySelector('track').getAttribute('src');pendingA();await old;
 assert.equal(video.querySelector('track').getAttribute('src'),before);assert(before.includes('/b/'));
 await w.qa.closePlayer();assert.equal(video.querySelectorAll('track').length,0);assert.equal([...timers.values()].filter(t=>t.ms===1500).length,0);
 console.log('PASS subtitle DOM: ready-track attachment, off/version preservation, progress/pause, late-response isolation, close cleanup (mocked media/HTTP).');dom.window.close();
})().catch(e=>{console.error(e);process.exitCode=1;dom.window.close();});
