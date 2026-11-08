// Capture the untouched nick-demo checkout. Run with the baseline URL and output directory.
const { chromium } = require('../app/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const out = process.argv[3] || 'docs/screenshots/nick-current';
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ headless: true, args: ['--disable-gpu'], executablePath: chromium.executablePath() });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'no-preference' });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(process.argv[2] || 'http://127.0.0.1:3001');
  await page.getByRole('button', { name: 'Look up my pub' }).waitFor();
  await page.evaluate(() => document.fonts.ready);
  const snap = async name => { await page.waitForTimeout(1600); await page.screenshot({ path: path.join(out, name + '.png'), timeout: 15000 }); console.log(name); };
  if (process.env.DASHBOARD_ONLY) {
    await page.goto((process.argv[2] || 'http://127.0.0.1:3001') + '/dashboard');
    for (const theme of ['light', 'dark']) {
      await page.evaluate(t => { document.documentElement.dataset.theme = t; localStorage.setItem('pubhedge.theme',t); }, theme);
      for (const viewport of [{width:1440,height:1000},{width:1024,height:768}]) {
        await page.setViewportSize(viewport);
        for (const name of ['Overview','Protections','Risks','Activity','Data sources','Settings']) {
          await page.getByRole('button',{name,exact:true}).click();
          await snap(`${name.toLowerCase().replaceAll(' ','-')}-${theme}-${viewport.width}`);
        }
      }
    }
    await browser.close();
    return;
  }
  await snap('01-business-light-desktop');
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await snap('01-business-dark-desktop');
  await page.setViewportSize({ width: 1024, height: 768 });
  await snap('01-business-dark-tablet');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Switch to light theme' }).click();
  await page.getByRole('button', { name: 'Look up my pub' }).click();
  await page.getByRole('button', { name: 'Confirm details' }).waitFor();
  await page.getByRole('button', { name: 'Confirm details' }).click({ timeout: 45000 });
  await snap('03-sources');
  await page.getByRole('button', { name: 'Connect all' }).click();
  await page.getByRole('button', { name: 'Run analysis' }).click({ timeout: 45000 });
  await page.getByRole('button', { name: 'See the impact' }).click({ timeout: 45000 });
  await snap('05-impact');
  await page.getByRole('button', { name: 'See recommendations' }).click();
  await snap('06-recommendations');
  await page.getByRole('button', { name: 'Review', exact: true }).click();
  await snap('07-review');
  await page.goto((process.argv[2] || 'http://127.0.0.1:3001') + '/dashboard');
  await page.getByRole('heading', { name: 'Overview', exact: true }).waitFor();
  await snap('08-overview-light-desktop');
  for (const name of ['Protections', 'Risks', 'Activity', 'Data sources', 'Settings']) {
    await page.getByRole('button', { name, exact: true }).click();
    await snap('09-' + name.toLowerCase().replaceAll(' ', '-'));
  }
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await snap('10-overview-dark-desktop');
  await page.setViewportSize({ width: 1024, height: 768 });
  await snap('10-overview-dark-tablet');
  fs.writeFileSync(path.join(out, 'capture.json'), JSON.stringify({ commit: '93a8f12ed52f4717d52bf7f49fe3762e0ace2d70', viewport: [1440,1000], reducedMotion: true, errors }, null, 2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
