"""Validate N deterministic seeds/template and count distinct physical contracts.

No web access or third-party dependency. This checks data/metric/resource bounds;
tools/mission_reference_flights.py supplies separate constructive flight evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from astra.procedural_missions import (OBJECTIVE_TYPES, VARIANTS_PER_TEMPLATE,
                                       contract_catalog, generate_mission, templates)


def physical_signature(mission):
    """Exclude identity, title, briefing, rewards and unused sampled parameters."""
    objectives = [{key: value for key, value in item.items() if key not in {"id", "label"}}
                  for item in mission["objectives"]]
    physical = {key: mission.get(key) for key in ("vehicle", "scenario", "setup", "events", "constraints", "bonus")}
    physical["objectives"] = objectives
    return hashlib.sha256(json.dumps(physical, sort_keys=True, allow_nan=False,
                                    separators=(",", ":")).encode()).hexdigest()


def check_mission(mission):
    errors = list(mission.get("feasibility", {}).get("errors", []))
    try:
        json.dumps(mission, allow_nan=False)
    except (ValueError, TypeError):
        errors.append("Mission contains nonfinite or non-JSON values")
    if mission.get("vehicle") not in {"space", "aircraft", "drone"}:
        errors.append("Invalid vehicle")
    if mission.get("scenario") not in {"mission", "orbital", "planetary"}:
        errors.append("Unsupported scenario")
    if mission["vehicle"] != "space" and mission["scenario"] != "mission":
        errors.append("Atmospheric vehicle cannot use a space scenario")
    if not mission.get("objectives"):
        errors.append("No objectives")
    identifiers = [o.get("id") for o in mission["objectives"]]
    if len(identifiers) != len(set(identifiers)):
        errors.append("Objective IDs are not unique")
    constraints = mission.get("constraints", {})
    deadline = constraints.get("deadline_s", float("inf"))
    if deadline <= 0:
        errors.append("Nonpositive deadline")
    for objective in mission["objectives"]:
        kind = objective["type"]
        if kind not in OBJECTIVE_TYPES:
            errors.append(f"No measured evaluator for {kind}")
        if kind == "hold_altitude":
            if objective["minimum_m"] >= objective["maximum_m"] or not 0 < objective["seconds"] < deadline:
                errors.append("Impossible altitude window or dwell duration")
        if kind in {"altitude", "distance"} and objective["value"] <= 0:
            errors.append("Nonpositive altitude/distance objective")
        if kind == "safe_landing" and objective["speed_m_s"] <= 0:
            errors.append("Nonpositive landing speed")
        if kind == "route" and len(mission["setup"].get("route", [])) < 2:
            errors.append("Route objective lacks a physical route")
        if kind == "fault_detected" and not mission.get("events"):
            errors.append("Fault objective lacks an actual event")
        if kind in {"rendezvous", "relative_waypoint"} and mission["scenario"] != "orbital":
            errors.append("Relative objective lacks orbital telemetry")
    route = mission["setup"].get("route")
    if route:
        if route[0] != [0, 0] or max(math.hypot(*p) for p in route) > 100:
            errors.append("Route leaves validated local envelope")
        estimate = mission["feasibility"]["resource_budget"]["estimated_flight_s"]
        if deadline < estimate:
            errors.append("Deadline below conservative route duration")
    if any(value <= 0 for value in mission["reward"].values()):
        errors.append("Nonpositive reward")
    return errors


def validate(samples_per_template=64, first_seed=0):
    if not 1 <= samples_per_template <= 10000 or not 0 <= first_seed <= 2147483647 - samples_per_template:
        raise ValueError("Choose 1..10000 samples and a valid nonnegative first seed")
    invalid, tested, by_vehicle = [], 0, Counter()
    template_rows = templates()
    for template in template_rows:
        for seed in range(first_seed, first_seed + samples_per_template):
            try:
                mission = generate_mission(template["id"], seed)
                errors = check_mission(mission)
                by_vehicle[mission["vehicle"]] += 1
            except (ValueError, TypeError, KeyError, ArithmeticError) as error:
                errors = [str(error)]
            tested += 1
            if errors:
                invalid.append({"template_id": template["id"], "seed": seed, "errors": errors})
    catalog = contract_catalog()
    counts, unique, duplicate_counts = {}, {}, {}
    for vehicle, missions in catalog.items():
        counts[vehicle] = len(missions)
        unique[vehicle] = len({physical_signature(mission) for mission in missions})
        duplicate_counts[vehicle] = counts[vehicle] - unique[vehicle]
    enough = all(count >= 300 for count in unique.values())
    return {"schema_version": 1, "validation": "STRUCTURAL_AND_CONSERVATIVE_RESOURCE_ENVELOPE",
            "passed": not invalid and enough, "templates": len(template_rows),
            "sampled_seeds_per_template": samples_per_template, "first_seed": first_seed,
            "missions_tested": tested, "tested_by_discipline": dict(by_vehicle),
            "catalog_variants_per_template": VARIANTS_PER_TEMPLATE,
            "catalog_entries": counts, "physically_distinct_contracts": unique,
            "duplicate_physical_configurations": duplicate_counts,
            "minimum_300_distinct_per_discipline": enough, "invalid_count": len(invalid), "invalid": invalid,
            "distinctness_fields": ["vehicle", "scenario", "setup", "objectives without labels/IDs", "events", "constraints", "bonus"],
            "excluded_from_distinctness": ["ID", "seed", "title", "briefing", "difficulty label", "rewards", "unused parameters"],
            "limits": "Envelope and metric checks are not a proof that every seed can be flown. Real engine reference flights are reported separately in mission-flight-witnesses.json. No geographic scenery, cargo transfer, docking contact or new propulsion models are inferred."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", "-n", type=int, default=64, help="Number of seeds per template")
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/validation/missions.json")
    args = parser.parse_args()
    report = validate(args.seeds, args.first_seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"invalid", "limits", "distinctness_fields", "excluded_from_distinctness"}}, indent=2))
    if report["invalid"]:
        print(json.dumps(report["invalid"][:20], indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
