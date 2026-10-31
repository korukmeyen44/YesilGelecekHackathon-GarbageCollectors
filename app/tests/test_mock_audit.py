import hashlib
from pathlib import Path
import tempfile
import unittest

from app.mock_audit import analyze,hourly_windows,read_snapshot
from app.storage import Operations


class MockAuditTests(unittest.TestCase):
    def test_hourly_rate_excludes_collection_quality_and_gaps(self):
        rows=[(i*900,10+i,"ok") for i in range(9)]
        self.assertTrue(all(rate==4 for _,rate in hourly_windows(rows,[])))
        self.assertEqual(hourly_windows(rows,[3500,7100]),[])
        bad=[(t,f,"invalid" if t==3600 else q) for t,f,q in rows]
        self.assertEqual(hourly_windows(bad,[]),[])
        missing=[r for r in rows if r[0]!=3600]
        self.assertEqual(hourly_windows(missing,[]),[])

    def test_emptying_changes_are_not_fill_rate(self):
        rows=[(i*900,90+i if i<4 else 5+i,"ok") for i in range(9)]
        windows=hourly_windows(rows,[])
        self.assertEqual(windows,[(3600,4.0)])

    def test_duplicate_boundary_events_are_not_counted_as_independent_observed_drops(self):
        rows=[(i*900,90+i if i<4 else 5+i,"ok") for i in range(13)]
        b={"id":"S01","area":"Test","lat":40.99,"lng":39.77,"rate":2,"capacity_l":770,
           "fill_percent":17,"fault":"normal","source":"simulated"}
        data={"meta":{"demo_now":10800},"bins":[b],"samples":{"S01":rows},"digest":"test",
              "events":[{"bin_id":"S01","kind":"collection","ts":t} for t in (3500,3600,7200)]}
        a=analyze(data)
        self.assertEqual(a["observed_drops"],1)
        self.assertEqual(a["collection_records"],3)
        self.assertEqual(a["same_drop_extra_records"],1)
        self.assertEqual(a["unconfirmed_collection_records"],1)

    def test_read_only_snapshot_preserves_database_and_audits_current_generator(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"operations.sqlite3"
            ops=Operations(path,now=1793386977.8770509);ops.close()
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            a=analyze(read_snapshot(path))
            after=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(before,after)
            self.assertEqual(a["samples_count"],48420)
            self.assertEqual(a["missing_slots_estimate"],0)
            self.assertEqual(a["quality_counts"],{"ok":48420})
            self.assertEqual(a["rate_min"],.7)
            self.assertEqual(a["rate_max"],8)
            self.assertEqual(len(a["base_rates"]),8)
            self.assertEqual(a["capacities_l"],[770])
            self.assertEqual(a["current_faults"]["offline"],1)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"missing.sqlite3"
            with self.assertRaises(FileNotFoundError):read_snapshot(path)
            self.assertFalse(path.exists())


if __name__=="__main__":unittest.main()
