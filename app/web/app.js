"use strict";
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const icon = (name, cls = "") => `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const nf = (value, digits = 0) => value == null ? "—" : Number(value).toLocaleString("tr-TR", {maximumFractionDigits: digits});
const date = (seconds, withDay = true) => new Date(seconds * 1000).toLocaleString("tr-TR", {timeZone:"Europe/Istanbul", ...(withDay ? {day:"2-digit",month:"short"} : {}),hour:"2-digit",minute:"2-digit"});
const sourceBadge = source => `<span class="badge ${source === "live" ? "live" : "simulated"}">${source === "live" ? '<span class="live-dot"></span> CANLI SENSÖR' : 'SİMÜLASYON'}</span>`;
const colors = {green:"#3b9b74",yellow:"#e8b347",red:"#e46c62",gray:"#99a5aa"};
const qualityLabels = {ok:"Normal",degraded:"Kısmi kalite",invalid:"Geçersiz ölçüm",missing:"Veri bekleniyor",uncalibrated:"Kalibrasyon gerekli",calibration_changed:"Kalibrasyon değişti",outside_geometry:"Geometri dışı",change_pending:"Değişim doğrulanıyor"};
const state = {data:null, view:"overview", source:"all", fill:"all", queue:"priority", search:"", selected:null,
  scope:"demo", online:true, token:"", loading:false, planning:false, offline:false, futureHours:0, lighting:"auto", quickStarting:false, map:null, markers:new Map(), routeLayers:[], detailVersion:0, focusBeforeDrawer:null};
let toastTimer;
function toast(message, error = false) {
  const el = $("#toast"); el.textContent = message; el.classList.toggle("error", error); el.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.hidden = true, 5000);
}
async function api(path, body) {
  if(body !== undefined && state.offline) throw new Error("Bağlantı yok. Bu işlem için sunucuya yeniden bağlanın.");
  const controller = new AbortController(), timer = setTimeout(()=>controller.abort(),body === undefined ? 10000 : 45000);
  let response;
  try { response = await fetch(path, {signal:controller.signal,method:body === undefined ? "GET" : "POST", cache:"no-store",
    headers:{...(body === undefined ? {} : {"Content-Type":"application/json"}), ...(state.token ? {Authorization:`Bearer ${state.token}`} : {})},
    ...(body === undefined ? {} : {body:JSON.stringify(body)})}); }
  catch(error){if(controller.signal.aborted)throw new Error("Sunucu yanıtı gecikti. Bağlantıyı kontrol edip tekrar deneyin.");throw error;}
  finally{clearTimeout(timer);}
  if (response.status === 401) {
    if (!$("#authDialog").open) $("#authDialog").showModal();
    const error = new Error("Erişim anahtarı gerekli."); error.auth = true; throw error;
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "İşlem tamamlanamadı.");
  return data;
}
const requestKey = () => crypto.randomUUID ? crypto.randomUUID() : `gc-${Date.now()}-${Math.random().toString(36).slice(2)}`;
async function refresh() {
  if (state.loading) return;
  state.loading = true;
  try {
    state.data = await api("/api/dashboard");
    state.offline = false;
    if(!state.token) await GCPWA.snapshot("put",{savedAt:Date.now(),data:state.data});
    $("#connectionBanner").hidden = true;
    $("#connectionLabel").textContent = "Sistem bağlı";
    $("#connectionDot").style.background = "#2caa79";
    render();
    if (state.selected && !$("#detailDrawer").hidden) await openDetail(state.selected, false);
  } catch (error) {
    if(!error.auth) {
      const saved = state.data ? null : await GCPWA.snapshot("get");
      if(saved?.data) state.data = saved.data;
      state.offline = true;
      if(state.data) {
        state.data.bins = state.data.bins.map(b=>b.source === "live" ? {...b,freshness:b.fill_percent == null ? "missing":"stale",usable:false,color:"gray",forecast:{...b.forecast,available:false}} : b);
        render();
      }
    } else { await GCPWA.snapshot("delete"); }
    $("#connectionBanner").hidden = false;
    $("#connectionBanner").textContent = state.data ? `Çevrimdışı · ${date(state.data.real_now)} tarihinde alınan son görünüm. Yeni plan ve kayıt işlemleri duraklatıldı; kayıtlı yol rotası önizlenebilir.` : "Sunucuya ulaşılamıyor. Bağlantı kurulunca veriler otomatik gelecek.";
    $("#connectionLabel").textContent = "Çevrimdışı";
    $("#connectionDot").style.background = "#d8a84c";
    if(!state.data) $("#binList").innerHTML = `<div class="empty-state">${icon("signal")}<strong>Sunucu bağlantısı bekleniyor</strong>${esc(error.message)}</div>`;
  } finally { state.loading = false; }
}
function metric(label, value, unit, note, ico, accent = false) {
  return `<article class="metric${accent ? " accent" : ""}"><div class="metric-label">${label}</div><span class="metric-icon">${icon(ico)}</span><div class="metric-value">${value}<small>${unit}</small></div><div class="metric-note">${note}</div></article>`;
}
function render() {
  const d = state.data;
  const live = d.bins.filter(b => b.source === "live" && b.freshness === "fresh").length;
  const candidates = d.bins.filter(b => b.selected).length;
  const high = d.bins.filter(b => b.fill_percent != null && b.fill_percent >= 80).length;
  const p = selectedPlan(), savings = p?.stops.length ? p.savings : null;
  $("#clockLabel").textContent = date(d.real_now);
  $("#navAlertCount").textContent = d.alerts.filter(a => a.kind !== "forecast").length;
  $("#metrics").innerHTML = metric("İzlenen çöp kutusu", nf(d.bins.length), "kutu", `<strong>${live}/${d.bins.filter(b=>b.source==="live").length} canlı</strong> · ${d.bins.filter(b=>b.source==="simulated").length} simüle`, "bin")
    + metric("Toplama önerilen", nf(candidates), "kutu", `${high} yüksek doluluk · kurallarla önceliklendirildi`, "route")
    + metric("Tahmini süre farkı", savings ? nf(savings.minutes,1) : "—", "dk", p ? "Son plan · tek seferlik karşılaştırma" : "İlk rotanızı oluşturun", "clock")
    + metric("Tahmini CO₂ farkı", savings ? nf(savings.co2_kg,2) : "—", "kg", p ? `${p.mode === "road" ? "Yol ağı" : "Yaklaşık mesafe"} · yakıt varsayımlarıyla` : "Rota karşılaştırması sonrasında hesaplanır", "leaf", true);
  renderFuture(); renderMap(); renderQueue(); renderPreviews(); renderPlanner(); renderRouteResults(); renderHealth(); renderImpact();
  $$("[data-advance], #applyFault, #settingsForm button[type=submit]").forEach(button=>button.disabled=state.offline);
  $("#demoClock").textContent = date(d.demo_now);
  if (!$("#demoDialog").open) {
    $("#demoBin").innerHTML = d.bins.filter(b=>b.source==="simulated").map(b=>`<option value="${b.id}">${b.id} · ${esc(b.name)}</option>`).join("");
  }
}
function visibleBins() {
  if (!state.data) return [];
  const source = state.view === "route" ? (state.scope === "demo" ? "simulated" : "live") : state.source;
  const fill = state.view === "route" ? "all" : state.fill;
  return projectionBins().filter(b => (source === "all" || b.source === source) && (fill === "all" || b.color === fill));
}
function selectedPlan() {
  return state.data?.latest_plans?.[state.scope] || (state.data?.latest_plan?.scope === state.scope ? state.data.latest_plan : null);
}
function projectionBins() {
  return state.data.bins.map(b=>GCFutureModel.project(b,state.futureHours,state.data.settings.threshold));
}
function renderFuture() {
  const hours=state.futureHours, live=state.view === "route" ? state.scope === "live" : state.source === "live";
  const base=live ? state.data.real_now : state.data.demo_now, target=base+hours*3600;
  $("#futureHours").value=hours;
  $("#futureHours").setAttribute("aria-valuetext",hours ? `${hours} saat sonrası` : "Şimdi");
  $("#futureTime").textContent=hours ? `+${hours} saat · ${date(target,false)}` : "Şimdi";
  $("#futureDate").textContent=date(target);
  const forecast=visibleBins().filter(b=>b.projection_available);
  $("#futureCaption").textContent=hours ? `${forecast.filter(b=>b.projected_threshold).length} kutu eşik üzerinde · öngörü` : `${live ? "Canlı sensör" : "Simülasyon"} · mevcut ölçümler`;
  const phase=state.lighting === "auto" ? GCFutureModel.lightAt(target).phase : state.lighting;
  $("#dayPhaseIcon use").setAttribute("href",phase === "night" ? "#i-moon" : "#i-sun");
  state.map?.setLighting(phase);
  $(".scene-hud").dataset.future=String(hours>0);
  $(".map-footnote").innerHTML=icon("info")+(hours ? `+${hours} saat öngörüsü · Toplama yapılmadığı ve mevcut dolum eğiliminin sürdüğü varsayılır. Ayrıntılar mevcut ölçümü gösterir.` : "Dairelerde doluluk (%) · OSM bina tabanları · eksik yükseklikler tahmini.");
  $("#quickDriveLabel").textContent=state.quickStarting ? "Hazırlanıyor" : state.scope === "live" ? "Canlı sefer" : "Demo seferi";
  $("#quickDrive").setAttribute("aria-label",`${state.scope === "live" ? "Canlı sensör" : "Simülasyon"} rotasını oluştur ve şoför modunu başlat`);
}
function setFuture(hours) {
  state.futureHours=Math.max(0,Math.min(24,Number(hours)||0));
  if(state.data){renderFuture();renderMap();renderQueue();}
}
function initMap() {
  state.map = new GCMapScene($("#map"),id=>openDetail(id));
  state.map.driver = new GCDriverMode(state.map);
}
function renderMap() {
  const bins=visibleBins();$("#mapCount").textContent=`${bins.length} kutu`;
  const plan=state.futureHours ? null : selectedPlan();
  const source=state.view === "route" ? (state.scope === "demo" ? "simulated" : "live") : state.source;
  const demandBins=state.data.bins.filter(b=>source === "all" || b.source === source);
  state.map?.render({bins,demandBins,allBins:state.data.bins,plan,depot:state.data.depot,selected:state.selected,futureHours:state.futureHours,offline:state.offline});
}
function renderQueue() {
  const all = visibleBins().filter(b=>`${b.id} ${b.name} ${b.area}`.toLocaleLowerCase("tr").includes(state.search.toLocaleLowerCase("tr")));
  const prioritized = all.filter(b=>state.futureHours ? b.projected_threshold : b.selected);
  const bins = (state.queue === "priority" ? prioritized : all).sort((a,b)=>(state.futureHours ? (b.fill_percent??-1)-(a.fill_percent??-1) : b.priority-a.priority) || a.id.localeCompare(b.id));
  $("#priorityCount").textContent = prioritized.length;
  $("#queueSubtitle").textContent = state.futureHours ? `+${state.futureHours} sa · tahmini eşik aşımı` : `${prioritized.length} kutu için toplama önerisi`;
  $("#queueToggleCount").textContent=prioritized.length;
  $("#binList").innerHTML = bins.length ? bins.map(b=>`<button class="bin-row${state.selected===b.id?" selected":""}" data-bin="${b.id}"><span class="bin-mini">${icon("bin")}<i class="status-dot ${b.color}"></i></span><span class="bin-row-text"><strong>${esc(b.name)}</strong><small>${esc(b.id)} · ${b.source==="live"?"Canlı sensör":esc(b.area)}${b.fast_filling?" · Hızlı dolum":""}</small></span><span class="bin-row-value ${b.color}-text">${b.fill_percent==null?"—":(b.projected?"≈":"")+"%"+nf(b.fill_percent)}</span></button>`).join("") : `<div class="empty-state">${icon("check")}<strong>Bu filtrede kutu bulunamadı</strong>Tüm kutular sekmesini veya filtreleri deneyin.</div>`;
}
function renderPreviews() {
  const forecasts = state.data.bins.filter(b=>b.forecast.available && b.fill_percent < state.data.settings.threshold).sort((a,b)=>a.forecast.hours_to_threshold-b.forecast.hours_to_threshold).slice(0,3);
  $("#forecastPreview").innerHTML = forecasts.map(b=>`<button class="forecast-row" data-bin="${b.id}"><span class="status-dot ${b.color}"></span><div><strong>${esc(b.name)}</strong><small>${esc(b.id)} · ${nf(b.forecast.rate_pph,1)} yüzde puan / saat · ${b.source==="live"?"Canlı":"Simülasyon"}</small></div><svg class="mini-spark" viewBox="0 0 64 25" aria-hidden="true"><path d="M1 23 11 21 20 18 29 19 38 12 47 10 56 4 63 2"/></svg><b>${nf(b.forecast.hours_to_threshold,1)} sa</b></button>`).join("") || '<div class="empty-state">Yeterli geçmişi olan kutularda tahminler burada görünür.</div>';
  const alerts = [...state.data.alerts].sort((a,b)=>(a.source==="live"?-1:0)-(b.source==="live"?-1:0)).slice(0,3);
  $("#healthPreview").innerHTML = alerts.map(a=>`<button class="health-row" data-bin="${a.bin_id}"><span class="status-dot ${a.severity==="danger"?"red":a.severity==="warning"?"yellow":"gray"}"></span><div><strong>${esc(a.name)}</strong><small>${esc(a.message.slice(0,72))}${a.message.length>72?"…":""}</small></div>${sourceBadge(a.source)}</button>`).join("") || `<div class="empty-state">${icon("check")}<strong>Açık sistem uyarısı yok</strong>Ölçüm ve bağlantılar izleniyor.</div>`;
}
function setView(view) {
  if (!["overview","route","health","impact"].includes(view)) view="overview";
  state.view=view; if(view === "route")state.futureHours=0; const labels={overview:["Genel bakış","Trabzon operasyon merkezi","Dolulukları izleyin, toplama önceliklerini belirleyin ve seferleri yönetin."],route:["Rota planlama","Toplama ve sefer planlama","Toplama adaylarını seçin, seferi planlayın ve referansla karşılaştırın."],health:["Sensör sağlığı","Sensör ve bağlantı sağlığı","Bağlantı kesintilerini ve ölçüm belirsizliklerini birlikte izleyin."],impact:["Etki analizi","Operasyonun tahmini etkisi","Mesafe, süre ve yakıt varsayımlarına dayalı şeffaf karşılaştırma."]};
  $("#breadcrumbView").textContent=labels[view][0]; $("#pageTitle").textContent=labels[view][1]; $("#pageSubtitle").textContent=labels[view][2];
  $$("nav [data-view]").forEach(b=>{b.classList.toggle("active",b.dataset.view===view); if(b.dataset.view===view)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current");});
  $("#mapWorkspace").hidden=!["overview","route"].includes(view);
  $("#metrics").hidden=!["overview","route"].includes(view);
  $("#queueToggle").hidden=view!=="overview"; $("#futureBar").hidden=view!=="overview";
  $("#queuePanel").hidden=view!=="overview"; $("#plannerPanel").hidden=view!=="route";
  $("#overviewExtras").hidden=view!=="overview"; $("#routeResults").hidden=view!=="route";
  $("#healthPage").hidden=view!=="health"; $("#impactPage").hidden=view!=="impact";
  $(".map-filters").hidden=view==="route"; $("#sidebar").classList.remove("open");
  $(".map-footnote").innerHTML = icon("info") + (view === "route" ? "Renkli daireler doluluk (%), koyu rozetler durak sırası. Bina tabanları OSM; eksik yükseklikler tahmini." : "Dairelerde doluluk (%) · OSM bina tabanları · eksik yükseklikler tahmini.");
  if(state.data)render(); if(state.map)requestAnimationFrame(()=>state.map.invalidateSize());
  history.replaceState(null,"",`#${view}`);
}
function renderPlanner() {
  $("#quickDrive").disabled=!state.data||state.planning||state.quickStarting;
  const bins=state.data.bins.filter(b=>b.source===(state.scope==="demo"?"simulated":"live"));
  const chosen=bins.filter(b=>b.selected), load=chosen.reduce((n,b)=>n+b.estimated_load_l,0), s=state.data.settings;
  const p=selectedPlan();
  $("#plannerPanel").innerHTML=`<div class="card-heading"><div><h2>Sefer oluştur</h2><p>Tek araç · başlangıç noktasına dönüş</p></div><span class="soft-icon green-soft">${icon("truck")}</span></div><div class="form-field"><label for="planScope">Planlama kaynağı</label><select id="planScope"><option value="demo"${state.scope==="demo"?" selected":""}>Simülasyon · ${state.data.bins.filter(b=>b.source==="simulated").length} kutu</option><option value="live"${state.scope==="live"?" selected":""}>Canlı sensörler · ${bins[0]?.source==="live"?bins.length:state.data.bins.filter(b=>b.source==="live").length} kutu</option></select></div><div class="plan-summary"><div><span>Toplama adayı</span><strong>${chosen.length} kutu</strong></div><div><span>Yaklaşık yük varsayımı</span><strong>${nf(load)} L</strong></div><div><span>Araç hacim varsayımı</span><strong>${nf(s.truck_capacity_l)} L</strong></div><div><span>Sonraki ziyaret</span><strong>${nf(s.horizon_hours,1)} saat sonra</strong></div><div><span>Sefer üst sınırı</span><strong>${nf(s.shift_minutes)} dk</strong></div></div><label class="checkbox-row"><input id="onlineRoads" type="checkbox"${state.online?" checked":""}>Yol ağı üzerinden hesapla</label><button class="button button-primary full-width" id="generatePlan"${state.planning||state.offline?" disabled":""}>${state.planning?'<span class="spinner"></span> Rota hesaplanıyor…':icon("route")+"Önerilen rotayı oluştur"}</button>${p?`<div class="plan-status">${p.completed_at?"✓ Toplama kaydı tamamlandı":p.stale?"⚠ Girdiler değişti; planı yeniden oluşturun.":"Son plan: "+date(p.created_at)}</div>`:""}<div class="planner-bottom">${icon("info")} Canlı kutular ve demo kutuları farklı zamanlara sahiptir; ayrı planlanır. Kutu panelinden elle ekleme/çıkarma yapabilirsiniz.</div>`;
}
async function generatePlan(forceRoad=false) {
  if(state.planning)return null; state.planning=true;renderPlanner();
  try {
    const p=await api("/api/plan",{scope:state.scope,online:forceRoad || state.online,request_key:requestKey()});
    state.data.latest_plan=p; state.data.latest_plans ||= {}; state.data.latest_plans[p.scope]=p;
    render(); if(p.stops.length&&state.map)state.map.fitBounds(p.geometry);
    if(!state.token) await GCPWA.snapshot("put",{savedAt:Date.now(),data:state.data});
    toast(p.stops.length?`${p.stops.length} duraklı plan hazır.`:"Bu koşullarda uygun toplama durağı yok.");
    return p;
  } catch(e) { toast(e.message,true); return null; }
  finally { state.planning=false;renderPlanner(); }

}
async function quickDrive() {
  if(state.quickStarting || state.planning || !state.data) return;
  const button=$("#quickDrive"); state.quickStarting=true; button.disabled=true;button.setAttribute("aria-busy","true");
  $(".quick-drive-spinner").hidden=false;
  try {
    setFuture(0); setView("overview");
    const plan=state.offline ? selectedPlan() : await generatePlan(true);
    if(!plan?.stops.length) { if(state.offline)toast("Bu kaynak için kayıtlı sefer yok. Yeni rota için bağlanın.",true); return; }
    if(!plan.road_geometry) { toast("Yol çizgisi alınamadı. Sürüş başlatılmadı; bağlantıyı kontrol edip yeniden deneyin.",true); return; }
    if(!state.map?.ready) { toast("Harita henüz hazır değil. Yüklendiğinde yeniden dokunun.",true); return; }
    await state.map.driver.open({gps:true,returnFocus:button});
  } finally {
    state.quickStarting=false;button.disabled=false;button.setAttribute("aria-busy","false");$(".quick-drive-spinner").hidden=true;
    if(state.data)renderFuture();
  }
}
function renderRouteResults() {
  const p=selectedPlan();
  if(!p){$("#routeResults").innerHTML='<div class="empty-state">Kutuların durumuna göre ilk seferinizi oluşturun. Tahmini kazanımlar burada görünecek.</div>';return;}
  const row=(label,key,unit,digits=1)=>`<tr><td>${label}</td><td>${nf(p.baseline[key],digits)} ${unit}</td><td>${nf(p.recommended[key],digits)} ${unit}</td></tr>`;
  const risky=[...p.unserved,...p.deferred_risks];
  const staleMessage = p.completed_at ? "Tamamlanmış planın kaydedildiği andaki sonuçları gösteriliyor." : "Planın girdileri değişti. Yeni sefer için yeniden hesaplayın.";
  $("#routeResults").innerHTML=`<div class="banner ${p.mode==="road"?"info":"warning"}" style="margin-top:18px">${esc(p.notice)} ${!p.road_geometry&&p.mode==="road"?"Yol çizgisi alınamadı; duraklar şematik bağlandı.":""}</div>${p.stale?`<div class="banner warning">${staleMessage}</div>`:""}<div class="route-results-grid"><article class="card"><div class="card-heading"><div><h2>Önerilen sefer <span class="count-pill">${p.stops.length} durak</span></h2><p>${p.scope==="demo"?"Simülasyon":"Canlı sensörler"} · ${date(p.snapshot_at)} anlık görüntüsü</p></div><span class="soft-icon green-soft">${icon("route")}</span></div><div class="route-stops"><div class="route-stop"><span class="stop-number">${icon("truck")}</span><div><strong>Demo başlangıç noktası</strong><small>Sefer sonunda aynı noktaya dönüş</small></div><span>Başlangıç</span></div>${p.stops.map((s,i)=>`<button class="route-stop full-width text-button" data-bin="${s.id}"><span class="stop-number">${i+1}</span><div style="text-align:left"><strong>${esc(s.name)}</strong><small>${s.id} · ${nf(s.load_l)} L yük varsayımı${s.overflow_before_arrival?" · Varış öncesi doluluk riski":""}</small></div><span>+${nf(s.arrival_minutes,1)} dk</span></button>`).join("")}${!p.stops.length?'<div class="empty-state">Toplama durağı seçilmedi.</div>':""}</div><div style="padding:0 21px 20px"><button class="button button-primary full-width" data-action="complete-plan"${p.completed_at||!p.stops.length||(p.stale&&p.scope==="demo")?" disabled":""}>${icon("check")}${p.completed_at?"Toplama kaydedildi":p.scope==="demo"?"Demo seferini tamamla":"Seferin toplama kaydını oluştur"}</button></div><p class="route-note">${p.scope==="demo"?"Tamamlama, seçilen simülasyon kutularını %5 seviyesine getirir.":"Tamamlama yalnız operatör kaydı oluşturur; gerçek sensör doluluğu değiştirilmez. Sefer sırasında değişen telemetri kayıt oluşturmayı engellemez."}</p>${risky.length?`<div class="route-warning">${risky.map(r=>`${esc(r.id)}: ${esc(r.reason)}`).join("<br>")}</div>`:""}</article><article class="card"><div class="card-heading"><div><h2>Referansla karşılaştırma</h2><p>Tek seferlik tahmin · ${p.comparable?"aynı araç ve varsayımlar":"referans araç/süre sınırına sığmıyor"}</p></div></div><div class="table-wrapper"><table class="comparison-table"><thead><tr><th>Gösterge</th><th>Sabit ziyaret</th><th>Önerilen</th></tr></thead><tbody>${row("Ziyaret","stops","kutu",0)}${row("Mesafe","distance_km","km",2)}${row("Toplam süre","minutes","dk",1)}</tbody></table></div><p class="route-note">${esc(p.baseline_notice)}<br><br><strong>Aynı duraklarda sıralama etkisi:</strong> ${nf(p.ordering_minutes_saved,1)} dakika. Bu değer ziyaret azaltımını içermez.<br><br>${p.unknown_count} kutuda otomatik planlamaya uygun doluluk yok. ${p.estimated_load_l}/${p.capacity_l} L yük/kapasite varsayımı.<br><br>${esc(p.method)}</p><div style="padding:0 21px 20px"><button class="text-button" data-view="impact">Yakıt ve CO₂ hesabını incele ${icon("arrow")}</button></div></article></div>`;
}
function renderHealth() {
  const bins=state.data.bins, alerts=state.data.alerts.filter(a=>a.kind!=="forecast");
  const normal=bins.filter(b=>b.freshness==="fresh"&&b.measurement_quality==="ok").length;
  $("#healthPage").innerHTML=`<div class="health-summary">${metric("Normal ölçüm",nf(normal),"kutu","Güncel ve tam kaliteli veri","signal",true)}${metric("Kontrol gerekli",nf(new Set(alerts.map(a=>a.bin_id)).size),"kutu","Bağlantı, kalibrasyon veya ölçüm uyarısı","alert")}${metric("Canlı veri bekleyen",nf(bins.filter(b=>b.source==="live"&&b.freshness!=="fresh").length),"kutu","Donanım verisi simüle edilmez","pulse")}</div><div class="card table-card"><div class="card-heading"><div><h2>Bağlantı ve ölçüm uyarıları</h2><p>Aynı durum tek satırda izlenir; her paket için yeni uyarı üretilmez.</p></div><span class="badge outline">${alerts.length} AÇIK DURUM</span></div><table class="health-table"><thead><tr><th>Kutu / cihaz</th><th>Kaynak</th><th>Durum</th><th>Gözlem ve öneri</th></tr></thead><tbody>${alerts.map(a=>`<tr class="focus-health" data-bin="${a.bin_id}" tabindex="0" role="button" aria-label="${esc(a.name)} ayrıntıları"><td><strong>${esc(a.name)}</strong><br><small>${esc(a.bin_id)}</small></td><td>${sourceBadge(a.source)}</td><td><span class="badge ${a.severity}">${a.severity==="danger"?"KONTROL GEREKLİ":a.severity==="info"?"BEKLENİYOR":"UYARI"}</span></td><td class="health-message">${esc(a.message)}</td></tr>`).join("")||'<tr><td colspan="4">Açık uyarı bulunmuyor.</td></tr>'}</tbody></table></div><div class="banner info" style="margin-top:18px">Uyarılar ölçüm ve bağlantı gözlemlerine dayanır. Pil seviyesi, kapak durumu ve fiziksel arıza nedeni doğrudan ölçülmez. Canlı veriler 35 saniyelik varsayılan güncellik sınırına tabidir.</div>`;
}
function renderImpact() {
  const p=selectedPlan(), s=p?.stops.length ? p.savings : null;
  const metrics=s?metric("Mesafe farkı",nf(s.distance_km,2),"km","Referans − önerilen rota","route")+metric("Süre farkı",nf(s.minutes,1),"dk","Sürüş ve durak hizmet süresi","clock")+metric("Yakıt maliyeti farkı",nf(s.fuel_cost,2),"₺","Yalnız varsayılan yakıt gideri","truck")+metric("Yakıt kaynaklı CO₂ farkı",nf(s.co2_kg,2),"kg","Tek seferlik tahmini etki","leaf",true):"";
  $("#impactPage").innerHTML=`<div class="impact-intro">${icon("leaf")}<div><h2>Bu senaryoda tahmini kazanım</h2><p>${p?`${p.scope==="demo"?"Simülasyon":"Canlı sensör"} planı · ${date(p.created_at)} · ${p.mode==="road"?"Yol ağı mesafesi":"Kuş uçuşu yaklaşık mesafe"}`:"Etki hesabını görmek için bir rota oluşturun."}<br>Gerçekleşmiş veya birikimli tasarruf değildir.</p></div></div>${p?.stale?'<div class="banner warning">Son plan güncel girdilerle eşleşmiyor. Bu sonuçlar kaydedildiği andaki senaryoya aittir.</div>':""}${p&&!p.comparable?'<div class="banner warning">Sabit ziyaret referansı aynı araç kapasitesine veya sefer süresine sığmıyor. Yanıltıcı bir tasarruf yüzdesi hesaplanmadı.</div>':""}${!p?'<button class="button button-primary" data-view="route">'+icon("route")+'Rota planlamaya geç</button>':""}<div class="impact-metrics">${metrics}</div><article class="card method-card"><h2>Hesap nasıl yapılıyor?</h2><p>Referans senaryo, kullanılabilir tüm kutuların kimlik sırasıyla ziyaret edildiği demo planıdır. İhtiyaç bazlı planın mesafesi ve hizmet süresi bu planla karşılaştırılır. Belediye operasyonundan ölçülmüş bir referans değildir. Ertelenen kutuların gelecekteki toplama maliyeti bu tek seferlik farkta bulunmaz.</p><div class="formula">Yakıt farkı (L) = mesafe farkı (km) × tüketim (L/100 km) ÷ 100</div><div class="formula">Yakıt maliyeti farkı (₺) = yakıt farkı (L) × birim fiyat (₺/L)</div><div class="formula">CO₂ farkı (kg) = yakıt farkı (L) × emisyon katsayısı (kg CO₂/L)</div><p>${p?`Bu planın varsayımları: <strong>${nf(p.assumptions.liters_per_100km,1)} L/100 km</strong> tüketim, <strong>${nf(p.assumptions.diesel_price,2)} ₺/L</strong> yakıt, <strong>${nf(p.assumptions.co2_kg_per_liter,2)} kg CO₂/L</strong> katsayı. Durak başına <strong>${nf(p.assumptions.service_minutes,1)} dakika</strong> hizmet süresi.`:"Varsayımlar Operasyon ayarları bölümünden düzenlenebilir."}</p><p>${esc(state.data.emission_notice)} Dur-kalk, rölanti, yük, eğim ve canlı trafik bu basit modelde ayrı hesaplanmaz. İşçilik ve bakım maliyetleri dahil değildir.</p><p><strong>${state.data.completed_plans} sefer için toplama kaydı oluşturuldu.</strong> Bu kayıt sayısı gerçek sürüş, yakıt tüketimi veya doğrulanmış tasarruf kanıtı değildir. Aynı plan tekrar tamamlandığında yeni kayıt veya kazanım eklenmez.</p><a href="https://www.epa.gov/sites/default/files/2021-01/documents/420b21002.pdf" target="_blank" rel="noopener">Yakıt × emisyon faktörü yöntemine ilişkin EPA SmartWay dokümanı ↗</a></article>`;
}
function chart(history, threshold) {
  if(history.length<2)return '<div class="empty-state">Grafik için yeterli geçerli ölçüm yok.</div>';
  const w=360,h=150,left=28,right=8,top=12,bottom=25,start=history[0][0],end=history.at(-1)[0];
  const x=t=>left+(t-start)/Math.max(1,end-start)*(w-left-right), y=f=>top+(100-f)/100*(h-top-bottom);
  let line="";
  history.forEach(([t,f],i)=>{const gap=i&&t-history[i-1][0]>3600;line+=`${i&&!gap?"L":"M"}${x(t).toFixed(1)},${y(f).toFixed(1)} `;});
  return `<svg class="chart-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="Son 48 saatte yaklaşık doluluk grafiği"><defs><linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#65a582" stop-opacity=".18"/><stop offset="1" stop-color="#65a582" stop-opacity=".01"/></linearGradient></defs>${[0,50,100].map(f=>`<path d="M${left} ${y(f)}H${w-right}" stroke="#edf2ee" stroke-width="1"/><text x="0" y="${y(f)+3}">${f}</text>`).join("")}<path d="M${left} ${y(threshold)}H${w-right}" stroke="#dcb15c" stroke-width="1" stroke-dasharray="4 4"/><text x="${w-right}" y="${y(threshold)-5}" text-anchor="end">%${threshold} eşik</text><path d="${line}" stroke="#519d76" stroke-width="2" fill="none"/><text x="${left}" y="${h-4}">${esc(date(start))}</text><text x="${w-right}" y="${h-4}" text-anchor="end">${esc(date(end))}</text></svg>`;
}
async function openDetail(id, moveFocus=true) {
  const version=++state.detailVersion;
  try {
    const b=state.offline ? {...state.data.bins.find(bin=>bin.id===id),history:[],events:[]} : await api(`/api/bins/${encodeURIComponent(id)}`); if(version!==state.detailVersion)return;
    state.selected=id;
    const drawer=$("#detailDrawer"), scroll=drawer.scrollTop, active=document.activeElement?.dataset?.action;
    const f=b.forecast, fill=b.fill_percent;
    drawer.innerHTML=`<div class="drawer-top"><span class="badge outline">${esc(b.id)}</span>${sourceBadge(b.source)}<button class="icon-button" data-action="close-detail" aria-label="Kutu ayrıntılarını kapat">${icon("close")}</button></div><div class="drawer-title"><span class="bin-mini">${icon("bin")}<i class="status-dot ${b.color}"></i></span><div><h2>${esc(b.name)}</h2><div class="drawer-area">${esc(b.area)}</div></div></div><div class="fill-display"><strong style="color:${colors[b.color]}">${fill==null?"—":"%"+nf(fill,1)}</strong><span>yaklaşık doluluk</span></div><div class="fill-track"><div class="${b.color}" style="width:${fill??0}%"></div></div><div class="drawer-data-row"><span>Ölçüm durumu</span><strong>${b.freshness==="stale"?"Veri güncel değil":qualityLabels[b.measurement_quality]||esc(b.measurement_quality)}</strong></div><div class="drawer-data-row"><span>Veri yaşı</span><strong>${b.age_ms==null?"Henüz veri yok":nf(b.age_ms/1000)+" saniye"}${b.source==="simulated"?" · demo zamanı":""}</strong></div>${b.measurement?`<div class="drawer-data-row"><span>Mesafe / geçerli çift</span><strong>${b.measurement.distance_mm==null?"—":nf(b.measurement.distance_mm)+" mm"} / ${b.measurement.valid_pairs} / ${b.measurement.attempted_pairs}</strong></div>`:""}<div class="reason-box"><h3>${icon("info")}Neden bu karar?</h3>${b.reasons.map(r=>`<p>${esc(r)}</p>`).join("")}</div><div class="drawer-actions"><button class="button${b.override==="include"?" button-primary":""}" data-action="override" data-mode="include">${icon("route")}Rotaya ekle</button><button class="button${b.override==="exclude"?" button-danger":""}" data-action="override" data-mode="exclude">Çıkar</button><button class="button${b.override==="auto"?" button-primary":""}" data-action="override" data-mode="auto">Otomatik</button></div><div class="drawer-section"><h3>Doluluk geçmişi</h3>${chart(b.history,state.data.settings.threshold)}<p class="chart-caption">${b.source==="simulated"?"Üretilmiş geçmiş · gerçek saha ölçümü değildir.":"Yalnız mevcut kalibrasyonla kabul edilmiş fiziksel ölçümler."} Bir saati aşan boşluklar çizgiyle birleştirilmez.</p></div><div class="drawer-section demand-detail"><h3>Geçmiş kapasite ihtiyacı</h3>${b.demand?.available?`<div class="drawer-data-row"><span>Son ${b.demand.window_days} gün · dolma hızı</span><strong>${nf(b.demand.rate_pph,1)} yp / saat</strong></div><p class="chart-caption">${nf(b.demand.observed_hours,1)} saat güvenilir gözlem · %${nf(b.demand.coverage_percent)} zaman kapsamı. Isı haritası bu geçmiş hızı kullanır; anlık doluluk değildir.${b.demand.saturated_hours>0?" Tam dolu bekleme süreleri nedeniyle ihtiyaç düşük tahmin edilebilir.":""}</p>`:`<p class="muted">${esc(b.demand?.reason||"Yeterli geçmiş yok.")}</p>`}</div><div class="drawer-section"><h3>Dolum tahmini</h3>${f.available?`<div class="forecast-stats"><div class="forecast-stat"><small>Toplama eşiğine</small><strong>${nf(f.hours_to_threshold,1)} <span>saat</span></strong></div><div class="forecast-stat"><small>Tam doluluğa</small><strong>${nf(f.hours_to_full,1)} <span>saat</span></strong></div></div><div class="drawer-data-row"><span>Dolum hızı</span><strong>${nf(f.rate_pph,1)} yüzde puan / saat</strong></div><div class="drawer-data-row"><span>Hıza duyarlı eşik aralığı</span><strong>${nf(f.range_hours[0],1)}–${nf(f.range_hours[1],1)} saat</strong></div>`:`<p class="muted">${esc(f.reason)}</p>`}<p class="chart-caption">${esc(f.method)}. ${f.available?esc(f.reason):"Boşaltma sonrası yeni dolum dönemi için yeniden veri birikir."}</p></div><div class="drawer-section"><h3>Toplama kaydı</h3><p class="muted">${b.last_collection_at?"Son kayıt: "+date(b.last_collection_at):"Henüz kayıtlı toplama yok."}</p><button class="button full-width" data-action="collect">${icon("check")}${b.source==="simulated"?"Demo kutusunu boşalt":"Toplandı olarak kaydet"}</button><p class="chart-caption">${b.source==="simulated"?"Yalnız bu simülasyon kutusunun seviyesi %5 yapılır.":"Operatör kaydı oluşturur. Sensör ölçümü değiştirilmez."}</p>${b.events.slice(0,3).map(e=>`<div class="event-row">${esc(e.detail)}<small>${date(e.ts)}</small></div>`).join("")}</div><p class="source-note">Konum: ${b.lat.toFixed(5)}, ${b.lng.toFixed(5)} · ${nf(b.capacity_l)} L nominal kutu varsayımı. Doluluk yüzdesi ağırlık veya gerçek hacim ölçümü değildir.</p>`;
    if(state.offline)$$('[data-action=override], [data-action=collect]',drawer).forEach(button=>button.disabled=true);
    if(moveFocus){document.body.classList.add("detail-open");$(".mobile-drive-dock").inert=true;state.focusBeforeDrawer=document.activeElement;drawer.hidden=false;$("#drawerShade").hidden=false;document.body.style.overflow="hidden";$(".app-shell").inert=true;$("#sidebar").inert=true;drawer.focus();}
    drawer.scrollTop=scroll;
    if(!moveFocus&&active){const target=$$('[data-action]',drawer).find(e=>e.dataset.action===active);target?.focus({preventScroll:true});}
    renderMap();renderQueue();
  } catch(e){if(moveFocus)toast(e.message,true);}
}
function closeDetail(){document.body.classList.remove("detail-open");$(".mobile-drive-dock").inert=false;state.detailVersion++;$("#detailDrawer").hidden=true;$("#drawerShade").hidden=true;document.body.style.overflow="";$(".app-shell").inert=false;$("#sidebar").inert=false;state.selected=null;if(state.data){renderMap();renderQueue();}if(state.focusBeforeDrawer?.isConnected)state.focusBeforeDrawer.focus({preventScroll:true});else $("#map").focus({preventScroll:true});}
function openSettings(){const fields=[ ["threshold","Toplama eşiği (%)",50,95,1],["horizon_hours","Sonraki ziyaret (saat)",.5,24,.5],["max_collection_hours","Azami toplama aralığı (saat)",6,168,1],["service_minutes","Durak hizmet süresi (dk)",.5,15,.5],["truck_capacity_l","Araç hacim varsayımı (L)",500,50000,100],["shift_minutes","Sefer üst sınırı (dk)",10,720,1],["liters_per_100km","Yakıt tüketimi (L/100 km)",5,150,.1],["diesel_price","Yakıt fiyatı (₺/L)",1,500,.01],["co2_kg_per_liter","Emisyon varsayımı (kg CO₂/L)",1,5,.01],["offline_speed_kmh","Yaklaşık planda hız (km/sa)",5,60,1] ];$("#settingsFields").innerHTML=fields.map(([name,label,min,max,step])=>`<div class="form-field"><label for="setting-${name}">${label}</label><input id="setting-${name}" name="${name}" type="number" min="${min}" max="${max}" step="${step}" value="${state.data.settings[name]}" required></div>`).join("");$("[name=use_degraded]").checked=state.data.settings.use_degraded;$("#settingsDialog").showModal();}
async function runAction(button, work){button.disabled=true;try{await work();await refresh();}catch(e){toast(e.message,true);}finally{if(button.isConnected)button.disabled=false;}}
document.addEventListener("click",async event=>{
  const button=event.target.closest("button,a[data-view],tr[data-bin]");if(!button)return;
  if(button.dataset.view){setView(button.dataset.view);return;}
  if(button.dataset.bin){await openDetail(button.dataset.bin);return;}
  if(button.dataset.close){$("#"+button.dataset.close).close();return;}
  if(button.dataset.source){state.source=button.dataset.source;if(state.source!=="all")state.scope=state.source==="live"?"live":"demo";if(state.data)renderFuture();$$("[data-source]").forEach(b=>b.classList.toggle("active",b===button));renderMap();renderQueue();return;}
  if(button.dataset.queue){state.queue=button.dataset.queue;$$("[data-queue]").forEach(b=>b.classList.toggle("active",b===button));renderQueue();return;}
  if(button.dataset.advance){await runAction(button,async()=>{await api("/api/demo/advance",{hours:Number(button.dataset.advance)});toast("Yalnız simülasyon zamanı ilerletildi. Rota varsa yeniden oluşturun.");});return;}
  const action=button.dataset.action;
  if(action==="close-detail"){closeDetail();return;}
  if(action==="override"){await runAction(button,async()=>{await api("/api/override",{bin_id:state.selected,mode:button.dataset.mode});toast("Rota tercihi güncellendi. Yeni plan oluşturabilirsiniz.");});return;}
  if(action==="collect"){await runAction(button,async()=>{await api("/api/collection",{bin_id:state.selected,request_key:requestKey()});toast("Toplama kaydı oluşturuldu.");});return;}
  if(action==="complete-plan"){await runAction(button,async()=>{await api("/api/plan/complete",{plan_id:selectedPlan().id});toast("Sefer için toplama kaydı oluşturuldu.");});return;}
  if(button.id==="quickDrive"){await quickDrive();return;}
  if(button.id==="queueToggle"){const open=$("#mapWorkspace").classList.toggle("queue-open");button.setAttribute("aria-expanded",String(open));if(open)$("#queuePanel").scrollIntoView({behavior:"auto",block:"nearest"});return;}
  if(button.id==="futureReset"){setFuture(0);return;}
  if(button.id==="generatePlan"){await generatePlan();return;}
  if(button.id==="settingsButton"&&state.data){$("#sidebar").classList.remove("open");openSettings();return;}
  if(button.id==="demoButton"&&state.data){$("#demoDialog").showModal();return;}
  if(button.id==="menuButton"){$("#sidebar").classList.toggle("open");return;}
  if(button.id==="fitMap"&&state.map){const bins=visibleBins();if(bins.length)state.map.fitBounds(bins.map(b=>[b.lat,b.lng]),{padding:[40,40],maxZoom:17});return;}
  if(button.id==="applyFault"){await runAction(button,async()=>{await api("/api/demo/fault",{bin_id:$("#demoBin").value,fault:$("#demoFault").value});toast("Simülasyon sensör durumu güncellendi.");});}
});
document.addEventListener("change",event=>{
  if(event.target.id==="mapLighting"){state.lighting=event.target.value;if(state.data)renderFuture();}
  if(event.target.id==="fillFilter"){state.fill=event.target.value;renderMap();renderQueue();}
  if(event.target.id==="planScope"){state.scope=event.target.value;render();}
  if(event.target.id==="onlineRoads")state.online=event.target.checked;
});
$("#futureHours").addEventListener("input",event=>setFuture(event.target.value));
$("#binSearch").addEventListener("input",event=>{state.search=event.target.value;renderQueue();});
$("#settingsForm").addEventListener("submit",async event=>{event.preventDefault();const body={};for(const [key,value]of new FormData(event.target))if(key!=="use_degraded")body[key]=Number(value);body.use_degraded=$("[name=use_degraded]").checked;await runAction($("button[type=submit]",event.target),async()=>{await api("/api/settings",body);$("#settingsDialog").close();toast("Operasyon ayarları kaydedildi.");});});
$("#authForm").addEventListener("submit",async event=>{event.preventDefault();state.token=$("#accessToken").value;try{await api("/health");$("#accessToken").value="";$("#authDialog").close();await refresh();}catch(e){$("#authError").textContent=e.message;}});
$("#authDialog").addEventListener("cancel",event=>event.preventDefault());
$("#drawerShade").addEventListener("click",closeDetail);
document.addEventListener("click",event=>{if($("#sidebar").classList.contains("open")&&!$("#sidebar").contains(event.target)&&!event.target.closest("#menuButton"))$("#sidebar").classList.remove("open");});
document.addEventListener("keydown",event=>{
  if(event.key==="Escape")$("#sidebar").classList.remove("open");
  const drawer=$("#detailDrawer");
  if(!drawer.hidden){
    if(event.key==="Escape"){event.preventDefault();closeDetail();}
    if(event.key==="Tab"){const f=$$("button,a[href],input,select,[tabindex='0']",drawer).filter(e=>!e.disabled);if(!f.length)return;if(event.shiftKey&&(document.activeElement===f[0]||document.activeElement===drawer)){event.preventDefault();f.at(-1).focus();}else if(!event.shiftKey&&(document.activeElement===f.at(-1)||document.activeElement===drawer)){event.preventDefault();f[0].focus();}}
  }
  if(event.target.matches("tr[data-bin]")&&["Enter"," "].includes(event.key)){event.preventDefault();openDetail(event.target.dataset.bin);}
});
window.addEventListener("hashchange",()=>setView(location.hash.slice(1)));
$("#binList").innerHTML='<div class="loading-skeleton"></div><div class="loading-skeleton"></div>';
window.addEventListener("online",()=>refresh());
window.addEventListener("offline",()=>{if(state.map?.basemap!=="city")state.map?.setBasemap("city");refresh();});
initMap();setView(location.hash.slice(1)||"overview");refresh();setInterval(()=>{if(!document.hidden)refresh();},5000);
