// Contract tests run the actual scene controller, without claiming a GPU/browser test.
const assert=require('node:assert/strict');
const vm=require('node:vm');const fs=require('node:fs');
const nodes=new Map();
function element(){return {innerHTML:'',textContent:'',style:{setProperty(){}},classList:{toggle(){}},addEventListener(){},setAttribute(k,v){this[k]=v;}};}
const document={hidden:false,querySelector(s){if(!nodes.has(s))nodes.set(s,element());return nodes.get(s);},querySelectorAll(){return [];},createElement:element,addEventListener(){}};
class MapMock{
 constructor(o){this.options=o;this.sources={};this.layers=[];this.events={};this.paint={};this.canvas=element();}
 addControl(){}on(name,...rest){this.events[name]=rest.at(-1);}
 addSource(id,source){this.sources[id]={...source,setData(data){this.data=data;}};}
 addLayer(l){this.layers.push(l);}getSource(id){return this.sources[id];}
 getCanvas(){return this.canvas;}setPaintProperty(id,p,value){this.paint[id+':'+p]=value;}
 getTerrain(){return this.terrain;}setTerrain(t){this.terrain=t;}
 fitBounds(b,o){this.bounds=b;this.fitOptions=o;}easeTo(o){this.camera=o;}setLight(o){this.light=o;}
 stop(){}resize(){this.resized=true;}remove(){}flyTo(o){this.flight=o;}
}
class MarkerMock{constructor(o){this.element=o.element;}setLngLat(p){this.location=p;return this;}addTo(){return this;}remove(){this.removed=true;}}
class BoundsMock{constructor(){this.points=[];}extend(p){this.points.push(p);}}
const context={window:{addEventListener(){}},document,maplibregl:{Map:MapMock,Marker:MarkerMock,LngLatBounds:BoundsMock,NavigationControl:class{},AttributionControl:class{},FullscreenControl:class{}},matchMedia:()=>({matches:false}),fetch:async()=>{throw new Error('offline');},AbortSignal,setTimeout:()=>1,clearTimeout(){},Map,Set,console};
context.window.maplibregl=context.maplibregl;
vm.createContext(context);vm.runInContext(fs.readFileSync('app/web/map-scene.js','utf8'),context);
const scene=new context.window.GCMapScene(element(),()=>{});
const bins=[{id:'S01',name:'A',lng:39.77,lat:40.99,color:'red',fill_percent:90,source:'simulated'}, {id:'H1',name:'B',lng:39.771,lat:40.991,color:'gray',fill_percent:null,source:'live'}];
const plan={id:'p1',stops:[{id:'S01'}],geometry:[[40.99,39.77],[40.991,39.771]],road_geometry:false,recommended:{distance_km:1}};
const payload={bins,plan,depot:{lng:39.77,lat:40.99},selected:null};
scene.render(payload);assert.equal(scene.payload,payload); // API may resolve before map style.
scene.map.events['style.load']();
assert.equal(scene.markers.size,2);assert.equal(scene.map.sources.occupancy.data.features.length,2);
assert.equal(scene.map.sources.occupancy.data.features[1].properties.height,3,'null fill stays unknown');
assert.equal(scene.markers.get('H1').element.title.includes('Belirsiz'),true);
assert.equal(scene.map.sources.route.data.geometry.coordinates[0][0],39.77,'route longitude first');
assert.equal(scene.map.sources.route.data.geometry.coordinates[0][1],40.99);
assert.equal(scene.map.paint['route-line:line-dasharray'][0],2,'approximate route is dashed');
const first=scene.markers.get('S01');scene.render(payload);assert.equal(scene.markers.get('S01'),first,'polling preserves marker identity/focus');
scene.camera('2d');assert.equal(scene.map.camera.pitch,0);scene.camera('3d');assert.equal(scene.map.camera.pitch,62);
scene.camera('relief');assert.equal(scene.map.terrain.exaggeration,1);scene.camera('relief');assert.equal(scene.map.terrain,null);
scene.camera('tour');assert.equal(scene.touring,true);scene.camera('tour');assert.equal(scene.touring,false,'tour toggles off');
scene.render({...payload,bins:[bins[0]],plan:null});assert.equal(scene.markers.size,1);assert.equal(scene.map.sources.route.data.features.length,0,'leaving route clears it');
scene.invalidateSize();assert.equal(scene.map.resized,true);
const geo=JSON.parse(fs.readFileSync('app/web/data/campus.geojson','utf8'));
const provenance=JSON.parse(fs.readFileSync('app/web/data/scene-source.json','utf8'));
for(const kind of ['building','road','land'])assert.equal(geo.features.filter(f=>f.properties.kind===kind).length,provenance.counts[kind]);
assert.ok(provenance.counts.building>0);
for(const f of geo.features.filter(f=>f.properties.kind==='building')){
 assert.equal(f.geometry.type,'Polygon');assert.deepEqual(f.geometry.coordinates[0][0],f.geometry.coordinates[0].at(-1));assert.ok(f.properties.height>=3&&f.properties.height<=180);
 assert.ok(['OSM height','OSM levels x 3m','12m visual estimate'].includes(f.properties.height_source));
}
console.log('PASS: 3D map integration contracts, route coordinates, null fill, marker updates, cameras, and sourced city geometry');
