'use strict';
(function(root) {
  function createSpeechController(dependencies = {}, onChange = () => {}) {
    const {fetch, Audio, URL, AbortController} = dependencies;
    const supported = Boolean(fetch && Audio && AbortController && URL?.createObjectURL && URL?.revokeObjectURL);
    let readiness;
    let revision = 0;
    let current = null;
    let state = {status:'idle', id:null, language:null, reason:null};

    function update(next) { state = {...state, ...next}; onChange(state); }
    function availability(language) {
      if (!supported) return 'unsupported';
      if (readiness === undefined) return 'checking';
      return readiness?.ready && readiness.languages?.includes(language) ? 'available' : 'unavailable';
    }
    function setReadiness(value) { readiness=value ?? null; onChange(state); }
    function active(item) { return current === item && item.token === revision; }
    function release(item) {
      item.controller.abort();
      if (item.audio) {
        // Invalidate before pausing: pause/load may dispatch media events later.
        try { item.audio.pause(); item.audio.removeAttribute('src'); item.audio.load(); } catch { /* Already detached. */ }
      }
      if (item.url) { URL.revokeObjectURL(item.url); item.url=null; }
    }
    function stop() {
      revision++;
      const previous=current; current=null;
      if (previous) release(previous);
      update({status:'idle',id:null,language:null,reason:null});
      return true;
    }
    function fail(item, reason) {
      if (!active(item)) return false;
      current=null; release(item);
      update({status:'error',id:item.id,language:item.language,reason});
      return false;
    }
    function startAudio(item) {
      if (!active(item) || !item.audio) return Promise.resolve(false);
      const attempt=++item.attempt;
      update({status:'preparing',reason:null});
      // Keep play() synchronous in this call stack for a direct second tap on iOS.
      let playing;
      try { playing=item.audio.play(); }
      catch (error) { playing=Promise.reject(error); }
      return Promise.resolve(playing).then(() => {
        if (!active(item) || item.attempt !== attempt) return false;
        update({status:'playing',reason:null});
        return true;
      }).catch(error => {
        if (!active(item) || item.attempt !== attempt) return false;
        if (error?.name === 'NotAllowedError') {
          update({status:'ready',reason:'blocked'});
          return false;
        }
        return fail(item,'media');
      });
    }
    async function prepare(item, body) {
      let response;
      try {
        response=await fetch('/api/speech', {
          method:'POST',headers:{'Content-Type':'application/json','Accept':'audio/wav'},
          body:JSON.stringify(body),signal:item.controller.signal,
        });
        if (!active(item)) return false;
        if (!response.ok) return fail(item,({413:'invalid',422:'invalid',429:'busy',503:'unavailable',504:'timeout'})[response.status] || 'server');
        const blob=await response.blob();
        if (!active(item)) return false;
        if (!blob.size) return fail(item,'media');
        item.url=URL.createObjectURL(blob);
        const audio=new Audio(item.url); item.audio=audio; audio.preload='auto';
        audio.onplaying=() => { if(active(item)) update({status:'playing',reason:null}); };
        audio.onpause=() => { if(active(item) && state.status==='playing') update({status:'paused'}); };
        audio.onended=() => {
          if (!active(item)) return;
          current=null; release(item);
          update({status:'idle',id:null,language:null,reason:null});
        };
        audio.onerror=() => fail(item,'media');
        return startAudio(item);
      } catch {
        return fail(item,response ? 'media' : 'network');
      }
    }
    function play(id, text, language, {guideId} = {}) {
      if (current && current.id===id && current.language===language && current.text===text && current.guideId===guideId) {
        if (['ready','paused'].includes(state.status)) return startAudio(current);
        if (['preparing','playing'].includes(state.status)) return Promise.resolve(true);
      }
      stop();
      if (availability(language) !== 'available') {
        update({status:'unavailable',language,reason:'unavailable'});
        return Promise.resolve(false);
      }
      if (!guideId && (typeof text !== 'string' || !text.trim() || text.length>4000)) {
        update({status:'error',id,language,reason:'invalid'});
        return Promise.resolve(false);
      }
      const item={id,text,language,guideId,token:revision,controller:new AbortController(),audio:null,url:null,attempt:0};
      current=item;
      update({status:'preparing',id,language,reason:null});
      return prepare(item,guideId ? {language,guide_id:guideId} : {language,text});
    }
    function togglePause() {
      if (!current?.audio) return;
      if (['paused','ready'].includes(state.status)) return startAudio(current);
      if (state.status!=='playing') return;
      const item=current;
      try { item.attempt++; item.audio.pause(); update({status:'paused'}); }
      catch { fail(item,'media'); }
    }
    return {play,stop,togglePause,availability,setReadiness,get state() { return state; }};
  }
  const api={createSpeechController};
  if (typeof module!=='undefined' && module.exports) module.exports=api;
  else root.OrchidSpeech=api;
})(globalThis);
