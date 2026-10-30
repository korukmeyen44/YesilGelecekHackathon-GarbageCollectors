"""Local MVP receiver: validated telemetry, SQLite history and calibrated fill.

Only the Python standard library is required. Not a public production service.
"""
from __future__ import annotations

import argparse
import copy
import hmac
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
UINT32_MAX = (1 << 32) - 1
MAX_BODY = 4096


class ValidationError(ValueError):
    pass


class IdentityConflict(ValueError):
    pass


def integer(value, name, minimum=0, maximum=UINT32_MAX):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationError(f"{name}: integer in [{minimum}, {maximum}] required")
    return value


def loads(text):
    def bad_constant(value):
        raise ValidationError(f"Non-finite JSON number: {value}")
    def unique_object(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValidationError(f"Duplicate JSON key: {key}")
            output[key] = value
        return output
    try:
        return json.loads(text, parse_constant=bad_constant, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValidationError(str(exc)) from exc


def validate_payload(p):
    if not isinstance(p, dict):
        raise ValidationError("JSON object required")
    integer(p.get("version"), "version", 1, 1)
    if p.get("source") not in ("rf", "simulator"):
        raise ValidationError("source must be rf or simulator")
    integer(p.get("node_id"), "node_id", 1, 3)
    integer(p.get("boot_id"), "boot_id", 1)
    for field in ("sequence", "measured_uptime_ms", "received_gateway_ms"):
        integer(p.get(field), field)
    integer(p.get("gateway_id"), "gateway_id", 1, 255)
    integer(p.get("gateway_boot_id"), "gateway_boot_id", 1)
    integer(p.get("age_ms"), "age_ms", 0, 60000)
    for field in ("http_dropped_total", "serial_dropped_total", "rf_rejected_total"):
        if field in p:
            integer(p[field], field)
    sensors = p.get("sensors")
    if not isinstance(sensors, list) or len(sensors) != 2:
        raise ValidationError("Exactly two sensor summaries required")
    for s in sensors:
        if not isinstance(s, dict):
            raise ValidationError("Sensor summary must be an object")
        count = integer(s.get("valid_samples"), "valid_samples", 0, 5)
        integer(s.get("error_mask"), "error_mask", 0, 15)
        spread = s.get("spread_mm")
        if count == 0:
            if spread is not None:
                raise ValidationError("No echoes requires null spread")
        else:
            integer(spread, "spread_mm", 0, 3980)
        status = s.get("status")
        if status == "ok":
            integer(s.get("distance_mm"), "distance_mm", 20, 4000)
            if count < 3 or spread > 80:
                raise ValidationError("ok requires >=3 echoes and spread <=80 mm")
        elif status in ("too_few", "unstable"):
            if s.get("distance_mm") is not None:
                raise ValidationError("Invalid measurement requires null distance")
            if status == "too_few" and count >= 3:
                raise ValidationError("too_few requires <3 echoes")
            if status == "unstable" and (count < 3 or spread <= 80):
                raise ValidationError("unstable requires >=3 echoes and spread >80 mm")
        else:
            raise ValidationError("Unknown sensor status")
    return p


def load_calibration(path):
    config = loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("calibration_id"), str):
        raise ValidationError("calibration_id required")
    if not config["calibration_id"]:
        raise ValidationError("calibration_id must not be empty")
    for key, minimum, maximum, default in (
        ("stale_after_ms", 1000, 60000, 15000),
        ("disagreement_percent", 1, 100, 20),
        ("jump_percent", 1, 100, 25),
        ("confirmation_cycles", 2, 10, 3),
        ("candidate_tolerance_percent", 1, 100, 8),
    ):
        config[key] = integer(config.get(key, default), key, minimum, maximum)
    nodes = config.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        raise ValidationError("nodes mapping required")
    for node_id, node in nodes.items():
        if node_id not in ("1", "2", "3") or not isinstance(node, dict):
            raise ValidationError("Unknown node in calibration")
        if type(node.get("calibrated")) is not bool:
            raise ValidationError("calibrated boolean required")
        sensors = node.get("sensors")
        if not isinstance(sensors, list) or len(sensors) != 2:
            raise ValidationError("Two independent sensor calibrations required")
        for sensor in sensors:
            if not isinstance(sensor, dict):
                raise ValidationError("Sensor calibration must be an object")
            full = integer(sensor.get("full_mm"), "full_mm", 20, 3999)
            integer(sensor.get("empty_mm"), "empty_mm", full + 1, 4000)
            sensor["geometry_margin_mm"] = integer(sensor.get("geometry_margin_mm", 50),
                                                     "geometry_margin_mm", 0, 500)
    return config


def analyze(payload, calibration):
    node = calibration["nodes"].get(str(payload["node_id"]))
    if node is None:
        raise ValidationError("Node not configured in calibration")
    values, statuses = [], []
    for summary, reference in zip(payload["sensors"], node["sensors"]):
        value = None
        status = summary["status"]
        if status == "ok":
            distance = summary["distance_mm"]
            if distance > reference["empty_mm"] + reference["geometry_margin_mm"]:
                status = "outside_geometry"
            else:
                value = round(max(0.0, min(100.0, 100 *
                    (reference["empty_mm"] - distance) /
                    (reference["empty_mm"] - reference["full_mm"]))), 1)
        values.append(value)
        statuses.append(status)
    available = [value for value in values if value is not None]
    quality = "invalid"
    fill = None
    if not node["calibrated"]:
        quality = "uncalibrated"
        values = [None, None]
    elif len(available) == 2:
        if abs(available[0] - available[1]) > calibration["disagreement_percent"]:
            quality = "sensor_disagreement"
        else:
            quality, fill = "ok", round(sum(available) / 2, 1)
    elif len(available) == 1:
        quality, fill = "degraded", available[0]
    return {"measurement_quality": quality, "fill_percent": fill,
            "sensor_fill_percent": values, "sensor_status": statuses,
            "calibration_id": calibration["calibration_id"]}


def newer(candidate, previous):
    delta = (candidate - previous) & UINT32_MAX
    return 0 < delta < (1 << 31)


def measurement_identity(payload):
    return {key: payload[key] for key in
            ("version", "source", "node_id", "boot_id", "sequence", "measured_uptime_ms", "sensors")}


class Store:
    def __init__(self, path, calibration):
        self.calibration = calibration
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS telemetry (
                node_id INTEGER NOT NULL, boot_id INTEGER NOT NULL, sequence INTEGER NOT NULL,
                received_at REAL NOT NULL, observed_at REAL NOT NULL,
                payload_json TEXT NOT NULL, result_json TEXT NOT NULL,
                PRIMARY KEY (node_id, boot_id, sequence)
            );
            CREATE TABLE IF NOT EXISTS latest (
                node_id INTEGER PRIMARY KEY, state_json TEXT NOT NULL
            );
        """)

    def close(self):
        with self.lock:
            self.db.close()

    def ingest(self, payload, now=None):
        validate_payload(payload)
        now = time.time() if now is None else now
        observed = now - payload["age_ms"] / 1000
        key = tuple(payload[k] for k in ("node_id", "boot_id", "sequence"))
        result = analyze(payload, self.calibration)
        with self.lock, self.db:
            existing = self.db.execute("SELECT payload_json, result_json FROM telemetry "
                                       "WHERE node_id=? AND boot_id=? AND sequence=?", key).fetchone()
            if existing:
                if measurement_identity(loads(existing[0])) != measurement_identity(payload):
                    raise IdentityConflict("Same measurement identity carries different data")
                return {"inserted": False, "duplicate": True, "result": loads(existing[1])}
            row = self.db.execute("SELECT state_json FROM latest WHERE node_id=?", key[:1]).fetchone()
            previous = loads(row[0]) if row else None
            ordered = (previous is None or newer(payload["boot_id"], previous["boot_id"]) or
                       (payload["boot_id"] == previous["boot_id"] and
                        newer(payload["sequence"], previous["sequence"])))
            # Measurements queued longer than the freshness limit cannot advance current state.
            fresh = payload["age_ms"] <= self.calibration["stale_after_ms"]
            result["out_of_order"] = not ordered
            if ordered and fresh:
                state = self._advance(payload, result, previous, now, observed)
                result = state["result"]
                self.db.execute("INSERT OR REPLACE INTO latest VALUES (?, ?)",
                                (payload["node_id"], json.dumps(state, allow_nan=False)))
            self.db.execute("INSERT INTO telemetry VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (*key, now, observed, json.dumps(payload, allow_nan=False),
                             json.dumps(result, allow_nan=False)))
        return {"inserted": True, "duplicate": False, "result": result}

    def _advance(self, p, result, previous, now, observed):
        same_calibration = previous and previous["result"]["calibration_id"] == self.calibration["calibration_id"]
        state = copy.deepcopy(previous) if same_calibration else {
            "last_valid_fill_percent": None, "last_valid_at": None, "pending": None,
            "sequence_gap_total": 0,
        }
        if previous and p["boot_id"] == previous["boot_id"]:
            gap = ((p["sequence"] - previous["sequence"]) & UINT32_MAX) - 1
            state["sequence_gap_total"] += gap
            if gap:
                state["pending"] = None
        elif previous:
            state["pending"] = None
        if previous and observed - previous["observed_at"] > self.calibration["stale_after_ms"] / 1000:
            state["pending"] = None
        candidate = result["fill_percent"]
        last = state["last_valid_fill_percent"]
        if candidate is None:
            state["pending"] = None
        elif last is not None and abs(candidate - last) >= self.calibration["jump_percent"]:
            pending = state["pending"]
            if pending and abs(candidate - pending["value"]) <= self.calibration["candidate_tolerance_percent"]:
                pending["count"] += 1
            else:
                pending = {"value": candidate, "count": 1}
            state["pending"] = pending
            if pending["count"] < self.calibration["confirmation_cycles"]:
                result["measurement_quality"] = "change_pending"
                result["fill_percent"] = None
            else:
                state["last_valid_fill_percent"], state["last_valid_at"] = candidate, observed
                state["pending"] = None
        else:
            state["last_valid_fill_percent"], state["last_valid_at"] = candidate, observed
            state["pending"] = None
        state.update(node_id=p["node_id"], boot_id=p["boot_id"], sequence=p["sequence"],
                     source=p["source"], received_at=now, observed_at=observed, result=result,
                     sensors=p["sensors"], measured_uptime_ms=p["measured_uptime_ms"],
                     gateway_id=p["gateway_id"], gateway_boot_id=p["gateway_boot_id"])
        return state

    def latest(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            rows = self.db.execute("SELECT state_json FROM latest ORDER BY node_id").fetchall()
        output = []
        for row in rows:
            state = loads(row[0])
            age_ms = max(0, round((now - state["observed_at"]) * 1000))
            result = copy.deepcopy(state["result"])
            result.update(node_id=state["node_id"], boot_id=state["boot_id"],
                          sequence=state["sequence"], source=state["source"], age_ms=age_ms,
                          sensors=state.get("sensors"),
                          measured_uptime_ms=state.get("measured_uptime_ms"),
                          gateway_id=state.get("gateway_id"), gateway_boot_id=state.get("gateway_boot_id"),
                          freshness="stale" if age_ms > self.calibration["stale_after_ms"] else "fresh",
                          received_at=datetime.fromtimestamp(state["received_at"], timezone.utc).isoformat(),
                          last_valid_fill_percent=state["last_valid_fill_percent"],
                          last_valid_age_ms=None if state["last_valid_at"] is None else
                          max(0, round((now - state["last_valid_at"]) * 1000)),
                          sequence_gap_total=state["sequence_gap_total"])
            if result["freshness"] == "stale":
                result["fill_percent"] = None
            if result["calibration_id"] != self.calibration["calibration_id"]:
                result["measurement_quality"] = "calibration_changed"
                result["fill_percent"] = None
                result["last_valid_fill_percent"] = None
            output.append(result)
        return output


def make_server(store, host="127.0.0.1", port=8080, token=""):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def reply(self, code, body):
            data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            if token and not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.reply(401, {"error": "Unauthorized"})
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            if self.path == "/health":
                self.reply(200, {"status": "ok", "scope": "local_hackathon_mvp"})
            elif self.path == "/api/latest":
                self.reply(200, {"nodes": store.latest()})
            else:
                self.reply(404, {"error": "Not found"})

        def do_POST(self):
            if not self.authorized():
                return
            if self.path != "/api/telemetry":
                self.reply(404, {"error": "Not found"})
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"error": "application/json required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
                if not 0 < length <= MAX_BODY:
                    self.reply(413 if length > MAX_BODY else 411, {"error": "Invalid body length"})
                    return
                data = self.rfile.read(length)
                if len(data) != length:
                    raise ValidationError("Incomplete request body")
                outcome = store.ingest(loads(data))
                self.reply(201 if outcome["inserted"] else 200, outcome)
            except IdentityConflict as exc:
                self.reply(409, {"error": str(exc)})
            except (ValueError, TypeError) as exc:
                self.reply(400, {"error": str(exc)})
            except sqlite3.Error:
                self.reply(503, {"error": "Storage unavailable; retry the same measurement"})

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/calibration.example.json")
    parser.add_argument("--db", type=Path, default=ROOT / ".build/telemetry.sqlite3")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--stdin", action="store_true", help="Ingest JSON lines instead of running HTTP")
    args = parser.parse_args()
    calibration = load_calibration(args.config)
    args.db.parent.mkdir(parents=True, exist_ok=True)
    store = Store(args.db, calibration)
    try:
        if args.stdin:
            for line in sys.stdin:
                if not line.strip() or line.startswith("#"):
                    continue
                try:
                    if len(line.encode("utf-8")) > MAX_BODY:
                        raise ValidationError("Line too long")
                    print(json.dumps(store.ingest(loads(line)), ensure_ascii=False))
                except (ValidationError, IdentityConflict) as exc:
                    print(f"Rejected: {exc}", file=sys.stderr)
        else:
            server = make_server(store, args.host, args.port, os.environ.get("GC_API_TOKEN", ""))
            print(f"Receiver: http://{args.host}:{server.server_port}; calibration={calibration['calibration_id']}")
            try:
                server.serve_forever()
            finally:
                server.server_close()
    except KeyboardInterrupt:
        pass
    finally:
        store.close()


if __name__ == "__main__":
    main()

