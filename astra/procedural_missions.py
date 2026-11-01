"""Versioned offline contracts. Data defines templates; the Python plant measures them.

The catalogue is deliberately bounded to supported local flight scenarios. A named
sector is a synthetic local training site, not downloaded geography or a new body.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import random

VERSION = 1
VARIANTS_PER_TEMPLATE = 64
VEHICLES = ("space", "aircraft", "drone")
OBJECTIVE_TYPES = {"altitude", "distance", "hold_altitude", "safe_landing",
                   "rendezvous", "relative_waypoint", "route", "waypoint", "fault_detected"}


@lru_cache(maxsize=1)
def _data():
    data = json.loads((Path(__file__).parent / "data" / "mission_templates.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != VERSION:
        raise ValueError("Unsupported mission template schema")
    ids = [row["id"] for row in data["templates"]]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate mission template ID")
    return data


def templates():
    return deepcopy(_data()["templates"])


def _language(value):
    if value not in ("it", "en"):
        raise ValueError("Mission language must be it or en")
    return value


def _resolve(value, parameters):
    if isinstance(value, str) and value.startswith("$"):
        return deepcopy(parameters[value[1:]])
    if isinstance(value, dict):
        return {key: _resolve(item, parameters) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, parameters) for item in value]
    return value


def _label(item, language):
    en = language == "en"
    kind = item["type"]
    if kind == "altitude":
        return ("Reach %.0f m" if en else "Raggiungi %.0f m") % item["value"]
    if kind == "distance":
        return ("Fly %.0f m" if en else "Percorri %.0f m") % item["value"]
    if kind == "hold_altitude":
        return (("Hold %.0f–%.0f m for %.0f consecutive seconds" if en else
                 "Mantieni %.0f–%.0f m per %.0f secondi consecutivi") %
                (item["minimum_m"], item["maximum_m"], item["seconds"]))
    if kind == "safe_landing":
        return ("Land safely at ground speed ≤%.1f m/s" if en else
                "Atterra in sicurezza a velocità al suolo ≤%.1f m/s") % item["speed_m_s"]
    if kind == "rendezvous":
        return ("Approach within %.0f m at ≤%.2f m/s" if en else
                "Avvicinati entro %.0f m a ≤%.2f m/s") % (item["range_m"], item["speed_m_s"])
    if kind == "relative_waypoint":
        return (("Reach RTN %s m, error ≤%.0f m, relative speed ≤%.2f m/s" if en else
                 "Raggiungi RTN %s m, errore ≤%.0f m, velocità relativa ≤%.2f m/s") %
                (item["position_m"], item["radius_m"], item["speed_m_s"]))
    if kind == "route":
        return "Visit every inspection waypoint and return to the pad" if en else "Visita tutti i waypoint di ispezione e rientra al pad"
    if kind == "waypoint":
        return ("Reach local waypoint %s m (radius %.0f m)" if en else
                "Raggiungi il waypoint locale %s m (raggio %.0f m)") % (item["position_m"], item["radius_m"])
    return "Detect the injected propulsion fault" if en else "Rileva il guasto di propulsione iniettato"


def rewards(vehicle, difficulty, duration_s, modifiers):
    """A one-time base payout; replay improvements only pay a medal difference."""
    base = {"space": 2400, "aircraft": 1100, "drone": 650}[vehicle]
    multiplier = (1 + .28 * (difficulty - 1)) * (.75 + .5 * math.sqrt(duration_s / 300)) * (1 + .12 * modifiers)
    return {"credits": int(round(base * multiplier / 10) * 10),
            "reputation": 2 + difficulty * 2 + modifiers,
            "science": (3 if vehicle == "drone" else 2) + difficulty + modifiers}


def generate_mission(template_id, seed, language="it"):
    language = _language(language)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2147483647:
        raise ValueError("Mission seed must be an integer between 0 and 2147483647")
    template = next((row for row in _data()["templates"] if row["id"] == template_id), None)
    if template is None:
        raise ValueError("Unknown mission template")
    digest = hashlib.sha256(f"astra-contract-v{VERSION}:{template_id}:{seed}".encode()).digest()
    rng = random.Random(int.from_bytes(digest[:16], "big"))
    difficulty = seed % 5 + 1
    parameters = {}
    for key, spec in sorted(template.get("parameters", {}).items()):
        if "choices" in spec:
            parameters[key] = deepcopy(rng.choice(spec["choices"]))
        else:
            count = int(round((spec["max"] - spec["min"]) / spec.get("step", 1)))
            parameters[key] = round(spec["min"] + rng.randrange(count + 1) * spec.get("step", 1), 6)
    setup = _resolve(template.get("setup", {}), parameters)
    # Layout and heading change the actual physical path, not merely its caption.
    if "layouts" in template:
        points = deepcopy(rng.choice(template["layouts"]))
        angle = math.radians(parameters.get("heading_deg", 0))
        scale = parameters.get("route_scale", 1)
        setup["route"] = [[round(scale * (n * math.cos(angle) - e * math.sin(angle)), 3),
                           round(scale * (n * math.sin(angle) + e * math.cos(angle)), 3)] for n, e in points]
    objectives = _resolve(template["objectives"], parameters)
    # Difficulty changes physical tasks, not only labels and payouts. Bounds
    # leave margin against the real reference flights in the validator report.
    level = difficulty - 1
    if "wind_ned_m_s" in setup:
        setup["wind_ned_m_s"] = [round(value * (1 + .05 * level), 4) for value in setup["wind_ned_m_s"]]
    if "route" in setup:
        setup["route"] = [[round(value * (1 + .03 * level), 3) for value in point] for point in setup["route"]]
    if "separation_m" in setup:
        setup["separation_m"] += 20 * level
    for item in objectives:
        kind = item["type"]
        if kind == "hold_altitude":
            item["seconds"] = round(item["seconds"] * (1 + .1 * level), 2)
        elif kind == "rendezvous":
            item["range_m"] -= 2 * level
            item["speed_m_s"] -= .025 * level
        elif kind == "relative_waypoint":
            item["radius_m"] -= level
        elif kind == "safe_landing":
            item["speed_m_s"] = round(item["speed_m_s"] - (.1 if template["vehicle"] == "aircraft" else .025) * level, 3)
        elif kind == "altitude" and template["vehicle"] == "space":
            item["value"] += 1000 * level
    for index, item in enumerate(objectives):
        item["id"] = item.get("id", f"o{index + 1}")
        item["label"] = _label(item, language)
    events = _resolve(template.get("events", []), parameters)
    duration = int(template["duration_s"])
    modifiers = int(bool(events)) + int(any(abs(x) > 0 for x in setup.get("wind_ned_m_s", [0, 0, 0])))
    sector = _data()["sectors"][seed % len(_data()["sectors"])][language]
    local_note = ("Synthetic local training sector; not geographic scenery." if language == "en" else
                  "Settore locale di addestramento sintetico; non una cartografia geografica.")
    mission = {
        "id": f"proc{VERSION}:{template_id}:{seed}", "version": VERSION,
        "template_id": template_id, "seed": seed, "source": "contracts",
        "vehicle": template["vehicle"], "scenario": template["scenario"],
        "family": template["family"], "category": template.get("category", "CONTRATTI"),
        "campaign": "CONTRACTS / " + sector if language == "en" else "CONTRATTI / " + sector,
        "title": f"{template['title'][language]} · {sector} #{seed + 1:02d}",
        "briefing": template["briefing"][language] + " " + local_note,
        "language": language, "difficulty": difficulty, "duration_s": duration,
        "location": {"name": sector, "frame": "RTN" if template["scenario"] == "orbital" else "ENU" if template["scenario"] == "planetary" else "NED", "synthetic": True},
        "objectives": objectives, "setup": setup, "events": events,
        "constraints": _resolve(template.get("constraints", {}), parameters),
        "bonus": _resolve(template.get("bonus", {}), parameters),
        "reward": rewards(template["vehicle"], difficulty, duration, modifiers),
        "parameters": parameters,
        "requirements": {"completed_in_discipline": (difficulty - 1) * 2},
    }
    if "deadline_s" in mission["constraints"]:
        mission["constraints"]["deadline_s"] *= 1 - .05 * level
    labels = {"max_elapsed_s": ("Completa entro %.0f s", "Finish within %.0f s"),
              "min_resource_pct": ("Conserva almeno %.0f%% di riserva", "Keep at least %.0f%% reserve"),
              "touchdown_speed_m_s": ("Contatto a ≤%.2f m/s", "Touchdown at ≤%.2f m/s"),
              "max_load_factor_g": ("Carico massimo ≤%.1f g", "Peak load ≤%.1f g")}
    mission["optional_objectives"] = [{"id": key, "label": labels[key][language == "en"] % value,
                                        "metric": key, "target": value} for key, value in mission["bonus"].items()]
    mission["feasibility"] = feasibility(mission)
    return mission


def parse_mission_id(mission_id, language="it"):
    try:
        prefix, template_id, seed_text = mission_id.split(":")
        if prefix != f"proc{VERSION}" or not seed_text.isdecimal():
            raise ValueError
        return generate_mission(template_id, int(seed_text), language)
    except (AttributeError, ValueError) as error:
        raise ValueError("Invalid generated mission ID") from error


def contract_catalog(vehicle=None, source="contracts", language="it", calendar_date=None):
    if vehicle is not None and vehicle not in VEHICLES:
        raise ValueError("Choose space, aircraft or drone")
    if source not in {"contracts", "daily", "weekly"}:
        raise ValueError("Choose contracts, daily or weekly")
    day = date.fromisoformat(calendar_date) if isinstance(calendar_date, str) else calendar_date or date.today()
    result = {kind: [] for kind in VEHICLES if vehicle is None or kind == vehicle}
    for template in _data()["templates"]:
        if template["vehicle"] not in result:
            continue
        if source == "contracts":
            seeds = range(VARIANTS_PER_TEMPLATE)
        else:
            period = day.isoformat() if source == "daily" else "%04d-W%02d" % day.isocalendar()[:2]
            raw = hashlib.sha256(f"{source}:{period}:{template['id']}".encode()).digest()
            # Date contracts always start at difficulty 1 so every pilot can try them.
            seeds = [int.from_bytes(raw[:4], "big") % 400000000 * 5]
        for seed in seeds:
            mission = generate_mission(template["id"], seed, language)
            mission["source"] = source
            if source != "contracts":
                mission["period"] = period
            result[template["vehicle"]].append(mission)
    return result


def feasibility(mission):
    """Conservative envelope screening; never presented as a completed flight."""
    errors = []
    kind, scenario, setup = mission["vehicle"], mission["scenario"], mission["setup"]
    if any(item["type"] not in OBJECTIVE_TYPES for item in mission["objectives"]):
        errors.append("Objective has no engine metric evaluator")
    wind = math.sqrt(sum(x * x for x in setup.get("wind_ned_m_s", [0, 0, 0])))
    reserve = 0.
    if kind == "drone":
        route = setup.get("route", [[0, 0], [0, 0]])
        length = 2 * sum(math.dist(a, b) for a, b in zip(route, route[1:]))
        duration = 90 + length / 2
        # 650 W conservative continuous draw against the real 177.6 Wh / 74% pack.
        required = duration * 650 / 3600
        available = 177.6 * .74
        reserve = available - required
        if wind > 3.6 or max(math.hypot(*p) for p in route) > 100 or reserve < 25:
            errors.append("UAV route/wind/energy envelope exceeded")
        resource = {"required_Wh": round(required, 3), "available_Wh": available,
                    "reserve_Wh": round(reserve, 3), "estimated_flight_s": round(duration, 3)}
    elif kind == "aircraft":
        # Corvo's full-power bound is intentionally well above the measured circuit use.
        duration = mission["duration_s"]
        required = duration * .025
        available = 170.
        if wind > 4 or required > available * .7:
            errors.append("Aircraft wind/fuel envelope exceeded")
        if any(o["type"] == "safe_landing" and o["speed_m_s"] < 44 for o in mission["objectives"]):
            errors.append("Touchdown ground speed below the demonstrated trainer envelope")
        resource = {"required_fuel_kg": round(required, 3), "available_fuel_kg": available,
                    "reserve_fuel_kg": round(available - required, 3)}
    elif scenario == "orbital":
        separation = setup.get("separation_m", 1000)
        required = 2 * math.sqrt(.04 * separation) + 20
        available = 220 * 9.80665 * math.log(465.6 / 400)
        if required > available * .5 or not 300000 <= setup.get("orbit_altitude_m", 420000) <= 650000:
            errors.append("Orbital delta-v/altitude envelope exceeded")
        resource = {"required_delta_v_m_s": round(required, 3), "available_delta_v_m_s": round(available, 3)}
    elif scenario == "planetary":
        height = setup.get("initial_height_m", 900)
        required = 30 + math.sqrt(2 * 1.62 * height) + 180
        available = 310 * 9.80665 * math.log(1000 / 650)
        if required > available * .5 or not 650 <= height <= 1100:
            errors.append("Lunar descent delta-v/height envelope exceeded")
        resource = {"required_delta_v_m_s": round(required, 3), "available_delta_v_m_s": round(available, 3)}
    else:
        maximum = max((o.get("value", 0) for o in mission["objectives"] if o["type"] == "altitude"), default=0)
        if maximum > 220000:
            errors.append("Launch target above the demonstrated 274 km reference apogee margin")
        resource = {"reference_apogee_m": 274086, "required_altitude_m": maximum,
                    "available_ideal_delta_v_m_s": round(300 * 9.80665 * math.log(24000 / 4000), 3)}
    for event in mission.get("events", []):
        if event.get("fault", {}).get("type") != "engine_thrust_loss" or not 0 < event["fault"].get("severity_fraction", 0) <= .1:
            errors.append("Fault outside the demonstrated recoverable envelope")
    return {"valid": not errors, "errors": errors, "resource_budget": resource,
            "verification": "CONSERVATIVE_ENVELOPE_NOT_A_FLIGHT_PROOF"}


def prepare_engine(engine, mission):
    """Configure only a Gioca start; all future motion still uses SimulationEngine."""
    setup = mission.get("setup", {})
    reset = {"vehicle": mission["vehicle"], "scenario": mission["scenario"], "advanced_models": True}
    for key in ("model_id", "wind_ned_m_s"):
        if key in setup:
            reset[key] = setup[key]
    reset["science_configuration"] = {"seed": mission.get("seed", 42)}
    engine.reset(**reset)
    if "route" in setup:
        engine.configure_route({"found": True, "waypoints_m": setup["route"], "seed": mission.get("seed", 42)})
    if mission["scenario"] == "orbital" and "orbit_altitude_m" in setup:
        from .engine import EARTH_RADIUS, MU_EARTH
        radius = EARTH_RADIUS + setup["orbit_altitude_m"]
        speed = math.sqrt(MU_EARTH / radius)
        inc = math.radians(setup.get("inclination_deg", 0))
        anomaly = math.radians(setup.get("anomaly_deg", -31.5))
        def orbit(angle):
            return [radius * math.cos(angle), radius * math.sin(angle) * math.cos(inc),
                    radius * math.sin(angle) * math.sin(inc), -speed * math.sin(angle),
                    speed * math.cos(angle) * math.cos(inc), speed * math.cos(angle) * math.sin(inc)]
        engine.orbit = orbit(anomaly)
        engine.target_orbit = orbit(anomaly + setup.get("separation_m", 1000) / radius)
        target = setup.get("relative_target_m", [0, -20, 0])
        engine.rendezvous_target_rtn_m = list(target)
        engine.rendezvous_guidance_state["target_offset_rtn_m"] = list(target)
        engine.mission_metrics["rendezvous_target_offset_rtn_m"] = list(target)
        engine.spacecraft_attitude.initialize(engine.orbit[:3], engine.orbit[3:], [0, 0, 0])
        engine.spacecraft_attitude.body_rates_rad_s = [0., 0., 0.]
        engine.spacecraft_attitude.inertial_hold_quaternion = engine.spacecraft_attitude.quaternion_body_to_eci[:]
        relative, velocity, _ = engine._relative_rtn_state()
        engine.relative_navigation.reset(relative, velocity)
        if engine.science is not None:
            engine.science.trajectory = (relative[:], velocity[:])
            engine.science.plan_start = engine.t
    if mission["scenario"] == "planetary" and "initial_height_m" in setup:
        from .planetary_mission import DescentNavigation
        engine.planetary.y[:3] = [setup.get("initial_east_m", 95), setup.get("initial_north_m", -35), setup["initial_height_m"]]
        engine.planetary.navigation = DescentNavigation(engine.planetary.y, mission.get("seed", 42))
    return engine.state()


def apply_mission_events(engine, session):
    if session.mission is None or session.complete or session.failed:
        return
    state = engine.state()
    if not state.get("mission_started"):
        return
    for index, event in enumerate(session.mission.get("events", [])):
        if index in session.events_fired:
            continue
        trigger = event["trigger"]
        if state.get(trigger["field"], 0) < trigger["minimum"]:
            continue
        engine.inject_fault(event["fault"])
        session.events_fired.append(index)
        session.event_log.append({"event": index, "type": event["fault"]["type"],
                                  "time_s": state["time_s"], "trigger_value": state.get(trigger["field"])})
