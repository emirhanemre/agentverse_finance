// Screenshot original nick-demo and its preserved replay with identical fixtures.
// Then compare screenshots with scripts/compare_visuals.py.
const {chromium}=require('../app/node_modules/playwright');
const fs=require('node:fs');
const path=require('node:path');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--disable-gpu'],executablePath:process.env.CHROME_PATH||chromium.executablePath()});
 try {
  const reports=[];
  const out='docs/screenshots/comparison';fs.mkdirSync(out,{recursive:true});
  for(const theme of ['light','dark'])for(const viewport of [{width:1440,height:1000},{width:1024,height:768}]){
   const pages=[];
   for(const url of ['http://127.0.0.1:3001/dashboard','http://127.0.0.1:3000/replay']){
    const page=await browser.newPage({viewport,reducedMotion:'no-preference'});
    await page.addInitScript(theme=>localStorage.setItem('pubhedge.theme',theme),theme);
    await page.goto(url);
    console.log('Loaded', url);
    await page.getByRole('heading',{name:'Overview',exact:true}).waitFor().catch(async e=>{console.log((await page.locator('body').innerText()).slice(0,2500));throw e;});
    await page.evaluate(()=>document.fonts.ready);
    pages.push(page);
   }
   for(const name of ['Overview','Protections','Risks','Activity','Data sources','Settings']){
    for(let i=0;i<pages.length;i++){
     const page=pages[i];await page.getByRole('button',{name,exact:true}).click();
     await page.waitForTimeout(1800);
     const file=`${name.toLowerCase().replaceAll(' ','-')}-${theme}-${viewport.width}-${i?'replay':'baseline'}.png`;
     await page.screenshot({path:path.join(out,file),timeout:20000});
     const metrics=await page.evaluate(()=>({background:getComputedStyle(document.body).backgroundColor,color:getComputedStyle(document.body).color,font:getComputedStyle(document.body).fontFamily,fontSize:getComputedStyle(document.body).fontSize,sidebar:document.querySelector('aside')?.getBoundingClientRect().width,panelRadius:document.querySelector('section')?getComputedStyle(document.querySelector('section')).borderRadius:null}));
     reports.push({name,theme,viewport,kind:i?'replay':'baseline',file,metrics});
    }
    console.log(`${name} ${theme} ${viewport.width}`);
   }
   for(const page of pages)await page.close();
  }
  fs.writeFileSync(path.join(out,'metrics.json'),JSON.stringify(reports,null,2));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
