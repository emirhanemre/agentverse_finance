// Run only on a fresh isolated APP_DB_PATH; never clears existing records.
const {chromium}=require('../app/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:3100';
 const out='docs/screenshots/operating-profit';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:chromium.executablePath()});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const state=async()=>{const r=await page.request.get(base+'/api/state');assert.equal(r.status(),200);return r.json();};
  const request=async(endpoint,method,data)=>{const r=await page.request[method](base+'/api'+endpoint,{data});assert.ok(r.ok(),await r.text());return r.json();};
  const button=n=>page.getByRole('button',{name:n,exact:true});
  const card=()=>page.locator('section').filter({has:page.getByText('Estimated operating profit',{exact:true})}).last();
  const cash=n=>new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP'}).format(n);
  const shown=async()=>{const s=await state();await card().getByText(cash(s.operating_profit.selected.operating_profit_gbp),{exact:true}).waitFor();return s;};
  const edit=async(fixed,pct)=>{
   if(await button('Edit demo cost assumptions').count())await button('Edit demo cost assumptions').click();
   await page.getByLabel('Fixed daily costs (GBP)',{exact:true}).fill(String(fixed));
   await page.getByLabel('Variable costs (% of revenue)',{exact:true}).fill(String(pct));
   await button('Save demo costs').click();await page.getByText('Costs saved',{exact:true}).waitFor();return shown();
  };
  assert.equal((await state()).profile,null,'Use a fresh isolated database. This script does not replace a business.');
  await request('/profile','put',{pubName:'Operating Profit Browser Test Pub',postcode:'SE22 8HD',owner:'Test Operator',email:'test@example.com',location_name:'London, UK',latitude:51.45,longitude:-.07});
  await request('/sources/sample','post');
  const date=new Date(Date.now()+2*86400000).toLocaleDateString('en-CA',{timeZone:'Europe/London'});
  const job=await request('/analyses','post',{target_date:date,market_mode:'test_suitable',temp_max_c:15,rain_mm:14});
  for(let i=0;i<120;i++){const r=await page.request.get(base+'/api/analyses/'+job.id);const jobState=await r.json();if(jobState.state!=='running')break;await page.waitForTimeout(250);}
  await page.goto(base+'/');await page.getByText('Conditional downside',{exact:false}).first().waitFor();
  let s=await shown();assert.equal(s.operating_profit.origin,'demo_cost_assumptions');
  const revision=s.revision;const proposalId=s.analysis.payload.proposal_id;
  s=await edit(500,20);
  assert.equal(s.analysis.id,job.id);assert.equal(s.revision,revision);assert.equal(s.analysis.payload.proposal_id,proposalId);
  assert.equal(s.operating_profit.assumptions.fixed_daily_cost_gbp,500);
  await page.reload();s=await shown();assert.equal(s.operating_costs.variable_cost_pct,20);
  await card().screenshot({path:path.join(out,'profit-card.png')});
  s=await edit(10000,90);assert.ok(s.operating_profit.selected.operating_profit_gbp<0);
  await card().getByText(cash(s.operating_profit.selected.operating_profit_gbp),{exact:true}).evaluate(el=>{if(!el.classList.contains('text-negative'))throw Error('Loss is not styled as negative');});
  await card().screenshot({path:path.join(out,'loss-card.png')});
  await button('Edit demo cost assumptions').click();
  const pct=page.getByLabel('Variable costs (% of revenue)',{exact:true});await pct.fill('101');
  await button('Save demo costs').click();assert.equal(await pct.evaluate(el=>el.checkValidity()),false);
  assert.equal((await state()).operating_costs.variable_cost_pct,90);
  await edit(500,20);
  for(const width of [1440,1024]){
   await page.setViewportSize({width,height:1000});await card().scrollIntoViewIfNeeded();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
   await page.screenshot({path:path.join(out,'impact-'+width+'.png')});
  }
  await request('/setup/complete','post');await page.goto(base+'/dashboard');await shown();
  await button('Settings').click();await page.getByLabel('Fixed daily costs (GBP)',{exact:true}).waitFor();
  await edit(650,25);await page.reload();await button('Settings').click();
  assert.equal(await page.getByLabel('Fixed daily costs (GBP)',{exact:true}).inputValue(),'650');
  await shown();await page.screenshot({path:path.join(out,'settings.png')});
  await button('Overview').click();await shown();
  await page.getByRole('tab',{name:'Scenarios',exact:true}).click();await shown();
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({passed:true,checked_at:new Date().toISOString(),origin:'Synthetic sales and explicit illustrative costs; isolated test records.',onboarding_card:true,editable_costs:true,losses_preserved:true,invalid_costs_rejected:true,reload_persistence:true,dashboard_and_settings:true,existing_analysis_and_proposal_preserved:true,page_errors:errors},null,2));
  console.log('Operating-profit browser checks passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
