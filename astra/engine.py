"""Deterministic engineering models used by the ASTRA local simulator.

The default space case uses an Earth-centred inertial state, J2 gravity and a
fixed-step RK4 integrator. Atmospheric vehicles use a local NED frame, a
standard-atmosphere model and six-degree-of-freedom rigid-body equations.
Vehicle coefficients are exposed in the returned model metadata so users can
replace the generic reference airframes with measured data.
"""

from __future__ import annotations

import copy
import math
from typing import Any

from . import __version__
from .attitude import LaunchVehicleAttitude, SpacecraftAttitude, _cross
from .aerodynamics import (fixed_wing_coefficients,
                           fixed_wing_moment_coefficients)
from .atmosphere import ATMOSPHERE_MODEL, atmosphere_isa
from .constants import AIRFIELD_RUNWAY_AIMPOINT_N_M, AIRFIELD_RUNWAY_END_N_M, G0, OMEGA_EARTH
from .gnc import (HorizontalNavigationKF, RelativeNavigationKF,
                  SpaceNavigationKF,
                  UAV_HORIZONTAL_LQR_WEIGHTS,
                  UAV_VERTICAL_LQR_WEIGHTS, VerticalNavigationKF,
                  continuous_lqr_double_integrator_gains,
                  lqr_double_integrator_acceleration)
from .multirotor import (allocate_rotor_thrusts, motor_speed_to_thrust,
                         rotor_geometry, rotor_mixer, rotor_wrench,
                         rotor_mixer_with_health, thrust_to_motor_speed)
from .propulsion import (fixed_wing_power_fraction_for_thrust,
                         fixed_wing_propulsion, multirotor_power)
from .turbulence import (DRYDEN_MODEL, DrydenTurbulence,
                         validate_turbulence_settings)
from .vehicle_design import (ACS_PROPELLANT_FRACTION,
                             build_spacecraft_design)
from .wind import (validate_wind_profile, wind_at_altitude,
                   validate_surface_layer, surface_layer_wind_at_altitude)

MU_EARTH = 3.986004418e14
EARTH_RADIUS = 6_378_137.0
EARTH_J2 = 1.08262668e-3
LAUNCH_SITE_LATITUDE_RAD = math.radians(28.5721)
LAUNCH_SITE_LONGITUDE_RAD = math.radians(-80.6480)
# Sutton–Graves Earth coefficient. With rho in kg/m^3, nose radius in m, and
# velocity in m/s, the convective stagnation-point heat flux is returned in W/m^2.
SUTTON_GRAVES_EARTH = 1.74153e-4
# A fixed-wing stall assessment is not actionable when the dynamic pressure
# produces only negligible wing loads. Keep the polar values for diagnostics,
# but mark stall state/margin as unassessed below this threshold.
STALL_ASSESSMENT_MIN_DYNAMIC_PRESSURE_PA = 1.0
MAX_STEP_S = 0.5
PYTHON_CONTROL_WATCHDOG_S = 1.0
LEO_TARGET_APOAPSIS_M = 300_000.0
LEO_TARGET_PERIAPSIS_M = 80_000.0
LEO_CIRCULARIZATION_ECCENTRICITY = 1e-3
LEO_MIN_IDEAL_DELTA_V_M_S = 9_200.0
ASTRA_TVC_MAX_GIMBAL_DEG = 6.0
ASTRA_TVC_GIMBAL_RATE_DEG_S = 5.0
ASTRA_RCS_FORCE_PER_AXIS_N = 24.0
ASTRA_RCS_ISP_S = 220.0
VEHICLES = {"space", "aircraft", "drone"}
MODEL_CATALOG = {
    "space": {
        "asteria-capsule": {"name": "Asteria · capsula recuperabile", "kind": "capsule",
                            "summary": "Lancio suborbitale con rientro e paracadute.",
                            "dry_kg": 4_000.0, "fuel_kg": 20_000.0,
                            "thrust_N": 320_000.0, "nozzle_exit_area_m2": 0.32, "isp_s": 300.0,
                            "area_m2": 4.0, "Cd": 0.45, "aeroshell_area_m2": 200.0,
                            "nose_radius_m": 1.8, "body_length_m": 13.0,
                            "body_radius_m": 1.8,
                            "drogue_area_m2": 32.0, "parachute_area_m2": 1_000.0},
        "dardo-lifting-body": {"name": "Dardo · corpo portante", "kind": "lifting-body",
                               "summary": "Capsula allungata con superfici di portanza e recupero.",
                               "dry_kg": 5_200.0, "fuel_kg": 26_000.0,
                               "thrust_N": 416_000.0, "nozzle_exit_area_m2": 0.416, "isp_s": 300.0,
                               "area_m2": 7.0, "Cd": 0.38, "aeroshell_area_m2": 280.0,
                               "nose_radius_m": 2.4, "body_length_m": 17.0,
                               "body_radius_m": 2.4,
                               "drogue_area_m2": 42.0, "parachute_area_m2": 1_300.0},
        "astra-leo-servicer": {"name": "ASTRA · veicolo di servizio LEO", "kind": "orbital-servicer",
                               "summary": "Rendezvous LEO · massa secca 400 kg · 80 kg ACS · carica iniziale 65,6 kg · RCS 24 N · Isp 220 s.",
                               "dry_kg": 400.0, "fuel_kg": 80.0,
                               "thrust_N": 24.0, "isp_s": 220.0,
                               "area_m2": 0.0, "Cd": 0.0},
    },
    "aircraft": {
        "aquila-x4": {"name": "Aquila X-4 · bimotore", "kind": "twin-engine",
                       "summary": "Velivolo di riferimento per circuito, salita e atterraggio.",
                       "dry_kg": 5_960.0, "fuel_kg": 240.0, "fuel_start_kg": 164.0,
                       "thrust_N": 22_000.0, "takeoff_speed_m_s": 65.0,
                       "propulsion": {"engine_type": "TURBOPROP_TWIN",
                                      "propeller_count": 2,
                                      "propeller_radius_m": 1.35,
                                      "propeller_efficiency": 0.82,
                                      "power_lapse_exponent": 0.85,
                                      "specific_fuel_consumption_kg_per_kWh": 0.32,
                                      "spool_time_constant_s": 1.2},
                       "aero": {"S_m2": 18.0, "b_m": 10.5, "c_m": 1.8,
                                "CL0": 0.25, "CLalpha_rad": 5.3,
                                "CD0": 0.032, "induced_drag_k": 0.055,
                                "alpha_stall_rad": math.radians(15.0),
                                "stall_transition_rad": math.radians(4.0),
                                "post_stall_decay_rad": math.radians(20.0),
                                "CL_post_stall": 0.55,
                                "CD_stall_per_rad2": 4.5,
                                "aileron_max_deflection_rad": math.radians(20.0),
                                "elevator_max_deflection_rad": math.radians(25.0),
                                "rudder_max_deflection_rad": math.radians(30.0),
                                "aileron_rate_limit_rad_s": math.radians(60.0),
                                "elevator_rate_limit_rad_s": math.radians(45.0),
                                "rudder_rate_limit_rad_s": math.radians(60.0),
                                "aileron_time_constant_s": 0.12,
                                "elevator_time_constant_s": 0.16,
                                "rudder_time_constant_s": 0.16,
                                "CYbeta_rad": -0.65,
                                # Generic, uncalibrated linear stability derivatives.
                                # Cm0 balances Cm_alpha at 3.6 deg reference alpha.
                                "Cl_beta_per_rad": -0.12, "Cl_p": -0.5,
                                "Cl_delta_a_at_max_deflection": 0.08,
                                "Cm0": 0.8*math.radians(3.6),
                                "Cm_alpha_per_rad": -0.8,
                                "Cm_q": -12.0,
                                "Cm_delta_e_at_max_deflection": 1.05,
                                "Cn_beta_per_rad": 0.16, "Cn_r": -0.22,
                                "Cn_delta_r_at_max_deflection": 0.07,
                                "Ixx_kgm2": 9_800.0,
                                "Iyy_kgm2": 32_000.0, "Izz_kgm2": 38_000.0}},
        "corvo-t2": {"name": "Corvo T-2 · addestratore", "kind": "trainer",
                     "summary": "Aereo leggero da addestramento, piu lento e agile.",
                     "dry_kg": 1_500.0, "fuel_kg": 220.0, "fuel_start_kg": 170.0,
                     "thrust_N": 7_000.0, "takeoff_speed_m_s": 42.0,
                     "propulsion": {"engine_type": "PISTON_SINGLE",
                                    "propeller_count": 1,
                                    "propeller_radius_m": 1.05,
                                    "propeller_efficiency": 0.80,
                                    "power_lapse_exponent": 0.85,
                                    "specific_fuel_consumption_kg_per_kWh": 0.34,
                                    "spool_time_constant_s": 0.65},
                     "aero": {"S_m2": 16.0, "b_m": 9.7, "c_m": 1.5,
                              "CL0": 0.32, "CLalpha_rad": 4.9,
                              "CD0": 0.034, "induced_drag_k": 0.052,
                              "alpha_stall_rad": math.radians(15.0),
                              "stall_transition_rad": math.radians(4.0),
                              "post_stall_decay_rad": math.radians(20.0),
                              "CL_post_stall": 0.55,
                              "CD_stall_per_rad2": 4.5,
                              "aileron_max_deflection_rad": math.radians(20.0),
                              "elevator_max_deflection_rad": math.radians(25.0),
                              "rudder_max_deflection_rad": math.radians(30.0),
                              "aileron_rate_limit_rad_s": math.radians(60.0),
                              "elevator_rate_limit_rad_s": math.radians(45.0),
                              "rudder_rate_limit_rad_s": math.radians(60.0),
                              "aileron_time_constant_s": 0.12,
                              "elevator_time_constant_s": 0.16,
                              "rudder_time_constant_s": 0.16,
                              "CYbeta_rad": -0.7,
                              # Generic, uncalibrated linear stability derivatives.
                              # Cm0 balances Cm_alpha at 2.5 deg reference alpha.
                              "Cl_beta_per_rad": -0.12, "Cl_p": -0.5,
                              "Cl_delta_a_at_max_deflection": 0.08,
                              "Cm0": 0.8*math.radians(2.5),
                              "Cm_alpha_per_rad": -0.8,
                              "Cm_q": -12.0,
                              "Cm_delta_e_at_max_deflection": 1.05,
                              "Cn_beta_per_rad": 0.16, "Cn_r": -0.22,
                              "Cn_delta_r_at_max_deflection": 0.07,
                              "Ixx_kgm2": 1_800.0,
                              "Iyy_kgm2": 5_200.0, "Izz_kgm2": 6_500.0}},
    },
    "drone": {
        "falco-q8": {"name": "Falco Q8 · quadricottero", "kind": "quadrotor",
                     "summary": "Drone leggero a quattro rotori per ispezione ravvicinata.",
                     "mass_kg": 2.4, "thrust_N": 48.0, "arm_m": 0.23,
                     "Ixx_kgm2": 0.035, "Iyy_kgm2": 0.035, "Izz_kgm2": 0.062,
                     "rotors": 4, "rotor_radius_m": 0.127,
                     "battery_capacity_Wh": 177.6, "battery_start_pct": 74.0,
                     "rotor_max_tip_speed_m_s": 120.0,
                     "motor_time_constant_up_s": 0.08,
                     "motor_time_constant_down_s": 0.12,
                     "yaw_moment_coefficient_m": 0.012,
                     "figure_of_merit": 0.65, "motor_efficiency": 0.90,
                     "profile_power_max_W": 65.0, "avionics_power_W": 12.0,
                     "body_drag_area_m2": 0.08,
                     "airframe_propulsive_efficiency": 0.72},
        "merlo-h6": {"name": "Merlo H6 · esacottero", "kind": "hexarotor",
                     "summary": "Piattaforma a sei rotori, piu pesante e con maggiore spinta.",
                     "mass_kg": 3.8, "thrust_N": 72.0, "arm_m": 0.28,
                     "Ixx_kgm2": 0.071, "Iyy_kgm2": 0.071, "Izz_kgm2": 0.13,
                     "rotors": 6, "rotor_radius_m": 0.14,
                     "battery_capacity_Wh": 266.4, "battery_start_pct": 74.0,
                     "rotor_max_tip_speed_m_s": 135.0,
                     "motor_time_constant_up_s": 0.09,
                     "motor_time_constant_down_s": 0.13,
                     "yaw_moment_coefficient_m": 0.014,
                     "figure_of_merit": 0.66, "motor_efficiency": 0.90,
                     "profile_power_max_W": 92.0, "avionics_power_W": 16.0,
                     "body_drag_area_m2": 0.11,
                     "airframe_propulsive_efficiency": 0.72},
    },
}
DEFAULT_MODELS = {"space": "asteria-capsule", "aircraft": "aquila-x4", "drone": "falco-q8"}


def _clamp(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))


def _norm3(a: list[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def _add(a: list[float], b: list[float], scale: float) -> list[float]:
    return [x + scale * y for x, y in zip(a, b)]


from .live_systems import LiveSystems
from .mission_route import MissionRoute
from .mission_science import MissionScience


class SimulationEngine:
    """One deterministic ASTRA vehicle simulation, safe for a local API."""

    def __init__(self) -> None:
        self.reset("space")

    def reset(self, vehicle: str = "space", scenario: str = "mission",
              model_id: str | None = None,
              custom_design: dict[str, Any] | None = None,
              wind_ned_m_s: list[float] | tuple[float, float, float] | None = None,
              turbulence: dict[str, Any] | None = None,
              wind_profile_ned_m_s: list[dict[str, Any]] | None = None,
              surface_layer_wind: dict[str, Any] | None = None,
              advanced_models: bool = False,
              science_configuration: dict[str, Any] | None = None
              ) -> dict[str, Any]:
        if not isinstance(advanced_models, bool):
            raise ValueError('advanced_models must be boolean')
        self.science = None
        self.planetary = None
        if vehicle not in VEHICLES:
            raise ValueError(f"vehicle must be one of {sorted(VEHICLES)}")
        wind = self._validate_wind(wind_ned_m_s)
        wind_profile = validate_wind_profile(wind_profile_ned_m_s, vehicle)
        surface_layer = validate_surface_layer(surface_layer_wind, vehicle)
        if surface_layer is not None and (wind_profile is not None or _norm3(wind) > 0):
            raise ValueError("surface_layer_wind replaces uniform wind and wind_profile_ned_m_s")
        if wind_profile is not None and _norm3(wind) > 0.0:
            raise ValueError(
                "wind_profile_ned_m_s replaces wind_ned_m_s; provide a zero uniform wind vector")
        if vehicle == "space" and _norm3(wind) > 0.0:
            raise ValueError("wind_ned_m_s is available only for aircraft and drones")
        if vehicle == "drone" and _norm3(wind) > 16.0:
            raise ValueError("drone wind magnitude must not exceed the 16 m/s model envelope")
        turbulence_settings = validate_turbulence_settings(turbulence, vehicle)
        if scenario not in {"mission", "leo-return", "orbital", "planetary"}:
            raise ValueError("scenario must be mission, leo-return, orbital or planetary")
        if vehicle != "space" and scenario != "mission":
            raise ValueError("leo-return and orbital scenarios are available only for spacecraft")
        if custom_design is not None:
            if vehicle != "space" or scenario not in {"mission", "leo-return"}:
                raise ValueError("custom launch stacks are available for spacecraft launch missions")
            if model_id not in (None, "astra-custom-stack"):
                raise ValueError("custom_design cannot be combined with a catalog model")
            design = build_spacecraft_design(custom_design)
            if scenario == "leo-return" and design["ideal_delta_v_m_s"] < LEO_MIN_IDEAL_DELTA_V_M_S:
                raise ValueError("leo-return requires a custom launch stack with at least 9.2 km/s ideal delta-v; actual ascent losses and maneuver reserves are simulated")
            if (scenario == "leo-return"
                    and min(design["stage_twr_at_sea_level"]) < 1.1):
                raise ValueError("leo-return requires every stage to have at least 1.1 sea-level thrust-to-weight ratio")
            self.model_id = "astra-custom-stack"
            self.vehicle_model = dict(MODEL_CATALOG["space"][DEFAULT_MODELS["space"]])
            self.vehicle_model.update({
                "name": design["name"],
                "summary": "Assemblato nel Vehicle Lab · stack multistadio parametrico con separazione automatica.",
                "dry_kg": design["dry_mass_kg"],
                "fuel_kg": design["propellant_capacity_kg"],
                "thrust_N": design["thrust_vacuum_N"],
                "nozzle_exit_area_m2": design["engine_nozzle_exit_area_m2"] * design["engine_count"],
                "isp_s": design["engine_isp_vacuum_s"],
            })
            self.custom_design = design
        else:
            if scenario == "leo-return":
                raise ValueError("leo-return requires a custom multistage spacecraft stack")
            if model_id == "astra-custom-stack":
                raise ValueError("custom_design is required for the ASTRA custom stack")
            requested_model_id = model_id or DEFAULT_MODELS[vehicle]
            if requested_model_id not in MODEL_CATALOG[vehicle]:
                raise ValueError(f"model_id must be one of {sorted(MODEL_CATALOG[vehicle])}")
            if scenario == "orbital":
                self.model_id = "astra-leo-servicer"
            else:
                if requested_model_id == "astra-leo-servicer":
                    raise ValueError("astra-leo-servicer is available only for orbital rendezvous")
                self.model_id = requested_model_id
            self.vehicle_model = MODEL_CATALOG[vehicle][self.model_id]
            self.custom_design = None
        self.vehicle = vehicle
        self.scenario = scenario
        self.wind_ned_m_s = wind
        self.wind_profile_ned_m_s = wind_profile
        self.surface_layer_wind = surface_layer
        self.turbulence_settings = turbulence_settings
        self.turbulence_model = (
            DrydenTurbulence(turbulence_settings["sigma_uvw_m_s"],
                             turbulence_settings["length_uvw_m"],
                             turbulence_settings["seed"])
            if turbulence_settings["model"] == DRYDEN_MODEL else None)
        # Optional per-engine ceiling used by isolated numerical studies.
        # It never changes the live engine or the model's normal step limits.
        self.integration_step_cap_s: float | None = None
        # Refinement studies can hold the controller sample period fixed while
        # making the numerical integration step smaller.
        self.guidance_update_period_s: float | None = None
        self._next_guidance_update_s: float | None = None
        self.t = 0.0
        self.live_systems = LiveSystems()
        self.mission_route = None
        self.launch_t = None
        self.mission_started = scenario == "orbital"
        self.phase = "RENDEZVOUS" if scenario == "orbital" else "READY"
        self.phase_time_s = 0.0
        self.fault = None
        self.injected_faults: list[dict[str, Any]] = []
        self.fdir_events: list[dict[str, Any]] = []
        self.next_fault_id = 1
        self.fdir_recovery_mode = "NOMINAL"
        self.rotor_fault_mixer: list[list[float]] | None = None
        self.fdir_landing_track_deg: float | None = None
        self.vertical_nav: VerticalNavigationKF | None = None
        self.horizontal_nav: HorizontalNavigationKF | None = None
        self.relative_navigation: RelativeNavigationKF | None = None
        self.space_navigation: SpaceNavigationKF | None = None
        self.guidance_target_ned_m = [0.0, 0.0]
        self.fdir_sensor_landing_position_ned_m: list[float] | None = None
        self.mission_metrics = {"max_altitude_m": 0.0,
                                "max_dynamic_pressure_Pa": 0.0,
                                "max_stagnation_point_convective_heat_flux_W_m2": 0.0,
                                "stagnation_point_convective_heat_load_J_m2": 0.0,
                                "touchdown_speed_m_s": None,
                                "touchdown_air_relative_speed_m_s": None,
                                "insertion_orbit": None,
                                "insertion_cutoff_orbit": None,
                                "deorbit_orbit": None,
                                "orbital_hold_s": 0.0,
                                "touchdown_position_eci_m": None,
                                "max_load_factor_g": 0.0,
                                "max_specific_force_m_s2": 0.0}
        self.mission_metrics["acs_propellant_used_kg"] = 0.0
        self.orbit_hold_started_s: float | None = None
        self.orbit_hold_duration_s: float | None = None
        self.nozzle_exit_area_m2 = 0.0
        self.command = {"throttle_pct": 0.0, "roll_deg": 0.0,
                        "pitch_deg": 0.0, "yaw_deg": 0.0,
                        "attitude_target_deg": [0.0, 0.0, 0.0],
                        "attitude_torque_body_fraction": [0.0, 0.0, 0.0],
                        "attitude_sas_mode": "stability_assist",
                        "sas_enabled": False,
                        "maneuver_direction_eci": None,
                        "brakes_pct": 0.0,
                        "mode": "auto"}
        self.external_control = {
            "state": "DISARMED",
            "watchdog_timeout_s": PYTHON_CONTROL_WATCHDOG_S,
            "last_command_time_s": None,
            "events": [],
        }
        self.acs_propellant_capacity_kg = 0.0
        self.acs_propellant_kg = 0.0
        self.specific_force_body_m_s2 = [0.0, 0.0, 0.0]
        self.load_factor_g = 0.0
        self.spacecraft_attitude: SpacecraftAttitude | None = None
        self.launch_vehicle_attitude: LaunchVehicleAttitude | None = None
        if vehicle == "space":
            if scenario == "orbital":
                self._reset_orbit()
            else:
                self._reset_space()
        elif vehicle == "aircraft":
            self._reset_aircraft()
        else:
            self._reset_drone()
        if vehicle != "space":
            self._update_atmospheric_specific_force()
        elif scenario != "orbital":
            # The launch pad is a static boundary condition at t=0; expose its
            # equivalent support force without adding ground contact dynamics.
            gravity_eci = self._gravity_eci_acceleration(self.orbit[:3])
            self._set_specific_force_eci([-value for value in gravity_eci])
        if scenario == 'planetary':
            from .planetary_mission import PlanetaryMission
            from .mission_science import validate_configuration
            config = validate_configuration(science_configuration or {})
            self.planetary = PlanetaryMission(config['seed'])
            self.mass_dry_kg = self.planetary.dry
            self.mass_kg = self.planetary.y[13]
            self.propellant_kg = self.mass_kg-self.mass_dry_kg
            self.propellant_capacity_kg = self.propellant_kg
            self.launch_vehicle_attitude = None
            self.space_navigation = None
            self.phase = 'READY'
        if advanced_models or scenario == 'planetary':
            self.science = MissionScience(self, science_configuration)
        return self.state()

    def _guidance_update_due(self, time_s: float) -> bool:
        period = self.guidance_update_period_s
        if period is None:
            return True
        if self._next_guidance_update_s is None:
            self._next_guidance_update_s = time_s + period
            return True
        if time_s + 1e-10 < self._next_guidance_update_s:
            return False
        elapsed_periods = math.floor(
            (time_s-self._next_guidance_update_s+1e-10)/period) + 1
        self._next_guidance_update_s += elapsed_periods*period
        return True

    def _reset_space(self) -> None:
        # Recoverable suborbital capsule: vertical launch, coast to apogee,
        # atmospheric return, staged drogue/main parachute and touchdown.
        radius = EARTH_RADIUS + 1.5
        latitude = LAUNCH_SITE_LATITUDE_RAD
        longitude = LAUNCH_SITE_LONGITUDE_RAD
        cos_latitude = math.cos(latitude)
        x = radius * cos_latitude * math.cos(longitude)
        y = radius * cos_latitude * math.sin(longitude)
        z = radius * math.sin(latitude)
        # ASTRA's reference launch point is Kennedy Space Center. At t=0 the
        # local atmosphere co-rotates with Earth, so initialize v = omega x r.
        self.orbit = [x, y, z, -OMEGA_EARTH * y,
                      OMEGA_EARTH * x, 0.0]
        target_radius = EARTH_RADIUS + 120_000.0
        self.target_orbit = [target_radius, 0.0, 0.0, 0.0,
                             math.sqrt(MU_EARTH / target_radius), 0.0]
        self.stage_events: list[dict[str, float | int | str]] = []
        self.active_stage_index = 0
        if self.custom_design:
            self.stage_specs = [dict(stage) for stage in self.custom_design["stages"]]
            self.stage_propellant_kg = [stage["propellant_capacity_kg"]
                                        for stage in self.stage_specs]
            self.mass_dry_kg = self.custom_design["dry_mass_kg"]
            self.propellant_capacity_kg = self.custom_design["propellant_capacity_kg"]
            self.propellant_kg = sum(self.stage_propellant_kg)
            self.acs_propellant_capacity_kg = self.custom_design["acs_propellant_capacity_kg"]
        else:
            self.stage_specs = [{"stage": 1, "dry_mass_kg": 0.0,
                                 "propellant_capacity_kg": self.vehicle_model["fuel_kg"],
                                 "thrust_vacuum_N": self.vehicle_model["thrust_N"],
                                 "nozzle_exit_area_m2": self.vehicle_model.get("nozzle_exit_area_m2", 0.0),
                                 "isp_vacuum_s": self.vehicle_model["isp_s"]}]
            self.stage_propellant_kg = [self.vehicle_model["fuel_kg"]]
            self.mass_dry_kg = self.vehicle_model["dry_kg"]
            self.propellant_capacity_kg = self.vehicle_model["fuel_kg"]
            self.propellant_kg = self.propellant_capacity_kg
            self.acs_propellant_capacity_kg = self.propellant_capacity_kg * ACS_PROPELLANT_FRACTION
        self.acs_propellant_kg = self.acs_propellant_capacity_kg
        self.mass_kg = (self.mass_dry_kg + self.propellant_kg +
                        self.acs_propellant_kg)
        self._activate_stage()
        self.launch_vehicle = {"Cd": self.vehicle_model["Cd"],
                               "area_m2": self.vehicle_model["area_m2"],
                               "aeroshell_Cd": 1.2,
                               "aeroshell_area_m2": self.vehicle_model["aeroshell_area_m2"],
                               "nose_radius_m": self.vehicle_model["nose_radius_m"],
                               "drogue_Cd": 1.5,
                               "drogue_area_m2": self.vehicle_model["drogue_area_m2"],
                               "parachute_Cd": 1.5,
                               "parachute_area_m2": self.vehicle_model["parachute_area_m2"],
                               "tvc_max_gimbal_deg": ASTRA_TVC_MAX_GIMBAL_DEG,
                               "tvc_gimbal_rate_deg_s": ASTRA_TVC_GIMBAL_RATE_DEG_S,
                               "geometry_model": "ASTRA_REFERENCE_STACK_GEOMETRY"}
        if self.custom_design:
            body_length_m = self.custom_design["body_length_m"]
            body_radius_m = self.custom_design["body_radius_m"]
            capsule_length_m = 3.4
            capsule_radius_m = 1.8
        else:
            body_length_m = self.vehicle_model["body_length_m"]
            body_radius_m = self.vehicle_model["body_radius_m"]
            capsule_length_m = body_length_m
            capsule_radius_m = body_radius_m
        self.launch_vehicle.update({
            "body_length_m": body_length_m,
            "body_radius_m": body_radius_m,
            "capsule_section_length_m": capsule_length_m,
            "capsule_reference_radius_m": capsule_radius_m,
        })
        self.launch_vehicle_attitude = LaunchVehicleAttitude(
            body_length_m, body_radius_m,
            ASTRA_TVC_MAX_GIMBAL_DEG, ASTRA_TVC_GIMBAL_RATE_DEG_S,
            ASTRA_RCS_FORCE_PER_AXIS_N, ASTRA_RCS_ISP_S)
        self.launch_vehicle_attitude.initialize(self.orbit[:3], self.orbit[3:], 90.0, 0.0)
        self.space_navigation = SpaceNavigationKF()
        self.space_navigation.reset(self.orbit[:3], self.orbit[3:])
        self.launch_attitude_update_period_s = 0.05
        self._launch_attitude_sample_start_s: float | None = None
        self._launch_attitude_sample_next_s: float | None = None
        self._launch_attitude_sample_start: LaunchVehicleAttitude | None = None
        self._launch_attitude_sample_mid: LaunchVehicleAttitude | None = None
        self._launch_attitude_sample_end: LaunchVehicleAttitude | None = None
        self._launch_attitude_sample_direction_eci: list[float] | None = None
        self._launch_attitude_sample_rcs_used_kg = 0.0
        self._launch_attitude_sample_rcs_applied_kg = 0.0
        stage_count = len(self.stage_specs)
        staging = f" · {stage_count} stadi" if stage_count > 1 else ""
        self.model_name = (f"{self.vehicle_model['name']}{staging} · ECI · J2 · RK4 · "
                           "quaternion attitude · TVC/RCS · Sutton–Graves heating")

    def _activate_stage(self) -> None:
        if self.science:
            self.science.spool = 0.
            self.science.nozzle = dict(ideal_thrust_N=0.,exhaust_mass_flow_kg_s=0.,
                                      flow_regime='STAGE_IGNITION_PENDING',
                                      chamber_pressure_Pa=0.,mass_continuity_relative_residual=0.)
            self.science.mass_flow_kg_s = 0.
        if self.active_stage_index >= len(self.stage_specs):
            self.max_thrust_N = 0.0
            self.nozzle_exit_area_m2 = 0.0
            self.isp_s = 0.0
            return
        stage = self.stage_specs[self.active_stage_index]
        self.max_thrust_N = stage["thrust_vacuum_N"]
        self.nozzle_exit_area_m2 = stage["nozzle_exit_area_m2"]
        self.isp_s = stage["isp_vacuum_s"]

    def _update_launch_vehicle_geometry(self) -> None:
        if not self.custom_design or self.launch_vehicle_attitude is None:
            return
        remaining = self.stage_specs[self.active_stage_index:]
        body_length_m = (self.launch_vehicle["capsule_section_length_m"] +
                         sum(stage["reference_length_m"] for stage in remaining))
        body_radius_m = max([
            self.launch_vehicle["capsule_reference_radius_m"],
            *(stage["reference_radius_m"] for stage in remaining)])
        self.launch_vehicle["body_length_m"] = body_length_m
        self.launch_vehicle["body_radius_m"] = body_radius_m
        self.launch_vehicle_attitude.update_geometry(body_length_m, body_radius_m)

    def _separate_spent_stage(self, event_time_s: float) -> None:
        stage = self.stage_specs[self.active_stage_index]
        if self.custom_design:
            jettisoned = stage["dry_mass_kg"]
            self.mass_dry_kg = max(0.0, self.mass_dry_kg-jettisoned)
            self.mass_kg = (self.mass_dry_kg+self.propellant_kg+
                            self.acs_propellant_kg)
            event_name = "STAGE_SEPARATION"
        else:
            jettisoned = 0.0
            event_name = "ENGINE_CUTOFF"
        self.stage_events.append({"event": event_name,
                                  "stage": self.active_stage_index+1,
                                  "time_s": event_time_s,
                                  "jettisoned_mass_kg": jettisoned,
                                  "jettisoned_propellant_kg": 0.0})
        self.active_stage_index += 1
        self._activate_stage()
        self._update_launch_vehicle_geometry()
        if self.active_stage_index >= len(self.stage_specs):
            self.command["throttle_pct"] = 0.0
            if self.phase == "ASCENT" and self.scenario == "mission":
                self.phase = "COAST"
                self.phase_time_s = 0.0
            elif self.phase == "ASCENT" and self.scenario == "leo-return":
                self.phase = "ABORTED"
                self.fault = "LEO_INSERTION_RESERVE_UNAVAILABLE"

    def _reset_orbit(self) -> None:
        altitude = 420_000.0
        radius = EARTH_RADIUS + altitude
        speed = math.sqrt(MU_EARTH / radius)
        anomaly = -0.55
        self.orbit = [radius * math.cos(anomaly), radius * math.sin(anomaly), 0.0,
                      -speed * math.sin(anomaly), speed * math.cos(anomaly), 0.0]
        target_anomaly = anomaly + 1_000.0 / radius
        self.target_orbit = [radius * math.cos(target_anomaly), radius * math.sin(target_anomaly), 0.0,
                             -speed * math.sin(target_anomaly), speed * math.cos(target_anomaly), 0.0]
        self.mass_dry_kg = 400.0
        self.propellant_capacity_kg = 80.0
        self.propellant_kg = 65.6
        self.mass_kg = self.mass_dry_kg + self.propellant_kg
        self.spacecraft_attitude = SpacecraftAttitude()
        self.space_navigation = None
        self.spacecraft_attitude.initialize(
            self.orbit[:3], self.orbit[3:], self.command["attitude_target_deg"])
        # A freshly inserted spacecraft is inertially at rest in attitude.
        # Tracking the local vertical is an explicit SAS choice, never the
        # unannounced default body rate of manual flight.
        self.spacecraft_attitude.body_rates_rad_s = [0.0, 0.0, 0.0]
        self.spacecraft_attitude.inertial_hold_quaternion = (
            self.spacecraft_attitude.quaternion_body_to_eci[:])
        self.stage_specs = []
        self.stage_propellant_kg = []
        self.active_stage_index = 0
        self.stage_events = []
        self.max_thrust_N = 24.0
        self.isp_s = 220.0
        self.rendezvous_target_rtn_m = [0.0, -20.0, 0.0]
        self.rendezvous_acceleration_eci_m_s2 = [0.0, 0.0, 0.0]
        self.relative_navigation = RelativeNavigationKF()
        initial_position_rtn, initial_velocity_rtn, _ = self._relative_rtn_state()
        self.relative_navigation.reset(initial_position_rtn, initial_velocity_rtn)
        self.rendezvous_guidance_state = {
            "controller": "Clohessy-Wiltshire PD · relative Kalman estimate",
            "control_state_source": "RELATIVE_KALMAN_ESTIMATE",
            "target_offset_rtn_m": list(self.rendezvous_target_rtn_m),
            "position_gain_s2": 2.0e-4,
            "velocity_gain_s": 3.0e-2,
            "maximum_acceleration_m_s2": 0.04,
            "actuator": "24 N · monopropellant RCS · Isp 220 s",
        }
        self.mission_metrics["rendezvous_target_offset_rtn_m"] = list(self.rendezvous_target_rtn_m)
        self.mission_metrics["rendezvous_hold_error_m"] = None
        self.model_name = "LEO · ECI/J₂ · RK4 · CW-PD · RCS · quaternion 6-DOF · reaction wheels"
        self.launch_vehicle = {"Cd": 0.0, "area_m2": 0.0,
                               "aeroshell_Cd": 0.0, "aeroshell_area_m2": 0.0,
                               "drogue_Cd": 0.0, "drogue_area_m2": 0.0,
                               "parachute_Cd": 0.0, "parachute_area_m2": 0.0}

    def _reset_aircraft(self) -> None:
        self.mass_dry_kg = self.vehicle_model["dry_kg"]
        self.propellant_capacity_kg = self.vehicle_model["fuel_kg"]
        self.propellant_kg = self.vehicle_model["fuel_start_kg"]
        self.mass_kg = self.mass_dry_kg + self.propellant_kg
        self.max_thrust_N = self.vehicle_model["thrust_N"]
        self.isp_s = 0.0
        self.aircraft_powertrain = dict(self.vehicle_model["propulsion"])
        self.aircraft_powertrain["total_disk_area_m2"] = (
            self.aircraft_powertrain["propeller_count"] * math.pi *
            self.aircraft_powertrain["propeller_radius_m"]**2)
        self.aero = dict(self.vehicle_model["aero"])
        # North, east, down; body u, v, w; Euler phi, theta, psi; body p, q, r.
        self.flight = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0,
                       self.mass_kg, self.propellant_kg]
        self.aircraft_airborne = False
        self.manual_takeoff_assist_engaged = False
        self.vertical_nav = VerticalNavigationKF()
        self.horizontal_nav = HorizontalNavigationKF()
        self.model_name = (f"{self.vehicle_model['name']} · 6-DOF · COESA76 · RK4 · "
                           "actuator-disk propeller · engine spool · rate-limited servos")

    def _reset_drone(self) -> None:
        self.mass_dry_kg = 0.6 * self.vehicle_model["mass_kg"]
        self.propellant_capacity_kg = 100.0
        self.battery_capacity_Wh = self.vehicle_model["battery_capacity_Wh"]
        self.battery_energy_Wh = (self.battery_capacity_Wh *
                                  self.vehicle_model["battery_start_pct"] / 100.0)
        self.battery_power_W = 0.0
        self.propellant_kg = 100.0*self.battery_energy_Wh/self.battery_capacity_Wh
        self.mass_kg = self.vehicle_model["mass_kg"]
        self.max_thrust_N = self.vehicle_model["thrust_N"]
        self.isp_s = 0.0
        self.drone = {"Ixx_kgm2": self.vehicle_model["Ixx_kgm2"],
                      "Iyy_kgm2": self.vehicle_model["Iyy_kgm2"],
                      "Izz_kgm2": self.vehicle_model["Izz_kgm2"],
                      "arm_m": self.vehicle_model["arm_m"],
                      "rotors": self.vehicle_model["rotors"],
                      "rotor_radius_m": self.vehicle_model["rotor_radius_m"],
                      "max_thrust_N": self.max_thrust_N,
                      "reference_mass_kg": self.mass_kg,
                      "total_disk_area_m2": (self.vehicle_model["rotors"] *
                                             math.pi * self.vehicle_model["rotor_radius_m"]**2),
                      "battery_capacity_Wh": self.battery_capacity_Wh,
                      "figure_of_merit": self.vehicle_model["figure_of_merit"],
                      "motor_efficiency": self.vehicle_model["motor_efficiency"],
                      "profile_power_max_W": self.vehicle_model["profile_power_max_W"],
                      "avionics_power_W": self.vehicle_model["avionics_power_W"],
                      "body_drag_area_m2": self.vehicle_model["body_drag_area_m2"],
                      "airframe_propulsive_efficiency": self.vehicle_model["airframe_propulsive_efficiency"],
                      "yaw_moment_coefficient_m": self.vehicle_model[
                          "yaw_moment_coefficient_m"],
                      "rotor_max_tip_speed_m_s": self.vehicle_model[
                          "rotor_max_tip_speed_m_s"],
                      "max_rotor_speed_rad_s": (
                          self.vehicle_model["rotor_max_tip_speed_m_s"] /
                          self.vehicle_model["rotor_radius_m"]),
                      "motor_time_constant_up_s": self.vehicle_model[
                          "motor_time_constant_up_s"],
                      "motor_time_constant_down_s": self.vehicle_model[
                          "motor_time_constant_down_s"]}
        self.drone["max_rotor_thrust_N"] = self.max_thrust_N/self.drone["rotors"]
        self.rotor_geometry = rotor_geometry(
            self.drone["rotors"], self.drone["arm_m"],
            self.drone["yaw_moment_coefficient_m"])
        self.rotor_mixer = rotor_mixer(self.rotor_geometry)
        self.mission_metrics["battery_energy_used_Wh"] = 0.0
        self.mission_metrics["max_horizontal_hold_error_m"] = 0.0
        self.drone_airborne = False
        self.command.update(throttle_pct=0.0)
        self.flight = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       *([0.0] * self.drone["rotors"]),
                       *([0.0] * self.drone["rotors"]),
                       0.0,
                       self.mass_kg, self.propellant_kg]
        self.vertical_nav = VerticalNavigationKF()
        self.horizontal_nav = HorizontalNavigationKF()
        self.model_name = (f"{self.vehicle_model['name']} · 6-DOF · {self.drone['rotors']} "
                           "first-order motor actuators · rotor mixer · COESA76 · RK4")

    def launch(self) -> dict[str, Any]:
        """Begin the selected launch/takeoff mission from its ground state."""
        if self.scenario == "orbital":
            return self.state()
        if self.scenario == 'planetary':
            self.mission_started = True
            self.phase = 'POWERED_DESCENT'
            self.launch_t = self.t
            return self.state()
        if not self.mission_started and self.phase == "READY":
            self.mission_started = True
            self.launch_t = self.t
            self.phase = "ASCENT" if self.vehicle == "space" else "TAKEOFF"
            if self.vehicle == "space":
                self.command.update(throttle_pct=100.0, pitch_deg=90.0)
        return self.state()

    def inject_fault(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Inject one deterministic propulsion or navigation-sensor fault."""
        if self.injected_faults:
            raise ValueError("clear the active injected fault before adding another")
        fault_type = str(payload.get("type", ""))
        if fault_type in {"barometer_dropout", "gnss_dropout"}:
            supported_sensor_fault = self.vehicle in {"aircraft", "drone"}
            supported_sensor_fault |= (
                fault_type == "gnss_dropout" and self.vehicle == "space" and
                self.scenario != "orbital")
            if not supported_sensor_fault:
                raise ValueError(
                    "barometer dropout requires an aircraft or drone; GNSS dropout "
                    "requires an aircraft, drone, or launch spacecraft")
            severity = None
            rotor_index = None
        elif self.vehicle in {"space", "aircraft"}:
            if fault_type != "engine_thrust_loss":
                raise ValueError("type must be engine_thrust_loss for this vehicle")
            if self.vehicle == "space" and self.scenario == "orbital":
                raise ValueError("main-engine thrust loss is unavailable in the orbital RCS scenario")
            severity = self._fault_severity(payload, maximum=0.95)
            rotor_index = None
        else:
            if fault_type != "rotor_thrust_loss":
                raise ValueError("type must be rotor_thrust_loss for this vehicle")
            severity = self._fault_severity(payload, maximum=1.0)
            raw_index = payload.get("rotor_index")
            if isinstance(raw_index, bool) or not isinstance(raw_index, int):
                raise ValueError("rotor_index must be an integer from zero to rotor_count - 1")
            if not 0 <= raw_index < self.drone["rotors"]:
                raise ValueError("rotor_index is outside the selected drone's rotor count")
            rotor_index = raw_index
        fault_id = f"F{self.next_fault_id:03d}"
        self.next_fault_id += 1
        fault = {"id": fault_id, "type": fault_type,
                 "severity_fraction": severity, "rotor_index": rotor_index,
                 "injected_at_s": self.t, "detected": False,
                 "detection_time_s": None, "last_residual_fraction": 0.0,
                 "last_monitor_time_s": None}
        self.injected_faults.append(fault)
        self.fdir_events.append({"time_s": self.t, "event": "FAULT_INJECTED",
                                 "fault_id": fault_id, "type": fault_type,
                                 "severity_fraction": severity,
                                 "rotor_index": rotor_index})
        return self.state()

    @staticmethod
    def _fault_severity(payload: dict[str, Any], *, maximum: float) -> float:
        severity = payload.get("severity_fraction", 0.3)
        if (isinstance(severity, bool) or not isinstance(severity, (int, float))
                or not math.isfinite(severity) or not 0.05 <= severity <= maximum):
            raise ValueError(f"severity_fraction must be between 0.05 and {maximum:g}")
        return float(severity)

    def clear_faults(self) -> dict[str, Any]:
        """Remove injected effects while retaining the FDIR event history."""
        cleared_sensor_fault = False
        for fault in self.injected_faults:
            event = ("SENSOR_FAULT_CLEARED" if fault["type"] in {
                "barometer_dropout", "gnss_dropout"} else "FAULT_CLEARED")
            cleared_sensor_fault |= event == "SENSOR_FAULT_CLEARED"
            self.fdir_events.append({"time_s": self.t, "event": event,
                                     "fault_id": fault["id"], "type": fault["type"]})
        self.injected_faults.clear()
        if (cleared_sensor_fault and
                self.fdir_recovery_mode == "ADVISORY_SENSOR_DEGRADED"):
            self.fdir_recovery_mode = "NOMINAL"
        return self.state()

    def _engine_availability(self) -> float:
        return math.prod(1.0-fault["severity_fraction"]
                         for fault in self.injected_faults
                         if fault["type"] == "engine_thrust_loss")

    def _rotor_availability(self, index: int) -> float:
        return math.prod(1.0-fault["severity_fraction"]
                         for fault in self.injected_faults
                         if fault["type"] == "rotor_thrust_loss"
                         and fault["rotor_index"] == index)

    def _update_fdir(self, time_s: float) -> None:
        """Run deterministic propulsion and navigation-integrity monitors."""
        if not self.injected_faults or not self.mission_started:
            return
        for fault in self.injected_faults:
            if fault["type"] in {"barometer_dropout", "gnss_dropout"}:
                # Require two missed measurement epochs before declaring loss:
                # 5 Hz for atmospheric sensors, 1 Hz for launch-spacecraft GNSS.
                persistence_s = 0.4
                if fault["type"] == "barometer_dropout":
                    persistence_s = 0.2
                elif self.vehicle == "space":
                    persistence_s = 2.0
                fault["last_residual_fraction"] = 1.0
                fault["last_monitor_time_s"] = time_s
                if (time_s-fault["injected_at_s"] >= persistence_s-1e-9 and
                        not fault["detected"]):
                    fault["detected"] = True
                    fault["detection_time_s"] = round(time_s, 9)
                    self.fdir_recovery_mode = "ADVISORY_SENSOR_DEGRADED"
                    action = "CONTINUE_INS_PROPAGATION_AND_REPORT_GROWING_UNCERTAINTY"
                    response_event = None
                    if (fault["type"] == "gnss_dropout" and
                            self.vehicle == "drone" and
                            self.command["mode"] == "auto"):
                        if (not self.drone_airborne and self.phase == "TAKEOFF"):
                            self.phase = "ABORTED"
                            self.fault = "GNSS_LOSS_DURING_TAKEOFF"
                            self.command["throttle_pct"] = 0.0
                            self.fdir_recovery_mode = "AUTOMATIC_TAKEOFF_ABORT"
                            action = "ABORT_TAKEOFF_ON_GNSS_LOSS"
                            response_event = {
                                "time_s": time_s, "event": "TAKEOFF_ABORT",
                                "fault_id": fault["id"], "action": action,
                            }
                        elif (self.drone_airborne and self.phase not in {
                                "LANDED", "CRASHED", "ABORTED"}):
                            self.fdir_sensor_landing_position_ned_m = (
                                [self.horizontal_nav.x[axis][0] for axis in range(2)]
                                if self.horizontal_nav is not None else
                                list(self.flight[:2]))
                            self.guidance_target_ned_m = list(
                                self.fdir_sensor_landing_position_ned_m)
                            self.phase = "LANDING"
                            self.phase_time_s = 0.0
                            self.fdir_recovery_mode = "AUTOMATIC_SENSOR_LANDING"
                            action = "LAND_IN_PLACE_USING_INERTIAL_NAVIGATION"
                            response_event = {
                                "time_s": time_s,
                                "event": "SENSOR_FAILSAFE_LANDING_STARTED",
                                "fault_id": fault["id"], "action": action,
                                "target_position_ned_m": list(
                                    self.fdir_sensor_landing_position_ned_m),
                            }
                    self.fdir_events.append({
                        "time_s": time_s,
                        "event": "SENSOR_FAULT_DETECTED",
                        "fault_id": fault["id"],
                        "type": fault["type"],
                        "action": action,
                    })
                    if response_event is not None:
                        self.fdir_events.append(response_event)
                continue
            if fault["type"] == "engine_thrust_loss":
                if self.vehicle == "space":
                    excited = self.command["throttle_pct"] > 1.0
                    residual = 1.0-self._engine_availability()
                else:
                    propulsion = self._aircraft_propulsion_state(self.flight)
                    excited = propulsion["nominal_thrust_N"] > 10.0
                    residual = (1.0-propulsion["thrust_N"]/
                                max(propulsion["nominal_thrust_N"], 1e-12))
            else:
                propulsion = self._drone_propulsion_state(self.flight)
                index = fault["rotor_index"]
                expected = propulsion["fault_free_actual_thrusts_N"][index]
                actual = propulsion["actual_thrusts_N"][index]
                excited = expected > 0.25
                residual = 1.0-actual/max(expected, 1e-12)
            fault["last_residual_fraction"] = max(0.0, min(1.0, residual))
            fault["last_monitor_time_s"] = time_s
            # The monitor is evaluated on physics substeps, so decimal mission
            # times can land a few ulps below the 100 ms persistence boundary.
            # Keep the configured delay exact without adding a whole extra tick.
            delay_complete = (time_s-fault["injected_at_s"] >= 0.1-1e-9)
            if (excited and delay_complete and not fault["detected"] and
                    fault["last_residual_fraction"] >= 0.05):
                fault["detected"] = True
                # Mission time accumulates binary floating-point substeps;
                # report the monitor timestamp at nanosecond resolution so
                # 100 ms does not appear as 99.999999999 ms in telemetry.
                fault["detection_time_s"] = round(time_s, 9)
                action = ("THRUST_SHORTFALL_ADVISORY" if
                          fault["type"] == "engine_thrust_loss" else
                          "ROTOR_CHANNEL_ISOLATED_LAND_ADVISORY")
                response_event = None
                if (self.command["mode"] == "auto" and
                        self.vehicle == "aircraft" and not self.aircraft_airborne and
                        self.phase == "TAKEOFF"):
                    self.phase = "ABORTED"
                    self.fault = "TAKEOFF_ENGINE_FAILURE"
                    self.command.update(throttle_pct=0.0, brakes_pct=100.0)
                    self.fdir_recovery_mode = "AUTOMATIC_TAKEOFF_ABORT"
                    action = "TAKEOFF_ABORT_AND_BRAKES"
                    response_event = {
                        "time_s": time_s, "event": "TAKEOFF_ABORT",
                        "fault_id": fault["id"], "action": action,
                    }
                elif (self.command["mode"] == "auto" and
                      self.vehicle == "drone" and not self.drone_airborne and
                      self.phase == "TAKEOFF"):
                    self.phase = "ABORTED"
                    self.fault = "TAKEOFF_ROTOR_FAILURE"
                    self.command["throttle_pct"] = 0.0
                    self.fdir_recovery_mode = "AUTOMATIC_TAKEOFF_ABORT"
                    action = "TAKEOFF_ABORT_AND_MOTOR_CUTOFF"
                    response_event = {
                        "time_s": time_s, "event": "TAKEOFF_ABORT",
                        "fault_id": fault["id"], "action": action,
                    }
                elif (self.command["mode"] == "auto" and
                      self.vehicle == "drone" and self.drone_airborne):
                    health = [self._rotor_availability(index)
                              for index in range(self.drone["rotors"])]
                    available_thrust = (sum(health) *
                                        self.drone["max_rotor_thrust_N"])
                    thrust_margin = available_thrust / max(self.mass_kg*G0, 1e-12)
                    try:
                        recovery_mixer = rotor_mixer_with_health(
                            self.rotor_geometry, health)
                    except ValueError:
                        recovery_mixer = None
                    tested_severity_limit = (0.30 if self.drone["rotors"] == 4
                                              else 0.80)
                    within_recovery_envelope = (
                        fault["severity_fraction"] <= tested_severity_limit)
                    if (recovery_mixer is not None and thrust_margin >= 1.25
                            and within_recovery_envelope):
                        self.rotor_fault_mixer = recovery_mixer
                        self.fdir_recovery_mode = "AUTOMATIC_RETURN_LAND"
                        if self.phase != "LANDING":
                            self.phase = "RETURN"
                            self.phase_time_s = 0.0
                        action = "RECONFIGURE_MIXER_AND_RETURN_TO_PAD"
                        response_event = {
                            "time_s": time_s, "event": "AUTOMATIC_RETURN_LAND",
                            "fault_id": fault["id"], "action": action,
                            "available_thrust_margin": thrust_margin,
                            "active_rotor_count": sum(value > 0.0 for value in health),
                        }
                    else:
                        self.fdir_recovery_mode = (
                            "ADVISORY_ONLY_OUTSIDE_RECOVERY_ENVELOPE")
                        if recovery_mixer is None:
                            self.fdir_recovery_mode = (
                                "ADVISORY_ONLY_UNCONTROLLABLE_ROTOR_SET")
                        elif thrust_margin < 1.25:
                            self.fdir_recovery_mode = (
                                "ADVISORY_ONLY_INSUFFICIENT_THRUST_MARGIN")
                        action = "AUTOMATIC_RECOVERY_NOT_AUTHORIZED_OUTSIDE_ENVELOPE"
                elif (self.command["mode"] == "auto" and
                      self.vehicle == "aircraft" and self.aircraft_airborne and
                      self.phase not in {"LANDED", "CRASHED", "ABORTED"}):
                    north_east_velocity = (
                        [self.horizontal_nav.x[axis][1] for axis in range(2)]
                        if self.horizontal_nav is not None else
                        self._ned_velocity(self.flight)[:2])
                    horizontal_speed = math.hypot(*north_east_velocity)
                    self.fdir_landing_track_deg = (
                        math.degrees(math.atan2(north_east_velocity[1],
                                                north_east_velocity[0]))
                        if horizontal_speed > 1.0 else
                        math.degrees(self.flight[8]))
                    altitude_m = max(0.0, -self.flight[2])
                    if self.phase == "ROLLOUT":
                        self.command.update(throttle_pct=0.0, brakes_pct=100.0)
                    elif self.phase not in {"LANDING", "APPROACH"}:
                        self.phase = ("APPROACH" if altitude_m <= 120.0 else
                                      "EMERGENCY_GLIDE")
                        self.phase_time_s = 0.0
                    self.fdir_recovery_mode = "AUTOMATIC_FORCED_LANDING"
                    action = "BEST_GLIDE_AND_FORCED_LANDING"
                    response_event = {
                        "time_s": time_s, "event": "AUTOMATIC_FORCED_LANDING",
                        "fault_id": fault["id"], "action": action,
                        "altitude_m": altitude_m,
                        "target_track_deg": self.fdir_landing_track_deg,
                    }
                if (self.vehicle == "space" and self.scenario != "orbital" and
                        self.phase == "ASCENT" and
                        _norm3(self.orbit[:3])-EARTH_RADIUS <= 1.51):
                    altitude_m = _norm3(self.orbit[:3])-EARTH_RADIUS
                    thrust_N = (self.command["throttle_pct"]/100.0 *
                                self._thrust_at_altitude(altitude_m) *
                                self._engine_availability())
                    local_gravity_m_s2 = _norm3(
                        self._gravity_eci_acceleration(self.orbit[:3]))
                    thrust_to_weight = thrust_N/max(
                        self.mass_kg*local_gravity_m_s2, 1e-12)
                    if thrust_to_weight <= 1.0:
                        self.phase = "ABORTED"
                        self.fault = "LIFTOFF_THRUST_MARGIN_UNAVAILABLE"
                        self.command["throttle_pct"] = 0.0
                        self.fdir_recovery_mode = "AUTOMATIC_TAKEOFF_ABORT"
                        action = "THROTTLE_CUTOFF_AND_LAUNCH_INHIBIT"
                        response_event = {
                            "time_s": time_s, "event": "GROUND_HOLD_ABORT",
                            "fault_id": fault["id"],
                            "thrust_to_weight": thrust_to_weight,
                            "action": action,
                        }
                self.fdir_events.append({
                    "time_s": time_s, "event": "FAULT_DETECTED_AND_ISOLATED",
                    "fault_id": fault["id"], "type": fault["type"],
                    "residual_fraction": fault["last_residual_fraction"],
                    "action": action,
                })
                if response_event is not None:
                    self.fdir_events.append(response_event)

    def _fault_management_state(self) -> dict[str, Any]:
        detected = any(fault["detected"] for fault in self.injected_faults)
        automatic_ground_abort = self.fdir_recovery_mode == "AUTOMATIC_TAKEOFF_ABORT"
        automatic_return = self.fdir_recovery_mode in {
            "AUTOMATIC_RETURN_LAND", "RECOVERY_LANDED", "RECOVERY_FAILED_IMPACT",
            "AUTOMATIC_FORCED_LANDING", "FORCED_LANDING_COMPLETED",
            "FORCED_LANDING_FAILED", "AUTOMATIC_SENSOR_LANDING",
            "SENSOR_FAILSAFE_LANDED", "SENSOR_FAILSAFE_FAILED"}
        return {"monitor": "PROPULSION_RESIDUAL_AND_NAVIGATION_INTEGRITY",
                "mode": "AUTOMATIC_ABORT" if automatic_ground_abort else
                        "AUTOMATIC_RECOVERY" if automatic_return else
                        "DETECTED_ADVISORY" if detected else
                        "INJECTED_UNDETECTED" if self.injected_faults else "NOMINAL",
                "threshold_fraction": 0.05,
                "active_faults": copy.deepcopy(self.injected_faults),
                "events": copy.deepcopy(self.fdir_events[-100:]),
                "automatic_recovery_eligibility": {
                    "minimum_available_thrust_margin": 1.25,
                    "maximum_rotor_thrust_loss_fraction_by_rotor_count": {
                        "4": 0.30, "6": 0.80,
                    },
                },
                "automatic_aircraft_response": (
                    "BEST_GLIDE_AND_FORCED_LANDING_IN_AUTO_MODE_ON_REFERENCE_SURFACE"),
                "recovery_automation": self.fdir_recovery_mode}

    def stage(self) -> dict[str, Any]:
        """Manually jettison the active custom stage and its remaining propellant."""
        if self.vehicle != "space" or not self.custom_design:
            raise ValueError("manual staging is available only for a custom spacecraft stack")
        if not self.mission_started or self.phase != "ASCENT":
            raise ValueError("manual staging is available only during powered ascent")
        if self.active_stage_index >= len(self.stage_specs)-1:
            raise ValueError("no upper stage remains to ignite")

        index = self.active_stage_index
        stage = self.stage_specs[index]
        residual_propellant = self.stage_propellant_kg[index]
        jettisoned_mass = stage["dry_mass_kg"]+residual_propellant
        self.command["throttle_pct"] = 0.0
        self.stage_propellant_kg[index] = 0.0
        self.propellant_kg = sum(self.stage_propellant_kg)
        self.mass_dry_kg = max(0.0, self.mass_dry_kg-stage["dry_mass_kg"])
        self.mass_kg = (self.mass_dry_kg+self.propellant_kg+
                        self.acs_propellant_kg)
        self.stage_events.append({"event": "STAGE_JETTISON", "stage": index+1,
                                  "time_s": self.t,
                                  "jettisoned_mass_kg": jettisoned_mass,
                                  "jettisoned_propellant_kg": residual_propellant})
        self.active_stage_index += 1
        self._activate_stage()
        self._update_launch_vehicle_geometry()
        return self.state()

    def set_command(self, payload: dict[str, Any], _radio_delivery: bool = False,
                    _command_time_s: float | None = None) -> dict[str, Any]:
        payload = self._validated_sas_command(payload)
        if (self.science and self.science.config['radio_commands'] and
                str(payload.get('mode',self.command['mode'])).lower() == 'python'
                and not _radio_delivery):
            # Validate command shape/ranges on a copy before queueing any effect.
            for key in ('throttle_pct','roll_deg','pitch_deg','yaw_deg','brakes_pct'):
                if key in payload and not math.isfinite(float(payload[key])):
                    raise ValueError(f'{key} must be finite')
            if 'attitude_target_deg' in payload:
                target=payload['attitude_target_deg']
                if (not isinstance(target,(list,tuple)) or len(target)!=3 or
                    any(isinstance(v,bool) or not isinstance(v,(int,float)) or
                        not math.isfinite(v) for v in target)):
                    raise ValueError('attitude_target_deg must contain three finite angles')
            queued = self.science.radio.send(payload, self.t)
            result = self.state()
            result['radio_command_receipt'] = dict(sequence=self.science.radio.sequence,
                queued=queued,queued_packets=len(self.science.radio.queue),
                dropped_packets=self.science.radio.dropped)
            return result
        for name, low, high in (("throttle_pct", 0.0, 100.0),
                                ("roll_deg", -60.0, 60.0),
                                ("pitch_deg", -45.0, 45.0),
                                ("yaw_deg", -180.0, 180.0),
                                ("brakes_pct", 0.0, 100.0)):
            if name in payload:
                value = float(payload[name])
                if not math.isfinite(value):
                    raise ValueError(f"{name} must be finite")
                self.command[name] = _clamp(value, low, high)
        if "attitude_target_deg" in payload:
            target = payload["attitude_target_deg"]
            if (not isinstance(target, (list, tuple)) or len(target) != 3 or
                    any(isinstance(value, bool) or not isinstance(value, (int, float)) or
                        not math.isfinite(value) for value in target)):
                raise ValueError("attitude_target_deg must contain three finite Euler angles in degrees")
            self.command["attitude_target_deg"] = [
                _clamp(float(value), -180.0, 180.0) for value in target]
        if "attitude_torque_body_fraction" in payload:
            torque = payload["attitude_torque_body_fraction"]
            if (not isinstance(torque, (list, tuple)) or len(torque) != 3 or
                    any(isinstance(value, bool) or not isinstance(value, (int, float)) or
                        not math.isfinite(value) or abs(value) > 1.0 for value in torque)):
                raise ValueError("attitude_torque_body_fraction must contain three finite values in [-1, 1]")
            self.command["attitude_torque_body_fraction"] = [float(value) for value in torque]
        if "maneuver_direction_eci" in payload:
            direction = payload["maneuver_direction_eci"]
            if direction is None:
                self.command["maneuver_direction_eci"] = None
            elif (not isinstance(direction, (list, tuple)) or len(direction) != 3 or
                    any(isinstance(value, bool) or not isinstance(value, (int, float)) or
                        not math.isfinite(value) for value in direction) or
                    _norm3([float(value) for value in direction]) < 1e-9):
                raise ValueError("maneuver_direction_eci must be a nonzero finite 3-vector")
            else:
                self.command["maneuver_direction_eci"] = [float(value) for value in direction]
        if "attitude_sas_mode" in payload:
            sas_mode = str(payload["attitude_sas_mode"]).lower()
            if sas_mode not in {"manual", "stability_assist", "prograde", "retrograde",
                                "radial_in", "radial_out", "normal", "anti_normal",
                                "target", "anti_target", "maneuver_node", "lvlh"}:
                raise ValueError("Unknown attitude_sas_mode")
            if sas_mode == "maneuver_node" and self.command.get("maneuver_direction_eci") is None:
                raise ValueError("Define maneuver_direction_eci before selecting maneuver-node SAS")
            self.command["attitude_sas_mode"] = sas_mode
        if "sas_enabled" in payload:
            was_enabled = self.command.get("sas_enabled", False)
            self.command["sas_enabled"] = payload["sas_enabled"]
            if (payload["sas_enabled"] and not was_enabled and
                    self.spacecraft_attitude is not None):
                # Enabling hold captures this instant, including while paused.
                self.spacecraft_attitude.inertial_hold_quaternion = (
                    self.spacecraft_attitude.quaternion_body_to_eci[:])
        if "mode" in payload:
            mode = str(payload["mode"]).lower()
            if mode not in {"auto", "manual", "python"}:
                raise ValueError("mode must be auto, manual or python")
            previous_mode = self.command["mode"]
            self.command["mode"] = mode
            if mode == "auto":
                self.command["sas_enabled"] = False
            if self.vehicle == "space" and self.scenario == "orbital" and "attitude_sas_mode" not in payload and "sas_enabled" not in payload:
                if mode == "auto":
                    self.command["attitude_sas_mode"] = "lvlh"
                elif mode == "manual" and previous_mode != "manual":
                    self.command["attitude_sas_mode"] = "manual"
                    self.command["sas_enabled"] = False
                elif mode == "python" and "attitude_target_deg" in payload:
                    # Preserve the legacy Python target-angle API as an explicit
                    # LVLH target; new clients should prefer SAS or torque input.
                    self.command["attitude_sas_mode"] = "lvlh"
                    self.command["sas_enabled"] = True
            if (mode != previous_mode and "attitude_torque_body_fraction" not in payload and
                    self.scenario == "orbital"):
                self.command["attitude_torque_body_fraction"] = [0.0, 0.0, 0.0]
        if self.command["mode"] == "python":
            # Any successful Python API command, including an empty command
            # used as a heartbeat, refreshes the simulation-time watchdog.
            self.external_control["state"] = "CONNECTED"
            self.external_control["last_command_time_s"] = self.t if _command_time_s is None else _command_time_s
        else:
            self.external_control["last_command_time_s"] = None
            if self.external_control["state"] == "CONNECTED":
                self.external_control["state"] = "DISARMED"
            elif (self.command["mode"] == "manual" and
                  self.external_control["state"] in {
                      "AUTO_TAKEOVER", "AUTO_RETURN", "FORCED_LANDING",
                      "ROLLOUT_STOP"}):
                self.external_control["state"] = "MANUAL_OVERRIDE"
            elif (self.command["mode"] == "auto" and
                  self.external_control["state"] == "MANUAL_OVERRIDE"):
                self.external_control["state"] = "DISARMED"
        if self.vehicle != "space" or self.scenario != "orbital":
            if self.command.get("sas_enabled") and self.command["mode"] != "auto":
                keys = ("roll_deg", "pitch_deg", "yaw_deg")
                engaging = payload.get("sas_enabled", False) or payload.get("attitude_sas_mode") == "stability_assist"
                override = payload.get("sas_manual_input", any(key in payload for key in keys))
                previous = getattr(self, "_local_sas_override", False)
                if engaging or not hasattr(self, "_local_sas_hold"):
                    self._local_sas_hold = {key: self.command[key] for key in keys}
                    override = False
                elif override:
                    self._local_sas_hold = {key: self.command[key] for key in keys}
                elif previous:
                    # The last pilot reference is retained at release. Existing
                    # bounded actuators continue integrating physical attitude.
                    pass
                if not override:
                    self.command.update(self._local_sas_hold)
                self._local_sas_override = bool(override)
            else:
                self._local_sas_override = False
                if hasattr(self, "_local_sas_hold"):del self._local_sas_hold
        return self.state()

    def _validated_sas_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate the new command surface before mutating any flight command.

        Legacy ``attitude_sas_mode`` remains valid. An explicit enable enters
        pilot authority with an inertial hold; GNC retains its own LVLH mode.
        """
        command = dict(payload)
        named = "attitude_sas_mode" in command
        toggled = "sas_enabled" in command
        if toggled and not isinstance(command["sas_enabled"], bool):
            raise ValueError("sas_enabled must be boolean")
        if "sas_manual_input" in command and not isinstance(command["sas_manual_input"], bool):
            raise ValueError("sas_manual_input must be boolean")
        if (self.vehicle != "space" or self.scenario != "orbital") and named:
            local_modes={"manual", "stability_assist"}
            if self.vehicle == "space" and getattr(self, "launch_vehicle_attitude", None) is not None:
                local_modes.update(self._launch_sas_vectors())
                if command.get("maneuver_direction_eci") is not None:local_modes.add("maneuver_node")
            if command["attitude_sas_mode"] not in local_modes:
                raise ValueError("SAS direction unavailable for this vehicle/state")
        direction = command.get("maneuver_direction_eci", self.command.get("maneuver_direction_eci"))
        if "maneuver_direction_eci" in command and direction is not None:
            if (not isinstance(direction, (list, tuple)) or len(direction) != 3 or
                    any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                        not math.isfinite(v) for v in direction) or
                    _norm3(direction) < 1e-9):
                raise ValueError("maneuver_direction_eci must be a nonzero finite 3-vector")
        if named:
            mode = str(command["attitude_sas_mode"]).lower()
            allowed = {"manual", "stability_assist", "prograde", "retrograde",
                       "normal", "anti_normal", "radial_in", "radial_out",
                       "target", "anti_target", "maneuver_node", "lvlh"}
            if mode not in allowed:
                raise ValueError("Unknown attitude_sas_mode")
            if mode == "maneuver_node" and direction is None:
                raise ValueError("Define maneuver_direction_eci before selecting maneuver-node SAS")
            if mode in {"target", "anti_target"}:
                target = getattr(self, "target_orbit", None)
                if (self.vehicle != "space" or
                        not target or _norm3([target[i]-self.orbit[i] for i in range(3)]) < 1e-6):
                    raise ValueError("Target SAS requires a distinct orbital target")
            command["attitude_sas_mode"] = mode
            command.setdefault("sas_enabled", mode != "manual")
        elif toggled and command["sas_enabled"]:
            command["attitude_sas_mode"] = "stability_assist"
        elif ("maneuver_direction_eci" in command and direction is None and
              self.command.get("attitude_sas_mode") == "maneuver_node"):
            # Removing a node disengages its target safely, without a step-time
            # exception or silently continuing to point at a deleted vector.
            command["attitude_sas_mode"] = "stability_assist"
        if toggled and command["sas_enabled"]:
            command.setdefault("mode", "manual")
            if command["mode"] == "auto":
                raise ValueError("SAS and autonomous GNC cannot own attitude simultaneously")
        elif toggled:
            command.setdefault("mode", "manual")
        return command

    def _effective_sas_mode(self) -> str:
        if self.command["mode"] == "auto":
            return "lvlh"
        selected = self.command["attitude_sas_mode"]
        if not self.command.get("sas_enabled", selected != "manual"):
            return "manual"
        if selected in {"target", "anti_target"}:
            target = getattr(self, "target_orbit", None)
            if not target or _norm3([target[i]-self.orbit[i] for i in range(3)]) < 1e-6:
                return "stability_assist"
        if selected == "maneuver_node" and self.command.get("maneuver_direction_eci") is None:
            return "stability_assist"
        return selected

    def _launch_sas_vectors(self):
        """Physical ECI references; launch nose is +Z, orbital nose is +X."""
        position, velocity = self.orbit[:3], self.orbit[3:]
        radius=_norm3(position)
        radial=[v/max(radius,1e-20) for v in position]
        angular=_cross(position,velocity);length=_norm3(angular)
        normal=[v/max(length,1e-20) for v in angular]
        vectors={"radial_out":radial,"radial_in":[-v for v in radial]}
        if length>1e-6:vectors.update(normal=normal,anti_normal=[-v for v in normal])
        # Surface-relative velocity avoids aiming sideways with Earth's rotation on pad.
        relative=[velocity[0]+OMEGA_EARTH*position[1],velocity[1]-OMEGA_EARTH*position[0],velocity[2]]
        speed=_norm3(relative)
        if speed>1.:
            prograde=[v/speed for v in relative]
            vectors.update(prograde=prograde,retrograde=[-v for v in prograde])
        target=getattr(self,"target_orbit",None)
        if target:
            delta=[target[i]-position[i] for i in range(3)];distance=_norm3(delta)
            if distance>1.:
                vectors.update(target=[v/distance for v in delta],anti_target=[-v/distance for v in delta])
        node=self.command.get("maneuver_direction_eci")
        if node:vectors["maneuver_node"]=[v/_norm3(node) for v in node]
        return vectors

    def _sas_state(self) -> dict[str, Any]:
        supported = self.vehicle == "space" and self.scenario == "orbital"
        if not supported or self.spacecraft_attitude is None:
            enabled = bool(self.command.get("sas_enabled")) and self.command["mode"] != "auto"
            directions = self._launch_sas_vectors() if self.vehicle == "space" and getattr(self, "launch_vehicle_attitude", None) is not None else {}
            markers = {key: dict(direction_eci=value, direction_body=self.launch_vehicle_attitude.vector_eci_to_body(value), axis="z") for key,value in directions.items()}
            return dict(supported=True, enabled=enabled, mode=self.command.get("attitude_sas_mode", "stability_assist"),
                        available_modes=["stability_assist", *directions], markers=markers,
                        context="launch" if directions else "local",
                        manual_override=enabled and getattr(self, "_local_sas_override", False),
                        authority="gnc" if self.command["mode"] == "auto" else "pilot",
                        actuator="existing_vehicle_attitude_controller",
                        reference="LOCAL_ATTITUDE_SETPOINT_HOLD")
        attitude = self.spacecraft_attitude
        radial = [v/_norm3(self.orbit[:3]) for v in self.orbit[:3]]
        speed = _norm3(self.orbit[3:])
        velocity = [v/max(speed, 1e-20) for v in self.orbit[3:]]
        normal = _cross(self.orbit[:3], self.orbit[3:])
        normal = [v/max(_norm3(normal), 1e-20) for v in normal]
        vectors = {"prograde": velocity, "retrograde": [-v for v in velocity],
                   "normal": normal, "anti_normal": [-v for v in normal],
                   "radial_in": [-v for v in radial], "radial_out": radial}
        target = getattr(self, "target_orbit", None)
        if target:
            delta = [target[i]-self.orbit[i] for i in range(3)]
            length = _norm3(delta)
            if length > 1e-6:
                vectors["target"] = [v/length for v in delta]
                vectors["anti_target"] = [-v/length for v in delta]
        maneuver = self.command.get("maneuver_direction_eci")
        if maneuver is not None:
            vectors["maneuver_node"] = [v/_norm3(maneuver) for v in maneuver]
        markers = {mode: dict(direction_eci=vector,
                             direction_body=attitude.vector_eci_to_body(vector), axis="x")
                   for mode, vector in vectors.items()}
        enabled = self.command["mode"] != "auto" and self._effective_sas_mode() != "manual"
        override = (enabled and self._effective_sas_mode() != "lvlh" and
                    any(abs(v) > 1e-6 for v in self.command["attitude_torque_body_fraction"]))
        return dict(supported=True, enabled=enabled, mode=self.command["attitude_sas_mode"],
                    effective_mode=self._effective_sas_mode(), available_modes=["stability_assist", *vectors],
                    manual_override=override, authority="gnc" if self.command["mode"] == "auto" else "pilot",
                    markers=markers, actuator="reaction_wheels",
                    torque_limit_N_m=attitude.wheel_torque_limit_N_m[:],
                    momentum_limit_N_m_s=attitude.wheel_momentum_limit_N_m_s[:],
                    wheel_saturated=attitude.wheel_saturated[:],
                    propellant_used_for_attitude=False)

    def _update_python_control_watchdog(self, time_s: float) -> None:
        """Return to a vehicle-specific autonomous response after link loss."""
        link = self.external_control
        last_command_time_s = link["last_command_time_s"]
        if (self.command["mode"] != "python" or last_command_time_s is None or
                not self.mission_started):
            return
        command_age_s = max(0.0, time_s-last_command_time_s)
        timeout_s = link["watchdog_timeout_s"]
        if command_age_s < timeout_s-1e-9:
            return

        phase_before = self.phase
        self.command["mode"] = "auto"
        if self.vehicle == "space" and self.scenario == "orbital":
            self.command["attitude_sas_mode"] = "lvlh"
            self.command["sas_enabled"] = False
        if self.vehicle == "space":
            link["state"] = "AUTO_TAKEOVER"
            action = "RESUME_AUTONOMOUS_MISSION_GUIDANCE"
        elif self.vehicle == "aircraft":
            if not self.aircraft_airborne and self.phase == "TAKEOFF":
                self.phase = "ABORTED"
                self.fault = "PYTHON_CONTROL_LINK_LOST_DURING_TAKEOFF"
                self.command.update(throttle_pct=0.0, brakes_pct=100.0)
                link["state"] = "TAKEOFF_ABORTED"
                action = "THROTTLE_CUTOFF_AND_BRAKES"
            elif not self.aircraft_airborne:
                link["state"] = "AUTO_TAKEOVER"
                action = "AUTONOMOUS_GROUND_HOLD"
            elif self.phase == "ROLLOUT":
                self.command.update(throttle_pct=0.0, brakes_pct=100.0)
                link["state"] = "ROLLOUT_STOP"
                action = "THROTTLE_CUTOFF_AND_MAXIMUM_BRAKING"
            else:
                velocity = ([self.horizontal_nav.x[axis][1]
                             for axis in range(2)]
                            if self.horizontal_nav is not None else
                            self._ned_velocity(self.flight)[:2])
                self.fdir_landing_track_deg = (
                    math.degrees(math.atan2(velocity[1], velocity[0]))
                    if math.hypot(*velocity) > 1.0 else
                    math.degrees(self.flight[8]))
                altitude_m = max(0.0, -self.flight[2])
                self.phase = ("APPROACH" if altitude_m <= 120.0 else
                              "EMERGENCY_GLIDE")
                self.phase_time_s = 0.0
                link["state"] = "FORCED_LANDING"
                action = "BEST_GLIDE_AND_FORCED_LANDING"
        elif not self.drone_airborne and self.phase == "TAKEOFF":
            self.phase = "ABORTED"
            self.fault = "PYTHON_CONTROL_LINK_LOST_DURING_TAKEOFF"
            self.command["throttle_pct"] = 0.0
            link["state"] = "TAKEOFF_ABORTED"
            action = "MOTOR_CUTOFF_AND_TAKEOFF_ABORT"
        elif not self.drone_airborne:
            self.command["throttle_pct"] = 0.0
            link["state"] = "AUTO_TAKEOVER"
            action = "MOTOR_CUTOFF_ON_GROUND"
        else:
            self.phase = "RETURN"
            self.phase_time_s = 0.0
            link["state"] = "AUTO_RETURN"
            action = "AUTONOMOUS_RETURN_TO_PAD"

        link["events"].append({
            "time_s": round(time_s, 9),
            "event": "PYTHON_CONTROL_LINK_LOST",
            "phase_before": phase_before,
            "phase_after": self.phase,
            "command_age_s": round(command_age_s, 9),
            "timeout_s": timeout_s,
            "action": action,
        })
        del link["events"][:-100]

    def _external_control_telemetry(self) -> dict[str, Any]:
        link = self.external_control
        last_command_time_s = link["last_command_time_s"]
        return {
            "mode": self.command["mode"],
            "state": link["state"],
            "watchdog_timeout_s": link["watchdog_timeout_s"],
            "last_command_age_s": (
                max(0.0, self.t-last_command_time_s)
                if last_command_time_s is not None else None),
            "clock": "SIMULATION_TIME",
            "events": copy.deepcopy(link["events"][-100:]),
        }

    def step(self, dt_s: float) -> dict[str, Any]:
        dt_s = float(dt_s)
        if not math.isfinite(dt_s) or dt_s < 0.0 or dt_s > 60.0:
            raise ValueError("dt_s must be finite and between 0 and 60 seconds")
        if dt_s == 0.0:
            return self.state()
        if not self.mission_started or self.phase in {"LANDED", "CRASHED", "ABORTED"}:
            return self.state()
        if self.scenario == 'planetary':
            return self._step_planetary(dt_s)
        max_step = (0.02 if self.vehicle == "drone" else
                    0.05 if self.vehicle == "aircraft" else
                    0.05 if self.command["throttle_pct"] > 0.0 else MAX_STEP_S)
        if self.integration_step_cap_s is not None:
            max_step = min(max_step, self.integration_step_cap_s)
        if self.science:
            max_step = min(max_step, .05)
        n = max(1, math.ceil(dt_s / max_step))
        h = dt_s / n
        advanced_s = 0.0
        for step_index in range(n):
            self._update_python_control_watchdog(self.t + advanced_s)
            if (self.vehicle == "space" and self.scenario == "orbital" and
                    self.command["mode"] != "auto" and self.command.get("sas_enabled") and
                    self._effective_sas_mode() != self.command["attitude_sas_mode"]):
                self.command["attitude_sas_mode"] = "stability_assist"
                self.spacecraft_attitude.inertial_hold_quaternion = (
                    self.spacecraft_attitude.quaternion_body_to_eci[:])
            if self.phase in {"LANDED", "CRASHED", "ABORTED"}:
                break
            old_phase = self.phase
            if (self.vehicle != "space" and self.command["mode"] == "auto"
                    and self.scenario == "mission" and
                    self._guidance_update_due(self.t + advanced_s)):
                self._guide_mission(self.t + advanced_s)
            elif (self.vehicle == "space" and self.scenario == "orbital"
                  and self.command["mode"] == "auto" and
                  self._guidance_update_due(self.t + advanced_s)):
                self._guide_orbital_rendezvous()
            if self.science:
                self.science.before_step(self, h, self.t+advanced_s)
            navigation_start_state = (
                self._relative_rtn_state()[:2]
                if self.vehicle == "space" and self.scenario == "orbital"
                and self.relative_navigation is not None else None)
            if self.vehicle == "space":
                remaining_h = h
                elapsed_h = 0.0
                while remaining_h > 1e-12:
                    segment_phase = self.phase
                    if (self.command["mode"] == "auto"
                            and self.scenario in {"mission", "leo-return"} and
                            self._guidance_update_due(
                                self.t+advanced_s+elapsed_h)):
                        self._guide_mission(self.t+advanced_s+elapsed_h)
                    segment_start_time_s = self.t+advanced_s+elapsed_h
                    self._prepare_launch_attitude_sample(segment_start_time_s)
                    throttle = self.command["throttle_pct"] / 100.0
                    segment_h = remaining_h
                    if throttle > 0.0:
                        segment_h = min(segment_h, 0.05)
                    if self.integration_step_cap_s is not None:
                        segment_h = min(segment_h, self.integration_step_cap_s)
                    segment_start_time_s = self.t+advanced_s+elapsed_h
                    segment_start_orbit = self.orbit[:]
                    if (self.launch_vehicle_attitude is not None and
                            self._launch_attitude_sample_next_s is not None):
                        until_attitude_update = (
                            self._launch_attitude_sample_next_s-segment_start_time_s)
                        if until_attitude_update > 1e-12:
                            segment_h = min(segment_h, until_attitude_update)
                    stage_burnout_at_end = False
                    mass_flow = 0.0
                    altitude = _norm3(self.orbit[:3]) - EARTH_RADIUS
                    engine_availability = self._engine_availability()
                    effective_thrust_N = self._thrust_at_altitude(altitude) * engine_availability
                    if (throttle > 0.0 and self.isp_s > 0.0
                            and effective_thrust_N > 0.0):
                        if self.propellant_kg <= 1e-12:
                            # A manual command may be issued after the last
                            # propellant is gone; never create a zero-duration
                            # integration segment in that state.
                            throttle = 0.0
                            self.command["throttle_pct"] = 0.0
                            if self.scenario == "orbital":
                                self.rendezvous_acceleration_eci_m_s2 = [0.0, 0.0, 0.0]
                        else:
                            # Chamber mass flow is set by the engine operating
                            # point. Ambient pressure changes net thrust, not
                            # propellant flow in proportion to that thrust.
                            # `isp_s` is the vacuum value, so use vacuum thrust
                            # here and apply the pressure correction only to
                            # acceleration.
                            mass_flow = (throttle*self.max_thrust_N*engine_availability/
                                         (self.isp_s*G0))
                            if self.science and self.science.mass_flow_kg_s is not None:
                                mass_flow = self.science.mass_flow_kg_s*engine_availability
                            if self.active_stage_index < len(self.stage_specs):
                                stage_fuel = self.stage_propellant_kg[self.active_stage_index]
                                burn_time_s = stage_fuel/mass_flow
                                if burn_time_s <= segment_h:
                                    segment_h = burn_time_s
                                    stage_burnout_at_end = True
                            else:
                                burn_time_s = self.propellant_kg/mass_flow
                                if burn_time_s <= segment_h:
                                    segment_h = burn_time_s
                                    stage_burnout_at_end = True
                    if segment_h <= 1e-12 and stage_burnout_at_end:
                        if self.active_stage_index < len(self.stage_specs):
                            self.stage_propellant_kg[self.active_stage_index] = 0.0
                        self.propellant_kg = sum(self.stage_propellant_kg)
                        self.mass_kg = (self.mass_dry_kg + self.propellant_kg +
                                        self.acs_propellant_kg)
                        self._separate_spent_stage(
                            self.t + advanced_s + elapsed_h)
                        continue
                    if (self.scenario == "orbital"
                            and self.command["mode"] == "auto"):
                        acceleration = list(self.rendezvous_acceleration_eci_m_s2)
                        derivative = lambda y: self._space_derivative(
                            y, thrust_accel_eci_m_s2=acceleration)
                    elif (self.launch_vehicle_attitude is not None and throttle > 0.0
                          and effective_thrust_N > 0.0):
                        heat_flux_before = self._space_stagnation_heat_flux_W_m2(self.orbit)
                        stage_index = self.active_stage_index
                        stage_fuel_start = (
                            self.stage_propellant_kg[stage_index]
                            if stage_index < len(self.stage_specs)
                            else self.propellant_kg)
                        direction = (self._launch_attitude_sample_direction_eci or
                                     self.launch_vehicle_attitude.thrust_direction_eci())

                        def derivative(y: list[float]) -> list[float]:
                            state = y[:6]
                            stage_fuel = (max(0.0, y[6]) if len(y) > 6
                                          else stage_fuel_start)
                            stage_mass = max(
                                1.0, self.mass_kg + stage_fuel-stage_fuel_start)
                            stage_altitude = _norm3(state[:3])-EARTH_RADIUS
                            stage_thrust = (throttle * engine_availability *
                                            self._thrust_at_altitude(stage_altitude))
                            acceleration = [stage_thrust/stage_mass*value
                                            for value in direction]
                            state_derivative = self._space_derivative(
                                state, thrust_accel_eci_m_s2=acceleration,
                                mass_kg_override=stage_mass)
                            if len(y) > 6:
                                return [*state_derivative, -mass_flow]
                            return state_derivative

                        integration_state = [*self.orbit, stage_fuel_start]
                        candidate = self._rk4(
                            integration_state, segment_h, derivative)
                        self.orbit = candidate[:6]
                        stage_fuel_end = max(0.0, candidate[6])
                        integrated_stage_fuel = (stage_index, stage_fuel_end,
                                                 stage_burnout_at_end)
                        derivative_state = [*self.orbit, stage_fuel_end]
                    else:
                        derivative = self._space_derivative
                    if not (self.launch_vehicle_attitude is not None and throttle > 0.0
                            and effective_thrust_N > 0.0):
                        heat_flux_before = self._space_stagnation_heat_flux_W_m2(self.orbit)
                        candidate = self._rk4(self.orbit, segment_h, derivative)
                        self.orbit = candidate
                        derivative_state = self.orbit
                        integrated_stage_fuel = None
                    integrated_state = (self.orbit if integrated_stage_fuel is None else
                                        [*self.orbit, integrated_stage_fuel[1]])
                    if not all(math.isfinite(value) for value in integrated_state):
                        self.fault = "NON_FINITE_STATE"
                        self.phase = "ABORTED"
                        self.command["throttle_pct"] = 0.0
                        break
                    total_acceleration_eci = derivative(derivative_state)[3:6]
                    heat_flux_after = self._space_stagnation_heat_flux_W_m2(self.orbit)
                    self.mission_metrics["max_stagnation_point_convective_heat_flux_W_m2"] = max(
                        self.mission_metrics[
                            "max_stagnation_point_convective_heat_flux_W_m2"],
                        heat_flux_before, heat_flux_after)
                    self.mission_metrics["stagnation_point_convective_heat_load_J_m2"] += (
                        0.5*(heat_flux_before+heat_flux_after)*segment_h)
                    if self.launch_vehicle_attitude is not None:
                        self._advance_launch_attitude_sample(
                            self.t+advanced_s+elapsed_h+segment_h)
                    if integrated_stage_fuel is not None:
                        stage_index, stage_fuel_end, stage_burnout = integrated_stage_fuel
                        if stage_index < len(self.stage_propellant_kg):
                            self.stage_propellant_kg[stage_index] = (
                                0.0 if stage_burnout else stage_fuel_end)
                        self.propellant_kg = sum(self.stage_propellant_kg)
                        self.mass_kg = (self.mass_dry_kg + self.propellant_kg +
                                        self.acs_propellant_kg)
                        if stage_burnout:
                            self._separate_spent_stage(
                                self.t+advanced_s+elapsed_h+segment_h)
                    else:
                        self._burn_mass(segment_h,
                                        self.t+advanced_s+elapsed_h+segment_h)
                    if self.scenario == "orbital" and self.spacecraft_attitude is not None:
                        self.spacecraft_attitude.step(
                            segment_h, self.orbit[:3], self.orbit[3:], MU_EARTH,
                            self.command["attitude_target_deg"],
                            control_mode=self._effective_sas_mode(),
                            manual_torque_body_fraction=self.command[
                                "attitude_torque_body_fraction"],
                            target_position_eci_m=self.target_orbit[:3],
                            maneuver_direction_eci=self.command.get(
                                "maneuver_direction_eci"))
                    gravity_eci = self._gravity_eci_acceleration(self.orbit[:3])
                    self._set_specific_force_eci([
                        total_acceleration_eci[i]-gravity_eci[i]
                        for i in range(3)])
                    if (self.scenario != "orbital" and
                            self.space_navigation is not None and
                            self.launch_vehicle_attitude is not None):
                        gnss_available = not any(
                            fault["type"] == "gnss_dropout"
                            for fault in self.injected_faults)
                        self.space_navigation.update(
                            segment_h, self.specific_force_body_m_s2,
                            self.launch_vehicle_attitude.quaternion_body_to_eci,
                            self.orbit[:3], self.orbit[3:],
                            segment_start_time_s+segment_h,
                            self._gravity_eci_acceleration,
                            gnss_available=gnss_available,
                            previous_truth_position_eci_m=segment_start_orbit[:3],
                            previous_truth_velocity_eci_m_s=segment_start_orbit[3:])
                    if self.scenario == "orbital" and self.propellant_kg <= 0.0:
                        self.rendezvous_acceleration_eci_m_s2 = [0.0, 0.0, 0.0]
                        self.command["throttle_pct"] = 0.0
                    elapsed_h += segment_h
                    remaining_h = max(0.0, remaining_h-segment_h)
                    if self.scenario != "orbital":
                        self._update_space_phase()
                        if self.phase != segment_phase:
                            self.phase_time_s = 0.0
                        else:
                            self.phase_time_s += segment_h
                    if self.phase == "ABORTED":
                        break
                if self.scenario == "orbital":
                    self.target_orbit = self._rk4(self.target_orbit, h,
                                                   lambda y: self._space_derivative(y, 0.0, 0.0))
                    if self.relative_navigation is not None:
                        truth_position, truth_velocity, axes = self._relative_rtn_state()
                        target_radius = max(_norm3(self.target_orbit[:3]), 1.0)
                        mean_motion = math.sqrt(MU_EARTH/target_radius**3)
                        acceleration_eci = (
                            self.rendezvous_acceleration_eci_m_s2
                            if self.command["mode"] == "auto" else [0.0, 0.0, 0.0])
                        acceleration_rtn = [
                            sum(acceleration_eci[i]*axis[i] for i in range(3))
                            for axis in axes]
                        self.relative_navigation.update(
                            h, truth_position, truth_velocity,
                            self.t+advanced_s+h, mean_motion, acceleration_rtn,
                            previous_truth_position_rtn_m=(
                                navigation_start_state[0]
                                if navigation_start_state is not None else None),
                            previous_truth_velocity_rtn_m_s=(
                                navigation_start_state[1]
                                if navigation_start_state is not None else None))
                    self._update_space_phase()
            else:
                previous_up_speed = -self._ned_velocity(self.flight)[2]
                candidate = self._rk4(self.flight, h, self._flight_derivative)
                if not all(math.isfinite(value) for value in candidate):
                    self.fault = "NON_FINITE_STATE"
                    self.phase = "ABORTED"
                    self.command["throttle_pct"] = 0.0
                    break
                self.flight = candidate
                if self.vehicle == "aircraft":
                    self.flight[-1] = max(0.0, self.flight[-1])
                    self.flight[-2] = max(self.mass_dry_kg, self.flight[-2])
                    self.propellant_kg = self.flight[-1]
                    self.mass_kg = self.flight[-2]
                else:
                    rotor_count = self.drone["rotors"]
                    phase_start = 12 + rotor_count
                    phase_end = phase_start + rotor_count
                    for index in range(phase_start, phase_end):
                        self.flight[index] = math.remainder(
                            self.flight[index], 2.0*math.pi)
                    power = self._drone_electrical_power_W()
                    energy_used = min(self.battery_energy_Wh, power*h/3600.0)
                    self.battery_energy_Wh = max(0.0, self.battery_energy_Wh-energy_used)
                    self.battery_power_W = power if self.battery_energy_Wh > 0.0 else 0.0
                    self.mission_metrics["battery_energy_used_Wh"] += energy_used
                    self.propellant_kg = (100.0*self.battery_energy_Wh/
                                          self.battery_capacity_Wh)
                    self.flight[-1] = self.propellant_kg
                self._update_air_phase(self.t + advanced_s + h)
                if self.vertical_nav is not None:
                    up_speed = -self._ned_velocity(self.flight)[2]
                    barometer_available = not any(
                        fault["type"] == "barometer_dropout"
                        for fault in self.injected_faults)
                    gnss_altitude_available = not any(
                        fault["type"] == "gnss_dropout"
                        for fault in self.injected_faults)
                    self.vertical_nav.update(h, -self.flight[2], up_speed,
                                             self.t + advanced_s + h,
                                             barometer_available=barometer_available,
                                             gnss_altitude_available=gnss_altitude_available)
                if self.horizontal_nav is not None:
                    ground_velocity = self._ned_velocity(self.flight)
                    gnss_available = not any(
                        fault["type"] == "gnss_dropout"
                        for fault in self.injected_faults)
                    self.horizontal_nav.update(
                        h, self.flight[:2], ground_velocity[:2],
                        self.t + advanced_s + h,
                        gnss_available=gnss_available)
                self._update_atmospheric_specific_force()
            self._enforce_space_launch_pad_contact()
            self._record_mission_metrics()
            if self.vehicle == "space" and self.scenario != "orbital":
                pass  # Phase time is advanced at each hybrid integration segment.
            elif self.phase != old_phase:
                self.phase_time_s = 0.0
            else:
                self.phase_time_s += h
            self.live_systems.advance(self, h, self.t + advanced_s + h)
            if self.science:
                self.science.after_step(self, h, self.t+advanced_s+h)
            advanced_s += h
            self._update_fdir(self.t + advanced_s)
            if self.phase in {"LANDED", "CRASHED", "ABORTED"}:
                if self.vehicle == "drone":
                    self.battery_power_W = 0.0
                break
        self.t += advanced_s
        return self.state()

    def _guide_mission(self, mission_time_s: float | None = None) -> None:
        current_time_s = self.t if mission_time_s is None else mission_time_s
        elapsed = current_time_s - (self.launch_t or 0.0)
        if self.vehicle == "space":
            navigation_state = self._space_guidance_state()
            radius = _norm3(navigation_state[:3])
            altitude = radius - EARTH_RADIUS
            if self.phase == "ASCENT":
                if self.scenario == "leo-return":
                    if altitude < 3_000:
                        pitch = 90.0
                    elif altitude < 10_000:
                        pitch = 90.0 - 9.0 * (altitude - 3_000) / 7_000
                    elif altitude < 50_000:
                        pitch = 81.0 - 61.0 * (altitude - 10_000) / 40_000
                    elif altitude < 100_000:
                        pitch = 20.0 - 12.0 * (altitude - 50_000) / 50_000
                    elif altitude < 150_000:
                        pitch = 8.0 * (1.0 - (altitude - 100_000) / 50_000)
                    else:
                        pitch = 0.0
                elif altitude < 3_000:
                    pitch = 90.0
                elif altitude < 10_000:
                    pitch = 90.0 - 9.0 * (altitude - 3_000) / 7_000
                elif altitude < 50_000:
                    pitch = 81.0 - 49.0 * (altitude - 10_000) / 40_000
                else:
                    pitch = max(12.0, 32.0 - 20.0 * _clamp((altitude - 50_000) / 50_000, 0.0, 1.0))
                if self.scenario == "leo-return":
                    elements = self._orbital_elements(navigation_state)
                    apoapsis = elements["apoapsis_altitude_m"]
                    required_reserve = self._leo_insertion_reserve_kg(elements)
                    current_stage_fuel = (
                        self.stage_propellant_kg[self.active_stage_index]
                        if self.active_stage_index < len(self.stage_propellant_kg)
                        else 0.0)
                    cutoff_ready = (
                        altitude >= 100_000.0
                        and self.active_stage_index == len(self.stage_specs)-1
                        and apoapsis is not None
                        and apoapsis >= LEO_TARGET_APOAPSIS_M
                        and current_stage_fuel >= required_reserve)
                    if cutoff_ready:
                        self.phase = "COAST_TO_APOGEE"
                        self.command.update(throttle_pct=0.0, pitch_deg=0.0,
                                            roll_deg=0.0)
                        self.mission_metrics["insertion_cutoff_orbit"] = {
                            key: elements[key] for key in
                            ("semi_major_axis_m", "eccentricity", "period_s",
                             "periapsis_altitude_m", "apoapsis_altitude_m")}
                        self.mission_metrics["insertion_cutoff_orbit"]["time_s"] = current_time_s
                    else:
                        self.command.update(throttle_pct=100.0 if self.propellant_kg > 0 else 0.0,
                                            pitch_deg=pitch, roll_deg=0.0)
                else:
                    self.command.update(throttle_pct=100.0 if self.propellant_kg > 0 else 0.0,
                                        pitch_deg=pitch, roll_deg=0.0)
            elif self.phase == "CIRCULARIZE":
                elements = self._orbital_elements(navigation_state)
                if elements["eccentricity"] <= LEO_CIRCULARIZATION_ECCENTRICITY:
                    self.phase = "ORBIT_COAST"
                    self.command.update(throttle_pct=0.0, pitch_deg=0.0,
                                        roll_deg=0.0)
                    self.mission_metrics["insertion_orbit"] = {
                        key: elements[key] for key in
                        ("semi_major_axis_m", "eccentricity", "period_s",
                         "periapsis_altitude_m", "apoapsis_altitude_m")}
                    self.mission_metrics["insertion_orbit"]["time_s"] = current_time_s
                    self.orbit_hold_started_s = current_time_s
                    self.orbit_hold_duration_s = elements["period_s"]
                else:
                    self.command.update(throttle_pct=100.0, pitch_deg=0.0,
                                        roll_deg=0.0)
            elif self.phase == "ORBIT_COAST":
                hold_remaining = (
                    math.inf if self.orbit_hold_started_s is None
                    or self.orbit_hold_duration_s is None else
                    self.orbit_hold_duration_s -
                    (current_time_s-self.orbit_hold_started_s))
                # Begin the retrograde slew before the burn window, using RCS
                # while the upper stage remains in coast.
                retrograde_slew = hold_remaining <= 240.0
                self.command.update(throttle_pct=0.0, pitch_deg=0.0,
                                    roll_deg=180.0 if retrograde_slew else 0.0)
                if (self.orbit_hold_started_s is not None
                        and self.orbit_hold_duration_s is not None
                        and current_time_s-self.orbit_hold_started_s >= self.orbit_hold_duration_s):
                    self.mission_metrics["orbital_hold_s"] = (
                        current_time_s-self.orbit_hold_started_s)
                    self.phase = "DEORBIT_ALIGN"
                    self.command.update(throttle_pct=0.0, pitch_deg=0.0,
                                        roll_deg=180.0)
                    if (self.launch_vehicle_attitude is not None and
                            self.launch_vehicle_attitude.attitude_error_deg <= 1.0):
                        self.phase = "DEORBIT_BURN"
                        self.command["throttle_pct"] = 100.0
            elif self.phase == "DEORBIT_ALIGN":
                aligned = (self.launch_vehicle_attitude is not None and
                           self.launch_vehicle_attitude.attitude_error_deg <= 1.0)
                self.command.update(throttle_pct=0.0, pitch_deg=0.0,
                                    roll_deg=180.0)
                if aligned:
                    self.phase = "DEORBIT_BURN"
                    self.command["throttle_pct"] = 100.0
                elif self.phase_time_s >= 600.0:
                    self.phase = "ABORTED"
                    self.fault = "DEORBIT_ATTITUDE_ALIGNMENT_TIMEOUT"
            elif self.phase == "DEORBIT_BURN":
                elements = self._orbital_elements(navigation_state)
                if elements["periapsis_altitude_m"] <= LEO_TARGET_PERIAPSIS_M:
                    self.phase = "DEORBIT_COAST"
                    self.command.update(throttle_pct=0.0, pitch_deg=0.0,
                                        roll_deg=0.0)
                    self.mission_metrics["deorbit_orbit"] = {
                        key: elements[key] for key in
                        ("semi_major_axis_m", "eccentricity", "period_s",
                         "periapsis_altitude_m", "apoapsis_altitude_m")}
                    self.mission_metrics["deorbit_orbit"]["time_s"] = current_time_s
                else:
                    self.command.update(throttle_pct=100.0, pitch_deg=0.0,
                                        roll_deg=180.0)
            elif self.phase in {"COAST", "COAST_TO_APOGEE", "ORBIT_COAST",
                                "DEORBIT_COAST", "REENTRY", "DROGUE", "PARACHUTE"}:
                self.command.update(throttle_pct=0.0, pitch_deg=0.0, roll_deg=0.0)
            return

        ned_velocity = self._ned_velocity(self.flight)
        if self.vertical_nav is None:
            altitude = max(0.0, -self.flight[2])
            up_speed = -ned_velocity[2]
            climb_rate = -ned_velocity[2]
        else:
            altitude = max(0.0, self.vertical_nav.x[0])
            up_speed = self.vertical_nav.x[1]
            climb_rate = self.vertical_nav.x[1]
        estimated_sink_rate = -up_speed
        if self.vehicle == "aircraft":
            air_velocity = self._air_relative_velocity_body(self.flight)
            airspeed = _norm3(air_velocity)
            takeoff_speed = self.vehicle_model["takeoff_speed_m_s"]
            elapsed = max(0.0, elapsed)
            if self.phase == "EMERGENCY_GLIDE" and altitude <= 120.0:
                self.phase = "APPROACH"
                self.phase_time_s = 0.0
            if self.phase == "TAKEOFF":
                rotation_fraction = _clamp(
                    (airspeed-0.92*takeoff_speed)/(0.08*takeoff_speed), 0.0, 1.0)
                self.command.update(throttle_pct=100.0,
                                    pitch_deg=13.0*rotation_fraction,
                                    roll_deg=0.0, brakes_pct=0.0)
                if airspeed >= takeoff_speed and altitude > 3.0:
                    self.phase = "CLIMB"
            elif self.phase == "CLIMB":
                pitch = _clamp(3.0 + (650.0 - altitude) * 0.012, -2.0, 10.0)
                self.command.update(throttle_pct=90.0, pitch_deg=pitch, roll_deg=0.0,
                                    yaw_deg=self._wind_corrected_heading_deg(85.0))
                if (altitude >= 620.0 or
                        (self.phase_time_s >= 240.0 and altitude >= 450.0)):
                    self.phase = "CRUISE"
            elif self.phase == "CRUISE":
                target_speed = max(1.45*self._aircraft_stall_speed_m_s(altitude),
                                   1.20*takeoff_speed)
                throttle = self._aircraft_speed_hold_throttle(target_speed)
                approach_speed = max(
                    1.30*self._aircraft_stall_speed_m_s(altitude),
                    1.05*takeoff_speed)
                approach_sink_rate = _clamp(
                    0.08*altitude, 0.6,
                    min(3.0, approach_speed*math.tan(math.radians(3.0))))
                approach_range = (altitude*approach_speed /
                                  max(approach_sink_rate, 0.6))
                target_track = self._aircraft_runway_track_deg()
                bank, heading = self._aircraft_track_commands(
                    target_track, target_speed)
                runway_range = math.hypot(
                    self.flight[0]-AIRFIELD_RUNWAY_AIMPOINT_N_M,
                    self.flight[1])
                ground_velocity = self._ned_velocity(self.flight)
                closing_to_runway = (
                    (AIRFIELD_RUNWAY_AIMPOINT_N_M-self.flight[0])
                    *ground_velocity[0] - self.flight[1]*ground_velocity[1]) > 0.0
                self.command.update(
                    throttle_pct=throttle,
                    pitch_deg=self._aircraft_altitude_hold_pitch_deg(
                        altitude, 450.0, airspeed,
                        math.degrees(self.flight[6])),
                    roll_deg=bank, yaw_deg=heading)
                if (runway_range <= approach_range + 500.0 and
                        self.flight[0] > AIRFIELD_RUNWAY_AIMPOINT_N_M and
                        ground_velocity[0] < -2.0 and closing_to_runway):
                    self.phase = "APPROACH"
            elif self.phase == "EMERGENCY_GLIDE":
                glide = self._aircraft_best_glide_state(altitude)
                target_speed = glide["best_glide_speed_m_s"]
                throttle = self._aircraft_speed_hold_throttle(target_speed)
                target_sink_rate = target_speed/glide["lift_to_drag_ratio"]
                sink_rate = estimated_sink_rate
                current_pitch = math.degrees(self.flight[7])
                overspeed_pitch = _clamp(
                    0.25*max(0.0, airspeed-target_speed), 0.0, 5.0)
                pitch = _clamp(current_pitch + 0.65*(sink_rate-target_sink_rate)
                               + overspeed_pitch, -5.0, 12.0)
                ground_track = (self.fdir_landing_track_deg
                                if self.fdir_landing_track_deg is not None else 0.0)
                self.command.update(
                    throttle_pct=throttle, pitch_deg=pitch, roll_deg=0.0,
                    yaw_deg=self._wind_corrected_heading_deg(
                        target_speed, ground_track))
            elif self.phase == "APPROACH":
                target_speed = max(1.30*self._aircraft_stall_speed_m_s(altitude),
                                   1.05*takeoff_speed)
                throttle = self._aircraft_speed_hold_throttle(target_speed)
                target_track = self._aircraft_runway_track_deg()
                approach_track = (self.fdir_landing_track_deg
                                  if (self.fdir_landing_track_deg is not None and
                                      (self.fdir_recovery_mode ==
                                       "AUTOMATIC_FORCED_LANDING" or
                                       self.external_control["state"] in {
                                           "FORCED_LANDING",
                                           "RECOVERY_COMPLETED",
                                           "RECOVERY_FAILED"}))
                                  else target_track)
                bank, heading = self._aircraft_track_commands(
                    approach_track, target_speed,
                    max_bank_deg=_clamp(0.10*altitude, 6.0, 10.0))
                target_sink_rate = _clamp(
                    0.08*altitude, 0.6,
                    min(3.0, target_speed*math.tan(math.radians(3.0))))
                sink_rate = estimated_sink_rate
                current_pitch = math.degrees(self.flight[7])
                overspeed_pitch = _clamp(
                    0.30*max(0.0, airspeed-target_speed), 0.0, 6.0)
                pitch = _clamp(current_pitch + 0.9*(sink_rate-target_sink_rate)
                               + overspeed_pitch, -2.0, 12.0)
                self.command.update(
                    throttle_pct=throttle, pitch_deg=pitch, roll_deg=bank,
                    yaw_deg=heading)
                if altitude < 30.0:
                    self.phase = "LANDING"
            elif self.phase == "LANDING":
                target_speed = max(1.20*self._aircraft_stall_speed_m_s(altitude),
                                   takeoff_speed)
                target_track = self._aircraft_runway_track_deg()
                bank, heading = self._aircraft_track_commands(
                    target_track, target_speed, max_bank_deg=8.0)
                target_sink_rate = _clamp(0.12*altitude, 0.4, 2.0)
                sink_rate = estimated_sink_rate
                current_pitch = math.degrees(self.flight[7])
                pitch = _clamp(current_pitch + 0.9*(sink_rate-target_sink_rate),
                               -1.0, 8.0)
                throttle = self._aircraft_speed_hold_throttle(target_speed)
                self.command.update(throttle_pct=throttle, pitch_deg=pitch,
                                    roll_deg=bank, yaw_deg=heading,
                                    brakes_pct=0.0)
                if altitude <= 0.2 and abs(climb_rate) < 0.5:
                    self.phase = "ROLLOUT"
                    if abs(self.flight[3]) < 1.0:
                        self.phase = "LANDED"
            elif self.phase == "ROLLOUT":
                self.command.update(
                    throttle_pct=0.0, pitch_deg=0.0, roll_deg=0.0,
                    yaw_deg=180.0,
                    brakes_pct=(100.0 if self.external_control["state"] ==
                                "ROLLOUT_STOP" else 75.0))
            return

        # GNSS position hold, a small inspection loop, home return and vertical landing.
        if self.phase == "TAKEOFF":
            target_altitude = 30.0
            target_position = [0.0, 0.0]
            if altitude >= 29.0:
                self.phase = "INSPECT"
        elif self.phase == "INSPECT":
            target_altitude = 30.0
            if self.mission_route is not None:
                position = ([self.horizontal_nav.x[i][0] for i in range(2)]
                            if self.horizontal_nav is not None else self.flight[:2])
                velocity = ([self.horizontal_nav.x[i][1] for i in range(2)]
                            if self.horizontal_nav is not None else self._ned_velocity(self.flight)[:2])
                target_position = self.mission_route.target(position, velocity)
                if self.mission_route.finished:
                    self.phase = "RETURN"
            else:
                angle = 0.10 * self.phase_time_s
                target_position = [2.5 * math.sin(angle),
                                   2.5 * (1.0 - math.cos(angle))]
                if elapsed > 35.0:
                    self.phase = "RETURN"
        elif self.phase == "RETURN":
            target_altitude = 18.0
            target_position = [0.0, 0.0]
            nav_position = ([self.horizontal_nav.x[axis][0] for axis in range(2)]
                            if self.horizontal_nav is not None else self.flight[:2])
            nav_velocity = ([self.horizontal_nav.x[axis][1] for axis in range(2)]
                            if self.horizontal_nav is not None else
                            self._ned_velocity(self.flight)[:2])
            home_error = math.hypot(*nav_position)
            horizontal_speed = math.hypot(*nav_velocity)
            # Start descent only after the vehicle has returned over the pad
            # and bled off lateral velocity; wind may extend the return leg.
            return_gate_s = (0.0 if self.fdir_recovery_mode ==
                             "AUTOMATIC_RETURN_LAND" or
                             self.external_control["state"] == "AUTO_RETURN"
                             else 50.0)
            if elapsed > return_gate_s and home_error < 1.25 and horizontal_speed < 0.65:
                self.phase = "LANDING"
        elif self.phase == "LANDING":
            target_altitude = 0.0
            target_position = (
                list(self.fdir_sensor_landing_position_ned_m)
                if self.fdir_sensor_landing_position_ned_m is not None else
                [0.0, 0.0])
        else:
            target_altitude = 0.0
            target_position = [0.0, 0.0]
        if self.phase in {"TAKEOFF", "INSPECT", "RETURN", "LANDING"}:
            if self.horizontal_nav is None:
                position_estimate = self.flight[:2]
                velocity_estimate = self._ned_velocity(self.flight)[:2]
            else:
                position_estimate = [self.horizontal_nav.x[axis][0] for axis in range(2)]
                velocity_estimate = [self.horizontal_nav.x[axis][1] for axis in range(2)]
            position_error = [target_position[i] - position_estimate[i] for i in range(2)]
            desired_acceleration = [lqr_double_integrator_acceleration(
                position_error[i], velocity_estimate[i],
                position_weight=UAV_HORIZONTAL_LQR_WEIGHTS[0],
                velocity_weight=UAV_HORIZONTAL_LQR_WEIGHTS[1],
                control_weight=UAV_HORIZONTAL_LQR_WEIGHTS[2],
                max_acceleration_m_s2=3.0) for i in range(2)]
            air_velocity = self._air_relative_velocity_body(self.flight)
            airspeed = _norm3(air_velocity)
            density = atmosphere_isa(-self.flight[2])["density_kg_m3"]
            drag_factor = 0.5 * density * self.drone["body_drag_area_m2"] * airspeed
            drag_body = [-drag_factor * component for component in air_velocity]
            dcm = self._body_to_ned(self.flight[6], self.flight[7], self.flight[8])
            drag_acceleration_ned = [
                sum(dcm[axis][j] * drag_body[j] for j in range(3)) / self.mass_kg
                for axis in range(3)]
            tilt_acceleration = [desired_acceleration[i] - drag_acceleration_ned[i]
                                 for i in range(2)]
            pitch_command = _clamp(-math.degrees(math.atan2(tilt_acceleration[0], G0)),
                                   -32.0, 32.0)
            roll_command = _clamp(math.degrees(math.atan2(tilt_acceleration[1], G0)),
                                  -32.0, 32.0)
            self.guidance_target_ned_m = list(target_position)
            tilt_projection = max(0.8, math.cos(math.radians(roll_command)) *
                                  math.cos(math.radians(pitch_command)))
            hover = self.mass_kg * G0 / (self.max_thrust_N * tilt_projection)
            vertical_acceleration = lqr_double_integrator_acceleration(
                target_altitude-altitude, up_speed,
                position_weight=UAV_VERTICAL_LQR_WEIGHTS[0],
                velocity_weight=UAV_VERTICAL_LQR_WEIGHTS[1],
                control_weight=UAV_VERTICAL_LQR_WEIGHTS[2],
                max_acceleration_m_s2=3.0)
            vertical_drag_feedforward = drag_acceleration_ned[2]
            throttle = _clamp(
                hover+self.mass_kg*(vertical_acceleration+vertical_drag_feedforward)
                /(self.max_thrust_N*tilt_projection), 0.0, 1.0) * 100.0
            self.command.update(throttle_pct=throttle,
                                roll_deg=roll_command,
                                pitch_deg=pitch_command)

    @staticmethod
    def _ned_velocity(y: list[float]) -> list[float]:
        dcm = SimulationEngine._body_to_ned(y[6], y[7], y[8])
        return [sum(dcm[i][j]*y[3+j] for j in range(3)) for i in range(3)]

    def _wind_corrected_heading_deg(self, target_airspeed_m_s: float,
                                    target_track_deg: float = 0.0) -> float:
        """Crab into steady wind to maintain a requested NED ground track."""
        track = math.radians(target_track_deg)
        direction = [math.cos(track), math.sin(track)]
        normal = [-math.sin(track), math.cos(track)]
        mean_wind = self._mean_wind_velocity_ned(self.flight)
        crosswind = (mean_wind[0]*normal[0] + mean_wind[1]*normal[1])
        along_air = math.sqrt(max(target_airspeed_m_s**2-crosswind**2, 0.0))
        air_north = along_air*direction[0]-crosswind*normal[0]
        air_east = along_air*direction[1]-crosswind*normal[1]
        return math.degrees(math.atan2(air_east, air_north))

    def _aircraft_runway_track_deg(self) -> float:
        """Capture the southbound runway line and damp lateral velocity."""
        north, east = self.flight[:2]
        if self.phase == "CRUISE":
            # Return to a point ahead of the runway before descending; the
            # approach controller then captures and tracks its centreline.
            if north >= AIRFIELD_RUNWAY_AIMPOINT_N_M:
                distance_ahead = north-AIRFIELD_RUNWAY_AIMPOINT_N_M
                runway_track = 180.0
                correction = math.degrees(math.atan2(
                    east, max(distance_ahead, 1_000.0)))
            else:
                distance_ahead = AIRFIELD_RUNWAY_AIMPOINT_N_M-north
                runway_track = 0.0
                correction = math.degrees(math.atan2(
                    -east, max(distance_ahead, 1_000.0)))
            return runway_track + correction

        ground_velocity = self._ned_velocity(self.flight)
        ground_speed = max(math.hypot(ground_velocity[0],
                                      ground_velocity[1]), 1.0)
        # A 10 s capture time yields the lateral velocity needed to reach the
        # centreline. Damping the measured lateral speed lets the aircraft
        # roll out of the intercept before wheel contact instead of arriving
        # over the runway with a large sideways component.
        desired_east_speed = _clamp(
            -east/10.0 - 0.25*ground_velocity[1],
            -0.45*ground_speed, 0.45*ground_speed)
        track_offset = math.degrees(math.atan2(
            -desired_east_speed, max(abs(ground_velocity[0]), 1.0)))
        return 180.0 + track_offset

    def _aircraft_track_commands(self, target_track_deg: float,
                                 target_airspeed_m_s: float,
                                 max_bank_deg: float = 6.0) -> tuple[float, float]:
        """Return coordinated bank and wind-corrected heading for a ground track."""
        ground_velocity = self._ned_velocity(self.flight)
        if math.hypot(ground_velocity[0], ground_velocity[1]) > 1.0:
            ground_track_deg = math.degrees(math.atan2(
                ground_velocity[1], ground_velocity[0]))
        else:
            ground_track_deg = math.degrees(self.flight[8])
        error_deg = ((target_track_deg-ground_track_deg+180.0) % 360.0)-180.0
        bank_deg = _clamp(0.7*error_deg, -max_bank_deg, max_bank_deg)
        target_heading_deg = self._wind_corrected_heading_deg(
            target_airspeed_m_s, target_track_deg)
        current_heading_deg = math.degrees(self.flight[8])
        heading_error_deg = ((target_heading_deg-current_heading_deg+180.0)
                             % 360.0)-180.0
        heading_deg = current_heading_deg + _clamp(
            heading_error_deg, -6.0, 6.0)
        return bank_deg, heading_deg

    def _aircraft_altitude_hold_pitch_deg(self, altitude_m: float,
                                          target_altitude_m: float,
                                          airspeed_m_s: float,
                                          bank_deg: float) -> float:
        """Estimate pitch from lift balance and a bounded altitude-error command."""
        density = atmosphere_isa(max(altitude_m, -500.0))["density_kg_m3"]
        qbar = 0.5*density*max(airspeed_m_s, 1.0)**2
        bank_cosine = max(math.cos(math.radians(bank_deg)), 0.5)
        required_cl = (self.mass_kg*G0 /
                       max(qbar*self.aero["S_m2"]*bank_cosine, 1e-9))
        alpha = ((required_cl-self.aero["CL0"])/
                 max(self.aero["CLalpha_rad"], 1e-9))
        alpha = _clamp(alpha, -self.aero["alpha_stall_rad"],
                       0.85*self.aero["alpha_stall_rad"])
        vertical_speed = _clamp(0.12*(target_altitude_m-altitude_m),
                                -4.0, 4.0)
        flight_path_angle = math.atan2(vertical_speed,
                                       max(airspeed_m_s, 1.0))
        return _clamp(math.degrees(alpha+flight_path_angle), -3.0, 12.0)

    @staticmethod
    def _validate_wind(wind: list[float] | tuple[float, float, float] | None) -> list[float]:
        """Validate a steady wind vector expressed in local NED axes (m/s)."""
        if wind is None:
            return [0.0, 0.0, 0.0]
        if not isinstance(wind, (list, tuple)) or len(wind) != 3:
            raise ValueError("wind_ned_m_s must be a three-element NED vector in m/s")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
               not math.isfinite(value) for value in wind):
            raise ValueError("wind_ned_m_s values must be finite numbers")
        vector = [float(value) for value in wind]
        if _norm3(vector) > 60.0:
            raise ValueError("wind_ned_m_s magnitude must not exceed 60 m/s")
        return vector

    def _air_relative_velocity_body(self, y: list[float]) -> list[float]:
        """Vehicle velocity relative to mean and turbulent air, in body axes."""
        relative_ned = self._air_relative_velocity_ned(y)
        dcm = self._body_to_ned(y[6], y[7], y[8])
        return [sum(dcm[j][i] * relative_ned[j] for j in range(3))
                for i in range(3)]

    def _air_relative_velocity_ned(self, y: list[float]) -> list[float]:
        """Vehicle velocity relative to mean and turbulent air, in NED axes."""
        ground_ned = self._ned_velocity(y)
        mean_wind = self._mean_wind_velocity_ned(y)
        gust = self._turbulence_gust_ned(y)
        return [ground_ned[i]-mean_wind[i]-gust[i]
                for i in range(3)]

    def _mean_wind_velocity_ned(self, y: list[float]) -> list[float]:
        """Return the local steady NED wind at the state's geometric altitude."""
        if self.surface_layer_wind is not None:
            return surface_layer_wind_at_altitude(self.surface_layer_wind, -float(y[2]))[0]
        if self.wind_profile_ned_m_s is None:
            return list(self.wind_ned_m_s)
        return wind_at_altitude(self.wind_profile_ned_m_s, -float(y[2]))[0]

    def _wind_telemetry_state(self, altitude_m: float) -> tuple[list[float], bool]:
        if self.surface_layer_wind is not None:
            return surface_layer_wind_at_altitude(self.surface_layer_wind, altitude_m)
        if self.wind_profile_ned_m_s is None:
            return list(self.wind_ned_m_s), False
        return wind_at_altitude(self.wind_profile_ned_m_s, altitude_m)

    def _turbulence_gust_ned(self, y: list[float]) -> list[float]:
        """Map seeded Dryden u/v/w gusts into local NED wind axes."""
        if (self.science and self.vehicle != 'space' and
                self.science.config['turbulence_sigma_m_s'] > 0):
            return self.science.wind.evaluate(y[-3])
        if self.turbulence_model is None:
            return [0.0, 0.0, 0.0]
        gust_forward, gust_right, gust_down = self.turbulence_model.evaluate(y[-3])
        ground_ned = self._ned_velocity(y)
        mean_wind = self._mean_wind_velocity_ned(y)
        mean_air = [ground_ned[i]-mean_wind[i] for i in range(3)]
        horizontal_air_speed = math.hypot(mean_air[0], mean_air[1])
        if horizontal_air_speed > 1e-6:
            course_north = mean_air[0]/horizontal_air_speed
            course_east = mean_air[1]/horizontal_air_speed
        else:
            course_north = math.cos(y[8])
            course_east = math.sin(y[8])
        return [gust_forward*course_north-gust_right*course_east,
                gust_forward*course_east+gust_right*course_north,
                gust_down]

    def _aircraft_propulsion_state(self, y: list[float]) -> dict[str, Any]:
        """Return calibrated propeller output at the current airspeed and density."""
        powertrain = self.aircraft_powertrain
        altitude = max(-y[2], -500.0)
        density = atmosphere_isa(altitude)["density_kg_m3"]
        airspeed = _norm3(self._air_relative_velocity_body(y))
        power_fraction = _clamp(float(y[15]), 0.0, 1.0)
        output = fixed_wing_propulsion(
            static_thrust_N=self.max_thrust_N,
            airspeed_m_s=airspeed,
            air_density_kg_m3=density,
            total_disk_area_m2=powertrain["total_disk_area_m2"],
            propeller_efficiency=powertrain["propeller_efficiency"],
            power_lapse_exponent=powertrain["power_lapse_exponent"],
            specific_fuel_consumption_kg_per_kWh=(
                powertrain["specific_fuel_consumption_kg_per_kWh"]),
            engine_power_fraction=power_fraction,
        )
        nominal_thrust_N = output["thrust_N"]
        nominal_fuel_flow_kg_s = output["fuel_flow_kg_s"]
        availability = self._engine_availability()
        output["thrust_N"] = nominal_thrust_N * availability
        output["fuel_flow_kg_s"] = nominal_fuel_flow_kg_s * availability
        return {
            **output,
            "nominal_thrust_N": nominal_thrust_N,
            "nominal_fuel_flow_kg_s": nominal_fuel_flow_kg_s,
            "engine_availability_fraction": availability,
            "engine_type": powertrain["engine_type"],
            "engine_spool_model": "FIRST_ORDER_POWER_FRACTION_LAG",
            "static_thrust_reference_N": self.max_thrust_N,
            "commanded_power_pct": self.command["throttle_pct"],
            "actual_power_pct": 100.0*power_fraction,
            "spool_time_constant_s": powertrain["spool_time_constant_s"],
            "propeller_count": powertrain["propeller_count"],
            "propeller_radius_m": powertrain["propeller_radius_m"],
            "propeller_efficiency": powertrain["propeller_efficiency"],
            "specific_fuel_consumption_kg_per_kWh": (
                powertrain["specific_fuel_consumption_kg_per_kWh"]),
            "air_relative_speed_m_s": airspeed,
        }

    def _aircraft_speed_hold_throttle(self, target_airspeed_m_s: float) -> float:
        """Invert the force balance for thrust along the air-relative velocity."""
        y = self.flight
        altitude = max(-y[2], -500.0)
        density = atmosphere_isa(altitude)["density_kg_m3"]
        air_velocity = self._air_relative_velocity_body(y)
        airspeed = _norm3(air_velocity)
        alpha = math.atan2(air_velocity[2], max(abs(air_velocity[0]), 0.1))
        beta = math.asin(_clamp(air_velocity[1]/max(airspeed, 0.1), -0.99, 0.99))
        dynamic_pressure = 0.5*density*airspeed*airspeed
        coefficients = fixed_wing_coefficients(self.aero, alpha, beta)
        drag = dynamic_pressure*self.aero["S_m2"]*coefficients["CD"]
        lift = dynamic_pressure*self.aero["S_m2"]*coefficients["CL"]
        side = dynamic_pressure*self.aero["S_m2"]*coefficients["CY"]
        aerodynamic_force = [
            -drag*math.cos(alpha)+lift*math.sin(alpha),
            side,
            -drag*math.sin(alpha)-lift*math.cos(alpha),
        ]
        phi, theta = y[6], y[7]
        p, q, r = y[9:12]
        u_air, v_air, w_air = air_velocity
        gravity = [-G0*math.sin(theta),
                   G0*math.sin(phi)*math.cos(theta),
                   G0*math.cos(phi)*math.cos(theta)]
        non_propulsive_acceleration = [
            aerodynamic_force[0]/self.mass_kg + gravity[0] - q*w_air + r*v_air,
            aerodynamic_force[1]/self.mass_kg + gravity[1] - r*u_air + p*w_air,
            aerodynamic_force[2]/self.mass_kg + gravity[2] - p*v_air + q*u_air,
        ]
        along_track_acceleration = sum(
            air_velocity[index]*non_propulsive_acceleration[index]
            for index in range(3))/max(airspeed, 0.1)
        acceleration_request = _clamp(
            0.18*(target_airspeed_m_s-airspeed), -1.5, 1.5)
        required_thrust = max(
            0.0, self.mass_kg*(acceleration_request-along_track_acceleration)
            * max(airspeed, 0.1)/max(u_air, 0.1))
        availability = self._engine_availability()
        if required_thrust <= 1e-9:
            return 0.0
        if availability <= 1e-9:
            return 100.0
        power_fraction = fixed_wing_power_fraction_for_thrust(
            required_thrust_N=required_thrust/availability,
            static_thrust_N=self.max_thrust_N,
            airspeed_m_s=airspeed,
            air_density_kg_m3=density,
            total_disk_area_m2=self.aircraft_powertrain["total_disk_area_m2"],
            propeller_efficiency=self.aircraft_powertrain[
                "propeller_efficiency"],
            power_lapse_exponent=self.aircraft_powertrain[
                "power_lapse_exponent"],
            specific_fuel_consumption_kg_per_kWh=(
                self.aircraft_powertrain[
                    "specific_fuel_consumption_kg_per_kWh"]),
        )
        return 100.0*power_fraction

    def _aircraft_stall_speed_m_s(self, altitude_m: float) -> float:
        """Clean-config stall speed from current mass and local air density."""
        density = atmosphere_isa(max(altitude_m, -500.0))["density_kg_m3"]
        cl_max = fixed_wing_coefficients(
            self.aero, self.aero["alpha_stall_rad"], 0.0)["CL"]
        if density <= 0.0 or cl_max <= 0.0 or self.aero["S_m2"] <= 0.0:
            return math.inf
        return math.sqrt(2.0*self.mass_kg*G0 /
                         (density*self.aero["S_m2"]*cl_max))

    def _aircraft_best_glide_state(self, altitude_m: float) -> dict[str, float]:
        """Calculate best L/D and the corresponding steady glide speed.

        The polar is the aircraft's current parabolic clean configuration.  The
        target lift coefficient is clamped below the modeled stall boundary;
        no flaps or wind gradient are represented.
        """
        density = atmosphere_isa(max(altitude_m, -500.0))["density_kg_m3"]
        cd0 = float(self.aero["CD0"])
        induced_drag_k = float(self.aero["induced_drag_k"])
        cl_alpha = float(self.aero["CLalpha_rad"])
        if density <= 0.0 or self.aero["S_m2"] <= 0.0 or cl_alpha <= 0.0:
            raise ValueError("best-glide calculation is outside the aerodynamic model domain")
        cl_max = fixed_wing_coefficients(
            self.aero, self.aero["alpha_stall_rad"], 0.0)["CL"]
        cl_best = min(math.sqrt(cd0/max(induced_drag_k, 1e-12)), 0.98*cl_max)
        alpha_best = (cl_best-float(self.aero["CL0"]))/cl_alpha
        alpha_best = _clamp(alpha_best, -self.aero["alpha_stall_rad"],
                            self.aero["alpha_stall_rad"])
        coefficients = fixed_wing_coefficients(self.aero, alpha_best, 0.0)
        glide_ratio = max(float(coefficients["CL"])/float(coefficients["CD"]), 1.0)
        best_glide_speed = math.sqrt(
            2.0*self.mass_kg*G0 /
            (density*self.aero["S_m2"]*max(float(coefficients["CL"]), 1e-6)))
        return {"best_glide_speed_m_s": best_glide_speed,
                "lift_to_drag_ratio": glide_ratio,
                "lift_coefficient": float(coefficients["CL"]),
                "drag_coefficient": float(coefficients["CD"]),
                "angle_of_attack_rad": alpha_best}

    def _update_space_phase(self) -> None:
        radius = _norm3(self.orbit[:3])
        altitude = radius - EARTH_RADIUS
        radial_speed = sum(self.orbit[i]*self.orbit[i+3] for i in range(3)) / max(radius, 1.0)
        x, y, _z, vx, vy, vz = self.orbit
        air_velocity = [vx + OMEGA_EARTH*y, vy - OMEGA_EARTH*x, vz]
        air_speed = _norm3(air_velocity)
        if (self.scenario == "leo-return"
                and self.phase in {"CIRCULARIZE", "DEORBIT_BURN"}
                and self.propellant_kg <= 0.01):
            self.phase = "ABORTED"
            self.fault = "ORBIT_MANEUVER_PROPELLANT_DEPLETED"
            self.command["throttle_pct"] = 0.0
        elif self.phase == "ASCENT" and self.propellant_kg <= 0.01:
            if self.scenario == "leo-return":
                self.phase = "ABORTED"
                self.fault = "LEO_INSERTION_RESERVE_UNAVAILABLE"
            else:
                self.phase = "COAST"
            self.command["throttle_pct"] = 0.0
        elif (self.phase == "COAST_TO_APOGEE" and radial_speed <= 0.0
              and altitude < 1_500_000.0):
            self.phase = "CIRCULARIZE"
        elif self.phase == "COAST" and radial_speed <= 0.0 and altitude < 1_500_000.0:
            self.phase = "REENTRY"
        elif self.phase in {"REENTRY", "DEORBIT_COAST"}:
            if self.scenario == "leo-return" and radial_speed < 0.0 and altitude <= 120_000.0:
                self.phase = "AEROSHELL"
            elif self.scenario != "leo-return" and altitude <= 85_000.0:
                density = atmosphere_isa(altitude)["density_kg_m3"]
                qbar = 0.5 * density * air_speed * air_speed
                if air_speed <= 5_000.0 and qbar <= 5_000.0:
                    self.phase = "AEROSHELL"
        elif self.phase == "AEROSHELL" and altitude <= 15_000.0:
            if air_speed <= 900.0:
                self.phase = "DROGUE"
        elif self.phase == "DROGUE" and altitude <= 5_000.0:
            if air_speed <= 180.0:
                self.phase = "PARACHUTE"
        if altitude <= 0.0 and self.phase in {"REENTRY", "AEROSHELL", "DROGUE", "PARACHUTE"}:
            impact_speed = air_speed
            self.mission_metrics["touchdown_speed_m_s"] = impact_speed
            if impact_speed <= 15.0:
                radial = [self.orbit[index]/max(radius, 1.0) for index in range(3)]
                surface_position = [EARTH_RADIUS*component for component in radial]
                self.mission_metrics["touchdown_position_eci_m"] = surface_position[:]
                self.orbit[:3] = surface_position
                self.orbit[3:] = [-OMEGA_EARTH*surface_position[1],
                                  OMEGA_EARTH*surface_position[0], 0.0]
                self.phase = "LANDED"
            else:
                self.phase = "CRASHED"

    def _leo_insertion_reserve_kg(self, elements: dict[str, Any]) -> float:
        """Estimate propellant for apogee circularization plus a later deorbit."""
        apoapsis = elements["apoapsis_altitude_m"]
        semi_major_axis = elements["semi_major_axis_m"]
        period = elements["period_s"]
        if (apoapsis is None or semi_major_axis is None or period is None
                or self.isp_s <= 0.0 or self.mass_kg <= self.mass_dry_kg):
            return math.inf
        apoapsis_radius = EARTH_RADIUS + apoapsis
        circular_speed = math.sqrt(MU_EARTH / apoapsis_radius)
        apoapsis_speed = math.sqrt(max(
            0.0, MU_EARTH*(2.0/apoapsis_radius-1.0/semi_major_axis)))
        deorbit_radius = EARTH_RADIUS + LEO_TARGET_PERIAPSIS_M
        deorbit_sma = 0.5*(apoapsis_radius+deorbit_radius)
        deorbit_speed = math.sqrt(max(
            0.0, MU_EARTH*(2.0/apoapsis_radius-1.0/deorbit_sma)))
        delta_v = max(0.0, circular_speed-apoapsis_speed)
        delta_v += max(0.0, circular_speed-deorbit_speed)
        delta_v += 25.0  # Guidance and finite-burn margin.
        ideal_propellant = self.mass_kg*(1.0-math.exp(-delta_v/(self.isp_s*G0)))
        return ideal_propellant*1.15

    def _update_air_phase(self, time_s: float | None = None) -> None:
        altitude = -self.flight[2]
        if self.vehicle == "drone":
            ned_velocity = self._ned_velocity(self.flight)
            if altitude > 0.5:
                self.drone_airborne = True
                if self.command["mode"] != "auto" and self.phase == "TAKEOFF":
                    self.phase = "INSPECT"
            if (altitude <= 0.15 and self.drone_airborne and
                    self.command["mode"] != "auto"):
                touchdown_speed = _norm3(ned_velocity)
                self.mission_metrics["touchdown_speed_m_s"] = touchdown_speed
                self.flight[2] = 0.0
                if touchdown_speed <= 2.5:
                    self.flight[3:6] = [0.0, 0.0, 0.0]
                    self.phase = "LANDED"
                else:
                    self.phase = "CRASHED"
                self.battery_power_W = 0.0
            elif (altitude <= 0.15 and
                  (self.phase == "LANDING" or self.fdir_recovery_mode in {
                      "AUTOMATIC_RETURN_LAND", "AUTOMATIC_SENSOR_LANDING"})):
                touchdown_speed = _norm3(ned_velocity)
                self.mission_metrics["touchdown_speed_m_s"] = touchdown_speed
                self.flight[2] = 0.0
                if touchdown_speed <= 2.5:
                    self.flight[3:6] = [0.0, 0.0, 0.0]
                    self.phase = "LANDED"
                    if self.external_control["state"] == "AUTO_RETURN":
                        self.external_control["state"] = "RECOVERY_COMPLETED"
                        self.external_control["events"].append({
                            "time_s": (self.t if time_s is None else time_s),
                            "event": "PYTHON_LINK_RECOVERY_COMPLETED",
                            "touchdown_speed_m_s": touchdown_speed,
                        })
                        del self.external_control["events"][:-100]
                    self.fdir_recovery_mode = (
                        "RECOVERY_LANDED" if self.fdir_recovery_mode ==
                        "AUTOMATIC_RETURN_LAND" else self.fdir_recovery_mode)
                    if self.fdir_recovery_mode == "AUTOMATIC_SENSOR_LANDING":
                        self.fdir_recovery_mode = "SENSOR_FAILSAFE_LANDED"
                        self.fdir_events.append({
                            "time_s": self.t if time_s is None else time_s,
                            "event": "SENSOR_FAILSAFE_LANDING_COMPLETED",
                            "touchdown_speed_m_s": touchdown_speed,
                            "position_ned_m": self.flight[:3],
                        })
                else:
                    self.phase = "CRASHED"
                    if self.external_control["state"] == "AUTO_RETURN":
                        self.external_control["state"] = "RECOVERY_FAILED"
                        self.external_control["events"].append({
                            "time_s": (self.t if time_s is None else time_s),
                            "event": "PYTHON_LINK_RECOVERY_FAILED",
                            "touchdown_speed_m_s": touchdown_speed,
                        })
                        del self.external_control["events"][:-100]
                    if self.fdir_recovery_mode == "AUTOMATIC_RETURN_LAND":
                        self.fdir_recovery_mode = "RECOVERY_FAILED_IMPACT"
                        self.fdir_events.append({
                            "time_s": self.t, "event": "AUTOMATIC_RECOVERY_FAILED",
                            "touchdown_speed_m_s": touchdown_speed,
                        })
                    elif self.fdir_recovery_mode == "AUTOMATIC_SENSOR_LANDING":
                        self.fdir_recovery_mode = "SENSOR_FAILSAFE_FAILED"
                        self.fdir_events.append({
                            "time_s": self.t if time_s is None else time_s,
                            "event": "SENSOR_FAILSAFE_LANDING_FAILED",
                            "touchdown_speed_m_s": touchdown_speed,
                            "position_ned_m": self.flight[:3],
                        })
                self.battery_power_W = 0.0
            return
        ned_velocity = self._ned_velocity(self.flight)
        if altitude > 3.0:
            self.aircraft_airborne = True
        if self.command["mode"] != "auto" and self.aircraft_airborne:
            if self.phase == "TAKEOFF":
                self.phase = "CLIMB"
            if altitude < 100.0 and ned_velocity[2] > 0.0:
                self.phase = "APPROACH"
        manual_touchdown = (self.command["mode"] != "auto" and
                            self.aircraft_airborne and self.flight[2] >= -0.01)
        if self.flight[2] >= -0.01 and (self.phase in {"APPROACH", "LANDING", "ROLLOUT"}
                                         or manual_touchdown):
            self.flight[2] = 0.0
            ned_v = self._ned_velocity(self.flight)
            if self.mission_metrics["touchdown_speed_m_s"] is None:
                self.mission_metrics["touchdown_speed_m_s"] = _norm3(ned_v)
                self.mission_metrics["touchdown_air_relative_speed_m_s"] = _norm3(
                    self._air_relative_velocity_body(self.flight))
            if ned_v[2] > 0.0:
                dcm = self._body_to_ned(self.flight[6], self.flight[7], self.flight[8])
                self.flight[5] -= ned_v[2] / max(dcm[2][2], 0.2)
            if self.phase in {"LANDING", "APPROACH"}:
                self.phase = "ROLLOUT"
            if manual_touchdown:
                self.phase = "ROLLOUT"
                self.command["throttle_pct"] = 0.0
        if self.phase == "ROLLOUT" and abs(self.flight[3]) < 1.0:
            self.flight[3:6] = [0.0, 0.0, 0.0]
            self.phase = "LANDED"
            if self.fdir_recovery_mode == "AUTOMATIC_FORCED_LANDING":
                self.fdir_recovery_mode = "FORCED_LANDING_COMPLETED"
                self.fdir_events.append({
                    "time_s": self.t if time_s is None else time_s,
                    "event": "FORCED_LANDING_COMPLETED",
                    "touchdown_speed_m_s": (
                        self.mission_metrics["touchdown_speed_m_s"]),
                    "position_ned_m": self.flight[:3],
                })
            if self.external_control["state"] == "FORCED_LANDING":
                self.external_control["state"] = "RECOVERY_COMPLETED"
                self.external_control["events"].append({
                    "time_s": self.t if time_s is None else time_s,
                    "event": "PYTHON_LINK_RECOVERY_COMPLETED",
                    "touchdown_speed_m_s": (
                        self.mission_metrics["touchdown_speed_m_s"]),
                    "position_ned_m": self.flight[:3],
                })
                del self.external_control["events"][:-100]

    def _record_mission_metrics(self) -> None:
        if self.vehicle == "space":
            radius = _norm3(self.orbit[:3])
            altitude = radius - EARTH_RADIUS
            x, y, _z, vx, vy, vz = self.orbit
            density = (atmosphere_isa(altitude)["density_kg_m3"]
                       if self.scenario in {"mission", "leo-return"} else 0.0)
            relative = _norm3([vx + OMEGA_EARTH * y,
                               vy - OMEGA_EARTH * x, vz])
            qbar = 0.5 * density * relative * relative
        else:
            altitude = -self.flight[2]
            atm = atmosphere_isa(altitude)
            airspeed = _norm3(self._air_relative_velocity_body(self.flight))
            qbar = 0.5 * atm["density_kg_m3"] * airspeed * airspeed
        self.mission_metrics["max_altitude_m"] = max(
            self.mission_metrics["max_altitude_m"], altitude)
        self.mission_metrics["max_dynamic_pressure_Pa"] = max(
            self.mission_metrics["max_dynamic_pressure_Pa"], qbar)
        specific_force_m_s2 = _norm3(self.specific_force_body_m_s2)
        self.mission_metrics["max_load_factor_g"] = max(
            self.mission_metrics["max_load_factor_g"], self.load_factor_g)
        self.mission_metrics["max_specific_force_m_s2"] = max(
            self.mission_metrics["max_specific_force_m_s2"], specific_force_m_s2)
        if self.vehicle == "drone" and self.horizontal_nav is not None:
            position = self.horizontal_nav.x
            error = math.hypot(self.guidance_target_ned_m[0] - position[0][0],
                               self.guidance_target_ned_m[1] - position[1][0])
            self.mission_metrics["max_horizontal_hold_error_m"] = max(
                self.mission_metrics["max_horizontal_hold_error_m"], error)

    def _drone_propulsion_state(self, y: list[float]) -> dict[str, Any]:
        """Return mixed rotor commands and current thrust/moment from motor states."""
        count = self.drone["rotors"]
        roll, pitch, yaw, p, q, r = y[6:12]
        roll_error = math.radians(self.command["roll_deg"]) - roll
        pitch_error = math.radians(self.command["pitch_deg"]) - pitch
        yaw_error = ((math.radians(self.command["yaw_deg"])-yaw+math.pi)
                     % (2.0*math.pi)-math.pi)
        max_yaw_moment = (self.drone["yaw_moment_coefficient_m"] *
                          self.max_thrust_N)
        yaw_moment = _clamp(0.45*yaw_error-0.24*r,
                            -max_yaw_moment, max_yaw_moment)
        throttle = self.command["throttle_pct"]/100.0
        if self.battery_energy_Wh <= 0.0:
            throttle = 0.0
        requested_wrench = [
            throttle*self.max_thrust_N,
            2.0*roll_error-0.65*p,
            2.0*pitch_error-0.65*q,
            yaw_moment,
        ]
        max_per_rotor = self.drone["max_rotor_thrust_N"]
        active_mixer = self.rotor_fault_mixer or self.rotor_mixer
        commanded_thrusts = allocate_rotor_thrusts(
            requested_wrench, active_mixer, max_per_rotor)
        max_speed = self.drone["max_rotor_speed_rad_s"]
        commanded_speeds = [thrust_to_motor_speed(
            thrust, max_per_rotor, max_speed) for thrust in commanded_thrusts]
        actual_speeds = [max(0.0, min(max_speed, value))
                         for value in y[12:12+count]]
        fault_free_actual_thrusts = [motor_speed_to_thrust(
            speed, max_speed, max_per_rotor) for speed in actual_speeds]
        actual_thrusts = [thrust*self._rotor_availability(index)
                          for index, thrust in enumerate(fault_free_actual_thrusts)]
        actual_wrench = rotor_wrench(actual_thrusts, self.rotor_geometry)
        motor_rates = [
            (commanded_speeds[index]-actual_speeds[index]) /
            (self.drone["motor_time_constant_up_s"]
             if commanded_speeds[index] >= actual_speeds[index]
             else self.drone["motor_time_constant_down_s"])
            for index in range(count)
        ]
        return {"requested_wrench_N_Nm": requested_wrench,
                "allocator_mode": ("HEALTH_AWARE_4_AXIS" if
                                   self.rotor_fault_mixer is not None else
                                   "NOMINAL_4_AXIS"),
                "commanded_thrusts_N": commanded_thrusts,
                "commanded_speeds_rad_s": commanded_speeds,
                "actual_speeds_rad_s": actual_speeds,
                "fault_free_actual_thrusts_N": fault_free_actual_thrusts,
                "actual_thrusts_N": actual_thrusts,
                "actual_wrench_N_Nm": actual_wrench,
                "motor_speed_rates_rad_s2": motor_rates}

    def _drone_electrical_power_W(self) -> float:
        """Estimate rotor, motor and airframe electrical load at current state."""
        if self.battery_energy_Wh <= 0.0:
            return 0.0
        altitude = -self.flight[2]
        atmosphere = atmosphere_isa(altitude)
        velocity_ned = self._air_relative_velocity_ned(self.flight)
        speed = _norm3(velocity_ned)
        density = atmosphere["density_kg_m3"]
        drag = 0.5*density*self.drone["body_drag_area_m2"]*speed*speed
        parasitic_power = (drag*speed /
                           self.drone["airframe_propulsive_efficiency"])
        thrust = self._drone_propulsion_state(self.flight)["actual_wrench_N_Nm"][0]
        estimate = multirotor_power(
            thrust_N=thrust,
            max_thrust_N=self.max_thrust_N,
            air_density_kg_m3=density,
            total_disk_area_m2=self.drone["total_disk_area_m2"],
            figure_of_merit=self.drone["figure_of_merit"],
            motor_efficiency=self.drone["motor_efficiency"],
            profile_power_max_W=self.drone["profile_power_max_W"],
            avionics_power_W=self.drone["avionics_power_W"],
            climb_rate_m_s=-velocity_ned[2],
            parasitic_power_W=parasitic_power,
        )
        return estimate["electrical_power_W"]

    @staticmethod
    def _rk4(y: list[float], h: float, derivative: Any) -> list[float]:
        k1 = derivative(y)
        k2 = derivative(_add(y, k1, 0.5 * h))
        k3 = derivative(_add(y, k2, 0.5 * h))
        k4 = derivative(_add(y, k3, h))
        return [a + h * (b + 2*c + 2*d + e) / 6.0
                for a, b, c, d, e in zip(y, k1, k2, k3, k4)]

    @staticmethod
    def _gravity_eci_acceleration(position_eci_m: list[float]) -> list[float]:
        """Earth central gravity plus J2 acceleration in the ECI frame."""
        x, yy, z = position_eci_m
        r = max(_norm3(position_eci_m), 1.0)
        r2 = r*r
        r3 = r2*r
        ax, ay, az = (-MU_EARTH*x/r3, -MU_EARTH*yy/r3,
                      -MU_EARTH*z/r3)
        # Earth J2 perturbation in the ECI frame (z is the Earth spin axis).
        f = 1.5 * EARTH_J2 * MU_EARTH * EARTH_RADIUS**2 / (r2 * r3)
        zratio = 5.0 * z * z / r2
        ax += f * x * (zratio - 1.0)
        ay += f * yy * (zratio - 1.0)
        az += f * z * (zratio - 3.0)
        return [ax, ay, az]

    def _space_guidance_state(self) -> list[float]:
        """Return the onboard estimate used by spacecraft guidance and attitude."""
        if self.space_navigation is not None:
            return list(self.space_navigation.x)
        return list(self.orbit)

    def _space_derivative(self, y: list[float], thrust_accel: float | None = None,
                          _unused: float | None = None,
                          thrust_accel_eci_m_s2: list[float] | None = None,
                          mass_kg_override: float | None = None) -> list[float]:
        x, yy, z, vx, vy, vz = y
        r = max(_norm3([x, yy, z]), 1.0)
        ax, ay, az = self._gravity_eci_acceleration([x, yy, z])
        if self.science:
            perturbation = self.science.gravity([x, yy, z])
            ax += perturbation[0]
            ay += perturbation[1]
            az += perturbation[2]
        altitude = r - EARTH_RADIUS
        if self.scenario in {"mission", "leo-return"}:
            # Static COESA76 reference atmosphere, including thermosphere data.
            atmosphere = atmosphere_isa(altitude)
            density = atmosphere["density_kg_m3"]
            if self.phase == "PARACHUTE":
                cd_area = (self.launch_vehicle["parachute_Cd"] *
                           self.launch_vehicle["parachute_area_m2"])
            elif self.phase == "DROGUE":
                cd_area = (self.launch_vehicle["drogue_Cd"] *
                           self.launch_vehicle["drogue_area_m2"])
            elif self.phase == "AEROSHELL":
                cd_area = (self.launch_vehicle["aeroshell_Cd"] *
                           self.launch_vehicle["aeroshell_area_m2"])
            else:
                cd_area = self.launch_vehicle["Cd"] * self.launch_vehicle["area_m2"]
            v_atm = [-OMEGA_EARTH * yy, OMEGA_EARTH * x, 0.0]
            vrel = [vx-v_atm[0], vy-v_atm[1], vz-v_atm[2]]
            speed_rel = _norm3(vrel)
            mass = max(self.mass_kg if mass_kg_override is None else mass_kg_override,
                       self.mass_dry_kg, 1.0)
            dynamic_pressure = 0.5 * density * speed_rel * speed_rel
            if self.phase in {"AEROSHELL", "DROGUE", "PARACHUTE"} and dynamic_pressure > 0.0:
                # Cap the added canopy load while retaining the capsule body drag.
                max_cd_area = 6.0 * G0 * mass / dynamic_pressure
                body_cd_area = self.launch_vehicle["Cd"] * self.launch_vehicle["area_m2"]
                cd_area = max(body_cd_area, min(cd_area, max_cd_area))
            drag_scale = -0.5 * density * cd_area * speed_rel / mass
            ax += drag_scale*vrel[0]
            ay += drag_scale*vrel[1]
            az += drag_scale*vrel[2]
        if thrust_accel_eci_m_s2 is not None:
            ax += thrust_accel_eci_m_s2[0]
            ay += thrust_accel_eci_m_s2[1]
            az += thrust_accel_eci_m_s2[2]
        elif thrust_accel is None:
            throttle = self.command["throttle_pct"] / 100.0
            if throttle > 0.0 and self.propellant_kg > 0.0:
                rhat = [x / r, yy / r, z / r]
                hv = [yy * vz - z * vy, z * vx - x * vz, x * vy - yy * vx]
                hn = max(_norm3(hv), 1.0)
                hhat = [v / hn for v in hv]
                that = [hhat[1]*rhat[2]-hhat[2]*rhat[1],
                        hhat[2]*rhat[0]-hhat[0]*rhat[2],
                        hhat[0]*rhat[1]-hhat[1]*rhat[0]]
                roll = math.radians(self.command["roll_deg"])
                pitch = math.radians(self.command["pitch_deg"])
                thrust = self._thrust_at_altitude(altitude)
                mass = self.mass_kg if mass_kg_override is None else mass_kg_override
                accel = throttle * thrust / max(mass, 1.0)
                direction = [that[i]*math.cos(pitch)*math.cos(roll)
                             + rhat[i]*math.sin(pitch)
                             + hhat[i]*math.sin(roll) for i in range(3)]
                ax += accel * direction[0]
                ay += accel * direction[1]
                az += accel * direction[2]
        else:
            ax += thrust_accel
        return [vx, vy, vz, ax, ay, az]

    def _prepare_launch_attitude_sample(self, time_s: float) -> None:
        """Sample launch GNC at a fixed 20 Hz, independent of RK4 refinement."""
        attitude = self.launch_vehicle_attitude
        if attitude is None:
            return
        if (self._launch_attitude_sample_next_s is not None and
                time_s < self._launch_attitude_sample_next_s-1e-10):
            return
        period = self.launch_attitude_update_period_s
        start = copy.deepcopy(attitude)
        guidance_state = self._space_guidance_state()
        if self.command.get("sas_enabled") and self.command["mode"] != "auto" and not getattr(self,"_local_sas_override",False):
            mode=self.command.get("attitude_sas_mode")
            if mode not in {"stability_assist","manual","lvlh"}:
                direction=self._launch_sas_vectors().get(mode)
                if direction is None:
                    self.command["attitude_sas_mode"]="stability_assist"
                else:
                    radial,tangent,normal,_=attitude._local_frame(guidance_state[:3],guidance_state[3:])
                    up=sum(a*b for a,b in zip(radial,direction))
                    forward=sum(a*b for a,b in zip(tangent,direction))
                    side=sum(a*b for a,b in zip(normal,direction))
                    self.command["pitch_deg"]=math.degrees(math.asin(_clamp(up,-1.,1.)))
                    self.command["roll_deg"]=math.degrees(math.atan2(side,forward))
        altitude = _norm3(guidance_state[:3])-EARTH_RADIUS
        thrust_N = (self.command["throttle_pct"]/100.0 *
                    self._thrust_at_altitude(altitude))
        midpoint = copy.deepcopy(start)
        midpoint.step(0.5*period, guidance_state[:3], guidance_state[3:], MU_EARTH,
                      self.mass_kg, thrust_N, self.command["pitch_deg"],
                      self.command["roll_deg"],
                      rcs_propellant_kg=self.acs_propellant_kg)
        endpoint = copy.deepcopy(start)
        rcs_used = endpoint.step(
            period, guidance_state[:3], guidance_state[3:], MU_EARTH,
            self.mass_kg, thrust_N, self.command["pitch_deg"],
            self.command["roll_deg"],
            rcs_propellant_kg=self.acs_propellant_kg)
        self._launch_attitude_sample_start_s = time_s
        self._launch_attitude_sample_next_s = time_s+period
        self._launch_attitude_sample_start = start
        self._launch_attitude_sample_mid = midpoint
        self._launch_attitude_sample_end = endpoint
        self._launch_attitude_sample_direction_eci = midpoint.thrust_direction_eci()
        self._launch_attitude_sample_rcs_used_kg = rcs_used
        self._launch_attitude_sample_rcs_applied_kg = 0.0

    def _advance_launch_attitude_sample(self, time_s: float) -> None:
        """Interpolate the sampled attitude plant state between 20 Hz updates."""
        start = self._launch_attitude_sample_start
        endpoint = self._launch_attitude_sample_end
        start_time = self._launch_attitude_sample_start_s
        if start is None or endpoint is None or start_time is None:
            return
        fraction = _clamp((time_s-start_time)/self.launch_attitude_update_period_s,
                          0.0, 1.0)
        q0 = start.quaternion_body_to_eci
        q1 = endpoint.quaternion_body_to_eci[:]
        if sum(a*b for a, b in zip(q0, q1)) < 0.0:
            q1 = [-value for value in q1]
        quaternion = [(1.0-fraction)*a+fraction*b for a, b in zip(q0, q1)]
        qnorm = math.sqrt(sum(value*value for value in quaternion))
        quaternion = ([1.0, 0.0, 0.0, 0.0] if qnorm <= 1e-15 else
                      [value/qnorm for value in quaternion])
        sample = copy.copy(endpoint)
        sample.quaternion_body_to_eci = quaternion
        sample.body_rates_rad_s = [
            (1.0-fraction)*a+fraction*b
            for a, b in zip(start.body_rates_rad_s, endpoint.body_rates_rad_s)]
        sample.gimbal_angles_rad = [
            (1.0-fraction)*a+fraction*b
            for a, b in zip(start.gimbal_angles_rad, endpoint.gimbal_angles_rad)]
        sample.attitude_error_deg = (
            (1.0-fraction)*start.attitude_error_deg+
            fraction*endpoint.attitude_error_deg)
        rcs_target = fraction*self._launch_attitude_sample_rcs_used_kg
        rcs_increment = max(
            0.0, rcs_target-self._launch_attitude_sample_rcs_applied_kg)
        self._launch_attitude_sample_rcs_applied_kg = rcs_target
        sample.rcs_propellant_used_kg = rcs_increment
        self.acs_propellant_kg = max(0.0, self.acs_propellant_kg-rcs_increment)
        self.mission_metrics["acs_propellant_used_kg"] += rcs_increment
        self.mass_kg = (self.mass_dry_kg+self.propellant_kg+
                        self.acs_propellant_kg)
        self.launch_vehicle_attitude = sample

    def _space_stagnation_heat_flux_W_m2(self, state: list[float]) -> float:
        """Estimate cold-wall Earth convective heating at the stagnation point.

        The Sutton–Graves correlation is used for the modeled blunt-body entry
        phase only. This does not compute radiative heating, wall temperature,
        ablation, or heat-shield response.
        """
        if (self.scenario not in {"mission", "leo-return"}
                or self.phase not in {"REENTRY", "DEORBIT_COAST", "AEROSHELL"}
                or not hasattr(self, "launch_vehicle")):
            return 0.0
        radius_m = _norm3(state[:3])
        nose_radius_m = self.launch_vehicle["nose_radius_m"]
        if radius_m <= EARTH_RADIUS or nose_radius_m <= 0.0:
            return 0.0
        atmosphere = atmosphere_isa(radius_m-EARTH_RADIUS)
        density = atmosphere["density_kg_m3"]
        if density <= 0.0:
            return 0.0
        x, y, _z, vx, vy, vz = state
        air_velocity = [vx+OMEGA_EARTH*y, vy-OMEGA_EARTH*x, vz]
        relative_speed_m_s = _norm3(air_velocity)
        return (SUTTON_GRAVES_EARTH * math.sqrt(density/nose_radius_m)
                * relative_speed_m_s**3)

    def _relative_rtn_state(self) -> tuple[list[float], list[float], list[list[float]]]:
        """Return spacecraft-target position and velocity in the target RTN frame.

        The relative velocity subtracts the rotation of the target-centred frame,
        so it is suitable for Hill/Clohessy-Wiltshire guidance.
        """
        target_r = self.target_orbit[:3]
        target_v = self.target_orbit[3:]
        target_radius = max(_norm3(target_r), 1.0)
        radial = [component/target_radius for component in target_r]
        angular_momentum = [target_r[1]*target_v[2]-target_r[2]*target_v[1],
                            target_r[2]*target_v[0]-target_r[0]*target_v[2],
                            target_r[0]*target_v[1]-target_r[1]*target_v[0]]
        angular_momentum_norm = max(_norm3(angular_momentum), 1.0)
        normal = [component/angular_momentum_norm for component in angular_momentum]
        transverse = [normal[1]*radial[2]-normal[2]*radial[1],
                      normal[2]*radial[0]-normal[0]*radial[2],
                      normal[0]*radial[1]-normal[1]*radial[0]]
        axes = [radial, transverse, normal]
        delta_r = [self.orbit[i]-target_r[i] for i in range(3)]
        delta_v = [self.orbit[i+3]-target_v[i] for i in range(3)]
        angular_rate = angular_momentum_norm/target_radius**2
        frame_rate = [angular_rate*component for component in normal]
        rotating_velocity = [delta_v[i] - (frame_rate[1]*delta_r[2]-frame_rate[2]*delta_r[1])
                             if i == 0 else
                             delta_v[i] - (frame_rate[2]*delta_r[0]-frame_rate[0]*delta_r[2])
                             if i == 1 else
                             delta_v[i] - (frame_rate[0]*delta_r[1]-frame_rate[1]*delta_r[0])
                             for i in range(3)]
        position_rtn = [sum(delta_r[i]*axis[i] for i in range(3)) for axis in axes]
        velocity_rtn = [sum(rotating_velocity[i]*axis[i] for i in range(3)) for axis in axes]
        return position_rtn, velocity_rtn, axes

    def _guide_orbital_rendezvous(self) -> None:
        """Saturated CW PD guidance to a 20 m trailing station-keeping point."""
        truth_position, truth_velocity, axes = self._relative_rtn_state()
        if self.relative_navigation is not None:
            estimate = self.relative_navigation.report()
            position = list(estimate["position_rtn_m"])
            velocity = list(estimate["velocity_rtn_m_s"])
        else:
            position, velocity = truth_position, truth_velocity
        target = self.rendezvous_target_rtn_m
        error = [position[i]-target[i] for i in range(3)]
        target_radius = max(_norm3(self.target_orbit[:3]), 1.0)
        mean_motion = math.sqrt(MU_EARTH/target_radius**3)
        kp = self.rendezvous_guidance_state["position_gain_s2"]
        kd = self.rendezvous_guidance_state["velocity_gain_s"]
        acceleration_rtn = [
            -kp*error[0] - kd*velocity[0] - 2.0*mean_motion*velocity[1]
            - 3.0*mean_motion**2*position[0],
            -kp*error[1] - kd*velocity[1] + 2.0*mean_motion*velocity[0],
            -kp*error[2] - kd*velocity[2] + mean_motion**2*position[2],
        ]
        if self.science:
            acceleration_rtn = self.science.rendezvous_acceleration(
                self, position, velocity, axes, target)
        requested = _norm3(acceleration_rtn)
        acceleration_limit = min(
            self.rendezvous_guidance_state["maximum_acceleration_m_s2"],
            self.max_thrust_N/max(self.mass_kg, 1.0))
        if self.propellant_kg <= 0.0:
            self.fault = "RENDEZVOUS_PROPELLANT_DEPLETED"
            self.phase = "ABORTED"
            acceleration_rtn = [0.0, 0.0, 0.0]
            requested = 0.0
        elif requested > acceleration_limit > 0.0:
            acceleration_rtn = [value*acceleration_limit/requested
                                for value in acceleration_rtn]
            requested = acceleration_limit
        acceleration_eci = [sum(acceleration_rtn[axis]*axes[axis][component]
                                for axis in range(3)) for component in range(3)]
        self.rendezvous_acceleration_eci_m_s2 = acceleration_eci
        self.command["throttle_pct"] = (
            100.0*requested*self.mass_kg/self.max_thrust_N
            if self.propellant_kg > 0.0 and self.max_thrust_N > 0.0 else 0.0)
        self.command["pitch_deg"] = math.degrees(math.asin(
            _clamp(acceleration_rtn[0]/max(requested, 1e-12), -1.0, 1.0))) if requested > 0.0 else 0.0
        self.command["roll_deg"] = math.degrees(math.asin(
            _clamp(acceleration_rtn[2]/max(requested, 1e-12), -1.0, 1.0))) if requested > 0.0 else 0.0
        self.command["yaw_deg"] = 0.0
        position_error = _norm3(error)
        relative_speed = _norm3(velocity)
        truth_position_error = _norm3([truth_position[i]-target[i] for i in range(3)])
        truth_relative_speed = _norm3(truth_velocity)
        self.mission_metrics["rendezvous_hold_error_m"] = truth_position_error
        if (self.phase == "RENDEZVOUS" and position_error <= 3.0
                and relative_speed <= 0.05):
            self.phase = "STATION_KEEPING"
        self.rendezvous_guidance_state.update({
            "active": True,
            "phase": self.phase,
            "target_relative_position_rtn_m": list(target),
            "relative_position_rtn_m": position,
            "relative_velocity_rtn_m_s": velocity,
            "truth_relative_position_rtn_m": truth_position,
            "truth_relative_velocity_rtn_m_s": truth_velocity,
            "truth_position_error_m": truth_position_error,
            "truth_relative_speed_m_s": truth_relative_speed,
            "navigation_estimate": (self.relative_navigation.report()
                                     if self.relative_navigation is not None else None),
            "position_error_m": position_error,
            "relative_speed_m_s": relative_speed,
            "commanded_acceleration_rtn_m_s2": acceleration_rtn,
            "commanded_acceleration_eci_m_s2": acceleration_eci,
            "actuator_saturated": requested >= acceleration_limit-1e-10,
            "propellant_remaining_kg": self.propellant_kg,
        })

    def _rendezvous_telemetry(self) -> dict[str, Any]:
        position, velocity, _axes = self._relative_rtn_state()
        navigation_estimate = (self.relative_navigation.report()
                               if self.relative_navigation is not None else None)
        return {
            "relative_position_rtn_m": position,
            "relative_velocity_rtn_m_s": velocity,
            "relative_range_m": _norm3(position),
            "relative_speed_m_s": _norm3(velocity),
            "relative_navigation_estimate": navigation_estimate,
            "rendezvous_guidance": {
                **self.rendezvous_guidance_state,
                "active": (self.command["mode"] == "auto"
                           and self.phase in {"RENDEZVOUS", "STATION_KEEPING"}),
                "phase": self.phase,
                "target_relative_position_rtn_m": list(self.rendezvous_target_rtn_m),
                "control_mode": self.command["mode"],
                "propellant_remaining_kg": self.propellant_kg,
            },
        }

    def _spacecraft_attitude_telemetry(self) -> dict[str, Any]:
        if self.launch_vehicle_attitude is not None:
            telemetry = self.launch_vehicle_attitude.telemetry(self.command["mode"])
            telemetry["attitude_control"]["update_period_s"] = (
                self.launch_attitude_update_period_s)
            telemetry["attitude_control"]["update_rate_hz"] = (
                1.0/self.launch_attitude_update_period_s)
            return telemetry
        if self.spacecraft_attitude is None:
            return {"attitude_deg": None,
                    "attitude_state_status": "NOT_MODELLED"}
        control_mode = self._effective_sas_mode()
        telemetry = self.spacecraft_attitude.telemetry(control_mode)
        telemetry["attitude_target_deg"] = list(self.command["attitude_target_deg"])
        return {
            **telemetry,
            "attitude_state_status": "MODELLED_3DOF_RIGID_BODY",
        }

    def _set_specific_force_body(self, specific_force_body_m_s2: list[float]) -> None:
        self.specific_force_body_m_s2 = list(specific_force_body_m_s2)
        self.load_factor_g = _norm3(self.specific_force_body_m_s2)/G0

    def _update_atmospheric_specific_force(self) -> None:
        derivative = self._flight_derivative(self.flight)
        _n, _east, _down, u, v, w, phi, theta, _psi, p, q, r = self.flight[:12]
        gravity_body = [-G0*math.sin(theta),
                        G0*math.sin(phi)*math.cos(theta),
                        G0*math.cos(phi)*math.cos(theta)]
        # In body coordinates, v_dot = F/m + g - omega x v.
        self._set_specific_force_body([
            derivative[3]-gravity_body[0]+q*w-r*v,
            derivative[4]-gravity_body[1]+r*u-p*w,
            derivative[5]-gravity_body[2]+p*v-q*u,
        ])

    def _set_specific_force_eci(self, specific_force_eci_m_s2: list[float]) -> None:
        if self.launch_vehicle_attitude is not None:
            specific_body = self.launch_vehicle_attitude.vector_eci_to_body(
                specific_force_eci_m_s2)
        elif self.spacecraft_attitude is not None:
            specific_body = self.spacecraft_attitude.vector_eci_to_body(
                specific_force_eci_m_s2)
        else:
            specific_body = specific_force_eci_m_s2
        self._set_specific_force_body(specific_body)

    def _thrust_at_altitude(self, altitude_m: float) -> float:
        """Apply the nozzle pressure-thrust correction in the atmosphere."""
        if self.science:
            reference = self.science.thrust_reference(self, altitude_m)
            if reference is not None:
                return reference
        ambient_pressure = (atmosphere_isa(altitude_m)["pressure_Pa"]
                            if self.scenario in {"mission", "leo-return"} else 0.0)
        return max(0.0, self.max_thrust_N - ambient_pressure * self.nozzle_exit_area_m2)

    def _enforce_space_launch_pad_contact(self) -> None:
        """Keep a non-lifting launch stack on the rotating pad surface."""
        if (self.vehicle != "space" or self.scenario == "orbital" or
                self.phase != "ASCENT" or self.launch_vehicle_attitude is None):
            return
        pad_radius_m = EARTH_RADIUS+1.5
        radius_m = _norm3(self.orbit[:3])
        if radius_m >= pad_radius_m or radius_m <= 0.0:
            return
        radial_unit = [value/radius_m for value in self.orbit[:3]]
        self.orbit[:3] = [value*pad_radius_m for value in radial_unit]
        radial_speed_m_s = sum(self.orbit[3+i]*radial_unit[i] for i in range(3))
        if radial_speed_m_s < 0.0:
            for i in range(3):
                self.orbit[3+i] -= radial_speed_m_s*radial_unit[i]

    def _burn_mass(self, dt_s: float,
                   event_time_s: float | None = None) -> None:
        throttle = self.command["throttle_pct"] / 100.0
        if throttle <= 0.0 or self.propellant_kg <= 0.0 or self.isp_s <= 0.0:
            return
        # Keep propellant flow tied to the vacuum engine rating. The ambient
        # pressure correction belongs in effective thrust only; scaling mass
        # flow by corrected thrust would incorrectly lengthen the burn.
        mass_flow = (throttle*self.max_thrust_N*self._engine_availability() /
                     (self.isp_s*G0))
        used = min(self.propellant_kg, mass_flow*dt_s)
        if self.stage_specs:
            stage_fuel = self.stage_propellant_kg[self.active_stage_index]
            used = min(stage_fuel, used)
            self.stage_propellant_kg[self.active_stage_index] = max(0.0, stage_fuel-used)
            self.propellant_kg = sum(self.stage_propellant_kg)
            self.mass_kg = (self.mass_dry_kg+self.propellant_kg+
                            self.acs_propellant_kg)
            if self.stage_propellant_kg[self.active_stage_index] <= 1e-8:
                self.stage_propellant_kg[self.active_stage_index] = 0.0
                self.propellant_kg = sum(self.stage_propellant_kg)
                self.mass_kg = (self.mass_dry_kg+self.propellant_kg+
                                self.acs_propellant_kg)
                self._separate_spent_stage(self.t+dt_s if event_time_s is None else event_time_s)
        else:
            self.propellant_kg = max(0.0, self.propellant_kg-used)
            self.mass_kg = (self.mass_dry_kg+self.propellant_kg+
                            self.acs_propellant_kg)

    @staticmethod
    def _body_to_ned(phi: float, theta: float, psi: float) -> list[list[float]]:
        cp, sp = math.cos(phi), math.sin(phi)
        ct, st = math.cos(theta), math.sin(theta)
        cy, sy = math.cos(psi), math.sin(psi)
        return [[ct*cy, sp*st*cy-cp*sy, cp*st*cy+sp*sy],
                [ct*sy, sp*st*sy+cp*cy, cp*st*sy-sp*cy],
                [-st, sp*ct, cp*ct]]

    def _aircraft_surface_actuators(self, y: list[float]
                                    ) -> tuple[list[float], list[float]]:
        """Return commanded surface angles and rate-limited servo derivatives."""
        a = self.aero
        phi, theta, psi, p, q, r = y[6:12]
        actual = y[12:15]
        roll_error = math.radians(self.command["roll_deg"]) - phi
        # Ground-run rotation schedule: a neutral manual pitch stick means
        # "rotate at Vr", not "hold an exactly level nose forever". This
        # preserves full 6-DoF aerodynamics while avoiding an impossible
        # takeoff with zero angle of attack. A deliberate nose-down command
        # overrides assistance; an early large pull is capped by the gear
        # rotation envelope so it cannot create excessive induced drag at
        # taxi speeds. External Python control remains fully explicit.
        requested_pitch_deg = self.command["pitch_deg"]
        if (self.command["mode"] == "manual" and
                self.phase == "TAKEOFF" and not self.aircraft_airborne):
            vr = self.vehicle_model["takeoff_speed_m_s"]
            airspeed = _norm3(self._air_relative_velocity_body(y))
            fraction = _clamp((airspeed - .88*vr)/(.12*vr), 0.0, 1.0)
            rotation_limit = 11.5*fraction
            if self.command["throttle_pct"] >= 65.0:
                self.manual_takeoff_assist_engaged = True
                if abs(requested_pitch_deg) < 0.25:
                    requested_pitch_deg = rotation_limit
                elif requested_pitch_deg > 0.0:
                    requested_pitch_deg = min(requested_pitch_deg, rotation_limit)
        elif (self.command["mode"] == "manual" and self.phase == "CLIMB"
              and self.manual_takeoff_assist_engaged):
            # The manual joystick is a neutral-centering device. Retain a
            # shallow, controlled climb on release immediately after rotation;
            # otherwise switching from +11 deg to 0 deg causes a ground
            # strike within seconds. A nose-down pilot command disengages.
            if requested_pitch_deg < -0.5:
                self.manual_takeoff_assist_engaged = False
            elif abs(requested_pitch_deg) < 0.25:
                # Hold a positive climb flight path using the lift balance at
                # the instantaneous true airspeed. Aircraft with high wing
                # loading need noticeably more pitch than light trainers.
                airspeed = max(_norm3(self._air_relative_velocity_body(y)), 1.0)
                density = atmosphere_isa(max(-y[2], 0.0))["density_kg_m3"]
                qbar = 0.5*density*airspeed**2
                required_cl = (y[-2]*G0/max(qbar*self.aero["S_m2"],1.0))
                alpha_trim = ((required_cl-self.aero["CL0"])/
                              self.aero["CLalpha_rad"])
                requested_pitch_deg = _clamp(
                    math.degrees(alpha_trim)+3.0, 6.0, 13.0)
        pitch_error = math.radians(requested_pitch_deg) - theta
        heading_error = ((math.radians(self.command["yaw_deg"])-psi+math.pi)
                         % (2.0*math.pi)-math.pi)
        air_velocity = self._air_relative_velocity_body(y)
        alpha = math.atan2(air_velocity[2], max(abs(air_velocity[0]), 0.1))
        static_pitch_moment = (
            float(a.get("Cm0", 0.0))
            + float(a.get("Cm_alpha_per_rad", 0.0))*alpha)
        elevator_trim = -static_pitch_moment/max(
            float(a.get("Cm_delta_e_at_max_deflection", 1.05)), 1e-9)
        # In manual/code flight, favor a better damped attitude servo.
        # This modifies only commanded actuator surfaces, never the aero model;
        # the automatic mission controller retains its calibrated gains.
        manual = self.command["mode"] != "auto"
        roll_kp, roll_kd = (1.2, 2.5) if manual else (0.65, 0.9)
        normalized = [
            _clamp(roll_kp*roll_error-roll_kd*p, -1.0, 1.0),
            _clamp(0.7*pitch_error-q+elevator_trim, -1.0, 1.0),
            _clamp(0.45*heading_error-0.7*r, -1.0, 1.0),
        ]
        names = ("aileron", "elevator", "rudder")
        targets = [normalized[i]*a[f"{name}_max_deflection_rad"]
                   for i, name in enumerate(names)]
        rates = [
            _clamp((targets[i]-actual[i])/a[f"{name}_time_constant_s"],
                   -a[f"{name}_rate_limit_rad_s"],
                   a[f"{name}_rate_limit_rad_s"])
            for i, name in enumerate(names)
        ]
        if self.science:
            rates = [v*self.science.control_power_factor for v in rates]
        return targets, rates

    def _flight_derivative(self, y: list[float]) -> list[float]:
        north, east, down, u, v, w, phi, theta, psi, p, q, r = y[:12]
        mass, fuel = y[-2:]
        air_velocity = self._air_relative_velocity_body(y)
        air_u, air_v, air_w = air_velocity
        speed = max(_norm3(air_velocity), 0.1)
        altitude = max(-down, -500.0)
        atm = atmosphere_isa(altitude)
        throttle = self.command["throttle_pct"] / 100.0
        if self.vehicle == "drone" and self.battery_energy_Wh <= 0.0:
            throttle = 0.0
        if self.vehicle == "aircraft":
            a = self.aero
            alpha = math.atan2(air_w, max(abs(air_u), 0.1))
            beta = math.asin(_clamp(air_v/speed, -0.99, 0.99))
            qbar = 0.5 * atm["density_kg_m3"] * speed * speed
            coefficients = fixed_wing_coefficients(
                a, alpha, beta, mach=speed/max(1.0, atm["speed_of_sound_m_s"]))
            _surface_targets, surface_rates = self._aircraft_surface_actuators(y)
            cl, cd = coefficients["CL"], coefficients["CD"]
            if self.science:
                cl += self.science.aero_delta_cl
                mach = speed/max(1., atm['speed_of_sound_m_s'])
                cd += min(.15, .8*max(0., mach-.72)**2)
            drag = qbar * a["S_m2"] * cd
            lift = qbar * a["S_m2"] * cl
            side = qbar * a["S_m2"] * coefficients["CY"]
            fx_aero = -drag * math.cos(alpha) + lift * math.sin(alpha)
            fz_aero = -drag * math.sin(alpha) - lift * math.cos(alpha)
            moment_coefficients = fixed_wing_moment_coefficients(
                a, alpha, beta, (p, q, r), speed, y[12:15])
            moments = [qbar*a["S_m2"]*a["b_m"]*moment_coefficients["Cl"],
                       qbar*a["S_m2"]*a["c_m"]*moment_coefficients["Cm"],
                       qbar*a["S_m2"]*a["b_m"]*moment_coefficients["Cn"]]
            inertia = (a["Ixx_kgm2"], a["Iyy_kgm2"], a["Izz_kgm2"])
            engine_power_fraction = _clamp(float(y[15]), 0.0, 1.0)
            propulsion = self._aircraft_propulsion_state(y)
            engine_target = throttle if fuel > 0.0 else 0.0
            engine_power_rate = (
                engine_target-engine_power_fraction)/self.aircraft_powertrain[
                    "spool_time_constant_s"]
            engine_force = propulsion["thrust_N"] if fuel > 0.0 else 0.0
            force = [fx_aero + engine_force, side, fz_aero]
            fuel_dot = -propulsion["fuel_flow_kg_s"] if fuel > 0.0 else 0.0
        else:
            propulsion = self._drone_propulsion_state(y)
            rotor_phase_rates = [speed*rotor["spin_direction"]
                                 for speed, rotor in zip(
                                     propulsion["actual_speeds_rad_s"],
                                     self.rotor_geometry)]
            inertia = (self.drone["Ixx_kgm2"], self.drone["Iyy_kgm2"], self.drone["Izz_kgm2"])
            moments = propulsion["actual_wrench_N_Nm"][1:]
            # Rotor thrust plus body-axis parasitic drag.
            drag_factor = (0.5 * atm["density_kg_m3"] *
                           self.drone["body_drag_area_m2"] * speed)
            force = [-drag_factor*air_u, -drag_factor*air_v,
                     -propulsion["actual_wrench_N_Nm"][0]-drag_factor*air_w]
            fuel_dot = 0.0
            surface_rates = propulsion["motor_speed_rates_rad_s2"]
        g_body = [-G0*math.sin(theta), G0*math.sin(phi)*math.cos(theta),
                  G0*math.cos(phi)*math.cos(theta)]
        udot = force[0]/mass + g_body[0] - q*w + r*v
        vdot = force[1]/mass + g_body[1] - r*u + p*w
        wdot = force[2]/mass + g_body[2] - p*v + q*u
        dcm = self._body_to_ned(phi, theta, psi)
        ground_velocity_ned = self._ned_velocity(y)
        on_ground = down >= -0.01 and ground_velocity_ned[2] >= -0.2
        if on_ground:
            if self.vehicle == "aircraft":
                # Wheel contact resists lateral sideslip while accelerating
                # along the north-aligned runway. Without a tire side force,
                # a small crosswind displaces a parked airplane hundreds of
                # metres sideways, even while the gear is on the asphalt.
                # Keep lateral tire acceleration bounded (wet runway proxy).
                # This applies only while the weight is supported by gear.
                lateral_accel = _clamp(-2.8*ground_velocity_ned[1], -4.0, 4.0)
                for axis in range(3):
                    accel = lateral_accel*dcm[1][axis]
                    if axis == 0:
                        udot += accel
                    elif axis == 1:
                        vdot += accel
                    else:
                        wdot += accel
                # Rolling and braking oppose horizontal ground motion in NED.
                horizontal_speed = math.hypot(ground_velocity_ned[0],
                                               ground_velocity_ned[1])
                if horizontal_speed > 1e-5:
                    rolling_accel = min(
                        6.0, (0.025 + 0.45*self.command["brakes_pct"]/100.0)*G0)
                    rolling_ned = [
                        -rolling_accel*ground_velocity_ned[0]/horizontal_speed,
                        -rolling_accel*ground_velocity_ned[1]/horizontal_speed,
                        0.0,
                    ]
                    rolling_body = [
                        sum(dcm[ned_axis][body_axis]*rolling_ned[ned_axis]
                            for ned_axis in range(3))
                        for body_axis in range(3)
                    ]
                    udot += rolling_body[0]
                    vdot += rolling_body[1]
                    wdot += rolling_body[2]
            # A unilateral gear normal acts vertically in NED, then transforms
            # into all three body axes so pitch cannot create false wheel drag.
            ned_down_accel = dcm[2][0]*udot + dcm[2][1]*vdot + dcm[2][2]*wdot
            if ned_down_accel > 0.0:
                normal_body = [-ned_down_accel*dcm[2][axis]
                               for axis in range(3)]
                udot += normal_body[0]
                vdot += normal_body[1]
                wdot += normal_body[2]
        ix, iy, iz = inertia
        pdot = (moments[0] + (iy-iz)*q*r) / ix
        qdot = (moments[1] + (iz-ix)*r*p) / iy
        rdot = (moments[2] + (ix-iy)*p*q) / iz
        ct = math.cos(theta)
        if abs(ct) < 0.08:
            ct = math.copysign(0.08, ct)
        tan_theta = math.sin(theta) / ct
        phidot = p + tan_theta*(q*math.sin(phi)+r*math.cos(phi))
        thetadot = q*math.cos(phi)-r*math.sin(phi)
        psidot = (q*math.sin(phi)+r*math.cos(phi))/ct
        ned_velocity = [sum(dcm[i][j]*vbody for j, vbody in enumerate((u,v,w)))
                        for i in range(3)]
        if on_ground and ned_velocity[2] > 0.0:
            ned_velocity[2] = 0.0
        phase_rates = rotor_phase_rates if self.vehicle == "drone" else []
        aircraft_power_rates = ([engine_power_rate]
                                if self.vehicle == "aircraft" else [])
        # Taylor's frozen-field hypothesis: the NED along-path coordinate
        # advances with speed relative to the mean air mass; turbulent velocity
        # itself does not advect the vehicle through its own frozen field.
        mean_wind = self._mean_wind_velocity_ned(y)
        mean_air_velocity_ned = [ground_velocity_ned[i]-mean_wind[i]
                                 for i in range(3)]
        path_rate_m_s = _norm3(mean_air_velocity_ned)
        return [*ned_velocity, udot, vdot, wdot, phidot, thetadot, psidot,
                pdot, qdot, rdot, *surface_rates, *phase_rates,
                *aircraft_power_rates, path_rate_m_s, fuel_dot, fuel_dot]

    def _orbital_elements(self, state_eci: list[float] | None = None) -> dict[str, Any]:
        x, y, z, vx, vy, vz = self.orbit if state_eci is None else state_eci
        r, v = [x,y,z], [vx,vy,vz]
        rn, vn = _norm3(r), _norm3(v)
        h = [y*vz-z*vy, z*vx-x*vz, x*vy-y*vx]
        hn = _norm3(h)
        evec = [((vy*h[2]-vz*h[1])/MU_EARTH)-x/rn,
                ((vz*h[0]-vx*h[2])/MU_EARTH)-y/rn,
                ((vx*h[1]-vy*h[0])/MU_EARTH)-z/rn]
        eccentricity = _norm3(evec)
        energy = 0.5*vn*vn-MU_EARTH/rn
        sma = -MU_EARTH/(2*energy) if energy < 0 else None
        period = 2*math.pi*math.sqrt(sma**3/MU_EARTH) if sma is not None else None
        periapsis = hn*hn/MU_EARTH/(1.0+eccentricity) if hn > 0.0 else rn
        apoapsis = sma*(1.0+eccentricity) if sma is not None else None
        inc = math.degrees(math.acos(_clamp(h[2]/max(hn, 1.0), -1, 1)))
        if abs(eccentricity - 1.0) <= 1e-8:
            conic_type = "PARABOLIC"
            orbit_type = "PARABOLIC_ESCAPE"
        elif eccentricity < 1.0:
            conic_type = "ELLIPTIC"
            if periapsis - EARTH_RADIUS <= 0.0:
                orbit_type = "SUBORBITAL"
            elif apoapsis is not None and apoapsis - EARTH_RADIUS <= 2_000_000.0:
                orbit_type = "LEO"
            else:
                orbit_type = "ELLIPTIC_EARTH_ORBIT"
        else:
            conic_type = "HYPERBOLIC"
            orbit_type = "ESCAPE"
        return {"semi_major_axis_m": sma, "eccentricity": eccentricity,
                "conic_type": conic_type, "orbit_type": orbit_type,
                "inclination_deg": inc, "specific_orbital_energy_J_kg": energy,
                "period_s": period,
                "periapsis_altitude_m": periapsis-EARTH_RADIUS,
                "apoapsis_altitude_m": apoapsis-EARTH_RADIUS if apoapsis is not None else None}

    def configure_route(self, plan: dict[str, Any]) -> dict[str, Any]:
        if self.vehicle != "drone" or self.mission_started:
            raise ValueError("Select a ready UAV mission before applying the route")
        self.mission_route = MissionRoute(plan)
        return self.state()

    def configure_systems(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.mission_started:
            raise ValueError("Reset the mission before changing subsystem assumptions")
        candidate = LiveSystems(payload)
        candidate.advance(self, 0.0, self.t)
        self.live_systems = candidate
        return self.state()

    def state(self) -> dict[str, Any]:
        if self.planetary is not None:
            result = self.planetary.state()
            result.update(version=__version__,vehicle='space',scenario='planetary',phase=self.phase,
                time_s=self.t,mission_started=self.mission_started,command=dict(self.command),
                model_id='astra-lunar-lander',vehicle_name='ASTRA Lunar Lander',
                frame='LOCAL_ENU',propellant_pct=100*self.propellant_kg/self.propellant_capacity_kg,
                load_factor_g=self.load_factor_g,mission_metrics=dict(self.mission_metrics),
                fault=self.fault,model='LIVE_LUNAR_6DOF_VARIABLE_INERTIA_RK4',
                science=self.science.snapshot() if self.science else {'enabled':False})
            result['sas'] = self._sas_state()
            return result
        result = self._flight_state()
        result['sas'] = self._sas_state()
        if not self.live_systems.snapshot():
            self.live_systems.advance(self, 0.0, self.t)
        result["live_systems"] = self.live_systems.snapshot()
        if self.mission_route is not None:
            result["mission_route"] = self.mission_route.snapshot()
        result['science'] = self.science.snapshot() if self.science else {'enabled':False}
        if self.science and self.vehicle == 'aircraft':
            aero = result['aerodynamics']
            aero['model'] = 'CONVECTIVE_LIFT_LAG_NONLINEAR_POLAR_EMPIRICAL_WAVE_DRAG'
            aero['lift_coefficient'] += self.science.aero_delta_cl
            mach = result['air_relative_speed_m_s']/max(1.,result['environment']['speed_of_sound_m_s'])
            aero['drag_coefficient'] += min(.15,.8*max(0.,mach-.72)**2)
            aero['compressibility_model_valid'] = mach < .9
        if (self.science and self.vehicle != 'space' and
                self.science.config['turbulence_sigma_m_s'] > 0):
            result['environment']['turbulence'] = dict(
                model='VON_KARMAN_SHAPED_FINITE_BAND_FROZEN_FIELD',
                sigma_uvw_m_s=[self.science.config['turbulence_sigma_m_s']]*3,
                length_uvw_m=[self.science.config['turbulence_length_m']]*3,
                seed=self.science.config['seed'],
                assumption='FINITE_BAND_1D_SPATIAL_SPECTRUM_NOT_3D_WEATHER')
        return result

    def _step_planetary(self, dt_s):
        cap = min(.02,self.integration_step_cap_s or .02)
        count = max(1,math.ceil(dt_s/cap))
        for _ in range(count):
            h = dt_s/count
            self._update_python_control_watchdog(self.t)
            self.science.before_step(self,h,self.t)
            elapsed = self.planetary.advance(h,self.command,self.science.control_power_factor)
            self.t += elapsed
            self.mass_kg = self.planetary.y[13]
            self.propellant_kg = max(0.,self.mass_kg-self.mass_dry_kg)
            self.load_factor_g = self.planetary.thrust_N/max(self.mass_kg,1)/G0
            if self.planetary.contact:
                self.phase = 'LANDED' if self.planetary.soft_landing else 'CRASHED'
                self.mission_metrics['touchdown_speed_m_s'] = self.planetary.touchdown_speed
            self.science.after_step(self,elapsed,self.t)
            if self.planetary.contact:
                break
        return self.state()

    def _flight_state(self) -> dict[str, Any]:
        if self.vehicle == "space":
            remaining_propellant_capacity = (
                sum(stage["propellant_capacity_kg"]
                    for stage in self.stage_specs[self.active_stage_index:])
                if self.stage_specs else self.propellant_capacity_kg)
            x, y, z, vx, vy, vz = self.orbit
            r = math.sqrt(x*x+y*y+z*z)
            speed = math.sqrt(vx*vx+vy*vy+vz*vz)
            altitude = r-EARTH_RADIUS
            atmosphere = atmosphere_isa(altitude)
            density = atmosphere["density_kg_m3"]
            v_atm = [-OMEGA_EARTH*y, OMEGA_EARTH*x, 0.0]
            relative_speed = _norm3([vx-v_atm[0], vy-v_atm[1], vz-v_atm[2]])
            stagnation_heat_flux = self._space_stagnation_heat_flux_W_m2(self.orbit)
            dx = self.target_orbit[0]-x
            dy = self.target_orbit[1]-y
            dz = self.target_orbit[2]-z
            return {"version": __version__, "vehicle": self.vehicle, "time_s": self.t,
                    "scenario": self.scenario,
                    "mission_profile": ("Lancio, orbita LEO e rientro con atterraggio" if self.scenario == "leo-return"
                                        else "Rendezvous LEO e mantenimento a 20 m" if self.scenario == "orbital"
                                        else "Rientro suborbitale"),
                    "phase": self.phase,
                    "phase_time_s": self.phase_time_s,
                    "mission_started": self.mission_started, "fault": self.fault,
                    "fault_management": self._fault_management_state(),
                    "external_control": self._external_control_telemetry(),
                    "model_id": self.model_id, "vehicle_name": self.vehicle_model["name"],
                    "frame": "ECI", "position_eci_m": [x,y,z],
                    "velocity_eci_m_s": [vx,vy,vz],
                    **({"navigation_estimate": self.space_navigation.report(),
                        "navigation_source": "SYNTHETIC_IMU_GNSS_ECI_KALMAN"
                        } if self.space_navigation is not None else {}),
                    **self._spacecraft_attitude_telemetry(),
                    "altitude_m": max(0.0, altitude) if self.phase == "LANDED" else altitude,
                    "speed_m_s": speed, "air_relative_speed_m_s": relative_speed,
                    "specific_force_body_m_s2": list(self.specific_force_body_m_s2),
                    "specific_force_magnitude_m_s2": _norm3(self.specific_force_body_m_s2),
                    "load_factor_g": self.load_factor_g,
                    "specific_force_model": "TRANSLATIONAL_NON_GRAVITATIONAL_FORCE_BODY_FRAME",
                    "range_to_target_m": math.sqrt(dx*dx+dy*dy+dz*dz),
                    "target_position_eci_m": self.target_orbit[:3],
                    "target_velocity_eci_m_s": self.target_orbit[3:],
                    "mass_kg": self.mass_kg, "propellant_kg": self.propellant_kg,
                    "propellant_pct": 100*self.propellant_kg/self.propellant_capacity_kg,
                    "acs_propellant_kg": self.acs_propellant_kg,
                    "acs_propellant_pct": (
                        100*self.acs_propellant_kg/self.acs_propellant_capacity_kg
                        if self.acs_propellant_capacity_kg > 0.0 else 0.0),
                    "active_stage": (self.active_stage_index+1
                                     if self.active_stage_index < len(self.stage_specs) else 0),
                    "stage_count": len(self.stage_specs),
                    "stage_events": [dict(event) for event in self.stage_events],
                    "attitude_command_deg": [self.command["roll_deg"], self.command["pitch_deg"], self.command["yaw_deg"]],
                    "command": dict(self.command), "orbital_elements": self._orbital_elements(),
                    "estimated_orbital_elements": (
                        self._orbital_elements(self._space_guidance_state())
                        if self.space_navigation is not None else None),
                    **(self._rendezvous_telemetry() if self.scenario == "orbital" else {}),
                    "mission_metrics": dict(self.mission_metrics),
                    "propulsion": {"model": "VACUUM_THRUST_MINUS_AMBIENT_PRESSURE_AREA",
                                   "vacuum_thrust_N": self.max_thrust_N,
                                   "net_thrust_N": self._thrust_at_altitude(altitude),
                                   "applied_thrust_N": (self._thrust_at_altitude(altitude)*self._engine_availability()*self.command["throttle_pct"]/100.0
                                                        if self.mission_started and self.propellant_kg > 0.0 else 0.0),
                                   "pressure_correction_N": self.max_thrust_N - self._thrust_at_altitude(altitude),
                                   "nozzle_exit_area_m2": self.nozzle_exit_area_m2,
                                   "reference_mass_flow_kg_s": (self.max_thrust_N/(self.isp_s*G0)
                                                                if self.isp_s>0 else 0),
                                   "effective_isp_s": (self._thrust_at_altitude(altitude)*self.isp_s/self.max_thrust_N
                                                       if self.max_thrust_N>0 else 0),
                                   "note": "Pressure correction drives live acceleration; chamber chemistry is not identified"},
                    "environment": {"mu_earth_m3_s2": MU_EARTH, "earth_radius_m": EARTH_RADIUS,
                                    "J2": EARTH_J2, "earth_rotation_rad_s": OMEGA_EARTH,
                                    "temperature_K": atmosphere["temperature_K"],
                                    "pressure_Pa": atmosphere["pressure_Pa"],
                                    "density_kg_m3": density,
                                    "atmosphere_model": atmosphere["model"],
                                    "in_model_domain": atmosphere["in_model_domain"],
                                    "drag_model_enabled": self.scenario in {"mission", "leo-return"},
                                    "dynamic_pressure_Pa": 0.5*density*relative_speed**2,
                                    "aerothermal_model": (
                                        "SUTTON_GRAVES_EARTH_STAGNATION_POINT"
                                        if self.scenario in {"mission", "leo-return"}
                                        else "NOT_MODELLED"),
                                    "stagnation_heating_active": stagnation_heat_flux > 0.0,
                                    "stagnation_point_convective_heat_flux_W_m2": (
                                        stagnation_heat_flux),
                                    "stagnation_point_convective_heat_load_J_m2": (
                                        self.mission_metrics[
                                            "stagnation_point_convective_heat_load_J_m2"]),
                                    "thermal_response_model": "NOT_MODELLED"},
                    "model": self.model_name,
                    "vehicle_design": dict(self.custom_design) if self.custom_design else None,
                    "vehicle_parameters": {"dry_mass_kg": self.mass_dry_kg,
                                            "propellant_capacity_kg": self.propellant_capacity_kg,
                                            "propellant_capacity_remaining_kg": remaining_propellant_capacity,
                                            "acs_propellant_capacity_kg": self.acs_propellant_capacity_kg,
                                            "wet_mass_kg": (self.mass_dry_kg +
                                                            remaining_propellant_capacity +
                                                            self.acs_propellant_capacity_kg),
                                            "thrust_vacuum_N": self.max_thrust_N,
                                            "thrust_sea_level_N": self._thrust_at_altitude(0.0),
                                            "nozzle_exit_area_m2": self.nozzle_exit_area_m2,
                                            "isp_vacuum_s": self.isp_s,
                                            "aeroshell_nose_radius_m": (
                                                self.launch_vehicle.get("nose_radius_m") if
                                                hasattr(self, "launch_vehicle") else None),
                                            "body_length_m": self.launch_vehicle.get("body_length_m"),
                                            "body_radius_m": self.launch_vehicle.get("body_radius_m"),
                                            "attitude_inertia_model": (
                                                "UNIFORM_CYLINDER_APPROXIMATION"
                                                if self.launch_vehicle_attitude is not None
                                                else "SPACECRAFT_CATALOG_INERTIA" if
                                                self.spacecraft_attitude is not None else "NOT_MODELLED"),
                                            "tvc_max_gimbal_deg": self.launch_vehicle.get(
                                                "tvc_max_gimbal_deg"),
                                            "tvc_gimbal_rate_deg_s": self.launch_vehicle.get(
                                                "tvc_gimbal_rate_deg_s")}}
        n, e, d, u, v, w, phi, theta, psi, p, q, r = self.flight[:12]
        delta_a, delta_e, delta_r = self.flight[12:15]
        mass, fuel = self.flight[-2:]
        speed = math.sqrt(u*u+v*v+w*w)
        altitude = -d
        env = dict(atmosphere_isa(altitude))
        ground_speed = _norm3(self._ned_velocity(self.flight))
        air_velocity_ned = self._air_relative_velocity_ned(self.flight)
        air_velocity = self._air_relative_velocity_body(self.flight)
        airspeed = _norm3(air_velocity)
        gust_ned = self._turbulence_gust_ned(self.flight)
        mean_wind_ned, wind_profile_clamped = self._wind_telemetry_state(altitude)
        total_wind_ned = [mean_wind_ned[i]+gust_ned[i] for i in range(3)]
        env.update({"wind_ned_m_s": list(mean_wind_ned),
                    "wind_velocity_ned_m_s": total_wind_ned,
                    "mean_wind_velocity_ned_m_s": mean_wind_ned,
                    "wind_profile_ned_m_s": copy.deepcopy(self.wind_profile_ned_m_s),
                    "surface_layer_wind": copy.deepcopy(self.surface_layer_wind),
                    "wind_profile_model": (
                        "MONIN_OBUKHOV_SURFACE_LAYER"
                        if self.surface_layer_wind is not None else
                        "LINEAR_ALTITUDE_NED_WITH_ENDPOINT_CLAMP"
                        if self.wind_profile_ned_m_s is not None else "UNIFORM_NED"),
                    "wind_profile_endpoint_clamped": wind_profile_clamped,
                    "turbulence_gust_velocity_ned_m_s": gust_ned,
                    "wind_speed_m_s": _norm3(total_wind_ned),
                    "wind_mean_speed_m_s": _norm3(mean_wind_ned),
                    "dynamic_pressure_Pa": 0.5 * env["density_kg_m3"] * airspeed**2,
                    "wind_direction_to_deg": (
                        math.degrees(math.atan2(total_wind_ned[1],
                                                total_wind_ned[0])) % 360.0
                        if _norm3(total_wind_ned) > 0.0 else None),
                    "turbulence": {
                        **copy.deepcopy(self.turbulence_settings),
                        "along_field_distance_m": self.flight[-3],
                        "assumption": ("TAYLOR_FROZEN_FIELD_1D_NO_GUST_GRADIENTS"
                                       if self.turbulence_model is not None else "NONE")}})
        result = {"version": __version__, "vehicle": self.vehicle, "time_s": self.t,
                "scenario": self.scenario, "phase": self.phase,
                "phase_time_s": self.phase_time_s,
                "mission_started": self.mission_started, "fault": self.fault,
                "fault_management": self._fault_management_state(),
                "external_control": self._external_control_telemetry(),
                "model_id": self.model_id, "vehicle_name": self.vehicle_model["name"],
                "frame": "NED", "position_ned_m": [n,e,d],
                "velocity_body_m_s": [u,v,w], "altitude_m": altitude,
                "speed_m_s": speed, "ground_speed_m_s": ground_speed,
                "air_relative_velocity_ned_m_s": air_velocity_ned,
                "air_relative_velocity_body_m_s": air_velocity,
                "air_relative_speed_m_s": airspeed,
                "specific_force_body_m_s2": list(self.specific_force_body_m_s2),
                "specific_force_magnitude_m_s2": _norm3(self.specific_force_body_m_s2),
                "load_factor_g": self.load_factor_g,
                "specific_force_model": "TRANSLATIONAL_NON_GRAVITATIONAL_FORCE_BODY_FRAME",
                "attitude_deg": [math.degrees(phi),math.degrees(theta),math.degrees(psi)],
                "body_rates_rad_s": [p,q,r], "mass_kg": mass,
                "propellant_kg": fuel, "propellant_pct": 100*fuel/self.propellant_capacity_kg,
                "command": dict(self.command), "environment": env,
                "mission_metrics": dict(self.mission_metrics),
                "model": self.model_name,
                "vehicle_parameters": self.aero if self.vehicle == "aircraft" else self.drone if self.vehicle == "drone" else None}
        if self.vehicle == "aircraft":
            # Runway/rotation indicators are measured from the same 6-DoF
            # state used by the aircraft plant; they are not scripted motion.
            vr = self.vehicle_model["takeoff_speed_m_s"]
            result["takeoff"] = {
                "rotation_speed_m_s": vr,
                "rotation_ready": airspeed >= .95*vr,
                "runway_remaining_m": max(0.0, AIRFIELD_RUNWAY_END_N_M-n),
                "on_ground": not self.aircraft_airborne,
                "manual_rotation_assist": (self.command["mode"] == "manual"
                                           and self.manual_takeoff_assist_engaged),
            }
            fdir_emergency = self.fdir_recovery_mode in {
                    "AUTOMATIC_FORCED_LANDING", "FORCED_LANDING_COMPLETED",
                    "FORCED_LANDING_FAILED"}
            link_emergency = self.external_control["state"] in {
                "FORCED_LANDING", "RECOVERY_COMPLETED", "RECOVERY_FAILED"}
            if fdir_emergency or link_emergency:
                result["emergency_guidance"] = {
                    "mode": (self.fdir_recovery_mode if fdir_emergency else
                             "PYTHON_LINK_LOSS_FORCED_LANDING"),
                    "controller": "BEST_GLIDE_POLAR_THEN_AUTOMATIC_APPROACH",
                    "target_ground_track_deg": self.fdir_landing_track_deg,
                    "best_glide": self._aircraft_best_glide_state(altitude),
                    "landing_surface_model": "FLAT_UNOBSTRUCTED_REFERENCE_SURFACE",
                    "terrain_and_runway_selection": "NOT_MODELLED",
                }
            result["propulsion"] = self._aircraft_propulsion_state(self.flight)
            alpha = math.atan2(air_velocity[2], max(abs(air_velocity[0]), 0.1))
            beta = math.asin(_clamp(air_velocity[1] / max(airspeed, 0.1), -0.99, 0.99))
            coefficients = fixed_wing_coefficients(
                self.aero, alpha, beta,
                mach=airspeed/max(1.0, env["speed_of_sound_m_s"]))
            moment_coefficients = fixed_wing_moment_coefficients(
                self.aero, alpha, beta, (p, q, r), max(airspeed, 0.11),
                (delta_a, delta_e, delta_r))
            surface_targets, surface_rates = self._aircraft_surface_actuators(self.flight)
            surface_names = ("aileron", "elevator", "rudder")
            surface_limits = [self.aero[f"{name}_rate_limit_rad_s"]
                              for name in surface_names]
            stall_assessment_valid = (
                env["dynamic_pressure_Pa"] >=
                STALL_ASSESSMENT_MIN_DYNAMIC_PRESSURE_PA)
            result["aerodynamics"] = {
                "model": "QUASI_STEADY_FIXED_WING_SMOOTH_STALL_POLAR",
                "moment_model": "LINEAR_FIXED_WING_STATIC_AND_RATE_DERIVATIVES",
                "moment_derivatives": {
                    key: float(self.aero.get(key, default))
                    for key, default in (
                        ("Cl_beta_per_rad", -0.12), ("Cl_p", -0.5),
                        ("Cl_delta_a_at_max_deflection", 0.08),
                        ("Cm0", 0.0), ("Cm_alpha_per_rad", 0.0),
                        ("Cm_q", -12.0),
                        ("Cm_delta_e_at_max_deflection", 1.05),
                        ("Cn_beta_per_rad", 0.16), ("Cn_r", -0.22),
                        ("Cn_delta_r_at_max_deflection", 0.07))},
                "moment_coefficients": {
                    key: moment_coefficients[key] for key in ("Cl", "Cm", "Cn")},
                "stall_assessment_valid": stall_assessment_valid,
                "stall_assessment_min_dynamic_pressure_Pa": (
                    STALL_ASSESSMENT_MIN_DYNAMIC_PRESSURE_PA),
                "angle_of_attack_rad": alpha,
                "angle_of_attack_deg": math.degrees(alpha),
                "angle_of_sideslip_rad": beta,
                "angle_of_sideslip_deg": math.degrees(beta),
                "dynamic_pressure_Pa": env["dynamic_pressure_Pa"],
                "lift_coefficient": coefficients["CL"],
                "drag_coefficient": coefficients["CD"],
                "side_force_coefficient": coefficients["CY"],
                "stall_angle_deg": math.degrees(self.aero["alpha_stall_rad"]),
                "stall_margin_deg": coefficients["stall_margin_deg"],
                "stall_state": (
                    ("POST_STALL" if coefficients["stall_state"] else "ATTACHED_FLOW")
                    if stall_assessment_valid else
                    "NOT_APPLICABLE_LOW_DYNAMIC_PRESSURE"),
            }
            result["control_surfaces"] = {
                "actuator_model": "FIRST_ORDER_RATE_LIMITED_SERVO",
                "command_deflection_rad": surface_targets,
                "actual_deflection_rad": [delta_a, delta_e, delta_r],
                "actual_deflection_deg": [math.degrees(value)
                                           for value in (delta_a, delta_e, delta_r)],
                "rate_rad_s": surface_rates,
                "rate_limit_rad_s": surface_limits,
                "rate_limited": [abs(abs(rate)-limit) <= 1e-9
                                 for rate, limit in zip(surface_rates, surface_limits)],
            }
        elif self.vehicle == "drone":
            propulsion = self._drone_propulsion_state(self.flight)
            speed_scale = 60.0/(2.0*math.pi)
            max_speed = self.drone["max_rotor_speed_rad_s"]
            rotor_count = self.drone["rotors"]
            result["propulsion_actuators"] = {
                "model": "INDIVIDUAL_ROTOR_FIRST_ORDER_MOTOR_DYNAMICS",
                "control_allocator": propulsion["allocator_mode"],
                "rotor_count": rotor_count,
                "total_thrust_command_N": propulsion["requested_wrench_N_Nm"][0],
                "total_thrust_actual_N": propulsion["actual_wrench_N_Nm"][0],
                "body_moment_command_N_m": propulsion["requested_wrench_N_Nm"][1:],
                "body_moment_actual_N_m": propulsion["actual_wrench_N_Nm"][1:],
                "motor_speed_command_rad_s": propulsion["commanded_speeds_rad_s"],
                "motor_speed_actual_rad_s": propulsion["actual_speeds_rad_s"],
                "motor_speed_command_rpm": [value*speed_scale for value in
                                             propulsion["commanded_speeds_rad_s"]],
                "motor_speed_actual_rpm": [value*speed_scale for value in
                                           propulsion["actual_speeds_rad_s"]],
                "motor_speed_rates_rad_s2": propulsion["motor_speed_rates_rad_s2"],
                "rotor_phase_rad": list(
                    self.flight[12+rotor_count:12+2*rotor_count]),
                "rotor_spin_direction": [rotor["spin_direction"]
                                         for rotor in self.rotor_geometry],
                "rotor_thrust_command_N": propulsion["commanded_thrusts_N"],
                "rotor_thrust_actual_N": propulsion["actual_thrusts_N"],
                "max_rotor_speed_rad_s": max_speed,
                "motor_time_constant_up_s": self.drone["motor_time_constant_up_s"],
                "motor_time_constant_down_s": self.drone["motor_time_constant_down_s"],
                "mixer_saturated": any(
                    value <= 1e-9 or value >= self.drone["max_rotor_thrust_N"]-1e-9
                    for value in propulsion["commanded_thrusts_N"]),
            }
        if self.vertical_nav is not None:
            result["navigation_estimate"] = self.vertical_nav.report()
        if self.horizontal_nav is not None:
            horizontal = self.horizontal_nav.report()
            estimated_position = horizontal["position_ned_m"]
            result["horizontal_navigation_estimate"] = horizontal
            if self.vehicle == "aircraft":
                estimated_velocity = horizontal["velocity_ned_m_s"]
                estimated_track = (math.degrees(math.atan2(
                    estimated_velocity[1], estimated_velocity[0]))
                    if math.hypot(*estimated_velocity) > 1.0 else None)
                emergency = self.fdir_recovery_mode in {
                    "AUTOMATIC_FORCED_LANDING", "FORCED_LANDING_COMPLETED",
                    "FORCED_LANDING_FAILED"} or self.external_control["state"] in {
                        "FORCED_LANDING", "RECOVERY_COMPLETED", "RECOVERY_FAILED"}
                result["guidance"] = {
                    "mode": ("PYTHON_LINK_LOSS_FORCED_LANDING"
                             if link_emergency else
                             "AUTOMATIC_FORCED_LANDING" if emergency else
                             "FIXED_WING_PHASE_PROFILE"),
                    "navigation_source": "SYNTHETIC_IMU_GNSS_PLANAR_KALMAN",
                    "estimated_ground_track_deg": estimated_track,
                    "vertical_navigation_source": (
                        "SYNTHETIC_IMU_BAROMETER_KALMAN"
                        if self.vertical_nav is not None else "TRUTH_FALLBACK"),
                    "estimated_vertical_speed_up_m_s": (
                        self.vertical_nav.x[1]
                        if self.vertical_nav is not None else None),
                    "estimated_sink_rate_down_m_s": (
                        -self.vertical_nav.x[1]
                        if self.vertical_nav is not None else None),
                    "flare_target_speed_m_s": (
                        max(1.20*self._aircraft_stall_speed_m_s(altitude),
                            self.vehicle_model["takeoff_speed_m_s"])
                        if self.phase == "LANDING" else None),
                    "target_ground_track_deg": (
                        self.fdir_landing_track_deg if emergency else None),
                    "best_glide_guidance_active": (
                        emergency and self.phase == "EMERGENCY_GLIDE"),
                }
            else:
                result["guidance"] = {
                    "mode": ("GNSS-loss land-in-place failsafe"
                             if self.fdir_recovery_mode in {
                                 "AUTOMATIC_SENSOR_LANDING",
                                 "SENSOR_FAILSAFE_LANDED",
                                 "SENSOR_FAILSAFE_FAILED"} else
                             "GNSS position hold · inspection orbit · return to pad"),
                    "horizontal_controller": "continuous-time LQR · planar double integrator",
                    "horizontal_lqr_gains": list(continuous_lqr_double_integrator_gains(
                        *UAV_HORIZONTAL_LQR_WEIGHTS)),
                    "vertical_controller": "continuous-time LQR · vertical double integrator",
                    "vertical_lqr_gains": list(continuous_lqr_double_integrator_gains(
                        *UAV_VERTICAL_LQR_WEIGHTS)),
                    "acceleration_limit_m_s2": 3.0,
                    "target_position_ned_m": list(self.guidance_target_ned_m),
                    "horizontal_position_error_m": math.hypot(
                        self.guidance_target_ned_m[0] - estimated_position[0],
                        self.guidance_target_ned_m[1] - estimated_position[1]),
                    "home_distance_m": math.hypot(n, e),
                }
        if self.vehicle == "drone":
            result["battery_pct"] = self.propellant_kg
            result["battery"] = {
                "energy_remaining_Wh": self.battery_energy_Wh,
                "capacity_Wh": self.battery_capacity_Wh,
                "power_draw_W": self.battery_power_W,
                "energy_used_Wh": self.mission_metrics["battery_energy_used_Wh"],
                "endurance_at_current_power_s": (
                    self.battery_energy_Wh*3600.0/self.battery_power_W
                    if self.battery_power_W > 0.0 else None),
                "model": "actuator-disk momentum theory · profile, motor, avionics and parasite losses",
            }
            result.pop("propellant_kg", None)
            result.pop("propellant_pct", None)
        return result
