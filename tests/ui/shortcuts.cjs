// Actual product handlers with mocked HTTP/media; native CI checks real seeking.
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const root=require('node:path').resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(root+'/media_clarity/static/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,v=d.getElementById('video'),dialog=d.getElementById('player-dialog');
const item={id:'a',title:'fixture',duration:60,position:20,position_revision:0,width:320,height:180,available:true,audio_index:0};
const writes=[];let paused=true,plays=0,position=0,duration=60,ready=2;
w.setTimeout=()=>1;w.clearTimeout=()=>{};
w.fetch=async(url,options={})=>{
 let value={};
 if(url==='/api/session')value={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}};
 else if(url==='/api/library')value={items:[{...item}]};
 else if(url==='/api/library/a')value={...item};
 else if(url.endsWith('/position')){const body=JSON.parse(options.body);writes.push(body);item.position=body.position;item.position_revision++;value={...item};}
 else if(url.split('?')[0].endsWith('/subtitles'))value={tracks:[],jobs:[]};
 else if(url.endsWith('/preference'))value={included:false,preference:'neutral',revision:0};
 else throw Error(url);
 return {ok:true,json:async()=>value};
};
Object.defineProperties(v,{paused:{get:()=>paused},duration:{get:()=>duration},readyState:{get:()=>ready},currentTime:{get:()=>position,set:x=>{position=x;v.dispatchEvent(new w.Event('seeked'));}}});
v.play=async()=>{paused=false;plays++;v.dispatchEvent(new w.Event('play'));};
v.pause=()=>{paused=true;v.dispatchEvent(new w.Event('pause'));};v.load=()=>{};
dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const key=(value,target=d.body,extra={})=>{const e=new w.KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true,...extra});target.dispatchEvent(e);return e.defaultPrevented;};
(async()=>{
 w.eval(fs.readFileSync(root+'/media_clarity/static/app.js','utf8')+'\nglobalThis.qa={openPlayer,closePlayer,entry:value=>entryAwaitingPlay=value};');await tick();
 assert.equal(key('k'),false);assert.equal(plays,0);
 await w.qa.openPlayer('a');v.dispatchEvent(new w.Event('loadedmetadata'));await tick();v.pause();await tick();
 assert.equal(key('l'),true);await tick();assert.equal(position,30);assert.equal(item.position,30);assert(paused);
 key('j');await tick();assert.equal(position,20);assert.equal(item.position,20);
 key('k');assert.equal(paused,false);const count=plays;key('k',d.body,{repeat:true});assert.equal(paused,false);assert.equal(plays,count);
 key('k');assert(paused);await tick();
 for(const target of [d.getElementById('title-input'),d.getElementById('subtitle-query'),d.getElementById('audio-select')]){
  for(const value of ['j','k','l'])assert.equal(key(value,target),false);
 }
 const editor=d.createElement('div');editor.setAttribute('contenteditable','');const child=editor.appendChild(d.createElement('span'));dialog.append(editor);
 assert.equal(key('l',child),false);editor.remove();
 for(const modifier of ['ctrlKey','altKey','metaKey','isComposing'])assert.equal(key('l',d.body,{[modifier]:true}),false);
 assert.equal(position,20);assert(paused);
 ready=0;assert.equal(key('l'),false);ready=2;
 duration=NaN;assert.equal(key('l'),false);duration=60;
 position=55;key('l');await tick();assert.equal(position,60);
 position=5;key('j');await tick();assert.equal(position,0);
 w.qa.entry(true);const before=writes.length;key('l');await tick();assert.equal(position,10);assert.equal(writes.length,before,'unplayed entry seeking cannot write history');
 key('k');key('j');await tick();assert.equal(item.position,0,'explicit play enables ordinary seek saves');
 await w.qa.closePlayer();assert.equal(key('l'),false);assert.equal(key('k'),false);
 console.log('PASS shortcuts DOM: J/K/L, bounds, paused seek, save queue, input/composition/modifier isolation, repeat toggle and unplayed entry history.');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>w.close());
