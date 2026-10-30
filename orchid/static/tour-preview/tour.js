'use strict';
(function(root) {
  const chars = value => Array.from(String(value));
  function questionPrefix(section) {
    return section ? `[Poster section: ${section.context_title}] ` : '[Study question] ';
  }
  function makeChatRequest({question, section, history = [], language = 'en'}) {
    const text = String(question || '').trim();
    if (!text) throw new Error('empty');
    const contextual = questionPrefix(section) + text;
    if (chars(contextual).length > 600) throw new Error('length');
    return {question:contextual, language:language === 'zh-TW' ? 'zh-TW' : 'en',
      history:history.filter(turn => ['user','assistant'].includes(turn.role) && typeof turn.content === 'string' && turn.content.trim())
        .slice(-4).map(turn => ({role:turn.role, content:chars(turn.content).slice(0,1000).join('')}))};
  }
  function parseSection(hash, allowed) {
    const section = String(hash || '').replace(/^#/, '');
    return section === 'overview' || allowed.includes(section) ? section : 'overview';
  }
  function createTourSequence({speech, onChapter = () => {}, onFinish = () => {}}) {
    let run = null;
    let revision = 0;
    let starting = false;
    let previous = {status:'idle',id:null};
    function stop() { run = null; revision++; speech.stop(); }
    function playCurrent() {
      const current = run;
      const chapter = current.chapters[current.index];
      current.expectedId = `tour-${current.revision}-${chapter.id}`;
      onChapter({sectionId:chapter.id,index:current.index,total:current.chapters.length});
      starting = true;
      let result;
      try { result = speech.play(current.expectedId, chapter.text, current.language); }
      finally { starting = false; }
      Promise.resolve(result).then(ok => {
        if (run === current && !ok && !['ready','paused'].includes(speech.state.status)) run = null;
      }).catch(() => { if (run === current) { run = null; onFinish('error'); } });
    }
    function start(chapters, language) {
      stop();
      if (!chapters.length) return;
      run = {chapters,language,index:0,revision};
      playCurrent();
    }
    function onState(state) {
      const before = previous;
      previous = {...state};
      if (['error','unavailable'].includes(state.status)) { run = null; return; }
      if (!run || starting || state.status !== 'idle' || !['playing','paused'].includes(before.status) || before.id !== run.expectedId) return;
      run.index++;
      if (run.index >= run.chapters.length) { run = null; onFinish('complete'); }
      else playCurrent();
    }
    return {start,stop,onState,get active() { return run ? {language:run.language,index:run.index,sectionId:run.chapters[run.index].id} : null; }};
  }
  async function createPreparedSpeechFetch({fetch, data, manifest, crypto}) {
    const clips = new Map();
    const totals = {};
    const counts = {};
    const tourOrder = data.tour_order || data.order;
    if (manifest?.complete && crypto?.subtle) {
      for (const clip of manifest.items || []) {
        if (!tourOrder.includes(clip.id)) continue;
        const entry = data.sections.find(item => item.id === clip.id);
        const narration = entry?.[clip.language]?.narration;
        if (!narration || !/^\/assets\/tour-preview\/audio\/[A-Za-z0-9_.-]+\.wav$/.test(clip.url) || !Number.isFinite(clip.duration_seconds) || clip.duration_seconds <= 0) continue;
        const digest = await crypto.subtle.digest('SHA-256',new TextEncoder().encode(narration));
        const hash = Array.from(new Uint8Array(digest),value => value.toString(16).padStart(2,'0')).join('');
        if (hash !== clip.text_sha256) continue;
        const key = clip.language + '\0' + narration;
        if (clips.has(key)) continue;
        clips.set(key,clip);
        counts[clip.language] = (counts[clip.language] || 0) + 1;
        totals[clip.language] = (totals[clip.language] || 0) + clip.duration_seconds;
      }
    }
    const preparedLanguages = Object.keys(counts).filter(language => counts[language] === tourOrder.length);
    return {preparedLanguages, durations:totals, fetch(url, options) {
      if (url === '/api/speech' && options?.method === 'POST' && typeof options.body === 'string') {
        const body = JSON.parse(options.body);
        const clip = clips.get(body.language + '\0' + body.text);
        if (clip) return fetch(clip.url,{signal:options.signal,headers:{Accept:'audio/wav'}});
      }
      return fetch(url,options);
    }};
  }
  const api = {questionPrefix,makeChatRequest,parseSection,createTourSequence,createPreparedSpeechFetch};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.OrchidTour = api;
  if (!root.document) return;

  const $ = id => document.getElementById(id);
  const text = {
    en:{brand:'Orchid guide',skip:'Skip to the guide text',back:'Back to entire poster',overview:'Entire poster tour',overviewLocation:'A guide to the whole study',duration:'Read the whole poster, or listen to the guide.',
      playFull:'Play full tour',playSection:'Play section',pause:'Pause',resume:'Resume',stop:'Stop',preparing:'Preparing audio…',checking:'Checking audio availability…',available:'Audio is optional. You can read every paragraph below.',paused:'Paused. Resume to continue the current section.',playing:'Playing the guide.',ready:'Audio is ready. Tap Resume to allow playback.',complete:'The guide has finished.',unavailable:'Audio is unavailable. You can still read the guide and sources.',unsupported:'This browser cannot use the audio controls. The text remains available.',speechError:'Audio could not be played',checkServices:'Check availability again',
      enlarge:'Enlarge image',posterPDF:'Original poster PDF',posterText:'Selectable English poster text',readingTitle:'Read along',readAlong:'Read guide',quickQuestion:'Ask a question',exploreHint:'Tap a framed section to explore',openSection:'Open section',openExcerpt:'Open excerpt',posterDirect:'Original poster section',posterNotes:'Poster supplementary notes',journalTitle:'Journal supplementary material',onDemand:'Audio is generated on request; preparation can take several seconds.',recorded:'Recorded narration',seconds:'seconds',durationTarget:'2–3 minute target',belowTarget:'below the target',readingHint:'The text is always available. Audio is optional.',evidence:'These are model predictions, not experimental proof.',paperPDF:'Full paper PDF',publication:'Publication',
      close:'Close',returnGuide:'Return to guide',actualPixels:'View full resolution',fitImage:'Fit image to screen',zoomHint:'Use browser zoom, or view full resolution and pan the image.',imageLimit:'Higher-resolution PDF text remains sharp. Scientific raster figures retain the detail of their original embedded images.',
      askStudy:'Ask about the study',askSection:'Ask about this section',questionLabel:'Your question',send:'Send question',clear:'Clear conversation',historyHint:'Only the last four short messages are used as context. This conversation is not saved.',context:'Question context: ',study:'Entire study',
      remaining:'characters left · section context included',tooLong:'The question and section context exceed 600 characters. Please shorten the question.',empty:'Please enter a question.',sending:'Waiting for the research answer…',chatFailure:'The answer could not be retrieved. No automatic retry was made.',chatTimeout:'The answer timed out after 80 seconds. The server may still be working; the question was not resent.',about:'about',minutes:'minutes',cleared:'Conversation cleared. Earlier results will not be shown.',user:'Your question',assistant:'Research answer',source:'Research excerpt',sourceLoading:'Loading the research source…',sourceError:'The source could not be loaded.',original:'Original English excerpt',notes:'Reviewed Chinese notes',sourceDocument:'Open source document',localDocument:'Open local PDF',
      imageOverview:'Complete original English research poster. Select one of the eight sections.',imageSection:'Complete original English poster section',captionOverview:'Original English poster · select a section to read it closely',captionSection:'Complete poster section, including its original figures and captions',assetError:'The high-resolution images could not be loaded. The guide text and original PDF remain available.',dataError:'The guide text could not be loaded. Please refresh or open the original PDF.',larger:'Larger text',resetText:'Reset text to 18 pixels',closer:'Closer look',listening:'Listening: ',sources:'Sources & evidence',textOnly:'The research model is unavailable; the guide text and audio remain usable.'},
    'zh-TW':{brand:'蘭花導覽',skip:'跳至導覽文字',back:'回到完整海報',overview:'完整海報導覽',overviewLocation:'從整篇研究開始',duration:'可以閱讀整張海報，也可以聆聽導覽。',
      playFull:'播放完整導覽',playSection:'播放此區介紹',pause:'暫停',resume:'繼續播放',stop:'停止',preparing:'正在準備音訊…',checking:'正在確認音訊可用性…',available:'可以選擇聆聽，也可以直接閱讀下方每一段文字。',paused:'已暫停，可從目前這一段繼續聽。',playing:'正在播放導覽。',ready:'音訊已準備好，請點「繼續播放」允許瀏覽器播放。',complete:'導覽已播放完畢。',unavailable:'目前無法使用音訊，仍可閱讀導覽與來源。',unsupported:'此瀏覽器無法使用音訊控制，仍可閱讀文字。',speechError:'音訊無法播放',checkServices:'重新確認可用性',
      enlarge:'放大圖片',posterPDF:'英文原版海報 PDF',posterText:'可選取的英文海報文字',readingTitle:'看文字，也能聽導覽',readAlong:'閱讀導覽文字',quickQuestion:'提問',exploreHint:'點選框起的區塊，放大探索',openSection:'開啟區塊',openExcerpt:'開啟節錄',posterDirect:'原海報區塊',posterNotes:'海報補充說明',journalTitle:'期刊補充資料',onDemand:'音訊依需求生成，準備一段可能需要數秒。',recorded:'實際錄音長度',seconds:'秒',durationTarget:'目標 2–3 分鐘',belowTarget:'短於目標',readingHint:'文字預設可讀，不必先播放音訊。',evidence:'這些是模型預測，不等於實驗證明。',paperPDF:'完整論文 PDF',publication:'出版頁面',
      close:'關閉',returnGuide:'回到導覽',actualPixels:'以完整解析度檢視',fitImage:'符合螢幕寬度',zoomHint:'可用瀏覽器縮放，或切換完整解析度後平移圖片。',imageLimit:'高解析輸出保留 PDF 字型與向量細節；科學點陣圖仍受原始內嵌圖片的細節上限限制。',
      askStudy:'詢問這篇研究',askSection:'詢問這個區塊',questionLabel:'你的問題',send:'送出問題',clear:'清除對話',historyHint:'只使用最近四則短訊息作為背景；不永久儲存對話。',context:'提問背景：',study:'整篇研究',
      remaining:'字元可用・已計入區塊背景',tooLong:'問題加上區塊背景超過 600 字元，請縮短問題。',empty:'請輸入問題。',sending:'正在等待研究問答回覆…',chatFailure:'無法取得回覆，沒有自動重送問題。',chatTimeout:'等待回覆已超過 80 秒。伺服器可能仍在處理，沒有自動重送問題。',about:'約',minutes:'分鐘',cleared:'對話已清除，先前的結果不會重新出現。',user:'你的問題',assistant:'研究問答',source:'研究來源',sourceLoading:'正在讀取研究來源…',sourceError:'無法讀取這個來源。',original:'英文原文節錄',notes:'已校對的中文摘要與校註',sourceDocument:'開啟來源文件',localDocument:'開啟本機 PDF',
      imageOverview:'完整英文原版研究海報，可選取八個區塊。',imageSection:'完整英文海報區塊',captionOverview:'英文原版海報・點選區塊可放大閱讀',captionSection:'完整海報區塊，保留原圖與圖說',assetError:'無法讀取高解析圖片，仍可閱讀導覽文字與原始 PDF。',dataError:'無法讀取導覽文字，請重新整理或開啟原始 PDF。',larger:'放大文字',resetText:'還原為 18 像素文字',closer:'進一步看',listening:'目前聆聽：',sources:'來源與依據',textOnly:'研究問答模型目前無法使用，仍可閱讀導覽與聆聽音訊。'}
  };
  let language = 'en';
  try { if (localStorage.getItem('orchid-language') === 'zh-TW') language = 'zh-TW'; } catch { /* Preference storage is optional. */ }
  let data = null, manifest = null, section = 'overview', readingSize = 18;
  let sequence, speech, listening = null, completed = false;
  let health = null, healthChecked = false, overviewScroll = 0, fromOverview = false;
  let preparedAudio = null;
  let speechFetch = fetch.bind(root);
  let chatEpoch = 0, requestController = null, pending = false, history = [];
  let sourceEpoch = 0, sourceController = null, zoomActual = false;
  const focusBeforeDialog = new Map();
  const t = key => text[language][key] || key;
  const currentSection = () => data?.sections.find(item => item.id === section);
  const tourSections = () => (data.tour_order || data.order).map(id => data.sections.find(item => item.id === id));
  const node = (tag, value, className) => { const element = document.createElement(tag); if (value !== undefined) element.textContent = value; if (className) element.className = className; return element; };
  function setText(id, value) { $(id).textContent = value; }
  function sourceButtons(refs, label = t('sources')) {
    const group = node('details',undefined,'source-list');
    const entries = [...new Map(refs.map(ref => typeof ref === 'string' ? [ref,{id:ref}] : [ref.id,ref])).values()];
    group.append(node('summary',`${label} (${entries.length})`));
    const row = node('div',undefined,'source-row');
    for (const ref of entries) {
      const id = ref.id;
      const title = ref.title || data?.source_labels?.[id]?.[language] || data?.source_labels?.[id.split('_')[0]]?.[language] || t('source');
      const button = node('button',undefined,'source-button'); button.type = 'button'; button.dataset.source = id;
      const copy = node('span',undefined,'source-copy');
      copy.append(node('span',title,'source-name'),node('span',`${id} · ${t('openExcerpt')}`,'source-meta'));
      const glyph = node('span','→','control-glyph'); glyph.setAttribute('aria-hidden','true');
      button.append(copy,glyph); row.append(button);
    }
    group.append(row); return group;
  }
  function directSources(entry) {
    const group = node('section',undefined,'poster-sources');
    group.append(node('h3',entry.id === 'supplementary' ? t('posterNotes') : t('posterDirect')));
    const links = node('div',undefined,'source-links');
    links.append(safeLink(t('posterPDF'),'/api/documents/poster#page=1'));
    const image = node('button',t('enlarge'),'secondary-button'); image.type = 'button'; image.dataset.sectionImage = 'true'; links.append(image);
    if (entry.id === 'references') links.append(safeLink(t('paperPDF'),'/api/documents/paper'));
    group.append(links);
    const supplement = data.journal_supplement;
    if (supplement) group.append(node('h3',t('journalTitle')),node('p',supplement[language].description),safeLink(supplement[language].label,supplement.url));
    return group;
  }
  function localizedUI() {
    document.documentElement.lang = language === 'en' ? 'en' : 'zh-Hant-TW';
    document.querySelectorAll('[data-i18n]').forEach(element => { element.textContent = t(element.dataset.i18n); });
    document.querySelectorAll('[data-language]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.language === language)));
    $('text-size').setAttribute('aria-label',readingSize === 22 ? t('resetText') : `${t('larger')}: ${readingSize + 2}px`);
    setText('question-title',section === 'overview' ? t('askStudy') : t('askSection'));
  }
  function imageItem() { return manifest?.images[section]; }
  function setImage(image, item, zoom = false) {
    if (!item) return;
    const variants = item.variants;
    const first = variants[0];
    image.width = first.width; image.height = first.height;
    image.sizes = zoom ? 'min(1120px, calc(100vw - 56px))' : '(max-width: 711px) calc(100vw - 32px), (max-width: 900px) 680px, (max-width: 1280px) calc((100vw - 80px) / 2), 600px';
    image.srcset = variants.map(value => `${value.url} ${value.width}w`).join(', ');
    image.src = first.url;
    image.alt = section === 'overview' ? t('imageOverview') : `${t('imageSection')}: ${currentSection()[language].title}`;
  }
  function renderImage() {
    $('poster-hotspots').replaceChildren();
    $('poster-hotspots').hidden = section !== 'overview';
    const item = imageItem();
    $('poster-figure').hidden = !item;
    $('open-image').disabled = !item;
    $('poster-text').hidden = !item;
    if (!item) return;
    setImage($('poster-image'),item);
    setText('image-caption',section === 'overview' ? t('captionOverview') : t('captionSection'));
    setText('poster-text-content',item.poster_text || '');
    if (section !== 'overview') return;
    for (const entry of data.sections) {
      const bounds = manifest.images[entry.id].bounds;
      const button = node('button',undefined,'poster-hotspot'); button.type = 'button'; button.dataset.section = entry.id;
      button.setAttribute('aria-label',`${t('openSection')}: ${entry[language].title}`);
      const frame = node('div',undefined,'poster-region-frame'); frame.setAttribute('aria-hidden','true'); frame.dataset.frame = entry.id;
      for (const element of [button,frame]) {
        element.style.left = bounds[0] * 100 + '%'; element.style.top = bounds[1] * 100 + '%';
        element.style.width = (bounds[2] - bounds[0]) * 100 + '%'; element.style.height = (bounds[3] - bounds[1]) * 100 + '%';
      }
      const label = node('span',undefined,'poster-region-label');
      label.append(node('span',entry[language].nav_title || entry[language].title,'region-name-long'),node('span',entry[language].map_label || entry[language].title,'region-name-short'),node('span','+','region-open'));
      frame.append(label); $('poster-hotspots').append(button,frame);
    }
  }
  function renderNarration() {
    $('narration').replaceChildren();
    const entries = section === 'overview' ? tourSections() : [currentSection()];
    for (const entry of entries) {
      const article = node('article',undefined,'narration-chapter'); article.dataset.chapter = entry.id;
      article.append(node('h2',entry[language].title),node('p',entry.position,'chapter-location'),node('p',entry[language].narration));
      if (section !== 'overview' && entry[language].detail) article.append(node('h3',t('closer'),'detail-heading'),node('p',entry[language].detail));
      if (section !== 'overview' && entry.source_locators) article.append(directSources(entry));
      article.append(sourceButtons(section === 'overview' ? entry.sources : [...entry.sources,...(entry.detail_sources || [])],entry.source_label?.[language] || t('sources')));
      $('narration').append(article);
    }
    highlightChapter();
  }
  function highlightChapter() {
    document.querySelectorAll('[data-chapter]').forEach(element => element.classList.toggle('is-speaking',element.dataset.chapter === listening?.sectionId));
  }
  function render() {
    localizedUI();
    if (!data) return;
    const entry = currentSection();
    setText('view-title',entry ? entry[language].title : t('overview'));
    setText('view-location',entry ? entry.position : t('overviewLocation'));
    document.title = `${$('view-title').textContent} · ${t('brand')}`;
    $('back-overview').hidden = !entry;
    $('poster-hint').hidden = !!entry;
    $('duration-note').hidden = !!entry;
    if (preparedAudio?.preparedLanguages.includes(language)) {
      const seconds = Math.round(preparedAudio.durations[language]);
      const clock = Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2,'0');
      setText('duration-note',language === 'en' ? `About ${Math.round(seconds / 60)} minutes · ${clock} of narration` : `約 ${Math.round(seconds / 60)} 分鐘・音訊 ${clock}`);
    }
    setText('open-question',entry ? t('askSection') : t('askStudy'));
    const context = t('context') + (entry ? entry[language].title : t('study'));
    setText('question-scope',context); setText('chat-context',context);
    $('section-links').replaceChildren(...data.sections.map(item => {
      const link = node('a',item[language].nav_title || item[language].title,'section-button'); link.href = `#${item.id}`; if (item.id === section) link.setAttribute('aria-current','page'); return link;
    }));
    renderImage(); renderNarration(); renderAudio(); updateBudget();
  }
  function renderAudio() {
    if (!speech) { setText('audio-status',t('unsupported')); return; }
    const state = speech.state;
    const availability = speech.availability(language);
    $('play-guide').disabled = !data || availability !== 'available' || state.status === 'preparing';
    $('stop-guide').disabled = !['playing','paused','preparing','ready'].includes(state.status);
    const key = state.status === 'playing' ? 'pause' : ['paused','ready'].includes(state.status) ? 'resume' : state.status === 'preparing' ? 'preparing' : section === 'overview' ? 'playFull' : 'playSection';
    setText('play-guide',t(key));
    let message = availability === 'checking' ? t('checking') : availability === 'unsupported' ? t('unsupported') : availability !== 'available' ? t('unavailable') : completed ? t('complete') : t('available');
    if (availability === 'available' && !completed && state.status === 'idle' && (section !== 'overview' || !preparedAudio?.preparedLanguages.includes(language))) message = t('onDemand');
    if (['preparing','playing','paused','ready'].includes(state.status)) message = t(state.status);
    if (state.status === 'error') message = `${t('speechError')} (${state.reason || 'unknown'}). ${t('unavailable')}`;
    setText('audio-status',message);
    $('check-services').hidden = !healthChecked || availability === 'available';
    const showLocation = listening && ['preparing','playing','paused','ready'].includes(state.status);
    $('listening-location').hidden = !showLocation;
    if (showLocation) { const entry = data.sections.find(value => value.id === listening.sectionId); setText('listening-location',`${t('listening')}${entry.position} · ${listening.index + 1}/${listening.total}`); }
  }
  function stopAudio() { completed = false; sequence?.stop(); listening = null; highlightChapter(); renderAudio(); }
  function changeView() {
    if (!data) return;
    const next = parseSection(location.hash,data.order);
    if (next === section) return;
    if (section === 'overview') overviewScroll = window.scrollY;
    stopAudio(); resetConversation();
    section = next; render();
    requestAnimationFrame(() => { window.scrollTo(0,section === 'overview' ? overviewScroll : 0); if (section !== 'overview') { $('back-overview').focus({preventScroll:true}); } });
  }
  function goSection(id) { fromOverview = section === 'overview'; location.hash = id; }
  function openDialog(id) { focusBeforeDialog.set(id,document.activeElement); $(id).showModal(); }
  function closeDialog(id) { $(id).close(); }
  function updateBudget() {
    const remaining = 600 - chars(questionPrefix(currentSection())).length - chars($('question').value.trim()).length;
    setText('question-budget',`${remaining} ${t('remaining')}`);
    $('send-question').disabled = pending || remaining < 0 || !$('question').value.trim();
  }
  function resetConversation() {
    chatEpoch++; requestController?.abort(); requestController = null; history = []; pending = false;
    $('messages').replaceChildren(); $('question').value = ''; $('chat-error').hidden = true; setText('chat-status','');
    updateBudget();
  }
  function appendMessage(role, value, citations = []) {
    const article = node('article',undefined,'message'); article.lang = language === 'en' ? 'en' : 'zh-Hant-TW';
    article.append(node('h3',t(role)),node('p',value));
    if (citations.length) article.append(sourceButtons(citations.filter(item => typeof item.id === 'string')));
    $('messages').append(article);
  }
  async function sendQuestion(event) {
    event.preventDefault(); if (pending) return;
    let body;
    try { body = makeChatRequest({question:$('question').value,section:currentSection(),history,language}); }
    catch (error) { setText('chat-error',error.message === 'length' ? t('tooLong') : t('empty')); $('chat-error').hidden = false; return; }
    const epoch = chatEpoch, requestLanguage = language;
    const activeController = new AbortController();
    requestController = activeController; pending = true; updateBudget(); $('chat-error').hidden = true; setText('chat-status',t('sending'));
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; activeController.abort(); },80000);
    appendMessage('user',$('question').value.trim());
    try {
      const response = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:activeController.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      if (epoch !== chatEpoch || language !== requestLanguage) return;
      if (typeof result.answer !== 'string') throw new Error('Invalid answer');
      appendMessage('assistant',result.answer,Array.isArray(result.citations) ? result.citations : []);
      if (result.status === 'answered') { history.push({role:'user',content:body.question},{role:'assistant',content:chars(result.answer).slice(0,1000).join('')}); history = history.slice(-4); }
      setText('chat-status',result.status === 'answered' ? '' : result.status || 'unknown');
      $('question').value = '';
    } catch (error) {
      if (epoch === chatEpoch && (timedOut || error.name !== 'AbortError')) { setText('chat-error',t(timedOut ? 'chatTimeout' : 'chatFailure')); $('chat-error').hidden = false; setText('chat-status',''); }
    } finally { clearTimeout(timeout); if (epoch === chatEpoch) { pending = false; requestController = null; updateBudget(); } }
  }
  function safeLink(label, value) {
    const link = node('a',label,'link-button');
    try { const url = new URL(value,location.origin); if (!['http:','https:'].includes(url.protocol)) return node('span',label); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; }
    catch { return node('span',label); }
    return link;
  }
  async function showSource(id) {
    if (!/^[A-Z][A-Z0-9_]{0,80}$/.test(id)) return;
    const epoch = ++sourceEpoch, sourceLanguage = language;
    sourceController?.abort(); sourceController = new AbortController();
    setText('source-title',`${id} · ${t('source')}`); $('source-content').replaceChildren(node('p',t('sourceLoading')));
    if (!$('source-dialog').open) openDialog('source-dialog');
    try {
      const response = await fetch(`/api/sources/${encodeURIComponent(id)}?language=${encodeURIComponent(language)}`,{signal:sourceController.signal});
      if (!response.ok) throw new Error('source');
      const item = await response.json(); if (epoch !== sourceEpoch || sourceLanguage !== language) return;
      setText('source-title',`${id} · ${item.title}`);
      const original = node('p',item.original_excerpt || 'Original excerpt unavailable.','source-excerpt'); original.lang = 'en';
      const notes = node('p',item.summary || item.text || '', 'source-excerpt'); notes.lang = 'zh-Hant-TW';
      const other = node('details'); other.append(node('summary',language === 'en' ? t('notes') : t('original')),language === 'en' ? notes : original);
      const links = node('div',undefined,'source-links');
      if (item.url) links.append(safeLink(t('sourceDocument'),item.url));
      if (item.local_url) links.append(safeLink(t('localDocument'),item.local_url + (item.page ? `#page=${item.page}` : '')));
      for (const locator of item.locators || []) if (['paper','poster'].includes(locator.document)) links.append(safeLink(`${locator.document} · p. ${locator.page}`,`/api/documents/${locator.document}#page=${locator.page}`));
      $('source-content').replaceChildren(node('p',[item.document_title,item.section,item.figure,item.kind].filter(Boolean).join(' · '),'small secondary'),node('h3',language === 'en' ? t('original') : t('notes')),language === 'en' ? original : notes,other,node('p',`${item.excerpt_type || ''} · ${item.license || ''}`,'small secondary'),links);
    } catch (error) { if (epoch === sourceEpoch && error.name !== 'AbortError') $('source-content').replaceChildren(node('p',t('sourceError'),'error')); }
  }
  async function checkHealth() {
    $('check-services').disabled = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(),10000);
    try { const response = await fetch('/api/health',{signal:controller.signal}); if (!response.ok) throw new Error('health'); health = await response.json(); speech?.setReadiness(health.speech); }
    catch { health = null; speech?.setReadiness(null); }
    finally { clearTimeout(timeout); healthChecked = true; $('check-services').disabled = false; renderAudio(); }
  }
  function startSpeech() {
    if (!speech || !data) return;
    completed = false;
    if (['playing','paused','ready'].includes(speech.state.status)) { speech.togglePause(); return; }
    const entries = section === 'overview' ? tourSections() : [currentSection()];
    sequence.start(entries.map(entry => ({id:entry.id,text:entry[language].narration + (section === 'overview' || !entry[language].detail ? '' : '\n\n' + entry[language].detail)})),language);
  }
  function openQuestion() {
    if (speech?.state.status === 'playing') speech.togglePause();
    else if (speech?.state.status === 'preparing') stopAudio();
    if (health && (!health.model?.ready || !health.index?.ready)) setText('chat-status',t('textOnly'));
    openDialog('question-dialog'); $('question').focus();
  }
  async function boot() {
    localizedUI();
    if (root.OrchidSpeech) {
      speech = root.OrchidSpeech.createSpeechController({fetch:(...args) => speechFetch(...args),Audio:root.Audio,URL:root.URL,AbortController:root.AbortController},state => { sequence?.onState(state); renderAudio(); });
      sequence = createTourSequence({speech,onChapter:chapter => { listening = chapter; highlightChapter(); renderAudio(); },onFinish:reason => { completed = reason === 'complete'; listening = null; highlightChapter(); renderAudio(); }});
    }
    const results = await Promise.allSettled([fetch('./tour-data.json').then(response => { if (!response.ok) throw new Error('data'); return response.json(); }),fetch('/assets/tour-preview/manifest.json').then(response => { if (!response.ok) throw new Error('assets'); return response.json(); }),fetch('/assets/tour-preview/audio/manifest.json').then(response => { if (!response.ok) throw new Error('audio'); return response.json(); })]);
    if (results[0].status === 'fulfilled') data = results[0].value;
    if (results[1].status === 'fulfilled') manifest = results[1].value;
    if (data) { preparedAudio = await createPreparedSpeechFetch({fetch:fetch.bind(root),data,manifest:results[2].status === 'fulfilled' ? results[2].value : null,crypto:root.crypto}); speechFetch = preparedAudio.fetch; }
    if (!data || !manifest) { $('asset-error').hidden = false; setText('asset-error',t(data ? 'assetError' : 'dataError')); }
    if (data) { section = parseSection(location.hash,data.order); if (location.hash !== `#${section}`) window.history.replaceState(null,'',`#${section}`); render(); }
    await checkHealth();
  }
  document.querySelectorAll('[data-language]').forEach(button => button.addEventListener('click',() => {
    if (button.dataset.language === language) return;
    stopAudio(); resetConversation(); language = button.dataset.language;
    try { localStorage.setItem('orchid-language',language); } catch { /* Reading and playback do not depend on preference storage. */ }
    render();
  }));
  $('text-size').addEventListener('click',() => { readingSize = readingSize === 22 ? 18 : readingSize + 2; document.documentElement.style.setProperty('--reading-size',`${readingSize}px`); $('text-size').textContent = readingSize === 22 ? 'A−' : 'A+'; localizedUI(); });
  $('play-guide').addEventListener('click',startSpeech); $('stop-guide').addEventListener('click',stopAudio); $('check-services').addEventListener('click',checkHealth);
  $('poster-hotspots').addEventListener('click',event => { const button = event.target.closest('[data-section]'); if (button) goSection(button.dataset.section); });
  $('section-links').addEventListener('click',() => { fromOverview = section === 'overview'; });
  $('back-overview').addEventListener('click',event => { if (fromOverview) { event.preventDefault(); fromOverview = false; window.history.back(); } });
  window.addEventListener('hashchange',changeView);
  $('open-image').addEventListener('click',() => { const item = imageItem(); if (!item) return; zoomActual = false; setText('image-title',$('view-title').textContent); setText('image-scale',t('actualPixels')); $('zoom-image').style.width = '100%'; setImage($('zoom-image'),item,true); openDialog('image-dialog'); });
  $('image-scale').addEventListener('click',() => { zoomActual = !zoomActual; const largest = imageItem().variants.at(-1); $('zoom-image').style.width = zoomActual ? `${largest.width}px` : '100%'; if (zoomActual) { $('zoom-image').removeAttribute('srcset'); $('zoom-image').src = largest.url; } else setImage($('zoom-image'),imageItem(),true); setText('image-scale',t(zoomActual ? 'fitImage' : 'actualPixels')); });
  $('open-question').addEventListener('click',openQuestion);
  $('quick-question').addEventListener('click',openQuestion);
  $('read-along').addEventListener('click',() => {
    const target = (listening && document.querySelector(`[data-chapter="${listening.sectionId}"]`)) || $('reading');
    target.style.scrollMarginTop = document.querySelector('.audio-panel').getBoundingClientRect().height + 16 + 'px';
    target.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
  });
  document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click',() => closeDialog(button.dataset.close)));
  document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('close',() => {
    if (dialog.id === 'source-dialog') { sourceEpoch++; sourceController?.abort(); }
    const previous = focusBeforeDialog.get(dialog.id); if (previous?.isConnected) previous.focus({preventScroll:true});
  }));
  document.addEventListener('click',event => { const button = event.target.closest('[data-source]'); if (button) showSource(button.dataset.source); });
  document.addEventListener('click',event => { if (event.target.closest('[data-section-image]')) $('open-image').click(); });
  $('chat-form').addEventListener('submit',sendQuestion); $('question').addEventListener('input',updateBudget);
  $('clear-chat').addEventListener('click',() => { resetConversation(); stopAudio(); setText('chat-status',t('cleared')); $('question').focus(); });
  window.addEventListener('pagehide',() => { stopAudio(); chatEpoch++; requestController?.abort(); sourceEpoch++; sourceController?.abort(); });
  boot().catch(() => { $('asset-error').hidden = false; setText('asset-error',t('dataError')); });
})(globalThis);
