const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.SUTECH_PLAYWRIGHT || 'playwright');

const files = path.resolve(__dirname, '../dist');
const types = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json', '.png':'image/png', '.svg':'image/svg+xml'};
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const file = path.resolve(files, '.' + url.pathname);
  if (!file.startsWith(files + path.sep)) { res.writeHead(404).end(); return; }
  fs.readFile(file, (error, data) => {
    if (error) { res.writeHead(404).end(); return; }
    res.writeHead(200, {'Content-Type':types[path.extname(file)] || 'application/octet-stream'}).end(data);
  });
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  let browser;
  try {
    browser = await chromium.launch(process.env.SUTECH_BROWSER ? {executablePath:process.env.SUTECH_BROWSER} : {});
    const page = await browser.newPage({viewport:{width:360,height:780},isMobile:true,hasTouch:true});
    const errors = [], external = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => {
      const url = route.request().url();
      if (url.startsWith(origin + '/')) return route.continue();
      external.push(url);
      return route.abort();
    });
    await page.goto(`${origin}/demo.html?example=greenhouse`);
    await page.locator('#status[data-status="critical"]').waitFor();
    assert.equal(await page.locator('#example').inputValue(),'1');
    assert.match(await page.locator('#m3').textContent(), /\d\.\d{2} m³/);
    assert.equal(await page.evaluate(() => !!window.Telegram), false);
    assert.equal(await page.locator('#rain').isDisabled(),true);
    await page.locator('#example').selectOption('2');
    assert.match(await page.locator('#example-note').textContent(), /2\.6 mm\/day/);
    assert.equal(await page.locator('#et0').isDisabled(),true);
    await page.locator('#example').selectOption('3');
    assert.equal(await page.locator('#status').getAttribute('data-status'),'unsupported');
    assert.equal(await page.locator('#m3').textContent(),'—');
    assert.equal(await page.locator('#steps li').count(),0);
    for (const lang of ['ru','kz','en']) {
      await page.locator(`[data-lang="${lang}"]`).click();
      assert.equal(await page.locator('#example').inputValue(),'3');
      const options=await page.locator('#crop option').evaluateAll(nodes=>nodes.map(n=>[n.value,n.textContent]));
      assert.ok(options.length >= 18);
      assert.ok(options.every(([value,name]) => name && name !== value));
    }
    await page.locator('[data-lang="kz"]').click();
    await page.goto(`${origin}/demo.html?example=greenhouse`);
    assert.equal(await page.locator('html').getAttribute('lang'),'kk');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
    assert.deepEqual(errors,[]);
    assert.ok(external.every(url=>/^https:\/\/fonts\.(googleapis|gstatic)\.com\//.test(url)),external.join('\n'));
    console.log('Browser demo: mobile, three languages, offline calculations and applicability verified');
  } finally { await browser?.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode=1; });
