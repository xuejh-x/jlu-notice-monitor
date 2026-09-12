import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const dir=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(path.resolve(dir,'../../../frontend/package.json'));
const {chromium}=require('playwright');
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const results=[];
const design=JSON.parse(fs.readFileSync(path.join(dir,'design-data.json'),'utf8'));
const known=new Set();
function checkNode(n){
 if(n.kind==='instance'){assert(known.has(n.component),'Unresolved dependency: '+n.component);return;}
 if(n.kind==='text'){assert(design.types[n.role]);assert(design.themes.Dark[n.color]);}
 if(n.kind==='icon')assert(design.icons[n.icon]);
 if(n.fill)assert(design.themes.Dark[n.fill]);
 if(n.border)assert(design.themes.Dark[n.border]);
 if(n.kind==='frame'){
  assert(design.spaces.includes(n.gap));
  for(const p of (Array.isArray(n.pad)?n.pad:[n.pad]))assert(design.spaces.includes(p),'Undefined spacing '+p);
 }
 if(n.radius!==undefined)assert(design.radii.includes(n.radius));
 for(const child of n.children||[])checkNode(child);
}
for(const c of design.components){for(const n of Object.values(c.variants))checkNode(n);known.add(c.name);}
for(const s of design.screens)checkNode(s.node);
for(const [index,w,h]of [[0,1440,900],[1,1440,900],[2,768,900],[3,390,844],[4,390,844]]){
 const page=await browser.newPage({viewport:{width:w,height:h},deviceScaleFactor:1});
 await page.goto(pathToFileURL(path.join(dir,'preview.html')).href+'?view=screen-'+index);
 await page.screenshot({path:path.join(dir,['desktop-dark.png','desktop-light.png','compact-768.png','mobile-list.png','mobile-reader.png'][index])});
 const check=await page.evaluate(()=>{
  const root=document.querySelector('.shown');const frame=root.firstElementChild;const r=frame.getBoundingClientRect();
  const overflow=[...frame.querySelectorAll('[data-name]')].filter(e=>{const p=e.parentElement;if(!p||p===frame)return false;const s=getComputedStyle(p);if(['hidden','auto','scroll'].includes(s.overflow)||s.flexDirection==='column')return false;const a=e.getBoundingClientRect(),b=p.getBoundingClientRect();return a.right>b.right+2||a.left<b.left-2;}).map(e=>e.dataset.name);
  return {width:r.width,height:r.height,documentWidth:document.documentElement.scrollWidth,horizontalOverflow:overflow};
 });results.push({screen:index,...check});await page.close();
}
const gallery=await browser.newPage({viewport:{width:1440,height:1000}});
await gallery.goto(pathToFileURL(path.join(dir,'preview.html')).href+'?view=component-7');
await gallery.screenshot({path:path.join(dir,'notification-row-variants.png'),fullPage:true});
const componentChecks=[];
for(let k=0;k<design.components.length;k++){
 await gallery.goto(pathToFileURL(path.join(dir,'preview.html')).href+'?view=component-'+k);
 componentChecks.push(await gallery.evaluate(()=>({name:document.querySelector('.shown h2').textContent,width:document.querySelector('.shown').getBoundingClientRect().width,variants:document.querySelectorAll('.shown .specimen').length})));
}
await gallery.goto(pathToFileURL(path.join(dir,'preview.html')).href+'?view=screen-4');
const scrollCheck=await gallery.evaluate(()=>{const s=document.querySelector('.shown [data-name="Reader scroll area"]');s.scrollTop=s.scrollHeight;return {canScroll:s.scrollTop>0,scrollHeight:s.scrollHeight,viewportHeight:s.clientHeight,originalLinkPresent:!!s.querySelector('[data-name="Original"]')};});
assert(scrollCheck.canScroll&&scrollCheck.originalLinkPresent);
await browser.close();
const lum=hex=>{const v=[1,3,5].map(p=>parseInt(hex.slice(p,p+2),16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return v[0]*.2126+v[1]*.7152+v[2]*.0722;};
const pairs=[['text-primary','list-surface'],['text-secondary','detail-surface'],['text-muted','list-surface'],['deadline-danger-fg','deadline-danger-bg'],['deadline-warning-fg','deadline-warning-bg'],['deadline-neutral-fg','deadline-neutral-bg'],['accent-soft-text','selected-surface'],['text-inverse','cta-surface']];
const contrasts=[];for(const [theme,c]of Object.entries(design.themes))for(const [fg,bg]of pairs){const a=lum(c[fg]),b=lum(c[bg]);const ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);assert(ratio>=4.5,`${theme} ${fg} contrast ${ratio}`);contrasts.push({theme,fg,bg,ratio:Number(ratio.toFixed(2))});}
fs.writeFileSync(path.join(dir,'verification.json'),JSON.stringify({scope:'HTML preview generated from shared design data; Figma runtime NOT executed due MCP quota.',results,componentChecks,scrollCheck,contrasts},null,2));
console.log(JSON.stringify(results,null,2));
