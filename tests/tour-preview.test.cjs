const {test} = require('node:test');
const assert = require('node:assert/strict');
const {makeChatRequest, parseSection, createTourSequence, createPreparedSpeechFetch, makeFeedbackRequest} = require('../orchid/static/tour-preview/tour.js');

test('question budget includes fixed context and preserves Unicode without silent truncation', () => {
  const section = {id:'clue2', context_title:'Clue 2: fused patches'};
  const prefix = '[Poster section: Clue 2: fused patches] ';
  const text = '花'.repeat(600 - prefix.length);
  const body = makeChatRequest({question:text, section, language:'zh-TW', history:[]});
  assert.equal(Array.from(body.question).length, 600);
  assert.equal(body.question, prefix + text);
  assert.throws(() => makeChatRequest({question:text+'花', section, language:'zh-TW'}), /length/);
  assert.throws(() => makeChatRequest({question:'  ', section}), /empty/);
});

test('chat history is bounded to four nonempty messages of at most 1000 characters', () => {
  const history = Array.from({length:8}, (_,i) => ({role:i%2?'assistant':'user', content:'x'.repeat(1200)+i}));
  const body = makeChatRequest({question:'What is simulated?', history, language:'en'});
  assert.equal(body.history.length, 4);
  assert.ok(body.history.every(turn => Array.from(turn.content).length === 1000));
  assert.equal(body.language, 'en');
});

test('feedback requires a rating or comment and preserves the Unicode budget without truncation', () => {
  const ids={submissionId:'4e640a9b-90ce-47e4-8318-43b70bed6310',conversationId:'d177f680-fb26-4dce-b0e9-c7575730b3ec'};
  assert.throws(()=>makeFeedbackRequest({...ids,comment:'  ',clarity:null}),/emptyFeedback/);
  assert.throws(()=>makeFeedbackRequest({...ids,comment:'花'.repeat(1501)}),/feedbackLength/);
  const original='\n'+'花'.repeat(1498)+' ';
  const body=makeFeedbackRequest({...ids,comment:original,clarity:'partly',language:'zh-TW',section:'clue2'});
  assert.equal(body.comment,original,'saved feedback must preserve the exact submitted whitespace and line breaks');
  assert.equal(Array.from(body.comment).length,1500);
  assert.equal(body.clarity,'partly');
  assert.equal(body.submission_id,ids.submissionId);
  assert.equal(body.conversation_id,ids.conversationId);
  assert.equal(body.section,'clue2');
  assert.equal(body.language,'zh-TW');
  assert.equal(makeFeedbackRequest({...ids,clarity:'clear',comment:''}).comment,'');
});

test('URL section selection rejects unknown or markup-like hashes', () => {
  assert.equal(parseSection('#clue2', ['intro','clue2']), 'clue2');
  assert.equal(parseSection('#overview', ['intro','clue2']), 'overview');
  assert.equal(parseSection('#<script>', ['intro','clue2']), 'overview');
});

test('natural speech end advances once; explicit stop and language replacement never advance', async () => {
  let sequence;
  const calls = [];
  const chapters = [];
  const speech = {
    state:{status:'idle',id:null},
    stop() { this.state={status:'idle',id:null}; sequence?.onState(this.state); },
    play(id,text,language) {
      this.stop();
      calls.push({id,text,language});
      this.state={status:'preparing',id}; sequence.onState(this.state);
      this.state={status:'playing',id}; sequence.onState(this.state);
      return Promise.resolve(true);
    }
  };
  sequence = createTourSequence({speech,onChapter:chapter => chapters.push(chapter.sectionId)});
  sequence.start([{id:'intro',text:'Intro'},{id:'clue2',text:'Clue two'}], 'en');
  assert.deepEqual(chapters, ['intro']);
  speech.state={status:'idle',id:null}; sequence.onState(speech.state);
  assert.deepEqual(chapters, ['intro','clue2']);
  sequence.stop();
  assert.equal(sequence.active, null);
  assert.equal(calls.length, 2);
  sequence.start([{id:'intro',text:'中文'}], 'zh-TW');
  sequence.stop();
  assert.deepEqual(chapters, ['intro','clue2','intro']);
  assert.equal(calls.at(-1).language, 'zh-TW');
  await Promise.resolve();
  assert.equal(sequence.active, null);
});

test('prepared audio requires exact language/text hash; static failure never retries the API', async () => {
  const {webcrypto,createHash} = require('node:crypto');
  const requests = [];
  const text = 'An exact reviewed narration.';
  const prepared = await createPreparedSpeechFetch({
    fetch:async(url) => { requests.push(url); return new Response('unavailable',{status:503}); },
    crypto:webcrypto,
    data:{order:['intro'],sections:[{id:'intro',en:{narration:text}}]},
    manifest:{complete:true,items:[{id:'intro',language:'en',text_sha256:createHash('sha256').update(text).digest('hex'),url:'/assets/tour-preview/audio/en-intro.wav',duration_seconds:10}]},
  });
  assert.deepEqual(prepared.preparedLanguages,['en']);
  const response = await prepared.fetch('/api/speech',{method:'POST',body:JSON.stringify({language:'en',text})});
  assert.equal(response.status,503);
  assert.deepEqual(requests,['/assets/tour-preview/audio/en-intro.wav']);
  await prepared.fetch('/api/speech',{method:'POST',body:JSON.stringify({language:'en',text:text+' changed'})});
  assert.equal(requests.at(-1),'/api/speech');
});

test('browser natural pause-before-ended advances the active sequence but an explicit stop does not', () => {
  let sequence;
  const calls=[];
  const speech={state:{status:'idle',id:null},stop(){this.state={status:'idle',id:null};sequence?.onState(this.state);},play(id){this.stop();calls.push(id);this.state={status:'playing',id};sequence.onState(this.state);return Promise.resolve(true);}};
  sequence=createTourSequence({speech});
  sequence.start([{id:'intro',text:'First'},{id:'methods',text:'Second'}],'en');
  speech.state={status:'paused',id:calls[0]};sequence.onState(speech.state);
  assert.equal(calls.length,1,'pause alone must not advance');
  speech.state={status:'idle',id:null};sequence.onState(speech.state);
  assert.equal(calls.length,2,'natural paused → idle must advance');
  speech.state={status:'paused',id:calls[1]};sequence.onState(speech.state);
  sequence.stop();
  assert.equal(calls.length,2,'stop withdraws the run before its idle notification');
});

test('eight navigation sections retain the original six-clip prepared tour', async () => {
  const {webcrypto,createHash}=require('node:crypto');
  const tour=['intro','methods','clue1','clue2','clue3','discussion'];
  const order=[...tour,'references','supplementary'];
  const sections=order.map(id=>({id,en:{narration:'Reviewed '+id}}));
  const items=tour.map(id=>({id,language:'en',text_sha256:createHash('sha256').update('Reviewed '+id).digest('hex'),url:'/assets/tour-preview/audio/en-'+id+'.wav',duration_seconds:10}));
  const result=await createPreparedSpeechFetch({fetch:()=>{},crypto:webcrypto,data:{order,tour_order:tour,sections},manifest:{complete:true,items}});
  assert.deepEqual(result.preparedLanguages,['en']);
  assert.equal(result.durations.en,60);
});

let chromium;
try { ({chromium}=require('playwright')); } catch { /* Same optional dependency as the existing browser check. */ }

test('tour UI preserves URL/audio boundaries, pauses questions, ignores cleared replies and fits mobile DPRs',
  {skip:!chromium,timeout:60000}, async () => {
    const fs = require('node:fs/promises');
    const path = require('node:path');
    const project = path.join(__dirname,'..');
    const browser = await chromium.launch({channel:process.env.ORCHID_BROWSER_CHANNEL || (process.platform === 'win32' ? 'msedge' : undefined),headless:true,args:['--disable-gpu','--disable-background-networking']});
    try {
      const context = await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:3});
      await context.addInitScript(() => {
        sessionStorage.setItem('orchid-tour-welcome-seen','1');
        window.testAudio = [];
        window.Audio = class {
          constructor(src) { this.src=src; this.plays=0; this.pauses=0; window.testAudio.push(this); }
          play() { this.plays++; this.onplaying?.(); return Promise.resolve(); }
          pause() { this.pauses++; this.onpause?.(); }
          removeAttribute() { this.src=''; }
          load() {}
        };
      });
      let releaseChat;
      let finishChat;
      let notifyChat;
      const chatStarted = new Promise(resolve => { notifyChat=resolve; });
      const chatFinished = new Promise(resolve => { finishChat=resolve; });
      const speechBodies = [];
      let chatRequests = 0;
      const routeHandler = async route => {
        const url = new URL(route.request().url());
        const prefix=process.env.ORCHID_TEST_PREFIX || '';
        assert.ok(url.pathname.startsWith(prefix+'/'),`escaped prefix: ${url.pathname}`);
        url.pathname=url.pathname.slice(prefix.length);
        if (url.pathname === '/api/health') return route.fulfill({json:{model:{ready:true},index:{ready:true},speech:{ready:true,languages:['en','zh-TW']}}});
        if (url.pathname === '/assets/tour-preview/audio/manifest.json') return route.fulfill({json:{complete:false,items:[]}});
        if (url.pathname === '/api/speech') { speechBodies.push(route.request().postDataJSON()); return route.fulfill({contentType:'audio/wav',body:Buffer.from('mock audio; no TTS model is called')}); }
        if (url.pathname.startsWith('/api/sources/')) return route.fulfill({json:{id:'P01',title:'Research question and scope',document_title:'Full research paper',original_excerpt:'A fixture original excerpt.',text:'已校對摘要fixture',section:'Abstract',kind:'Reviewed summary',url:'/api/documents/paper',local_url:'/api/documents/paper',locators:[]}});
        if (url.pathname === '/api/chat') {
          chatRequests++;
          await new Promise(resolve => { releaseChat=resolve; notifyChat(); });
          try { await route.fulfill({json:{status:'answered',answer:'A late answer that must stay cleared.',citations:[]}}); } catch { /* The clear operation intentionally aborted this request. */ }
          finishChat(); return;
        }
        let file;
        if (url.pathname.startsWith('/tour-preview/')) file=path.join(project,'orchid','static',url.pathname.endsWith('/')?'tour-preview/index.html':url.pathname.slice(1));
        else if (['/speech.js','/urls.js'].includes(url.pathname)) file=path.join(project,'orchid','static',url.pathname.slice(1));
        else if (url.pathname.startsWith('/assets/tour-preview/')) file=path.join(project,'.orchid',url.pathname.slice(1));
        if (!file) return route.fulfill({status:404});
        const contentType=file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':file.endsWith('.webp')?'image/webp':file.endsWith('.png')?'image/png':'text/html';
        return route.fulfill({body:await fs.readFile(file),contentType,headers:{'Content-Security-Policy':"default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self'; script-src 'self'"}});
      };
      await context.route('**/*',routeHandler);
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror',error => errors.push(error.message));
      await page.goto(`https://orchid.test${process.env.ORCHID_TEST_PREFIX || ''}/tour-preview/`);
      await page.locator('#play-guide:not([disabled])').waitFor();
      assert.equal(await page.locator('#menu-toggle').count(),1,'the guide needs one visible Menu disclosure');
      const titleCenter=await page.locator('#view-title').evaluate(el=>{const box=el.getBoundingClientRect();return box.y+box.height/2;});
      const menuCenter=await page.locator('#menu-toggle').evaluate(el=>{const box=el.getBoundingClientRect();return box.y+box.height/2;});
      assert.ok(Math.abs(titleCenter-menuCenter)<.6,'the dynamic title and Menu must share their vertical center');
      assert.equal(await page.locator('html').getAttribute('lang'),'en');
      assert.equal(await page.locator('#poster-hotspots button').count(),8);
      assert.equal(await page.locator('.narration-chapter').count(),6);
      assert.equal(await page.locator('.narration-chapter p:not(.chapter-location)').first().evaluate(el => getComputedStyle(el).fontSize),'18px');
      assert.equal(await page.locator('#read-along').evaluate(el => getComputedStyle(el).textDecorationLine),'none');
      await page.locator('.source-list summary').first().click();
      assert.ok((await page.locator('.source-list .source-name').first().textContent()).length > 5);
      await page.locator('.source-list [data-source]').first().click();
      await page.locator('#source-content .link-button').first().waitFor();
      await page.keyboard.press('Escape');
      await page.locator('#play-guide').click();
      await page.waitForFunction(() => document.querySelector('#play-guide').textContent === 'Pause');
      await page.locator('#quick-question').click();
      assert.match(await page.locator('#audio-status').textContent(),/Paused/);
      await page.locator('[data-close="question-dialog"]').click();
      assert.equal(await page.locator('#play-guide').textContent(),'Resume','closing questions must not automatically resume audio');
      await page.locator('#play-guide').click();
      await page.evaluate(() => window.testAudio.at(-1).onended());
      await page.waitForFunction(() => document.querySelector('#listening-location').textContent.includes('METHODS'));
      assert.equal(await page.locator('#view-title').textContent(),'Entire poster tour','audio chapters must not auto-zoom');
      await page.locator('[data-section="clue2"]').click();
      await page.waitForURL('**/#clue2');
      await page.waitForFunction(() => document.querySelector('#view-title').textContent.includes('Clue 2'));
      assert.match(await page.locator('#view-title').textContent(),/Clue 2/);
      assert.match(await page.locator('#poster-image').getAttribute('srcset'),/clue2-2400/);
      assert.ok(await page.locator('.detail-heading').count());
      assert.ok(await page.locator('.narration-chapter > p:not(.chapter-location)').count() >= 3,'section details must remain separate readable paragraphs');
      assert.equal(await page.locator('#play-guide').textContent(),'Play section');
      assert.ok(await page.evaluate(() => window.testAudio.every(audio => audio.pauses > 0)));
      await page.locator('#back-overview').click();
      await page.waitForURL('**/#overview');
      await page.waitForFunction(() => document.querySelector('#view-title').textContent === 'Entire poster tour');
      for (const id of ['references','supplementary']) {
        await page.locator(`#section-links a[href="#${id}"]`).click();
        await page.waitForFunction(value => location.hash === '#'+value && document.querySelector('#poster-image').getAttribute('srcset').includes(value+'-2400'),id);
        assert.equal(await page.locator('.poster-sources a[href$="/api/documents/poster#page=1"]').count(),1);
        assert.equal(await page.locator('.poster-sources a[href*="media.springernature.com"]').count(),1);
        assert.match(await page.locator('.source-list summary').textContent(),/Related sources/);
        await page.locator('#quick-question').click();
        assert.match(await page.locator('#chat-context').textContent(),id === 'references' ? /References/ : /Poster supplement/);
        await page.locator('[data-close="question-dialog"]').click();
        if (id === 'supplementary') {
          await page.setViewportSize({width:320,height:844});
          assert.ok(await page.locator('#view-title').evaluate(el => el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight) <= 2.1),'the supplementary title must fit at most two lines at 320px');
          await page.setViewportSize({width:390,height:844});
        }
        await page.locator('#back-overview').click();
        await page.waitForFunction(() => location.hash === '#overview' && document.querySelector('#view-title').textContent === 'Entire poster tour');
      }
      await page.locator('#menu-toggle').click();
      await page.locator('#site-menu [data-language="zh-TW"]').click();
      assert.equal(await page.locator('html').getAttribute('lang'),'zh-Hant-TW');
      await page.locator('#text-size').click();
      await page.locator('#text-size').click();
      assert.equal(await page.locator('.narration-chapter p:not(.chapter-location)').first().evaluate(el => getComputedStyle(el).fontSize),'22px');
      await page.locator('#quick-question').click();
      await page.locator('#question').fill('花'.repeat(600));
      assert.equal(await page.locator('#send-question').isDisabled(),true);
      await page.locator('#question').fill('模型能解釋什麼？');
      await page.locator('#send-question').click();
      await page.waitForFunction(() => document.querySelector('#send-question').disabled);
      await chatStarted;
      await page.locator('#clear-chat').click();
      releaseChat(); await chatFinished;
      assert.equal(await page.locator('#messages').textContent(),'');
      await page.evaluate(() => {
        const schedule = window.setTimeout.bind(window);
        window.setTimeout = (callback,delay,...args) => schedule(callback,delay === 80000 ? 30 : delay,...args);
      });
      await page.locator('#question').fill('這次等待會逾時嗎？');
      await page.locator('#send-question').click();
      await page.locator('#chat-error:not([hidden])').waitFor();
      assert.match(await page.locator('#chat-error').textContent(),/80/);
      assert.equal(await page.locator('#send-question').isDisabled(),false);
      assert.equal(chatRequests,2,'a timeout must not retry automatically');
      releaseChat();
      await page.locator('[data-close="question-dialog"]').click();
      for (const width of [320,360,390,430,1280]) {
        await page.setViewportSize({width,height:844});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth),false,`overflow at width ${width}`);
        const header=await page.evaluate(()=>{const title=document.querySelector('#view-title').getBoundingClientRect(),menu=document.querySelector('#menu-toggle').getBoundingClientRect();return {centerGap:Math.abs(title.y+title.height/2-menu.y-menu.height/2),menuHeight:menu.height};});
        assert.ok(header.centerGap<.6 && header.menuHeight>=48,'title and 48px Menu remain centered at each width');
        const geometry = await page.evaluate(() => {
          const buttons=[...document.querySelectorAll('#poster-hotspots button')].map(el=>({id:el.dataset.section,rect:el.getBoundingClientRect().toJSON()}));
          const overlaps=[];
          for(let i=0;i<buttons.length;i++)for(let j=i+1;j<buttons.length;j++){const a=buttons[i].rect,b=buttons[j].rect;if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>.5&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>.5)overlaps.push([buttons[i].id,buttons[j].id]);}
          return {overlaps,tooSmall:buttons.filter(b=>b.id!=='references'&&(b.rect.height<43.5||b.rect.width<43.5)),navigationMin:Math.min(...[...document.querySelectorAll('#section-links a')].map(el=>el.getBoundingClientRect().height))};
        });
        assert.deepEqual(geometry.overlaps,[],`map regions overlap at ${width}`);
        assert.deepEqual(geometry.tooSmall,[],`only the source-sized Reference map control has a documented size exception at ${width}`);
        assert.ok(geometry.navigationMin>=44,'all eight external section controls must provide 44px targets');
        const shortcuts=await page.locator('.audio-shortcuts').evaluate(el=>[...el.children].map(child=>child.getBoundingClientRect().height));
        assert.ok(shortcuts.every(height=>height>=44) && Math.abs(shortcuts[0]-shortcuts[1])<.5,'reading and question shortcuts must have matching touch heights');
      }
      for (const dpr of [1,2]) {
        const other = await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:dpr});
        await other.route('**/*',routeHandler);
        await other.addInitScript(() => sessionStorage.setItem('orchid-tour-welcome-seen','1'));
        const otherPage = await other.newPage();
        await otherPage.goto(`https://orchid.test${process.env.ORCHID_TEST_PREFIX || ''}/tour-preview/`);
        await otherPage.locator('#play-guide:not([disabled])').waitFor();
        assert.equal(await otherPage.evaluate(() => devicePixelRatio),dpr);
        for (const width of [320,360,390,430]) {
          await otherPage.setViewportSize({width,height:844});
          assert.equal(await otherPage.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth),false,`overflow at DPR ${dpr}, width ${width}`);
        }
        await other.close();
      }
      assert.ok(speechBodies.length >= 2);
      assert.deepEqual(errors,[]);
      await context.close();
    } finally { await browser.close(); }
  });


test('first-use guidance and feedback are bilingual, accessible on phones and save only on confirmed receipts',
  {skip:!chromium,timeout:60000}, async () => {
    const fs=require('node:fs/promises');
    const path=require('node:path');
    const project=path.join(__dirname,'..');
    const browser=await chromium.launch({channel:process.env.ORCHID_BROWSER_CHANNEL || (process.platform==='win32'?'msedge':undefined),headless:true,args:['--disable-gpu','--disable-background-networking']});
    try {
      const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:2});
      await context.addInitScript(()=>{
        window.testAudio=[];
        window.Audio=class {
          constructor(){window.testAudio.push(this);} play(){this.onplaying?.();return Promise.resolve();}
          pause(){this.onpause?.();} removeAttribute(){} load(){}
        };
      });
      const feedbackBodies=[],chatBodies=[];
      let releaseFailure;
      await context.route('**/*',async route=>{
        const url=new URL(route.request().url());
        const prefix=process.env.ORCHID_TEST_PREFIX || '';
        assert.ok(url.pathname.startsWith(prefix+'/'),`escaped prefix: ${url.pathname}`);
        url.pathname=url.pathname.slice(prefix.length);
        if(url.pathname==='/api/health')return route.fulfill({json:{model:{ready:true},index:{ready:true},speech:{ready:true,languages:['en','zh-TW']}}});
        if(url.pathname==='/assets/tour-preview/audio/manifest.json')return route.fulfill({json:{complete:false,items:[]}});
        if(url.pathname==='/api/speech')return route.fulfill({contentType:'audio/wav',body:Buffer.from('fixture; no TTS')});
        if(url.pathname==='/api/feedback'){
          const body=route.request().postDataJSON();feedbackBodies.push(body);
          if(feedbackBodies.length===1){await new Promise(resolve=>{releaseFailure=resolve;});return route.fulfill({status:503,json:{detail:{code:'recording_unavailable'}}});}
          return route.fulfill({status:201,json:{status:'saved',id:body.submission_id,created_at:'2026-11-01T00:00:00Z'}});
        }
        if(url.pathname==='/api/chat'){const body=route.request().postDataJSON();chatBodies.push(body);return chatBodies.length<=2 ? route.fulfill({status:503,json:{detail:{code:'recording_unavailable'}}}) : route.fulfill({json:{status:'answered',answer:'A fixture answer.',citations:[],request_id:body.request_id,record_saved:true}});}
        let file;
        if(url.pathname.startsWith('/tour-preview/'))file=path.join(project,'orchid','static',url.pathname.endsWith('/')?'tour-preview/index.html':url.pathname.slice(1));
        else if(['/speech.js','/urls.js'].includes(url.pathname))file=path.join(project,'orchid','static',url.pathname.slice(1));
        else if(url.pathname.startsWith('/assets/tour-preview/'))file=path.join(project,'.orchid',url.pathname.slice(1));
        if(!file)return route.fulfill({status:404});
        const contentType=file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':file.endsWith('.webp')?'image/webp':file.endsWith('.png')?'image/png':'text/html';
        return route.fulfill({body:await fs.readFile(file),contentType,headers:{'Content-Security-Policy':"default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self'; script-src 'self'"}});
      });
      const page=await context.newPage();
      const errors=[];page.on('pageerror',error=>errors.push(error.message));
      await page.goto(`https://orchid.test${process.env.ORCHID_TEST_PREFIX || ''}/tour-preview/`);
      await page.locator('#welcome-dialog[open]').waitFor();
      assert.equal(await page.locator('html').getAttribute('lang'),'en');
      assert.match(await page.locator('#welcome-dialog .recording-notice').textContent(),/saved locally/);
      assert.equal(await page.evaluate(()=>window.testAudio.length),0,'onboarding must not autoplay');
      for(const width of [320,360,390,430]){
        await page.setViewportSize({width,height:844});
        const dimensions=await page.locator('#welcome-dialog').evaluate(el=>({rect:el.getBoundingClientRect().toJSON(),overflow:el.scrollWidth>el.clientWidth,targets:[...el.querySelectorAll('button')].map(b=>b.getBoundingClientRect().height)}));
        assert.ok(dimensions.rect.left>=0 && dimensions.rect.right<=width);
        assert.equal(dimensions.overflow,false);
        assert.ok(dimensions.targets.every(height=>height>=44));
      }
      await page.setViewportSize({width:390,height:844});
      await page.screenshot({path:path.join(project,'output','tour-onboarding-en.png')});
      await page.locator('#welcome-dialog [data-language="zh-TW"]').click();
      assert.equal(await page.locator('html').getAttribute('lang'),'zh-Hant-TW');
      assert.match(await page.locator('#welcome-title').textContent(),/開始/);
      await page.locator('#start-exploring').click();
      assert.equal(await page.evaluate(()=>sessionStorage.getItem('orchid-tour-welcome-seen')),'1');
      await page.reload();await page.locator('#play-guide:not([disabled])').waitFor();
      assert.equal(await page.locator('#welcome-dialog').evaluate(el=>el.open),false);
      assert.equal(await page.locator('#site-menu').isVisible(),false);
      const headingBefore=await page.locator('#view-title').boundingBox();
      await page.locator('#menu-toggle').click();
      assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'),'true');
      assert.deepEqual(await page.locator('#view-title').boundingBox(),headingBefore,'the popover must not move the title');
      await page.keyboard.press('Escape');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'menu-toggle');
      await page.locator('#menu-toggle').click();
      await page.mouse.click(2,700);
      assert.equal(await page.locator('#site-menu').isVisible(),false,'a click outside closes Menu');
      await page.locator('#menu-toggle').click();
      await page.locator('#open-feedback').focus();
      await page.keyboard.press('Tab');
      assert.equal(await page.locator('#site-menu').isVisible(),false,'Tab out closes without trapping focus');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'text-size');
      await page.locator('#menu-toggle').click();
      await page.locator('#how-to-use').click();
      assert.equal(await page.locator('#site-menu').isVisible(),false);
      await page.keyboard.press('Escape');
      await page.waitForFunction(()=>document.activeElement.id==='menu-toggle');
      assert.equal(await page.locator('#welcome-dialog').evaluate(el=>el.open),false);
      await page.locator('#play-guide').click();
      await page.locator('#menu-toggle').click();
      await page.locator('#open-feedback').click();
      assert.match(await page.locator('#audio-status').textContent(),/暫停/);
      assert.match(await page.locator('#feedback-dialog .recording-notice').textContent(),/本機/);
      assert.equal(await page.locator('#submit-feedback').isDisabled(),true);
      await page.locator('#feedback-comment').fill('希望更容易理解模擬和實驗的差別。');
      await page.locator('label[for="clarity-partly"]').click();
      await page.evaluate(()=>{document.querySelector('#feedback-form').requestSubmit();document.querySelector('#feedback-form').requestSubmit();});
      await page.waitForFunction(()=>document.querySelector('#submit-feedback').disabled);
      await page.waitForFunction(()=>document.querySelector('#feedback-status').textContent.includes('儲存'));
      assert.equal(feedbackBodies.length,1,'pending must prevent duplicate feedback requests');
      assert.match(feedbackBodies[0].submission_id,/^[0-9a-f-]{36}$/i);
      assert.match(feedbackBodies[0].conversation_id,/^[0-9a-f-]{36}$/i);
      assert.equal(feedbackBodies[0].language,'zh-TW');
      assert.equal(feedbackBodies[0].section,'overview');
      await page.locator('[data-close="feedback-dialog"]').click();
      await page.waitForFunction(()=>document.activeElement.id==='menu-toggle');
      releaseFailure();
      await page.locator('#menu-toggle').click();
      await page.locator('#open-feedback').click();
      await page.locator('#feedback-error:not([hidden])').waitFor();
      assert.match(await page.locator('#feedback-error').textContent(),/儲存/);
      assert.equal(await page.locator('#feedback-comment').inputValue(),'希望更容易理解模擬和實驗的差別。');
      assert.equal(await page.locator('#clarity-partly').isChecked(),true);
      assert.equal(feedbackBodies.length,1,'failure must not retry automatically');
      for(const width of [320,360,390,430]){
        await page.setViewportSize({width,height:844});
        assert.equal(await page.locator('#feedback-dialog').evaluate(el=>el.scrollWidth>el.clientWidth),false);
        const targets=await page.locator('.clarity-options label').evaluateAll(labels=>labels.map(el=>el.getBoundingClientRect().height));
        assert.ok(targets.every(height=>height>=44));
      }
      await page.setViewportSize({width:390,height:844});
      await page.screenshot({path:path.join(project,'output','tour-feedback-zh.png')});
      await page.locator('#submit-feedback').scrollIntoViewIfNeeded();
      const saveButton=await page.locator('#submit-feedback').boundingBox();
      assert.ok(saveButton.y>=0 && saveButton.y+saveButton.height<=844,'the bottom save control must be reachable within the phone viewport');
      await page.locator('#submit-feedback').click();
      await page.waitForFunction(()=>document.querySelector('#feedback-status').textContent.includes('謝謝'));
      assert.equal(feedbackBodies.length,2);
      assert.equal(feedbackBodies[0].submission_id,feedbackBodies[1].submission_id,'an explicit unchanged retry must reuse the id');
      assert.equal(await page.locator('#feedback-comment').inputValue(),'');
      assert.equal(await page.locator('#clarity-partly').isChecked(),false);
      await page.locator('#feedback-comment').fill('保留這段繁體中文草稿');
      await page.locator('[data-close="feedback-dialog"]').click();
      assert.equal(await page.locator('#play-guide').textContent(),'繼續播放','closing feedback must keep audio paused');
      await page.locator('#menu-toggle').click();
      await page.locator('#site-menu [data-language="en"]').click();
      await page.locator('#reading-feedback').click();
      assert.equal(await page.locator('#feedback-comment').inputValue(),'保留這段繁體中文草稿','language changes must preserve the original draft');
      await page.locator('#submit-feedback').click();
      await page.waitForFunction(()=>document.querySelector('#feedback-status').textContent.includes('Thank'));
      assert.notEqual(feedbackBodies[2].submission_id,feedbackBodies[1].submission_id);
      await page.locator('[data-close="feedback-dialog"]').click();
      await page.locator('#quick-question').click();
      assert.match(await page.locator('#question-dialog .recording-notice').textContent(),/saved locally/);
      await page.locator('#question').fill('What is simulated?');await page.locator('#send-question').click();
      await page.locator('#chat-error:not([hidden])').waitFor();
      assert.match(await page.locator('#chat-error').textContent(),/saving is unavailable/i);
      assert.equal(chatBodies.length,1);
      assert.match(chatBodies[0].request_id,/^[0-9a-f-]{36}$/i);
      assert.equal(chatBodies[0].section,'overview');
      await page.locator('#clear-chat').click();
      assert.match(await page.locator('#chat-status').textContent(),/saved records/i);
      await page.locator('#question').fill('What is simulated?');await page.locator('#send-question').click();
      await page.waitForFunction(()=>!document.querySelector('#send-question').disabled);
      assert.equal(chatBodies.length,2);
      assert.notEqual(chatBodies[1].request_id,chatBodies[0].request_id);
      assert.notEqual(chatBodies[1].conversation_id,chatBodies[0].conversation_id);
      await page.locator('[data-close="question-dialog"]').click();
      await page.locator('#section-links a[href="#clue2"]').click();
      await page.waitForFunction(()=>location.hash==='#clue2' && document.querySelector('#view-title').textContent.includes('Clue 2'));
      await page.locator('#quick-question').click();
      await page.locator('#question').fill('Which changes produce fusion?');await page.locator('#send-question').click();
      await page.waitForFunction(()=>document.querySelector('#chat-status').textContent.includes('saved locally'));
      assert.equal(chatBodies[2].section,'clue2');
      assert.notEqual(chatBodies[2].conversation_id,chatBodies[1].conversation_id,'selecting a section must begin a new conversation');
      await page.locator('[data-close="question-dialog"]').click();
      await page.locator('#menu-toggle').click();
      await page.locator('#site-menu [data-language="zh-TW"]').click();
      await page.locator('#quick-question').click();
      await page.locator('#question').fill('哪些變化能產生融合？');await page.locator('#send-question').click();
      await page.waitForFunction(()=>document.querySelector('#chat-status').textContent.includes('已保存在本機'));
      assert.equal(chatBodies[3].language,'zh-TW');
      assert.notEqual(chatBodies[3].conversation_id,chatBodies[2].conversation_id,'language changes must begin a new conversation');
      assert.deepEqual(errors,[]);
      await context.close();
    }finally{await browser.close();}
  });


test('help screenshots match the language, enlarge without completing welcome and fail without blocking Start',
  {skip:!chromium,timeout:60000}, async()=>{
    const fs=require('node:fs/promises'),path=require('node:path');
    const project=path.join(__dirname,'..');
    const browser=await chromium.launch({channel:process.env.ORCHID_BROWSER_CHANNEL || (process.platform==='win32'?'msedge':undefined),headless:true,args:['--disable-gpu','--disable-background-networking']});
    try{
      const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:2});
      const writes=[];
      await context.route('**/*',async route=>{
        const request=route.request(),url=new URL(request.url());
        const prefix=process.env.ORCHID_TEST_PREFIX || '';
        assert.ok(url.pathname.startsWith(prefix+'/'),`escaped prefix: ${url.pathname}`);
        url.pathname=url.pathname.slice(prefix.length);
        if(request.method()!=='GET'){writes.push(url.pathname);return route.fulfill({status:405});}
        if(url.pathname==='/api/health')return route.fulfill({json:{model:{ready:false},index:{ready:true},speech:{ready:false,languages:[]}}});
        if(url.pathname==='/assets/tour-preview/audio/manifest.json')return route.fulfill({json:{complete:false,items:[]}});
        let file;
        if(url.pathname.startsWith('/tour-preview/'))file=path.join(project,'orchid','static',url.pathname.endsWith('/')?'tour-preview/index.html':url.pathname.slice(1));
        else if(['/speech.js','/urls.js'].includes(url.pathname))file=path.join(project,'orchid','static',url.pathname.slice(1));
        else if(url.pathname.startsWith('/assets/tour-preview/'))file=path.join(project,'.orchid',url.pathname.slice(1));
        if(!file)return route.fulfill({status:404});
        const type=file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':file.endsWith('.png')?'image/png':file.endsWith('.webp')?'image/webp':'text/html';
        return route.fulfill({contentType:type,body:await fs.readFile(file),headers:{'Content-Security-Policy':"default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self'; script-src 'self'"}});
      });
      const page=await context.newPage(),errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      await page.goto(`https://orchid.test${process.env.ORCHID_TEST_PREFIX || ''}/tour-preview/`);await page.locator('#welcome-dialog[open]').waitFor();
      assert.equal(await page.locator('[data-help-image]').count(),3);
      for(const language of ['en','zh-TW']){
        await page.locator(`#welcome-dialog [data-language="${language}"]`).click();
        for(const kind of ['guide','question','feedback']){
          const preview=page.locator(`[data-help-image="${kind}"]`);
          await preview.scrollIntoViewIfNeeded();
          await preview.locator('img').evaluate(img=>img.decode());
          assert.ok((await preview.locator('img').getAttribute('src')).endsWith('/'+language+'-'+kind+'.png'));
          await preview.click();await page.locator('#help-image-dialog[open]').waitFor();
          assert.equal(await page.locator('#welcome-dialog').evaluate(el=>el.open),true);
          assert.equal(await page.evaluate(()=>sessionStorage.getItem('orchid-tour-welcome-seen')),null);
          assert.ok((await page.locator('#help-full-image').getAttribute('src')).endsWith('/'+language+'-'+kind+'.png'));
          await page.locator('#help-image-scale').click();
          assert.ok(await page.locator('#help-full-image').evaluate(el=>parseFloat(el.style.width)>=el.naturalWidth));
          if(kind==='guide')await page.keyboard.press('Escape');else await page.locator('[data-close="help-image-dialog"]').click();
          await page.waitForFunction(()=>!document.querySelector('#help-image-dialog').open);
          assert.equal(await page.evaluate(kind=>document.activeElement?.dataset.helpImage===kind,kind),true,'closing the image must restore the matching preview focus');
          assert.equal(await page.evaluate(()=>sessionStorage.getItem('orchid-tour-welcome-seen')),null,'image close must not finish onboarding');
        }
        for(const width of [320,390,430,1280]){
          await page.setViewportSize({width,height:844});
          for(const end of [0,1]){
            await page.locator('.welcome-scroll').evaluate((el,end)=>{el.scrollTop=end ? el.scrollHeight : 0;},end);
            const start=await page.locator('#start-exploring').boundingBox();
            assert.ok(start.y>=0 && start.y+start.height<=844,'Start stays visible while help content scrolls');
          }
          assert.equal(await page.locator('#welcome-dialog').evaluate(el=>el.scrollWidth>el.clientWidth),false);
          const buttons=await page.locator('#welcome-dialog .language-switch').evaluate(el=>({gap:parseFloat(getComputedStyle(el).gap),buttons:[...el.children].map(button=>({height:button.getBoundingClientRect().height,border:getComputedStyle(button).borderTopWidth,radius:getComputedStyle(button).borderRadius}))}));
          assert.equal(buttons.gap,8);
          assert.ok(buttons.buttons.every(button=>button.height>=44 && button.border==='2px' && button.radius==='6px'));
        }
        await page.setViewportSize({width:390,height:844});
        await page.locator('.welcome-scroll').evaluate(el=>{el.scrollTop=0;});
        await page.screenshot({path:path.join(project,'output',`tour-help-welcome-${language}.png`)});
      }
      await page.setViewportSize({width:1280,height:900});
      await page.screenshot({path:path.join(project,'output','tour-help-desktop.png')});
      await page.route('**/assets/tour-preview/help/*.png',route=>route.fulfill({status:404}));
      await page.reload();await page.locator('#welcome-dialog[open]').waitFor();
      for(const kind of ['guide','question','feedback']){
        await page.locator(`[data-help-image="${kind}"]`).scrollIntoViewIfNeeded();
        await page.locator(`[data-help-fallback="${kind}"]:not([hidden])`).waitFor();
      }
      assert.match(await page.locator('[data-i18n="welcomeExploreBody"]').textContent(),/播放完整導覽/);
      await page.locator('#start-exploring').click();
      assert.equal(await page.locator('#welcome-dialog').evaluate(el=>el.open),false);
      assert.equal(await page.evaluate(()=>sessionStorage.getItem('orchid-tour-welcome-seen')),'1');
      await page.locator('#menu-toggle').click();
      for(const width of [320,390,430,1280]){
        await page.setViewportSize({width,height:844});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth),false);
        const controls=await page.locator('#site-menu .language-switch button').evaluateAll(buttons=>buttons.map(button=>({width:button.getBoundingClientRect().width,height:button.getBoundingClientRect().height,border:getComputedStyle(button).borderTopWidth})));
        assert.ok(controls.every(button=>button.width>=44 && button.height>=44 && button.border==='2px'));
      }
      assert.deepEqual(writes,[],'help images must never play audio or send visitor content');
      assert.deepEqual(errors,[]);
      await context.close();
    }finally{await browser.close();}
  });

test('prepared tour WAV and document links stay inside the application prefix',
  {skip:!chromium,timeout:30000},async()=>{
    const fs=require('node:fs/promises'),path=require('node:path');
    const project=path.join(__dirname,'..'),prefix=process.env.ORCHID_TEST_PREFIX || '';
    const browser=await chromium.launch({channel:process.env.ORCHID_BROWSER_CHANNEL || (process.platform==='win32'?'msedge':undefined),headless:true,args:['--disable-gpu','--disable-background-networking']});
    try {
      const context=await browser.newContext({viewport:{width:390,height:844}});
      await context.addInitScript(()=>{
        sessionStorage.setItem('orchid-tour-welcome-seen','1');
        window.Audio=class {play(){this.onplaying?.();return Promise.resolve();}pause(){}removeAttribute(){}load(){}};
      });
      const requests=[],errors=[];
      await context.route('**/*',async route=>{
        const request=route.request(),url=new URL(request.url());
        requests.push({path:url.pathname,method:request.method()});
        assert.ok(url.pathname.startsWith(prefix+'/'),`escaped prefix: ${url.pathname}`);
        url.pathname=url.pathname.slice(prefix.length);
        if(url.pathname==='/api/health')return route.fulfill({json:{model:{ready:false},index:{ready:true},speech:{ready:true,languages:['en','zh-TW']}}});
        if(url.pathname.endsWith('.wav'))return route.fulfill({contentType:'audio/wav',body:Buffer.from('prepared fixture; no TTS')});
        let file;
        if(url.pathname.startsWith('/tour-preview/'))file=path.join(project,'orchid','static',url.pathname.endsWith('/')?'tour-preview/index.html':url.pathname.slice(1));
        else if(['/speech.js','/urls.js'].includes(url.pathname))file=path.join(project,'orchid','static',url.pathname.slice(1));
        else if(url.pathname.startsWith('/assets/tour-preview/'))file=path.join(project,'.orchid',url.pathname.slice(1));
        if(!file)return route.fulfill({status:404});
        const type=file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':file.endsWith('.png')?'image/png':file.endsWith('.webp')?'image/webp':'text/html';
        return route.fulfill({contentType:type,body:await fs.readFile(file)});
      });
      const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
      await page.goto(`https://orchid.test${prefix}/tour-preview/`);
      await page.locator('#play-guide:not([disabled])').waitFor();
      await page.locator('#play-guide').click();
      await page.waitForFunction(()=>document.querySelector('#play-guide').textContent==='Pause');
      assert.ok(requests.some(request=>request.method==='GET' && request.path.startsWith(prefix+'/assets/tour-preview/audio/') && request.path.endsWith('.wav')));
      assert.ok(!requests.some(request=>request.method==='POST'),'prepared narration must never call TTS');
      await page.locator('[data-section="references"]').click();
      await page.waitForURL('**/#references');
      await page.locator('a[href*="/api/documents/"]').first().waitFor();
      const links=await page.locator('a[href*="/api/documents/"]').evaluateAll(items=>items.map(item=>item.href));
      assert.ok(links.some(link=>link.includes(prefix+'/api/documents/poster')));
      assert.ok(links.every(link=>new URL(link,'https://orchid.test').pathname.startsWith(prefix+'/api/documents/')));
      assert.deepEqual(errors,[]);
      await context.close();
    } finally { await browser.close(); }
  });
