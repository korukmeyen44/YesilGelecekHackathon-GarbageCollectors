"""Run: python -m app.server. Same telemetry contract as the firmware collector."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import mimetypes
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "firmware/tools"))
from collector import Store, IdentityConflict, ValidationError, load_calibration, loads
from app.domain import DEPOT, decorate, validate_settings
from app.routing import Roads, plan_route
from app.storage import Operations


class Application:
    def __init__(self, data_dir, calibration_path, hardware_db=None, roads_enabled=True, now=None):
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        self.ops = Operations(data_dir / "operations.sqlite3", now)
        db = Path(hardware_db) if hardware_db else data_dir / "hardware.sqlite3"
        db.parent.mkdir(parents=True, exist_ok=True)
        self.live = Store(db, load_calibration(calibration_path))
        self.roads = Roads(self.ops.db, roads_enabled)

    def close(self):
        self.live.close()
        self.ops.close()

    def live_history(self, node_id, since=0):
        with self.live.lock:
            rows = self.live.db.execute("SELECT observed_at,result_json,payload_json FROM telemetry WHERE node_id=? AND observed_at>=? ORDER BY observed_at", (node_id, since)).fetchall()
        result = []
        calibration_id = self.live.calibration["calibration_id"]
        for ts, raw, payload in rows:
            r, p = json.loads(raw), json.loads(payload)
            if p["source"] == "rf" and r.get("calibration_id") == calibration_id and not r.get("out_of_order") and r.get("fill_percent") is not None and r.get("measurement_quality") in ("ok", "degraded"):
                result.append((ts, r["fill_percent"]))
        return result

    def bins(self):
        settings, demo_now, real_now = self.ops.settings(), self.ops.get("demo_now"), time.time()
        overrides = dict(self.ops.db.execute("SELECT bin_id,mode FROM overrides"))
        output = []
        for raw in self.ops.demo_bins():
            fault = raw["fault"]
            b = {**raw, "override": overrides.get(raw["id"], "auto"),
                 "fill_percent": None if fault in ("offline", "unstable") else round(raw["fill_percent"],1),
                 "last_valid_fill_percent": round(raw.get("last_valid_fill", raw["fill_percent"]),1),
                 "measurement_quality": "invalid" if fault == "unstable" else "degraded" if fault == "degraded" else "ok",
                 "freshness": "stale" if fault == "offline" else "fresh",
                 "age_ms": max(0, round((demo_now-raw.get("last_seen", demo_now-120 if fault == "offline" else demo_now))*1000)), "clock": demo_now,
                 "measurement": None, "gateway_id": "demo-gateway"}
            output.append(decorate(b, self.ops.history(b["id"], demo_now-6*3600), settings, demo_now,
                                   self.ops.last_collection(b["id"])))
        live = {p["node_id"]: p for p in self.live.latest() if p["source"] == "rf"}
        for registry in self.config["live_bins"]:
            p = live.get(registry["node_id"], {})
            b = {**registry, **p, "source": "live", "override": overrides.get(registry["id"], "auto"),
                 "fill_percent": p.get("fill_percent"), "measurement_quality": p.get("measurement_quality", "missing"),
                 "freshness": p.get("freshness", "missing"), "age_ms": p.get("age_ms"), "clock": real_now}
            output.append(decorate(b, self.live_history(registry["node_id"], real_now-6*3600), settings, real_now,
                                   self.ops.last_collection(b["id"])))
        return output

    @staticmethod
    def alerts(bins):
        result = []
        for b in bins:
            message, severity, kind = None, "warning", "quality"
            if b["freshness"] == "missing":
                message, severity, kind = "Henüz canlı ölçüm alınmadı. Cihaz bağlantısını ve kalibrasyonu kontrol edin.", "info", "missing"
            elif b["freshness"] == "stale":
                message, severity, kind = "Veri güncel değil. Bağlantı veya cihaz kontrolü gerekli; kutu boş kabul edilmiyor.", "danger", "offline"
            elif b["measurement_quality"] not in ("ok",):
                labels = {"degraded": "Kısmi ölçüm: geçerli çift sayısı düşük.", "invalid": "Ölçüm geçersiz veya kararsız.",
                          "uncalibrated": "Fiziksel kalibrasyon yapılmamış.", "calibration_changed": "Kalibrasyon değişti; yeni ölçüm gerekli.",
                          "change_pending": "Büyük seviye değişimi doğrulanıyor.", "outside_geometry": "Ölçüm kalibrasyon geometrisinin dışında."}
                message = labels.get(b["measurement_quality"], "Ölçüm kalitesi kontrol edilmeli.")
            if message:
                result.append({"id": f"{b['id']}:{kind}", "bin_id": b["id"], "name": b["name"],
                               "source": b["source"], "severity": severity, "kind": kind, "message": message})
            if b["usable"] and b["fast_filling"] and b["forecast"]["hours_to_threshold"] <= 4:
                result.append({"id": f"{b['id']}:forecast", "bin_id": b["id"], "name": b["name"],
                               "source": b["source"], "severity": "warning", "kind": "forecast",
                               "message": f"Hızlı dolum. Eşiğe yaklaşık {b['forecast']['hours_to_threshold']:.1f} saat kaldı."})
        groups = {}
        for b in bins:
            if b["source"] == "live" and b.get("gateway_id") is not None:
                groups.setdefault(b["gateway_id"], []).append(b)
        for gateway, group in groups.items():
            if len(group) >= 2 and all(b["freshness"] == "stale" for b in group):
                result.append({"id": f"gateway:{gateway}", "bin_id": group[0]["id"], "name": f"Gateway {gateway}",
                               "source": "live", "severity": "danger", "kind": "gateway",
                               "message": "Bağlı kutular birlikte veri göndermeyi bıraktı; ortak bağlantı sorunu olabilir."})
        return result

    def dashboard(self):
        bins = self.bins()
        plan = self.ops.db.execute("SELECT data,completed_at FROM plans ORDER BY created_at DESC,rowid DESC LIMIT 1").fetchone()
        latest = json.loads(plan[0]) if plan else None
        if latest:
            latest["completed_at"] = plan[1]
            scoped = [b for b in bins if b["source"] == ("simulated" if latest["scope"] == "demo" else "live")]
            latest["stale"] = latest["input_digest"] != self.digest(scoped, self.ops.settings())
        completed = self.ops.db.execute("SELECT COUNT(*) FROM plans WHERE completed_at IS NOT NULL").fetchone()[0]
        return {"bins": bins, "alerts": self.alerts(bins), "settings": self.ops.settings(), "depot": DEPOT,
                "region": self.config["region"], "location_notice": self.config["location_notice"],
                "demo_now": self.ops.get("demo_now"), "real_now": time.time(), "latest_plan": latest,
                "completed_plans": completed,
                "calibration_id": self.live.calibration["calibration_id"],
                "emission_notice": "2,68 kg CO₂/L başlangıç değeri düzenlenebilir demo varsayımıdır; yerel filo ölçümü değildir. Yalnız yakıtın yanmasından kaynaklı CO₂ tahmini; yaşam döngüsü/CO₂e hesabı içermez."}

    @staticmethod
    def digest(bins, settings):
        fields = ("id", "fill_percent", "usable", "measurement_quality", "freshness", "override",
                  "last_collection_at", "selected", "estimated_load_l", "forecast")
        snapshot = {"settings": settings, "bins": [{k: b.get(k) for k in fields} for b in bins]}
        return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()

    def detail(self, bin_id):
        b = next((b for b in self.bins() if b["id"] == bin_id), None)
        if b is None:
            raise KeyError("Kutu bulunamadı.")
        history = self.ops.history(bin_id, b["clock"]-48*3600) if b["source"] == "simulated" else self.live_history(b["node_id"], b["clock"]-48*3600)
        # Keep the last sample of each 10-minute bucket for browser charts.
        buckets = {int(stamp//600): (stamp, fill) for stamp, fill in history}
        b["history"] = list(buckets.values())
        b["events"] = [dict(r) for r in self.ops.db.execute("SELECT ts,kind,source,detail FROM events WHERE bin_id=? ORDER BY ts DESC LIMIT 8", (bin_id,))]
        return b

    def action(self, path, body):
        if not isinstance(body, dict):
            raise ValueError("JSON nesnesi gerekli.")
        if path == "/api/settings":
            validate_settings(body)
            with self.ops.db:
                self.ops.put("settings", {**self.ops.settings(), **body})
            return {"ok": True}
        if path == "/api/override":
            if body.get("mode") not in ("auto", "include", "exclude"):
                raise ValueError("Geçersiz rota tercihi.")
            self.detail(body.get("bin_id"))
            with self.ops.db:
                self.ops.db.execute("INSERT OR REPLACE INTO overrides VALUES (?,?)", (body["bin_id"], body["mode"]))
            return {"ok": True}
        if path == "/api/demo/advance":
            hours = body.get("hours", 1)
            if type(hours) not in (int, float) or hours not in (0.25, 1, 4):
                raise ValueError("Demo 15 dakika, 1 veya 4 saat ilerletilebilir.")
            self.ops.advance(hours)
            return {"ok": True, "demo_now": self.ops.get("demo_now")}
        if path == "/api/demo/fault":
            b = next((b for b in self.ops.demo_bins() if b["id"] == body.get("bin_id")), None)
            if b is None or body.get("fault") not in ("normal", "offline", "unstable", "degraded"):
                raise ValueError("Yalnız simülasyon kutularının durumu değiştirilebilir.")
            b["fault"] = body["fault"]
            now = self.ops.get("demo_now")
            b["last_seen"] = now-120 if b["fault"] == "offline" else now
            if b["fault"] in ("normal", "degraded"):
                b["last_valid_fill"] = b["fill_percent"]
            with self.ops.db:
                self.ops.save_bin(b)
                if b["fault"] != "offline":
                    quality = "ok" if b["fault"] == "normal" else "degraded" if b["fault"] == "degraded" else "invalid"
                    self.ops.db.execute("INSERT OR REPLACE INTO samples VALUES (?,?,?,?)", (b["id"], now, b["fill_percent"], quality))
            return {"ok": True}
        if path == "/api/collection":
            b = self.detail(body.get("bin_id"))
            request_key = body.get("request_key")
            if not isinstance(request_key, str) or not 8 <= len(request_key) <= 100:
                raise ValueError("İşlem kimliği gerekli.")
            key = "collection:" + request_key
            if self.ops.get(key):
                return {"ok": True, "duplicate": True}
            with self.ops.db:
                self.collect(b["id"], "Operatör toplama kaydı")
                self.ops.put(key, True)
            return {"ok": True}
        if path == "/api/plan":
            scope = body.get("scope", "demo")
            request_key = body.get("request_key")
            if scope not in ("demo", "live") or not isinstance(request_key, str) or not 8 <= len(request_key) <= 100:
                raise ValueError("Geçerli kapsam ve işlem kimliği gerekli.")
            if "online" in body and type(body["online"]) is not bool:
                raise ValueError("online boolean olmalı.")
            existing = self.ops.db.execute("SELECT data FROM plans WHERE request_key=?", (request_key,)).fetchone()
            if existing:
                return json.loads(existing[0])
            bins = [b for b in self.bins() if b["source"] == ("simulated" if scope == "demo" else "live")]
            result = plan_route(bins, self.ops.settings(), self.roads, body.get("online", True))
            result.update(id=str(uuid.uuid4()), scope=scope, created_at=time.time(),
                          snapshot_at=self.ops.get("demo_now") if scope == "demo" else time.time(), completed_at=None)
            result["input_digest"] = self.digest(bins, self.ops.settings())
            with self.ops.db:
                self.ops.db.execute("INSERT INTO plans VALUES (?,?,?,?,?,NULL)",
                                    (result["id"], request_key, result["created_at"], scope, json.dumps(result, ensure_ascii=False)))
            return result
        if path == "/api/plan/complete":
            row = self.ops.db.execute("SELECT data,completed_at FROM plans WHERE id=?", (body.get("plan_id"),)).fetchone()
            if not row:
                raise KeyError("Plan bulunamadı.")
            if row[1] is not None:
                return {"ok": True, "duplicate": True}
            plan = json.loads(row[0])
            if not plan["stops"]:
                raise ValueError("Duraksız plan tamamlanamaz.")
            bins = [b for b in self.bins() if b["source"] == ("simulated" if plan["scope"] == "demo" else "live")]
            if plan["scope"] == "demo" and plan["input_digest"] != self.digest(bins, self.ops.settings()):
                raise ValueError("Plan girdileri değişti. Toplama kaydı oluşturmadan önce rotayı yeniden hesaplayın.")
            with self.ops.db:
                for stop in plan["stops"]:
                    self.collect(stop["id"], "Plan tamamlandı: " + plan["id"])
                self.ops.db.execute("UPDATE plans SET completed_at=? WHERE id=?", (time.time(), plan["id"]))
            return {"ok": True}
        raise KeyError("İşlem bulunamadı.")

    def collect(self, bin_id, detail):
        b = next((b for b in self.ops.demo_bins() if b["id"] == bin_id), None)
        now = self.ops.get("demo_now") if b else time.time()
        source = "simulated" if b else "live_operator_record"
        self.ops.db.execute("INSERT INTO events(bin_id,ts,kind,source,detail) VALUES (?,?,?,?,?)", (bin_id, now, "collection", source, detail))
        if b:
            b["fill_percent"] = 5
            if b["fault"] in ("normal", "degraded"):
                b["last_valid_fill"] = 5
                b["last_seen"] = now
                self.ops.db.execute("INSERT OR REPLACE INTO samples VALUES (?,?,?,?)", (bin_id, now, 5, "degraded" if b["fault"] == "degraded" else "ok"))
            self.ops.save_bin(b)
        self.ops.db.execute("DELETE FROM overrides WHERE bin_id=?", (bin_id,))


def make_server(app, host="127.0.0.1", port=8080, token=""):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def reply(self, code, data):
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            if token and not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.reply(401, {"error": "Erişim anahtarı gerekli."})
                return False
            return True

        def safe_origin(self):
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                self.reply(403, {"error": "Farklı kaynaktan işlem kabul edilmez."})
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path).path
            if path.startswith("/api/") or path == "/health":
                if not self.authorized():
                    return
                try:
                    with app.lock:
                        if path == "/health":
                            self.reply(200, {"status": "ok", "scope": "local_hackathon_mvp"})
                        elif path == "/api/latest":
                            self.reply(200, {"nodes": app.live.latest()})
                        elif path == "/api/dashboard":
                            self.reply(200, app.dashboard())
                        elif path.startswith("/api/bins/"):
                            self.reply(200, app.detail(path.rsplit("/",1)[-1]))
                        else:
                            self.reply(404, {"error": "Bulunamadı."})
                except KeyError as exc:
                    self.reply(404, {"error": str(exc)})
                except sqlite3.Error:
                    self.reply(503, {"error": "Kayıt deposuna erişilemedi."})
                return
            filename = "index.html" if path == "/" else path.lstrip("/")
            target = (ROOT / "web" / filename).resolve()
            if not target.is_relative_to((ROOT / "web").resolve()) or not target.is_file():
                self.reply(404, {"error": "Dosya bulunamadı."})
                return
            raw = target.read_bytes()
            mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") or mime == "application/javascript" else ""))
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            if not self.authorized() or not self.safe_origin():
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"error": "application/json gerekli."})
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
                if not 0 < length <= 16384:
                    self.reply(413, {"error": "Geçersiz istek boyutu."})
                    return
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError("Eksik istek gövdesi.")
                body = loads(raw)
                path = urlsplit(self.path).path
                with app.lock:
                    if path == "/api/telemetry":
                        if not isinstance(body, dict) or body.get("source") != "rf":
                            raise ValueError("Canlı telemetri yalnız source=rf kabul eder. Sentetik veri ayrı demo deposundadır.")
                        outcome = app.live.ingest(body)
                        self.reply(201 if outcome["inserted"] else 200, outcome)
                    else:
                        self.reply(200, app.action(path, body))
            except IdentityConflict as exc:
                self.reply(409, {"error": str(exc)})
            except KeyError as exc:
                self.reply(404, {"error": str(exc)})
            except (ValueError, TypeError) as exc:
                self.reply(400, {"error": str(exc)})
            except sqlite3.Error:
                self.reply(503, {"error": "Kayıt deposuna erişilemedi; aynı işlem kimliğiyle yeniden deneyin."})

    return ThreadingHTTPServer((host, port), Handler)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".data")
    local = ROOT.parent / "firmware/config/calibration.local.json"
    parser.add_argument("--config", type=Path, default=local if local.exists() else ROOT.parent / "firmware/config/calibration.example.json")
    parser.add_argument("--hardware-db", type=Path, help="Mevcut collector veritabanını kullan; collector HTTP sunucusunu aynı portta çalıştırma.")
    parser.add_argument("--offline", action="store_true", help="Yol servisine ağ isteği yapma.")
    args = parser.parse_args()
    app = Application(args.data_dir, args.config, args.hardware_db, not args.offline)
    server = make_server(app, args.host, args.port, os.environ.get("GC_API_TOKEN", ""))
    print(f"Garbage Collectors: http://{args.host}:{server.server_port}", flush=True)
    print(f"Kalibrasyon: {app.live.calibration['calibration_id']} | Simülasyon deposu ayrıdır.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()


if __name__ == "__main__":
    main()
