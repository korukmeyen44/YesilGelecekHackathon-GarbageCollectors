import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.domain import DEFAULTS, decorate, forecast
from app.routing import optimize, tour_cost
from app.server import Application, ROOT, make_server


class ForecastTests(unittest.TestCase):
    def samples(self, end=7200, rate=8):
        return [(t, 20+rate*t/3600) for t in range(0, end+1, 300)]

    def test_known_slope_and_threshold(self):
        f = forecast(self.samples(), 7200, 80)
        self.assertEqual(f["rate_pph"], 8)
        self.assertEqual(f["hours_to_threshold"], 5.5)

    def test_future_samples_cannot_change_prediction(self):
        rows = self.samples()
        self.assertEqual(forecast(rows, 7200), forecast(rows+[(7500,100)], 7200))

    def test_emptying_starts_a_new_cycle(self):
        rows = self.samples() + [(7500, 5),(7800,6),(8100,7)]
        self.assertFalse(forecast(rows,8100)["available"])

    def test_gap_is_not_bridged(self):
        rows = self.samples() + [(12000,70),(12300,71)]
        self.assertFalse(forecast(rows,12300)["available"])

    def test_flat_and_insufficient_series_have_no_eta(self):
        self.assertFalse(forecast([(0,20),(300,21)],300)["available"])
        self.assertFalse(forecast([(t,30) for t in range(0,7201,300)],7200)["available"])

    def test_collection_boundary_discards_pre_collection_samples(self):
        self.assertFalse(forecast(self.samples(),7200,boundary=7000)["available"])

    def test_unknown_bin_does_not_become_empty_or_automatically_selected(self):
        b = decorate({"id":"x","capacity_l":770,"fill_percent":None,"freshness":"stale","measurement_quality":"ok"}, [], DEFAULTS, 7200)
        self.assertFalse(b["selected"])
        self.assertEqual(b["estimated_load_l"],770)
        self.assertIsNone(b["fill_percent"])

    def test_manual_unknown_bin_uses_full_capacity_assumption(self):
        b=decorate({"id":"x","capacity_l":770,"fill_percent":None,"freshness":"stale","measurement_quality":"ok","override":"include"},[],DEFAULTS,7200)
        self.assertTrue(b["selected"])
        self.assertEqual(b["estimated_load_l"],770)


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Application(self.temp.name, ROOT.parent / "firmware/config/calibration.demo.json", roads_enabled=False)

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def plan(self, key="test-plan-key-001", **kwargs):
        return self.app.action("/api/plan", {"scope":"demo","online":False,"request_key":key,**kwargs})

    def test_25_bins_and_no_fabricated_live_measurements(self):
        d=self.app.dashboard()
        self.assertEqual(len(d["bins"]),25)
        live=[b for b in d["bins"] if b["source"]=="live"]
        self.assertTrue(all(b["fill_percent"] is None and not b["selected"] for b in live))
        self.assertEqual(self.app.live.db.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0],0)

    def test_demo_advance_is_persistent_and_does_not_write_physical_store(self):
        before=self.app.ops.get("demo_now")
        self.app.action("/api/demo/advance",{"hours":1})
        self.assertEqual(self.app.ops.get("demo_now"),before+3600)
        self.assertEqual(self.app.live.latest(),[])
        self.app.close()
        self.app=Application(self.temp.name,ROOT.parent/"firmware/config/calibration.demo.json",roads_enabled=False)
        self.assertEqual(self.app.ops.get("demo_now"),before+3600)

    def test_offline_plan_is_explicit_and_all_stops_obey_capacity(self):
        p=self.plan()
        self.assertEqual(p["mode"],"approximate")
        self.assertFalse(p["road_geometry"])
        self.assertGreater(len(p["stops"]),0)
        self.assertLessEqual(p["estimated_load_l"],p["capacity_l"])
        self.assertGreaterEqual(p["ordering_minutes_saved"],0)

    def test_capacity_and_time_constraints_report_unserved(self):
        self.app.action("/api/settings",{"truck_capacity_l":500,"shift_minutes":10})
        p=self.plan()
        self.assertGreater(len(p["unserved"]),0)
        self.assertLessEqual(p["estimated_load_l"],500)
        self.assertLessEqual(p["recommended"]["minutes"],10)
        self.assertFalse(p["comparable"])
        self.assertIsNone(p["savings"])

    def test_plan_request_id_is_idempotent(self):
        first=self.plan()
        self.assertEqual(first["id"],self.plan()["id"])
        self.assertEqual(self.app.ops.db.execute("SELECT COUNT(*) FROM plans").fetchone()[0],1)

    def test_completion_is_idempotent_and_does_not_touch_live_telemetry(self):
        p=self.plan()
        self.app.action("/api/plan/complete",{"plan_id":p["id"]})
        count=self.app.ops.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.app.action("/api/plan/complete",{"plan_id":p["id"]})
        self.assertEqual(count,self.app.ops.db.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        self.assertTrue(all(self.app.detail(s["id"])["fill_percent"]==5 for s in p["stops"]))
        self.assertEqual(self.app.live.latest(),[])

    def test_changed_settings_make_plan_stale_and_block_completion(self):
        p=self.plan()
        self.assertFalse(self.app.dashboard()["latest_plan"]["stale"])
        self.app.action("/api/settings",{"threshold":85})
        self.assertTrue(self.app.dashboard()["latest_plan"]["stale"])
        with self.assertRaises(ValueError):
            self.app.action("/api/plan/complete",{"plan_id":p["id"]})

    def test_critical_manual_exclusion_remains_visible_as_risk(self):
        self.app.action("/api/override",{"bin_id":"S01","mode":"exclude"})
        p=self.plan()
        self.assertNotIn("S01",[s["id"] for s in p["stops"]])
        self.assertIn("S01",[r["id"] for r in p["deferred_risks"]])

    def test_invalid_settings_rejected_without_mutation(self):
        old=self.app.ops.settings()
        for patch in ({"threshold":float("nan")},{"threshold":101},{"use_degraded":1},{"unknown":3}):
            with self.assertRaises(ValueError): self.app.action("/api/settings",patch)
        self.assertEqual(old,self.app.ops.settings())

    def test_degraded_policy_is_explicit(self):
        self.assertFalse(self.app.detail("S24")["usable"])
        self.app.action("/api/settings",{"use_degraded":True})
        self.assertTrue(self.app.detail("S24")["usable"])

    def test_live_scope_never_contains_demo_bins(self):
        p=self.plan(scope="live")
        self.assertEqual(p["stops"],[])
        with self.assertRaises(ValueError):self.app.action("/api/plan/complete",{"plan_id":p["id"]})

    def test_live_collection_can_be_recorded_after_sensor_changes(self):
        from simulate import scenario, measurement
        payload=next(scenario(100));payload["source"]="rf"
        self.app.live.ingest(payload)
        self.app.action("/api/override",{"bin_id":"H1","mode":"include"})
        p=self.plan(scope="live")
        for sequence in (2,3,4):
            payload["sequence"]=sequence
            payload["measurement"]=measurement(220)
            self.app.live.ingest(payload)
        self.assertTrue(self.app.dashboard()["latest_plan"]["stale"])
        self.app.action("/api/plan/complete",{"plan_id":p["id"]})
        self.assertEqual(self.app.live.latest()[0]["fill_percent"],50)

    def test_offline_bin_age_increases_while_unseen_fill_is_not_exposed(self):
        before=self.app.detail("S22")
        self.app.action("/api/demo/advance",{"hours":1})
        after=self.app.detail("S22")
        self.assertEqual(after["age_ms"]-before["age_ms"],3600000)
        self.assertIsNone(after["fill_percent"])
        self.assertEqual(before["last_valid_fill_percent"],after["last_valid_fill_percent"])

    def test_explicit_approximation_does_not_use_cached_road_matrix(self):
        points=[{"lat":40.99,"lng":39.77},{"lat":40.991,"lng":39.771}]
        self.app.roads.enabled=True
        value={"code":"Ok","durations":[[0,30],[40,0]],"distances":[[0,300],[400,0]]}
        with patch.object(self.app.roads,"fetch",return_value=value):
            self.assertEqual(self.app.roads.matrix(points,DEFAULTS)["mode"],"road")
        self.assertEqual(self.app.roads.matrix(points,DEFAULTS,online=False)["mode"],"approximate")

    def test_collection_retry_writes_one_event(self):
        body={"bin_id":"S02","request_key":"collect-request-001"}
        self.app.action("/api/collection",body)
        count=self.app.ops.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.app.action("/api/collection",body)
        self.assertEqual(count,self.app.ops.db.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def test_physical_collection_record_does_not_forge_a_sensor_reading(self):
        from simulate import scenario
        payload=next(scenario(100));payload["source"]="rf"
        self.app.live.ingest(payload)
        before=copy.deepcopy(self.app.live.latest()[0]["fill_percent"])
        self.app.action("/api/collection",{"bin_id":"H1","request_key":"physical-collection-001"})
        self.assertEqual(self.app.live.latest()[0]["fill_percent"],before)
        self.assertEqual(self.app.ops.db.execute("SELECT source FROM events WHERE bin_id='H1'").fetchone()[0],"live_operator_record")

    def test_directed_solver_never_worsens_fixed_order(self):
        matrix=[[0,4,9,3],[8,0,2,10],[2,9,0,4],[5,2,7,0]]
        order=optimize([1,2,3],matrix)
        self.assertEqual(set(order[1:-1]),{1,2,3})
        self.assertEqual(order[0],0)
        self.assertEqual(order[-1],0)
        self.assertLessEqual(tour_cost(order,matrix),tour_cost([0,1,2,3,0],matrix))

    def test_http_auth_telemetry_validation_and_static_assets(self):
        from simulate import scenario
        server=make_server(self.app,port=0,token="test-key")
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f"http://127.0.0.1:{server.server_port}"
        def request(path,body=None,auth=True):
            headers={"Content-Type":"application/json"}
            if auth:headers["Authorization"]="Bearer test-key"
            return urlopen(Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers),timeout=5)
        try:
            with self.assertRaises(HTTPError) as e:request("/api/dashboard",auth=False)
            self.assertEqual(e.exception.code,401)
            with request("/") as response:self.assertIn("Garbage Collectors",response.read().decode())
            p=next(scenario(100))
            with self.assertRaises(HTTPError) as e:request("/api/telemetry",p)
            self.assertEqual(e.exception.code,400)
            p["source"]="rf"
            with request("/api/telemetry",p) as r:self.assertEqual(r.status,201)
            with request("/api/telemetry",p) as r:self.assertEqual(r.status,200)
            with request("/api/dashboard") as r:
                live=[b for b in json.load(r)["bins"] if b["source"]=="live"]
                self.assertEqual(live[0]["fill_percent"],0)
                self.assertEqual(len(live),1)
            with self.assertRaises(HTTPError) as e:request("/../config.json")
            self.assertEqual(e.exception.code,404)
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__ == "__main__":
    unittest.main()
