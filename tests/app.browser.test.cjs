const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
let chromium;
try { ({chromium}=require('playwright')); } catch { /* Optional browser-test dependency. */ }

test('mobile playback exposes the introduction and preserves Chinese preferences for old English answers',
  {skip:!chromium}, async()=>{
    const channel=process.env.ORCHID_BROWSER_CHANNEL || (process.platform==='win32'?'msedge':undefined);
    const browser=await chromium.launch({channel,headless:true});
    try {
      const page=await browser.newPage();
      await page.setViewportSize({width:390,height:844});
      const root=path.join(__dirname,'..');
      await page.addInitScript(()=>{
        const setItem=Storage.prototype.setItem;
        window.languageWrites=[];
        Storage.prototype.setItem=function(key,value) {
          if(key==='orchid-language') window.languageWrites.push(value);
          return setItem.call(this,key,value);
        };
      });
      await page.route('**/*',async route=>{
        const url=new URL(route.request().url());
        const file=url.pathname==='/'?'index.html':url.pathname.slice(1);
        if(['index.html','style.css','locale.js','speech.js','app.js'].includes(file)) {
          const type=file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html';
          return route.fulfill({contentType:type,body:await fs.readFile(path.join(root,'orchid','static',file))});
        }
        if(url.pathname==='/api/guide') {
          const file=url.searchParams.get('language')==='zh-TW'?'guide.json':'guide.en.json';
          return route.fulfill({contentType:'application/json',body:await fs.readFile(path.join(root,'data',file))});
        }
        if(url.pathname==='/api/health') return route.fulfill({json:{
          index:{ready:true},model:{ready:true},speech:{ready:true,languages:['en','zh-TW']},
        }});
        if(url.pathname==='/api/chat') return route.fulfill({json:{
          status:'answered',answer:'The model explores orchid patterns. [S04]',citations:[],poster_sections:[],
        }});
        if(url.pathname==='/api/speech') {
          // A short valid silent WAV exercises the audio request without a TTS model.
          const wav=Buffer.alloc(1004);
          wav.write('RIFF'); wav.writeUInt32LE(996,4); wav.write('WAVEfmt ',8);
          wav.writeUInt32LE(16,16); wav.writeUInt16LE(1,20); wav.writeUInt16LE(1,22);
          wav.writeUInt32LE(24000,24); wav.writeUInt32LE(48000,28); wav.writeUInt16LE(2,32);
          wav.writeUInt16LE(16,34); wav.write('data',36); wav.writeUInt32LE(960,40);
          return route.fulfill({contentType:'audio/wav',body:wav});
        }
        return route.fulfill({status:204});
      });
      await page.goto('https://orchid.test/');
      await page.locator('#play-intro:not([disabled])').waitFor();
      assert.equal(await page.locator('#play-intro').count(),1);
      const intro=await page.locator('#play-intro').boundingBox();
      assert.ok(intro.y>=0 && intro.y+intro.height<=844,'introduction playback must be visible before scrolling');
      await page.locator('#question').fill('What does the model explore?');
      await page.locator('#send').click();
      const answer=page.locator('[data-play="answer"][data-language="en"]');
      await answer.waitFor();
      await page.locator('.language-switch [data-language="zh-TW"]').click();
      assert.equal(await page.locator('html').getAttribute('lang'),'zh-Hant-TW');
      const requested=page.waitForRequest(request=>new URL(request.url()).pathname==='/api/speech');
      await answer.click();
      assert.deepEqual((await requested).postDataJSON(),{
        language:'en',text:'The model explores orchid patterns. [S04]',
      });
      assert.equal(await page.locator('html').getAttribute('lang'),'zh-Hant-TW');
      assert.equal(await page.evaluate(()=>localStorage.getItem('orchid-language')),'zh-TW');
      assert.deepEqual(await page.evaluate(()=>window.languageWrites),['zh-TW']);
      assert.equal(await page.locator('.language-switch [data-language="zh-TW"]').getAttribute('aria-pressed'),'true');
      assert.equal(await page.locator('.language-switch [data-language="en"]').getAttribute('aria-pressed'),'false');
    } finally { await browser.close(); }
  });
