/* Read-only projections from the fitted model. Never uses mock generator rates. */
"use strict";
const GCFutureModel = {
  project(bin, hours, threshold = 80) {
    if (!hours) return bin;
    const valid = bin.usable && bin.fill_percent != null && bin.forecast?.available && Number.isFinite(bin.forecast.rate_pph);
    const fill = valid ? Math.min(100, Math.max(0, bin.fill_percent + bin.forecast.rate_pph * hours)) : null;
    return {...bin, observed_fill_percent:bin.fill_percent, fill_percent:fill,
      projected:true, projection_hours:hours, projection_available:valid,
      color:fill == null ? 'gray' : fill >= 80 ? 'red' : fill >= 50 ? 'yellow' : 'green',
      projected_threshold:fill != null && fill >= threshold};
  },
  // Approximate solar elevation, NOAA fractional-year equations (UTC input).
  // https://gml.noaa.gov/grad/solcalc/solareqns.PDF
  lightAt(seconds, lat = 40.9915, lng = 39.7722) {
    const d = new Date(seconds * 1000), year = d.getUTCFullYear();
    const day = Math.floor((Date.UTC(year,d.getUTCMonth(),d.getUTCDate()) - Date.UTC(year,0,1))/86400000)+1;
    const hour = d.getUTCHours()+d.getUTCMinutes()/60+d.getUTCSeconds()/3600;
    const days = (Date.UTC(year+1,0,1)-Date.UTC(year,0,1))/86400000;
    const g = 2*Math.PI/days*(day-1+(hour-12)/24);
    const eq = 229.18*(.000075+.001868*Math.cos(g)-.032077*Math.sin(g)-.014615*Math.cos(2*g)-.040849*Math.sin(2*g));
    const dec = .006918-.399912*Math.cos(g)+.070257*Math.sin(g)-.006758*Math.cos(2*g)+.000907*Math.sin(2*g)-.002697*Math.cos(3*g)+.00148*Math.sin(3*g);
    const rad = Math.PI/180, ha = (hour*60+eq+4*lng)/4-180;
    const elevation = Math.asin(Math.sin(lat*rad)*Math.sin(dec)+Math.cos(lat*rad)*Math.cos(dec)*Math.cos(ha*rad))/rad;
    return {phase:elevation < -6 ? 'night' : elevation < 6 ? 'twilight' : 'day', elevation};
  }
};
if (typeof window !== 'undefined') window.GCFutureModel = GCFutureModel;
if (typeof module !== 'undefined') module.exports = GCFutureModel;
