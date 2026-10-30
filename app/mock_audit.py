"""Read-only audit of the existing simulated dataset; no reseeding or telemetry writes."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import statistics

from app.domain import DEFAULTS, decorate

ISTANBUL = timezone(timedelta(hours=3))
VALID = {"ok", "degraded"}


def local_date(stamp):
    return datetime.fromtimestamp(stamp, ISTANBUL)


def read_snapshot(path):
    path = Path(path).resolve(strict=True)
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("BEGIN")
        meta = {k: json.loads(v) for k, v in db.execute(
            "SELECT key,value FROM meta WHERE key IN ('demo_now','seed_at','settings')")}
        bins = [json.loads(r[0]) for r in db.execute("SELECT data FROM demo_bins ORDER BY id")]
        samples = defaultdict(list)
        for ident, stamp, fill, quality in db.execute("SELECT bin_id,ts,fill,quality FROM samples ORDER BY bin_id,ts"):
            samples[ident].append((stamp, fill, quality))
        events = [dict(zip(("bin_id", "ts", "kind", "detail"), r)) for r in db.execute(
            "SELECT bin_id,ts,kind,detail FROM events ORDER BY bin_id,ts")]
    finally:
        db.close()
    if not bins or "demo_now" not in meta:
        raise ValueError("İncelenecek simülasyon kutusu veya demo zamanı bulunamadı.")
    if any(b.get("source") != "simulated" for b in bins):
        raise ValueError("Demo deposunda simüle olmayan kutu var; kaynak ayrımı kontrol edilmeli.")
    data = {"meta": meta, "bins": bins, "samples": dict(samples), "events": events}
    unknown = set(samples) - {b["id"] for b in bins}
    if unknown:
        raise ValueError("Örnek tablosunda envanter dışı kutular var; kaynak ayrımı kontrol edilmeli.")
    data["digest"] = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return data


def hourly_windows(rows, event_times):
    """One-hour net change, excluding gaps, invalid samples and collection windows."""
    stamps = [r[0] for r in rows]
    result = []
    for i, (stamp, fill, quality) in enumerate(rows):
        if quality not in VALID or fill is None:
            continue
        j = bisect_left(stamps, stamp + 3600 - 0.5, i + 1)
        if j == len(rows) or abs(stamps[j] - stamp - 3600) > 0.5:
            continue
        segment = rows[i:j+1]
        if any(q not in VALID or f is None for _, f, q in segment):
            continue
        if any(b[0]-a[0] > 1350 or b[1] < a[1]-20 for a, b in zip(segment, segment[1:])):
            continue
        if bisect_right(event_times, stamp) != bisect_right(event_times, stamps[j]):
            continue
        result.append((stamp, (rows[j][1]-fill)/((stamps[j]-stamp)/3600)))
    return result


def speed_group(rate):
    if rate < 1: return "Çok yavaş"
    if rate < 2: return "Yavaş"
    if rate < 4: return "Orta"
    if rate < 6: return "Hızlı"
    return "Çok hızlı"


def analyze(data):
    now = data["meta"]["demo_now"]
    all_rows = [r for rows in data["samples"].values() for r in rows]
    if not all_rows: raise ValueError("Örnek kaydı bulunamadı.")
    start, end = min(r[0] for r in all_rows), max(r[0] for r in all_rows)
    quality_counts = dict(Counter(r[2] for r in all_rows))
    events_by_bin = defaultdict(list)
    for e in data["events"]:
        if e["kind"] == "collection" and e["ts"] <= now:
            events_by_bin[e["bin_id"]].append(e["ts"])
    bin_stats, decisions, windows = [], {}, {}
    future = sum(r[0] > now for r in all_rows)
    invalid_values = sum(r[1] is not None and (not math.isfinite(r[1]) or not 0 <= r[1] <= 100) for r in all_rows)
    for b in data["bins"]:
        rows = [r for r in data["samples"].get(b["id"], []) if r[0] <= now]
        stamps = [r[0] for r in rows]
        deltas = [y-x for x, y in zip(stamps, stamps[1:])]
        cadence = statistics.median(deltas) if deltas else 900
        expected = math.floor((now-start)/cadence + .01)+1 if cadence else 0
        gaps = sum(max(0, round(dt/cadence)-1) for dt in deltas) if cadence else 0
        good = [(t, f) for t, f, q in rows if q in VALID and f is not None]
        drops = [(after[0], before[1]-after[1]) for before, after in zip(rows, rows[1:])
                 if before[1] is not None and after[1] is not None and before[2] in VALID and after[2] in VALID
                 and after[0]-before[0] <= cadence*1.5 and after[1] < before[1]-20]
        event_times = sorted(events_by_bin[b["id"]])
        unconfirmed = 0
        matched_drop_slots = Counter()
        for stamp in event_times:
            j = bisect_left(stamps, stamp)
            if not (0 < j < len(rows) and rows[j][1] is not None and rows[j-1][1] is not None
                    and rows[j-1][1]-rows[j][1] > 20):
                unconfirmed += 1
            else:
                matched_drop_slots[j] += 1
        w = hourly_windows(rows, event_times)
        windows[b["id"]] = w
        daily = defaultdict(list)
        for stamp, rate in w: daily[local_date(stamp).date().isoformat()].append(rate)
        last_collection = max(event_times) if event_times else None
        fault = b.get("fault", "normal")
        view = {**b, "fill_percent": None if fault in ("offline", "unstable") else b.get("fill_percent"),
                "freshness": "stale" if fault == "offline" else "fresh",
                "measurement_quality": "invalid" if fault == "unstable" else "degraded" if fault == "degraded" else "ok"}
        decision = decorate(view, good, {**DEFAULTS, **data["meta"].get("settings", {})}, now, last_collection)
        decisions[b["id"]] = {"selected": decision["selected"], "fill": view["fill_percent"],
                              "reasons": decision["reasons"], "forecast": decision["forecast"]}
        bin_stats.append({"id": b["id"], "area": b["area"], "lat": b["lat"], "lng": b["lng"],
                          "base_rate_pph": b["rate"], "speed_group": speed_group(b["rate"]),
                          "observed_median_pph": round(statistics.median(r for _, r in w), 3) if w else None,
                          "samples": len(rows), "expected_samples": expected, "gap_slots": gaps,
                          "quality_counts": dict(Counter(r[2] for r in rows)),
                          "collection_records": len(event_times), "observed_drops": len(drops),
                          "unconfirmed_collection_records": unconfirmed, "drops": drops,
                          "same_drop_extra_records": sum(n-1 for n in matched_drop_slots.values()),
                          "daily_rate_pph": {k: round(statistics.median(v), 3) for k, v in sorted(daily.items())},
                          "current_fault": fault, "constant_tail_hours": round((now-last_collection)/3600, 2) if last_collection else None})
    rates = [b["rate"] for b in data["bins"]]
    neighbor_pairs = []
    for b in data["bins"]:
        nearest = sorted((o for o in data["bins"] if o["id"] != b["id"]),
                         key=lambda o: ((b["lat"]-o["lat"])*111000)**2 + ((b["lng"]-o["lng"])*84000)**2)[:3]
        if nearest: neighbor_pairs.append((b["rate"], statistics.mean(o["rate"] for o in nearest)))
    correlation = statistics.correlation(*zip(*neighbor_pairs)) if len(neighbor_pairs)>2 and len(set(y for _, y in neighbor_pairs))>1 and len(set(rates))>1 else None
    regions = {area: {"bins": len(group), "mean_base_rate_pph": round(statistics.mean(b["rate"] for b in group), 3)}
               for area in sorted({b["area"] for b in data["bins"]})
               for group in [[b for b in data["bins"] if b["area"]==area]]}
    total_expected = sum(b["expected_samples"] for b in bin_stats)
    return {"source_digest": data["digest"], "demo_now": now, "start": start, "end": end,
            "span_days": (end-start)/86400, "bins_count": len(bin_stats), "samples_count": len(all_rows),
            "expected_samples": total_expected, "missing_slots_estimate": max(0, total_expected-len(all_rows)),
            "quality_counts": quality_counts, "future_samples": future, "invalid_fill_values": invalid_values,
            "base_rates": dict(sorted(Counter(rates).items())), "rate_min": min(rates), "rate_max": max(rates),
            "rate_ratio": max(rates)/min(rates), "speed_groups": dict(Counter(speed_group(r) for r in rates)),
            "capacities_l": sorted({b["capacity_l"] for b in data["bins"]}),
            "current_faults": dict(Counter(b.get("fault", "normal") for b in data["bins"])),
            "collection_records": sum(b["collection_records"] for b in bin_stats),
            "observed_drops": sum(b["observed_drops"] for b in bin_stats),
            "unconfirmed_collection_records": sum(b["unconfirmed_collection_records"] for b in bin_stats),
            "same_drop_extra_records": sum(b["same_drop_extra_records"] for b in bin_stats),
            "neighbor_rate_correlation": correlation, "regions": regions, "bins": bin_stats,
            "decisions": decisions,
            "scope": "Mevcut simülasyon deposunun salt okunur anlık görüntüsü; gerçek belediye veya sensör verisi değildir.",
            "limitations": [
                "14 gün yalnız iki haftalık döngü içerir; haftalık genelleme değerlendirmesi için sınırlıdır.",
                "Üretici 8 sabit temel hızı tekrarlar; son dolum dönemi hedef son seviyeye doğrusal bağlanır.",
                "Gündüz/gece ortak katsayısı vardır; hafta sonu, tatil veya bölgeye özgü etkinlik takvimi üretilmez.",
                "Mevcut arıza bayrakları geçmişte arıza/eksik örnek olduğu anlamına gelmez.",
                "Koordinatlar ve seviyeler heatmap çizimine yeter; bölgeye bağlı yoğunluk süreci açıkça modellenmemiştir.",
                "Tanımlı rate üretici parametresidir; gelecekte tahmin modeline ölçülmüş özellik olarak verilmemelidir.",
                "Toplama kayıtları ile gözlenen büyük düşüşler ayrı sayılır; bazı model sınırları ikinci bir toplama gibi kaydedilebilir.",
                "Bu grafiklerdeki doluluk ve artış hızı atık ağırlığı veya gerçek hacim ölçümü değildir.",
            ]}
