// Focused post-layout check against the already completed isolated browser record.
const {chromium}=require('../app/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||chromium.executablePath()});
 try {
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const response=await page.request.get('http://127.0.0.1:3000/api/state');const state=await response.json();
  assert.equal(state.profile.pubName,'Browser Suitable Pub');assert.equal(state.positions.length,1);
  assert.equal(state.settings.weekly_spend_gbp,250);
  const screenshots=[];
  for(const theme of ['light','dark'])for(const viewport of [{width:1440,height:1000},{width:1024,height:768}]){
   await page.setViewportSize(viewport);
   await page.goto('http://127.0.0.1:3000/dashboard');
   await page.getByText('Browser Suitable Pub',{exact:true}).first().waitFor();
   await page.evaluate(t=>{document.documentElement.dataset.theme=t;localStorage.setItem('pubhedge.theme',t);},theme);
   await page.waitForTimeout(1500);
   const layout=await page.evaluate(()=>{
    const panel=[...document.querySelectorAll('section')].find(s=>s.querySelector('h2')?.textContent==='Recorded monthly revenue');
    const pending=[...document.querySelectorAll('section')].find(s=>s.querySelector('h2')?.textContent==='Needs approval');
    return {left:panel.getBoundingClientRect().width,right:pending.getBoundingClientRect().width,overflow:document.documentElement.scrollWidth>innerWidth};
   });
   assert.ok(Math.abs(layout.left/layout.right-1.45)<.025,JSON.stringify(layout));
   assert.equal(layout.overflow,false);
   const file=`docs/screenshots/integrated/overview-${theme}-${viewport.width}.png`;
   await page.screenshot({path:file});screenshots.push({file,layout});
   await page.getByRole('button',{name:'Protections',exact:true}).click();
   await page.waitForTimeout(500);
   await page.screenshot({path:`docs/screenshots/integrated/protections-${theme}-${viewport.width}.png`});
  }
  await page.reload();
  await page.getByRole('button',{name:'Switch to light theme',exact:true}).click();
  assert.equal(await page.evaluate(()=>localStorage.getItem('pubhedge.theme')),'light');
  await page.reload();
  assert.notEqual(await page.evaluate(()=>document.documentElement.dataset.theme),'dark');
  assert.deepEqual(errors,[]);
  fs.writeFileSync('docs/screenshots/integrated/layout-check.json',JSON.stringify({passed:true,screenshots,theme_toggle_persists:true,page_errors:errors},null,2));
  console.log('Focused layout, theme and persisted dashboard checks passed');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
