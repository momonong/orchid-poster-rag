'use strict';
const $ = id => document.getElementById(id);
const {locales, initialLanguage} = OrchidLocale;
let storage;
try { storage = window.localStorage; } catch { /* Text and language switching remain available. */ }
let language = initialLanguage(storage);
let guide;
const guideCache = {};
let clue = 0;
let history = [];
let epoch = 0;
let localeRevision = 0;
let sourceRevision = 0;
let activeSource;
let controller;
let pending = false;
let lastFocus;
let lastHealth;
let messageNumber = 0;
const speech = OrchidSpeech.createSpeechController({fetch:(...args)=>fetch(...args),
  Audio:window.Audio,URL:window.URL,AbortController:window.AbortController}, () => renderSpeech());
const t = (key, lang = language) => locales[lang][key];
function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (cls) el.className = cls;
  return el;
}
function sourceButton(id, label) {
  const button = node('button', label || id, 'source-button');
  button.type = 'button'; button.dataset.source = id;
  return button;
}
function sources(el, ids) {
  el.replaceChildren(...ids.map(id => sourceButton(id, `${id} ${t('sourceExcerpt')} ↗`)));
}
function renderSpeech() {
  const state = speech.state;
  const active = ['preparing','playing','paused','ready'].includes(state.status);
  const pinned = active || (state.status === 'error' && Boolean(state.id));
  const availability = speech.availability(language);
  const statusKeys = {preparing:'speechPreparing',playing:'speechPlaying',paused:'speechPaused',ready:'speechReady',error:'speechError'};
  const availabilityKeys = {unsupported:'speechUnsupported',checking:'speechChecking',unavailable:'speechUnavailable'};
  let text = t(statusKeys[state.status] || 'speechIdle');
  if (state.status === 'error') text=t(({busy:'speechBusy',timeout:'speechTimeout',network:'speechNetwork',
    unavailable:'speechUnavailable',invalid:'speechInvalid'})[state.reason] || 'speechError');
  if (active) {
    const kind = state.id === 'intro' ? 'intro' : state.id === 'clue' ? 'clue' : 'answer';
    text += ` · ${t(kind)} · ${state.language === 'en' ? 'English' : '繁體中文'}`;
  } else if (state.status !== 'error' && availability !== 'available') text=t(availabilityKeys[availability]);
  $('speech-status').textContent = text;
  $('speech-pause').textContent = t(state.status === 'ready' ? 'play' : state.status === 'paused' ? 'resume' : 'pause');
  $('speech-pause').disabled = !['playing','paused','ready'].includes(state.status);
  $('speech-stop').disabled = !pinned;
  document.querySelector('.speech-controls').classList.toggle('is-active',pinned);
  document.querySelector('.speech-controls').classList.toggle('has-error',state.status==='error');
  $('play-intro').hidden=active;
  document.documentElement.classList.toggle('speech-active',pinned);
  updateSpeechOffset();
  for (const button of document.querySelectorAll('[data-play]')) {
    const lang = button.dataset.language || language;
    const available = speech.availability(lang) === 'available';
    const selected = active && state.id === button.dataset.speechId && state.language === lang;
    button.disabled = !available || (button.dataset.play !== 'answer' && !guide) || (selected && ['preparing','playing'].includes(state.status));
    button.title = available ? '' : t(availabilityKeys[speech.availability(lang)], lang);
    button.setAttribute('aria-pressed',selected);
  }
}
function updateSpeechOffset() {
  const controls=document.querySelector('.speech-controls');
  const height=controls.classList.contains('is-active') ? Math.ceil(controls.getBoundingClientRect().height)+16 : 20;
  document.documentElement.style.setProperty('--speech-sticky-offset',`${height}px`);
}
function renderHealth() {
  const ready = lastHealth?.index?.ready && lastHealth?.model?.ready;
  $('health').textContent = t(lastHealth === undefined ? 'checking' : lastHealth === null ? 'healthUnknown'
    : ready ? 'ready' : !lastHealth.index?.ready ? 'indexNotReady' : 'modelNotReady');
  $('health').classList.toggle('ready', Boolean(ready));
}
function applyLocale() {
  document.documentElement.lang = language === 'en' ? 'en' : 'zh-Hant-TW';
  document.title = t('pageTitle');
  document.querySelector('meta[name="description"]').content = t('description');
  for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
  for (const el of document.querySelectorAll('[data-i18n-aria]')) el.setAttribute('aria-label', t(el.dataset.i18nAria));
  for (const el of document.querySelectorAll('[data-i18n-alt]')) el.alt = t(el.dataset.i18nAlt);
  for (const button of document.querySelectorAll('.language-switch [data-language]')) button.setAttribute('aria-pressed', button.dataset.language === language);
  for (const button of document.querySelectorAll('[data-clue]')) button.textContent = t('tabs')[Number(button.dataset.clue)];
  $('intro-toggle').textContent = t($('intro-toggle').getAttribute('aria-expanded') === 'true' ? 'introCollapse' : 'introExpand');
  $('question').placeholder = t('placeholder');
  $('suggestions').replaceChildren(...t('suggestions').map(([label, question]) => {
    const button = node('button', label); button.type='button'; button.dataset.question=question; return button;
  }));
  setPending(pending); renderHealth(); renderSpeech();
}
function selectClue(index, focus = false, stop = true) {
  if (!guide) return;
  if (stop) speech.stop();
  clue = Math.max(0, Math.min(guide.clues.length - 1, index));
  const item = guide.clues[clue];
  for (const button of document.querySelectorAll('[data-clue]')) {
    const selected = Number(button.dataset.clue) === clue;
    button.setAttribute('aria-selected', selected); button.tabIndex = selected ? 0 : -1;
    if (selected && focus) button.focus();
  }
  $('clue-panel').setAttribute('aria-labelledby', `tab-${item.id}`);
  $('clue-number').textContent = item.number;
  $('clue-title').textContent = item.title;
  $('clue-summary').textContent = item.summary;
  $('clue-detail').textContent = item.detail;
  $('clue-image').src = `/assets/${item.image}`;
  $('clue-image').alt = `${t('clueAlt')} ${clue + 1}: ${item.summary}`;
  $('clue-caption').textContent = `${t('clueFigure')} ${clue + 2} · ${t('modelSimulation')}`;
  $('previous-clue').disabled = clue === 0;
  $('next-clue').disabled = clue === guide.clues.length - 1;
  sources($('clue-sources'), item.sources);
}
async function loadGuide() {
  const revision = ++localeRevision;
  const lang = language;
  guide = null;
  $('clue-panel').hidden = true;
  $('intro-text').textContent = t('introFallback');
  $('intro-sources').replaceChildren();
  renderSpeech();
  try {
    if (!guideCache[lang]) {
      const response = await fetch(`/api/guide?language=${encodeURIComponent(lang)}`);
      if (!response.ok) throw new Error('guide');
      guideCache[lang] = await response.json();
    }
    if (revision !== localeRevision) return;
    guide = guideCache[lang];
    $('intro-text').textContent = guide.introduction;
    sources($('intro-sources'), guide.introduction_sources);
    selectClue(clue, false, false);
    $('clue-panel').hidden = false;
  } catch { if (revision === localeRevision) $('intro-text').textContent = t('guideError'); }
  if (revision === localeRevision) renderSpeech();
}
function switchLanguage(next) {
  if (!locales[next] || next === language) return;
  speech.stop(); language = next;
  try { storage?.setItem('orchid-language', language); } catch { /* Preference is optional. */ }
  applyLocale(); loadGuide();
  if ($('source-dialog').open && activeSource) showSource(activeSource);
}
function fillQuestion(text) {
  $('question').value = text; $('question').focus({preventScroll:true});
  $('question').scrollIntoView({block:'center',behavior:'instant'});
}
function showDialog(id) { lastFocus = document.activeElement; $(id).showModal(); }
function closeDialog(id) { $(id).close(); if (lastFocus?.isConnected) lastFocus.focus(); }
async function showSource(id) {
  activeSource = id;
  const revision = ++sourceRevision;
  const lang = language;
  $('source-title').textContent = `${id} ${t('sourceExcerpt',lang)}`;
  $('source-content').replaceChildren(node('p',t('sourceLoading',lang)));
  if (!$('source-dialog').open) showDialog('source-dialog');
  try {
    const response = await fetch(`/api/sources/${encodeURIComponent(id)}?language=${encodeURIComponent(lang)}`);
    if (!response.ok) throw new Error('source');
    const item = await response.json();
    if (revision !== sourceRevision || lang !== language) return;
    $('source-title').textContent = `${id} | ${item.title}`;
    const pages = item.pages || (item.page ? [item.page] : []);
    const page = pages.length ? `${t('sourcePage')} ${pages.join(', ')}` : '';
    const meta = node('p',[item.document_title,page,item.figure,item.section,item.kind].filter(Boolean).join(' · '),'source-meta');
    const links = node('div',undefined,'source-links');
    function link(label, url) { const el=node('a',label); el.href=url; el.target='_blank'; el.rel='noopener noreferrer'; return el; }
    links.append(link(t('sourceRead'),item.url));
    if (item.local_url) links.append(link(t('sourceLocal'),item.local_url+(item.page?`#page=${item.page}`:'')));
    const originalText = node('p',item.original_excerpt||t('sourceUnavailable'),'source-excerpt'); originalText.lang='en';
    const summaryText = node('p',item.summary||item.text,'source-excerpt'); summaryText.lang='zh-Hant-TW';
    const details = node('details',undefined,'original-source');
    if (lang === 'en') details.append(node('summary',t('sourceChinese')),summaryText);
    else details.append(node('summary',t('sourceOriginal')),originalText);
    const locators=node('div',undefined,'source-links');
    for (const locator of item.locators||[]) {
      if (locator.document === 'correction') continue;
      locators.append(link(`${t('docNames')[locator.document]} · ${t('sourcePage')} ${locator.page}${locator.section?' · '+locator.section:''} ↗`, `/api/documents/${locator.document}#page=${locator.page}`));
    }
    $('source-content').replaceChildren(meta,node('h3',t(lang==='en'?'sourceOriginal':'sourceChinese')),
      lang==='en'?originalText:summaryText,details,locators,
      node('p',`${item.excerpt_type}. ${t('sourceVersion')}: ${item.version}. ${item.license}`,'source-context'),links);
  } catch { if (revision === sourceRevision) $('source-content').replaceChildren(node('p',t('sourceError'))); }
}
function message(role, text, lang, reviewedSummary = false) {
  const el = node('article',undefined,`message ${role}`); el.lang=lang==='en'?'en':'zh-Hant-TW';
  const label=role==='user'?'user':reviewedSummary&&lang==='en'?'reviewedSummary':'assistant';
  el.append(node('p',t(label,lang),'message-label'),node('p',text,'message-text'));
  $('messages').append(el); $('messages').scrollTop=$('messages').scrollHeight;
  return el;
}
function setPending(value) {
  pending=value; $('send').disabled=value;
  $('send').textContent=t(value?'sending':'send'); $('question').setAttribute('aria-busy',value);
}
async function sendQuestion(event) {
  event.preventDefault();
  if (pending) return;
  const question=$('question').value.trim();
  if (!question) { $('question').focus(); return; }
  const requestEpoch=epoch;
  const requestLanguage=language;
  const requestController=new AbortController(); controller=requestController;
  setPending(true); $('form-error').hidden=true; $('messages').querySelector('.welcome')?.remove();
  message('user',question,requestLanguage);
  const waiting=message('waiting',t('waiting',requestLanguage),requestLanguage);
  $('question').value='';
  const clientTimer=setTimeout(()=>requestController.abort(),80000);
  try {
    const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({question,history:history.slice(-4),language:requestLanguage}),signal:requestController.signal});
    if (!response.ok) throw new Error(t(response.status===422?'tooLong':'requestError',requestLanguage));
    const answer=await response.json();
    if (requestEpoch!==epoch) return;
    waiting.remove();
    const item=message('assistant',answer.answer,requestLanguage,answer.status==='answered');
    if (answer.citations?.length) {
      const refs=node('div',undefined,'source-row');
      for (const citation of answer.citations) refs.append(sourceButton(citation.id,`${citation.id} ${t('docNames',requestLanguage)[citation.document]||t('source',requestLanguage)}${citation.figure?' · '+citation.figure:''} ↗`));
      item.append(refs,node('p',t('checked',requestLanguage),'answer-state'));
    }
    if (answer.status==='answered') {
      const play=node('button',t('playAnswer',requestLanguage),'play-button'); play.type='button';
      play.dataset.play='answer'; play.dataset.speechId=`answer-${++messageNumber}`;
      play.dataset.text=answer.answer; play.dataset.language=requestLanguage; item.append(play); renderSpeech();
      history.push({role:'user',content:question},{role:'assistant',content:answer.answer.slice(0,1000)}); history=history.slice(-4);
    }
    if (guide && answer.poster_sections?.length) {
      const index=guide.clues.findIndex(c=>answer.poster_sections.includes(c.id));
      if (index>=0 && index!==clue) selectClue(index);
    }
    $('messages').scrollTop=$('messages').scrollHeight;
  } catch (error) {
    if (requestEpoch!==epoch) return;
    waiting.remove();
    const text=error.name==='AbortError'?t('timeout',requestLanguage)
      :error instanceof TypeError?t('connectionError',requestLanguage):error.message||t('connectionError',requestLanguage);
    message('assistant',text,requestLanguage);
    $('form-error').textContent=text; $('form-error').lang=requestLanguage; $('form-error').hidden=false;
  } finally { clearTimeout(clientTimer); if (requestEpoch===epoch) setPending(false); }
}
document.addEventListener('click',event=>{
  const source=event.target.closest('[data-source]'); if(source) showSource(source.dataset.source);
  const close=event.target.closest('[data-close]'); if(close) closeDialog(close.dataset.close);
  const suggestion=event.target.closest('[data-question]'); if(suggestion) fillQuestion(suggestion.dataset.question);
  const tab=event.target.closest('[data-clue]'); if(tab) selectClue(Number(tab.dataset.clue));
  const locale=event.target.closest('.language-switch [data-language]'); if(locale) switchLanguage(locale.dataset.language);
  const play=event.target.closest('[data-play]');
  if (play && !play.disabled) {
    const kind=play.dataset.play;
    const text=kind==='intro'?guide?.introduction:kind==='clue'?`${guide?.clues[clue].title}. ${guide?.clues[clue].detail}`:play.dataset.text;
    const guideId=kind==='intro'?'intro':kind==='clue'?guide?.clues[clue].id:undefined;
    if(text) speech.play(play.dataset.speechId,text,play.dataset.language||language,{guideId});
  }
});
document.querySelector('.clue-tabs').addEventListener('keydown',event=>{
  if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
  event.preventDefault(); selectClue(event.key==='Home'?0:event.key==='End'?2:(clue+(event.key==='ArrowRight'?1:2))%3,true);
});
$('intro-toggle').addEventListener('click',()=>{
  const expanded=$('intro-toggle').getAttribute('aria-expanded')==='true';
  $('intro-toggle').setAttribute('aria-expanded',!expanded); $('intro-detail').hidden=expanded;
  $('intro-toggle').textContent=t(expanded?'introExpand':'introCollapse');
});
$('play-intro').dataset.speechId='intro'; $('play-clue').dataset.speechId='clue';
$('speech-pause').addEventListener('click',()=>speech.togglePause());
$('speech-stop').addEventListener('click',()=>speech.stop());
$('previous-clue').addEventListener('click',()=>selectClue(clue-1));
$('next-clue').addEventListener('click',()=>selectClue(clue+1));
$('ask-clue').addEventListener('click',()=>{ if(guide) fillQuestion(guide.clues[clue].question); });
$('poster-open').addEventListener('click',()=>showDialog('poster-dialog'));
$('chat-form').addEventListener('submit',sendQuestion);
$('question').addEventListener('keydown',event=>{ if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing) { event.preventDefault(); $('chat-form').requestSubmit(); } });
$('clear-chat').addEventListener('click',()=>{
  speech.stop(); epoch++; controller?.abort(); history=[]; setPending(false); $('form-error').hidden=true;
  const welcome=node('p',t('cleared'),'welcome'); welcome.dataset.i18n='cleared'; $('messages').replaceChildren(welcome);
  $('question').value=''; $('question').focus();
});
for (const dialog of document.querySelectorAll('dialog')) dialog.addEventListener('close',()=>{
  if(dialog.id==='source-dialog') sourceRevision++;
  if(lastFocus?.isConnected) lastFocus.focus();
});
if (window.ResizeObserver) new ResizeObserver(updateSpeechOffset).observe(document.querySelector('.speech-controls'));
window.addEventListener('pagehide',()=>speech.stop());
window.addEventListener('beforeunload',()=>speech.stop());
applyLocale(); loadGuide();
(async()=>{
  try { const response=await fetch('/api/health'); if(!response.ok) throw new Error('health'); lastHealth=await response.json(); }
  catch { lastHealth=null; }
  speech.setReadiness(lastHealth?.speech);
  renderHealth();
})();
