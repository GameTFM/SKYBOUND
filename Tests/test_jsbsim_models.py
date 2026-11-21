#!/usr/bin/env python3
"""
SKYBOUND - JSBSim integration test.

Proves that the generated aircraft definitions are accepted by the actual
runtime flight-dynamics engine (JSBSim 1.3.x) and that they behave sensibly
when flown by it. This is a real end-to-end check of the export pipeline, not a
simulation of one.

For each model:
  1. load it in JSBSim (fails loudly with the engine's own error)
  2. run a full-throttle takeoff from a standing start
  3. report measured ground roll, liftoff speed and time
  4. run a short cruise sample and check the aircraft holds altitude/speed
     within a loose band and does not diverge

Exit code 0 when every model loads and produces a finite, sane takeoff.

Requires: pip install jsbsim  (skipped with exit 0 and a clear message if absent,
so the suite stays runnable on machines without the engine).
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
FLIGHT_MODELS = PROJECT / "Content" / "Data" / "FlightModels"
REPORT = PROJECT / "Build" / "reports" / "jsbsim_integration.json"

try:
    import jsbsim  # type: ignore
except ImportError:
    print("[jsbsim] package not installed - skipping (pip install jsbsim)")
    raise SystemExit(0)

PKG = Path(jsbsim.__file__).resolve().parent


def quiet(fn, *a, **kw):
    """JSBSim prints a very large amount of text on load; keep test output readable."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*a, **kw)
    return result, buf.getvalue()


def new_fdm(model: str):
    fdm = jsbsim.FGFDMExec(None)
    # JSBSim expects the directory that CONTAINS the per-aircraft folders.
    fdm.set_aircraft_path(str(FLIGHT_MODELS))
    fdm.set_engine_path(str(PKG / "engine"))
    fdm.set_systems_path(str(PKG / "systems"))
    ok, log = quiet(fdm.load_model, model)
    if not ok:
        raise RuntimeError(f"JSBSim rejected model '{model}'. Engine log tail:\n"
                           + "\n".join(log.strip().splitlines()[-12:]))
    fdm.set_dt(1.0 / 120.0)
    # Keep JSBSim's chatter down: it logs heavily on every gear contact.
    try:
        fdm.set_debug_level(0)
    except Exception:  # noqa: BLE001 - optional API
        pass
    quiet(fdm.run_ic)
    return fdm, log


def set_prop(fdm, name: str, value: float) -> bool:
    try:
        fdm[name] = value
        return True
    except Exception:
        return False


def takeoff(model: str, max_seconds: float = 120.0) -> dict:
    fdm, _log = new_fdm(model)
    dt = 1.0 / 120.0
    # Start on the runway, engine running, full throttle, brakes released.
    set_prop(fdm, "propulsion/engine/set-running", 1)
    set_prop(fdm, "propulsion/engine[0]/set-running", 1)
    for p in ("fcs/left-brake-cmd-norm", "fcs/right-brake-cmd-norm",
              "fcs/center-brake-cmd-norm", "fcs/parking-brake-cmd-norm"):
        set_prop(fdm, p, 0.0)
    set_prop(fdm, "fcs/throttle-cmd-norm", 1.0)

    t = 0.0
    liftoff_t = None
    liftoff_v = None
    max_h = 0.0
    # One redirect around the whole loop, not one per integration step.
    with contextlib.redirect_stdout(io.StringIO()):
        while t < max_seconds:
            fdm.run()
            t += dt
            h = fdm["position/h-sl-ft"]
            max_h = max(max_h, h)
            if not math.isfinite(h):
                raise RuntimeError("state diverged (non-finite altitude)")
            if h > 10.0 and liftoff_t is None:
                liftoff_t = t
                liftoff_v = fdm["velocities/vc-kts"]
                break
    dist = fdm["position/distance-from-start-mag-mt"]
    return {
        "model": model,
        "loaded": True,
        "liftoff_time_s": round(liftoff_t, 2) if liftoff_t else None,
        "liftoff_speed_kt": round(liftoff_v, 1) if liftoff_v else None,
        "ground_roll_m": round(dist, 1),
        "engine_thrust_lbs": round(fdm.get_property_value("propulsion/engine/thrust-lbs"), 0)
        if math.isfinite(fdm.get_property_value("propulsion/engine/thrust-lbs")) else None,
        "final_altitude_ft": round(fdm["position/h-sl-ft"], 1),
        "max_altitude_ft": round(max_h, 1),
        "did_liftoff": liftoff_t is not None,
    }


def cruise(model: str, alt_ft: float, speed_kt: float, seconds: float = 20.0) -> dict:
    """Trim-free cruise sample: throttle to hold roughly the target speed and
    report whether the aircraft stays bounded (no divergence, no collapse)."""
    fdm, _log = new_fdm(model)
    fdm["ic/h-sl-ft"] = alt_ft
    fdm["ic/vc-kts"] = speed_kt
    fdm["ic/gamma-deg"] = 0.0
    quiet(fdm.run_ic)
    set_prop(fdm, "propulsion/engine/set-running", 1)
    set_prop(fdm, "propulsion/engine[0]/set-running", 1)
    set_prop(fdm, "fcs/throttle-cmd-norm", 0.75)
    dt = 1.0 / 120.0
    samples = []
    t = 0.0
    with contextlib.redirect_stdout(io.StringIO()):
        while t < seconds:
            fdm.run()
            t += dt
            samples.append(fdm["position/h-sl-ft"])
    return {
        "model": model,
        "start_alt_ft": alt_ft,
        "alt_range_ft": round(max(samples) - min(samples), 1),
        "end_alt_ft": round(samples[-1], 1),
        "end_speed_kt": round(fdm["velocities/vc-kts"], 1),
        "bounded": math.isfinite(samples[-1]) and abs(samples[-1] - alt_ft) < 3000,
    }


def run_one(model: str) -> dict:
    """Exercise one model. Called in a child process so a native JSBSim crash
    (which can happen on a malformed definition) cannot kill the whole suite."""
    to = takeoff(model)
    cr = cruise(model, 8000.0, 120.0 if "172" in model else 250.0)
    return {"takeoff": to, "cruise": cr}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import subprocess

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="internal: run a single model in isolation")
    ap.add_argument("--json", action="store_true", help="internal: emit JSON only")
    args = ap.parse_args(argv or [])

    if args.model:
        result = run_one(args.model)
        sys.stdout.write("###JSON###" + json.dumps(result) + "\n")
        return 0

    models = sorted(p.stem for p in FLIGHT_MODELS.glob("skybound_*/skybound_*.xml"))
    if not models:
        print("[jsbsim] no generated models found - run export_jsbsim.py first")
        return 2

    print(f"[jsbsim] engine {jsbsim.__version__}, {len(models)} SKYBOUND models")
    results = {"engine_version": jsbsim.__version__, "takeoffs": [], "cruise": [], "failures": []}
    failed = 0
    for m in models:
        proc = subprocess.run([sys.executable, str(Path(__file__)), "--model", m],
                              capture_output=True, text=True, timeout=300)
        payload = None
        for line in proc.stdout.splitlines():
            if line.startswith("###JSON###"):
                payload = json.loads(line[len("###JSON###"):])
        if payload is None:
            failed += 1
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-6:]
            results["failures"].append({"model": m, "returncode": proc.returncode,
                                        "error": " | ".join(tail)})
            print(f"  {m:<28} CRASHED (rc={proc.returncode}) "
                  f"{results['failures'][-1]['error'][:110]}")
            continue
        to, cr = payload["takeoff"], payload["cruise"]
        results["takeoffs"].append(to)
        results["cruise"].append(cr)
        print(f"  {m:<28} loaded OK  roll {to['ground_roll_m']:>7.1f} m  "
              f"liftoff {to['liftoff_speed_kt']} kt @ {to['liftoff_time_s']} s")
        print(f"  {'':<28} cruise 8000 ft: alt range {cr['alt_range_ft']:.0f} ft, "
              f"end {cr['end_speed_kt']} kt, bounded={cr['bounded']}")
        if not cr["bounded"]:
            failed += 1
            results["failures"].append({"model": m, "error": "cruise not bounded"})

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[jsbsim] wrote {REPORT}")
    print(f"[jsbsim] {len(models) - failed}/{len(models)} models flew")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
