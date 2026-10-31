const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const model = require('../web/future-model.js');

const bin={id:'S03',lat:40.99,lng:39.77,fill_percent:62,usable:true,forecast:{available:true,rate_pph:8}};
const saved=JSON.stringify(bin);
assert.equal(model.project(bin,0),bin);
assert.equal(model.project(bin,3).fill_percent,86,'future fill comes from fitted slope');
assert.equal(model.project(bin,24).fill_percent,100,'projection cannot exceed full');
assert.equal(model.project({...bin,usable:false},3).fill_percent,null,'stale observations cannot create future certainty');
assert.equal(model.project({...bin,forecast:{available:false}},3).color,'gray','insufficient history stays unknown');
assert.equal(JSON.stringify(bin),saved,'time lens cannot change telemetry');
assert.equal(model.project(bin,3).lng,bin.lng,'future view cannot move a marker');
assert.equal(model.lightAt(Date.parse('2026-10-31T09:00:00Z')/1000).phase,'day','Trabzon noon');
assert.equal(model.lightAt(Date.parse('2026-10-31T21:00:00Z')/1000).phase,'night','Trabzon midnight');
assert.equal(model.lightAt(Date.parse('2026-06-21T16:00:00Z')/1000).phase,'day','seasonal daylight is not a fixed hour switch');

const manifest=JSON.parse(fs.readFileSync('app/web/manifest.webmanifest','utf8'));
assert.equal(manifest.scope,'/');assert.equal(manifest.id,'/');
assert.equal(manifest.display,'standalone');
assert.ok(manifest.icons.some(i=>i.purpose==='maskable'));
for(const icon of manifest.icons){
 const bytes=fs.readFileSync('app/web'+icon.src), size=Number(icon.sizes.split('x')[0]);
 assert.equal(bytes.readUInt32BE(16),size);assert.equal(bytes.readUInt32BE(20),size);
}
const listeners={}, entries=new Map([['/',new Response('<main>offline shell</main>')]]);
let requested=[];
const cache={addAll:async paths=>{for(const p of paths)assert.ok(fs.existsSync('app/web'+(p==='/'?'/index.html':p)),p+' must exist');},match:async key=>entries.get(key)?.clone(),put:async(key,response)=>entries.set(key,response)};
const context={self:{location:{origin:'https://gc.test'},addEventListener:(event,fn)=>listeners[event]=fn,clients:{claim:async()=>{}},skipWaiting:()=>{}},
 caches:{open:async()=>cache,keys:async()=>[],delete:async()=>true,match:async key=>entries.get(key)?.clone()},
 fetch:async req=>{requested.push(req);throw new Error('offline');},URL,Response,AbortController,setTimeout,clearTimeout};
vm.runInNewContext(fs.readFileSync('app/web/sw.js','utf8'),context);
const pageEvents={}, workerEvents={}, nodes=new Map(), sent=[];
function node(){return {dataset:{theme:'dark'},classList:{add(){}},setAttribute(){},querySelector:()=>({setAttribute(){}}),addEventListener(type,fn){this[type]=fn;}};}
const fakeRegistration={waiting:{postMessage:msg=>sent.push(msg)},addEventListener(){}};
const pwaContext={window:{isSecureContext:true,indexedDB:{},addEventListener:(type,fn)=>pageEvents[type]=fn},
 document:{documentElement:node(),querySelector:selector=>{if(!nodes.has(selector))nodes.set(selector,node());return nodes.get(selector);}},
 navigator:{userAgent:'Test',serviceWorker:{controller:{},addEventListener:(type,fn)=>workerEvents[type]=fn,register:async()=>fakeRegistration}},
 localStorage:{getItem:()=>null,setItem(){}},matchMedia:()=>({matches:false,addEventListener(){}}),
 indexedDB:{open(){throw new Error('storage blocked');}},location:{reload:()=>sent.push('reload')}};
vm.runInNewContext(fs.readFileSync('app/web/pwa.js','utf8'),pwaContext);
(async()=>{
 await pageEvents.load();
 pwaContext.window.GCPWA.setDriving(true);
 assert.equal(nodes.get('#applyUpdate').disabled,true,'an update cannot interrupt a drive');
 nodes.get('#applyUpdate').click();assert.equal(sent.length,0);
 pwaContext.window.GCPWA.setDriving(false);nodes.get('#applyUpdate').click();
 assert.equal(sent[0].type,'ACTIVATE_UPDATE');assert.equal(sent.length,1,'activation does not itself refresh a live screen');
 workerEvents.controllerchange();assert.equal(sent[1],'reload','only an accepted update refreshes');
 assert.equal(await pwaContext.window.GCPWA.snapshot('get'),null,'blocked device storage must not make the API appear offline');
 let installed;listeners.install({waitUntil:p=>installed=p});await installed;
 for(const [url,method] of [['https://gc.test/api/dashboard','GET'],['https://gc.test/health','GET'],['https://gc.test/api/plan','POST'],['https://tile.openstreetmap.org/1/1/1.png','GET']]){
  let intercepted=false;listeners.fetch({request:{url,method,mode:'cors'},respondWith:()=>intercepted=true});
  assert.equal(intercepted,false,'API, writes, and third-party tiles bypass offline cache');
 }
 let navigation;listeners.fetch({request:{url:'https://gc.test/?launch=driver',method:'GET',mode:'navigate'},respondWith:p=>navigation=p});
 assert.match(await (await navigation).text(),/offline shell/,'installed app opens without network');
 console.log('PASS: forecast immutability, quality gates, seasonal day/night, PWA assets, offline shell and API cache isolation');
})().catch(e=>{console.error(e);process.exitCode=1;});
