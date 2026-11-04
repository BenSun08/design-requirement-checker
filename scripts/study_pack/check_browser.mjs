// Build-machine smoke check: open extracted files with network and page JS disabled.
import assert from 'node:assert/strict';
import {readdir, mkdir} from 'node:fs/promises';
import {resolve, join, basename} from 'node:path';
import {pathToFileURL} from 'node:url';
const [packArg, nodeToolsArg, screenshotsArg] = process.argv.slice(2);
const pack = resolve(packArg);
const {default: puppeteer} = await import(pathToFileURL(
  resolve(nodeToolsArg, 'node_modules/puppeteer/lib/puppeteer/puppeteer.js')
).href);
const browser = await puppeteer.launch({
  headless: true,
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
  args: ['--no-sandbox'],
});
let visits = 0;
try {
  const page = await browser.newPage();
  await page.setJavaScriptEnabled(false);
  await page.setOfflineMode(true);
  const external = [];
  page.on('request', request => {
    if (/^https?:/i.test(request.url())) external.push(request.url());
  });
  const files = (await readdir(pack, {recursive: true})).filter(f => f.endsWith('.html'));
  for (const width of [1440, 390]) {
    await page.setViewport({width, height: 900, deviceScaleFactor: 1});
    for (const file of files) {
      await page.goto(pathToFileURL(join(pack, file)).href, {waitUntil: 'load'});
      const state = await page.evaluate(() => ({
        title: document.title,
        broken: [...document.images].filter(i => !i.complete || !i.naturalWidth).map(i => i.src),
        overflow: document.documentElement.scrollWidth > innerWidth + 1,
      }));
      assert(state.title, `${file}: empty title`);
      assert.deepEqual(state.broken, [], `${file}: broken image`);
      assert(!state.overflow, `${file}: page overflows at ${width}px`);
      visits++;
    }
    await page.goto(pathToFileURL(join(pack, '06-learning-path/exercises.html')).href);
    await page.click('details summary');
    assert(await page.$eval('details', el => el.open), 'Native disclosure did not open');
    await page.goto(pathToFileURL(join(pack, 'index.html')).href);
    await page.click('a[href="06-learning-path/start-here.html"]');
    assert(page.url().endsWith('/06-learning-path/start-here.html'), 'Relative navigation failed');
    if (screenshotsArg) {
      await mkdir(screenshotsArg, {recursive: true});
      for (const file of ['index.html', '01-overview/architecture.html', '02-code-structure/call-graph.html']) {
        await page.goto(pathToFileURL(join(pack, file)).href);
        await page.screenshot({path: join(screenshotsArg, `${width}-${basename(file)}.png`), fullPage: true});
      }
    }
  }
  assert.deepEqual(external, [], 'Browser attempted external requests');
  console.log(`PASS: ${visits} file:// page visits at desktop/mobile widths; images, links, disclosures; zero HTTP requests; page JavaScript disabled.`);
} finally {
  await browser.close();
}
