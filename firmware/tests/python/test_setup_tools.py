import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"))
from collector import load_calibration
from calibrate_bin import calibrated_config
from check_link import usable_node


class SetupToolsTests(unittest.TestCase):
    def test_measured_calibration_preserves_other_nodes_and_source_config(self):
        original=load_calibration(ROOT/"config/calibration.example.json")
        snapshot=copy.deepcopy(original)
        result=calibrated_config(original,1,600,80)
        self.assertTrue(result["nodes"]["1"]["calibrated"])
        self.assertEqual(result["nodes"]["1"]["measurement"]["empty_mm"],600)
        self.assertEqual(result["nodes"]["2"],original["nodes"]["2"])
        self.assertEqual(original,snapshot)
        self.assertNotEqual(result["calibration_id"],original["calibration_id"])

    def test_calibration_rejects_reversed_or_invalid_references(self):
        config=load_calibration(ROOT/"config/calibration.example.json")
        for empty,full in ((80,600),(400,400),(400,0),(True,40),(4001,40)):
            with self.subTest(empty=empty,full=full),self.assertRaises(ValueError):calibrated_config(config,1,empty,full)

    def test_link_check_cannot_pass_for_missing_or_invalid_distance(self):
        node={"source":"rf","freshness":"fresh","measurement":{"distance_mm":220,"status":"ok","attempted_pairs":5},"fill_percent":None,"measurement_quality":"uncalibrated"}
        self.assertTrue(usable_node(node))
        self.assertFalse(usable_node(node,True))
        for mutate in (lambda n:n.update(freshness="stale"),lambda n:n["measurement"].update(distance_mm=None),lambda n:n.update(source="simulator"),lambda n:n["measurement"].update(status="too_few"),lambda n:n["measurement"].update(attempted_pairs=10)):
            bad=copy.deepcopy(node);mutate(bad);self.assertFalse(usable_node(bad))
        node.update(fill_percent=50,measurement_quality="ok")
        self.assertTrue(usable_node(node,True))
