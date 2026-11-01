"""Offline flight witnesses for deterministic Gioca contracts.

This is deliberately separate from static mission-envelope validation. It flies
the actual Python plant with its existing GNC, feeds the normal objective
evaluator, and records observed success or failure. A failed witness means this
reference controller did not solve that sample, not a proof of impossibility.
No flight state, fuel, objective progress, or elapsed simulation time is edited.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE_FILES = ("astra/data/mission_templates.json", "astra/procedural_missions.py",
                "astra/gameplay.py", "astra/engine.py", "astra/attitude.py",
                "astra/mission_science.py", "astra/mission_route.py",
                "astra/planetary_mission.py", "tools/mission_reference_flights.py")


def source_hashes():
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE_FILES}


class ManualRoutePilot:
    """Command-only reference pilot; never advances the engine's route flags.

    The pilot reads position/velocity, follows the assigned waypoints, then
    lands. This exercises the same manual setpoint path as keyboard/gamepad.
    It independently uses a tighter arrival gate than the mission evaluator.
    """
    def __init__(self, mission):
        outbound = mission["setup"]["route"]
        self.points = outbound + list(reversed(outbound[:-1]))
        self.index = 1
        self.climbed = self.landing = False

    @staticmethod
    def clamp(value, limit):
        return max(-limit, min(limit, value))

    def command(self, state):
        parameters = state["vehicle_parameters"]
        environment = state["environment"]
        position = state["position_ned_m"]
        air_velocity = state["air_relative_velocity_ned_m_s"]
        wind = environment["wind_velocity_ned_m_s"]
        velocity = [air_velocity[i]+wind[i] for i in range(3)]
        altitude = state["altitude_m"]
        self.climbed |= altitude >= 29.
        target = self.points[self.index] if self.climbed else [0., 0.]
        if (self.climbed and not self.landing and math.dist(position[:2], target) < .7
                and math.hypot(*velocity[:2]) < .8):
            if self.index == len(self.points)-1:
                self.landing = True
            else:
                self.index += 1
                target = self.points[self.index]
        target_altitude = 0. if self.landing else 30.
        mass = state["mass_kg"]
        drag = (.5*environment["density_kg_m3"]*parameters["body_drag_area_m2"]*
                math.sqrt(sum(v*v for v in air_velocity))/mass)
        horizontal_acceleration = [self.clamp(1.2*(target[i]-position[i])-
                                    math.sqrt(2.4)*velocity[i], 3.)+
                                    drag*air_velocity[i] for i in range(2)]
        pitch = self.clamp(-math.degrees(math.atan2(horizontal_acceleration[0], 9.80665)), 32.)
        roll = self.clamp(math.degrees(math.atan2(horizontal_acceleration[1], 9.80665)), 32.)
        projection = max(.8, math.cos(math.radians(roll))*math.cos(math.radians(pitch)))
        up_acceleration = self.clamp(.36*(target_altitude-altitude)+math.sqrt(4.2436)*velocity[2], 3.)
        thrust = mass*(9.80665+up_acceleration-drag*air_velocity[2])/projection
        return dict(mode="manual", throttle_pct=max(0., min(100., 100*thrust/parameters["max_thrust_N"])),
                    roll_deg=roll, pitch_deg=pitch, yaw_deg=0.)


def fly_mission(template_id: str, seed: int, *, max_seconds: float = 2400.,
                sample_seconds: float = .5, controller: str = "gnc") -> dict:
    """Return measured evidence for one deterministic generated mission."""
    from astra.engine import SimulationEngine
    from astra.gameplay import GameSession
    from astra.procedural_missions import (apply_mission_events,
                                           generate_mission, prepare_engine)

    if not math.isfinite(max_seconds) or max_seconds <= 0:
        raise ValueError("max_seconds must be finite and positive")
    if not math.isfinite(sample_seconds) or not 0 < sample_seconds <= 1.:
        raise ValueError("sample_seconds must be between 0 and 1")
    started = time.perf_counter()
    mission = generate_mission(template_id, seed)
    if controller not in {"gnc", "manual_route"}:
        raise ValueError("controller must be gnc or manual_route")
    if controller == "manual_route" and (mission["vehicle"] != "drone" or "route" not in mission["setup"]):
        raise ValueError("manual_route requires a drone route mission")
    pilot = ManualRoutePilot(mission) if controller == "manual_route" else None
    if pilot:
        sample_seconds = min(sample_seconds, .1)
    engine = SimulationEngine()
    prepare_engine(engine, mission)
    session = GameSession()
    session.start(mission["id"])
    engine.set_command({"mode": "manual" if pilot else "auto"})
    engine.launch()
    state = engine.state()
    result = session.update(state, 0.)
    peak_altitude = state["altitude_m"]
    minimum_fuel = state.get("propellant_pct")
    minimum_battery = state.get("battery_pct")
    samples = 0
    while state["time_s"] < max_seconds:
        if result.get("complete") or result.get("failed"):
            break
        if state["phase"] in {"LANDED", "CRASHED", "ABORTED"}:
            break
        apply_mission_events(engine, session)
        if pilot:
            engine.set_command(pilot.command(state))
        prior_time = state["time_s"]
        state = engine.step(min(sample_seconds, max_seconds-prior_time))
        result = session.update(state, state["time_s"]-prior_time)
        peak_altitude = max(peak_altitude, state["altitude_m"])
        if "propellant_pct" in state:
            minimum_fuel = min(minimum_fuel if minimum_fuel is not None else 100., state["propellant_pct"])
        if "battery_pct" in state:
            minimum_battery = min(minimum_battery if minimum_battery is not None else 100., state["battery_pct"])
        samples += 1
        if state["time_s"] <= prior_time:
            break
    touchdown = state.get("mission_metrics", {}).get("touchdown_speed_m_s")
    if touchdown is None:
        touchdown = state.get("touchdown_speed_m_s")
    report = dict(
        mission_id=mission["id"], template_id=template_id, seed=seed,
        mission_sha256=hashlib.sha256(json.dumps(mission, sort_keys=True,
            ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest(),
        vehicle=mission["vehicle"], scenario=mission["scenario"],
        controller="COMMAND_ONLY_MANUAL_ROUTE_PILOT" if pilot else "EXISTING_ENGINE_GNC",
        evidence="INTEGRATED_PYTHON_PLANT", final_control_mode=state["command"]["mode"],
        engine_route_completed=state.get("mission_route", {}).get("completed"),
        complete=bool(result.get("complete")), failed=bool(result.get("failed")),
        failure_reason=result.get("failure_reason", result.get("reason")),
        phase=state["phase"], simulated_seconds=state["time_s"],
        max_seconds=max_seconds, peak_altitude_m=peak_altitude,
        distance_m=result.get("distance_m"), hold_s=result.get("hold_s"),
        touchdown_speed_m_s=touchdown, minimum_propellant_pct=minimum_fuel,
        minimum_battery_pct=minimum_battery,
        relative_range_m=state.get("relative_range_m"),
        relative_speed_m_s=state.get("relative_speed_m_s"),
        progress=result.get("progress"), metrics=result.get("metrics"),
        medal=result.get("medal"), events=result.get("events"),
        samples=samples, sample_seconds=sample_seconds,
        wall_seconds=time.perf_counter()-started)
    # JSON serialization with allow_nan=False makes numerical failure explicit.
    json.dumps(report, allow_nan=False)
    return report


def main(argv=None) -> int:
    from astra.procedural_missions import templates

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="0", help="Comma-separated deterministic seed sample")
    parser.add_argument("--templates", default="", help="Comma-separated IDs; blank runs every family")
    parser.add_argument("--vehicle", choices=("space", "aircraft", "drone"))
    parser.add_argument("--max-seconds", type=float, default=2400.)
    parser.add_argument("--sample-seconds", type=float, default=.5)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--manual-route", action="store_true", help="Fly UAV routes through manual commands only")
    parser.add_argument("--output", type=Path, default=ROOT/"test-results/mission-flight-witnesses.json")
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 4:
        parser.error("workers must be 1–4")
    seeds = [int(value) for value in args.seeds.split(",")]
    selected = set(filter(None, args.templates.split(",")))
    rows = [t for t in templates() if (not selected or t["id"] in selected)
            and (not args.vehicle or t["vehicle"] == args.vehicle)]
    if not rows or (selected and selected != {t["id"] for t in rows}):
        parser.error("No templates matched, or an unknown template ID was supplied")
    results = []
    initial_hashes = source_hashes()
    tasks = [(row["id"], seed) for row in rows for seed in seeds]
    def record(result):
        results.append(result)
        print(json.dumps({key: result[key] for key in
              ("mission_id", "complete", "phase", "simulated_seconds", "wall_seconds")}), flush=True)
    if args.workers == 1:
        for template_id, seed in tasks:
            record(fly_mission(template_id, seed, max_seconds=args.max_seconds,
                               sample_seconds=args.sample_seconds,
                               controller="manual_route" if args.manual_route else "gnc"))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(fly_mission, template_id, seed,
                        max_seconds=args.max_seconds, sample_seconds=args.sample_seconds,
                        controller="manual_route" if args.manual_route else "gnc")
                       for template_id, seed in tasks]
            for future in as_completed(futures):
                record(future.result())
    results.sort(key=lambda row: (row["template_id"], row["seed"]))
    report = dict(
        evidence="REAL_ENGINE_FLIGHT_WITNESSES", samples=len(results),
        completed=sum(row["complete"] for row in results),
        passed=all(row["complete"] for row in results) and initial_hashes == source_hashes(),
        source_files_sha256=initial_hashes, sources_unchanged=initial_hashes == source_hashes(),
        templates=len(rows), seeds=seeds,
        limits=("Sampled constructive flight evidence only; finite samples do not prove every "
                "possible seed solvable. Existing educational dynamics, flat local landing "
                "surfaces and synthetic navigation retain their documented limitations."),
        results=results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False,
                                    allow_nan=False)+"\n", encoding="utf-8")
    print(f"{report['completed']}/{report['samples']} flights completed; report: {args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
