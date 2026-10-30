import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from collector import (IdentityConflict, Store, ValidationError, analyze, load_calibration,
                       loads, make_server, validate_payload)
from simulate import scenario, sensor
from serial_bridge import LineFramer


def record(sequence=1, distances=(220, 220), boot=1):
    p = next(scenario(boot))
    p["sequence"] = sequence
    p["sensors"] = [sensor(d, "ok" if d is not None else "too_few") for d in distances]
    return p


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.config = load_calibration(ROOT / "config/calibration.demo.json")
        self.store = Store(":memory:", self.config)

    def tearDown(self):
        self.store.close()

    def test_calibration_endpoints_and_midpoint(self):
        for d, expected in ((400, 0), (220, 50), (40, 100), (20, 100)):
            with self.subTest(d=d):
                self.assertEqual(analyze(record(distances=(d, d)), self.config)["fill_percent"], expected)

    def test_independent_sensor_calibrations(self):
        self.config["nodes"]["1"]["sensors"][1]["empty_mm"] = 600
        self.config["nodes"]["1"]["sensors"][1]["full_mm"] = 100
        self.assertEqual(analyze(record(distances=(220, 350)), self.config)["fill_percent"], 50)

    def test_missing_echo_is_not_empty_or_full(self):
        result = analyze(record(distances=(None, None)), self.config)
        self.assertIsNone(result["fill_percent"])
        self.assertEqual(result["measurement_quality"], "invalid")

    def test_single_sensor_is_degraded(self):
        result = analyze(record(distances=(None, 220)), self.config)
        self.assertEqual(result["fill_percent"], 50)
        self.assertEqual(result["measurement_quality"], "degraded")

    def test_disagreement_is_not_silently_averaged(self):
        result = analyze(record(distances=(40, 400)), self.config)
        self.assertIsNone(result["fill_percent"])
        self.assertEqual(result["measurement_quality"], "sensor_disagreement")

    def test_geometry_error_does_not_become_empty(self):
        result = analyze(record(distances=(900, 900)), self.config)
        self.assertIsNone(result["fill_percent"])
        self.assertEqual(result["sensor_status"], ["outside_geometry", "outside_geometry"])

    def test_example_calibration_does_not_claim_real_fill(self):
        c = load_calibration(ROOT / "config/calibration.example.json")
        result = analyze(record(), c)
        self.assertIsNone(result["fill_percent"])
        self.assertEqual(result["measurement_quality"], "uncalibrated")

    def test_duplicate_retry_is_idempotent_despite_different_gateway_age(self):
        p = record()
        self.assertTrue(self.store.ingest(p, 100)["inserted"])
        p["age_ms"] = 1000
        p["gateway_boot_id"] += 1
        self.assertFalse(self.store.ingest(p, 102)["inserted"])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0], 1)
        self.assertEqual(self.store.latest(102)[0]["age_ms"], 2000)

    def test_identity_collision_detected(self):
        self.store.ingest(record(), 100)
        with self.assertRaises(IdentityConflict):
            self.store.ingest(record(distances=(400, 400)), 101)

    def test_old_sequence_and_previous_boot_do_not_replace_latest(self):
        self.store.ingest(record(10, boot=2), 100)
        self.store.ingest(record(9, distances=(400, 400), boot=2), 101)
        self.store.ingest(record(100, distances=(400, 400), boot=1), 102)
        latest = self.store.latest(102)[0]
        self.assertEqual((latest["boot_id"], latest["sequence"], latest["fill_percent"]), (2, 10, 50))

    def test_reboot_and_sequence_wrap(self):
        self.store.ingest(record(0xFFFFFFFF), 100)
        self.store.ingest(record(0), 101)
        self.assertEqual(self.store.latest(101)[0]["sequence"], 0)
        self.store.ingest(record(1, boot=2), 102)
        self.assertEqual(self.store.latest(102)[0]["boot_id"], 2)

    def test_stale_data_has_no_current_fill(self):
        self.store.ingest(record(), 100)
        latest = self.store.latest(116)[0]
        self.assertEqual(latest["freshness"], "stale")
        self.assertIsNone(latest["fill_percent"])
        self.assertEqual(latest["last_valid_fill_percent"], 50)

    def test_queue_age_is_used_and_very_old_data_cannot_advance_latest(self):
        p = record()
        p["age_ms"] = 14000
        self.store.ingest(p, 100)
        self.assertEqual(self.store.latest(102)[0]["freshness"], "stale")
        p = record(2, distances=(400, 400))
        p["age_ms"] = 20000
        self.store.ingest(p, 103)
        self.assertEqual(self.store.latest(103)[0]["sequence"], 1)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0], 2)

    def test_invalid_new_measurement_preserves_only_labelled_last_good_value(self):
        self.store.ingest(record(), 100)
        self.store.ingest(record(2, distances=(None, None)), 104)
        latest = self.store.latest(104)[0]
        self.assertIsNone(latest["fill_percent"])
        self.assertEqual(latest["measurement_quality"], "invalid")
        self.assertEqual(latest["last_valid_fill_percent"], 50)
        self.assertEqual(latest["last_valid_age_ms"], 4000)

    def test_large_change_requires_three_cycles_and_accepts_emptying(self):
        self.store.ingest(record(distances=(40, 40)), 100)
        for sequence in (2, 3):
            outcome = self.store.ingest(record(sequence, (400, 400)), 100 + sequence)
            self.assertEqual(outcome["result"]["measurement_quality"], "change_pending")
            self.assertIsNone(outcome["result"]["fill_percent"])
        self.store.ingest(record(4, (400, 400)), 104)
        self.assertEqual(self.store.latest(104)[0]["fill_percent"], 0)

    def test_invalid_or_missing_cycle_resets_change_confirmation(self):
        self.store.ingest(record(distances=(400, 400)), 100)
        self.store.ingest(record(2, (40, 40)), 101)
        self.store.ingest(record(3, (None, None)), 102)
        self.store.ingest(record(4, (40, 40)), 103)
        self.assertEqual(self.store.latest(103)[0]["measurement_quality"], "change_pending")
        self.store.ingest(record(6, (40, 40)), 104)
        self.store.ingest(record(7, (40, 40)), 105)
        self.assertIsNone(self.store.latest(105)[0]["fill_percent"])
        self.store.ingest(record(8, (40, 40)), 106)
        self.assertEqual(self.store.latest(106)[0]["fill_percent"], 100)

    def test_changed_calibration_invalidates_old_current_result(self):
        self.store.ingest(record(), 100)
        self.config["calibration_id"] = "new-calibration"
        latest = self.store.latest(101)[0]
        self.assertIsNone(latest["fill_percent"])
        self.assertIsNone(latest["last_valid_fill_percent"])
        self.assertEqual(latest["measurement_quality"], "calibration_changed")

    def test_state_survives_receiver_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.sqlite3"
            first = Store(path, self.config)
            first.ingest(record(), 100)
            first.close()
            second = Store(path, self.config)
            try:
                self.assertEqual(second.latest(101)[0]["fill_percent"], 50)
                self.assertFalse(second.ingest(record(), 102)["inserted"])
            finally:
                second.close()

    def test_malformed_and_inconsistent_telemetry_rejected(self):
        variants = []
        for key, value in (("node_id", 4), ("node_id", True), ("boot_id", 0),
                           ("age_ms", -1), ("age_ms", 70000), ("source", "unknown"),
                           ("sequence", 1.5), ("version", 2)):
            p = record(); p[key] = value; variants.append(p)
        for key, value in (("distance_mm", 0), ("valid_samples", 2),
                           ("status", "garbage"), ("spread_mm", 100), ("error_mask", 16)):
            p = record(); p["sensors"][0][key] = value; variants.append(p)
        p = record(); p["sensors"] = []; variants.append(p)
        for p in variants:
            with self.subTest(p=p), self.assertRaises(ValidationError):
                validate_payload(p)
        for data in ('{"x":NaN}', '{"x":1,"x":2}', '{broken'):
            with self.assertRaises(ValidationError):
                loads(data)

    def test_zero_width_and_invalid_calibration_rejected(self):
        for mutate in (lambda c: c["nodes"]["1"]["sensors"][0].update(full_mm=400),
                       lambda c: c.update(stale_after_ms=0),
                       lambda c: c["nodes"]["1"].update(calibrated="yes")):
            config = copy.deepcopy(self.config)
            mutate(config)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "bad.json"
                path.write_text(json.dumps(config))
                with self.assertRaises(ValidationError):
                    load_calibration(path)

    def test_production_cpp_gateway_json_is_accepted_by_python(self):
        fixture = os.environ.get("GC_CPP_JSON_FIXTURE")
        if not fixture:
            self.skipTest("Run tools/run_tests.py for production C++ JSON integration")
        payload = validate_payload(loads(Path(fixture).read_text()))
        result = self.store.ingest(payload, 100)["result"]
        self.assertEqual(result["measurement_quality"], "degraded")
        self.assertEqual(result["fill_percent"], 50)
        self.assertEqual(payload["boot_id"], 0x12345678)
        latest = self.store.latest(100)[0]
        self.assertEqual(latest["sensors"], payload["sensors"])
        self.assertEqual(latest["gateway_boot_id"], 17)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:", load_calibration(ROOT / "config/calibration.demo.json"))
        self.server = make_server(self.store, port=0, token="test-token")
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02})
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.store.close()

    def request(self, path, body=None, authorized=True, content_type="application/json"):
        headers = {"Content-Type": content_type}
        if authorized:
            headers["Authorization"] = "Bearer test-token"
        req = Request(self.base + path, data=body, headers=headers,
                      method="POST" if body is not None else "GET")
        try:
            response = urlopen(req, timeout=3)
        except HTTPError as exc:
            response = exc
        with response:
            return response.code, json.loads(response.read())

    def test_real_http_post_duplicate_and_read(self):
        data = json.dumps(record()).encode()
        self.assertEqual(self.request("/api/telemetry", data)[0], 201)
        self.assertEqual(self.request("/api/telemetry", data)[0], 200)
        code, body = self.request("/api/latest")
        self.assertEqual(code, 200)
        self.assertEqual(body["nodes"][0]["fill_percent"], 50)
        self.assertEqual(self.request("/health")[0], 200)

    def test_http_rejects_auth_schema_bad_json_and_oversize(self):
        data = json.dumps(record()).encode()
        self.assertEqual(self.request("/api/telemetry", data, authorized=False)[0], 401)
        self.assertEqual(self.request("/api/latest", authorized=False)[0], 401)
        self.assertEqual(self.request("/api/telemetry", b"{broken")[0], 400)
        self.assertEqual(self.request("/api/telemetry", data, content_type="text/plain")[0], 415)
        self.assertEqual(self.request("/api/telemetry", b" " * 4097)[0], 413)
        self.assertEqual(self.request("/missing", data)[0], 404)

    def test_http_identity_conflict_returns_409(self):
        self.request("/api/telemetry", json.dumps(record()).encode())
        self.assertEqual(self.request("/api/telemetry", json.dumps(record(distances=(400, 400))).encode())[0], 409)


class SerialFramingTests(unittest.TestCase):
    def test_fragmented_and_multiple_lines(self):
        framer = LineFramer()
        self.assertEqual(framer.feed(b'{"x":'), [])
        self.assertEqual(framer.feed(b'1}\n# stats\n'), [b'{"x":1}', b'# stats'])

    def test_oversized_line_is_discarded_until_newline(self):
        framer = LineFramer()
        self.assertEqual(framer.feed(b'x' * 5000), [])
        self.assertEqual(framer.feed(b'fragment\n{}\n'), [b'{}'])
        self.assertEqual(framer.dropped, 1)


if __name__ == "__main__":
    unittest.main()

