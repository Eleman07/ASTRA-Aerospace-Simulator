"""Small regression witnesses; use mission_reference_flights.py for every family."""
import unittest

from tools.mission_reference_flights import fly_mission


class MissionFlightWitnessTests(unittest.TestCase):
    def test_lunar_survey_completes_in_the_rigid_body_plant_with_fuel_reserve(self):
        report = fly_mission("space_lunar_survey", 49)
        self.assertTrue(report["complete"], report)
        self.assertFalse(report["failed"])
        self.assertEqual(report["evidence"], "INTEGRATED_PYTHON_PLANT")
        self.assertEqual(report["phase"], "LANDED")
        self.assertGreater(report["simulated_seconds"], 20.)
        self.assertGreater(report["samples"], 40)
        self.assertGreaterEqual(report["hold_s"], 4.)
        self.assertLess(report["touchdown_speed_m_s"], 1.2)
        self.assertGreater(report["minimum_propellant_pct"], 35.)

    def test_short_budget_never_fabricates_a_completed_flight(self):
        report = fly_mission("space_lunar_survey", 49, max_seconds=2.)
        self.assertFalse(report["complete"])
        self.assertFalse(report["failed"])
        self.assertAlmostEqual(report["simulated_seconds"], 2., places=9)
        self.assertIsNone(report["touchdown_speed_m_s"])
        self.assertNotEqual(report["phase"], "LANDED")

    def test_manual_route_is_scored_from_flight_without_gnc_completion_flag(self):
        report = fly_mission("drone_delivery", 0, controller="manual_route")
        self.assertTrue(report["complete"], report)
        self.assertEqual(report["final_control_mode"], "manual")
        self.assertFalse(report["engine_route_completed"])
        self.assertTrue(report["progress"]["route"])
        self.assertTrue(report["progress"]["safe_landing"])
        self.assertGreater(report["distance_m"], 50.)
        self.assertLess(report["touchdown_speed_m_s"], 1.)
        self.assertGreater(report["minimum_battery_pct"], 35.)


if __name__ == "__main__":
    unittest.main()
