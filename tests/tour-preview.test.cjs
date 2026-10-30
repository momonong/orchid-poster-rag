const {test} = require('node:test');
const assert = require('node:assert/strict');
const {makeChatRequest, parseSection, createTourSequence, createPreparedSpeechFetch} = require('../orchid/static/tour-preview/tour.js');

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
        else if (url.pathname === '/speech.js') file=path.join(project,'orchid','static','speech.js');
        else if (url.pathname.startsWith('/assets/tour-preview/')) file=path.join(project,'.orchid',url.pathname.slice(1));
        if (!file) return route.fulfill({status:404});
        const contentType=file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':file.endsWith('.webp')?'image/webp':'text/html';
        return route.fulfill({body:await fs.readFile(file),contentType,headers:{'Content-Security-Policy':"default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self'; script-src 'self'"}});
      };
      await context.route('**/*',routeHandler);
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror',error => errors.push(error.message));
      await page.goto('https://orchid.test/tour-preview/');
      await page.locator('#play-guide:not([disabled])').waitFor();
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
      await page.locator('[data-language="zh-TW"]').click();
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
        const otherPage = await other.newPage();
        await otherPage.goto('https://orchid.test/tour-preview/');
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
