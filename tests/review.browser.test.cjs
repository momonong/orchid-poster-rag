const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');

test('private review login, safe visitor text, filters, feedback, pagination and mobile layout', async () => {
  const browser = await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
  const prefix = process.env.ORCHID_TEST_PREFIX || '/orchid-poster';
  const root = path.join(__dirname,'..');
  const key = 'synthetic-review-key-'+'x'.repeat(32);
  try {
    const page = await browser.newPage({viewport:{width:1440,height:900}});
    const errors=[];
    page.on('pageerror', e=>errors.push(e.message));
    let requests=0;
    await page.route('**/*', async route => {
      const request=route.request(), url=new URL(request.url());
      assert.ok(url.pathname.startsWith(prefix+'/review'));
      assert.ok(!url.href.includes(key), 'password must never be in the URL');
      if (url.pathname===prefix+'/review') {
        const html=(await fs.readFile(path.join(root,'orchid/static/review/index.html'),'utf8')).replaceAll('__ROOT__',prefix);
        return route.fulfill({contentType:'text/html',body:html});
      }
      if (url.pathname.startsWith(prefix+'/review/api/')) {
        requests++;
        if (request.headers().authorization!=='Bearer '+key) return route.fulfill({status:401,json:{detail:'denied'}});
        const feedback=url.searchParams.get('kind')==='feedback';
        const filter=url.searchParams.get('q');
        const offset=Number(url.searchParams.get('offset'));
        const row={id:'synthetic',created_at:'2026-11-03T01:20:00Z',section:'clue2',language:'en',status:'unknown',
          question:'<img src=x onerror="window.injected=true"> What changes the spot size?',
          answer:'Saved reply: <script>window.injected=true</script>',citations:['P08_1'],latency_ms:500,
          clarity:'partly',comment:'希望圖說更大一點'};
        return route.fulfill({json:{totals:{questions:26,feedback:1},total:feedback?1:filter?0:26,
          items:filter?[]:[{...row,id:'row-'+offset}],limit:25,offset}});
      }
      const filename=path.basename(url.pathname);
      assert.ok(['review.css','review.js'].includes(filename));
      return route.fulfill({contentType:filename.endsWith('.css')?'text/css':'text/javascript',
        body:await fs.readFile(path.join(root,'orchid/static/review',filename))});
    });
    await page.goto('https://orchid.test'+prefix+'/review');
    assert.equal(requests,0,'opening shell must not fetch visitor data');
    await page.locator('#password').fill('wrong');
    await page.locator('#login-form button').click();
    await page.getByText('審閱密碼不正確或已更換，請重新輸入。',{exact:true}).waitFor();
    await page.locator('#password').fill(key);
    await page.locator('#login-form button').click();
    await page.locator('.record').waitFor();
    assert.match(await page.locator('.question').textContent(),/<img/);
    assert.equal(await page.locator('#items img').count(),0);
    await page.locator('.record summary').click();
    assert.match(await page.locator('.answer').textContent(),/<script>/);
    assert.equal(await page.evaluate(()=>window.injected),undefined);
    assert.equal(await page.evaluate(()=>Object.keys(localStorage).length+Object.keys(sessionStorage).length),0);
    assert.equal(await page.locator('#password').inputValue(),'');
    const screenshotDir=path.join(root,'output/review-20261103');
    await fs.mkdir(screenshotDir,{recursive:true});
    await page.screenshot({path:path.join(screenshotDir,'synthetic-desktop.png'),fullPage:true});
    await page.locator('#next').click();
    await page.getByText('第 2 頁',{exact:true}).waitFor();
    await page.locator('#search').fill('no match');
    await page.locator('#filters button').click();
    await page.getByText('目前沒有符合條件的紀錄。',{exact:true}).waitFor();
    await page.locator('#search').fill('');
    await page.locator('#filters button').click();
    await page.locator('.record').waitFor();
    await page.locator('[data-kind="feedback"]').click();
    await page.getByText('希望圖說更大一點',{exact:true}).waitFor();
    await page.setViewportSize({width:390,height:844});
    await page.locator('#filter-panel').evaluate(el=>el.open=false);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    const first=await page.locator('.record').boundingBox();
    assert.ok(first.y<844*.6,'first record must be visible above 60% viewport height');
    await page.screenshot({path:path.join(screenshotDir,'synthetic-mobile.png'),fullPage:true});
    await page.locator('#logout').click();
    assert.equal(await page.locator('#items .record').count(),0);
    assert.equal(await page.locator('#login-panel').isVisible(),true);
    assert.deepEqual(errors,[]);
  } finally {await browser.close();}
});
