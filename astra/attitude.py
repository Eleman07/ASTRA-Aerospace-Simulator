"""Rigid-body attitude propagation and reaction-wheel control for ASTRA."""

from __future__ import annotations

import math

from .constants import G0


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x*y for x, y in zip(a, b))


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0]]


def _norm(a: list[float]) -> float:
    return math.sqrt(_dot(a, a))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _q_normalize(q: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value*value for value in q))
    if magnitude < 1e-15 or not math.isfinite(magnitude):
        raise ValueError("attitude quaternion must have finite nonzero norm")
    return [value/magnitude for value in q]


def _q_multiply(a: list[float], b: list[float]) -> list[float]:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [aw*bw-ax*bx-ay*by-az*bz,
            aw*bx+ax*bw+ay*bz-az*by,
            aw*by-ax*bz+ay*bw+az*bx,
            aw*bz+ax*by-ay*bx+az*bw]


def _q_conjugate(q: list[float]) -> list[float]:
    return [q[0], -q[1], -q[2], -q[3]]


def _q_rotate(q: list[float], vector: list[float]) -> list[float]:
    rotated = _q_multiply(_q_multiply(q, [0.0, *vector]), _q_conjugate(q))
    return rotated[1:]


def _q_from_matrix(matrix: list[list[float]]) -> list[float]:
    """Convert a proper rotation matrix (rows, ECI components by body axis)."""
    trace = matrix[0][0]+matrix[1][1]+matrix[2][2]
    if trace > 0.0:
        scale = 2.0*math.sqrt(max(0.0, trace+1.0))
        q = [0.25*scale,
             (matrix[2][1]-matrix[1][2])/scale,
             (matrix[0][2]-matrix[2][0])/scale,
             (matrix[1][0]-matrix[0][1])/scale]
    elif matrix[0][0] > matrix[1][1] and matrix[0][0] > matrix[2][2]:
        scale = 2.0*math.sqrt(max(0.0, 1.0+matrix[0][0]-matrix[1][1]-matrix[2][2]))
        q = [(matrix[2][1]-matrix[1][2])/scale, 0.25*scale,
             (matrix[0][1]+matrix[1][0])/scale,
             (matrix[0][2]+matrix[2][0])/scale]
    elif matrix[1][1] > matrix[2][2]:
        scale = 2.0*math.sqrt(max(0.0, 1.0+matrix[1][1]-matrix[0][0]-matrix[2][2]))
        q = [(matrix[0][2]-matrix[2][0])/scale,
             (matrix[0][1]+matrix[1][0])/scale, 0.25*scale,
             (matrix[1][2]+matrix[2][1])/scale]
    else:
        scale = 2.0*math.sqrt(max(0.0, 1.0+matrix[2][2]-matrix[0][0]-matrix[1][1]))
        q = [(matrix[1][0]-matrix[0][1])/scale,
             (matrix[0][2]+matrix[2][0])/scale,
             (matrix[1][2]+matrix[2][1])/scale, 0.25*scale]
    return _q_normalize(q)


def _q_from_euler_321(angles_rad: list[float]) -> list[float]:
    roll, pitch, yaw = angles_rad
    cr, sr = math.cos(roll/2.0), math.sin(roll/2.0)
    cp, sp = math.cos(pitch/2.0), math.sin(pitch/2.0)
    cy, sy = math.cos(yaw/2.0), math.sin(yaw/2.0)
    return _q_normalize([cy*cp*cr+sy*sp*sr,
                         cy*cp*sr-sy*sp*cr,
                         cy*sp*cr+sy*cp*sr,
                         sy*cp*cr-cy*sp*sr])


def _euler_321_deg(q: list[float]) -> list[float]:
    w, x, y, z = _q_normalize(q)
    roll = math.atan2(2.0*(w*x+y*z), 1.0-2.0*(x*x+y*y))
    pitch_sine = max(-1.0, min(1.0, 2.0*(w*y-z*x)))
    pitch = math.asin(pitch_sine)
    yaw = math.atan2(2.0*(w*z+x*y), 1.0-2.0*(y*y+z*z))
    return [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]


def _rk4_step(state: list[float], dt_s: float, derivative) -> list[float]:
    k1 = derivative(state)
    k2 = derivative([x+0.5*dt_s*k for x, k in zip(state, k1)])
    k3 = derivative([x+0.5*dt_s*k for x, k in zip(state, k2)])
    k4 = derivative([x+dt_s*k for x, k in zip(state, k3)])
    return [x+dt_s*(a+2.0*b+2.0*c+d)/6.0
            for x, a, b, c, d in zip(state, k1, k2, k3, k4)]


class SpacecraftAttitude:
    """Three-axis rigid body with LVLH quaternion guidance and reaction wheels.

    The body frame is right-handed: +X is along-track, +Y is opposite orbit
    normal, and +Z points nadir. Euler telemetry uses the 3-2-1 convention and
    is accompanied by the body-to-ECI quaternion to avoid Euler ambiguity.
    """

    def __init__(self, inertia_kg_m2: tuple[float, float, float] = (380.0, 380.0, 190.0),
                 wheel_torque_limit_N_m: tuple[float, float, float] = (0.5, 0.5, 0.35),
                 wheel_momentum_limit_N_m_s: tuple[float, float, float] = (30.0, 30.0, 20.0)) -> None:
        if (len(inertia_kg_m2) != 3 or any(not math.isfinite(x) or x <= 0.0
                                           for x in inertia_kg_m2)):
            raise ValueError("spacecraft inertia must contain three positive finite values")
        if (len(wheel_torque_limit_N_m) != 3 or any(not math.isfinite(x) or x <= 0.0
                                                    for x in wheel_torque_limit_N_m)):
            raise ValueError("reaction-wheel torque limits must be positive and finite")
        if (len(wheel_momentum_limit_N_m_s) != 3 or any(not math.isfinite(x) or x <= 0.0
                                                      for x in wheel_momentum_limit_N_m_s)):
            raise ValueError("reaction-wheel momentum limits must be positive and finite")
        self.inertia_kg_m2 = list(inertia_kg_m2)
        self.wheel_torque_limit_N_m = list(wheel_torque_limit_N_m)
        self.wheel_momentum_limit_N_m_s = list(wheel_momentum_limit_N_m_s)
        self.natural_frequency_rad_s = 0.06
        self.damping_ratio = 0.9
        self.quaternion_body_to_eci = [1.0, 0.0, 0.0, 0.0]
        self.body_rates_rad_s = [0.0, 0.0, 0.0]
        self.wheel_momentum_body_N_m_s = [0.0, 0.0, 0.0]
        self.target_angles_deg = [0.0, 0.0, 0.0]
        self.target_quaternion_body_to_eci = [1.0, 0.0, 0.0, 0.0]
        self.target_angular_velocity_eci_rad_s = [0.0, 0.0, 0.0]
        self.control_torque_body_Nm = [0.0, 0.0, 0.0]
        self.gravity_gradient_torque_body_N_m = [0.0, 0.0, 0.0]
        self.wheel_saturated = [False, False, False]
        self.attitude_error_deg = 0.0
        self.control_mode = "lvlh"
        self.inertial_hold_quaternion = self.quaternion_body_to_eci[:]
        self.manual_torque_fraction = [0.0, 0.0, 0.0]
        self.manual_override = False

    def _lvlh_target(self, position_eci_m: list[float], velocity_eci_m_s: list[float],
                     target_angles_deg: list[float]) -> tuple[list[float], list[float], list[float]]:
        radius = _norm(position_eci_m)
        if radius < 1.0:
            raise ValueError("spacecraft position must be outside the ECI origin")
        radial = [value/radius for value in position_eci_m]
        angular_momentum = _cross(position_eci_m, velocity_eci_m_s)
        hmag = _norm(angular_momentum)
        if hmag < 1e-6:
            raise ValueError("LVLH attitude requires nonzero orbital angular momentum")
        normal = [value/hmag for value in angular_momentum]
        transverse = _cross(normal, radial)
        body_x = transverse
        body_y = [-value for value in normal]
        body_z = [-value for value in radial]
        # Columns are body basis vectors expressed in ECI coordinates.
        matrix = [[body_x[row], body_y[row], body_z[row]] for row in range(3)]
        lvlh_q = _q_from_matrix(matrix)
        offset_q = _q_from_euler_321([math.radians(value) for value in target_angles_deg])
        target_q = _q_normalize(_q_multiply(lvlh_q, offset_q))
        angular_velocity_eci = [hmag/radius**2*value for value in normal]
        return target_q, angular_velocity_eci, normal

    def initialize(self, position_eci_m: list[float], velocity_eci_m_s: list[float],
                   target_angles_deg: list[float] | None = None) -> None:
        self.target_angles_deg = list(target_angles_deg or [0.0, 0.0, 0.0])
        target_q, angular_velocity_eci, _normal = self._lvlh_target(
            position_eci_m, velocity_eci_m_s, self.target_angles_deg)
        self.quaternion_body_to_eci = target_q
        self.target_quaternion_body_to_eci = target_q[:]
        self.target_angular_velocity_eci_rad_s = angular_velocity_eci
        self.body_rates_rad_s = _q_rotate(_q_conjugate(target_q), angular_velocity_eci)

    def _target(self, position_eci_m: list[float], velocity_eci_m_s: list[float],
                target_angles_deg: list[float]) -> tuple[list[float], list[float], list[float]]:
        return self._lvlh_target(position_eci_m, velocity_eci_m_s, target_angles_deg)

    def _direction_target(self, direction_eci: list[float],
                          reference_eci: list[float], axis: str = "x") -> list[float]:
        """Build a stable inertial attitude frame around the requested body axis."""
        direction_norm = _norm(direction_eci)
        if direction_norm < 1e-9:
            raise ValueError("SAS direction must be nonzero")
        direction = [value/direction_norm for value in direction_eci]
        reference = [reference_eci[i]-_dot(reference_eci, direction)*direction[i]
                     for i in range(3)]
        reference_norm = _norm(reference)
        if reference_norm < 1e-9:
            fallback = [0.0, 0.0, 1.0] if abs(direction[2]) < .9 else [0.0, 1.0, 0.0]
            reference = [fallback[i]-_dot(fallback, direction)*direction[i]
                         for i in range(3)]
            reference_norm = _norm(reference)
        reference = [value/reference_norm for value in reference]
        if axis == "x":
            body_x = direction
            body_z = reference
            body_y = _cross(body_z, body_x)
        elif axis == "y":
            body_y = direction
            body_z = reference
            body_x = _cross(body_y, body_z)
        else:
            body_z = direction
            body_x = reference
            body_y = _cross(body_z, body_x)
        body_x = [value/_norm(body_x) for value in body_x]
        body_y = [value/_norm(body_y) for value in body_y]
        body_z = [value/_norm(body_z) for value in body_z]
        return _q_from_matrix([[body_x[row], body_y[row], body_z[row]]
                               for row in range(3)])

    def _sas_target(self, mode: str, position_eci_m: list[float],
                    velocity_eci_m_s: list[float], target_position_eci_m: list[float] | None,
                    maneuver_direction_eci: list[float] | None,
                    angles: list[float]) -> tuple[list[float], list[float]]:
        radius = _norm(position_eci_m)
        radial = [value/radius for value in position_eci_m]
        speed = _norm(velocity_eci_m_s)
        prograde = ([value/speed for value in velocity_eci_m_s]
                    if speed > 1e-9 else [1.0, 0.0, 0.0])
        angular_momentum = _cross(position_eci_m, velocity_eci_m_s)
        hmag = _norm(angular_momentum)
        normal = ([value/hmag for value in angular_momentum]
                  if hmag > 1e-9 else [0.0, 0.0, 1.0])
        orbital_rate = [hmag/max(radius*radius, 1.0)*value for value in normal]
        if mode == "stability_assist":
            return self.inertial_hold_quaternion[:], [0.0, 0.0, 0.0]
        if mode == "prograde":
            return self._direction_target(prograde, [-value for value in radial], "x"), orbital_rate
        if mode == "retrograde":
            return self._direction_target([-value for value in prograde], [-value for value in radial], "x"), orbital_rate
        if mode in {"radial_in", "radial_out"}:
            direction = [-value for value in radial] if mode == "radial_in" else radial
            return self._direction_target(direction, prograde, "x"), orbital_rate
        if mode in {"normal", "anti_normal"}:
            direction = normal if mode == "normal" else [-value for value in normal]
            return self._direction_target(direction, [-value for value in radial], "x"), orbital_rate
        if mode in {"target", "anti_target"}:
            if target_position_eci_m is None:
                raise ValueError("Target SAS requires target orbit position")
            direction = [target_position_eci_m[i]-position_eci_m[i] for i in range(3)]
            if mode == "anti_target":
                direction = [-value for value in direction]
            return self._direction_target(direction, [-value for value in radial], "x"), [0.0, 0.0, 0.0]
        if mode == "maneuver_node":
            if maneuver_direction_eci is None:
                raise ValueError("Maneuver-node SAS requires a defined maneuver direction")
            return self._direction_target(maneuver_direction_eci, [-value for value in radial], "x"), [0.0, 0.0, 0.0]
        if mode == "lvlh":
            target_q, target_omega, _normal = self._lvlh_target(position_eci_m, velocity_eci_m_s, angles)
            return target_q, target_omega
        if mode in {"manual", "off"}:
            return self.quaternion_body_to_eci[:], [0.0, 0.0, 0.0]
        raise ValueError("Unknown spacecraft SAS mode")

    def _torque_and_disturbance(self, state: list[float], target_q: list[float],
                                target_omega_eci: list[float], radial_eci: list[float],
                                mu_m3_s2: float, radius_m: float
                                ) -> tuple[list[float], list[float], list[bool]]:
        q = _q_normalize(state[:4])
        omega = state[4:7]
        wheel_momentum = state[7:10]
        error_q = _q_normalize(_q_multiply(_q_conjugate(q), target_q))
        if error_q[0] < 0.0:
            error_q = [-value for value in error_q]
        sin_half = _norm(error_q[1:])
        angle = 2.0*math.atan2(sin_half, max(0.0, error_q[0]))
        error_vector = ([2.0*value for value in error_q[1:]] if sin_half < 1e-10
                        else [angle*value/sin_half for value in error_q[1:]])
        target_omega_body = _q_rotate(_q_conjugate(q), target_omega_eci)
        radial_body = _q_rotate(_q_conjugate(q), radial_eci)
        inertia_r = [self.inertia_kg_m2[i]*radial_body[i] for i in range(3)]
        gravity_gradient = [3.0*mu_m3_s2/radius_m**3*value
                            for value in _cross(radial_body, inertia_r)]
        kp = [moment*self.natural_frequency_rad_s**2 for moment in self.inertia_kg_m2]
        kd = [2.0*self.damping_ratio*moment*self.natural_frequency_rad_s
              for moment in self.inertia_kg_m2]
        torque = [kp[i]*error_vector[i]-kd[i]*(omega[i]-target_omega_body[i])
                  -gravity_gradient[i] for i in range(3)]
        torque = [v*getattr(self,'control_power_factor',1.) for v in torque]
        saturated = []
        for i in range(3):
            torque[i] = max(-self.wheel_torque_limit_N_m[i],
                            min(self.wheel_torque_limit_N_m[i], torque[i]))
            momentum_rate = -torque[i]
            blocked = ((wheel_momentum[i] >= self.wheel_momentum_limit_N_m_s[i]-1e-9
                        and momentum_rate > 0.0) or
                       (wheel_momentum[i] <= -self.wheel_momentum_limit_N_m_s[i]+1e-9
                        and momentum_rate < 0.0))
            if blocked:
                torque[i] = 0.0
            saturated.append(blocked or abs(torque[i]) >= self.wheel_torque_limit_N_m[i]-1e-9)

        return torque, gravity_gradient, saturated

    def step(self, dt_s: float, position_eci_m: list[float],
             velocity_eci_m_s: list[float], mu_m3_s2: float,
             target_angles_deg: list[float] | None = None,
             control_mode: str = "lvlh",
             manual_torque_body_fraction: list[float] | None = None,
             target_position_eci_m: list[float] | None = None,
             maneuver_direction_eci: list[float] | None = None) -> None:
        if not math.isfinite(dt_s) or dt_s <= 0.0 or dt_s > 1.0:
            raise ValueError("attitude integration step must be in (0, 1] seconds")
        angles = list(target_angles_deg or [0.0, 0.0, 0.0])
        if control_mode not in {"manual", "off", "stability_assist", "prograde",
                                "retrograde", "radial_in", "radial_out", "normal",
                                "anti_normal", "target", "anti_target", "maneuver_node", "lvlh"}:
            raise ValueError("Unknown spacecraft SAS mode")
        if control_mode == "stability_assist" and self.control_mode != "stability_assist":
            self.inertial_hold_quaternion = self.quaternion_body_to_eci[:]
        if control_mode == "manual" and self.control_mode != "manual":
            self.manual_torque_fraction = [0.0, 0.0, 0.0]
        torque_fraction = list(manual_torque_body_fraction or [0.0, 0.0, 0.0])
        if len(torque_fraction) != 3 or any(not math.isfinite(v) or abs(v) > 1.0 for v in torque_fraction):
            raise ValueError("manual attitude torque must contain three finite fractions in [-1, 1]")
        manual_override = (control_mode not in {"manual", "off", "lvlh"}
                           and any(abs(value) > 1e-6 for value in torque_fraction))
        if control_mode == "stability_assist" and (manual_override or self.manual_override):
            # The stick temporarily owns the actual actuator, not an invisible
            # moving target. On release capture the reached quaternion and damp
            # residual rates with the available wheel torque; never snap pose.
            self.inertial_hold_quaternion = self.quaternion_body_to_eci[:]
        self.manual_override = manual_override
        direct_torque = control_mode in {"manual", "off"} or manual_override
        target_q, target_omega_eci = self._sas_target(
            control_mode, position_eci_m, velocity_eci_m_s,
            target_position_eci_m, maneuver_direction_eci, angles)
        self.control_mode = control_mode
        self.target_angles_deg = angles
        self.target_quaternion_body_to_eci = target_q
        self.target_angular_velocity_eci_rad_s = target_omega_eci
        radius = _norm(position_eci_m)
        radial_eci = [value/radius for value in position_eci_m]
        self.manual_torque_fraction = torque_fraction[:]
        state = [*self.quaternion_body_to_eci, *self.body_rates_rad_s,
                 *self.wheel_momentum_body_N_m_s]

        def derivative(value: list[float]) -> list[float]:
            q = _q_normalize(value[:4])
            omega = value[4:7]
            h = value[7:10]
            if direct_torque:
                q_now = _q_normalize(value[:4])
                omega_now = value[4:7]
                radial_body_now = _q_rotate(_q_conjugate(q_now), radial_eci)
                inertia_r_now = [self.inertia_kg_m2[i]*radial_body_now[i] for i in range(3)]
                disturbance = [3.0*mu_m3_s2/radius**3*item
                               for item in _cross(radial_body_now, inertia_r_now)]
                torque = [torque_fraction[i]*self.wheel_torque_limit_N_m[i]*
                          _clamp(getattr(self, "control_power_factor", 1.0), 0.0, 1.0)
                          for i in range(3)]
                saturated_now = []
                for i in range(3):
                    momentum_rate = -torque[i]
                    blocked = ((value[7+i] >= self.wheel_momentum_limit_N_m_s[i]-1e-9 and momentum_rate > 0.0) or
                               (value[7+i] <= -self.wheel_momentum_limit_N_m_s[i]+1e-9 and momentum_rate < 0.0))
                    if blocked:
                        torque[i] = 0.0
                    saturated_now.append(blocked or abs(torque[i]) >= self.wheel_torque_limit_N_m[i]-1e-9)
            else:
                torque, disturbance, saturated_now = self._torque_and_disturbance(
                    value, target_q, target_omega_eci, radial_eci, mu_m3_s2, radius)
            qdot = [0.5*x for x in _q_multiply(q, [0.0, *omega])]
            angular_momentum = [self.inertia_kg_m2[i]*omega[i]+h[i]
                                for i in range(3)]
            gyroscopic = _cross(omega, angular_momentum)
            omegadot = [(torque[i]+disturbance[i]-gyroscopic[i])/
                        self.inertia_kg_m2[i] for i in range(3)]
            return [*qdot, *omegadot, *[-value for value in torque]]

        propagated = _rk4_step(state, dt_s, derivative)
        self.quaternion_body_to_eci = _q_normalize(propagated[:4])
        self.body_rates_rad_s = propagated[4:7]
        self.wheel_momentum_body_N_m_s = [
            max(-limit, min(limit, value))
            for value, limit in zip(propagated[7:10], self.wheel_momentum_limit_N_m_s)]
        final_state = [*self.quaternion_body_to_eci, *self.body_rates_rad_s,
                       *self.wheel_momentum_body_N_m_s]
        if direct_torque:
            radial_body = _q_rotate(_q_conjugate(self.quaternion_body_to_eci), radial_eci)
            inertia_r = [self.inertia_kg_m2[i]*radial_body[i] for i in range(3)]
            self.gravity_gradient_torque_body_N_m = [3.0*mu_m3_s2/radius**3*value
                for value in _cross(radial_body, inertia_r)]
            torque = [torque_fraction[i]*self.wheel_torque_limit_N_m[i]*
                      _clamp(getattr(self, "control_power_factor", 1.0), 0.0, 1.0)
                      for i in range(3)]
            self.wheel_saturated = []
            for i in range(3):
                rate = -torque[i]
                blocked = ((self.wheel_momentum_body_N_m_s[i] >= self.wheel_momentum_limit_N_m_s[i]-1e-9 and rate > 0.0) or
                           (self.wheel_momentum_body_N_m_s[i] <= -self.wheel_momentum_limit_N_m_s[i]+1e-9 and rate < 0.0))
                if blocked:torque[i]=0.0
                self.wheel_saturated.append(blocked or abs(torque[i]) >= self.wheel_torque_limit_N_m[i]-1e-9)
            self.control_torque_body_Nm = torque
        else:
            self.control_torque_body_Nm, self.gravity_gradient_torque_body_N_m, self.wheel_saturated = (
                self._torque_and_disturbance(final_state, target_q, target_omega_eci,
                                             radial_eci, mu_m3_s2, radius))
        error = _q_normalize(_q_multiply(
            _q_conjugate(self.quaternion_body_to_eci), target_q))
        self.attitude_error_deg = math.degrees(2.0*math.atan2(
            _norm(error[1:]), abs(error[0])))

    def telemetry(self, control_mode: str) -> dict[str, object]:
        return {
            "attitude_deg": _euler_321_deg(self.quaternion_body_to_eci),
            "attitude_frame": "BODY_TO_ECI · 3-2-1 EULER",
            "attitude_quaternion_body_to_eci": self.quaternion_body_to_eci[:],
            "body_axis_z_eci": _q_rotate(self.quaternion_body_to_eci, [0.0, 0.0, 1.0]),
            "attitude_target_deg": self.target_angles_deg[:],
            "attitude_error_deg": self.attitude_error_deg,
            "body_rates_rad_s": self.body_rates_rad_s[:],
            "wheel_momentum_body_N_m_s": self.wheel_momentum_body_N_m_s[:],
            "attitude_control": {
                "mode": control_mode,
                "controller": "quaternion PD · gravity-gradient feed-forward · reaction wheels",
                "commanded_torque_body_N_m": self.control_torque_body_Nm[:],
                "gravity_gradient_torque_body_N_m": self.gravity_gradient_torque_body_N_m[:],
                "wheel_torque_limit_N_m": self.wheel_torque_limit_N_m[:],
                "wheel_momentum_limit_N_m_s": self.wheel_momentum_limit_N_m_s[:],
                "wheel_saturated": self.wheel_saturated[:],
                "manual_torque_fraction": self.manual_torque_fraction[:],
                "manual_override": self.manual_override,
                "actuator": "reaction_wheels",
                "inertia_kg_m2": self.inertia_kg_m2[:],
            },
        }

    def vector_eci_to_body(self, vector_eci: list[float]) -> list[float]:
        """Express an inertial vector in the current spacecraft body frame."""
        return _q_rotate(_q_conjugate(self.quaternion_body_to_eci), vector_eci)


class LaunchVehicleAttitude:
    """Rigid launch-vehicle attitude with a rate-limited two-axis TVC actuator.

    The reference body is a uniform cylinder. This is an explicit inertia
    approximation for ASTRA's conceptual vehicles; aerodynamic moments,
    structural bending, propellant slosh, sensor errors, and roll actuation are
    not modeled. The gimbaled engine is the only attitude actuator.
    """

    def __init__(self, body_length_m: float, body_radius_m: float,
                 max_gimbal_deg: float = 6.0,
                 gimbal_rate_deg_s: float = 5.0,
                 rcs_force_N: float = 24.0, rcs_isp_s: float = 220.0) -> None:
        values = (body_length_m, body_radius_m, max_gimbal_deg, gimbal_rate_deg_s,
                  rcs_force_N, rcs_isp_s)
        if any(not math.isfinite(value) or value <= 0.0 for value in values):
            raise ValueError("launch attitude geometry and actuator limits must be positive and finite")
        if max_gimbal_deg >= 45.0:
            raise ValueError("launch vehicle gimbal angle must be below 45 degrees")
        self.body_length_m = body_length_m
        self.body_radius_m = body_radius_m
        self.max_gimbal_rad = math.radians(max_gimbal_deg)
        self.gimbal_rate_rad_s = math.radians(gimbal_rate_deg_s)
        self.rcs_force_N = rcs_force_N
        self.rcs_isp_s = rcs_isp_s
        self.gimbal_to_com_m = 0.5 * body_length_m
        self.natural_frequency_rad_s = 0.25
        self.damping_ratio = 0.9
        self.quaternion_body_to_eci = [1.0, 0.0, 0.0, 0.0]
        self.body_rates_rad_s = [0.0, 0.0, 0.0]
        self.gimbal_angles_rad = [0.0, 0.0]
        self.gimbal_command_rad = [0.0, 0.0]
        self.target_quaternion_body_to_eci = [1.0, 0.0, 0.0, 0.0]
        self.target_angular_velocity_eci_rad_s = [0.0, 0.0, 0.0]
        self.target_direction_eci = [1.0, 0.0, 0.0]
        self.guidance_command_deg = [90.0, 0.0]
        self.control_torque_body_N_m = [0.0, 0.0, 0.0]
        self.actuator_torque_body_N_m = [0.0, 0.0, 0.0]
        self.gravity_gradient_torque_body_N_m = [0.0, 0.0, 0.0]
        self.inertia_kg_m2 = [1.0, 1.0, 1.0]
        self.attitude_error_deg = 0.0
        self.gimbal_saturated = [False, False]
        self.thrust_N = 0.0
        self.rcs_torque_N_m = [0.0, 0.0, 0.0]
        self.rcs_propellant_used_kg = 0.0
        self.rcs_mass_flow_kg_s = 0.0

    def update_geometry(self, body_length_m: float, body_radius_m: float) -> None:
        if (not math.isfinite(body_length_m) or body_length_m <= 0.0 or
                not math.isfinite(body_radius_m) or body_radius_m <= 0.0):
            raise ValueError("launch vehicle geometry must be positive and finite")
        self.body_length_m = body_length_m
        self.body_radius_m = body_radius_m
        self.gimbal_to_com_m = 0.5 * body_length_m

    def _local_frame(self, position_eci_m: list[float],
                     velocity_eci_m_s: list[float]
                     ) -> tuple[list[float], list[float], list[float], list[float]]:
        radius = _norm(position_eci_m)
        if radius < 1.0:
            raise ValueError("launch vehicle position must be outside the ECI origin")
        radial = [value / radius for value in position_eci_m]
        angular_momentum = _cross(position_eci_m, velocity_eci_m_s)
        hmag = _norm(angular_momentum)
        if hmag < 1e-6:
            raise ValueError("launch attitude reference requires orbital angular momentum")
        normal = [value / hmag for value in angular_momentum]
        tangent = _cross(normal, radial)
        angular_velocity = [hmag / radius**2 * value for value in normal]
        return radial, tangent, normal, angular_velocity

    def _target(self, position_eci_m: list[float], velocity_eci_m_s: list[float],
                pitch_deg: float, crossrange_deg: float
                ) -> tuple[list[float], list[float], list[float]]:
        radial, tangent, normal, angular_velocity = self._local_frame(
            position_eci_m, velocity_eci_m_s)
        pitch = math.radians(pitch_deg)
        crossrange = math.radians(crossrange_deg)
        direction = [radial[i] * math.sin(pitch)
                     + tangent[i] * math.cos(pitch) * math.cos(crossrange)
                     + normal[i] * math.cos(pitch) * math.sin(crossrange)
                     for i in range(3)]
        direction = [value / _norm(direction) for value in direction]
        body_x = _cross(normal, direction)
        xnorm = _norm(body_x)
        if xnorm < 1e-9:
            body_x = tangent
        else:
            body_x = [value / xnorm for value in body_x]
        body_y = _cross(direction, body_x)
        body_y = [value / _norm(body_y) for value in body_y]
        matrix = [[body_x[row], body_y[row], direction[row]] for row in range(3)]
        return _q_from_matrix(matrix), angular_velocity, direction

    def initialize(self, position_eci_m: list[float], velocity_eci_m_s: list[float],
                   pitch_deg: float = 90.0, crossrange_deg: float = 0.0) -> None:
        target_q, target_omega_eci, direction = self._target(
            position_eci_m, velocity_eci_m_s, pitch_deg, crossrange_deg)
        self.guidance_command_deg = [pitch_deg, crossrange_deg]
        self.quaternion_body_to_eci = target_q[:]
        self.target_quaternion_body_to_eci = target_q[:]
        self.target_angular_velocity_eci_rad_s = target_omega_eci
        self.target_direction_eci = direction
        self.body_rates_rad_s = _q_rotate(_q_conjugate(target_q), target_omega_eci)

    def thrust_direction_eci(self) -> list[float]:
        dx, dy = self.gimbal_angles_rad
        body_force_direction = [math.sin(dy) * math.cos(dx),
                                -math.sin(dx),
                                math.cos(dy) * math.cos(dx)]
        return _q_rotate(self.quaternion_body_to_eci, body_force_direction)

    @staticmethod
    def _attitude_error(q: list[float], target_q: list[float]) -> list[float]:
        error_q = _q_normalize(_q_multiply(_q_conjugate(q), target_q))
        if error_q[0] < 0.0:
            error_q = [-value for value in error_q]
        sin_half = _norm(error_q[1:])
        angle = 2.0 * math.atan2(sin_half, max(0.0, error_q[0]))
        if sin_half < 1e-10:
            return [2.0 * value for value in error_q[1:]]
        return [angle * value / sin_half for value in error_q[1:]]

    def _gravity_gradient(self, q: list[float], position_eci_m: list[float],
                          mu_m3_s2: float, inertia: list[float]
                          ) -> list[float]:
        radius = _norm(position_eci_m)
        radial_eci = [value / radius for value in position_eci_m]
        radial_body = _q_rotate(_q_conjugate(q), radial_eci)
        inertia_r = [inertia[i] * radial_body[i] for i in range(3)]
        return [3.0 * mu_m3_s2 / radius**3 * value
                for value in _cross(radial_body, inertia_r)]

    @staticmethod
    def _gimbal_force_body(angles: list[float], thrust_N: float) -> list[float]:
        dx, dy = angles
        return [thrust_N * math.sin(dy) * math.cos(dx),
                -thrust_N * math.sin(dx),
                thrust_N * math.cos(dy) * math.cos(dx)]

    def step(self, dt_s: float, position_eci_m: list[float],
             velocity_eci_m_s: list[float], mu_m3_s2: float,
             mass_kg: float, thrust_N: float,
             pitch_deg: float, crossrange_deg: float,
             rcs_propellant_kg: float = 0.0) -> float:
        if not math.isfinite(dt_s) or dt_s <= 0.0 or dt_s > 1.0:
            raise ValueError("launch attitude integration step must be in (0, 1] seconds")
        if not math.isfinite(mass_kg) or mass_kg <= 0.0:
            raise ValueError("launch vehicle mass must be positive and finite")
        if not math.isfinite(thrust_N) or thrust_N < 0.0:
            raise ValueError("launch thrust must be nonnegative and finite")
        if not math.isfinite(rcs_propellant_kg) or rcs_propellant_kg < 0.0:
            raise ValueError("launch attitude propellant must be nonnegative and finite")
        target_q, target_omega_eci, target_direction = self._target(
            position_eci_m, velocity_eci_m_s, pitch_deg, crossrange_deg)
        self.guidance_command_deg = [pitch_deg, crossrange_deg]
        self.target_quaternion_body_to_eci = target_q
        self.target_angular_velocity_eci_rad_s = target_omega_eci
        self.target_direction_eci = target_direction
        self.thrust_N = thrust_N

        # Uniform-cylinder inertia is intentionally exposed as an ASTRA design
        # approximation, rather than presented as measured vehicle data.
        axial = 0.5 * mass_kg * self.body_radius_m**2
        transverse = mass_kg * (3.0*self.body_radius_m**2 + self.body_length_m**2) / 12.0
        self.inertia_kg_m2 = [transverse, transverse, axial]
        if getattr(self, 'inertia_override_kg_m2', None) is not None:
            self.inertia_kg_m2 = list(self.inertia_override_kg_m2)
        attitude_error = self._attitude_error(self.quaternion_body_to_eci, target_q)
        target_omega_body = _q_rotate(_q_conjugate(self.quaternion_body_to_eci),
                                      target_omega_eci)
        gravity_gradient = self._gravity_gradient(
            self.quaternion_body_to_eci, position_eci_m, mu_m3_s2,
            self.inertia_kg_m2)
        kp = [value * self.natural_frequency_rad_s**2 for value in self.inertia_kg_m2]
        kd = [2.0*self.damping_ratio*value*self.natural_frequency_rad_s
              for value in self.inertia_kg_m2]
        torque_command = [kp[i]*attitude_error[i]
                          - kd[i]*(self.body_rates_rad_s[i]-target_omega_body[i])
                          - gravity_gradient[i] for i in range(3)]
        torque_command = [v*getattr(self,"control_power_factor",1.) for v in torque_command]
        self.rcs_propellant_used_kg = 0.0
        self.rcs_mass_flow_kg_s = 0.0
        self.rcs_torque_N_m = [0.0, 0.0, 0.0]

        if thrust_N > 1e-6 and self.gimbal_to_com_m > 0.0:
            torque_command[2] = 0.0  # A single gimbaled engine cannot control roll.
            max_torque = (self.gimbal_to_com_m * thrust_N *
                          math.sin(self.max_gimbal_rad))
            torque_command[0] = _clamp(torque_command[0], -max_torque, max_torque)
            torque_command[1] = _clamp(torque_command[1], -max_torque, max_torque)
            dx = math.asin(_clamp(-torque_command[0] /
                                  (self.gimbal_to_com_m * thrust_N),
                                  -math.sin(self.max_gimbal_rad),
                                  math.sin(self.max_gimbal_rad)))
            cos_dx = max(math.cos(dx), 1e-9)
            dy = math.asin(_clamp(-torque_command[1] /
                                  (self.gimbal_to_com_m * thrust_N * cos_dx),
                                  -math.sin(self.max_gimbal_rad),
                                  math.sin(self.max_gimbal_rad)))
            self.gimbal_command_rad = [dx, dy]
            self.gimbal_saturated = [
                abs(value) >= self.max_gimbal_rad - 1e-9
                for value in self.gimbal_command_rad]
            for i in range(2):
                delta = _clamp(self.gimbal_command_rad[i] - self.gimbal_angles_rad[i],
                               -self.gimbal_rate_rad_s*dt_s,
                               self.gimbal_rate_rad_s*dt_s)
                self.gimbal_angles_rad[i] += delta
            force_body = self._gimbal_force_body(self.gimbal_angles_rad, thrust_N)
            lever = [0.0, 0.0, -self.gimbal_to_com_m]
            actuator_torque = _cross(lever, force_body)
        else:
            self.gimbal_command_rad = [0.0, 0.0]
            self.gimbal_saturated = [False, False]
            recenter_rate = self.gimbal_rate_rad_s*dt_s
            self.gimbal_angles_rad = [
                angle - _clamp(angle, -recenter_rate, recenter_rate)
                for angle in self.gimbal_angles_rad]
            actuator_torque = [0.0, 0.0, 0.0]
            if rcs_propellant_kg > 0.0 and self.gimbal_to_com_m > 0.0:
                rcs_torque_limit = self.rcs_force_N*self.gimbal_to_com_m
                requested = [_clamp(value, -rcs_torque_limit, rcs_torque_limit)
                             for value in torque_command]
                requested_force = sum(abs(value) for value in requested)/self.gimbal_to_com_m
                mass_flow = requested_force/(self.rcs_isp_s*G0)
                requested_propellant = mass_flow*dt_s
                if requested_propellant > rcs_propellant_kg and requested_propellant > 0.0:
                    scale = rcs_propellant_kg/requested_propellant
                    requested = [scale*value for value in requested]
                    requested_force *= scale
                    requested_propellant = rcs_propellant_kg
                    mass_flow *= scale
                actuator_torque = requested
                self.rcs_torque_N_m = requested[:]
                self.rcs_mass_flow_kg_s = mass_flow
                self.rcs_propellant_used_kg = requested_propellant
        self.control_torque_body_N_m = torque_command
        self.actuator_torque_body_N_m = actuator_torque
        self.gravity_gradient_torque_body_N_m = gravity_gradient
        state = [*self.quaternion_body_to_eci, *self.body_rates_rad_s]

        def derivative(value: list[float]) -> list[float]:
            q = _q_normalize(value[:4])
            omega = value[4:7]
            qdot = [0.5*x for x in _q_multiply(q, [0.0, *omega])]
            gravity = self._gravity_gradient(q, position_eci_m,
                                             mu_m3_s2, self.inertia_kg_m2)
            angular_momentum = [self.inertia_kg_m2[i]*omega[i]
                                for i in range(3)]
            gyroscopic = _cross(omega, angular_momentum)
            omegadot = [(actuator_torque[i] + gravity[i] - gyroscopic[i]) /
                        self.inertia_kg_m2[i] for i in range(3)]
            return [*qdot, *omegadot]

        propagated = _rk4_step(state, dt_s, derivative)
        self.quaternion_body_to_eci = _q_normalize(propagated[:4])
        self.body_rates_rad_s = propagated[4:7]
        self.attitude_error_deg = math.degrees(_norm(
            self._attitude_error(self.quaternion_body_to_eci, target_q)))
        return self.rcs_propellant_used_kg

    def telemetry(self, control_mode: str) -> dict[str, object]:
        commanded_direction = self.target_direction_eci
        actual_direction = self.thrust_direction_eci()
        alignment = _clamp(_dot(commanded_direction, actual_direction), -1.0, 1.0)
        return {
            "attitude_deg": _euler_321_deg(self.quaternion_body_to_eci),
            "attitude_frame": "BODY_TO_ECI · 3-2-1 EULER",
            "attitude_quaternion_body_to_eci": self.quaternion_body_to_eci[:],
            "attitude_guidance_command_deg": self.guidance_command_deg[:],
            "attitude_guidance_frame": "LOCAL_THRUST_DIRECTION · PITCH/CROSSRANGE",
            "attitude_error_deg": self.attitude_error_deg,
            "body_rates_rad_s": self.body_rates_rad_s[:],
            "body_axis_z_eci": _q_rotate(self.quaternion_body_to_eci, [0.0, 0.0, 1.0]),
            "thrust_direction_eci": actual_direction,
            "thrust_direction_error_deg": math.degrees(math.acos(alignment)),
            "attitude_state_status": "MODELLED_3DOF_TVC_RCS_APPROXIMATE_INERTIA",
            "attitude_control": {
                "mode": control_mode,
                "controller": "quaternion PD · two-axis TVC under thrust · three-axis RCS in coast",
                "actuator": "single gimbaled engine · two axes · RCS for coast/roll control",
                "gimbal_angle_rad": self.gimbal_angles_rad[:],
                "gimbal_command_rad": self.gimbal_command_rad[:],
                "gimbal_max_angle_rad": self.max_gimbal_rad,
                "gimbal_rate_limit_rad_s": self.gimbal_rate_rad_s,
                "gimbal_to_com_m": self.gimbal_to_com_m,
                "gimbal_saturated": self.gimbal_saturated[:],
                "commanded_torque_body_N_m": self.control_torque_body_N_m[:],
                "actuator_torque_body_N_m": self.actuator_torque_body_N_m[:],
                "gravity_gradient_torque_body_N_m": self.gravity_gradient_torque_body_N_m[:],
                "inertia_kg_m2": self.inertia_kg_m2[:],
                "inertia_model": ("dry shell + shrinking propellant cylinder, parallel axis"
                                  if getattr(self,'inertia_override_kg_m2',None) else
                                  "uniform-cylinder using current mass and ASTRA reference geometry"),
                "body_length_m": self.body_length_m,
                "body_radius_m": self.body_radius_m,
                "aerodynamic_moments": "NOT_MODELLED",
                "flexible_body_dynamics": "NOT_MODELLED",
                "propellant_slosh": "NOT_MODELLED",
                "roll_control": "RCS_IN_COAST_ONLY",
                "coast_attitude_actuator": "RCS · three-axis torque allocation",
                "rcs_force_per_axis_N": self.rcs_force_N,
                "rcs_isp_s": self.rcs_isp_s,
                "rcs_torque_body_N_m": self.rcs_torque_N_m[:],
                "rcs_mass_flow_kg_s": self.rcs_mass_flow_kg_s,
                "rcs_propellant_used_this_step_kg": self.rcs_propellant_used_kg,
                "rcs_propellant_model": "ideal three-axis allocation; total force from L1 torque demand",
                "attitude_disturbance_models": "gravity gradient only; aerodynamic moments, slosh and flexible modes omitted",
            },
        }

    def vector_eci_to_body(self, vector_eci: list[float]) -> list[float]:
        """Express an inertial vector in the current launch-vehicle body frame."""
        return _q_rotate(_q_conjugate(self.quaternion_body_to_eci), vector_eci)

    def vector_body_to_eci(self, vector_body: list[float]) -> list[float]:
        """Express a body-frame sensor vector in the ECI frame."""
        return _q_rotate(self.quaternion_body_to_eci, vector_body)
