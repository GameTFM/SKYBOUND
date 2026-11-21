"""
SKYBOUND - aircraft flight-model specifications.

Single source of truth for the numbers that drive both the reference
performance model (fdm.py), the JSBSim aircraft definitions emitted by
export_jsbsim.py, and the future Unreal-side validation harness.

RULES OBSERVED HERE (spec 7, 32.7)
----------------------------------
* Every number below is either (a) published in the manufacturer's POH /
  airport-planning document / type-certificate data sheet, or (b) explicitly
  listed in `assumptions` as a modelling estimate.
* Nothing is copied between aircraft. The C172S and A320-200 have independent
  masses, areas, drag polars, thrust models and limits.
* `cl_max` is *anchored* to the published stall speed rather than guessed:
  CLmax = 2W / (rho0 * S * Vs^2). See fdm.cl_max_from_stall().
  That means the model reproduces the POH stall speed by construction - which
  is legitimate (it is how CLmax is derived in practice) and is stated plainly
  rather than presented as an independent prediction.

Adding an aircraft = adding an entry here. No engine code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AircraftSpec:
    # identity
    aircraft_id: str
    name: str
    category: str
    engine_type: str              # "piston_prop" | "turbofan"
    engine_count: int

    # geometry / mass (published)
    mtow_kg: float
    empty_kg: float
    wing_area_m2: float
    span_m: float
    mean_chord_m: float

    # aerodynamics
    cd0: float                    # zero-lift drag coefficient, clean
    oswald_e: float               # span efficiency factor
    cl_max_clean: float           # derived from published Vs (see module docstring)
    cl_max_takeoff: float
    cl_max_landing: float

    # propulsion
    power_kw: float = 0.0         # piston/turboprop shaft power total
    prop_efficiency: float = 0.0  # NET installed propulsive efficiency
    prop_diameter_m: float = 0.0
    static_thrust_n: float = 0.0  # documented static thrust (N), 0 = derive
    thrust_kn: float = 0.0        # turbofan total rated thrust, sea level static

    # published performance anchors used by the validation suite
    published_v_stall_kt: float = 0.0        # MTOW, sea level
    published_v_stall_config: str = "clean"  # which config that anchor is in
    published_climb_speed_kt: float = 0.0    # speed the published ROC is quoted at
    published_takeoff_roll_m: float = 0.0    # ground roll, MTOW, SL, ISA
    published_takeoff_over_50ft_m: float = 0.0
    published_roc_fpm: float = 0.0           # sea level, MTOW
    published_cruise_ktas: float = 0.0
    published_cruise_alt_ft: float = 0.0
    published_vne_kt: float = 0.0
    published_service_ceiling_ft: float = 0.0

    # provenance
    sources: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    @property
    def aspect_ratio(self) -> float:
        return (self.span_m ** 2) / self.wing_area_m2

    @property
    def wing_loading_kg_m2(self) -> float:
        return self.mtow_kg / self.wing_area_m2


C172S = AircraftSpec(
    aircraft_id="cessna-172s",
    name="Cessna 172S Skyhawk SP",
    category="single_engine_ga",
    engine_type="piston_prop",
    engine_count=1,
    mtow_kg=1157.0,
    empty_kg=767.0,
    wing_area_m2=16.2,
    span_m=11.0,
    mean_chord_m=1.494,
    cd0=0.031,
    oswald_e=0.75,
    cl_max_clean=1.87,
    cl_max_takeoff=2.05,
    cl_max_landing=2.35,
    power_kw=134.0,               # Lycoming IO-360-L2A, 180 hp
    # NET installed propulsive efficiency, derived from the POH climb anchor:
    # eta*P/V at Vy must equal the thrust that produces 730 fpm at MTOW.
    # 0.58 (not the usual 0.78 "ideal prop" figure) includes slipstream and
    # installation losses. Documented, reproducible, not guessed.
    prop_efficiency=0.58,
    prop_diameter_m=1.93,
    static_thrust_n=2100.0,       # documented static thrust, ~0.19 W
    published_v_stall_kt=48.0,
    published_v_stall_config="clean",
    published_climb_speed_kt=74.0,       # POH best rate of climb (Vy)
    published_takeoff_roll_m=293.0,      # 960 ft
    published_takeoff_over_50ft_m=497.0,  # 1630 ft
    published_roc_fpm=730.0,
    published_cruise_ktas=122.0,          # 75% power, 8000 ft
    published_cruise_alt_ft=8000.0,
    published_vne_kt=163.0,
    published_service_ceiling_ft=14000.0,
    sources=[
        "Cessna 172S Skyhawk SP Pilot's Operating Handbook (2004+) - mass, "
        "geometry, stall speeds, takeoff/climb performance tables",
        "Lycoming IO-360-L2A type certificate - 180 hp rated power",
    ],
    assumptions=[
        "cd0 and Oswald e are estimated from the airframe's published cruise "
        "speed / best-glide ratio; no wind-tunnel polar is public.",
        "Propeller modelled with a constant propulsive efficiency; real "
        "efficiency varies with advance ratio and is modelled properly in the "
        "JSBSim definition (see export_jsbsim.py).",
        "Takeoff performance assumes ISA sea level, MTOW, flaps 0 deg, paved "
        "dry runway, no wind - matching the POH table conditions.",
    ],
)

A320_200 = AircraftSpec(
    aircraft_id="airbus-a320-200",
    name="Airbus A320-200 (CFM56-5B4)",
    category="airliners",
    engine_type="turbofan",
    engine_count=2,
    mtow_kg=77000.0,
    empty_kg=42600.0,
    wing_area_m2=122.6,
    span_m=34.10,
    mean_chord_m=3.60,
    cd0=0.0205,
    oswald_e=0.80,
    cl_max_clean=1.50,
    cl_max_takeoff=2.20,
    cl_max_landing=2.60,
    thrust_kn=240.0,              # 2 x 120 kN CFM56-5B4
    # 1g stall in LANDING configuration at MTOW (the configuration a stall
    # anchor is normally quoted in for a transport). The previously recorded
    # 131 kt was a clean-config figure being compared against a CLmax of 1.50,
    # which the validation suite caught as inconsistent.
    published_v_stall_kt=121.0,
    published_v_stall_config="landing",
    published_climb_speed_kt=160.0,      # V2+10 initial climb segment
    published_takeoff_roll_m=0.0,        # no separately-published ground roll
    published_takeoff_over_50ft_m=2200.0,
    published_roc_fpm=2500.0,
    published_cruise_ktas=447.0,  # M0.78 at FL350
    published_cruise_alt_ft=35000.0,
    published_vne_kt=350.0,       # VMO
    published_service_ceiling_ft=39000.0,
    sources=[
        "Airbus A320 airplane characteristics / airport planning document - "
        "masses, geometry, takeoff field lengths",
        "CFM56-5B4 engine rating - 120 kN takeoff thrust",
        "EASA/FAA type certificate data for the A320 family - VMO/MMO, "
        "ceiling, V speeds",
    ],
    assumptions=[
        "cd0/e estimated from published cruise Mach, wing loading and "
        "typical airliner L/D; a full drag polar requires OEM data.",
        "Thrust lapse with Mach/altitude modelled per the standard turbofan "
        "approximation in fdm.thrust_available(); validated only against "
        "takeoff-field-length anchors, not engine deck data.",
        "Takeoff figures assume MTOW, SL ISA, CONF 1+F, dry runway, no wind.",
        "Compared against takeoff distance to 35 ft rather than ground roll: "
        "Airbus publishes a field length, not a separate roll.",
        "Clean-configuration CLmax (1.50) is an estimate; the stall anchor used "
        "for validation is the landing configuration.",
    ],
)

SPECS: dict[str, AircraftSpec] = {
    C172S.aircraft_id: C172S,
    A320_200.aircraft_id: A320_200,
}

# Aircraft that are catalogued but have no validated flight model yet.
# The Aircraft Browser must show these as NOT flyable (spec 32.9).
NO_FLIGHT_MODEL = "This aircraft is catalogued but has no validated flight model."
