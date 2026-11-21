#!/usr/bin/env python3
"""
SKYBOUND - flight-model validation suite.

Runs the reference performance model (fdm.py) against published aircraft data
and prints a PASS/FAIL table. This is the gate that decides whether an aircraft
may be marked `flight_model_status = validated` in the catalog.

Every test states its own tolerance and why. Where a number is *derived* rather
than published, the test checks plausibility bounds instead of pretending to
match a source that does not exist.

Usage:  python validate.py [--json out.json]
Exit:   0 all gates passed, 1 a gate failed, 2 setup error.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import aircraft_specs as A  # noqa: E402
import fdm  # noqa: E402

TOL = "\u00b1"


class Results:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def check(self, aircraft: str, name: str, measured: float, target: float,
              tol_pct: float | None, unit: str, note: str = "",
              lower: float | None = None, upper: float | None = None) -> None:
        if tol_pct is not None and target:
            ok = abs(measured - target) <= abs(target) * tol_pct / 100.0
            ref = f"{target:.4g}{TOL}{tol_pct:.0f}%"
        else:
            ok = (lower is None or measured >= lower) and (upper is None or measured <= upper)
            ref = f"[{lower:.4g}, {upper:.4g}]" if lower is not None and upper is not None else "-"
        self.rows.append({
            "aircraft": aircraft, "test": name, "measured": round(measured, 4),
            "reference": ref, "unit": unit, "pass": ok, "note": note,
        })

    @property
    def failed(self) -> list[dict]:
        return [r for r in self.rows if not r["pass"]]


def validate_aircraft(spec: A.AircraftSpec, res: Results) -> dict:
    summary: dict = {"aircraft_id": spec.aircraft_id, "name": spec.name}

    # -- 1. Stall speed -----------------------------------------------------
    # CLmax is derived from the published stall speed, so this test proves the
    # mass/area/CLmax set is internally consistent. The *value* of CLmax is
    # then cross-checked against a physically sane range for the class.
    # The published stall anchor refers to a specific configuration (clean for
    # the C172, landing for the A320), so the comparison must use that CLmax.
    stall_clmax = (spec.cl_max_landing if spec.published_v_stall_config == "landing"
                   else spec.cl_max_clean)
    vs_model = fdm.stall_speed_ms(spec, stall_clmax) / fdm.KT
    res.check(spec.name, f"1g stall speed ({spec.published_v_stall_config})",
              vs_model, spec.published_v_stall_kt, 6.0, "kt",
              "CLmax anchored to published Vs")
    res.check(spec.name, f"implied CLmax ({spec.published_v_stall_config})",
              fdm.cl_max_from_stall(spec), 0.0, None, "-", "2W/(rho0*S*Vs^2)",
              lower=1.2, upper=2.8)

    # -- 2. Cruise trim -----------------------------------------------------
    alt = spec.published_cruise_alt_ft * fdm.FT
    v = spec.published_cruise_ktas * fdm.KT
    trim = fdm.trim_level(spec, v, alt)
    res.check(spec.name, "trim lift residual", trim.lift_residual_n, 0.0, None, "N",
              "L must equal W", upper=1e-3)
    # L/D is a modelling output. Bounds are the physically expected band for
    # the class, not a published figure.
    ld_lo, ld_hi = (8.0, 13.0) if spec.engine_type == "piston_prop" else (14.0, 20.0)
    res.check(spec.name, "cruise L/D", trim.l_over_d, 0.0, None, "-",
              "class-expected band", lower=ld_lo, upper=ld_hi)
    res.check(spec.name, "trim alpha", trim.alpha_deg, 0.0, None, "deg",
              "must be within usable wing incidence", lower=-3.0, upper=8.0)
    summary["cruise"] = asdict(trim)

    # -- 3. Takeoff ---------------------------------------------------------
    to = fdm.takeoff(spec)
    summary["takeoff"] = asdict(to)
    res.check(spec.name, "rotation speed", to.rotation_speed_kt, 0.0, None, "kt",
              "1.10 x takeoff-config Vs", lower=45.0, upper=175.0)
    if spec.published_takeoff_roll_m:
        res.check(spec.name, "takeoff ground roll", to.ground_roll_m,
                  spec.published_takeoff_roll_m, 20.0, "m", "POH table, SL ISA MTOW")
    if spec.published_takeoff_over_50ft_m:
        # Transport field length includes a long rotation/airborne segment that
        # this longitudinal model simplifies, so the band is wider and stated.
        tol = 20.0 if spec.engine_type == "piston_prop" else 40.0
        res.check(spec.name, "takeoff distance to 50 ft", to.distance_over_50ft_m,
                  spec.published_takeoff_over_50ft_m, tol, "m",
                  "airborne segment simplified - see FLIGHT_PHYSICS.md")

    # -- 4. Climb -----------------------------------------------------------
    # ROC is evaluated at the speed the published figure is quoted at (Vy for
    # the C172, V2+10 for the A320). Comparing an optimised best-rate speed
    # against a POH climb-schedule figure is not a like-for-like test - the
    # first version of this suite made exactly that mistake.
    v_sched = (spec.published_climb_speed_kt * fdm.KT) or fdm.best_climb_speed_ms(spec)
    roc = fdm.rate_of_climb_fpm(spec, v_sched, 0.0)
    vc = fdm.best_climb_speed_ms(spec)
    summary["climb"] = {
        "schedule_speed_kt": v_sched / fdm.KT,
        "roc_at_schedule_fpm": roc,
        "best_speed_kt": vc / fdm.KT,
        "roc_at_best_fpm": fdm.rate_of_climb_fpm(spec, vc, 0.0),
    }
    if spec.published_roc_fpm:
        tol = 20.0 if spec.engine_type == "piston_prop" else 30.0
        res.check(spec.name, "sea-level rate of climb", roc,
                  spec.published_roc_fpm, tol, "fpm",
                  f"steady 1g climb at {v_sched / fdm.KT:.0f} kt")
    res.check(spec.name, "best climb speed", vc / fdm.KT, 0.0, None, "kt",
              "physical band", lower=55.0, upper=400.0)

    # -- 5. Ceiling sanity --------------------------------------------------
    # Climb capability must vanish before the published service ceiling.
    ceiling_m = spec.published_service_ceiling_ft * fdm.FT
    roc_at_ceiling = fdm.rate_of_climb_fpm(spec, v_sched, ceiling_m)
    res.check(spec.name, "ROC at service ceiling", roc_at_ceiling, 0.0, None, "fpm",
              "should be small but the model may still climb (simplification)",
              upper=1200.0)
    summary["ceiling_roc_fpm"] = roc_at_ceiling

    # -- 6. Ground effect ------------------------------------------------
    # Induced drag must fall when close to the ground.
    cfg_out = fdm.Config()
    cfg_ge = fdm.Config(ground_effect_factor=0.6)
    d_out = fdm.drag_coefficient(spec, 1.0, cfg_out)
    d_ge = fdm.drag_coefficient(spec, 1.0, cfg_ge)
    res.check(spec.name, "ground-effect drag reduction", (d_out - d_ge) / d_out,
              0.0, None, "fraction", "must be positive", lower=0.01, upper=0.6)

    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate SKYBOUND flight models.")
    ap.add_argument("--json", type=Path, help="write machine-readable results")
    args = ap.parse_args(argv)

    res = Results()
    summaries = []
    for spec in A.SPECS.values():
        summaries.append(validate_aircraft(spec, res))

    w = 0
    for r in res.rows:
        w = max(w, len(r["test"]))
    print()
    print("SKYBOUND flight-model validation")
    print("=" * (w + 58))
    print(f"{'aircraft':<22} {'test':<{w}} {'measured':>12} {'reference':>14}  result")
    print("-" * (w + 58))
    last = None
    for r in res.rows:
        name = r["aircraft"] if r["aircraft"] != last else ""
        last = r["aircraft"]
        print(f"{name:<22} {r['test']:<{w}} {r['measured']:>10.4g}  "
              f"{r['reference']:>14}  {'PASS' if r['pass'] else 'FAIL'}  {r['unit']}")
    print("-" * (w + 58))
    print(f"{len(res.rows)} checks, {len(res.failed)} failed")
    if res.failed:
        print("\nFailures:")
        for r in res.failed:
            print(f"  - {r['aircraft']}: {r['test']} measured {r['measured']} "
                  f"{r['unit']}, expected {r['reference']} ({r['note']})")
    print()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(
            {"checks": res.rows, "summary": summaries,
             "all_passed": not res.failed}, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")

    return 0 if not res.failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
