'use strict';
const $ = (id) => document.getElementById(id);
let guide;
let clue = 0;
let history = [];
let epoch = 0;
let controller;
let pending = false;
let lastFocus;
const docNames = {paper:'論文',poster:'海報',correction:'官方勘誤'};
function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (cls) el.className = cls;
  return el;
}
function sourceButton(id, label) {
  const button = node('button', label || id, 'source-button');
  button.type = 'button';
  button.dataset.source = id;
  return button;
}
function sources(el, ids) {
  el.replaceChildren(...ids.map(id => sourceButton(id, `${id} 來源摘錄 ↗`)));
}
function selectClue(index, focus = false) {
  if (!guide) return;
  clue = index;
  const item = guide.clues[index];
  for (const button of document.querySelectorAll('[data-clue]')) {
    const selected = Number(button.dataset.clue) === index;
    button.setAttribute('aria-selected', selected);
    button.tabIndex = selected ? 0 : -1;
    if (selected && focus) button.focus();
  }
  $('clue-panel').setAttribute('aria-labelledby', `tab-${item.id}`);
  $('clue-number').textContent = item.number;
  $('clue-title').textContent = item.title;
  $('clue-summary').textContent = item.summary;
  $('clue-detail').textContent = item.detail;
  $('clue-image').src = `/assets/${item.image}`;
  $('clue-image').alt = `海報 ${item.id}：${item.summary}，數值模擬結果`;
  $('clue-caption').textContent = `海報圖 ${index + 2}・模型模擬`;
  sources($('clue-sources'), item.sources);
}
function fillQuestion(text) {
  $('question').value = text;
  $('question').focus({preventScroll:true});
  $('question').scrollIntoView({block:'center',behavior:'instant'});
}
function showDialog(id) {
  lastFocus = document.activeElement;
  $(id).showModal();
}
function closeDialog(id) {
  $(id).close();
  if (lastFocus?.isConnected) lastFocus.focus();
}
async function showSource(id) {
  $('source-title').textContent = `${id} 來源摘錄`;
  $('source-content').replaceChildren(node('p','正在讀取來源…'));
  if (!$('source-dialog').open) showDialog('source-dialog');
  try {
    const response = await fetch(`/api/sources/${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error('source');
    const item = await response.json();
    $('source-title').textContent = `${id}｜${item.title}`;
    const page = item.pages ? `第 ${item.pages.join('、')} 頁` : item.page ? `第 ${item.page} 頁` : '';
    const meta = node('p', [item.document_title,page,item.figure,item.section,item.kind].filter(Boolean).join(' · '),'source-meta');
    const links = node('div',undefined,'source-links');
    const link = node('a','閱讀原始來源 ↗');
    link.href = item.url; link.target='_blank';link.rel='noopener noreferrer';links.append(link);
    if (item.local_url) { const local=node('a','本機論文 PDF ↗');local.href=item.local_url+(item.page?`#page=${item.page}`:'');local.target='_blank';local.rel='noopener noreferrer';links.append(local); }
    const original=node('details',undefined,'original-source');
    original.append(node('summary','核對英文原文（PDF 文字擷取）'),node('p',item.original_excerpt||'此來源暫無文字擷取，請核對原始文件。','source-excerpt'));
    for(const locator of item.locators||[]) {
      if(locator.document==='correction')continue;
      const ref=node('a',`${docNames[locator.document]}・第 ${locator.page} 頁${locator.section?'・'+locator.section:''} ↗`);
      ref.href=`/api/documents/${locator.document}#page=${locator.page}`;ref.target='_blank';ref.rel='noopener noreferrer';original.append(ref);
    }
    $('source-content').replaceChildren(meta,node('h3','導覽摘要'),node('p',item.summary||item.text,'source-excerpt'),original,node('p',`${item.excerpt_type}。版本：${item.version}。${item.license}`,'source-context'),links);
  } catch { $('source-content').replaceChildren(node('p','目前無法讀取這個來源，請稍後再試。')); }
}
function message(role, text) {
  const el=node('article',undefined,`message ${role}`);
  el.append(node('p',role==='user'?'你的問題':'研究導覽','message-label'),node('p',text,'message-text'));
  $('messages').append(el);
  $('messages').scrollTop=$('messages').scrollHeight;
  return el;
}
function setPending(value) {
  pending=value;
  $('send').disabled=value;
  $('send').textContent=value?'正在查找與回答…':'送出問題 ↗';
  $('question').setAttribute('aria-busy',value);
}
async function sendQuestion(event) {
  event.preventDefault();
  if (pending) return;
  const question=$('question').value.trim();
  if (!question) { $('question').focus();return; }
  const requestEpoch=epoch;
  controller=new AbortController();
  setPending(true);
  $('form-error').hidden=true;
  $('messages').querySelector('.welcome')?.remove();
  message('user',question);
  const waiting=message('waiting','正在檢索研究資料並準備回答；一次只處理一題，請稍候。');
  $('question').value='';
  let clientTimer=setTimeout(()=>controller?.abort(),80000);
  try {
    const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,history:history.slice(-4)}),signal:controller.signal});
    if (!response.ok) throw new Error(response.status===422?'問題或對話過長，請縮短後再送出。':'服務目前無法處理這個問題。');
    const answer=await response.json();
    if (requestEpoch!==epoch) return;
    waiting.remove();
    const item=message('assistant',answer.answer);
    if (answer.citations?.length) {
      const refs=node('div',undefined,'source-row');
      for(const citation of answer.citations) refs.append(sourceButton(citation.id,`${citation.id} ${docNames[citation.document]||'來源'}${citation.figure?'・'+citation.figure:''} ↗`));
      item.append(refs,node('p','引用 ID 已核對；語意正確性仍需人工判斷。','answer-state'));
    }
    if(answer.status==='answered') {
      history.push({role:'user',content:question},{role:'assistant',content:answer.answer.slice(0,1000)});
      history=history.slice(-4);
    }
    if(answer.poster_sections?.length) {
      const index=guide.clues.findIndex(c=>answer.poster_sections.includes(c.id));
      if(index>=0) selectClue(index);
    }
    $('messages').scrollTop=$('messages').scrollHeight;
  } catch(error) {
    if(requestEpoch!==epoch) return;
    waiting.remove();
    const text=error.name==='AbortError'?'等待已結束，此題結果未知。服務仍可能處理中，沒有自動重送。':error.message||'連線中斷，此題結果未知；沒有自動重送。';
    message('assistant',text);
    $('form-error').textContent=text;$('form-error').hidden=false;
  } finally {clearTimeout(clientTimer);if(requestEpoch===epoch)setPending(false);}
}
document.addEventListener('click',event=>{
  const source=event.target.closest('[data-source]');if(source)showSource(source.dataset.source);
  const close=event.target.closest('[data-close]');if(close)closeDialog(close.dataset.close);
  const suggestion=event.target.closest('[data-question]');if(suggestion)fillQuestion(suggestion.dataset.question);
  const tab=event.target.closest('[data-clue]');if(tab)selectClue(Number(tab.dataset.clue));
});
document.querySelector('.clue-tabs').addEventListener('keydown',event=>{
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  event.preventDefault();selectClue(event.key==='Home'?0:event.key==='End'?2:(clue+(event.key==='ArrowRight'?1:2))%3,true);
});
$('intro-toggle').addEventListener('click',()=>{
  const expanded=$('intro-toggle').getAttribute('aria-expanded')==='true';
  $('intro-toggle').setAttribute('aria-expanded',!expanded);$('intro-detail').hidden=expanded;
  $('intro-toggle').textContent=expanded?'展開導覽 ＋':'收起導覽 −';
});
$('ask-clue').addEventListener('click',()=>{if(guide)fillQuestion(guide.clues[clue].question);});
$('poster-open').addEventListener('click',()=>showDialog('poster-dialog'));
$('chat-form').addEventListener('submit',sendQuestion);
$('question').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();$('chat-form').requestSubmit();}});
$('clear-chat').addEventListener('click',()=>{
  epoch++;controller?.abort();history=[];setPending(false);$('form-error').hidden=true;
  $('messages').replaceChildren(node('p','對話已清除，可以從新的問題開始。','welcome'));
  $('question').value='';$('question').focus();
});
for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('close',()=>{if(lastFocus?.isConnected)lastFocus.focus();});
async function init(){
  try{const response=await fetch('/api/guide');if(!response.ok)throw new Error();guide=await response.json();$('intro-text').textContent=guide.introduction;sources($('intro-sources'),guide.introduction_sources);selectClue(0);}catch{$('intro-text').textContent='目前無法載入完整導覽，仍可開啟海報與論文。';}
  try{const response=await fetch('/api/health');if(!response.ok)throw new Error();const state=await response.json();const ready=state.index.ready&&state.model.ready;$('health').textContent=ready?'研究資料與本機問答已就緒。':!state.index.ready?'資料索引尚未就緒，可以先讀導覽與來源。':'本機模型尚未就緒，可以先讀導覽與來源。';$('health').classList.toggle('ready',ready);}catch{$('health').textContent='目前無法確認問答狀態，可以先讀導覽與來源。';}
}
init();
