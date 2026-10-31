/* Driver cockpit: read-only route guidance. Never writes collections or telemetry. */
"use strict";
class GCDriverMode {
  constructor(scene){
    this.scene=scene;this.root=document.querySelector('.map-card');this.panel=document.querySelector('#driverCockpit');this.follow=true;
    document.querySelector('#driverLaunch').addEventListener('click',()=>this.open());
    this.panel.addEventListener('click',e=>{const action=e.target.closest('[data-drive]')?.dataset.drive;if(action)this.action(action);});
    document.addEventListener('keydown',e=>{if(!this.active)return;if(e.key==='Escape')this.close();if(e.key==='Tab'){const controls=[...this.panel.querySelectorAll('button')].filter(b=>!b.disabled);const first=controls[0],last=controls.at(-1);if(e.shiftKey&&(document.activeElement===first||document.activeElement===this.panel)){e.preventDefault();last?.focus();}else if(!e.shiftKey&&(document.activeElement===last||document.activeElement===this.panel)){e.preventDefault();first?.focus();}}});
    document.addEventListener('fullscreenchange',()=>{if(this.active){if(!document.fullscreenElement)this.nativeFullscreen=false;this.scene.invalidateSize();}});
  }
  sync(payload){
    if(!this.active)return;
    if(!payload.plan||payload.plan.id!==this.plan.id){this.close();this.scene.notice('Plan değişti. Yeni plan için şoför modunu tekrar açın.');return;}
    this.plan=payload.plan;this.updateUI();
  }
  async open(){
    const p=this.scene.payload;if(!this.scene.ready||!p?.plan?.stops.length)return;
    this.scene.stop();this.plan=p.plan;this.path=GCRouteMath.route(this.plan.geometry.map(c=>[c[1],c[0]]));if(this.path.length<1)return;
    let previous=0;this.stops=this.plan.stops.map(s=>{const bin=(p.allBins||p.bins).find(b=>b.id===s.id);const snap=bin?GCRouteMath.nearest(this.path,[bin.lng,bin.lat],previous):{meters:previous};previous=Math.max(previous,snap.meters);return {...s,meters:previous};});
    this.maneuvers=this.plan.maneuvers||[];
    this.before={center:this.scene.map.getCenter(),zoom:this.scene.map.getZoom(),pitch:this.scene.map.getPitch(),bearing:this.scene.map.getBearing()};
    this.active=true;this.mode='preview';this.progress=0;this.stopIndex=0;this.speed=0;this.accuracy=null;this.gpsTime=null;this.follow=true;this.position=this.path.points[0];this.root.classList.add('driver-mode');this.panel.hidden=false;this.panel.focus();
    this.message('Durak geçişleri önizlemedir; toplama kaydı oluşturmaz. GPS, izin verdiğinizde yalnız bu cihazda işlenir.');
    const el=document.createElement('div');el.className='driver-truck';el.innerHTML='<svg viewBox="0 0 48 64" aria-hidden="true"><path d="M24 1 43 30H31v24H17V30H5Z" fill="#f8fffc" stroke="#0b765e" stroke-width="3"/></svg><span>GC</span>';
    this.truck=new maplibregl.Marker({element:el,anchor:'center',rotationAlignment:'map'}).setLngLat(this.position).addTo(this.scene.map);
    // CSS is the guaranteed fullscreen fallback when the browser declines native fullscreen.
    if(!document.fullscreenElement&&this.root.requestFullscreen){try{await this.root.requestFullscreen();this.nativeFullscreen=true;}catch{this.nativeFullscreen=false;}}
    this.scene.invalidateSize();this.paintPosition(GCRouteMath.at(this.path,0),true);this.updateUI();
  }
  action(action){
    if(action==='close')return this.close();if(action==='demo')return this.demo();if(action==='gps')return this.gps();if(action==='pause')return this.pause();
    if(action==='follow'){this.follow=true;this.paintPosition(this.lastPoint||GCRouteMath.at(this.path,this.progress),true);}
    if(action==='next'||action==='previous'){this.stopIndex=Math.max(0,Math.min(this.stops.length, this.stopIndex+(action==='next'?1:-1)));this.updateUI();}
  }
  demo(){
    this.pause();if(this.scene.motion){this.message('Sunum animasyonları kapalı. Haritada Diğer seçenekler → Sunum animasyonları ile açabilirsiniz; durak önizlemesi kullanılabilir.');return;}
    if(this.progress>=this.path.length)this.progress=0;this.mode='demo';this.running=true;this.follow=true;let last=performance.now(),lastPaint=0;
    const tick=now=>{if(!this.running||!this.active)return;const dt=Math.min(.25,(now-last)/1000);last=now;this.progress=Math.min(this.path.length,this.progress+this.path.length/150*dt);if(now-lastPaint>=100){lastPaint=now;this.advanceStop();this.paintPosition(GCRouteMath.at(this.path,this.progress));this.updateUI();}if(this.progress>=this.path.length){this.pause();this.message('Demo sürüşü bitti. Toplama kaydı oluşturulmadı.');return;}this.frame=requestAnimationFrame(tick);};this.frame=requestAnimationFrame(tick);this.updateUI();
  }
  gps(){
    if(!this.plan.road_geometry)return this.message('GPS rota takibi için yol ağı çizgisi olan bir sefer oluşturun. Yaklaşık çizgi sürüş yolu değildir.');
    this.pause();if(!navigator.geolocation)return this.message('Bu tarayıcı konum servisini desteklemiyor. Demo sürüşünü kullanabilirsiniz.');
    if(!window.isSecureContext)return this.message('GPS için HTTPS veya bu cihazda localhost gerekir.');
    this.mode='gps';this.accuracy=null;this.message('Konum izni bekleniyor…');this.updateUI();
    this.watch=navigator.geolocation.watchPosition(pos=>{
      if(!this.active||this.mode!=='gps')return;const {longitude,latitude,accuracy,speed,heading}=pos.coords;
      this.accuracy=accuracy;this.speed=speed==null?null:speed*3.6;this.gpsTime=pos.timestamp;
      if(accuracy>60){this.message(`GPS doğruluğu düşük (±${Math.round(accuracy)} m); rota ilerlemesi güncellenmedi.`);this.updateUI();return;}
      this.position=[longitude,latitude];const snap=GCRouteMath.nearest(this.path,this.position,Math.max(0,this.progress-50));this.offRoute=snap.distance>Math.max(40,accuracy*1.5);
      if(!this.offRoute)this.progress=snap.meters;
      this.advanceStop();
      const point=GCRouteMath.at(this.path,this.progress);point.position=this.position;if(heading!=null)point.bearing=heading;
      this.paintPosition(point);this.message(this.offRoute?'Rota dışındasınız. Güvenli biçimde planlanan yola dönün; otomatik yeniden rota yok.':'Konum cihazda işleniyor · otomatik toplama kaydı yok.');this.updateUI();
    },()=>{this.pause();this.message('GPS alınamadı. Konum iznini ve bağlantıyı kontrol edin; demo sürüşü kullanılabilir.');},{enableHighAccuracy:true,maximumAge:2000,timeout:15000});
  }
  pause(){cancelAnimationFrame(this.frame);this.frame=null;this.running=false;if(this.watch!=null){navigator.geolocation.clearWatch(this.watch);this.watch=null;}if(this.mode==='gps')this.mode='preview';if(this.active)this.updateUI();}
  unfollow(){if(!this.active)return;this.follow=false;this.updateUI();}
  advanceStop(){this.stopIndex=this.stops.findIndex(s=>s.meters>this.progress-12);if(this.stopIndex<0)this.stopIndex=this.stops.length;}
  paintPosition(point,immediate=false){
    if(!this.active||!point)return;this.lastPoint=point;this.position=point.position;this.truck.setLngLat(point.position).setRotation(point.bearing);
    if(this.follow)this.scene.map.easeTo({center:point.position,zoom:17.2,pitch:50,bearing:point.bearing,padding:{top:100,bottom:170,left:0,right:0},duration:immediate||this.scene.motion?0:180});
  }
  message(text){document.querySelector('#driverMessage').textContent=text;}
  updateUI(){
    if(!this.active)return;const q=s=>document.querySelector(s),next=this.stops[this.stopIndex],remaining=Math.max(0,this.path.length-this.progress),distance=next?Math.max(0,next.meters-this.progress):remaining;
    q('#driveMode').textContent=this.mode==='gps'?'GPS · CANLI KONUM':this.mode==='demo'?(this.running?'DEMO SÜRÜŞÜ · SİMÜLASYON':'DEMO DURAKLATILDI'):'SEFER ÖNİZLEMESİ';
    q('#driverTarget').textContent=next?next.name:'Başlangıç deposuna dönüş';q('#driverDistance').textContent=distance>=1000?(distance/1000).toFixed(1)+' km':Math.round(distance)+' m';q('#driverOrdinal').textContent=next?`${this.stopIndex+1} / ${this.stops.length} DURAK · ${next.id}`:'TÜM DURAKLAR İNCELENDİ';
    q('#driverRemaining').textContent=(remaining/1000).toFixed(2)+' km';q('#driverSpeed').textContent=this.mode==='gps'&&this.speed!=null?Math.round(this.speed)+' km/sa':'—';q('#driverProgress').value=this.path.length?this.progress/this.path.length*100:0;
    q('#driverRoad').textContent=!this.plan.road_geometry?'YAKLAŞIK ROTA · YÖNLENDİRME İÇİN KULLANMAYIN':this.plan.stale?'PLAN GİRDİLERİ DEĞİŞTİ · YENİDEN HESAPLAYIN':'PLANLANAN YOL · CANLI TRAFİK YOK';
    q('[data-drive="follow"]').setAttribute('aria-pressed',String(this.follow));q('[data-drive="demo"]').setAttribute('aria-pressed',String(this.running));q('[data-drive="gps"]').setAttribute('aria-pressed',String(this.mode==='gps'));
    q('[data-drive="previous"]').disabled=this.stopIndex===0;q('[data-drive="next"]').disabled=this.stopIndex>=this.stops.length;
    q('[data-drive="gps"]').disabled=!this.plan.road_geometry;
    q('#driverAccuracy').textContent=this.mode==='gps'?(this.accuracy==null?'GPS konumu bekleniyor':`GPS ±${Math.round(this.accuracy)} m${this.gpsTime?' · '+new Date(this.gpsTime).toLocaleTimeString('tr-TR'):''}`):'Rota üzerinde 150 saniyelik demo';
    const turn=this.plan.road_geometry?this.maneuvers.find(m=>m.type!=='depart'&&m.distance_from_start>this.progress+8):null;
    const instruction=GCRouteMath.instruction(turn);q('#driverDirection').textContent=turn?instruction.icon:'◎';
    q('#driverManeuver').textContent=turn?`${Math.round(turn.distance_from_start-this.progress)} m sonra · ${instruction.text}${turn.name?' · '+turn.name:''}`:this.plan.road_geometry?'Sıradaki durağa rota üzerinden ilerleyin':'Durak önizlemesi · sürüş yönlendirmesi değildir';
  }
  close(){
    if(!this.active)return;this.pause();this.active=false;this.truck?.remove();this.root.classList.remove('driver-mode');this.panel.hidden=true;
    if(this.nativeFullscreen&&document.fullscreenElement===this.root)document.exitFullscreen().catch(()=>{});this.nativeFullscreen=false;
    this.scene.map?.easeTo({...this.before,padding:{top:0,bottom:0,left:0,right:0},duration:0});this.scene.invalidateSize();document.querySelector('#driverLaunch').focus();
  }
}
window.GCDriverMode=GCDriverMode;
