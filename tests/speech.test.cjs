const {test} = require('node:test');
const assert = require('node:assert/strict');
const {createSpeechController} = require('../orchid/static/speech.js');

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve=yes; reject=no; });
  return {promise, resolve, reject};
}
const wav = () => new Response(new Blob(['wav fixture'], {type:'audio/wav'}), {
  status:200, headers:{'Content-Type':'audio/wav'},
});

function fixture() {
  const requests=[], audio=[], revoked=[], blobs=[];
  let respond = async () => wav();
  class Audio {
    constructor(src) { this.src=src; this.plays=0; this.pauses=0; audio.push(this); }
    play() { this.plays++; return Promise.resolve(); }
    pause() { this.pauses++; this.onpause?.(); }
    removeAttribute(name) { if(name==='src') this.src=''; }
    load() {}
  }
  const dependencies = {
    fetch:(url, options) => { requests.push({url,...options}); return respond(url,options); },
    Audio, AbortController,
    URL:{createObjectURL:blob => { blobs.push(blob); return `blob:audio-${blobs.length}`; },
      revokeObjectURL:url => revoked.push(url)},
  };
  const player=createSpeechController(dependencies);
  assert.equal(typeof player.setReadiness,'function','backend readiness must control playback availability');
  player.setReadiness({ready:true, languages:['en','zh-TW']});
  return {player,requests,audio,revoked,dependencies,setResponse:value => { respond=value; }};
}

test('backend readiness enables both languages without an operating system voice',()=>{
  const {player,dependencies}=fixture();
  assert.equal(player.availability('en'),'available');
  assert.equal(player.availability('zh-TW'),'available');
  assert.equal(player.availability('fr'),'unavailable');
  player.setReadiness({ready:false,languages:['en','zh-TW']});
  assert.equal(player.availability('en'),'unavailable');
  assert.equal(createSpeechController(dependencies).availability('en'),'checking');
  assert.equal(createSpeechController({...dependencies,Audio:null}).availability('en'),'unsupported');
});

test('guide playback requests a vetted guide id and plays the returned audio',async()=>{
  const {player,requests,audio}=fixture();
  const playing=player.play('intro','Ignored local copy','en',{guideId:'intro'});
  assert.equal(player.state.status,'preparing');
  assert.equal(await playing,true);
  assert.equal(requests[0].url,'/api/speech');
  assert.equal(requests[0].method,'POST');
  assert.equal(requests[0].headers['Content-Type'],'application/json');
  assert.deepEqual(JSON.parse(requests[0].body),{language:'en',guide_id:'intro'});
  assert.equal(audio[0].src,'blob:audio-1');
  assert.equal(player.state.status,'playing');
  assert.equal(player.state.id,'intro');
});

test('answer text and selected language reach the backend without changing scientific text',async()=>{
  const {player,requests}=fixture();
  await player.play('answer-1','PeMYB11 activates G_A [S04].','zh-TW');
  assert.deepEqual(JSON.parse(requests[0].body),{language:'zh-TW',text:'PeMYB11 activates G_A [S04].'});
  assert.equal(player.state.language,'zh-TW');
});

test('pause and resume reuse prepared audio, and stop releases it',async()=>{
  const {player,requests,audio,revoked}=fixture();
  await player.play('answer-1','A model','en');
  player.togglePause();
  assert.equal(player.state.status,'paused');
  await player.togglePause();
  assert.equal(player.state.status,'playing');
  assert.equal(audio[0].plays,2);
  assert.equal(requests.length,1);
  player.stop();
  assert.equal(player.state.status,'idle');
  assert.equal(player.state.id,null);
  assert.deepEqual(revoked,['blob:audio-1']);
  assert.equal(audio[0].src,'');
});

test('stop aborts preparation and late responses cannot start audio',async()=>{
  const {player,requests,audio,setResponse}=fixture();
  const response=deferred(); setResponse(()=>response.promise);
  const playing=player.play('intro','Hello','en');
  player.stop();
  assert.equal(requests[0].signal.aborted,true);
  response.resolve(wav()); await playing;
  assert.equal(audio.length,0);
  assert.equal(player.state.status,'idle');
});

test('new selection aborts the old request and ignores its late response',async()=>{
  const {player,requests,audio,setResponse}=fixture();
  const first=deferred(); setResponse(()=>first.promise);
  const old=player.play('intro','First','en',{guideId:'intro'});
  player.togglePause();
  assert.equal(player.state.status,'preparing');
  setResponse(async()=>wav());
  const current=player.play('clue','Second','zh-TW',{guideId:'clue2'});
  assert.equal(requests[0].signal.aborted,true);
  await current;
  first.resolve(wav()); await old;
  assert.equal(audio.length,1);
  assert.equal(player.state.id,'clue');
  assert.equal(player.state.language,'zh-TW');
  assert.deepEqual(JSON.parse(requests[1].body),{language:'zh-TW',guide_id:'clue2'});
});

test('late audio events cannot revive stopped audio or overwrite a new selection',async()=>{
  const {player,audio,revoked}=fixture();
  await player.play('intro','First','en');
  const old=[audio[0].onplaying,audio[0].onpause,audio[0].onended,audio[0].onerror];
  await player.play('clue','Second','en');
  for(const callback of old) callback();
  assert.equal(player.state.id,'clue');
  assert.equal(player.state.status,'playing');
  const latest=[audio[1].onplaying,audio[1].onpause,audio[1].onended,audio[1].onerror];
  player.stop();
  for(const callback of latest) callback();
  assert.equal(player.state.status,'idle');
  assert.deepEqual(revoked,['blob:audio-1','blob:audio-2']);
});

test('autoplay blocking keeps prepared audio for the next direct Play gesture',async()=>{
  const {player,requests,audio,dependencies,revoked}=fixture();
  dependencies.Audio.prototype.play=function() {
    this.plays++;
    return this.plays===1 ? Promise.reject(new DOMException('Gesture required','NotAllowedError')) : Promise.resolve();
  };
  assert.equal(await player.play('intro','Hello','en'),false);
  assert.equal(player.state.status,'ready');
  assert.equal(player.state.reason,'blocked');
  assert.deepEqual(revoked,[]);
  const replay=player.play('intro','Hello','en');
  assert.equal(audio[0].plays,2,'the retained audio plays synchronously in the second gesture');
  assert.equal(await replay,true);
  assert.equal(player.state.status,'playing');
  assert.equal(requests.length,1);
});

test('the compact playback control starts ready audio without another request',async()=>{
  const {player,requests,dependencies}=fixture();
  dependencies.Audio.prototype.play=function() {
    this.plays++;
    return this.plays===1 ? Promise.reject(new DOMException('Gesture required','NotAllowedError')) : Promise.resolve();
  };
  await player.play('intro','Hello','en');
  await player.togglePause();
  assert.equal(player.state.status,'playing');
  assert.equal(requests.length,1);
});

for(const [code,reason] of [[422,'invalid'],[413,'invalid'],[429,'busy'],[503,'unavailable'],[504,'timeout'],[500,'server']]) {
  test(`HTTP ${code} surfaces ${reason} without an automatic retry`,async()=>{
    const {player,requests,audio,setResponse}=fixture();
    setResponse(async()=>new Response('{"detail":"generic"}',{status:code}));
    assert.equal(await player.play('answer-1','A model','en'),false);
    assert.equal(player.state.status,'error');
    assert.equal(player.state.reason,reason);
    assert.equal(requests.length,1);
    assert.equal(audio.length,0);
  });
}

test('network failure surfaces an error, while an explicit Play can try again',async()=>{
  const {player,requests,setResponse}=fixture();
  setResponse(async()=>{throw new TypeError('offline');});
  assert.equal(await player.play('answer-1','A model','en'),false);
  assert.equal(player.state.reason,'network');
  assert.equal(requests.length,1);
  setResponse(async()=>wav());
  assert.equal(await player.play('answer-1','A model','en'),true);
  assert.equal(requests.length,2);
});

test('a stopped audio Play rejection cannot overwrite the idle state',async()=>{
  const {player,audio,dependencies}=fixture();
  const blocked=deferred(); dependencies.Audio.prototype.play=()=>blocked.promise;
  const playing=player.play('intro','Hello','en');
  while(!audio.length) await new Promise(resolve=>setImmediate(resolve));
  player.stop(); blocked.reject(new DOMException('Gesture required','NotAllowedError'));
  await playing;
  assert.equal(player.state.status,'idle');
});

test('playback ending and media errors both release the object URL',async()=>{
  const {player,audio,revoked}=fixture();
  await player.play('intro','Hello','en'); audio[0].onended();
  assert.equal(player.state.status,'idle');
  await player.play('answer-1','A model','en'); audio[1].onerror();
  assert.equal(player.state.status,'error');
  assert.equal(player.state.reason,'media');
  assert.deepEqual(revoked,['blob:audio-1','blob:audio-2']);
});

test('unavailable language, blank text and oversized answers never request synthesis',async()=>{
  const {player,requests}=fixture();
  assert.equal(await player.play('intro','Hello','fr'),false);
  assert.equal(player.state.status,'unavailable');
  assert.equal(await player.play('answer-1',' ','en'),false);
  assert.equal(player.state.reason,'invalid');
  assert.equal(await player.play('answer-1','a'.repeat(4001),'en'),false);
  assert.equal(player.state.reason,'invalid');
  assert.equal(requests.length,0);
});
