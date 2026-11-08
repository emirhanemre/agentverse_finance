// Run only against a fresh, isolated APP_DB_PATH. Never resets a user's records.
const { chromium } = require('../app/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const url = process.argv[2] || 'http://127.0.0.1:3000';
  const out = process.argv[3] || 'docs/screenshots/integrated';
  fs.mkdirSync(out,{recursive:true});
  const browser = await chromium.launch({headless:true,args:['--disable-gpu'],executablePath:process.env.CHROME_PATH||chromium.executablePath()});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const state=async()=>{const response=await page.request.get(url+'/api/state');assert.equal(response.status(),200);return response.json();};
    const resume=process.argv.includes('--resume-no-hedge-checkpoint');
    if(resume){
      const checkpoint=await state();
      assert.equal(checkpoint.profile?.pubName,'Browser No Hedge Pub');
      assert.equal(checkpoint.positions.length,0);
      assert.equal(checkpoint.analysis.payload.status,'no_suitable_hedge');
      assert.equal(checkpoint.setup_complete,true);
    }else assert.equal((await state()).profile,null,'Use a fresh isolated APP_DB_PATH; this test will not overwrite an existing business.');
    const snap=async name=>{await page.waitForTimeout(1600);await page.screenshot({path:path.join(out,name+'.png'),timeout:20000});console.log(name);};
    const button=name=>page.getByRole('button',{name,exact:true});
    const setup=async(name,mode)=>{
      await page.goto(url);
      await button('Use sample business').waitFor();
      await button('Use sample business').click();
      await page.getByLabel('Pub name',{exact:true}).fill(name);
      await button('Save business details').click();
      await page.getByRole('button',{name:/^(Connect|Replay) Companies House demo$/}).click();
      await page.getByText('Demo connected',{exact:true}).waitFor();
      assert.equal((await state()).sources.find(s=>s.id==='companies_house').status,'demo_connected');
      await button('Continue with these details').click();
      await page.getByRole('heading',{name:'Sources',exact:true}).waitFor();
      await button('Connect all demos').click();
      await page.getByText('Demo connected',{exact:true}).first().waitFor();
      await page.waitForFunction(()=>[...document.querySelectorAll('span')].filter(s=>s.textContent==='Demo connected').length===3);
      assert.equal((await state()).dataset,null,'Provider animations must not import sales.');
      await page.getByLabel('Import sales CSV',{exact:true}).setInputFiles({name:'invalid.csv',mimeType:'text/csv',buffer:Buffer.from('date,revenue_gbp,currency\n2026-01-01,-12,GBP')});
      await page.getByRole('alert').filter({hasText:'nonnegative'}).waitFor();
      await button('Use synthetic sample sales').click();
      await page.getByText('Synthetic sample',{exact:true}).waitFor();
      await snap(mode+'-03-sources');
      await button('Configure analysis').click();
      await page.getByLabel('Market evidence',{exact:true}).selectOption(mode);
      await button('Run weather analysis').click();
      await button('See the impact').click({timeout:30000});
      await snap(mode+'-05-impact');
      await button('See recommendations').click();
      await snap(mode+'-06-recommendations');
    };
    if(!resume){
    await setup('Browser No Hedge Pub','test_no_match');
    await page.getByText('No suitable hedge',{exact:false}).first().waitFor();
    await button('Continue without a hedge').click();
    await button('Open dashboard').click();
    await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();
    assert.equal((await state()).positions.length,0);
    await snap('no-hedge-dashboard');
    await page.reload();
    await page.getByText('Browser No Hedge Pub',{exact:true}).waitFor();
    assert.equal((await state()).summary.pending_approvals,0);
    }
    await page.goto(url);
    await page.getByRole('heading',{name:'Impact',exact:true}).waitFor();
    await page.getByRole('button',{name:/Your business/}).click();
    // Re-enter the actual setup through the existing tracker.
    await button('Use sample business').click();
    await page.getByLabel('Pub name',{exact:true}).fill('Browser Suitable Pub');
    await button('Save business details').click();
    await button('Continue with these details').click();
    await button('Use synthetic sample sales').click();
    await page.getByText('Synthetic sample',{exact:true}).waitFor();
    await button('Configure analysis').click();
    await page.getByLabel('Market evidence',{exact:true}).selectOption('test_suitable');
    await button('Run weather analysis').click();
    await button('See the impact').click({timeout:30000});
    await button('See recommendations').click();
    await page.getByRole('checkbox').locator('..').click();
    assert.equal(await page.getByRole('checkbox').isChecked(),true);
    await button('Review').click();
    await page.getByRole('heading',{name:'Paper approval',exact:true}).waitFor();
    await snap('suitable-07-review');
    await page.getByRole('checkbox').locator('..').click();
    assert.equal(await page.getByRole('checkbox').isChecked(),true);
    await button('Approve and record paper position').click();
    await page.getByText('Approved · recorded as paper',{exact:true}).waitFor();
    await button('Open dashboard').click();
    await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();
    let saved=await state();
    assert.equal(saved.positions.length,1);
    assert.equal(saved.positions[0].actual_resolved_outcome,'UNRESOLVED');
    assert.equal(saved.summary.pending_approvals,0);
    await page.reload();
    await page.getByText('Browser Suitable Pub',{exact:true}).first().waitFor();
    assert.equal((await state()).positions[0].position_id,saved.positions[0].position_id);
    const forecastResponse=page.waitForResponse(r=>r.url().endsWith('/api/weather/refresh')&&r.request().method()==='POST');
    await button('Refresh forecast').click();
    const forecast=await (await forecastResponse).json();
    assert.ok(['current_forecast','cached_forecast','unavailable'].includes(forecast.origin));
    for(const theme of ['light','dark']) {
      await page.evaluate(theme=>{document.documentElement.dataset.theme=theme;localStorage.setItem('pubhedge.theme',theme);},theme);
      for(const viewport of [{width:1440,height:1000},{width:1024,height:768}]) {
        await page.setViewportSize(viewport);
        for(const name of ['Overview','Protections','Risks','Activity','Data sources','Settings']) {
          await button(name).click();
          await snap(name.toLowerCase().replaceAll(' ','-')+'-'+theme+'-'+viewport.width);
        }
      }
    }
    await button('Protections').click();
    await button('Check settlement').click();
    await page.getByText('No real payouts or redemptions occurred.',{exact:false}).waitFor();
    await button('Settings').click();
    await page.getByLabel('Weekly spending limit (GBP)').fill('250');
    await button('Save settings').click();
    await page.getByText('Saved',{exact:true}).waitFor();
    assert.equal((await state()).settings.weekly_spend_gbp,250);
    assert.equal(errors.length,0,errors.join('\n'));
    fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({checked_at:new Date().toISOString(),journeys:['sample business → invalid import → sample sales → no suitable hedge → dashboard without positions','sample business → suitable synthetic scenario → explicit human approval → persisted paper position → reload','all dashboard pages in light/dark at 1440×1000 and 1024×768','settings persistence and unresolved settlement refresh'],positions:1,forecast_origin:forecast.origin,page_errors:errors},null,2));
    console.log('Browser acceptance passed');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
