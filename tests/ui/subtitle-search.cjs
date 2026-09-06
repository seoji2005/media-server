const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const repo=path.resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(path.join(repo,'media_clarity/static/index.html'),'utf8'),{url:'http://127.0.0.1:8765',runScripts:'outside-only'});
const w=dom.window,d=w.document,video=d.getElementById('video'),dialog=d.getElementById('player-dialog');
const query=d.getElementById('subtitle-query'),results=d.getElementById('subtitle-results'),status=d.getElementById('subtitle-search-status');
const items=['a','b'].map(id=>({id,title:id,duration:120,position:0,width:320,height:180,available:true,thumbnail:false}));
const requests=[],timers=new Map();let counter=0,ready=1,plays=0;
w.setTimeout=(fn,ms)=>{timers.set(++counter,{fn,ms});return counter;};w.clearTimeout=id=>timers.delete(id);
w.fetch=async (url,options={})=>{
 requests.push({url,...options});
 if(url==='/api/session')return {ok:true,json:async()=>({token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true}})};
 if(url==='/api/library')return {ok:true,json:async()=>({items})};
 if(url.endsWith('/subtitles'))return {ok:true,json:async()=>({tracks:[{id:'one',source:'generated'},{id:'two',source:'supplied'}],jobs:[]})};
 const item=items.find(i=>url.split('/')[3]===i.id);
 return {ok:true,json:async()=>({...item,...(options.body?JSON.parse(options.body):{})})};
};
Object.defineProperty(video,'readyState',{get:()=>ready});Object.defineProperty(video,'duration',{get:()=>120});
Object.defineProperty(video,'textTracks',{value:new w.EventTarget()});
video.play=()=>{plays++;return Promise.resolve();};video.pause=()=>{};video.load=()=>{video.currentTime=0;};dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
w.eval(fs.readFileSync(path.join(repo,'media_clarity/static/app.js'),'utf8')+'\nglobalThis.qa={openPlayer,closePlayer};');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function search(text){query.value=text;query.dispatchEvent(new w.Event('input'));for(const [id,t] of timers){if(t.ms===150){timers.delete(id);t.fn();}}}
function loaded(cues,beforeLoad=()=>{}){
 const track=video.querySelector('track');
 const nativeCues=cues.map(([start,text])=>({startTime:start,getCueAsHTML:()=>{const fragment=d.createDocumentFragment();fragment.append(d.createTextNode(text));return fragment;}}));
 Object.defineProperty(track,'track',{value:{mode:'showing',get cues(){return this.mode==='disabled'?null:nativeCues;}}});
 beforeLoad(track);track.dispatchEvent(new w.Event('load'));return track;
}
function select(id){const s=d.getElementById('subtitle-select');s.value=id;s.dispatchEvent(new w.Event('change'));}
function saves(){return requests.filter(r=>r.method==='PUT');}
(async()=>{
 await settle();await w.qa.openPlayer('a');await settle();
 search('한글');assert.equal(results.children.length,0);assert.match(status.textContent,/불러오는 중/);
 const oldTrack=loaded([[2,'한글 대사'],[12.5,'<Enter> & ＡＢＣ'],[20,'두 번째 한글']]);
 assert.equal(results.children.length,2,'match decomposed Korean without sending a query');
 search('abc');assert.equal(results.children.length,1,'case/width normalization');
 assert.match(results.textContent,/<Enter> & ＡＢＣ/);assert.equal(results.querySelector('enter'),null,'render literal cue text');
 const button=results.querySelector('button'),before=saves().length,playsBefore=plays;
 ready=0;button.click();assert.equal(video.currentTime,0);assert.equal(saves().length,before);
 ready=1;button.click();assert.equal(video.currentTime,12.5);assert.equal(plays,playsBefore+1);assert.equal(saves().length,before,'do not save before seek completion');
 video.dispatchEvent(new w.Event('seeked'));await settle();assert.equal(JSON.parse(saves().at(-1).body).position,12.5);assert.match(saves().at(-1).url,/\/a\//);
 oldTrack.track.mode='disabled';video.currentTime=1;button.click();assert.equal(video.currentTime,1,'native Off rejects retained clicks before the change event');
 video.textTracks.dispatchEvent(new w.Event('change'));assert.equal(results.children.length,0);assert.match(status.textContent,/자막을 켜/);
 oldTrack.track.mode='showing';video.textTracks.dispatchEvent(new w.Event('change'));assert.equal(results.children.length,1);
 button.click();assert.equal(video.currentTime,1,'native off/on invalidates old callbacks');
 results.querySelector('button').click();assert.equal(video.currentTime,12.5);
 search('없는 문장');assert.equal(results.children.length,0);assert.match(status.textContent,/없습니다/);
 search('');assert.equal(results.children.length,0,'no unsolicited transcript on empty query');
 select('two');assert.equal(results.children.length,0);search('한글');
 const secondTrack=loaded(Array.from({length:55},(_,i)=>[i+1,`한글 ${i}`]));
 assert.equal(results.children.length,50);assert.match(status.textContent,/55개.*50개/);
 const staleButton=results.querySelector('button');
 select('');assert.equal(results.children.length,0);assert.match(status.textContent,/선택해/);
 staleButton.click();assert.equal(video.currentTime,12.5,'off invalidates old result callbacks');
 select('one');oldTrack.dispatchEvent(new w.Event('load'));oldTrack.dispatchEvent(new w.Event('error'));
 assert.match(status.textContent,/불러오는 중/,'detached same-id track cannot overwrite the new load');
 const failing=video.querySelector('track');failing.dispatchEvent(new w.Event('error'));assert.match(status.textContent,/못했습니다/);
 select('two');loaded([[9,'한글 새 버전']]);search('한글');const itemAButton=results.querySelector('button');
 d.getElementById('subtitle-search-panel').open=true;
 await w.qa.closePlayer();assert.equal(query.value,'');assert.equal(results.children.length,0);assert.equal(d.getElementById('subtitle-search-panel').open,false);
 await w.qa.openPlayer('b');await settle();loaded([[30,'다른 영상']]);search('다른');
 const currentResults=results.textContent,writeCount=saves().length;
 itemAButton.click();secondTrack.dispatchEvent(new w.Event('load'));secondTrack.dispatchEvent(new w.Event('error'));await settle();
 assert.equal(video.currentTime,0);assert.equal(saves().length,writeCount);assert.equal(results.textContent,currentResults,'old item cannot leak cues or seek/save the new item');
 select('two');search('대기');
 const waiting=loaded([[2,'대기 중인 자막']],track=>{track.track.mode='disabled';video.textTracks.dispatchEvent(new w.Event('change'));});
 assert.equal(waiting.track.mode,'disabled','load completion preserves native Off chosen during fetch');
 assert.equal(results.children.length,0);assert.match(status.textContent,/자막을 켜/);
 waiting.track.mode='showing';video.textTracks.dispatchEvent(new w.Event('change'));assert.equal(results.children.length,1);
 assert.equal(w.localStorage.length,0);assert.equal(w.sessionStorage.length,0);assert.equal(w.location.search,'');
 assert(!requests.some(r=>JSON.stringify(r).includes('한글')||JSON.stringify(r).includes('없는 문장')||JSON.stringify(r).includes('다른')),'search text never enters HTTP');
 await w.qa.closePlayer();assert.equal([...timers.values()].filter(t=>t.ms===150).length,0);
 console.log('PASS subtitle search DOM: Unicode/literal text, bounded results, seek completion persistence, off/version/item isolation, errors, no query egress/history (mocked media/HTTP).');dom.window.close();
})().catch(e=>{console.error(e);process.exitCode=1;dom.window.close();});
