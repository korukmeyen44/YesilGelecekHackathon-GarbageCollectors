/* Local-first 3D scene. Public geometry is kept separate from simulated telemetry. */
"use strict";
class GCMapScene {
  constructor(container,onSelect){
    this.container=container;this.onSelect=onSelect;this.markers=new Map();this.mode="3d";this.night=false;this.ready=false;this.payload=null;this.frame=null;this.motion=matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.style={version:8,sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,maxzoom:19},campus:{type:"geojson",data:"/data/campus.geojson",attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors · ODbL'}},layers:[
      {id:"ground",type:"background",paint:{"background-color":"#e2e9dc"}},
      {id:'context-osm',type:'raster',source:'osm',paint:{'raster-saturation':-.25,'raster-opacity':.75}},
      {id:"land",type:"fill",source:"campus",filter:["==",["get","kind"],"land"],paint:{"fill-color":"#b8d4a6","fill-opacity":.7}},
      {id:"road-border",type:"line",source:"campus",filter:["==",["get","kind"],"road"],paint:{"line-color":"#c1c7ba","line-width":["interpolate",["linear"],["zoom"],13,2,18,15]}},
      {id:"roads",type:"line",source:"campus",filter:["==",["get","kind"],"road"],paint:{"line-color":"#fffdf2","line-width":["interpolate",["linear"],["zoom"],13,1,18,11]}},
      {id:"buildings",type:"fill-extrusion",source:"campus",filter:["==",["get","kind"],"building"],paint:{"fill-extrusion-color":["case",["get","estimated"],"#cfbea2","#d8cbb5"],"fill-extrusion-height":["get","height"],"fill-extrusion-base":0,"fill-extrusion-opacity":.97,"fill-extrusion-vertical-gradient":true}}
    ],light:{anchor:"viewport",color:"#fff2d6",intensity:.5,position:[1.5,210,40]}};
    try{
      if(!window.maplibregl)throw new Error("MapLibre unavailable");
      this.map=new maplibregl.Map({container,style:this.style,center:[39.7722,40.9915],zoom:16.3,pitch:62,bearing:-26,maxPitch:78,antialias:true,attributionControl:false,canvasContextAttributes:{preserveDrawingBuffer:true}});
      this.map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'top-right');
      this.map.addControl(new maplibregl.AttributionControl({compact:true}),'bottom-right');
      this.map.addControl(new maplibregl.FullscreenControl({container:document.querySelector('.map-workspace')}),'top-right');
      this.map.on('style.load',()=>{if(this.ready)return;this.ready=true;this.installLayers();this.render(this.payload);this.onlineContext();});
      this.map.on('error',e=>{if(e.sourceId==='elevation'){this.map.setTerrain(null);document.querySelector('[data-camera="relief"]').setAttribute('aria-pressed','false');this.notice('Arazi servisi yüklenemedi; 3D binalar ve rota kullanılabilir.');}else if(e.sourceId==='campus')this.notice('Yerel şehir geometrisi yüklenemedi; sayfayı yenileyin veya 2D yedeği açın.');else if(!this.ready)this.notice('3D zemin yüklenemedi; yerel model ve liste kullanılabilir.');});
      this.map.on('dragstart',()=>this.stop());this.map.on('zoomstart',e=>{if(e.originalEvent)this.stop();});
      this.map.getCanvas().addEventListener('webglcontextlost',()=>this.notice('Grafik bağlamı kesildi. Sayfayı yenileyin veya 2D yedeğini açın.'));
    }catch(error){this.fallback();}
    document.addEventListener('visibilitychange',()=>{if(document.hidden)this.stop();});
    window.addEventListener('pagehide',()=>this.stop());
    document.addEventListener('click',e=>{const b=e.target.closest('[data-camera]');if(b)this.camera(b.dataset.camera);});
  }
  notice(text){const el=document.querySelector('#tileNotice');el.textContent=text;el.hidden=false;}
  installLayers(){
    const m=this.map;
    for(const name of ['occupancy','route'])m.addSource(name,{type:'geojson',data:{type:'FeatureCollection',features:[]},...(name==='route'?{lineMetrics:true}:{})});
    m.addLayer({id:'occupancy',type:'fill-extrusion',source:'occupancy',paint:{'fill-extrusion-height':['get','height'],'fill-extrusion-color':['get','color'],'fill-extrusion-opacity':.65,'fill-extrusion-vertical-gradient':true}});
    m.addLayer({id:'route-glow',type:'line',source:'route',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#39f5bd','line-width':16,'line-opacity':.22,'line-blur':5}});
    m.addLayer({id:'route-line',type:'line',source:'route',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#008961','line-width':5,'line-opacity':.95}});
    m.addLayer({id:'route-core',type:'line',source:'route',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#bdffdf','line-width':1.5,'line-opacity':.9}});
    m.on('click','occupancy',e=>{const id=e.features?.[0]?.properties?.id;if(id)this.onSelect(id);});
    m.on('mouseenter','occupancy',()=>m.getCanvas().style.cursor='pointer');m.on('mouseleave','occupancy',()=>m.getCanvas().style.cursor='');
  }
  async onlineContext(){
    // This enriches the cached local city model; failure never removes local geometry.
    try{
      const response=await fetch('https://tiles.openfreemap.org/styles/liberty',{signal:AbortSignal.timeout(10000)});
      if(!response.ok)throw new Error('style');const style=await response.json();
      if(!this.ready)return;
      for(const [key,source]of Object.entries(style.sources||{}))this.map.addSource('context-'+key,source);
      // No sprite dependency: only terrain/land/road geometries, no missing icons or fonts.
      for(const layer of style.layers||[]){
        if(!['background','fill','line'].includes(layer.type)||/building/.test(layer.id))continue;
        const copy=JSON.parse(JSON.stringify(layer));copy.id='context-'+copy.id;if(copy.source)copy.source='context-'+copy.source;
        if(copy.paint){delete copy.paint['fill-pattern'];delete copy.paint['line-pattern'];}
        this.map.addLayer(copy,'land');
      }
      this.map.setPaintProperty('land','fill-opacity',.38);
      document.querySelector('#sceneStatus').textContent='OSM ŞEHİR MODELİ · VEKTÖR ZEMİN';
    }catch(error){document.querySelector('#sceneStatus').textContent='YEREL OSM MODELİ · ÇEVRİMDIŞI HAZIR';}
  }
  render(payload){
    if(!payload)return;this.payload=payload;
    if(this.leaflet)return this.renderFallback(payload);
    if(!this.ready)return;
    const {bins,plan,depot,selected}=payload;const visible=new Set();
    const numbers=new Map((plan?.stops||[]).map((s,i)=>[s.id,i+1]));
    const columns=[];
    for(const b of bins){
      visible.add(b.id);let entry=this.markers.get(b.id);
      if(!entry){const element=document.createElement('button');element.type='button';element.className='scene-pin';element.addEventListener('click',e=>{e.stopPropagation();this.onSelect(b.id);});const marker=new maplibregl.Marker({element,anchor:'bottom',pitchAlignment:'viewport',rotationAlignment:'viewport'}).setLngLat([b.lng,b.lat]).addTo(this.map);entry={element,marker};this.markers.set(b.id,entry);}
      const color={green:'#39ca91',yellow:'#f1bd51',red:'#fb7567',gray:'#9aafbb'}[b.color];
      entry.element.style.setProperty('--pin-color',color);entry.element.classList.toggle('is-selected',selected===b.id);entry.element.classList.toggle('is-live',b.source==='live');entry.element.classList.toggle('is-muted',!!plan&&!numbers.has(b.id));
      const label=numbers.get(b.id)??(b.fill_percent==null?'?':Math.round(b.fill_percent)+'%');
      const content=`<span class="pin-value">${label}</span><span class="pin-id">${b.id}${b.fast_filling?' ↗':''}</span><span class="pin-stem"></span><span class="pin-ring"></span>`;
      if(entry.element.innerHTML!==content)entry.element.innerHTML=content;
      entry.element.title=`${b.name} · ${b.source==='live'?'Canlı sensör':'Simülasyon'} · ${b.fill_percent==null?'Belirsiz':b.fill_percent+'% dolu'}`;
      entry.element.setAttribute('aria-label',entry.element.title);
      const ring=Array.from({length:17},(_,i)=>[b.lng+Math.cos(i*Math.PI/8)*.000045,b.lat+Math.sin(i*Math.PI/8)*.000034]);
      columns.push({type:'Feature',properties:{id:b.id,color,height:b.fill_percent==null?3:4+b.fill_percent*.23},geometry:{type:'Polygon',coordinates:[ring]}});
    }
    for(const [id,entry]of this.markers)if(!visible.has(id)){entry.marker.remove();this.markers.delete(id);}
    this.map.getSource('occupancy').setData({type:'FeatureCollection',features:columns});
    const route=plan?.stops.length?{type:'Feature',properties:{},geometry:{type:'LineString',coordinates:plan.geometry.map(p=>[p[1],p[0]])}}:{type:'FeatureCollection',features:[]};
    this.map.getSource('route').setData(route);this.map.setPaintProperty('route-line','line-dasharray',plan&&!plan.road_geometry?[2,2]:[1,0]);
    if(plan){if(!this.depotMarker){const element=document.createElement('div');element.className='scene-depot';element.innerHTML='⌂<small>BAŞLANGIÇ</small>';this.depotMarker=new maplibregl.Marker({element,anchor:'bottom'}).setLngLat([depot.lng,depot.lat]).addTo(this.map);}}else{this.depotMarker?.remove();this.depotMarker=null;}
    if(plan?.stops.length&&this.fitted!==plan.id){this.fitted=plan.id;this.fitBounds(plan.geometry,{padding:75});}
    document.querySelector('#sceneStopCount').textContent=plan?`${plan.stops.length} DURAK · ${plan.recommended.distance_km.toFixed(1)} KM`:`${bins.length} NOKTA · DOLULUK TAKİBİ`;
  }
  invalidateSize(){this.map?.resize?.();this.leaflet?.invalidateSize();}
  fitBounds(latlngs,options={}){
    if(!latlngs?.length)return;
    if(this.leaflet){this.leaflet.fitBounds(latlngs,{padding:[35,35],maxZoom:17});return;}
    if(!this.ready)return;
    const bounds=new maplibregl.LngLatBounds();latlngs.forEach(p=>bounds.extend([p[1],p[0]]));
    this.map.fitBounds(bounds,{padding:typeof options.padding==='number'?options.padding:65,maxZoom:16.8,pitch:this.mode==='3d'?60:0,bearing:this.mode==='3d'?-26:0,duration:this.motion?0:1300});
  }
  camera(action){
    if(action==='export'){this.exportImage();return;}
    if(action==='fallback'){this.fallback();return;}
    if(this.leaflet){this.notice('WebGL kullanılamadığı için 2D yedek açık.');return;}
    if(!this.ready)return;
    const wasTouring=this.touring;this.stop();
    if(action==='tour'&&wasTouring)return;
    if(action==='3d'||action==='2d'){this.mode=action;this.map.easeTo({pitch:action==='3d'?62:0,bearing:action==='3d'?-26:0,duration:this.motion?0:1200});document.querySelectorAll('[data-camera="3d"],[data-camera="2d"]').forEach(e=>e.setAttribute('aria-pressed',String(e.dataset.camera===action)));}
    if(action==='light'){
      this.night=!this.night;
      this.map.setLight({anchor:'viewport',color:this.night?'#b7d4ff':'#fff2d6',intensity:this.night?.25:.5,position:[1.5,this.night?80:210,this.night?75:40]});
      this.map.setPaintProperty('buildings','fill-extrusion-color',this.night?'#657b8e':['case',['get','estimated'],'#cfbea2','#d8cbb5']);
      this.map.setPaintProperty('context-osm','raster-brightness-max',this.night?.55:1);
      document.querySelector('.map-container').classList.toggle('night-scene',this.night);
    }
    if(action==='relief'){
      const enabled=!this.map.getTerrain();
      if(enabled&&!this.map.getSource('elevation'))this.map.addSource('elevation',{type:'raster-dem',tiles:['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],tileSize:256,encoding:'terrarium',maxzoom:14,attribution:'Elevation: Mapzen / AWS Terrain Tiles'});
      this.map.setTerrain(enabled?{source:'elevation',exaggeration:1}:null);document.querySelector('[data-camera="relief"]').setAttribute('aria-pressed',String(enabled));
    }
    if(action==='tour'){
      if(this.motion){this.notice('Azaltılmış hareket tercihi açık; otomatik kamera kapalı.');return;}
      const path=this.payload?.plan?.stops?.length?this.payload.plan.geometry:this.payload?.bins.map(b=>[b.lat,b.lng]);
      if(!path?.length)return;
      const stops=this.payload?.plan?.stops||[];
      const points=stops.length?stops.map(stop=>{const b=this.payload.bins.find(b=>b.id===stop.id);return b?[b.lat,b.lng]:null;}).filter(Boolean):path;
      if(!points.length)return;
      let i=0;this.touring=true;const next=()=>{if(!this.touring||document.hidden)return;const p=points[i++%points.length];this.map.flyTo({center:[p[1],p[0]],zoom:17,pitch:65,bearing:(i*29)%360,duration:3500,essential:false});this.timer=setTimeout(next,4300);};next();
      document.querySelector('[data-camera="tour"]').setAttribute('aria-pressed','true');
    }
    if(action==='home')this.fitBounds(this.payload.bins.map(b=>[b.lat,b.lng]));
  }
  stop(){clearTimeout(this.timer);this.touring=false;this.map?.stop();document.querySelector('[data-camera="tour"]')?.setAttribute('aria-pressed','false');}
  exportImage(){
    if(!this.ready||!this.map){this.notice('PNG çıktısı için 3D haritanın yüklenmesi gerekli.');return;}
    this.stop();
    this.map.once('render',()=>{
      try{
        const source=this.map.getCanvas(),canvas=document.createElement('canvas');canvas.width=source.width;canvas.height=source.height;
        const ctx=canvas.getContext('2d');ctx.drawImage(source,0,0);const scale=source.width/source.clientWidth;ctx.scale(scale,scale);
        const width=source.clientWidth,height=source.clientHeight;
        ctx.fillStyle='#0d2729df';ctx.fillRect(14,14,Math.min(410,width-28),69);
        ctx.fillStyle='#a6f4ce';ctx.font='bold 17px sans-serif';ctx.fillText('GARBAGE COLLECTORS / KANUNİ',26,40);
        ctx.fillStyle='#e4f4e9';ctx.font='10px sans-serif';ctx.fillText('3D OPERASYON · CANLI SENSÖR + SİMÜLASYON',26,61);
        const numbers=new Map((this.payload.plan?.stops||[]).map((s,i)=>[s.id,i+1]));
        for(const b of this.payload.bins){const p=this.map.project([b.lng,b.lat]);if(p.x<0||p.x>width||p.y<0||p.y>height)continue;
          const color={green:'#39ca91',yellow:'#f1bd51',red:'#fb7567',gray:'#9aafbb'}[b.color];ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(p.x,p.y-31);ctx.stroke();ctx.fillStyle=color;ctx.beginPath();ctx.roundRect(p.x-21,p.y-61,42,30,7);ctx.fill();ctx.strokeStyle='white';ctx.stroke();ctx.fillStyle='#092c26';ctx.font='bold 11px sans-serif';ctx.textAlign='center';ctx.fillText(String(numbers.get(b.id)??(b.fill_percent==null?'?':Math.round(b.fill_percent)+'%')),p.x,p.y-42);ctx.fillStyle='#15372c';ctx.fillRect(p.x-16,p.y-31,32,12);ctx.fillStyle='white';ctx.font='8px sans-serif';ctx.fillText(b.id,p.x,p.y-22);ctx.textAlign='left';}
        ctx.fillStyle='#102b2de8';ctx.fillRect(0,height-31,width,31);ctx.fillStyle='#e4f4e9';ctx.font='9px sans-serif';ctx.fillText('© OpenStreetMap contributors / ODbL · Eksik bina yükseklikleri tahmini · Doluluk göstergeleri temsilî',12,height-12);
        const a=document.createElement('a');a.download='garbage-collectors-3d.png';a.href=canvas.toDataURL('image/png');a.click();
      }catch(error){this.notice('Görüntü dışa aktarılamadı. Tarayıcının ekran görüntüsü aracını kullanabilirsiniz.');}
    });this.map.triggerRepaint();
  }
  fallback(){
    this.stop();this.map?.remove();this.map=null;this.container.innerHTML='';this.ready=false;
    if(!window.L){this.notice('Harita yüklenemedi. Kutu listesi ve rota sonuçları kullanılabilir.');return;}
    this.leaflet=L.map(this.container,{scrollWheelZoom:false}).setView([40.9916,39.7723],16);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',maxZoom:19}).addTo(this.leaflet);
    this.notice('2D yedek görünüm açık. Noktalar, renkler ve rota korunur.');
    document.querySelector('#sceneStatus').textContent='2D YEDEK GÖRÜNÜM';this.renderFallback(this.payload);
  }
  renderFallback(p){
    if(!p)return;this.fallbackLayers?.forEach(l=>this.leaflet.removeLayer(l));this.fallbackLayers=[];
    for(const b of p.bins){const color={green:'#39ca91',yellow:'#f1bd51',red:'#fb7567',gray:'#9aafbb'}[b.color];const m=L.circleMarker([b.lat,b.lng],{radius:10,color:'#fff',weight:2,fillColor:color,fillOpacity:1}).addTo(this.leaflet).bindTooltip(`${b.id} · ${b.fill_percent==null?'Belirsiz':b.fill_percent+'%'}`);m.on('click',()=>this.onSelect(b.id));this.fallbackLayers.push(m);}
    if(p.plan?.stops.length)this.fallbackLayers.push(L.polyline(p.plan.geometry,{color:'#147d5a',weight:5,dashArray:p.plan.road_geometry?null:'8 8'}).addTo(this.leaflet));
  }
}
window.GCMapScene=GCMapScene;
