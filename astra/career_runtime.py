"""Gioca-only catalogue, progression and in-memory physical checkpoints.

The simulator and its reset interface never load procedural mission parameters.
Career JSON stores identifiers, seeds, preferences and measured results, not text.
"""
from __future__ import annotations

from copy import deepcopy
import math

from .gameplay import GameSession, MISSIONS, find_mission, mission_catalog
from .procedural_missions import prepare_engine, apply_mission_events, templates


def career_defaults():
    return dict(schema_version=2, credits=25000, reputation=0, science=0, launches=0,
                missions_completed=0, completed_missions=[], unlocked_technologies=["flight_basics"],
                facilities={"hangar": 1, "mission_control": 1, "research": 1},
                mission_records={}, favorites=[], recent=[], preferences={"language": "it"},
                tutorial_seen=[], active_session={}, statistics={"failures": 0, "flight_seconds": 0.})


def initialize_game(runtime):
    runtime.game_checkpoint = None
    runtime.game_result_recorded = False
    runtime.game_next_id = ""
    runtime.game_earned_reward = {"credits": 0, "reputation": 0, "science": 0}
    runtime.game_tutorial = ""


def _integer(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}")
    return value


def _language(runtime, payload):
    language = payload.get("language", runtime.career["preferences"].get("language", "it"))
    if language not in {"it", "en"}:
        raise ValueError("Mission language must be it or en")
    return language


def _completed_count(runtime, vehicle):
    count = 0
    for mission_id in set(runtime.career["completed_missions"]):
        try:
            if find_mission(mission_id)["vehicle"] == vehicle:
                count += 1
        except (ValueError, AttributeError):
            pass
    return count


def _requires(runtime, mission, completed_count=None):
    if mission["source"] == "story":
        ordered = MISSIONS[mission["vehicle"]]
        index = next(i for i, row in enumerate(ordered) if row["id"] == mission["id"])
        if index and ordered[index - 1]["id"] not in runtime.career["completed_missions"]:
            return [ordered[index - 1]["id"]]
        return []
    need = mission.get("requirements", {}).get("completed_in_discipline", 0)
    done = _completed_count(runtime, mission["vehicle"]) if completed_count is None else completed_count
    if done >= need:
        return []
    return [(f"Complete {need} missions in this discipline ({done}/{need})" if mission["language"] == "en" else
             f"Completa {need} missioni nella disciplina ({done}/{need})")]


def _annotate(runtime, mission, count):
    item = deepcopy(mission)
    record = runtime.career["mission_records"].get(item["id"], {})
    completed = item["id"] in runtime.career["completed_missions"]
    active = runtime.game_session.mission is not None and runtime.game_session.mission["id"] == item["id"] and not (runtime.game_session.complete or runtime.game_session.failed)
    item.update(requires=_requires(runtime, item, count), favorite=item["id"] in runtime.career["favorites"],
                medal=record.get("best_medal", "bronze" if completed else ""),
                status="in_progress" if active else "completed" if completed else "new")
    item["locked"] = bool(item["requires"])
    return item


def game_catalogue(runtime, payload):
    language = _language(runtime, payload)
    vehicle = payload.get("vehicle")
    source = payload.get("source", "story")
    if source not in {"all", "story", "contracts", "daily", "weekly", "favorites", "recent"}:
        raise ValueError("Unknown mission source")
    if vehicle is not None and vehicle not in MISSIONS:
        raise ValueError("Choose space, aircraft or drone")
    query = payload.get("query", "")
    if not isinstance(query, str) or len(query) > 200:
        raise ValueError("query must be text of at most 200 characters")
    difficulty = _integer(payload.get("difficulty", 0), "difficulty", 0, 5)
    offset = _integer(payload.get("offset", 0), "offset", 0, 100000)
    limit = _integer(payload.get("limit", 1000), "limit", 1, 1000)
    duration = payload.get("max_duration_s", 0)
    if isinstance(duration, bool) or not isinstance(duration, (float, int)) or not math.isfinite(duration) or duration < 0:
        raise ValueError("max_duration_s must be a nonnegative finite number")
    family = payload.get("family", "")
    if not isinstance(family, str):
        raise ValueError("family must be text")
    sort = payload.get("sort", "difficulty")
    if sort not in {"difficulty", "duration", "reward", "recent", "title"}:
        raise ValueError("Unknown mission sort")
    if source in {"favorites", "recent"}:
        catalogue = {kind: [] for kind in MISSIONS if vehicle is None or vehicle == kind}
        for mission_id in runtime.career[source]:
            try:
                item = find_mission(mission_id, language)
                if item["vehicle"] in catalogue:
                    catalogue[item["vehicle"]].append(item)
            except (ValueError, AttributeError):
                continue
    else:
        catalogue = mission_catalog(vehicle, source=source, language=language, calendar_date=payload.get("date"))
    families = sorted({"story"} | {row["family"] for row in templates() if vehicle is None or row["vehicle"] == vehicle})
    result, total, catalog_total = {}, 0, sum(len(rows) for rows in catalogue.values())
    for kind, rows in catalogue.items():
        count = _completed_count(runtime, kind)
        filtered = [row for row in rows if (not difficulty or row["difficulty"] == difficulty)
                    and (not duration or row["duration_s"] <= duration)
                    and (not family or family == "all" or row["family"] == family)
                    and (not query or query.casefold() in (row["title"] + " " + row["briefing"] + " " + row["family"]).casefold())]
        if source not in {"recent", "favorites"}:
            key = (lambda row: (row["duration_s"], row["id"])) if sort == "duration" else (lambda row: (-row["reward"]["credits"], row["id"])) if sort == "reward" else (lambda row: row["title"]) if sort == "title" else (lambda row: (row["source"] != "story", row["difficulty"], row["id"]))
            filtered.sort(key=key)
        total += len(filtered)
        result[kind] = [_annotate(runtime, row, count) for row in filtered[offset:offset + limit]]
    # Keep the no-option/legacy response shape intact, including the 12 story IDs.
    if any(key in payload for key in ("source", "query", "offset", "limit", "difficulty", "family", "sort", "max_duration_s")):
        result["_meta"] = {"total": total, "catalog_total": catalog_total, "offset": offset, "limit": limit,
                           "families": families, "source": source, "language": language}
    return result


def next_mission_id(runtime):
    current = runtime.game_session.mission
    if current is None:
        return ""
    rows = mission_catalog(current["vehicle"], source="all", language=current["language"])[current["vehicle"]]
    count = _completed_count(runtime, current["vehicle"])
    for item in rows:
        if item["id"] != current["id"] and item["id"] not in runtime.career["completed_missions"] and not _requires(runtime, item, count):
            return item["id"]
    return ""


def game_snapshot(runtime):
    result = runtime.game_session.snapshot()
    result.update(checkpoint_available=runtime.game_checkpoint is not None,
                  checkpoint_scope="CURRENT_PROCESS_ONLY", next_mission_id=runtime.game_next_id,
                  earned_reward=deepcopy(runtime.game_earned_reward), tutorial=runtime.game_tutorial)
    mission = runtime.game_session.mission
    if mission is not None:
        failures = runtime.career["mission_records"].get(mission["id"], {}).get("failures", 0)
        en = mission["language"] == "en"
        result["hint"] = (("Use small corrections, check reserve and save a checkpoint before the difficult segment. Read the next waypoint and slow down before reaching it." if en else
                           "Usa piccole correzioni, controlla la riserva e salva un checkpoint prima del tratto difficile. Leggi il prossimo waypoint e rallenta prima di raggiungerlo.") if failures >= 2 else "")
    return result


def _save_checkpoint(runtime):
    if runtime.game_session.mission is None or runtime.game_session.complete or runtime.game_session.failed:
        raise ValueError("A live Gioca mission is required for a checkpoint")
    # Preserve the engine object's identity: browser_bridge and SDK share it.
    runtime.game_checkpoint = {"engine": deepcopy(runtime.engine.__dict__), "session": deepcopy(runtime.game_session)}


def _start(runtime, mission_id, language):
    mission = find_mission(mission_id, language)
    required = _requires(runtime, mission)
    if required:
        raise ValueError("Mission locked: " + "; ".join(required))
    if not mission.get("feasibility", {"valid": True})["valid"]:
        raise ValueError("Mission does not pass its physical envelope validator")
    runtime.running = False
    runtime.controller_armed = False
    runtime.last_pilot_wall = None
    runtime.clock_owner = "desktop"
    runtime.play_mode = "free"
    runtime.revision += 1
    runtime.samples = []; runtime.events = []; runtime.next_sample = 0.; runtime.dropped_samples = 0
    prepare_engine(runtime.engine, mission)
    runtime._command(dict(mode="manual", throttle_pct=0, pitch_deg=90 if mission["vehicle"] == "space" and mission["scenario"] == "mission" else 0))
    runtime.game_session = GameSession()
    runtime.game_session.start(mission_id, language)
    runtime.game_session.update(runtime.engine.state(), 0.)
    runtime.game_awarded = False
    initialize_game(runtime)
    record = runtime.career["mission_records"].setdefault(mission_id, {})
    record["attempts"] = record.get("attempts", 0) + 1
    record.update(template_id=mission.get("template_id"), seed=mission.get("seed"))
    runtime.career["recent"] = ([mission_id] + [entry for entry in runtime.career["recent"] if entry != mission_id])[:30]
    runtime.career["launches"] += 1
    runtime.career["preferences"]["language"] = language
    if mission["vehicle"] not in runtime.career["tutorial_seen"]:
        runtime.game_tutorial = ("Start with low inputs. T toggles SAS where available. Track the measured objectives; save a checkpoint before a difficult segment." if language == "en" else
                                 "Inizia con comandi piccoli. T attiva il SAS dove disponibile. Segui gli obiettivi misurati; salva un checkpoint prima di un tratto difficile.")
        runtime.career["tutorial_seen"].append(mission["vehicle"])
    _save_checkpoint(runtime)
    runtime.career["active_session"] = runtime.game_session.save_state()
    runtime._save_career()
    return runtime._snapshot()


def before_game_step(runtime):
    apply_mission_events(runtime.engine, runtime.game_session)


def advance_game(runtime, state, dt):
    if runtime.game_session.mission is None:
        return
    old = dict(runtime.game_session.progress)
    progress = runtime.game_session.update(state, dt)
    if progress["complete"] or progress["failed"]:
        runtime.running = False
        if runtime.game_result_recorded:
            return
        runtime.game_result_recorded = True
        mission_id = progress["mission"]["id"]
        record = runtime.career["mission_records"].setdefault(mission_id, {})
        runtime.career["statistics"]["flight_seconds"] += progress["elapsed_s"]
        if progress["complete"]:
            first = mission_id not in runtime.career["completed_missions"]
            ranks = {"": 0, "bronze": 1, "silver": 2, "gold": 3}
            current = ranks[progress["medal"]]
            best = ranks.get(record.get("best_medal", "" if first else "bronze"), 1)
            multiplier = 1 + .1 * (current - 1)
            previous = 0 if first else 1 + .1 * (best - 1)
            payout = {key: max(0, round(value * multiplier) - round(value * previous))
                      for key, value in progress["mission"]["reward"].items()}
            for key, value in payout.items():
                runtime.career[key] += value
            if first:
                runtime.career["completed_missions"].append(mission_id)
                runtime.career["missions_completed"] += 1
            record["completions"] = record.get("completions", 0) + 1
            if current >= best:
                record["best_medal"] = progress["medal"]
                record["best_metrics"] = progress["metrics"]
            runtime.game_awarded = True
            runtime.game_earned_reward = payout
            runtime.events.append(dict(type="CAREER_MISSION_COMPLETE", mission_id=mission_id,
                                       reward=deepcopy(payout), medal=progress["medal"], time_s=state["time_s"]))
        else:
            record["failures"] = record.get("failures", 0) + 1
            runtime.career["statistics"]["failures"] += 1
            record["last_failure"] = progress["failure_reason"]
        runtime.career["active_session"] = runtime.game_session.save_state()
        runtime.game_next_id = next_mission_id(runtime)
        runtime._save_career()
    elif old != runtime.game_session.progress:
        _save_checkpoint(runtime)
        runtime.career["active_session"] = runtime.game_session.save_state()
        runtime._save_career()


def dispatch_game(runtime, endpoint, payload):
    if endpoint == "/desktop/game/catalog":
        return game_catalogue(runtime, payload)
    if endpoint == "/desktop/game/career":
        return deepcopy(runtime.career)
    if endpoint == "/desktop/game/state":
        return {"game": game_snapshot(runtime), "career": deepcopy(runtime.career)}
    if endpoint == "/desktop/game/preferences":
        runtime.career["preferences"]["language"] = _language(runtime, payload)
        runtime._save_career()
        return deepcopy(runtime.career["preferences"])
    if endpoint == "/desktop/game/start":
        return _start(runtime, payload.get("mission_id", ""), _language(runtime, payload))
    if endpoint == "/desktop/game/retry":
        if runtime.game_session.mission is None:
            raise ValueError("No Gioca mission to retry")
        return _start(runtime, runtime.game_session.mission["id"], _language(runtime, payload))
    if endpoint == "/desktop/game/next":
        mission_id = next_mission_id(runtime)
        if not mission_id:
            raise ValueError("No unlocked next mission")
        return _start(runtime, mission_id, _language(runtime, payload))
    if endpoint == "/desktop/game/checkpoint":
        action = payload.get("action", "save")
        if action == "save":
            _save_checkpoint(runtime)
        elif action == "restore":
            if runtime.game_checkpoint is None:
                raise ValueError("No checkpoint in this application session")
            runtime.running = False; runtime.controller_armed = False; runtime.last_pilot_wall = None
            runtime.engine.__dict__.clear()
            runtime.engine.__dict__.update(deepcopy(runtime.game_checkpoint["engine"]))
            runtime.game_session = deepcopy(runtime.game_checkpoint["session"])
            runtime.game_result_recorded = False; runtime.game_awarded = False
            runtime.game_next_id = ""; runtime.clock_owner = "desktop"; runtime.revision += 1
            runtime.game_earned_reward = {"credits": 0, "reputation": 0, "science": 0}
            runtime.samples = []; runtime.next_sample = 0.
        else:
            raise ValueError("Checkpoint action must be save or restore")
        runtime.career["active_session"] = runtime.game_session.save_state()
        runtime._save_career()
        return runtime._snapshot()
    if endpoint == "/desktop/game/favorite":
        mission = find_mission(payload.get("mission_id", ""))
        wanted = payload.get("favorite", True)
        if not isinstance(wanted, bool):
            raise ValueError("favorite must be boolean")
        favorites = runtime.career["favorites"]
        if wanted and mission["id"] not in favorites:
            favorites.append(mission["id"])
        elif not wanted and mission["id"] in favorites:
            favorites.remove(mission["id"])
        runtime._save_career()
        return {"mission_id": mission["id"], "favorite": wanted}
    if endpoint == "/desktop/game/abandon":
        runtime.running = False
        runtime.game_session = GameSession(); initialize_game(runtime)
        runtime.career["active_session"] = {}; runtime._save_career()
        return runtime._snapshot()
    if endpoint == "/desktop/game/career/upgrade":
        facility = str(payload.get("facility", ""))
        if facility not in runtime.career["facilities"]:
            raise ValueError("Unknown ASTRA facility")
        level = int(runtime.career["facilities"][facility])
        if level >= 3:
            raise ValueError("Facility is already at maximum level")
        if runtime.career["credits"] < level * 5000:
            raise ValueError("Not enough career credits")
        runtime.career["credits"] -= level * 5000
        runtime.career["facilities"][facility] = level + 1
        runtime._save_career()
        return deepcopy(runtime.career)
    if endpoint == "/desktop/game/career/unlock":
        technology = str(payload.get("technology", ""))
        costs = {"orbital_operations": 15, "planetary_science": 30, "precision_navigation": 45}
        if technology not in costs:
            raise ValueError("Unknown ASTRA technology")
        if technology not in runtime.career["unlocked_technologies"]:
            if runtime.career["science"] < costs[technology]:
                raise ValueError("Not enough science points")
            runtime.career["science"] -= costs[technology]
            runtime.career["unlocked_technologies"].append(technology)
            runtime._save_career()
        return deepcopy(runtime.career)
    raise ValueError("Unknown Gioca endpoint")
