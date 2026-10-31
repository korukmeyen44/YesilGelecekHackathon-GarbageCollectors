/* A capacity-normalized historical surface in fixed geographic coordinates.
   No current fill, generator rate, forecast, zoom or point-count normalization. */
"use strict";
const GCDemandModel = {
  radius: 180, // metres of local influence, not a municipal service boundary
  reference: 8, // percentage points/hour; fixed across filters and camera changes
  colors: [[113,55,193],[47,105,224],[40,183,114],[247,217,74],[248,142,44],[226,54,54]],
  status(bins, offline=false) {
    if(bins.some(b=>typeof b.demand?.available!=='boolean'))return {
      kind:'outdated',message:offline
        ? 'Kayıtlı görünümde geçmiş analizi yok. Sunucuya bağlanıp görünümü yenileyin.'
        : 'Çalışan backend eski sürümde; geçmiş analizini göndermiyor. Backend terminalinde Ctrl+C yapıp yeniden başlatın.'
    };
    const points=this.points(bins);
    if(!points.length)return {kind:'insufficient',message:bins.length
      ? 'Seçili kaynakta yeterli geçmiş yok. En az 24 saate yayılan 12 saat güvenilir gözlem gerekli; Simülasyon veya Tümü seçeneğini deneyin.'
      : 'Seçili kaynakta kutu yok; ısı haritası oluşturulamadı.'};
    const simulated=bins.filter(b=>b.demand?.available&&b.source==='simulated').length;
    return {kind:'ready',message:`${points.length}/${bins.length} kutuda yeterli geçmiş · ${simulated} simülasyon, ${points.length-simulated} canlı${offline?' · kayıtlı görünüm':''}`};
  },
  points(bins) {
    return bins.filter(b=>b.demand?.available && Number.isFinite(b.demand.rate_pph) &&
      Number.isFinite(b.lat) && Number.isFinite(b.lng) && b.capacity_l > 0)
      .map(b=>({id:b.id,lat:b.lat,lng:b.lng,capacity:b.capacity_l,rate:Math.max(0,b.demand.rate_pph)}));
  },
  at(points, lat, lng) {
    let weighted=0, capacity=0, nearest=Infinity;
    for(const p of points) {
      const x=(p.lng-lng)*111320*Math.cos(lat*Math.PI/180), y=(p.lat-lat)*111320;
      const d2=(x*x+y*y)/(this.radius*this.radius);
      if(d2>1)continue;
      const w=Math.exp(-4.5*d2)*p.capacity;
      weighted+=w*p.rate;capacity+=w;nearest=Math.min(nearest,d2);
    }
    return capacity ? {rate:weighted/capacity,alpha:Math.pow(1-nearest,.6)} : null;
  },
  color(rate) {
    const scaled=Math.max(0,Math.min(1,rate/this.reference))*(this.colors.length-1);
    const i=Math.min(this.colors.length-2,Math.floor(scaled)), mix=scaled-i;
    return this.colors[i].map((v,j)=>Math.round(v+(this.colors[i+1][j]-v)*mix));
  },
  surface(bins) {
    const points=this.points(bins);
    if(!points.length)return null;
    // Mercator coordinates make the image align with the map at every zoom/pitch.
    const R=6378137, project=(lat,lng)=>[R*lng*Math.PI/180,R*Math.log(Math.tan(Math.PI/4+lat*Math.PI/360))];
    const inverse=(x,y)=>[x/R*180/Math.PI,(2*Math.atan(Math.exp(y/R))-Math.PI/2)*180/Math.PI];
    const projected=points.map(p=>project(p.lat,p.lng));
    const padding=this.radius/Math.cos(points[0].lat*Math.PI/180);
    const west=Math.min(...projected.map(p=>p[0]))-padding, east=Math.max(...projected.map(p=>p[0]))+padding;
    const south=Math.min(...projected.map(p=>p[1]))-padding, north=Math.max(...projected.map(p=>p[1]))+padding;
    const scale=320/Math.max(east-west,north-south), width=Math.max(2,Math.ceil((east-west)*scale)), height=Math.max(2,Math.ceil((north-south)*scale));
    const pixels=new Uint8ClampedArray(width*height*4);
    for(let y=0;y<height;y++)for(let x=0;x<width;x++) {
      const [lng,lat]=inverse(west+(x+.5)*(east-west)/width,north-(y+.5)*(north-south)/height);
      const value=this.at(points,lat,lng);
      if(!value)continue;
      const offset=(y*width+x)*4;pixels.set(this.color(value.rate),offset);pixels[offset+3]=Math.round(210*value.alpha);
    }
    return {width,height,pixels,coordinates:[inverse(west,north),inverse(east,north),inverse(east,south),inverse(west,south)]};
  },
  image(surface) {
    const canvas=document.createElement('canvas');canvas.width=surface.width;canvas.height=surface.height;
    canvas.getContext('2d').putImageData(new ImageData(surface.pixels,surface.width,surface.height),0,0);
    return canvas.toDataURL('image/png');
  }
};
if(typeof window!=='undefined')window.GCDemandModel=GCDemandModel;
if(typeof module!=='undefined')module.exports=GCDemandModel;
