"""Regression tests for manual orbital attitude and the SAS command surface."""
from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from astra.attitude import SpacecraftAttitude, _q_rotate
from astra.engine import SimulationEngine, EARTH_RADIUS, MU_EARTH
from astra_sdk import AstraClient
from desktop_runtime import DesktopRuntime


def quaternion_distance_deg(a, b):
    dot = abs(sum(x*y for x, y in zip(a, b)))
    return math.degrees(2*math.acos(max(-1.0, min(1.0, dot))))


class OrbitalSASTests(unittest.TestCase):
    def setUp(self):
        self.engine = SimulationEngine()
        self.engine.reset("space", "orbital", advanced_models=True)

    def test_manual_mode_releases_lvlh_servo_and_keeps_inertial_attitude(self):
        initial = self.engine.state()["attitude_quaternion_body_to_eci"]
        self.engine.set_command({"mode": "manual"})
        self.assertEqual(self.engine.command["attitude_sas_mode"], "manual")
        state = self.engine.step(8.0)
        final = state["attitude_quaternion_body_to_eci"]
        self.assertLess(quaternion_distance_deg(initial, final), .02)
        self.assertEqual(state["attitude_control"]["mode"], "manual")

    def test_manual_torque_rotates_then_zero_torque_does_not_retarget_vertical(self):
        initial = self.engine.state()["attitude_quaternion_body_to_eci"]
        self.engine.set_command({"mode": "manual",
                                 "attitude_torque_body_fraction": [0, 0, 1]})
        rotated = self.engine.step(12.0)["attitude_quaternion_body_to_eci"]
        self.assertGreater(quaternion_distance_deg(initial, rotated), 2.0)
        rates = self.engine.state()["body_rates_rad_s"]
        self.engine.set_command({"attitude_torque_body_fraction": [0, 0, 0]})
        state = self.engine.step(2.0)
        self.assertGreater(quaternion_distance_deg(rotated,
                            state["attitude_quaternion_body_to_eci"]), .01)
        self.assertGreater(math.sqrt(sum(v*v for v in state["body_rates_rad_s"])), 0.0)
        self.assertGreater(math.sqrt(sum(v*v for v in rates)), 0.0)

    def test_stability_and_orbit_direction_sas_targets(self):
        current = self.engine.state()["attitude_quaternion_body_to_eci"]
        self.engine.set_command({"mode": "manual", "attitude_sas_mode": "stability_assist"})
        stable = self.engine.step(8.0)
        self.assertLess(quaternion_distance_deg(current,
                         stable["attitude_quaternion_body_to_eci"]), .1)
        self.engine.set_command({"attitude_sas_mode": "prograde"})
        prograde = self.engine.step(.2)
        q = prograde["attitude_quaternion_body_to_eci"]
        body_x = _q_rotate(q, [1, 0, 0])
        velocity = prograde["velocity_eci_m_s"]
        vnorm = math.sqrt(sum(v*v for v in velocity))
        self.assertGreater(sum(body_x[i]*velocity[i]/vnorm for i in range(3)), .99)
        self.engine.set_command({"attitude_sas_mode": "target"})
        self.engine.step(.2)
        self.engine.set_command({"attitude_sas_mode": "maneuver_node",
                                 "maneuver_direction_eci": [1, 1, 0]})
        self.engine.step(.2)

    def test_invalid_manual_torque_and_unset_maneuver_are_rejected(self):
        self.engine.set_command({"mode": "manual"})
        with self.assertRaises(ValueError):
            self.engine.set_command({"attitude_torque_body_fraction": [0, 2, 0]})
        with self.assertRaises(ValueError):
            self.engine.set_command({"attitude_sas_mode": "maneuver_node"})

    def test_desktop_gioca_orbit_uses_same_manual_attitude_physics(self):
        runtime = DesktopRuntime()
        snapshot = runtime.dispatch("/desktop/free", {"vehicle": "space",
            "scenario": "orbital", "advanced_models": True}, "POST")
        self.assertEqual(snapshot["desktop"]["play_mode"], "free")
        self.assertEqual(snapshot["state"]["command"]["attitude_sas_mode"], "manual")
        initial = snapshot["state"]["attitude_quaternion_body_to_eci"]
        runtime.dispatch("/command", {"attitude_torque_body_fraction": [1, 0, 0]}, "POST")
        rotated = runtime.engine.step(12.0)["attitude_quaternion_body_to_eci"]
        self.assertGreater(quaternion_distance_deg(initial, rotated), 2.0)

    def test_enable_disable_and_gnc_authority_are_explicit(self):
        self.engine.set_command({"sas_enabled": True})
        sas = self.engine.state()["sas"]
        self.assertTrue(sas["enabled"])
        self.assertEqual(sas["mode"], "stability_assist")
        self.assertEqual(self.engine.command["mode"], "manual")
        self.engine.set_command({"attitude_sas_mode": "retrograde"})
        self.engine.set_command({"sas_enabled": False})
        sas = self.engine.step(.2)["sas"]
        self.assertFalse(sas["enabled"])
        self.assertEqual(sas["mode"], "retrograde")
        self.assertEqual(sas["effective_mode"], "manual")
        self.engine.set_command({"sas_enabled": True})
        self.assertEqual(self.engine.command["attitude_sas_mode"], "stability_assist")
        self.engine.set_command({"mode": "auto"})
        sas = self.engine.state()["sas"]
        self.assertFalse(sas["enabled"])
        self.assertEqual(sas["authority"], "gnc")
        self.assertEqual(sas["effective_mode"], "lvlh")
        self.engine.set_command({"mode": "python", "attitude_target_deg": [5, 0, 0]})
        self.assertEqual(self.engine.state()["sas"]["effective_mode"], "lvlh")

    def test_contextual_modes_markers_and_node_removal(self):
        sas = self.engine.state()["sas"]
        self.assertIn("anti_target", sas["available_modes"])
        self.assertNotIn("maneuver_node", sas["available_modes"])
        for marker in sas["markers"].values():
            self.assertAlmostEqual(sum(v*v for v in marker["direction_body"]), 1., places=12)
        a, b = sas["markers"]["target"], sas["markers"]["anti_target"]
        self.assertEqual(a["direction_eci"], [-v for v in b["direction_eci"]])
        self.engine.set_command({"mode": "manual", "attitude_sas_mode": "anti_target"})
        self.engine.step(.1)
        self.engine.set_command({"attitude_sas_mode": "maneuver_node",
                                 "maneuver_direction_eci": [1, 2, 3]})
        self.assertIn("maneuver_node", self.engine.state()["sas"]["available_modes"])
        self.engine.set_command({"maneuver_direction_eci": None})
        self.assertEqual(self.engine.step(.1)["sas"]["mode"], "stability_assist")
        self.engine.set_command({"attitude_sas_mode": "target"})
        self.engine.target_orbit = self.engine.orbit[:]
        self.assertNotIn("target", self.engine.state()["sas"]["available_modes"])
        with self.assertRaises(ValueError):
            self.engine.set_command({"attitude_sas_mode": "anti_target"})
        self.assertEqual(self.engine.step(.1)["sas"]["mode"], "stability_assist")

    def test_invalid_sas_is_atomic_and_other_vehicles_hide_it(self):
        original = dict(self.engine.command)
        for bad in ({"sas_enabled": 1}, {"sas_enabled": True, "mode": "auto"},
                    {"attitude_sas_mode": "undefined"},
                    {"attitude_sas_mode": "maneuver_node", "maneuver_direction_eci": [0, 0, 0]}):
            with self.assertRaises(ValueError):
                self.engine.set_command({"throttle_pct": 75, **bad})
            self.assertEqual(self.engine.command, original)
        for vehicle, scenario in (("aircraft", "mission"), ("drone", "mission"), ("space", "planetary")):
            self.engine.reset(vehicle, scenario, advanced_models=True)
            self.assertTrue(self.engine.state()["sas"]["supported"])
            self.assertTrue(self.engine.set_command({"sas_enabled": True})["sas"]["enabled"])

    def test_launch_directional_sas_tracks_all_valid_references(self):
        for mode in ('prograde','retrograde','normal','anti_normal','radial_in','radial_out','target','anti_target','maneuver_node'):
            self.engine.reset('space',advanced_models=True)
            self.engine.launch();self.engine.step(20)
            payload={'mode':'manual','attitude_sas_mode':mode}
            if mode=='maneuver_node':payload['maneuver_direction_eci']=[1,1,0]
            before=self.engine.state()['attitude_quaternion_body_to_eci']
            selected=self.engine.set_command(payload)
            self.assertIn(mode,selected['sas']['available_modes'])
            self.assertEqual(before,selected['attitude_quaternion_body_to_eci'])
            result=self.engine.step(.1)
            self.assertEqual(result['sas']['mode'],mode)
            self.assertTrue(all(math.isfinite(v) for v in result['attitude_quaternion_body_to_eci']))
            self.assertGreaterEqual(result['acs_propellant_kg'],0)
            if mode=='retrograde':self.assertLess(result['command']['pitch_deg'],0)
            if mode=='normal':self.assertAlmostEqual(result['command']['roll_deg'],90,delta=.1)
            self.engine.set_command({'roll_deg':7,'pitch_deg':20,'sas_manual_input':True})
            self.engine.step(.1)
            self.assertTrue(self.engine.state()['sas']['manual_override'])
            self.engine.set_command({'roll_deg':0,'pitch_deg':0,'sas_manual_input':False})
            self.assertFalse(self.engine.state()['sas']['manual_override'])

    def test_launch_desktop_pitch_hold_survives_neutral_input(self):
        runtime=DesktopRuntime()
        runtime.dispatch('/desktop/free',{'vehicle':'space'},'POST')
        runtime._command({'sas_enabled':True})
        runtime._command({'pitch_deg':75,'sas_manual_input':True})
        state=runtime._command({'pitch_deg':90,'sas_manual_input':False})
        self.assertEqual(state['command']['pitch_deg'],75)

    def test_local_sas_latches_pilot_reference_at_release(self):
        for vehicle, scenario in (("space", "mission"), ("space", "planetary"), ("aircraft", "mission"), ("drone", "mission")):
            self.engine.reset(vehicle, scenario, advanced_models=True)
            self.engine.set_command({"mode":"manual", "sas_enabled":True})
            self.engine.set_command({"roll_deg":7, "pitch_deg":4, "sas_manual_input":True})
            result=self.engine.set_command({"roll_deg":0, "pitch_deg":0, "sas_manual_input":False})
            self.assertEqual(result["command"]["roll_deg"],7)
            self.assertEqual(result["command"]["pitch_deg"],4)
            self.assertFalse(result["sas"]["manual_override"])
            self.engine.launch()
            state=self.engine.step(.1)
            self.assertTrue(state["sas"]["enabled"])
            self.assertTrue(all(math.isfinite(v) for v in state.get("attitude_deg",[])))
            self.engine.set_command({"sas_enabled":False})
            result=self.engine.set_command({"roll_deg":0,"pitch_deg":0})
            self.assertEqual(result["command"]["roll_deg"],0)

    def test_sdk_helpers_and_status_use_same_controller(self):
        runtime = DesktopRuntime()
        runtime.dispatch("/reset", {"vehicle": "space", "scenario": "orbital"}, "POST")
        client = AstraClient("http://127.0.0.1:1")
        def local_request(path, payload=None):
            return runtime.dispatch(path.removeprefix("/api/v1"), payload, "GET" if payload is None else "POST")
        with patch.object(client, "_request", side_effect=local_request):
            self.assertTrue(client.sas_enable()["sas"]["enabled"])
            self.assertEqual(client.sas_mode("retrograde")["sas"]["mode"], "retrograde")
            self.assertTrue(client.status()["sas"]["enabled"])
            self.assertFalse(client.sas_enable(False)["sas"]["enabled"])
            self.assertEqual(client.orbital_attitude("prograde")["sas"]["mode"], "prograde")
            client.reset("aircraft")
            self.assertTrue(client.sas_mode("stability_assist")["sas"]["enabled"])


class SASDynamicsTests(unittest.TestCase):
    """Exercise the actual actuator/rigid-body plant along an analytic LEO.

    A six-hundred-second circular reference avoids making a second numerical
    orbit solver the oracle for guidance convergence. No pose is assigned after
    the initial condition; all subsequent attitude changes are integrated.
    """
    radius = EARTH_RADIUS+420000.
    mean_motion = math.sqrt(MU_EARTH/radius**3)

    def initial(self):
        a = SpacecraftAttitude()
        a.initialize([self.radius, 0., 0.], [0., self.mean_motion*self.radius, 0.])
        a.body_rates_rad_s = [0., 0., 0.]
        return a

    def advance(self, a, start, duration, mode, torque=None, mu=MU_EARTH):
        errors = []
        for index in range(round(duration/.1)):
            angle = self.mean_motion*(start+(index+1)*.1)
            p = [self.radius*math.cos(angle), self.radius*math.sin(angle), 0.]
            v = [-self.radius*self.mean_motion*math.sin(angle), self.radius*self.mean_motion*math.cos(angle), 0.]
            a.step(.1, p, v, mu, control_mode=mode, manual_torque_body_fraction=torque)
            errors.append(a.attitude_error_deg)
            for used, limit in zip(a.control_torque_body_Nm, a.wheel_torque_limit_N_m):
                self.assertLessEqual(abs(used), limit+1e-12)
            for used, limit in zip(a.wheel_momentum_body_N_m_s, a.wheel_momentum_limit_N_m_s):
                self.assertLessEqual(abs(used), limit+1e-12)
        return errors

    def test_180_degree_prograde_and_retrograde_converge_without_tail_jitter(self):
        for mode in ("prograde", "retrograde"):
            with self.subTest(mode=mode):
                a = self.initial()
                if mode == "prograde":
                    a.quaternion_body_to_eci = a._direction_target([0, -1, 0], [-1, 0, 0])
                initial = a.quaternion_body_to_eci[:]
                first = self.advance(a, 0., .1, mode)
                self.assertLess(quaternion_distance_deg(initial, a.quaternion_body_to_eci), .001)
                self.assertGreater(first[0], 179.)
                errors = self.advance(a, .1, 599.9, mode)
                self.assertLess(max(errors[-300:]), .01)
                self.assertLess(max(errors[-300:])-min(errors[-300:]), .0001)

    def test_stability_holds_without_disturbances_and_recaptures_on_release(self):
        a = self.initial()
        initial = a.quaternion_body_to_eci[:]
        self.advance(a, 0., 120., "stability_assist", mu=0.)
        self.assertLess(quaternion_distance_deg(initial, a.quaternion_body_to_eci), .00001)
        self.advance(a, 120., 8., "stability_assist", [0, 0, .4])
        self.assertTrue(a.manual_override)
        released = a.quaternion_body_to_eci[:]
        self.assertGreater(quaternion_distance_deg(initial, released), 1.)
        errors = self.advance(a, 128., 300., "stability_assist")
        self.assertFalse(a.manual_override)
        self.assertLess(quaternion_distance_deg(released, a.quaternion_body_to_eci), .001)
        self.assertLess(max(errors[-300:]), .001)
        self.assertLess(max(abs(v) for v in a.body_rates_rad_s), 1e-6)

    def test_every_directional_preset_yields_to_stick_then_resumes(self):
        for mode in ("prograde", "retrograde", "normal", "anti_normal", "radial_in", "radial_out", "target", "anti_target", "maneuver_node"):
            with self.subTest(mode=mode):
                a = self.initial()
                p, v = [self.radius, 0., 0.], [0., self.mean_motion*self.radius, 0.]
                kwargs = dict(control_mode=mode, target_position_eci_m=[self.radius, 1000., 0.],
                              maneuver_direction_eci=[1., 1., 0.])
                a.step(.1, p, v, MU_EARTH, manual_torque_body_fraction=[.3, -.4, .5], **kwargs)
                self.assertTrue(a.manual_override)
                for torque, fraction, limit in zip(a.control_torque_body_Nm, [.3, -.4, .5], a.wheel_torque_limit_N_m):
                    self.assertAlmostEqual(torque, fraction*limit, places=12)
                a.step(.1, p, v, MU_EARTH, **kwargs)
                self.assertFalse(a.manual_override)
                self.assertEqual(a.control_mode, mode)

    def test_power_loss_and_saturation_do_not_produce_free_torque(self):
        a = self.initial()
        a.control_power_factor = 0.
        self.advance(a, 0., 1., "retrograde", [1, 1, 1], mu=0.)
        self.assertEqual(a.control_torque_body_Nm, [0., 0., 0.])
        self.assertEqual(a.body_rates_rad_s, [0., 0., 0.])
        a.control_power_factor = 1.
        a.wheel_momentum_body_N_m_s = [-v for v in a.wheel_momentum_limit_N_m_s]
        self.advance(a, 1., 1., "manual", [1, 1, 1], mu=0.)
        self.assertEqual(a.control_torque_body_Nm, [0., 0., 0.])
        self.assertEqual(a.body_rates_rad_s, [0., 0., 0.])


if __name__ == "__main__":
    unittest.main()
