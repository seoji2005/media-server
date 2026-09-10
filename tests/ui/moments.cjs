const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');

module.exports = async function checkMoments(html, source) {
  for (const delayed of ['session', 'library']) {
    const entry = id => ({item_id:id.repeat(32), timeline:{file_id:id,sha256:id}, duration_ms:20000, start_ms:3000, end_ms:null});
    const a=entry('a'), b=entry('b'), c=entry('c');
    const fragment = value => '#moment='+encodeURIComponent(JSON.stringify(value));
    const dom = new JSDOM(html, {url:'http://127.0.0.1:8765/'+fragment(a),runScripts:'outside-only'});
    const w=dom.window, d=w.document, video=d.getElementById('video'), dialog=d.getElementById('player-dialog');
    const tick=()=>new Promise(resolve=>setTimeout(resolve,10));
    let release, releaseSave, holdSave=false;
    const startup=new Promise(resolve=>{release=resolve;});
    const save=new Promise(resolve=>{releaseSave=resolve;});
    const item=id=>({id,title:id,duration:20,position:8,width:320,height:180,available:true,thumbnail:false,
      preparation:'original',audio_index:0,audio_tracks:[],file_id:id[0],sha256:id[0]});
    const writes=[];
    w.fetch=async(url,options={})=>{
      let data={};
      if(url==='/api/session') {
        if(delayed==='session')await startup;
        data={token:'fixture',diagnostics:{ffmpeg:true,ffprobe:true,models:{}}};
      } else if(url==='/api/library') {
        if(delayed==='library')await startup;
        data={items:[a,b,c].map(e=>item(e.item_id))};
      } else if(url.endsWith('/moment-entry')) {
        assert.equal(options.headers['X-Media-Token'],'fixture');
        data={start_ms:3000,end_ms:null};
      } else if(url.split('?')[0].endsWith('/subtitles'))data={tracks:[],jobs:[]};
      else if(url.endsWith('/preference'))data={included:true,preference:'neutral',revision:1};
      else if(url.endsWith('/position')) {writes.push(JSON.parse(options.body));if(holdSave)await save;}
      else data=item(url.split('/')[3]);
      return {ok:true,json:async()=>data};
    };
    Object.defineProperty(video,'readyState',{get:()=>1});
    Object.defineProperty(video,'duration',{get:()=>20});
    video.play=()=>{video.dispatchEvent(new w.Event('play'));return Promise.resolve();};
    video.pause=()=>video.dispatchEvent(new w.Event('pause'));
    video.load=()=>{};
    dialog.showModal=()=>{dialog.open=true;};dialog.close=()=>{dialog.open=false;};
    try {
      w.eval(source+'\nglobalThis.qa={owner:()=>activeItem,openPlayer};');
      await tick();w.location.hash=fragment(b);await tick();
      if(delayed==='library')assert.equal(w.qa.owner().id,b.item_id);
      else assert.equal(w.qa.owner(),null);
      release();await tick();
      assert.equal(w.qa.owner().id,b.item_id,'slow startup must not replace newer scene');
      assert.equal(writes.length,0,'navigation does not save history');
      // Two new scene links arrive while an ordinary player's last save is pending.
      await w.qa.openPlayer(a.item_id);video.currentTime=8;holdSave=true;
      w.location.hash=fragment(b);await tick();
      w.location.hash=fragment(c);await tick();
      releaseSave();await tick();
      assert.equal(w.qa.owner().id,c.item_id,'latest scene wins after delayed close');
      video.dispatchEvent(new w.Event('loadedmetadata'));
      assert.equal(video.currentTime,3,'stale metadata callbacks cannot restore older position');
      assert.equal(dialog.open,true);
    } finally {release();releaseSave();w.close();}
  }
  console.log('PASS moment DOM: delayed session/startup and consecutive scene entry during pending close (mock HTTP/media).');
};
