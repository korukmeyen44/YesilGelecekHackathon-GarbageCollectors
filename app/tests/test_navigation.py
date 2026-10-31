"""OSRM navigation is sourced from steps; offline routes never invent instructions."""
import sqlite3
import unittest
from unittest.mock import Mock

from app.routing import Roads


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.roads = Roads(self.db)
        self.points = [{"lng": 39.77, "lat": 40.99}, {"lng": 39.771, "lat": 40.991}]
        self.result = {"routes": [{"geometry": {"coordinates": [[39.77, 40.99], [39.771, 40.991]]},
                                  "legs": [{"steps": [
                                      {"distance": 80, "name": "Kampüs Yolu", "maneuver": {"type": "depart", "location": [39.77, 40.99]}},
                                      {"distance": 40, "name": "", "maneuver": {"type": "turn", "modifier": "right", "location": [39.771, 40.991]}}]}]}]}

    def tearDown(self):
        self.db.close()

    def test_steps_and_versioned_cache(self):
        self.roads.fetch = Mock(return_value=self.result)
        line, road = self.roads.geometry(self.points, [0, 1, 0], "road")
        self.assertTrue(road)
        self.assertEqual(line[0], [40.99, 39.77])
        self.assertIn("steps=true", self.roads.fetch.call_args.args[0])
        self.assertEqual(self.roads.last_maneuvers[1]["distance_from_start"], 80)
        self.roads.geometry(self.points, [0, 1, 0], "road")
        self.roads.fetch.assert_called_once()
        self.assertEqual(len(self.roads.last_maneuvers), 2)

    def test_failure_never_reuses_old_instructions(self):
        self.roads.last_maneuvers = [{"type": "turn"}]
        line, road = self.roads.geometry(self.points, [0, 1, 0], "approximate")
        self.assertFalse(road)
        self.assertEqual(self.roads.last_maneuvers, [])

    def test_invalid_geometry_falls_back(self):
        self.result["routes"][0]["geometry"]["coordinates"][0][0] = float("nan")
        self.roads.fetch = Mock(return_value=self.result)
        _, road = self.roads.geometry(self.points, [0, 1, 0], "road")
        self.assertFalse(road)
        self.assertEqual(self.roads.last_maneuvers, [])
