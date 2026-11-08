// Exercise training and monitoring through the actual UI on an isolated test DB.
const {chromium}=require('../app/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:3100';
 const out='docs/screenshots/functional-v2';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:chromium.executablePath()});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const state=async()=>{const r=await page.request.get(base+'/api/state');assert.equal(r.status(),200);return r.json();};
  const button=n=>page.getByRole('button',{name:n,exact:true});
  const snap=async n=>{await page.waitForTimeout(1200);await page.screenshot({path:path.join(out,n+'.png')});console.log(n);};
  assert.equal((await state()).profile.pubName,'Browser Suitable Pub','This script requires the isolated acceptance record.');
  await page.goto(base+'/dashboard');
  await button('Data sources').click();
  const imported=page.waitForResponse(r=>r.url().endsWith('/api/sources/import') && r.request().method()==='POST');
  await page.getByLabel('Import sales CSV',{exact:true}).setInputFiles(path.resolve('app/public/synthetic-sales-training.csv'));
  assert.equal((await imported).status(),200);
  await page.getByText('User import · unverified',{exact:true}).waitFor();
  const started=page.waitForResponse(r=>r.url().endsWith('/api/models/train') && r.request().method()==='POST');
  await button('Train and evaluate sales model').click();
  const trainResponse=await started;assert.equal(trainResponse.status(),202);
  const trainingId=(await trainResponse.json()).id;const trainingStart=Date.now();
  while(true){const job=await (await page.request.get(base+'/api/models/training/'+trainingId)).json();assert.notEqual(job.state,'failed',job.payload?.error);if(job.state==='complete')break;assert.ok(Date.now()-trainingStart<120000,'Training timed out');await page.waitForTimeout(500);}
  await page.getByText('Chronological holdout passed',{exact:true}).waitFor({timeout:120000});
  let s=await state();assert.equal(s.business_model.accepted,true);assert.equal(s.business_model.origin,'user_import');
  assert.equal(s.business_model.matched_rows,1461);const modelId=s.business_model.id;
  await snap('training-evaluated-business-model');
  await page.reload();await button('Data sources').click();
  await page.getByText('Chronological holdout passed',{exact:true}).waitFor();
  assert.equal((await state()).business_model.id,modelId);
  await page.getByRole('tab',{name:'Scenarios',exact:true}).click();
  await button('Cold scenario').click();
  await page.getByLabel('Market evidence',{exact:true}).selectOption('live');
  await button('Run weather analysis').click();
  await page.getByText('Assessment saved',{exact:true}).waitFor({timeout:90000});
  s=await state();assert.equal(s.analysis.payload.comparison.scenario_prediction.model_version,modelId);
  assert.equal(s.analysis.payload.discovery.origin,'live_polymarket_api');
  const status=s.analysis.payload.status;
  await snap('live-contract-assessment-with-imported-model');
  await button('Settings').click();
  await page.getByLabel('Enable forecast monitoring and in-app alerts',{exact:true}).check();
  await button('Save monitoring settings').click();
  await page.getByText('Enabled while API runs',{exact:true}).waitFor();
  const start=Date.now();
  while(!(await state()).monitoring?.completed_at){assert.ok(Date.now()-start<90000,'Automatic monitor did not complete');await page.waitForTimeout(1000);}
  s=await state();assert.equal(s.settings.monitor_enabled,true);
  assert.ok(s.monitoring.last_run_at && s.monitoring.note);
  await snap('scheduled-monitoring-result');
  await page.getByRole('button',{name:'Show alerts and approvals',exact:true}).click();
  await page.getByRole('heading',{name:'Alerts',exact:true}).waitFor();
  assert.ok((await state()).notifications.length>0);
  const mark=button('Mark read').first();await mark.click();await page.waitForTimeout(500);
  assert.ok((await state()).notifications.some(n=>n.read_at));
  await snap('persisted-in-app-alerts');
  await button('Settings').click();
  await page.getByLabel('Enable forecast monitoring and in-app alerts',{exact:true}).uncheck();
  await button('Save monitoring settings').click();
  await page.getByText('Disabled',{exact:true}).first().waitFor();
  assert.equal((await state()).settings.monitor_enabled,false);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'weather-features.json'),JSON.stringify({passed:true,checked_at:new Date().toISOString(),records:'Explicit synthetic repository sales uploaded through CSV; actual historical weather fetched.',model_id:modelId,live_assessment_status:status,training_survives_reload:true,automatic_monitoring_completed:true,alerts_persist:true,page_errors:errors},null,2));
  console.log('Training, live analysis, automatic monitoring and alerts passed');
 } finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
