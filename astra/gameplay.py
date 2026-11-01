"""Measured, scenario-backed career missions for ASTRA's native Gioca mode."""
from __future__ import annotations

from copy import deepcopy
import math


MISSIONS = {
    "space": [
        {"id": "space_skyward", "vehicle": "space", "scenario": "mission",
         "category": "INGEGNERIA", "campaign": "FRONTIERA BLU · I / VI",
         "title": "SKYWARD · Orbita al primo tentativo",
         "briefing": "CONTROLLO MISSIONE: la finestra di lancio è aperta per pochi minuti. Porta il vettore oltre la linea di Kármán, mantieni il corridoio di ascesa e conserva il margine di propellente per la sequenza di inserzione.",
         "objectives": [{"type": "altitude", "value": 120000, "label": "Raggiungi 120 km"}],
         "reward": {"credits": 18000, "reputation": 12, "science": 8}},
        {"id": "space_pulsar", "vehicle": "space", "scenario": "orbital",
         "category": "INGEGNERIA", "campaign": "FRONTIERA BLU · II / VI",
         "title": "PULSAR · Rendezvous in LEO",
         "briefing": "Una capsula di rifornimento ha perso la guida autonoma. Intercetta il bersaglio con impulsi RCS progressivi, controlla la velocità relativa e fermati nel corridoio di prossimità prima del contatto.",
         "objectives": [{"type": "rendezvous", "range_m": 30, "speed_m_s": 0.3,
                         "label": "≤30 m e ≤0,3 m/s dal bersaglio"}],
         "reward": {"credits": 24000, "reputation": 16, "science": 12}},
        {"id": "space_depot", "vehicle": "space", "scenario": "orbital",
         "category": "INGEGNERIA", "campaign": "FRONTIERA BLU · III / VI",
         "title": "WAYFARER · Aggancio al deposito orbitale",
         "briefing": "Il deposito ha energia limitata e una finestra di aggancio. Allinea il veicolo sul corridoio finale, annulla la deriva relativa e completa un rendezvous stabile senza superare il limite di contatto.",
         "objectives": [{"type": "rendezvous", "range_m": 5, "speed_m_s": 0.1,
                         "label": "Stabilizza entro 5 m e 0,1 m/s"}],
         "reward": {"credits": 30000, "reputation": 20, "science": 15}},
        {"id": "space_selene", "vehicle": "space", "scenario": "planetary",
         "category": "ESPLORAZIONE", "campaign": "FRONTIERA BLU · IV / VI",
         "title": "SELENE · Discesa di precisione",
         "briefing": "La base lunare attende un lander prima del passaggio notturno. Leggi la velocità di discesa, frena con anticipo e posa il veicolo senza danneggiare antenne o carico scientifico.",
         "objectives": [{"type": "safe_landing", "speed_m_s": 3.0,
                         "label": "Atterra a ≤3 m/s"}],
         "reward": {"credits": 21000, "reputation": 14, "science": 16}},
        {"id": "space_shackleton", "vehicle": "space", "scenario": "planetary",
         "category": "ESPLORAZIONE", "campaign": "FRONTIERA BLU · V / VI",
         "title": "SHACKLETON · Stazione di misura polare",
         "briefing": "La squadra robotica ha localizzato ghiaccio vicino al bordo del cratere. Mantieni il lander nella fascia di campionamento per acquisire una misura stabile, poi scendi nel sito sicuro prima che la luce svanisca.",
         "objectives": [{"type": "hold_altitude", "minimum_m": 90, "maximum_m": 140,
                         "seconds": 6, "label": "Mantieni 90–140 m per 6 s"},
                        {"type": "safe_landing", "speed_m_s": 1.5,
                         "label": "Atterra nel sito a ≤1,5 m/s"}],
         "reward": {"credits": 27000, "reputation": 19, "science": 24}},
        {"id": "space_vesta", "vehicle": "space", "scenario": "planetary",
         "category": "ESPLORAZIONE", "campaign": "FRONTIERA BLU · VI / VI",
         "title": "VESTA · Deposito del contenitore campioni",
         "briefing": "Ultima discesa della spedizione: consegna il contenitore al sito di raccolta e conserva il veicolo per la missione di rientro. Il contatto deve essere dolce e l'assetto stabile durante l'ultima finestra di misura.",
         "objectives": [{"type": "hold_altitude", "minimum_m": 30, "maximum_m": 55,
                         "seconds": 10, "label": "Stabilizza 30–55 m per 10 s"},
                        {"type": "safe_landing", "speed_m_s": 1.0,
                         "label": "Completa il touchdown a ≤1 m/s"}],
         "reward": {"credits": 34000, "reputation": 24, "science": 30}},
    ],
    "aircraft": [
        {"id": "air_blue_line", "vehicle": "aircraft", "scenario": "mission",
         "category": "PILOTAGGIO", "campaign": "COLLAUDO ATMOSFERICO · I / III",
         "title": "BLUE LINE · Circuito completo",
         "briefing": "Il collaudo inaugurale viene seguito in diretta dalla torre. Decolla, porta il velivolo in quota sul circuito costiero e rientra sulla pista entro il limite di velocità di contatto.",
         "objectives": [{"type": "altitude", "value": 700, "label": "Raggiungi 700 m"},
                        {"type": "distance", "value": 12000, "label": "Vola 12 km"},
                        {"type": "safe_landing", "speed_m_s": 35, "label": "Rientra e atterra in sicurezza"}],
         "reward": {"credits": 8500, "reputation": 8, "science": 2}},
        {"id": "air_alpine", "vehicle": "aircraft", "scenario": "mission",
         "category": "PILOTAGGIO", "campaign": "COLLAUDO ATMOSFERICO · II / III",
         "title": "ALPINE WINDOW · Rotta in quota",
         "briefing": "Una perturbazione chiude il corridoio basso. Attraversa la finestra di quota lungo la rotta alpina, mantieni il controllo in aria rarefatta e riporta il velivolo alla base.",
         "objectives": [{"type": "altitude", "value": 2200, "label": "Raggiungi 2.200 m"},
                        {"type": "distance", "value": 30000, "label": "Completa 30 km"},
                        {"type": "safe_landing", "speed_m_s": 42, "label": "Atterra sotto 42 m/s"}],
         "reward": {"credits": 14000, "reputation": 13, "science": 4}},
        {"id": "air_recovery", "vehicle": "aircraft", "scenario": "mission",
         "category": "PILOTAGGIO", "campaign": "COLLAUDO ATMOSFERICO · III / III",
         "title": "RUNWAY 27 · Rientro stretto",
         "briefing": "Il vento in coda ha ridotto la lunghezza utile della pista. Esegui il circuito compatto, stabilizza l'avvicinamento e atterra entro il limite; portanza, stallo e touchdown sono valutati dal modello 6-DoF.",
         "objectives": [{"type": "altitude", "value": 350, "label": "Supera 350 m"},
                        {"type": "distance", "value": 5000, "label": "Completa 5 km"},
                        {"type": "safe_landing", "speed_m_s": 27, "label": "Atterra sotto 27 m/s"}],
         "reward": {"credits": 10000, "reputation": 10, "science": 3}},
    ],
    "drone": [
        {"id": "drone_grid", "vehicle": "drone", "scenario": "mission",
         "category": "SCIENZA", "campaign": "OCCHI SULLA TERRA · I / III",
         "title": "GRID 04 · Ispezione della linea",
         "briefing": "Una tempesta ha interrotto il monitoraggio della linea elettrica. Acquisisci una traccia continua lungo il corridoio, mantieni la quota di campionamento e rientra con energia sufficiente per l'atterraggio.",
         "objectives": [{"type": "hold_altitude", "minimum_m": 25, "maximum_m": 80,
                         "seconds": 12, "label": "Resta tra 25 e 80 m per 12 s"},
                        {"type": "distance", "value": 250, "label": "Percorri 250 m"},
                        {"type": "safe_landing", "speed_m_s": 1.5, "label": "Rientra e atterra"}],
         "reward": {"credits": 4200, "reputation": 7, "science": 6}},
        {"id": "drone_tower", "vehicle": "drone", "scenario": "mission",
         "category": "SCIENZA", "campaign": "OCCHI SULLA TERRA · II / III",
         "title": "TOWER ECHO · Controllo strutturale",
         "briefing": "Il sensore acustico ha rilevato vibrazioni anomale sulla torre. Mantieni una quota ravvicinata ma sicura per completare la finestra di acquisizione, poi torna al pad senza urti.",
         "objectives": [{"type": "hold_altitude", "minimum_m": 15, "maximum_m": 45,
                         "seconds": 18, "label": "Completa 18 s nella fascia 15–45 m"},
                        {"type": "safe_landing", "speed_m_s": 1.2, "label": "Atterra senza urti"}],
         "reward": {"credits": 5800, "reputation": 9, "science": 9}},
        {"id": "drone_med", "vehicle": "drone", "scenario": "mission",
         "category": "SCIENZA", "campaign": "OCCHI SULLA TERRA · III / III",
         "title": "AEROSOL-3 · Profilo atmosferico",
         "briefing": "Una sonda a terra ha perso il sensore meteo. Vola la tratta di campionamento a quota costante, completa la finestra di misura e recupera il drone sul pad con il pacco dati integro.",
         "objectives": [{"type": "hold_altitude", "minimum_m": 45, "maximum_m": 70,
                         "seconds": 20, "label": "Campiona tra 45 e 70 m per 20 s"},
                        {"type": "distance", "value": 350, "label": "Completa la tratta di 350 m"},
                        {"type": "safe_landing", "speed_m_s": 1.5, "label": "Recupera sul pad a ≤1,5 m/s"}],
         "reward": {"credits": 8500, "reputation": 12, "science": 14}},
    ],
}


# IDs and ordering remain stable for existing career saves. These Gioca-only
# limits use the actual Corvo ground-speed touchdown metric (not sink rate).
MISSIONS["aircraft"][0]["objectives"][0]["value"] = 550
MISSIONS["aircraft"][0]["objectives"][0]["label"] = "Raggiungi 550 m"
MISSIONS["aircraft"][0]["objectives"][-1]["speed_m_s"] = 46
MISSIONS["aircraft"][0]["objectives"][-1]["label"] = "Rientra e atterra a velocità al suolo ≤46 m/s"
MISSIONS["aircraft"][1]["objectives"][0]["value"] = 600
MISSIONS["aircraft"][1]["objectives"][0]["label"] = "Raggiungi 600 m"
MISSIONS["aircraft"][1]["objectives"][1]["value"] = 20000
MISSIONS["aircraft"][1]["objectives"][1]["label"] = "Completa 20 km"
MISSIONS["aircraft"][1]["objectives"][-1]["speed_m_s"] = 46
MISSIONS["aircraft"][1]["objectives"][-1]["label"] = "Atterra a velocità al suolo ≤46 m/s"
MISSIONS["aircraft"][2]["objectives"][-1]["speed_m_s"] = 44
MISSIONS["aircraft"][2]["objectives"][-1]["label"] = "Atterra a velocità al suolo ≤44 m/s"
for _story in MISSIONS["aircraft"]:
    _story["setup"] = {"model_id": "corvo-t2"}

_STORY_EN = {
    "space_skyward": ("SKYWARD · First suborbital ascent", "Climb beyond 120 km with the recoverable capsule. Read real altitude and preserve attitude control during ascent."),
    "space_pulsar": ("PULSAR · LEO rendezvous", "Approach the orbital target and reduce relative speed before entering the proximity corridor."),
    "space_depot": ("WAYFARER · Depot proximity", "Reach the final proximity corridor with low relative speed. This verifies rendezvous, not a simulated docking mechanism."),
    "space_selene": ("SELENE · Precision descent", "Brake the lunar descent and land softly on the local reference plane."),
    "space_shackleton": ("SHACKLETON · Polar measurement", "Hold the measurement altitude band, then land safely. The landing site is a local reference plane."),
    "space_vesta": ("VESTA · Sample container recovery", "Hold a stable measurement window and complete a soft lunar touchdown. Cargo transfer is not simulated."),
    "air_blue_line": ("BLUE LINE · Complete circuit", "Take the Corvo trainer above 550 m, fly 12 km and return to the local runway. Touchdown speed is ground speed."),
    "air_alpine": ("ALPINE WINDOW · Altitude route", "Climb above 600 m and complete 20 km before landing. This is a local training corridor, not geographic Alpine terrain."),
    "air_recovery": ("RUNWAY 27 · Compact recovery", "Climb above 350 m, fly 5 km and land under 44 m/s ground speed with the Corvo trainer."),
    "drone_grid": ("GRID 04 · Line inspection", "Hold the sampling altitude band, fly the measured distance and return with a safe touchdown."),
    "drone_tower": ("TOWER ECHO · Structural survey", "Hold the observation band continuously, then land without impact."),
    "drone_med": ("AEROSOL-3 · Atmospheric profile", "Maintain the sampling altitude, complete the measured route and recover the drone on the local pad."),
}


def _story_mission(mission, language="it"):
    from .procedural_missions import _label, _language
    _language(language)
    item = deepcopy(mission)
    item.update(source="story", family="story", language=language,
                difficulty=1, duration_s=1500 if item["scenario"] == "mission" and item["vehicle"] == "space" else 900 if item["scenario"] == "orbital" else 700 if item["vehicle"] == "aircraft" else 240,
                requirements={})
    for index, objective in enumerate(item["objectives"]):
        objective["id"] = objective["type"]
        objective["label"] = _label(objective, language)
    if language == "en":
        item["title"], item["briefing"] = _STORY_EN[item["id"]]
        item["campaign"] = item["campaign"].replace("FRONTIERA BLU", "BLUE FRONTIER").replace("COLLAUDO ATMOSFERICO", "ATMOSPHERIC TRIALS").replace("OCCHI SULLA TERRA", "EYES ON EARTH")
    return item


def mission_catalog(vehicle: str | None = None, *, source="story", language="it", calendar_date=None) -> dict:
    """The legacy no-option catalogue still returns the original 12 story IDs."""
    from .procedural_missions import contract_catalog
    if vehicle is not None and vehicle not in MISSIONS:
        raise ValueError("Choose space, aircraft or drone")
    if source not in {"story", "contracts", "all", "daily", "weekly"}:
        raise ValueError("Unknown mission source")
    result = {key: [_story_mission(row, language) for row in value] if source in {"story", "all"} else []
              for key, value in MISSIONS.items() if vehicle is None or key == vehicle}
    if source != "story":
        generated = contract_catalog(vehicle, "contracts" if source == "all" else source, language, calendar_date)
        for key in result:
            result[key].extend(generated[key])
    return result


def find_mission(mission_id: str, language="it") -> dict:
    if mission_id.startswith("proc"):
        from .procedural_missions import parse_mission_id
        return parse_mission_id(mission_id, language)
    for missions in MISSIONS.values():
        for mission in missions:
            if mission["id"] == mission_id:
                return _story_mission(mission, language)
    raise ValueError("Gioca mission not found")


class GameSession:
    def __init__(self) -> None:
        self.mission = None
        self.progress = {}
        self.values = {}
        self.holds = {}
        self.in_band = {}
        self.elapsed_s = self.distance_m = self.hold_s = 0.
        self.previous_position = None
        self.last_time_s = None
        self.complete = self.failed = False
        self.failure_reason = ""
        self.medal = ""
        self.events_fired = []
        self.event_log = []
        self.route_index = 1
        self.route_distance_m = None
        self.route_speed_m_s = None
        self.metrics = {"max_altitude_m": 0., "max_load_factor_g": 0., "min_resource_pct": 100.}

    def start(self, mission_id, language="it"):
        self.__init__()
        self.mission = find_mission(mission_id, language)
        self.progress = {item["id"]: False for item in self.mission["objectives"]}
        return self.snapshot()

    @staticmethod
    def _position(state):
        p = state.get("position_ned_m", state.get("position_enu_m"))
        return [float(p[0]), float(p[1])] if p is not None else None

    def update(self, state, dt_s):
        if self.mission is None or self.complete or self.failed:
            return self.snapshot()
        now = float(state.get("time_s", 0))
        dt = max(0., min(now - self.last_time_s, float(dt_s), 10.)) if self.last_time_s is not None else 0.
        self.last_time_s = now
        active = bool(state.get("mission_started"))
        altitude = float(state.get("altitude_m", 0))
        resource = state.get("battery_pct", state.get("propellant_pct"))
        self.metrics["max_altitude_m"] = max(self.metrics["max_altitude_m"], altitude)
        if active:
            self.elapsed_s += dt
            position = self._position(state)
            if position is not None and self.previous_position is not None:
                self.distance_m += math.dist(position, self.previous_position)
            self.previous_position = position
            self.metrics["max_altitude_m"] = max(self.metrics["max_altitude_m"], altitude)
            self.metrics["max_load_factor_g"] = max(self.metrics["max_load_factor_g"], float(state.get("load_factor_g", 0)))
            if resource is not None:
                self.metrics["min_resource_pct"] = min(self.metrics["min_resource_pct"], float(resource))
                self.metrics["resource_pct"] = float(resource)
        touchdown = state.get("mission_metrics", {}).get("touchdown_speed_m_s", state.get("touchdown_speed_m_s"))
        if touchdown is None:
            touchdown = state.get("touchdown_speed_m_s")
        if touchdown is not None:
            self.metrics["touchdown_speed_m_s"] = float(touchdown)
        for objective in self.mission["objectives"]:
            key, kind = objective["id"], objective["type"]
            if self.progress.get(key, False):
                continue
            done, value, target, fraction = False, 0., 1., 0.
            if kind == "altitude":
                value, target = altitude, objective["value"]
                done = active and value >= target
            elif kind == "distance":
                value, target = self.distance_m, objective["value"]
                done = value >= target
            elif kind == "hold_altitude":
                inside = active and objective["minimum_m"] <= altitude <= objective["maximum_m"]
                self.holds[key] = (self.holds.get(key, 0.) + (dt if self.in_band.get(key) else 0.)) if inside else 0.
                self.in_band[key] = inside
                value, target = self.holds[key], objective["seconds"]
                self.hold_s = max(self.holds.values(), default=0.)
                done = value >= target
            elif kind == "safe_landing":
                value, target = touchdown, objective["speed_m_s"]
                done = active and state.get("phase") == "LANDED" and touchdown is not None and 0 <= touchdown <= target
                fraction = float(done)
            elif kind in {"rendezvous", "relative_waypoint"}:
                position = state.get("relative_position_rtn_m")
                velocity = state.get("relative_velocity_rtn_m_s")
                target = objective.get("range_m", objective.get("radius_m"))
                if position is not None and velocity is not None:
                    center = objective.get("position_m", [0, 0, 0])
                    value = math.dist(position, center)
                    speed = math.sqrt(sum(float(v) ** 2 for v in velocity))
                    self.metrics["relative_range_m"] = math.sqrt(sum(float(v) ** 2 for v in position))
                    self.metrics["relative_speed_m_s"] = speed
                    done = value <= target and speed <= objective["speed_m_s"]
                    fraction = min(1., target / max(target, value)) if speed <= objective["speed_m_s"] else .5 * min(1., target / max(target, value))
            elif kind == "route":
                # Score truth independently of the autopilot. Manual pilots
                # must be able to complete the identical waypoint task.
                outbound = self.mission.get("setup", {}).get("route", [])
                points = outbound + list(reversed(outbound[:-1]))
                position = self._position(state)
                velocity = state.get("velocity_ned_m_s")
                if velocity is None and "air_relative_velocity_ned_m_s" in state:
                    air = state["air_relative_velocity_ned_m_s"]
                    wind = state.get("environment", {}).get("wind_velocity_ned_m_s", [0, 0, 0])
                    velocity = [air[i] + wind[i] for i in range(3)]
                target = max(1, len(points) - 1)
                if points and position is not None and self.route_index < len(points):
                    self.route_distance_m = math.dist(position, points[self.route_index])
                    speed = math.hypot(*velocity[:2]) if velocity is not None else None
                    self.route_speed_m_s = speed
                    if active and self.route_distance_m <= 2. and speed is not None and speed <= 2.:
                        self.route_index += 1
                    if self.route_index < len(points):
                        self.route_distance_m = math.dist(position, points[self.route_index])
                value = min(target, self.route_index - 1)
                done = bool(points) and self.route_index >= len(points)
            elif kind == "waypoint":
                position = self._position(state)
                target = objective["radius_m"]
                value = math.dist(position, objective["position_m"]) if position else None
                done = active and value is not None and value <= target
                fraction = min(1., target / max(target, value)) if value is not None else 0.
            elif kind == "fault_detected":
                done = any(f.get("detected") for f in state.get("fault_management", {}).get("active_faults", []))
                value = float(done)
            if kind in {"altitude", "distance", "hold_altitude", "route", "fault_detected"}:
                fraction = min(1., max(0., value / max(target, 1e-9)))
            self.progress[key] = done
            self.values[key] = {"value": value, "target": target, "fraction": 1. if done else fraction}
        constraints = self.mission.get("constraints", {})
        reason = ""
        if active and state.get("phase") in {"CRASHED", "ABORTED"}:
            reason = state["phase"]
        elif active and self.elapsed_s > constraints.get("deadline_s", float("inf")):
            reason = "DEADLINE_EXCEEDED"
        elif active and resource is not None and resource < constraints.get("min_resource_pct", 0):
            reason = "RESOURCE_RESERVE_EXCEEDED"
        elif active and state.get("speed_m_s", 0) > constraints.get("max_speed_m_s", float("inf")):
            reason = "SPEED_LIMIT_EXCEEDED"
        elif active and state.get("phase") == "LANDED" and not all(self.progress.values()):
            reason = "OBJECTIVES_INCOMPLETE_AT_LANDING"
        self.failed = bool(reason)
        self.failure_reason = reason
        self.complete = bool(self.progress) and all(self.progress.values()) and not self.failed
        if self.complete:
            bonus = self.mission.get("bonus", {})
            checks = []
            for key, threshold in bonus.items():
                value = self.elapsed_s if key == "max_elapsed_s" else self.metrics.get("resource_pct") if key == "min_resource_pct" else self.metrics.get(key)
                checks.append(value is not None and (value >= threshold if key == "min_resource_pct" else value <= threshold))
            self.medal = "gold" if checks and all(checks) else "silver" if any(checks) else "bronze"
        return self.snapshot()

    def save_state(self):
        """Persist identifiers and measured state, never generated text or objectives."""
        return {"mission_id": self.mission["id"] if self.mission else None,
                "template_id": self.mission.get("template_id") if self.mission else None,
                "seed": self.mission.get("seed") if self.mission else None,
                **{key: deepcopy(getattr(self, key)) for key in ("progress", "values", "holds", "in_band", "elapsed_s", "distance_m", "hold_s", "previous_position", "last_time_s", "complete", "failed", "failure_reason", "medal", "events_fired", "event_log", "metrics", "route_index", "route_distance_m", "route_speed_m_s")}}

    def snapshot(self):
        if self.mission is None:
            return {"active": False, "mission": None, "progress": {}, "elapsed_s": 0.,
                    "distance_m": 0., "hold_s": 0., "complete": False, "failed": False,
                    "objective_progress": [], "medal": "", "metrics": {}}
        progress = dict(self.progress)
        details = []
        for objective in self.mission["objectives"]:
            key = objective["id"]
            progress.setdefault(objective["type"], self.progress[key])
            details.append({"id": key, "type": objective["type"], "label": objective["label"],
                            "complete": self.progress[key], **self.values.get(key, {"value": 0, "target": 1, "fraction": 0})})
        outbound = self.mission.get("setup", {}).get("route", [])
        points = outbound + list(reversed(outbound[:-1]))
        route_target = ({"position_ned_m": points[self.route_index] + [-30.],
                         "index": self.route_index, "total": len(points) - 1,
                         "distance_m": self.route_distance_m, "radius_m": 2., "max_horizontal_speed_m_s": 2.}
                        if points and self.route_index < len(points) else None)
        navigation = ({"target_m": points[self.route_index], "distance_m": self.route_distance_m,
                       "speed_m_s": self.route_speed_m_s, "index": self.route_index, "total": len(points) - 1}
                      if route_target else {})
        return {"active": True, "mission": deepcopy(self.mission), "progress": progress,
                "objective_progress": details, "elapsed_s": self.elapsed_s, "distance_m": self.distance_m,
                "hold_s": self.hold_s, "complete": self.complete, "failed": self.failed,
                "failure_reason": self.failure_reason, "medal": self.medal,
                "metrics": dict(self.metrics, elapsed_s=self.elapsed_s, distance_m=self.distance_m),
                "events": deepcopy(self.event_log), "route_target": route_target, "navigation": navigation}
