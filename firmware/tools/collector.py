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
    integer(p.get("version"), "version (v2 firmware required)", 2, 2)
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
    if "sensors" in p:
        raise ValidationError("v2 accepts one combined measurement, not separate sensor distances")
    m = p.get("measurement")
    if not isinstance(m, dict):
        raise ValidationError("One combined measurement object required")
    attempted = integer(m.get("attempted_pairs"), "attempted_pairs", 10, 10)
    count = integer(m.get("valid_pairs"), "valid_pairs", 0, attempted)
    integer(m.get("window_duration_ms"), "window_duration_ms", 1, 60000)
    counts, errors = m.get("valid_samples"), m.get("error_masks")
    if not isinstance(counts, list) or len(counts) != 2 or not isinstance(errors, list) or len(errors) != 2:
        raise ValidationError("Two diagnostic sample counts/error masks required")
    for n, error in zip(counts, errors):
        integer(n, "valid_samples", count, attempted)
        integer(error, "error_mask", 0, 15)
        if (n == attempted) != (error == 0):
            raise ValidationError("Failed readings must carry an error mask")
    if sum(counts) > attempted + count:
        raise ValidationError("Inconsistent paired sample counts")
    spread = m.get("spread_mm")
    if count == 0:
        if spread is not None:
            raise ValidationError("No valid pairs requires null spread")
    else:
        integer(spread, "spread_mm", 0, 3980)
    status = m.get("status")
    if status in ("ok", "degraded"):
        integer(m.get("distance_mm"), "distance_mm", 20, 4000)
        if count < 6 or spread > 80 or ((status == "ok") != (count == attempted)):
            raise ValidationError("Accepted mean requires >=6 stable pairs; ok requires all 10")
    elif status in ("too_few", "unstable"):
        if m.get("distance_mm") is not None:
            raise ValidationError("Invalid measurement requires null distance")
        if status == "too_few" and count >= 6:
            raise ValidationError("too_few requires <6 valid pairs")
        if status == "unstable" and (count < 6 or spread <= 80):
            raise ValidationError("unstable requires >=6 pairs and spread >80 mm")
    else:
        raise ValidationError("Unknown measurement status")
    return p


def load_calibration(path):
    config = loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("calibration_id"), str):
        raise ValidationError("calibration_id required")
    if not config["calibration_id"]:
        raise ValidationError("calibration_id must not be empty")
    for key, minimum, maximum, default in (
        ("stale_after_ms", 25000, 60000, 35000),
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
        reference = node.get("measurement")
        if not isinstance(reference, dict):
            raise ValidationError("v2 requires one measurement calibration per bin; recalibrate the combined mean")
        full = integer(reference.get("full_mm"), "full_mm", 20, 3999)
        integer(reference.get("empty_mm"), "empty_mm", full + 1, 4000)
        reference["geometry_margin_mm"] = integer(reference.get("geometry_margin_mm", 50),
                                                 "geometry_margin_mm", 0, 500)
    return config


def analyze(payload, calibration):
    node = calibration["nodes"].get(str(payload["node_id"]))
    if node is None:
        raise ValidationError("Node not configured in calibration")
    measurement, reference = payload["measurement"], node["measurement"]
    quality, fill = "invalid", None
    if not node["calibrated"]:
        quality = "uncalibrated"
    elif measurement["status"] in ("ok", "degraded"):
        distance = measurement["distance_mm"]
        if distance > reference["empty_mm"] + reference["geometry_margin_mm"]:
            quality = "outside_geometry"
        else:
            fill = round(max(0.0, min(100.0, 100 *
                (reference["empty_mm"] - distance) /
                (reference["empty_mm"] - reference["full_mm"]))), 1)
            quality = measurement["status"]
    return {"measurement_quality": quality, "fill_percent": fill,
            "calibration_id": calibration["calibration_id"]}


def newer(candidate, previous):
    delta = (candidate - previous) & UINT32_MAX
    return 0 < delta < (1 << 31)


def measurement_identity(payload):
    return {key: payload.get(key) for key in
            ("version", "source", "node_id", "boot_id", "sequence", "measured_uptime_ms", "measurement")}


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
                     measurement=p["measurement"], measured_uptime_ms=p["measured_uptime_ms"],
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
                          measurement=state.get("measurement"),
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

