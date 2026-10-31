/* MapLibre GL JS 5.6.2. One renderer, cached geometry, no idle animation loop. */
"use strict";
class GCMapScene {
  constructor(container,onSelect){
    container.setAttribute('aria-busy','true');
    Object.assign(this,{container,onSelect,markers:new Map(),mode:'3d',basemap:'satellite',buildings:true,quality:'auto',night:false,ready:false,payload:null,signatures:{},motion:matchMedia('(prefers-reduced-motion: reduce)').matches});
    this.style={version:8,sources:{campus:{type:'geojson',data:'/data/campus.geojson',tolerance:.8,attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors · ODbL'}},layers:[
      {id:'ground',type:'background',paint:{'background-color':'#dce7df'}},
      {id:'land',type:'fill',source:'campus',filter:['==',['get','kind'],'land'],paint:{'fill-color':'#b8d6ba','fill-opacity':.8}},
      {id:'road-border',type:'line',source:'campus',filter:['==',['get','kind'],'road'],paint:{'line-color':'#adc1be','line-width':['interpolate',['linear'],['zoom'],13,1,18,12]}},
      {id:'roads',type:'line',source:'campus',filter:['==',['get','kind'],'road'],paint:{'line-color':'#faf9ee','line-width':['interpolate',['linear'],['zoom'],13,.5,18,9]}},
      {id:'buildings',type:'fill-extrusion',source:'campus',minzoom:14,paint:{'fill-extrusion-color':['interpolate',['linear'],['get','height'],3,'#b6c7c9',18,'#d9e1dc',50,'#91aaaf'],'fill-extrusion-height':['get','height'],'fill-extrusion-opacity':.85,'fill-extrusion-vertical-gradient':true}}
    ],light:{anchor:'map',color:'#fff9eb',intensity:.4,position:[1.5,210,35]}};
    try{
      if(!window.maplibregl)throw Error('MapLibre unavailable');
      maplibregl.setWorkerCount?.(Math.min(2,Math.max(1,(navigator.hardwareConcurrency||4)-1)));maplibregl.setMaxParallelImageRequests?.(8);
      this.map=new maplibregl.Map({container,style:this.style,center:[39.7722,40.9915],zoom:15.8,pitch:48,bearing:-24,maxPitch:70,maxZoom:19,renderWorldCopies:false,attributionControl:false,maxTileCacheSize:96,maxTileCacheZoomLevels:3,pixelRatio:this.pixelRatio(),fadeDuration:150,canvasContextAttributes:{antialias:false,powerPreference:'high-performance',preserveDrawingBuffer:false}});
      this.map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'top-right');this.map.addControl(new maplibregl.AttributionControl({compact:true}),'bottom-right');this.map.addControl(new maplibregl.ScaleControl({maxWidth:90,unit:'metric'}),'bottom-left');
      this.map.on('style.load',()=>{this.ready=true;this.installLayers();this.setBasemap(this.basemap);this.render(this.payload);this.pressed('motion',!this.motion);});this.map.on('error',e=>this.sourceError(e));
      // Never call Map.stop() from a gesture event: it also stops the active handler.
      const manual=()=>{this.cancelTour();this.driver?.unfollow();};
      this.map.on('dragstart',manual);this.map.on('rotatestart',e=>{if(e.originalEvent)manual();});this.map.on('pitchstart',e=>{if(e.originalEvent)manual();});
      this.map.on('zoomstart',e=>{if(e.originalEvent)manual();});
      this.map.dragRotate.enable();this.map.touchZoomRotate.enableRotation();this.map.touchPitch.enable();
      this.map.on('pitchend',()=>this.syncCameraControls());this.map.on('rotate',()=>this.updateCompass());
      this.map.on('movestart',()=>{container.setAttribute('aria-busy','true');this.startMeter();});this.map.on('moveend',()=>this.endMeter());
      this.map.on('render',()=>this.measureFrame());
      this.map.on('dataloading',()=>container.setAttribute('aria-busy','true'));
      this.map.on('idle',()=>{if(!this.applyPendingQuality())container.setAttribute('aria-busy','false');});
      this.map.getCanvas().addEventListener('webglcontextlost',()=>{this.stop();this.driver?.pause();this.notice('Grafik bağlantısı kesildi. 2D yedeğe geçebilirsiniz.');});
    }catch(error){this.fallback();}
    document.addEventListener('visibilitychange',()=>{if(document.hidden){this.stop();this.driver?.pause();this.endMeter();}});window.addEventListener('pagehide',()=>{this.stop();this.driver?.close();this.endMeter();});
    document.addEventListener('click',e=>{const b=e.target.closest('[data-camera]');if(b)this.camera(b.dataset.camera);const base=e.target.closest('[data-basemap]');if(base)this.setBasemap(base.dataset.basemap);});
    document.querySelector('#noticeClose')?.addEventListener('click',()=>this.dismissNotice());
    document.querySelector('#tileNotice')?.addEventListener('pointerenter',()=>this.pauseNotice());
    document.querySelector('#tileNotice')?.addEventListener('pointerleave',()=>this.resumeNotice());
    document.querySelector('#tileNotice')?.addEventListener('focusin',()=>this.pauseNotice());
    document.querySelector('#tileNotice')?.addEventListener('focusout',()=>this.resumeNotice());
    document.querySelector('#sceneQuality')?.addEventListener('change',e=>this.setQuality(e.target.value));document.querySelector('#mapFullscreen')?.addEventListener('click',()=>this.fullscreen());document.addEventListener('fullscreenchange',()=>this.invalidateSize());new ResizeObserver(()=>this.invalidateSize()).observe(container);
    document.querySelector('#sceneRegion')?.addEventListener('change',e=>this.showRegion(e.target.value));
  }
  notice(text){
    const el=document.querySelector('#tileNotice');
    if(!el.hidden&&this.lastNotice===text)return;
    this.dismissNotice();this.lastNotice=text;document.querySelector('#noticeText').textContent=text;el.hidden=false;
    this.noticeRemaining=8000;this.resumeNotice();
  }
  dismissNotice(){clearTimeout(this.noticeTimer);this.noticeTimer=null;this.noticeAnimation?.cancel();this.noticeAnimation=null;document.querySelector('#tileNotice').hidden=true;}
  pauseNotice(){if(!this.noticeTimer)return;clearTimeout(this.noticeTimer);this.noticeTimer=null;this.noticeRemaining=Math.max(0,this.noticeRemaining-(performance.now()-this.noticeStarted));this.noticeAnimation?.pause();}
  resumeNotice(){if(document.querySelector('#tileNotice').hidden||this.noticeTimer)return;this.noticeStarted=performance.now();const bar=document.querySelector('#noticeTimebar');if(!this.noticeAnimation)this.noticeAnimation=bar.animate?.([{transform:'scaleX(0)'},{transform:'scaleX(1)'}],{duration:this.noticeRemaining,fill:'forwards'});else this.noticeAnimation.play();this.noticeTimer=setTimeout(()=>this.dismissNotice(),this.noticeRemaining);}
  pixelRatio(){return Math.min(window.devicePixelRatio||1,this.quality==='eco'?1:this.quality==='sharp'?2:matchMedia('(max-width: 720px)').matches?1.25:1.5);}
  setQuality(value){this.quality=value;this.pendingPixelRatio=null;this.map?.setPixelRatio(this.pixelRatio());document.querySelector('#scenePerformance').textContent=`${value==='eco'?'EKONOMİK':value==='sharp'?'KESKİN':'OTOMATİK'} · ${this.pixelRatio().toFixed(2)}×`;}
  startMeter(){
    this.measuring=true;this.frameCount??=0;this.frameSum??=0;
  }
  measureFrame(){if(!this.measuring||document.hidden)return;const now=performance.now(),delta=this.frameTime==null?0:now-this.frameTime;this.frameTime=now;if(delta>0&&delta<250){this.frameSum+=delta;this.frameCount++;}if(this.frameCount>=45){this.lastFrameMs=this.frameSum/this.frameCount;document.querySelector('#scenePerformance').textContent=`${Math.round(1000/this.lastFrameMs)} FPS · ${this.map.getPixelRatio().toFixed(2)}×`;if(this.quality==='auto'&&this.lastFrameMs>28&&this.map.getPixelRatio()>1)this.pendingPixelRatio=1;this.frameCount=0;this.frameSum=0;}}
  applyPendingQuality(){if(this.pendingPixelRatio&&this.quality==='auto'&&this.map&&!this.map.isMoving()){const ratio=this.pendingPixelRatio;this.pendingPixelRatio=null;this.map.setPixelRatio(ratio);return true;}return false;}
  endMeter(){this.measuring=false;this.frameTime=null;}
  sourceError(e){
    if(e.sourceId==='elevation'){this.map.setTerrain(null);this.pressed('relief',false);this.notice('Arazi servisine erişilemiyor. Rota ve bina görünümü açık.');}
    if(e.sourceId==='satellite'&&this.basemap==='satellite'&&!this.imageryFailed){this.imageryFailed=true;this.setBasemap('city');this.notice('Uydu servisine erişilemiyor; yerel 3D şehir açıldı. Uyduyu tekrar deneyebilirsiniz.');}
    if(e.sourceId==='campus')this.notice('Yerel şehir verisi yüklenemedi. Yol, kutular ve rota bağımsız çalışır.');
    if(e.sourceId==='trabzon-buildings')this.notice('Geniş Trabzon modeli yüklenemedi. Kampüs modeli, kutular ve rota kullanılabilir.');
  }
  installLayers(){
    const m=this.map,empty={type:'FeatureCollection',features:[]};m.addSource('demand',{type:'geojson',data:empty});m.addSource('route',{type:'geojson',data:empty});
    m.addLayer({id:'demand',type:'heatmap',source:'demand',layout:{visibility:'none'},paint:{'heatmap-weight':['/',['get','fill'],100],'heatmap-radius':['interpolate',['linear'],['zoom'],13,18,18,65],'heatmap-intensity':.9,'heatmap-opacity':.65,'heatmap-color':['interpolate',['linear'],['heatmap-density'],0,'rgba(0,0,0,0)',.2,'#56b6ab',.5,'#f9d464',1,'#f16b50']}},'buildings');
    for(const [id,color,width]of [['route-casing','#092c34',10],['route-line','#39e7b0',6],['route-core','#d8fff2',1.4]])m.addLayer({id,type:'line',source:'route',layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':color,'line-width':width}});
  }
  setBasemap(value){
    this.basemap=value;document.querySelectorAll('[data-basemap]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.basemap===value)));
    if(this.leaflet){this.fallbackTile?.setUrl(value==='satellite'?GCMapScene.imagery:'https://tile.openstreetmap.org/{z}/{x}/{y}.png');return;}if(!this.ready)return;
    if(value==='satellite'&&!this.map.getSource('satellite')){this.map.addSource('satellite',{type:'raster',tiles:[GCMapScene.imagery],tileSize:256,maxzoom:19,attribution:'Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community'});this.map.addLayer({id:'satellite',type:'raster',source:'satellite',paint:{'raster-fade-duration':150,'raster-saturation':-.1}},'land');}
    if(value==='street'&&!this.map.getSource('street')){this.map.addSource('street',{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,maxzoom:19,attribution:'© OpenStreetMap contributors'});this.map.addLayer({id:'street',type:'raster',source:'street',paint:{'raster-saturation':-.5}},'land');}
    for(const layer of ['satellite','street'])if(this.map.getLayer(layer))this.map.setLayoutProperty(layer,'visibility',value===layer?'visible':'none');for(const layer of ['land','roads','road-border'])this.map.setLayoutProperty(layer,'visibility',value==='city'?'visible':'none');
    this.applyBuildings();
    this.map.setPaintProperty('buildings','fill-extrusion-opacity',.96);document.querySelector('#sceneStatus').textContent={satellite:'UYDU GÖRÜNTÜSÜ · ESRI WORLD IMAGERY',city:'YEREL 3D ŞEHİR · LOW POLY',street:'YOL HARİTASI + OSM BİNALAR'}[value];
  }
  render(payload){
    if(!payload)return;this.payload=payload;this.driver?.sync(payload);if(this.leaflet)return this.renderFallback(payload);if(!this.ready)return;
    const {bins,plan,depot,selected}=payload,numbers=new Map((plan?.stops||[]).map((s,i)=>[s.id,i+1])),visible=new Set();
    for(const b of bins){
      visible.add(b.id);let entry=this.markers.get(b.id);if(!entry){const element=document.createElement('button');element.type='button';element.className='scene-pin';element.addEventListener('click',e=>{e.stopPropagation();this.selectBin(b.id);});const marker=new maplibregl.Marker({element,anchor:'center',pitchAlignment:'viewport',rotationAlignment:'viewport',subpixelPositioning:true}).setLngLat([b.lng,b.lat]).addTo(this.map);entry={element,marker};this.markers.set(b.id,entry);}
      const location=`${b.lng},${b.lat}`;if(entry.location!==location){entry.marker.setLngLat([b.lng,b.lat]);entry.location=location;}entry.element.style.setProperty('--pin-color',GCMapScene.colors[b.color]||GCMapScene.colors.gray);entry.element.classList.toggle('is-selected',selected===b.id);entry.element.classList.toggle('is-live',b.source==='live');entry.element.classList.toggle('is-muted',!!plan&&!numbers.has(b.id));
      entry.element.dataset.lng=String(b.lng);entry.element.dataset.lat=String(b.lat);
      const label=b.fill_percent==null?'?':Math.round(b.fill_percent)+'',num=numbers.get(b.id),content=`<span class="pin-value">${label}</span>${num?`<span class="pin-order">${num}</span>`:''}<span class="pin-id">${b.id}${b.fast_filling?' ↗':''}</span>`;if(entry.element.innerHTML!==content)entry.element.innerHTML=content;
      entry.element.title=`${b.name} · ${b.source==='live'?'Canlı sensör':'Simülasyon'} · ${b.fill_percent==null?'Belirsiz':b.fill_percent+'% dolu'}${num?' · Durak '+num:''}`;entry.element.setAttribute('aria-label',entry.element.title);
    }
    for(const [id,entry]of this.markers)if(!visible.has(id)){entry.marker.remove();this.markers.delete(id);}
    this.setData('demand',{type:'FeatureCollection',features:bins.filter(b=>b.fill_percent!=null).map(b=>({type:'Feature',properties:{fill:b.fill_percent},geometry:{type:'Point',coordinates:[b.lng,b.lat]}}))});
    this.setData('route',plan?.stops.length&&plan.geometry.length>1?{type:'Feature',properties:{},geometry:{type:'LineString',coordinates:plan.geometry.map(p=>[p[1],p[0]])}}:{type:'FeatureCollection',features:[]});
    const dashed=!!plan&&!plan.road_geometry;if(this.dashed!==dashed){for(const layer of ['route-casing','route-line','route-core'])this.map.setPaintProperty(layer,'line-dasharray',dashed?[2,2]:[1,0]);this.dashed=dashed;}
    if(plan?.stops.length){if(!this.depotMarker){const element=document.createElement('div');element.className='scene-depot';element.innerHTML='⌂<small>DEPO</small>';this.depotMarker=new maplibregl.Marker({element,anchor:'bottom'}).setLngLat([depot.lng,depot.lat]).addTo(this.map);}}else{this.depotMarker?.remove();this.depotMarker=null;}
    if(plan?.stops.length&&this.fitted!==plan.id){this.fitted=plan.id;this.initialFit=true;this.fitBounds(plan.geometry);}
    else if(!this.initialFit&&bins.length){this.initialFit=true;this.fitBounds(bins.map(b=>[b.lat,b.lng]));}
    document.querySelector('#sceneStopCount').textContent=plan?`${plan.stops.length} DURAK · ${plan.recommended.distance_km.toFixed(1)} KM · ${plan.road_geometry?'YOL AĞI':'YAKLAŞIK ÇİZGİ'}`:`${bins.length} NOKTA · DOLULUK TAKİBİ`;
    const drive=document.querySelector('#driverLaunch');if(drive){drive.disabled=!plan?.stops.length;drive.title=plan?.stops.length?'Planlanan seferi tam ekran aç':'Önce rota planlama bölümünde sefer oluşturun';}
  }
  setData(name,data){const signature=JSON.stringify(data);if(this.signatures[name]===signature)return;this.signatures[name]=signature;this.map.getSource(name).setData(data);}
  async selectBin(id){this.driver?.close();if(document.fullscreenElement)try{await document.exitFullscreen();}catch{}document.querySelector('.map-card').classList.remove('map-expanded');this.onSelect(id);}
  invalidateSize(){this.map?.resize();this.leaflet?.invalidateSize();}
  fitBounds(latlngs,options={}){if(!latlngs?.length)return;if(this.leaflet){this.leaflet.fitBounds(latlngs,{padding:[35,35],maxZoom:17});return;}if(!this.ready)return;const bounds=new maplibregl.LngLatBounds();latlngs.forEach(p=>bounds.extend([p[1],p[0]]));this.map.fitBounds(bounds,{padding:typeof options.padding==='number'?options.padding:matchMedia('(max-width: 720px)').matches?45:85,maxZoom:16.8,pitch:this.mode==='3d'?48:0,bearing:this.mode==='3d'?-24:0,duration:this.motion?0:950});}
  pressed(action,value){document.querySelector(`[data-camera="${action}"]`)?.setAttribute('aria-pressed',String(value));}
  applyBuildings(){
    if(this.ready&&this.map){this.map.setLayoutProperty('buildings','visibility',this.buildings?'visible':'none');
      if(this.buildings&&!this.map.getSource('trabzon-buildings')){const layer=JSON.parse(JSON.stringify(this.style.layers.find(l=>l.id==='buildings')));this.map.addSource('trabzon-buildings',{type:'geojson',data:'/data/trabzon-buildings.geojson',tolerance:1.5,maxzoom:16,attribution:'© OpenStreetMap contributors · ODbL'});layer.id='trabzon-buildings';layer.source='trabzon-buildings';layer.minzoom=14;this.map.addLayer(layer,'buildings');}
      if(this.map.getLayer('trabzon-buildings'))this.map.setLayoutProperty('trabzon-buildings','visibility',this.buildings?'visible':'none');
    }this.pressed('buildings',this.buildings);
  }
  syncCameraControls(mode){this.mode=mode||(this.map.getPitch()<5?'2d':'3d');const button=document.querySelector('[data-camera="dimension"]');button?.setAttribute('aria-pressed',String(this.mode==='3d'));button?.setAttribute('title',this.mode==='3d'?'2D görünüme geç':'3D görünüme geç');document.querySelector('#dimensionLabel').textContent=this.mode==='3d'?'3D':'2D';}
  showRegion(region){
    this.stop();const regions={campus:{center:[39.7722,40.9915],zoom:15.6,label:'KANUNİ KAMPÜSÜ'},meydan:{center:[39.7284,41.0053],zoom:16,label:'TRABZON / MEYDAN'},kalkinma:{center:[39.7567,40.9924],zoom:16,label:'KALKINMA'},trabzon:{center:[39.751,40.999],zoom:13.5,label:'TRABZON / ORTAHİSAR'}};
    document.querySelector('#sceneLocation').textContent=(regions[region]||regions.campus).label;
    const target=regions[region]||regions.campus;if(this.leaflet){this.leaflet.setView([target.center[1],target.center[0]],target.zoom);return;}
    this.map?.flyTo({...target,pitch:this.mode==='3d'?48:0,bearing:this.map.getBearing(),duration:this.motion?0:1500});
  }
  updateCompass(){const icon=document.querySelector('#mapCompass');if(icon)icon.style.transform=`rotate(${-this.map.getBearing()}deg)`;}
  camera(action){
    if(action==='export')return this.exportImage();if(action==='fallback')return this.fallback();if(this.leaflet)return this.notice('Bu kamera için sayfayı yenileyerek 3D haritaya dönün.');if(!this.ready)return;const wasTouring=this.touring;this.stop();if(action==='tour'&&wasTouring)return;
    if(action==='dimension'||action==='3d'||action==='2d'){this.mode=action==='dimension'?(this.mode==='2d'?'3d':'2d'):action;this.map.easeTo({pitch:this.mode==='3d'?48:0,duration:this.motion?0:700});this.syncCameraControls(this.mode);}
    if(action==='buildings'){this.buildings=!this.buildings;this.applyBuildings();}
    if(action==='motion'){this.motion=!this.motion;this.pressed('motion',!this.motion);}
    if(action==='rotate-left'||action==='rotate-right')this.map.easeTo({bearing:this.map.getBearing()+(action==='rotate-left'?-30:30),duration:this.motion?0:450});
    if(action==='north')this.map.easeTo({bearing:0,duration:this.motion?0:450});
    if(action==='light'){this.night=!this.night;this.map.setLight({anchor:'map',color:this.night?'#c6ddff':'#fff9eb',intensity:this.night?.2:.4,position:[1.5,210,this.night?80:35]});for(const layer of ['buildings','trabzon-buildings'])if(this.map.getLayer(layer))this.map.setPaintProperty(layer,'fill-extrusion-color',this.night?'#557982':['interpolate',['linear'],['get','height'],3,'#b6c7c9',18,'#d9e1dc',50,'#91aaaf']);this.pressed('light',this.night);}
    if(action==='heat'){this.heat=!this.heat;this.map.setLayoutProperty('demand','visibility',this.heat?'visible':'none');this.pressed('heat',this.heat);document.querySelector('#demandKey').hidden=!this.heat;}
    if(action==='relief'){const enabled=!this.map.getTerrain();if(enabled&&!this.map.getSource('elevation'))this.map.addSource('elevation',{type:'raster-dem',tiles:['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],tileSize:256,encoding:'terrarium',maxzoom:13,attribution:'Terrain: Mapzen / AWS'});this.map.setTerrain(enabled?{source:'elevation',exaggeration:1}:null);this.pressed('relief',enabled);}
    if(action==='tour'){if(this.motion)return this.notice('Azaltılmış hareket tercihi nedeniyle otomatik uçuş kapalı.');const points=this.payload?.plan?.stops?.length?this.payload.plan.stops.map(s=>(this.payload.allBins||this.payload.bins).find(b=>b.id===s.id)).filter(Boolean):this.payload?.bins;if(!points?.length)return;let i=0;this.touring=true;const next=()=>{if(!this.touring||document.hidden)return;const b=points[i++%points.length];this.map.flyTo({center:[b.lng,b.lat],zoom:16.8,pitch:55,bearing:(i*30)%360,duration:3000});this.timer=setTimeout(next,4200);};next();this.pressed('tour',true);}
  }
  cancelTour(){clearTimeout(this.timer);this.timer=null;this.touring=false;this.pressed('tour',false);}
  stop(){this.cancelTour();this.map?.stop();}
  async fullscreen(){const el=document.querySelector('.map-card'),enabled=!el.classList.contains('map-expanded');el.classList.toggle('map-expanded',enabled);if(enabled&&!document.fullscreenElement&&el.requestFullscreen){try{await el.requestFullscreen();}catch{/* CSS fullscreen stays available. */}}else if(!enabled&&document.fullscreenElement)try{await document.exitFullscreen();}catch{}this.invalidateSize();}
  exportImage(){
    if(!this.map||!this.ready)return this.notice('PNG için 3D görünüm gerekli.');this.stop();this.map.once('render',()=>{try{const source=this.map.getCanvas(),canvas=document.createElement('canvas');canvas.width=source.width;canvas.height=source.height;const ctx=canvas.getContext('2d');ctx.drawImage(source,0,0);ctx.scale(source.width/source.clientWidth,source.width/source.clientWidth);ctx.font='bold 12px sans-serif';ctx.textAlign='center';for(const b of this.payload.bins){const p=this.map.project([b.lng,b.lat]);ctx.fillStyle=GCMapScene.colors[b.color];ctx.beginPath();ctx.roundRect(p.x-22,p.y-32,44,25,6);ctx.fill();ctx.fillStyle='#102733';ctx.fillText(b.fill_percent==null?'?':Math.round(b.fill_percent)+'%',p.x,p.y-15);}ctx.textAlign='left';ctx.fillStyle='#102733';ctx.fillRect(0,source.clientHeight-40,source.clientWidth,40);ctx.fillStyle='white';ctx.font='9px sans-serif';ctx.fillText('GC · © OSM / ODbL · Imagery © Esri, Maxar, Earthstar Geographics, GIS User Community',8,source.clientHeight-24);ctx.fillText('Eksik bina yükseklikleri tahmini. Simülasyon ve canlı sensör ayrı kaynaklardır.',8,source.clientHeight-9);const a=document.createElement('a');a.download='gc-operasyon.png';a.href=canvas.toDataURL();a.click();}catch{this.notice('Görsel aktarılamadı; tarayıcı ekran görüntüsünü kullanın.');}});this.map.triggerRepaint();
  }
  fallback(){
    if(this.leaflet)return;this.driver?.close();this.stop();this.endMeter();this.map?.remove();this.map=null;this.container.innerHTML='';this.ready=false;this.markers.clear();if(!window.L)return this.notice('Harita açılamadı. Kutu listesi ve sefer sonuçları kullanılabilir.');
    this.container.setAttribute('aria-busy','false');
    this.leaflet=L.map(this.container).setView([40.9916,39.7723],16);this.fallbackTile=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors · Imagery © Esri, Maxar, Earthstar Geographics, GIS User Community',maxZoom:19}).addTo(this.leaflet);document.querySelector('#sceneStatus').textContent='2D YEDEK · ROTA VE KUTULAR KORUNUR';this.notice('2D yedek açık. 3D görünüm için sayfayı yenileyin.');this.renderFallback(this.payload);
  }
  renderFallback(p){if(!p)return;this.fallbackLayers?.forEach(l=>this.leaflet.removeLayer(l));this.fallbackLayers=[];const numbers=new Map((p.plan?.stops||[]).map((s,i)=>[s.id,i+1]));for(const b of p.bins){const marker=L.circleMarker([b.lat,b.lng],{radius:10,color:'#fff',weight:2,fillColor:GCMapScene.colors[b.color],fillOpacity:1}).addTo(this.leaflet).bindTooltip(`${numbers.has(b.id)?numbers.get(b.id)+'. durak · ':''}${b.id} · ${b.fill_percent==null?'Belirsiz':b.fill_percent+'%'}`);marker.on('click',()=>this.selectBin(b.id));this.fallbackLayers.push(marker);}if(p.plan?.stops.length)this.fallbackLayers.push(L.polyline(p.plan.geometry,{color:'#087f63',weight:6,dashArray:p.plan.road_geometry?null:'8 8'}).addTo(this.leaflet));const launch=document.querySelector('#driverLaunch');if(launch)launch.disabled=true;}
}
GCMapScene.imagery='https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
GCMapScene.colors={green:'#51d6a4',yellow:'#ffd166',red:'#ff8274',gray:'#b8c4cb'};
window.GCMapScene=GCMapScene;
