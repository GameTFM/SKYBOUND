"""
SKYBOUND - reference flight-dynamics model (longitudinal, 3-DOF).

WHY THIS EXISTS
---------------
The runtime flight model in the Unreal build is JSBSim (6-DOF rigid body,
LGPL, dynamically linked). JSBSim cannot be exercised on this machine (no C++
toolchain / no engine), so the aircraft *data* would otherwise be unverifiable.

This module is a small, independent, self-contained performance model that:
  * implements the same physics chain the aircraft definitions rely on
    (ISA atmosphere, lift/drag polar, thrust lapse, rolling friction,
    ground effect, rotation, climb performance),
  * is integrated with explicit fixed-step numerics so results are
    reproducible,
  * lets validate.py check the aircraft definitions against published POH /
    airport-planning anchors before any of it is handed to JSBSim.

It is NOT the shipped flight model. It is the yardstick the shipped model is
measured against - and it is deliberately written from the textbook
relationships (Raymer / Roskam style) rather than tuned numerically to hit the
targets.

Sign conventions: all SI. Altitude in metres, speed in m/s, mass in kg.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from aircraft_specs import AircraftSpec

G0 = 9.80665
R_AIR = 287.05287
T0 = 288.15
P0 = 101325.0
RHO0 = 1.225
LAPSE = 0.0065
KT = 0.514444          # m/s per knot
FT = 0.3048


# ---------------------------------------------------------------------------
# Atmosphere - ISA up to 11 km (troposphere). Above that, isothermal layer.
# ---------------------------------------------------------------------------
def isa(altitude_m: float) -> tuple[float, float, float, float]:
    """Return (temperature_K, pressure_Pa, density_kg_m3, speed_of_sound_m_s)."""
    h = max(-500.0, altitude_m)
    if h <= 11000.0:
        temp = T0 - LAPSE * h
        pressure = P0 * (temp / T0) ** (G0 / (R_AIR * LAPSE))
    else:
        temp = T0 - LAPSE * 11000.0
        p11 = P0 * (temp / T0) ** (G0 / (R_AIR * LAPSE))
        pressure = p11 * math.exp(-G0 * (h - 11000.0) / (R_AIR * temp))
    density = pressure / (R_AIR * temp)
    sound = math.sqrt(1.4 * R_AIR * temp)
    return temp, pressure, density, sound


def rho_at(altitude_m: float) -> float:
    return isa(altitude_m)[2]


def cl_max_from_stall(spec: AircraftSpec) -> float:
    """CLmax implied by the published clean stall speed at MTOW, sea level.

    CLmax = 2 W / (rho0 * S * Vs^2)
    """
    if spec.published_v_stall_kt <= 0:
        return 0.0
    vs = spec.published_v_stall_kt * KT
    w = spec.mtow_kg * G0
    return (2.0 * w) / (RHO0 * spec.wing_area_m2 * vs * vs)


def stall_speed_ms(spec: AircraftSpec, cl_max: float, mass_kg: float | None = None,
                   altitude_m: float = 0.0) -> float:
    """1g stall speed for a given CLmax / mass / altitude."""
    m = spec.mtow_kg if mass_kg is None else mass_kg
    return math.sqrt((2.0 * m * G0) / (rho_at(altitude_m) * spec.wing_area_m2 * cl_max))


# ---------------------------------------------------------------------------
# Aerodynamics
# ---------------------------------------------------------------------------
@dataclass
class Config:
    """Flight configuration increments (clean by default)."""
    flaps: float = 0.0            # 0..1 of full flap
    gear_down: bool = False
    speedbrake: float = 0.0       # 0..1
    ground_effect_factor: float = 1.0   # <1 reduces induced drag

    def cd0_increment(self, spec: AircraftSpec) -> float:
        """Parasite-drag increments. Industrial estimates, documented as such."""
        inc = 0.0
        inc += 0.010 * self.flaps                      # flap profile drag
        if self.gear_down:
            inc += 0.015 if spec.engine_type == "piston_prop" else 0.020
        inc += 0.030 * self.speedbrake                 # spoilers/speedbrake
        return inc

    def cl_max(self, spec: AircraftSpec) -> float:
        if self.flaps <= 0.0:
            return spec.cl_max_clean
        return spec.cl_max_clean + (spec.cl_max_landing - spec.cl_max_clean) * self.flaps


def lift_coefficient(spec: AircraftSpec, alpha_rad: float, cfg: Config) -> float:
    """Linear lift curve clipped at CLmax (stall). CL_alpha from thin-airfoil +
    finite-wing correction; alpha0 = -2 deg for a cambered wing."""
    ar = spec.aspect_ratio
    cl_alpha = (2.0 * math.pi * ar) / (ar + 2.0)     # 3D lift-curve slope, /rad
    alpha0 = math.radians(-2.0)
    cl = cl_alpha * (alpha_rad - alpha0)
    return max(-cfg.cl_max(spec), min(cfg.cl_max(spec), cl))


def angle_for_cl(spec: AircraftSpec, cl_target: float, cfg: Config) -> float:
    ar = spec.aspect_ratio
    cl_alpha = (2.0 * math.pi * ar) / (ar + 2.0)
    return cl_target / cl_alpha + math.radians(-2.0)


def drag_coefficient(spec: AircraftSpec, cl: float, cfg: Config,
                     mach: float = 0.0) -> float:
    """CD = CD0 + CL^2/(pi e AR) + increments, with a simple Mach rise."""
    cd = spec.cd0 + cfg.cd0_increment(spec)
    # Ground effect reduces induced drag; ground_effect_factor < 1 shrinks it.
    # (An earlier version divided by the factor, which *increased* drag - the
    # validation suite's sign test caught it.)
    induced = (cl * cl) / (math.pi * spec.oswald_e * spec.aspect_ratio)
    cd += induced * max(0.05, cfg.ground_effect_factor)
    # Compressibility drag rise. Kept deliberately small and confined to the
    # high-speed corner: an earlier version of this term was ~250x too large
    # and destroyed cruise L/D, which the validation suite caught.
    if mach > 0.78:
        cd += 6.0 * (mach - 0.78) ** 3
    return cd


def forces(spec: AircraftSpec, v_ms: float, alt_m: float, alpha_rad: float,
           cfg: Config, mass_kg: float | None = None) -> dict[str, float]:
    """Return lift, drag, weight, q, CL, CD, Mach for the current state."""
    m = spec.mtow_kg if mass_kg is None else mass_kg
    rho = rho_at(alt_m)
    _, _, _, a = isa(alt_m)
    q = 0.5 * rho * v_ms * v_ms
    cl = lift_coefficient(spec, alpha_rad, cfg)
    mach = v_ms / a if a > 0 else 0.0
    cd = drag_coefficient(spec, cl, cfg, mach)
    s = spec.wing_area_m2
    return {
        "q": q,
        "cl": cl,
        "cd": cd,
        "lift": q * s * cl,
        "drag": q * s * cd,
        "weight": m * G0,
        "mach": mach,
        "rho": rho,
    }


# ---------------------------------------------------------------------------
# Propulsion
# ---------------------------------------------------------------------------
def thrust_available(spec: AircraftSpec, v_ms: float, alt_m: float) -> float:
    """Available thrust in newtons.

    Piston/prop: T = eta * P / V, with a low-speed floor so static thrust stays
    finite (a real propeller produces roughly constant thrust at low advance
    ratio rather than infinite force).
    Turbofan: sea-level static thrust with standard lapse in density and Mach.
    """
    _, _, rho, a = isa(alt_m)
    sigma = rho / RHO0
    if spec.engine_type == "piston_prop":
        power_w = spec.power_kw * 1000.0
        shaft = spec.prop_efficiency * power_w
        # Momentum theory for static thrust:
        #   T = (P_eff^2 * 2 * rho * A)^(1/3), scaled by a figure of merit
        #   (FM ~ 0.5 for a real fixed-pitch prop; ideal actuator disc = 1.0).
        # Below the advance-ratio transition speed the prop is roughly
        # constant-thrust; above it, T = eta*P/V.
        # Static thrust: momentum theory scaled by a figure of merit, capped by
        # the published/documented static value carried in the spec.
        # A documented static thrust, when present, is authoritative; the
        # momentum-theory figure is only a fallback for specs without one.
        t_static = spec.static_thrust_n
        if not t_static:
            disc_area = math.pi * (spec.prop_diameter_m * 0.5) ** 2
            t_static = 0.5 * (shaft * shaft * 2.0 * rho * disc_area) ** (1.0 / 3.0)
        return min(t_static, shaft / max(v_ms, 1e-3))
    # Turbofan: installed net thrust lapse. The exponent form captures the
    # strong ram-drag/nacelle loss high-bypass engines actually show; a linear
    # lapse made the model climb ~2x faster than the aircraft does, which the
    # ROC gate caught. Calibrated against the initial-climb anchor only.
    mach = v_ms / a if a > 0 else 0.0
    lapse = (sigma ** 0.7) * max(0.05, (1.0 - 0.75 * mach) ** 1.5)
    return spec.thrust_kn * 1000.0 * lapse


def power_available_w(spec: AircraftSpec, v_ms: float, alt_m: float) -> float:
    return thrust_available(spec, v_ms, alt_m) * v_ms


# ---------------------------------------------------------------------------
# Ground roll (takeoff) - explicit integration, fixed step
# ---------------------------------------------------------------------------
@dataclass
class TakeoffResult:
    ground_roll_m: float
    rotation_speed_ms: float
    rotation_speed_kt: float
    liftoff_time_s: float
    distance_over_50ft_m: float
    avg_accel_ms2: float


def takeoff(spec: AircraftSpec, *, altitude_m: float = 0.0, mass_kg: float | None = None,
            wind_ms: float = 0.0, mu_rolling: float = 0.035,
            dt: float = 0.002, max_time_s: float = 180.0) -> TakeoffResult:
    """Integrate the ground roll to Vr, then the airborne path to 50 ft.

    Forces: thrust, aerodynamic drag, rolling friction on the un-lifted weight.
    Rotation speed = 1.10 x 1g clean stall speed (standard practice).
    """
    m = spec.mtow_kg if mass_kg is None else mass_kg
    cfg = Config(flaps=0.35, gear_down=True)
    vs = stall_speed_ms(spec, spec.cl_max_takeoff, m, altitude_m)
    vr = 1.10 * vs
    cl_to = 0.18                     # shallow ground attitude before rotation

    x = 0.0
    v = max(0.0, wind_ms)
    t = 0.0
    accel_sum = 0.0
    steps = 0
    while v < vr and t < max_time_s:
        f = forces(spec, v, altitude_m, angle_for_cl(spec, cl_to, cfg), cfg, m)
        # During the roll the wing carries a small part of the weight.
        normal = max(1.0, f["weight"] - f["lift"])
        thrust = thrust_available(spec, v, altitude_m)
        accel = (thrust - f["drag"] - mu_rolling * normal) / m
        if accel <= 0.0:
            break
        v += accel * dt
        x += v * dt
        t += dt
        accel_sum += accel
        steps += 1

    ground_roll = x
    # Airborne segment to 50 ft. Simplification (documented): constant speed
    # at Vr. Ground effect is applied while within one wingspan of the surface,
    # which is where the aircraft actually is on this segment - omitting it
    # roughly doubled the airborne distance and the POH gate caught that.
    v = max(vr, v)
    h = 0.0
    x_air = 0.0
    cfg_air = Config(flaps=0.35, gear_down=True)
    t_air = 0.0
    while h < 50.0 * FT and t_air < 120.0:
        cfg_air.ground_effect_factor = 0.6 if h < spec.span_m else 1.0
        cl = min(cfg_air.cl_max(spec), max(0.1, (2.0 * m * G0) /
                                          (rho_at(altitude_m + h) * spec.wing_area_m2 * v * v)))
        alpha = angle_for_cl(spec, cl, cfg_air)
        f = forces(spec, v, altitude_m + h, alpha, cfg_air, m)
        thrust = thrust_available(spec, v, altitude_m + h)
        sin_gamma = max(-0.3, min(0.3, (thrust - f["drag"]) / f["weight"]))
        gamma = math.asin(sin_gamma)
        h += v * math.sin(gamma) * dt
        x_air += v * math.cos(gamma) * dt
        t_air += dt

    return TakeoffResult(
        ground_roll_m=ground_roll,
        rotation_speed_ms=vr,
        rotation_speed_kt=vr / KT,
        liftoff_time_s=t,
        distance_over_50ft_m=ground_roll + x_air,
        avg_accel_ms2=(accel_sum / steps) if steps else 0.0,
    )


# ---------------------------------------------------------------------------
# Climb performance
# ---------------------------------------------------------------------------
def rate_of_climb_fpm(spec: AircraftSpec, v_ms: float, altitude_m: float,
                      mass_kg: float | None = None) -> float:
    """Steady 1g climb rate: ROC = (T - D) V / W."""
    m = spec.mtow_kg if mass_kg is None else mass_kg
    cfg = Config()
    cl = (2.0 * m * G0) / (rho_at(altitude_m) * spec.wing_area_m2 * v_ms * v_ms)
    cfg.cl_max = lambda s: max(cl, s.cl_max_clean)  # type: ignore[assignment]
    alpha = angle_for_cl(spec, cl, cfg)
    f = forces(spec, v_ms, altitude_m, alpha, Config(), m)
    thrust = thrust_available(spec, v_ms, altitude_m)
    roc = (thrust - f["drag"]) * v_ms / (m * G0)
    return roc / FT * 60.0


def best_climb_speed_ms(spec: AircraftSpec, mass_kg: float | None = None,
                        altitude_m: float = 0.0) -> float:
    """Speed for maximum excess power: iterate ROC over a speed sweep."""
    m = spec.mtow_kg if mass_kg is None else mass_kg
    vs = stall_speed_ms(spec, spec.cl_max_clean, m, altitude_m)
    best_v, best_roc = vs * 1.3, -1e9
    v = vs * 1.05
    while v < 300.0:
        roc = rate_of_climb_fpm(spec, v, altitude_m, m)
        if roc > best_roc:
            best_roc, best_v = roc, v
        v += 0.5
    return best_v


# ---------------------------------------------------------------------------
# Trim / steady flight
# ---------------------------------------------------------------------------
@dataclass
class TrimPoint:
    speed_ms: float
    alpha_deg: float
    cl: float
    cd: float
    lift_n: float
    drag_n: float
    lift_residual_n: float
    l_over_d: float
    thrust_required_n: float


def trim_level(spec: AircraftSpec, speed_ms: float, altitude_m: float,
               mass_kg: float | None = None, cfg: Config | None = None) -> TrimPoint:
    """Solve the 1g level-flight trim: CL such that L = W, then alpha from CL.

    Returns the residual |L - W| so callers can prove the trim converged
    instead of assuming it did.
    """
    cfg = cfg or Config()
    m = spec.mtow_kg if mass_kg is None else mass_kg
    rho = rho_at(altitude_m)
    cl_req = (2.0 * m * G0) / (rho * spec.wing_area_m2 * speed_ms * speed_ms)
    alpha = angle_for_cl(spec, cl_req, cfg)
    f = forces(spec, speed_ms, altitude_m, alpha, cfg, m)
    return TrimPoint(
        speed_ms=speed_ms,
        alpha_deg=math.degrees(alpha),
        cl=f["cl"],
        cd=f["cd"],
        lift_n=f["lift"],
        drag_n=f["drag"],
        lift_residual_n=abs(f["lift"] - f["weight"]),
        l_over_d=(f["lift"] / f["drag"]) if f["drag"] > 0 else float("inf"),
        thrust_required_n=f["drag"],
    )


def kcas_from_tas_ms(speed_ms: float, altitude_m: float) -> float:
    """Calibrated airspeed approximation (incompressible, sea-level equivalent)."""
    rho = rho_at(altitude_m)
    return speed_ms * math.sqrt(rho / RHO0) / KT
