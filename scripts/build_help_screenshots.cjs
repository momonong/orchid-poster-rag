'use strict';
// Rebuild public help images from the existing loopback UI. No model or service is started.
const fs=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require('playwright');

async function build(baseURL='http://127.0.0.1:8000') {
  const base=new URL(baseURL);
  if(base.protocol!=='http:' || !['127.0.0.1','localhost','[::1]'].includes(base.hostname) || base.username || base.password || base.pathname!=='/' || base.search || base.hash) {
    throw new Error('Use the already-running loopback HTTP origin; this script never starts a service.');
  }
  const project=path.resolve(__dirname,'..');
  const output=path.join(project,'.orchid','assets','tour-preview','help');
  await fs.mkdir(output,{recursive:true});
  const browser=await chromium.launch({channel:process.env.ORCHID_BROWSER_CHANNEL || (process.platform==='win32'?'msedge':undefined),headless:true,args:['--disable-gpu','--disable-background-networking']});
  const manifest={schema:1,source_origin:base.origin,viewport_css:{width:390,height:1400},device_scale_factor:2,
    note:'Real DOM screenshots from the existing website. API health is a fixed display fixture; the prepared-audio manifest is read from the existing website. Drafts and ratings are examples, never submitted; no audio or generated answer is captured.',items:[]};
  const writes=[];
  try {
    for(const language of ['en','zh-TW']) {
      const context=await browser.newContext({viewport:manifest.viewport_css,deviceScaleFactor:2,reducedMotion:'reduce'});
      try {
        await context.addInitScript(language=>{localStorage.setItem('orchid-language',language);sessionStorage.setItem('orchid-tour-welcome-seen','1');},language);
        await context.route('**/*',async route=>{
          const request=route.request(),url=new URL(request.url());
          if(request.method()!=='GET'){writes.push(url.pathname);return route.fulfill({status:405,body:'Help screenshots never submit visitor content or audio requests.'});}
          if(url.origin!==base.origin)return route.abort();
          if(url.pathname==='/api/health')return route.fulfill({json:{index:{ready:true},model:{ready:true},speech:{ready:true,languages:['en','zh-TW']}}});
          if(url.pathname.startsWith('/tour-preview/') || url.pathname==='/speech.js' || url.pathname.startsWith('/assets/tour-preview/'))return route.continue();
          return route.fulfill({status:404});
        });
        const page=await context.newPage();
        await page.goto(base.origin+'/tour-preview/',{waitUntil:'networkidle'});
        await page.locator('#play-guide:not([disabled])').waitFor();
        await page.waitForFunction(language=>document.documentElement.lang===(language==='en'?'en':'zh-Hant-TW'),language);
        await page.locator('#poster-image').evaluate(image=>image.decode());
        const guide=await page.locator('.tour-header').boundingBox();
        const poster=await page.locator('.poster-frame').boundingBox();
        const column=await page.locator('.page').boundingBox();
        const top=Math.max(0,Math.floor(guide.y-8));
        const bottom=Math.min(poster.y+poster.height,poster.y+330);
        const files=[];
        const guideFile=`${language}-guide.png`;
        await page.screenshot({path:path.join(output,guideFile),clip:{x:column.x,y:top,width:column.width,height:Math.ceil(bottom-top+4)}});
        files.push({kind:'guide',filename:guideFile,description:'Dynamic title and Menu, playback and reading controls plus a crop of the framed poster; no playback.'});
        await page.locator('#quick-question').click();
        await page.locator('#question').fill(language==='en'?'How do simulations differ from experiments?':'模擬與實驗有什麼不同？');
        await page.locator('#question').blur();
        const questionFile=`${language}-question.png`;
        await page.locator('#chat-form').screenshot({path:path.join(output,questionFile)});
        files.push({kind:'question',filename:questionFile,description:'Question composer with an unsent public research example; no answer.'});
        await page.locator('[data-close="question-dialog"]').click();
        await page.locator('#menu-toggle').click();
        await page.locator('#open-feedback').click();
        await page.locator('label[for="clarity-partly"]').click();
        await page.locator('#feedback-comment').blur();
        const feedbackFile=`${language}-feedback.png`;
        await page.locator('#feedback-form').screenshot({path:path.join(output,feedbackFile)});
        files.push({kind:'feedback',filename:feedbackFile,description:'Feedback rating, empty comment field and Save control; not submitted or saved.'});
        for(const item of files){
          const bytes=await fs.readFile(path.join(output,item.filename));
          manifest.items.push({...item,language,url:'/assets/tour-preview/help/'+item.filename,width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20),bytes:bytes.length});
          console.log(`${item.filename}: ${bytes.readUInt32BE(16)}x${bytes.readUInt32BE(20)} (${bytes.length} bytes)`);
        }
      } finally { await context.close(); }
    }
    if(writes.length)throw new Error('Unexpected POST was blocked: '+writes.join(', '));
    manifest.submitted_requests=0;
    await fs.writeFile(path.join(output,'manifest.json'),JSON.stringify(manifest,null,2)+'\n','utf8');
    console.log('Created six real UI screenshots. Submitted requests: 0. API health was display-only fixture.');
    return manifest;
  } finally { await browser.close(); }
}
if(require.main===module){
  const args=process.argv.slice(2);
  if(args.length && !(args.length===2 && args[0]==='--base-url'))throw new Error('Usage: node scripts/build_help_screenshots.cjs [--base-url http://127.0.0.1:8000]');
  build(args[1]).catch(error=>{console.error(error.message);process.exitCode=1;});
}
module.exports={build};