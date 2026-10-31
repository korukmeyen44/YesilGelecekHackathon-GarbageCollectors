/* Geometry shared by the driver view and its deterministic tests. Coordinates: [lng, lat]. */
"use strict";
(function(root){
  const R=6371000,rad=Math.PI/180;
  const distance=(a,b)=>{const x=(b[0]-a[0])*rad*Math.cos((a[1]+b[1])*rad/2),y=(b[1]-a[1])*rad;return Math.hypot(x,y)*R;};
  const bearing=(a,b)=>{const x=(b[0]-a[0])*rad;return (Math.atan2(Math.sin(x)*Math.cos(b[1]*rad),Math.cos(a[1]*rad)*Math.sin(b[1]*rad)-Math.sin(a[1]*rad)*Math.cos(b[1]*rad)*Math.cos(x))/rad+360)%360;};
  function route(points){const cumulative=[0];for(let i=1;i<points.length;i++)cumulative.push(cumulative.at(-1)+distance(points[i-1],points[i]));return {points,cumulative,length:cumulative.at(-1)||0};}
  function at(path,meters){
    const p=path.points;if(!p.length)return null;if(p.length===1)return {position:p[0],bearing:0,index:0};
    meters=Math.max(0,Math.min(path.length,meters));let i=1;while(i<path.cumulative.length-1&&path.cumulative[i]<meters)i++;
    const a=p[i-1],b=p[i],span=path.cumulative[i]-path.cumulative[i-1],t=span?(meters-path.cumulative[i-1])/span:0;
    return {position:[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t],bearing:bearing(a,b),index:i-1};
  }
  function nearest(path,position,minMeters=0){
    let best={distance:Infinity,meters:0,position:path.points[0]};
    const kx=R*rad*Math.cos(position[1]*rad),ky=R*rad;
    for(let i=1;i<path.points.length;i++){
      if(path.cumulative[i]<minMeters)continue;
      const a=path.points[i-1],b=path.points[i],ax=(a[0]-position[0])*kx,ay=(a[1]-position[1])*ky,dx=(b[0]-a[0])*kx,dy=(b[1]-a[1])*ky;
      const span=path.cumulative[i]-path.cumulative[i-1],minimum=span?Math.max(0,(minMeters-path.cumulative[i-1])/span):0;
      const t=Math.max(minimum,Math.min(1,-(ax*dx+ay*dy)/(dx*dx+dy*dy||1))),d=Math.hypot(ax+t*dx,ay+t*dy);
      if(d<best.distance)best={distance:d,meters:path.cumulative[i-1]+t*(path.cumulative[i]-path.cumulative[i-1]),position:[a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]};
    }return best;
  }
  function instruction(m){
    if(!m)return {text:'Planlanan yolda ilerleyin',icon:'↑'};
    if(m.type==='arrive')return {text:'Durağa varış',icon:'●'};
    if(m.type==='roundabout'||m.type==='rotary')return {text:m.exit?`Döner kavşakta ${m.exit}. çıkışı kullanın`:'Döner kavşaktan devam edin',icon:'↻'};
    if(m.modifier==='uturn')return {text:'U dönüşü',icon:'↶'};
    if(m.modifier?.includes('left'))return {text:m.modifier==='slight left'?'Hafif sola devam edin':'Sola dönün',icon:'↰'};
    if(m.modifier?.includes('right'))return {text:m.modifier==='slight right'?'Hafif sağa devam edin':'Sağa dönün',icon:'↱'};
    return {text:'Düz devam edin',icon:'↑'};
  }
  const api={distance,bearing,route,at,nearest,instruction};root.GCRouteMath=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
