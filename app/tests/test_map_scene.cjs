// Contract tests run the actual scene controller, without claiming a GPU/browser test.
const assert=require('node:assert/strict');
const vm=require('node:vm');const fs=require('node:fs');
const nodes=new Map();
function element(){const classes=new Set();return {innerHTML:'',textContent:'',dataset:{},hidden:true,style:{setProperty(){}},classList:{toggle(k,v){if(v??!classes.has(k))classes.add(k);else classes.delete(k);},add(k){classes.add(k);},remove(k){classes.delete(k);},contains(k){return classes.has(k);}},addEventListener(){},focus(){},setAttribute(k,v){this[k]=v;}};}
const document={hidden:false,querySelector(s){if(!nodes.has(s))nodes.set(s,element());return nodes.get(s);},querySelectorAll(){return [];},createElement:element,addEventListener(){}};
class MapMock{
 constructor(o){this.options=o;this.sources={};this.layers=[];this.events={};this.paint={};this.canvas=element();this.bearing=-24;this.pitch=48;this.dragRotate={enable(){}};this.touchZoomRotate={enableRotation(){}};this.touchPitch={enable(){}};}
 addControl(){}on(name,...rest){this.events[name]=rest.at(-1);}
 addSource(id,source){this.sources[id]={...source,updates:0,setData(data){this.data=data;this.updates++;}};}
 addLayer(l){this.layers.push(l);}getSource(id){return this.sources[id];}
 getLayer(id){return this.layers.find(l=>l.id===id);}setLayoutProperty(id,p,value){this.paint[id+':'+p]=value;}
 setPixelRatio(r){this.ratio=r;}getPixelRatio(){return this.ratio||1.5;}
 isMoving(){return !!this.moving;}
 getCenter(){return {lng:39.77,lat:40.99};}getZoom(){return 16;}getPitch(){return this.pitch;}getBearing(){return this.bearing;}
 getCanvas(){return this.canvas;}setPaintProperty(id,p,value){this.paint[id+':'+p]=value;}
 getTerrain(){return this.terrain;}setTerrain(t){this.terrain=t;}
 fitBounds(b,o){this.bounds=b;this.fitOptions=o;this.fits=(this.fits||0)+1;}easeTo(o){this.camera=o;this.pitch=o.pitch??this.pitch;this.bearing=o.bearing??this.bearing;}setLight(o){this.light=o;}
 stop(){this.stops=(this.stops||0)+1;}resize(){this.resized=true;}remove(){}flyTo(o){this.flight=o;}
}
class MarkerMock{constructor(o){this.element=o.element;}setLngLat(p){this.location=p;return this;}setRotation(v){this.rotation=v;return this;}addTo(){return this;}remove(){this.removed=true;}}
class BoundsMock{constructor(){this.points=[];}extend(p){this.points.push(p);}}
let frames=new Map(),frameId=0,watchCallback,watchError,cleared=[];
const context={window:{addEventListener(){},devicePixelRatio:2,isSecureContext:true},document,navigator:{hardwareConcurrency:8,geolocation:{watchPosition(cb,err){watchCallback=cb;watchError=err;return 7;},clearWatch(id){cleared.push(id);}}},performance:{now:()=>0},ResizeObserver:class{observe(){}},maplibregl:{Map:MapMock,Marker:MarkerMock,LngLatBounds:BoundsMock,NavigationControl:class{},AttributionControl:class{},ScaleControl:class{}},matchMedia:()=>({matches:false}),fetch:async()=>{throw new Error('unexpected fetch');},requestAnimationFrame(cb){frames.set(++frameId,cb);return frameId;},cancelAnimationFrame(id){frames.delete(id);},AbortSignal,setTimeout:()=>1,clearTimeout(){},Map,Set,console};
context.window.maplibregl=context.maplibregl;
vm.createContext(context);vm.runInContext(fs.readFileSync('app/web/map-scene.js','utf8'),context);
const scene=new context.window.GCMapScene(element(),()=>{});
const bins=[{id:'S01',name:'A',lng:39.77,lat:40.99,color:'red',fill_percent:90,source:'simulated'}, {id:'H1',name:'B',lng:39.771,lat:40.991,color:'gray',fill_percent:null,source:'live'}];
const plan={id:'p1',stops:[{id:'S01'}],geometry:[[40.99,39.77],[40.991,39.771]],road_geometry:false,recommended:{distance_km:1}};
const payload={bins,plan,depot:{lng:39.77,lat:40.99},selected:null};
scene.render(payload);assert.equal(scene.payload,payload); // API may resolve before map style.
scene.map.events['style.load']();
assert.equal(scene.markers.size,2);assert.equal(scene.map.sources.demand.data.features.length,1,'unknown fill excluded from heatmap');
assert.equal(scene.map.options.canvasContextAttributes.preserveDrawingBuffer,false,'no permanent export framebuffer');
assert.equal(scene.map.options.pixelRatio,1.5,'automatic DPR cap');
assert.equal(scene.map.paint['buildings:visibility'],'visible','buildings can overlay satellite');
assert.ok(scene.map.getSource('trabzon-buildings'),'regional model is available');
assert.equal(scene.markers.get('H1').element.title.includes('Belirsiz'),true);
assert.equal(scene.map.sources.route.data.geometry.coordinates[0][0],39.77,'route longitude first');
assert.equal(scene.map.sources.route.data.geometry.coordinates[0][1],40.99);
assert.equal(scene.map.paint['route-line:line-dasharray'][0],2,'approximate route is dashed');
const first=scene.markers.get('S01');scene.render(payload);assert.equal(scene.markers.get('S01'),first,'polling preserves marker identity/focus');
assert.equal(scene.map.fits,1,'periodic refresh must not recenter the camera twice');
assert.equal(scene.map.sources.route.updates,1,'unchanged polling does not upload route geometry again');
scene.camera('buildings');scene.setBasemap('city');assert.equal(scene.map.paint['satellite:visibility'],'none');assert.equal(scene.map.paint['buildings:visibility'],'none','basemap cannot override buildings toggle');assert.equal(scene.map.paint['trabzon-buildings:visibility'],'none');
scene.camera('buildings');scene.setBasemap('satellite');assert.equal(scene.map.paint['buildings:visibility'],'visible');assert.equal(scene.map.sources.route.updates,1,'basemap preserves route');
scene.setQuality('eco');assert.equal(scene.map.ratio,1);scene.setQuality('sharp');assert.equal(scene.map.ratio,2);
scene.setQuality('auto');scene.startMeter();scene.map.moving=true;for(let i=0;i<46;i++){context.performance.now=()=>i*40;scene.measureFrame();}scene.applyPendingQuality();assert.equal(scene.map.ratio,1.5,'quality adjustment cannot interrupt a gesture');scene.endMeter();scene.map.moving=false;scene.applyPendingQuality();assert.equal(scene.map.ratio,1,'slow render samples reduce resolution only when idle');assert.equal(scene.measuring,false,'idle frame sampling stops');
scene.camera('2d');assert.equal(scene.map.camera.pitch,0);scene.camera('3d');assert.equal(scene.map.camera.pitch,48);
scene.camera('dimension');assert.equal(scene.mode,'2d');assert.equal(scene.map.camera.pitch,0);scene.camera('dimension');assert.equal(scene.mode,'3d');
const location=JSON.stringify(scene.markers.get('S01').marker.location);scene.camera('rotate-right');assert.equal(scene.map.camera.bearing,6);scene.camera('north');assert.equal(scene.map.camera.bearing,0);assert.equal(JSON.stringify(scene.markers.get('S01').marker.location),location,'camera never mutates geographic coordinates');
scene.camera('heat');assert.equal(scene.map.paint['demand:visibility'],'visible');
scene.camera('relief');assert.equal(scene.map.terrain.exaggeration,1);scene.camera('relief');assert.equal(scene.map.terrain,null);
scene.camera('tour');assert.equal(scene.touring,true);scene.camera('tour');assert.equal(scene.touring,false,'tour toggles off');
scene.camera('tour');const stopCount=scene.map.stops||0;scene.map.events.rotatestart({});assert.equal(scene.touring,true,'programmatic rotation cannot cancel flight');scene.map.events.dragstart({originalEvent:{}});assert.equal(scene.touring,false);assert.equal(scene.map.stops||0,stopCount,'manual drag must not call stop on the active gesture');
scene.notice('test');assert.equal(nodes.get('#tileNotice').hidden,false);assert.equal(nodes.get('#noticeText').textContent,'test');scene.dismissNotice();assert.equal(nodes.get('#tileNotice').hidden,true);
scene.render({...payload,bins:[bins[0]],plan:null});assert.equal(scene.markers.size,1);assert.equal(scene.map.sources.route.data.features.length,0,'leaving route clears it');
scene.invalidateSize();assert.equal(scene.map.resized,true);
// Driver lifecycle runs without GPS permission prompts or backend writes.
context.performance.now=()=>0;
context.GCRouteMath=require('../web/route-math.js');
vm.runInContext(fs.readFileSync('app/web/driver-mode.js','utf8'),context);
const driver=new context.window.GCDriverMode(scene);scene.driver=driver;
scene.render(payload);
(async()=>{
 await scene.fullscreen();assert.equal(nodes.get('.map-card').classList.contains('map-expanded'),true);await scene.fullscreen();assert.equal(nodes.get('.map-card').classList.contains('map-expanded'),false,'fullscreen toggle has its own stable state');
 await driver.open();assert.equal(driver.active,true);assert.equal(driver.mode,'preview');
 driver.demo();assert.equal(driver.running,true);assert.ok(frames.size>0);
 const tick=[...frames.values()].at(-1);tick(200);assert.ok(driver.progress>0);driver.pause();assert.equal(driver.running,false);
 driver.gps();assert.equal(driver.mode,'demo','approximate route cannot start real GPS guidance');
 driver.plan={...driver.plan,road_geometry:true};driver.gps();assert.equal(driver.mode,'gps');
 watchCallback({coords:{longitude:39.77,latitude:40.99,accuracy:150,speed:null,heading:null},timestamp:1000});assert.equal(driver.accuracy,150);
 watchCallback({coords:{longitude:39.77,latitude:40.99,accuracy:5,speed:2,heading:20},timestamp:2000});assert.equal(driver.speed,7.2);assert.equal(driver.offRoute,false);
 driver.pause();assert.ok(cleared.includes(7),'GPS watcher released on pause');assert.equal(driver.mode,'preview');
 driver.gps();watchError();assert.equal(driver.mode,'preview','permission failure falls back to preview');
 driver.sync({...payload,plan:{...plan,id:'changed'}});assert.equal(driver.active,false,'new plan closes old driver session');
 assert.equal(driver.truck.removed,true);assert.equal(scene.map.camera.padding.top,0,'camera padding restored');
 console.log('PASS: driver simulation, GPS quality gate, cleanup, plan replacement, and camera restoration');
})().catch(e=>{console.error(e);process.exitCode=1;});
const geo=JSON.parse(fs.readFileSync('app/web/data/campus.geojson','utf8'));
const provenance=JSON.parse(fs.readFileSync('app/web/data/scene-source.json','utf8'));
const regional=JSON.parse(fs.readFileSync('app/web/data/trabzon-buildings.geojson','utf8'));
const regionSource=JSON.parse(fs.readFileSync('app/web/data/trabzon-source.json','utf8'));
assert.equal(regional.features.length,regionSource.building_count);
assert.ok(regional.features.length>1000);const campusIds=new Set(geo.features.filter(f=>f.properties.kind==='building').map(f=>f.id));assert.ok(regional.features.every(f=>!campusIds.has(f.id)),'no duplicate buildings across sources');
for(const kind of ['building','road','land'])assert.equal(geo.features.filter(f=>f.properties.kind===kind).length,provenance.counts[kind]);
assert.ok(provenance.counts.building>0);
for(const f of geo.features.filter(f=>f.properties.kind==='building')){
 assert.equal(f.geometry.type,'Polygon');assert.deepEqual(f.geometry.coordinates[0][0],f.geometry.coordinates[0].at(-1));assert.ok(f.properties.height>=3&&f.properties.height<=180);
 assert.ok(['OSM height','OSM levels x 3m','12m visual estimate'].includes(f.properties.height_source));
}
console.log('PASS: 3D map integration contracts, route coordinates, null fill, marker updates, cameras, and sourced city geometry');
