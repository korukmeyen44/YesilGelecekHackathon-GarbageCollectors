"""Road matrix + deterministic tour heuristic, with an explicit offline approximation."""
from __future__ import annotations

import hashlib
import json
import math
import time
from urllib.request import Request, urlopen

from app.domain import DEPOT, haversine


def tour_cost(order, matrix):
    return sum(matrix[a][b] for a, b in zip(order, order[1:]))


def optimize(indices, matrix):
    remaining, order = set(indices), [0]
    while remaining:
        nxt = min(remaining, key=lambda j: (matrix[order[-1]][j], j))
        order.append(nxt)
        remaining.remove(nxt)
    order.append(0)
    # Directed matrices: evaluate the whole reversed segment, not a symmetric 2-opt shortcut.
    best = tour_cost(order, matrix)
    for _ in range(30):
        improved = False
        for i in range(1, len(order)-2):
            for j in range(i+2, len(order)):
                trial = order[:i] + list(reversed(order[i:j])) + order[j:]
                value = tour_cost(trial, matrix)
                if value + 0.001 < best:
                    order, best, improved = trial, value, True
        if not improved:
            break
    # Keep a fixed-order incumbent, so the proposed ordering never worsens it.
    fixed = [0, *sorted(indices), 0]
    return fixed if tour_cost(fixed, matrix) < best else order


class Roads:
    def __init__(self, db, enabled=True):
        self.db, self.enabled = db, enabled
        self.db.execute("CREATE TABLE IF NOT EXISTS road_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    @staticmethod
    def fetch(path):
        req = Request("https://router.project-osrm.org/" + path,
                      headers={"User-Agent": "GarbageCollectors-Hackathon-MVP/1.0"})
        with urlopen(req, timeout=5) as response:
            result = json.load(response)
        if result.get("code") != "Ok":
            raise ValueError("Yol servisi geçerli sonuç döndürmedi.")
        return result

    def matrix(self, points, settings, online=True):
        coords = ";".join(f"{p['lng']:.6f},{p['lat']:.6f}" for p in points)
        key = "matrix:" + hashlib.sha256(coords.encode()).hexdigest()
        row = self.db.execute("SELECT value FROM road_cache WHERE key=?", (key,)).fetchone()
        if row and online:
            cached = json.loads(row[0])
            cached["cached"] = True
            return cached
        error = "Çevrimdışı yaklaşık hesaplama seçildi."
        if self.enabled and online:
            try:
                result = self.fetch("table/v1/driving/" + coords + "?annotations=duration,distance")
                n = len(points)
                for matrix in (result["durations"], result["distances"]):
                    if len(matrix) != n or any(len(r) != n for r in matrix) or any(
                        type(x) not in (int, float) or not math.isfinite(x) or x < 0 for r in matrix for x in r):
                        raise ValueError("Bazı noktalara yol bağlantısı bulunamadı.")
                value = {"durations": result["durations"], "distances": result["distances"],
                         "mode": "road", "cached": False, "retrieved_at": time.time(),
                         "notice": "OSRM otomobil profili; canlı trafik ve kamyona özel erişim kısıtları içermez."}
                with self.db:
                    self.db.execute("INSERT OR REPLACE INTO road_cache VALUES (?,?)", (key, json.dumps(value)))
                return value
            except (OSError, ValueError, KeyError, TypeError) as exc:
                error = f"Yol servisine erişilemedi ({type(exc).__name__})."
        distances = [[haversine(a, b) for b in points] for a in points]
        return {"distances": distances,
                "durations": [[d / (settings["offline_speed_kmh"]/3.6) for d in row] for row in distances],
                "mode": "approximate", "cached": False, "retrieved_at": None,
                "notice": error + " Kuş uçuşu mesafe ve varsayılan hız kullanılır; çizgiler sürüş güzergâhı değildir."}

    def geometry(self, points, order, mode):
        fallback = [[points[i]["lat"], points[i]["lng"]] for i in order]
        if mode != "road" or len(order) <= 2:
            return fallback, False
        coords = ";".join(f"{points[i]['lng']:.6f},{points[i]['lat']:.6f}" for i in order)
        key = "route:" + hashlib.sha256(coords.encode()).hexdigest()
        row = self.db.execute("SELECT value FROM road_cache WHERE key=?", (key,)).fetchone()
        if row:
            return json.loads(row[0]), True
        if self.enabled:
            try:
                result = self.fetch("route/v1/driving/"+coords+"?overview=full&geometries=geojson&steps=false")
                line = [[lat, lng] for lng, lat in result["routes"][0]["geometry"]["coordinates"]]
                with self.db:
                    self.db.execute("INSERT OR REPLACE INTO road_cache VALUES (?,?)", (key, json.dumps(line)))
                return line, True
            except (OSError, ValueError, KeyError, TypeError, IndexError):
                pass
        return fallback, False


def plan_route(bins, settings, roads, online=True):
    all_bins = sorted(bins, key=lambda b: b["id"])
    points = [DEPOT, *all_bins]
    index = {b["id"]: i for i, b in enumerate(points)}
    matrix = roads.matrix(points, settings, online)
    duration, distance = matrix["durations"], matrix["distances"]
    candidates = sorted((b for b in all_bins if b["selected"]), key=lambda b: (-b["priority"], b["id"]))
    chosen, unserved, load = [], [], 0
    for b in candidates:
        if load + b["estimated_load_l"] > settings["truck_capacity_l"]:
            unserved.append({"id": b["id"], "reason": "Varsayılan araç hacim kapasitesine sığmıyor."})
            continue
        trial = chosen + [index[b["id"]]]
        order = optimize(trial, duration)
        minutes = tour_cost(order, duration)/60 + len(trial)*settings["service_minutes"]
        if minutes > settings["shift_minutes"]:
            unserved.append({"id": b["id"], "reason": "Sefer süresi sınırını aşıyor."})
            continue
        chosen, load = trial, load + b["estimated_load_l"]
    order = optimize(chosen, duration)
    fixed_same = [0, *sorted(chosen), 0]
    # All usable bins form the declared scheduled-visit baseline; unknown bins excluded in both.
    baseline_indices = [index[b["id"]] for b in all_bins if b["usable"] or b["selected"]]
    baseline_order = [0, *baseline_indices, 0]

    def describe(tour):
        count = max(0, len(tour)-2)
        return {"distance_km": round(tour_cost(tour, distance)/1000, 3),
                "minutes": round(tour_cost(tour, duration)/60 + count*settings["service_minutes"], 2),
                "stops": count}

    recommended, baseline, fixed = describe(order), describe(baseline_order), describe(fixed_same)
    baseline_load = sum(points[i]["estimated_load_l"] for i in baseline_indices)
    comparable = baseline_load <= settings["truck_capacity_l"] and baseline["minutes"] <= settings["shift_minutes"]
    km = baseline["distance_km"]-recommended["distance_km"]
    liters = km*settings["liters_per_100km"]/100
    savings = {"distance_km": round(km, 3), "minutes": round(baseline["minutes"]-recommended["minutes"], 2),
               "liters": round(liters, 3), "fuel_cost": round(liters*settings["diesel_price"], 2),
               "co2_kg": round(liters*settings["co2_kg_per_liter"], 3)} if comparable else None
    line, road_geometry = roads.geometry(points, order, matrix["mode"])
    elapsed, stops = 0, []
    for previous, current in zip(order, order[1:]):
        elapsed += duration[previous][current]/60
        if current:
            b = points[current]
            hours = b["forecast"].get("hours_to_full")
            stops.append({"id": b["id"], "name": b["name"], "arrival_minutes": round(elapsed, 1),
                          "source": b["source"], "load_l": b["estimated_load_l"],
                          "overflow_before_arrival": hours is not None and hours*60 < elapsed})
            elapsed += settings["service_minutes"]
    selected_ids = {s["id"] for s in stops}
    risks = [{"id": b["id"], "reason": "Bu sefer dışında; sonraki ziyaretten önce toplama eşiği riski var."}
             for b in all_bins if b["automatic_candidate"] and b["id"] not in selected_ids]
    return {"stops": stops, "geometry": line, "road_geometry": road_geometry,
            "baseline_geometry": [[points[i]["lat"], points[i]["lng"]] for i in baseline_order],
            "recommended": recommended, "baseline": baseline, "same_stops_fixed": fixed,
            "ordering_minutes_saved": round(fixed["minutes"]-recommended["minutes"], 2),
            "estimated_load_l": load, "capacity_l": settings["truck_capacity_l"],
            "unserved": unserved, "deferred_risks": risks,
            "unknown_count": sum(not b["usable"] for b in all_bins),
            "comparable": comparable, "savings": savings, "mode": matrix["mode"],
            "notice": matrix["notice"], "road_data_at": matrix["retrieved_at"],
            "baseline_notice": "Kimlik sırasıyla tüm kullanılabilir kutuları ziyaret eden demo referansı. Aynı başlangıç/dönüş, yol matrisi ve hizmet süresi. Gerçek belediye rotası değildir. Seçilmeyen kutuların gelecekteki hizmet maliyeti bu tek seferlik farkta yoktur.",
            "method": "En yakın komşu + yönlü 2-opt; kesin optimum garantisi yok.",
            "savings_scope": "Tek seferlik plan karşılaştırması; gerçekleşmiş veya birikimli tasarruf değildir.",
            "assumptions": settings.copy()}
