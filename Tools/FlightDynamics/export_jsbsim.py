#!/usr/bin/env python3
"""
SKYBOUND - JSBSim aircraft definition exporter.

Generates the runtime flight-model files consumed by the Unreal project via the
FlightSimulation plugin (JSBSim, dynamically linked - see LICENSES_AND_ATTRIBUTION.md).

HONESTY NOTES (read before trusting these files)
------------------------------------------------
* These definitions are PERFORMANCE-GRADE. Mass, geometry, lift-curve slope,
  drag polar and thrust come from aircraft_specs.py and are anchored to
  published data (validated by validate.py).
* The lateral/directional stability derivatives (Cl_beta, Cn_beta, Cm_q, ...)
  are ESTIMATES from tail-volume geometry, not wind-tunnel or OEM data. They
  are good enough to fly plausibly and to exercise the plugin, but they are
  labelled `estimated` in the file header and in the aircraft catalog.
* Engine and propeller *behaviour* is delegated to JSBSim's bundled engine and
  propeller definitions (engIO360C, prop_75in2f, CFM56_5) rather than
  re-derived here. Those are LGPL parts of JSBSim and ship with it.

Usage:
    python export_jsbsim.py [--out DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import aircraft_specs as A  # noqa: E402
import fdm  # noqa: E402

KT = fdm.KT

# JSBSim engine/propeller parts that ship with JSBSim 1.3.x.
PARTS = {
    "cessna-172s": {"engine": "engIO360C", "thruster": "prop_75in2f"},
    "airbus-a320-200": {"engine": "CFM56_5", "thruster": None},
}


def _cl_alpha_per_deg(spec: A.AircraftSpec) -> float:
    ar = spec.aspect_ratio
    return (2.0 * 3.141592653589793 * ar) / (ar + 2.0) / 57.29577951308232


def _aero_axes(spec: A.AircraftSpec) -> str:
    """Lift/drag/side + moment axes.

    Lift and drag mirror fdm.py exactly. Moment derivatives are estimates from
    tail volume; documented in the file header.
    """
    cla = _cl_alpha_per_deg(spec)
    alpha0 = -2.0
    # Tail volume coefficients for the estimate (htailarm/chord etc.)
    htail_arm = 4.7 if spec.engine_type == "piston_prop" else 14.0
    vtail_arm = 4.9 if spec.engine_type == "piston_prop" else 14.0
    htail_area = 2.0 if spec.engine_type == "piston_prop" else 31.0
    vtail_area = 1.5 if spec.engine_type == "piston_prop" else 22.0
    # Cm_alpha ~ -a_t * Vh  (classic tail-volume formula)
    vh = (htail_area * htail_arm) / (spec.wing_area_m2 * spec.mean_chord_m)
    cm_alpha_per_rad = -cla * 57.29577951308232 * vh * 0.8
    vv = (vtail_area * vtail_arm) / (spec.wing_area_m2 * spec.span_m)
    cn_beta_per_deg = -0.055 if spec.engine_type == "piston_prop" else -0.09
    cl_beta_per_deg = 0.02 if spec.engine_type == "piston_prop" else 0.03

    def table_2pt(x0: float, y0: float, x1: float, y1: float) -> str:
        return (f"<table><independentVar>aero/alpha-deg</independentVar>"
                f"<tableData>{x0} {y0} {x1} {y1}</tableData></table>")

    # NOTE ON JSBSim AXIS SEMANTICS: functions inside <axis> return a
    # COEFFICIENT. JSBSim itself multiplies by qbar and the relevant reference
    # area. Multiplying by qbar/Sw here too (as an earlier version did) double
    # counts, and referencing aero/cl-squared at zero airspeed produced 0/0 = NaN
    # on the very first integration step.
    return f"""
  <alphalimits unit="DEG">
    <min>-12</min>
    <max>18</max>
  </alphalimits>

  <axis name="LIFT">
    <function name="aero/coefficient/CLalpha">
      <description>CL = CLalpha*(alpha - alpha0), clipped at CLmax</description>
      <table>
          <independentVar>aero/alpha-deg</independentVar>
          <tableData>
            -12 {cla * (-12 - alpha0):.5f}
            -4 {cla * (-4 - alpha0):.5f}
            0 {cla * (0 - alpha0):.5f}
            4 {cla * (4 - alpha0):.5f}
            8 {cla * (8 - alpha0):.5f}
            12 {cla * (12 - alpha0):.5f}
            15 {cla * (15 - alpha0):.5f}
            16 {spec.cl_max_clean:.5f}
            18 {spec.cl_max_clean * 0.92:.5f}
            30 {spec.cl_max_clean * 0.62:.5f}
          </tableData>
        </table>
    </function>
  </axis>

  <axis name="DRAG">
    <function name="aero/coefficient/CDo">
      <description>Zero-lift drag coefficient (clean)</description>
      <value>{spec.cd0:.5f}</value>
    </function>
    <function name="aero/coefficient/CDi">
      <description>Induced drag: CL^2 / (pi*e*AR)</description>
      <product>
        <property>aero/coefficient/CLalpha</property>
        <property>aero/coefficient/CLalpha</property>
        <value>{1.0 / (3.141592653589793 * spec.oswald_e * spec.aspect_ratio):.5f}</value>
      </product>
    </function>
  </axis>

  <axis name="SIDE">
    <function name="aero/coefficient/CYb">
      <product>
        <property>aero/beta-rad</property>
        <value>-1.0</value>
      </product>
    </function>
  </axis>

  <axis name="PITCH">
    <function name="aero/coefficient/Cmalpha">
      <description>Static pitch stability, tail-volume estimate (ESTIMATED)</description>
      <table>
        <independentVar>aero/alpha-rad</independentVar>
        <!-- Cm_alpha must be NEGATIVE for a statically stable aircraft.
             An earlier version applied a second minus sign here, which made the
             model longitudinally unstable and the state diverged within 3 s. -->
        <tableData>
          -0.20 {cm_alpha_per_rad * -0.20:.6f}
          0.0 0.0
          0.20 {cm_alpha_per_rad * 0.20:.6f}
          0.30 {cm_alpha_per_rad * 0.30:.6f}
        </tableData>
      </table>
    </function>
    <function name="aero/coefficient/Cmde">
      <description>Elevator authority (ESTIMATED - no OEM data available).</description>
      <product>
        <property>fcs/elevator-pos-rad</property>
        <value>{abs(cm_alpha_per_rad) * 0.35:.5f}</value>
      </product>
    </function>
  </axis>

  <axis name="ROLL">
    <function name="aero/coefficient/Clb">
      <product>
        <property>aero/beta-rad</property>
        <value>{cl_beta_per_deg:.5f}</value>
      </product>
    </function>
    <function name="aero/coefficient/Clda">
      <description>Differential aileron (core JSBSim surface properties)</description>
      <product>
        <difference>
          <property>fcs/left-aileron-pos-rad</property>
          <property>fcs/right-aileron-pos-rad</property>
        </difference>
        <value>{0.09 if spec.engine_type == 'piston_prop' else 0.055:.5f}</value>
      </product>
    </function>
  </axis>

  <axis name="YAW">
    <function name="aero/coefficient/Cnb">
      <product>
        <property>aero/beta-rad</property>
        <value>{cn_beta_per_deg:.5f}</value>
      </product>
    </function>
    <function name="aero/coefficient/Cndr">
      <product>
        <property>fcs/rudder-pos-rad</property>
        <value>-{0.06 if spec.engine_type == 'piston_prop' else 0.045:.5f}</value>
      </product>
    </function>
  </axis>
"""


def build_xml(spec: A.AircraftSpec) -> str:
    parts = PARTS[spec.aircraft_id]
    half_span = spec.span_m / 2.0
    cg_x = 0.30 * spec.mean_chord_m
    # Gear geometry: nose ahead of CG, mains slightly behind.
    nose_x = cg_x + (2.6 if spec.engine_type == "piston_prop" else 12.0)
    main_x = cg_x - (0.55 if spec.engine_type == "piston_prop" else 1.5)
    main_y = half_span * 0.33
    leg_h = 1.15 if spec.engine_type == "piston_prop" else 2.6
    inertia_scale = spec.mtow_kg / 1157.0
    ixx = 1400.0 * inertia_scale * (1.0 if spec.engine_type == "piston_prop" else 6.0)
    iyy = 1800.0 * inertia_scale * (1.0 if spec.engine_type == "piston_prop" else 9.0)
    izz = 2900.0 * inertia_scale * (1.0 if spec.engine_type == "piston_prop" else 7.0)
    fuel_kg = 145.0 if spec.engine_type == "piston_prop" else 15000.0
    spring = 30000.0 if spec.engine_type == "piston_prop" else 900000.0
    damp = 8000.0 if spec.engine_type == "piston_prop" else 240000.0
    max_steer = 60 if spec.engine_type == "piston_prop" else 30

    # JSBSim requires the thruster to be nested INSIDE its <engine> element.
    # Turbofans use the "direct" thruster; props use a real propeller part and
    # need sense=-1 (the bundled JSBSim convention for a tractor prop).
    engines = []
    if spec.engine_count == 1:
        y_offsets = [0.0]
    else:
        y_offsets = [-0.168 * spec.span_m, 0.168 * spec.span_m]
    for i, y in enumerate(y_offsets):
        if parts["thruster"]:
            thruster = f"""
        <thruster file="{parts['thruster']}">
          <location unit="M"><x>{-nose_x:.3f}</x><y>{y:.3f}</y><z>-0.35</z></location>
          <orient unit="DEG"><roll>0</roll><pitch>-2</pitch><yaw>0</yaw></orient>
          <sense>-1</sense>
          <p_factor>10.0</p_factor>
        </thruster>"""
        else:
            thruster = f"""
        <thruster file="direct">
          <location unit="M"><x>{-nose_x:.3f}</x><y>{y:.3f}</y><z>-0.6</z></location>
          <orient unit="DEG"><roll>0</roll><pitch>0</pitch><yaw>0</yaw></orient>
        </thruster>"""
        engines.append(f"""
    <engine file="{parts['engine']}">
      <location unit="M"><x>{-nose_x:.3f}</x><y>{y:.3f}</y><z>0</z></location>
      <orient unit="DEG"><roll>0</roll><pitch>0</pitch><yaw>0</yaw></orient>
      <feed>0</feed>{thruster}
    </engine>""")
    engine_block = "".join(engines)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!--
  SKYBOUND aircraft definition - GENERATED by Tools/FlightDynamics/export_jsbsim.py
  Do not hand-edit: change aircraft_specs.py and re-run the exporter.

  MODEL GRADE: performance-grade.
    - mass / geometry / lift slope / drag polar / thrust: anchored to published
      data and validated by validate.py.
    - lateral-directional and pitch derivatives: ESTIMATED from tail volume.
      Not wind-tunnel or OEM data. Suitable for flight, not for certification.
  ENGINE/THRUSTER: JSBSim bundled parts ({parts['engine']}{', ' + parts['thruster'] if parts['thruster'] else ''}).
-->
<fdm_config name="skybound_{spec.aircraft_id.replace('-', '_')}" version="2.0" release="ALPHA">
  <fileheader>
    <author>SKYBOUND</author>
    <filetype>Flight Dynamics Model</filetype>
    <description>{spec.name} - generated from validated SKYBOUND specifications</description>
    <version>1.0</version>
    <reference unit="M">{spec.sources[0]}</reference>
  </fileheader>

  <metrics>
    <wingarea unit="M2">{spec.wing_area_m2}</wingarea>
    <wingspan unit="M">{spec.span_m}</wingspan>
    <chord unit="M">{spec.mean_chord_m}</chord>
    <htailarea unit="M2">{2.0 if spec.engine_type == 'piston_prop' else 31.0}</htailarea>
    <htailarm unit="M">{4.7 if spec.engine_type == 'piston_prop' else 14.0}</htailarm>
    <vtailarea unit="M2">{1.5 if spec.engine_type == 'piston_prop' else 22.0}</vtailarea>
    <vtailarm unit="M">{4.9 if spec.engine_type == 'piston_prop' else 14.0}</vtailarm>
    <wing_incidence unit="DEG">2.0</wing_incidence>
    <location name="AERORP" unit="M"><x>{cg_x:.3f}</x><y>0</y><z>0</z></location>
    <location name="EYEPOINT" unit="M"><x>{cg_x + 0.6:.3f}</x><y>0</y><z>-1.1</z></location>
    <location name="VRP" unit="M"><x>0</x><y>0</y><z>0</z></location>
  </metrics>

  <mass_balance>
    <emptywt unit="KG">{spec.empty_kg}</emptywt>
    <location name="CG" unit="M"><x>{cg_x:.3f}</x><y>0</y><z>0</z></location>
    <inertia unit="KG*M2">
      <ixx>{ixx:.1f}</ixx><iyy>{iyy:.1f}</iyy><izz>{izz:.1f}</izz><ixz>0</ixz>
    </inertia>
  </mass_balance>

  <ground_reactions>
    <!-- Gear contact Z convention: NEGATIVE places the legs below the reference
         point, matching JSBSim's own c172x model. Verified in engine: with
         negative Z the aircraft reports weight-on-wheels at t=0; with positive
         Z it free-falls and the state diverges. -->
    <contact type="BOGEY" name="NOSE">
      <location unit="M"><x>{-nose_x:.3f}</x><y>0</y><z>{-leg_h:.2f}</z></location>
      <static_friction>0.80</static_friction>
      <dynamic_friction>0.50</dynamic_friction>
      <rolling_friction>0.020</rolling_friction>
      <spring_coeff unit="N/M">{spring:.0f}</spring_coeff>
      <damping_coeff unit="N/M/SEC">{damp:.0f}</damping_coeff>
      <max_steer unit="DEG">{max_steer}</max_steer>
    </contact>
    <contact type="BOGEY" name="LEFT_MAIN">
      <location unit="M"><x>{-main_x:.3f}</x><y>{-main_y:.3f}</y><z>{-leg_h:.2f}</z></location>
      <static_friction>0.80</static_friction>
      <dynamic_friction>0.50</dynamic_friction>
      <rolling_friction>0.020</rolling_friction>
      <spring_coeff unit="N/M">{spring:.0f}</spring_coeff>
      <damping_coeff unit="N/M/SEC">{damp:.0f}</damping_coeff>
    </contact>
    <contact type="BOGEY" name="RIGHT_MAIN">
      <location unit="M"><x>{-main_x:.3f}</x><y>{main_y:.3f}</y><z>{-leg_h:.2f}</z></location>
      <static_friction>0.80</static_friction>
      <dynamic_friction>0.50</dynamic_friction>
      <rolling_friction>0.020</rolling_friction>
      <spring_coeff unit="N/M">{spring:.0f}</spring_coeff>
      <damping_coeff unit="N/M/SEC">{damp:.0f}</damping_coeff>
    </contact>
  </ground_reactions>

  <propulsion>{engine_block}
    <tank type="FUEL">
      <location unit="M"><x>0</x><y>0</y><z>0</z></location>
      <capacity unit="KG">{fuel_kg:.0f}</capacity>
      <contents unit="KG">{fuel_kg:.0f}</contents>
    </tank>
  </propulsion>

<aerodynamics>{_aero_axes(spec)}
  </aerodynamics>
</fdm_config>
"""


def main(argv: list[str] | None = None) -> int:
    project = HERE.parent.parent
    ap = argparse.ArgumentParser(description="Export JSBSim aircraft definitions.")
    ap.add_argument("--out", type=Path,
                    default=project / "Content" / "Data" / "FlightModels")
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    for spec in A.SPECS.values():
        model_name = f"skybound_{spec.aircraft_id.replace('-', '_')}"
        d = args.out / model_name
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{model_name}.xml"
        path.write_text(build_xml(spec), encoding="utf-8")
        print(f"[export] {path}  ({path.stat().st_size:,} bytes)")
    print(f"[export] {len(A.SPECS)} JSBSim definitions written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
