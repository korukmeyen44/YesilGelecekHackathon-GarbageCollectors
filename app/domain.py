"""Deterministic decisions. Fill is calibrated level, not measured mass/volume."""
from __future__ import annotations

import math
import statistics

DEFAULTS = {
    "threshold": 80, "horizon_hours": 4, "max_collection_hours": 48,
    "service_minutes": 2, "truck_capacity_l": 18000, "shift_minutes": 240,
    "liters_per_100km": 35, "diesel_price": 50, "co2_kg_per_liter": 2.68,
    "offline_speed_kmh": 20, "use_degraded": False,
}
# 2.68 kg/L is an editable demonstration assumption, not a local fleet measurement.
SETTING_LIMITS = {
    "threshold": (50, 95), "horizon_hours": (0.5, 24),
    "max_collection_hours": (6, 168), "service_minutes": (0.5, 15),
    "truck_capacity_l": (500, 50000), "shift_minutes": (10, 720),
    "liters_per_100km": (5, 150), "diesel_price": (1, 500),
    "co2_kg_per_liter": (1, 5), "offline_speed_kmh": (5, 60),
}
DEPOT = {"id": "depot", "name": "Demo araç başlangıç / dönüş noktası",
         "lat": 40.99120, "lng": 39.76670}


def validate_settings(values):
    if not isinstance(values, dict) or set(values) - set(DEFAULTS):
        raise ValueError("Bilinmeyen ayar alanı.")
    for key, value in values.items():
        if key == "use_degraded":
            if type(value) is not bool:
                raise ValueError("use_degraded bir boolean olmalı.")
        elif type(value) not in (int, float) or not math.isfinite(value) or not SETTING_LIMITS[key][0] <= value <= SETTING_LIMITS[key][1]:
            raise ValueError(f"{key}: {SETTING_LIMITS[key]} aralığında sayı gerekli.")
    return values


def forecast(samples, now, threshold=80, boundary=None):
    """Theil–Sen local slope on the last cycle; no future observations or gap bridging."""
    rows = sorted((s for s in samples if s[0] <= now and s[1] is not None), key=lambda s: s[0])
    rows = [s for s in rows if s[0] >= now - 6 * 3600 and (boundary is None or s[0] >= boundary)]
    start = 0
    for i in range(1, len(rows)):
        if rows[i][1] < rows[i-1][1] - 20 or rows[i][0] - rows[i-1][0] > 3600:
            start = i
    rows = rows[start:]
    # Downsample by time, so 10-second sensor packets do not overwhelm hourly trends.
    buckets = {}
    for stamp, fill in rows:
        buckets.setdefault(int(stamp // 300), []).append((stamp, fill))
    rows = [(statistics.median(x[0] for x in b), statistics.median(x[1] for x in b))
            for b in buckets.values()]
    missing = {"available": False, "rate_pph": None, "hours_to_threshold": None,
               "hours_to_full": None, "range_hours": None, "reason": "En az 45 dakikaya yayılan 4 geçerli örnek gerekli.",
               "method": "Son dolum döneminde dayanıklı doğrusal eğilim"}
    if len(rows) < 4 or rows[-1][0] - rows[0][0] < 2700:
        return missing
    if now - rows[-1][0] > 1800:
        return {**missing, "reason": "Tahmin için yeterince güncel geçmiş yok."}
    slopes = [(b[1]-a[1]) / ((b[0]-a[0])/3600)
              for i, a in enumerate(rows) for b in rows[i+1:] if b[0]-a[0] >= 900]
    rate = statistics.median(slopes)
    if rate <= 0.1:
        return {**missing, "reason": "Pozitif ve kararlı bir dolum hızı gözlenmiyor.", "rate_pph": round(rate, 2)}
    current = rows[-1][1]
    eta = max(0, threshold-current) / rate
    full = max(0, 100-current) / rate
    positive = sorted(s for s in slopes if s > 0.1)
    low = positive[int((len(positive)-1)*0.2)]
    high = positive[int((len(positive)-1)*0.8)]
    return {"available": True, "rate_pph": round(rate, 2),
            "hours_to_threshold": round(eta, 2), "hours_to_full": round(full, 2),
            "range_hours": [round(max(0, threshold-current)/high, 2), round(max(0, threshold-current)/low, 2)],
            "reason": "Mevcut dolum eğiliminin sürmesi varsayılır; aralık hız duyarlılığıdır, kalibre edilmiş olasılık aralığı değildir.",
            "method": missing["method"]}


def decorate(bin_data, samples, settings, now, last_collection=None):
    b = dict(bin_data)
    fill = b.get("fill_percent")
    quality = b.get("measurement_quality", "missing")
    usable = fill is not None and b.get("freshness") == "fresh" and (
        quality == "ok" or quality == "degraded" and settings["use_degraded"])
    f = forecast(samples, now, settings["threshold"], last_collection) if usable else {
        "available": False, "rate_pph": None, "hours_to_threshold": None,
        "hours_to_full": None, "range_hours": None,
        "reason": "Güncel ve kullanılabilir doluluk bekleniyor.", "method": "Dayanıklı doğrusal eğilim"}
    reasons, priority, automatic = [], 0, False
    age = None if last_collection is None else max(0, (now-last_collection)/3600)
    if not usable:
        reasons.append("Güncel ve güvenilir doluluk yok; otomatik plana alınmadı. Operatör kontrolü gerekli.")
    else:
        if fill >= settings["threshold"]:
            reasons.append(f"Yaklaşık doluluk %{fill:.0f}; %{settings['threshold']:g} toplama eşiği aşıldı.")
            priority, automatic = 300 + fill, True
        elif f["available"] and f["hours_to_threshold"] <= settings["horizon_hours"]:
            reasons.append(f"Mevcut hız sürerse {f['hours_to_threshold']:.1f} saat içinde toplama eşiğine ulaşabilir; sonraki planlı ziyaretten önce toplama önerilir.")
            priority, automatic = 200 + fill, True
        if age is not None and age >= settings["max_collection_hours"]:
            reasons.append(f"Son kayıtlı toplamadan beri {age:.0f} saat geçti; azami toplama aralığı aşıldı.")
            priority, automatic = max(priority, 250 + fill), True
        if not reasons:
            reasons.append("Doluluk toplama eşiğinin altında; mevcut verilere göre bu sefer ertelenebilir.")
    if f["available"] and f["rate_pph"] >= 6:
        reasons.append(f"Hızlı dolum: saatte yaklaşık {f['rate_pph']:g} yüzde puan (demo kuralı: ≥6).")
    override = b.get("override", "auto")
    selected = automatic
    if override == "include":
        selected, priority = True, max(priority, 500)
        reasons.insert(0, "Operatör tarafından rotaya eklendi." + (" Doluluk bilinmediği için kapasite hesabında tam kutu varsayılır." if not usable else ""))
    elif override == "exclude":
        selected = False
        reasons.insert(0, "Operatör tarafından rotadan çıkarıldı; risk varsa ayrıca izlenmeli.")
    b.update(usable=usable, forecast=f, reasons=reasons, priority=priority,
             automatic_candidate=automatic, selected=selected, last_collection_at=last_collection,
             collection_age_hours=None if age is None else round(age, 1),
             color="gray" if fill is None else "red" if fill >= 80 else "yellow" if fill >= 50 else "green",
             estimated_load_l=round(b["capacity_l"] * (fill / 100 if usable else 1)),
             fast_filling=f["available"] and f["rate_pph"] >= 6)
    return b


def haversine(a, b):
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp = p2-p1
    dl = math.radians(b["lng"]-a["lng"])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 6371000 * 2 * math.atan2(math.sqrt(h), math.sqrt(max(0, 1-h)))
