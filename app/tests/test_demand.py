import json
import tempfile
import time
import unittest

from app.demand import historical_demand
from app.server import Application, ROOT


class HistoricalDemandTests(unittest.TestCase):
    now = 1_800_000_000

    def series(self, rate, hours=48):
        return [(self.now-hours*3600+i*900, 5+(i*rate/4)%85) for i in range(hours*4+1)]

    def test_fast_and_slow_cycles_are_distinguished(self):
        for rate in (.7, 2, 8):
            d = historical_demand(self.series(rate), self.now)
            self.assertTrue(d['available'])
            self.assertAlmostEqual(d['rate_pph'], rate, places=2)

    def test_emptying_is_not_negative_waste_or_an_added_positive_jump(self):
        d = historical_demand(self.series(8), self.now)
        self.assertEqual(d['rate_pph'], 8)

    def test_duplicate_packet_frequency_and_future_rows_do_not_inflate_rate(self):
        rows = self.series(1)
        expected = historical_demand(rows, self.now)
        self.assertEqual(historical_demand(rows*3+[(self.now+900, 100)], self.now), expected)

    def test_invalid_gaps_do_not_create_demand(self):
        rows = [(t, None if i%3==0 else f) for i, (t, f) in enumerate(self.series(2))]
        d = historical_demand(rows, self.now)
        self.assertFalse(d['available'])
        self.assertIsNone(d['pressure'])
        sparse = [(t, f) for i, (t, f) in enumerate(self.series(2)) if i%4==0]
        self.assertFalse(historical_demand(sparse, self.now)['available'])

    def test_insufficient_or_old_history_is_unknown_not_low(self):
        self.assertFalse(historical_demand(self.series(2, 6), self.now)['available'])
        self.assertFalse(historical_demand(self.series(2), self.now+3*86400)['available'])
        self.assertIsNone(historical_demand([], self.now)['rate_pph'])

    def test_flat_and_noisy_series_are_low_not_accumulated_upticks(self):
        rows = [(t, 30+(.2 if i%2 else 0)) for i, (t, _) in enumerate(self.series(0))]
        self.assertEqual(historical_demand(rows, self.now)['rate_pph'], 0)

    def test_known_small_emptying_boundary_splits_growth(self):
        rows = [(t, f-(10 if i>=96 else 0)) for i, (t, f) in enumerate(self.series(1))]
        d = historical_demand(rows, self.now, [rows[96][0]])
        self.assertEqual(d['rate_pph'], 1)

    def test_saturation_is_reported_as_a_limitation(self):
        d = historical_demand([(t, 100) for t, _ in self.series(0)], self.now)
        self.assertTrue(d['available'])
        self.assertEqual(d['rate_pph'], 0)
        self.assertGreater(d['saturated_hours'], 40)


class DemandIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Application(self.temp.name, ROOT.parent/'firmware/config/calibration.demo.json', roads_enabled=False)

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def test_dashboard_history_varies_and_live_has_no_fabricated_score(self):
        bins = self.app.dashboard()['bins']
        rates = [b['demand']['rate_pph'] for b in bins if b['source']=='simulated']
        self.assertGreater(max(rates), 5)
        self.assertLess(min(rates), 1)
        self.assertTrue(all(b['demand']['pressure'] is None for b in bins if b['source']=='live'))
        self.assertEqual(self.app.live.db.execute('SELECT COUNT(*) FROM telemetry').fetchone()[0], 0)

    def test_current_fill_and_forecast_settings_cannot_change_historical_rate(self):
        before = self.app.detail('S03')['demand']
        b = next(b for b in self.app.ops.demo_bins() if b['id']=='S03')
        b['fill_percent'] = 3
        with self.app.ops.db:
            self.app.ops.save_bin(b)
        self.app.action('/api/settings', {'threshold':95, 'horizon_hours':24})
        self.assertEqual(self.app.detail('S03')['demand'], before)
        self.assertIs(self.app.detail('S03')['demand'], self.app.detail('S03')['demand'])

    def test_invalid_quality_and_old_calibration_do_not_create_a_live_hotspot(self):
        now=time.time()
        records=[]
        for i in range(48*4+1):
            stamp=now-48*3600+i*900
            for boot, quality, calibration in [(1,'invalid',self.app.live.calibration['calibration_id']), (2,'ok','old')]:
                records.append((1,boot,i,stamp,stamp,json.dumps({'source':'rf'}),json.dumps({
                    'measurement_quality':quality,'calibration_id':calibration,'fill_percent':i%100})))
        with self.app.live.db:
            self.app.live.db.executemany('INSERT INTO telemetry VALUES (?,?,?,?,?,?,?)',records)
        b=next(b for b in self.app.bins() if b['source']=='live')
        self.assertFalse(self.app.demand_for(b)['available'])
        good=[]
        for i in range(48*4+1):
            stamp=now-48*3600+i*900
            good.append((1,3,i,stamp,stamp,json.dumps({'source':'rf'}),json.dumps({
                'measurement_quality':'ok','calibration_id':self.app.live.calibration['calibration_id'],
                'fill_percent':5+i/4})))
        with self.app.live.db:
            self.app.live.db.executemany('INSERT INTO telemetry VALUES (?,?,?,?,?,?,?)',good)
        self.app.demand_cache.clear()
        self.assertEqual(self.app.demand_for(b)['rate_pph'],1)


if __name__ == '__main__':
    unittest.main()
