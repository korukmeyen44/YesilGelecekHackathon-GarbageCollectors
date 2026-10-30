"""Persistent demo state, isolated from physical telemetry."""
from __future__ import annotations

import json
import math
import random
import sqlite3
import time

from app.domain import DEFAULTS


class Operations:
    def __init__(self, path, now=None):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS demo_bins (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS samples (bin_id TEXT NOT NULL, ts REAL NOT NULL, fill REAL, quality TEXT NOT NULL,
                PRIMARY KEY(bin_id, ts));
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, bin_id TEXT NOT NULL, ts REAL NOT NULL,
                kind TEXT NOT NULL, source TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS events_lookup ON events(bin_id, kind, ts);
            CREATE TABLE IF NOT EXISTS overrides (bin_id TEXT PRIMARY KEY, mode TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
                created_at REAL NOT NULL, scope TEXT NOT NULL, data TEXT NOT NULL, completed_at REAL);
        """)
        if self.get("demo_now") is None:
            self.seed(time.time() if now is None else now)

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    def put(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False)))

    def settings(self):
        return {**DEFAULTS, **self.get("settings", {})}

    def save_bin(self, b):
        self.db.execute("INSERT OR REPLACE INTO demo_bins VALUES (?,?)", (b["id"], json.dumps(b, ensure_ascii=False)))

    def demo_bins(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT data FROM demo_bins ORDER BY id")]

    def seed(self, now):
        # Approximate presentation positions around campus; not asserted municipal assets.
        positions = [
            (40.9915,39.7678),(40.9923,39.7684),(40.9930,39.7692),(40.9936,39.7702),
            (40.9940,39.7714),(40.9938,39.7726),(40.9937,39.7740),(40.9933,39.7754),
            (40.9927,39.7768),(40.9919,39.7775),(40.9910,39.7774),(40.9902,39.7766),
            (40.9896,39.7754),(40.9890,39.7742),(40.9890,39.7727),(40.9895,39.7713),
            (40.9900,39.7699),(40.9906,39.7685),(40.9913,39.7700),(40.9918,39.7720),
            (40.9914,39.7737),(40.9908,39.7751),(40.9923,39.7747),(40.9928,39.7727),
        ]
        fills = [91,34,62,85,22,76,45,93,58,18,81,39,66,27,88,51,12,73,42,96,31,54,68,47]
        areas = ["Batı bölgesi", "Kuzey aksı", "Doğu bölgesi", "Güney aksı", "Merkez bölgesi", "Merkez bölgesi"]
        with self.db:
            self.put("demo_now", now)
            self.put("seed_at", now)
            for i, ((lat, lng), fill) in enumerate(zip(positions, fills), 1):
                rng = random.Random(7300+i)
                rate = [2.0,1.1,8.0,3.2,0.7,4.5,1.8,2.6][(i-1)%8]
                b = {"id": f"S{i:02d}", "name": f"Kampüs noktası {i:02d}", "area": areas[(i-1)//4],
                     "lat": lat, "lng": lng, "capacity_l": 770, "source": "simulated",
                     "fill_percent": fill, "last_valid_fill": fill, "last_seen": now-120 if i == 22 else now,
                     "rate": rate, "fault": "offline" if i == 22 else "unstable" if i == 23 else "degraded" if i == 24 else "normal"}
                self.save_bin(b)
                rows = []
                current, last = rng.uniform(5,30), None
                cycle_start = now - max(1, (fill-5)/rate)*3600
                for step in range(14*96+1):
                    stamp = now-14*86400+step*900
                    if stamp >= cycle_start:
                        value = max(5, min(100, fill-rate*(now-stamp)/3600 + (0 if stamp == now else rng.uniform(-0.35,0.35))))
                    else:
                        hour = (stamp/3600 + 3) % 24
                        current += rate*0.25*(0.45 if hour < 7 else 1.25)*rng.uniform(0.75,1.25)
                        if current >= 94:
                            current = rng.uniform(4,9)
                        value = round(current, 2)
                    if last is not None and value < last-20:
                        self.db.execute("INSERT INTO events(bin_id,ts,kind,source,detail) VALUES (?,?,?,?,?)",
                                        (b["id"], stamp, "collection", "simulated", "Sentetik geçmişte boşaltma"))
                    rows.append((b["id"], stamp, round(value,2), "ok"))
                    last = value
                self.db.executemany("INSERT INTO samples VALUES (?,?,?,?)", rows)
                # Exact model boundary, independent of whether the 15-minute sample captured the drop.
                self.db.execute("INSERT INTO events(bin_id,ts,kind,source,detail) VALUES (?,?,?,?,?)",
                                (b["id"], cycle_start, "collection", "simulated", "Sentetik son dolum dönemi başlangıcı"))

    def history(self, bin_id, since=None):
        rows = self.db.execute("SELECT ts,fill FROM samples WHERE bin_id=? AND ts>=? AND quality IN ('ok','degraded') ORDER BY ts",
                               (bin_id, since or 0)).fetchall()
        return [(r[0], r[1]) for r in rows]

    def last_collection(self, bin_id):
        row = self.db.execute("SELECT MAX(ts) FROM events WHERE bin_id=? AND kind='collection'", (bin_id,)).fetchone()
        return row[0]

    def advance(self, hours):
        start = self.get("demo_now")
        steps = max(1, math.ceil(hours*4))
        bins = self.demo_bins()
        with self.db:
            for step in range(1, steps+1):
                stamp = start + hours*3600*step/steps
                for b in bins:
                    b.setdefault("last_seen", start-120 if b["fault"] == "offline" else start)
                    b.setdefault("last_valid_fill", b["fill_percent"])
                    b["fill_percent"] = min(100, b["fill_percent"] + b["rate"]*hours/steps)
                    if b["fault"] == "offline":
                        continue
                    b["last_seen"] = stamp
                    quality = "invalid" if b["fault"] == "unstable" else "degraded" if b["fault"] == "degraded" else "ok"
                    if quality != "invalid":
                        b["last_valid_fill"] = b["fill_percent"]
                    self.db.execute("INSERT OR REPLACE INTO samples VALUES (?,?,?,?)",
                                    (b["id"], stamp, round(b["fill_percent"],2), quality))
            for b in bins:
                self.save_bin(b)
            self.put("demo_now", start+hours*3600)

    def close(self):
        self.db.close()
