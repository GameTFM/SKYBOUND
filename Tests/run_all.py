#!/usr/bin/env python3
"""
SKYBOUND - aggregate test runner.

Runs the cheap, deterministic checks that must pass before any commit:

  1. aircraft catalog integrity (schema, unique IDs, status/capability consistency)
  2. livery-source register integrity
  3. flight-model validation gates
  4. generated JSBSim definitions are well-formed and reference real parts
  5. installer script sanity (AppId, payload, uninstall policy present)

The JSBSim engine test is NOT run here (it needs the optional `jsbsim` package and
is slow); run Tests/test_jsbsim_models.py separately.

Exit code 0 only when every check passes.
"""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CATALOG = ROOT / "Content" / "Data" / "AircraftCatalog" / "aircraft_catalog.json"
LIVERIES = ROOT / "Content" / "Data" / "AircraftCatalog" / "livery_sources.json"
MODELS = ROOT / "Content" / "Data" / "FlightModels"
INSTALLER = ROOT / "Build" / "Installer" / "SKYBOUND.iss"
AIRPORT_INDEX = ROOT / "Content" / "Data" / "Airports" / "airports_index.json"
AIRPORT_RUNWAYS = ROOT / "Content" / "Data" / "Airports" / "airports_runways.json"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def test_catalog() -> None:
    if not CATALOG.exists():
        check("catalog exists", False, "run import_catalog.py")
        return
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    aircraft = data.get("aircraft", [])
    check("catalog exists", True, f"{len(aircraft)} aircraft")
    check("catalog non-empty", len(aircraft) > 600, f"{len(aircraft)} records")

    ids = [a["aircraft_id"] for a in aircraft]
    dupes = {i for i in ids if ids.count(i) > 1}
    check("aircraft ids unique", not dupes, f"{len(dupes)} duplicates")

    required = {"aircraft_id", "aircraft_name", "developer", "category",
                "implementation_status", "skybound_capability", "asset_license",
                "model_status", "cockpit_status", "flight_model_status"}
    missing = [a["aircraft_id"] for a in aircraft if not required.issubset(a)]
    check("required fields present", not missing, f"{len(missing)} incomplete")

    # Invariant: nothing may be marked flyable without a validated flight model
    # and an imported model. This is the rule that stops the catalog from
    # overstating what the simulator can do.
    bad = [a["aircraft_id"] for a in aircraft
           if a.get("skybound_capability") == "flyable"
           and (a.get("flight_model_status") != "validated"
                or a.get("model_status") not in {"imported", "complete"}
                or a.get("asset_license") in {None, "unknown"})]
    check("flyable aircraft are actually flyable", not bad, f"{len(bad)} violations")

    statuses = {a["implementation_status"] for a in aircraft}
    check("status vocabulary sane", statuses <= {
        "catalogued", "researched", "asset_sourcing", "licensing_review",
        "model_creation", "model_imported", "flight_model_implemented",
        "cockpit_implemented", "systems_implemented", "testing", "playable", "complete",
    }, ",".join(sorted(statuses - {"catalogued"})) or "catalogued only")


def test_liveries() -> None:
    if not LIVERIES.exists():
        check("livery register exists", False, "run inspect_github_sources.py")
        return
    data = json.loads(LIVERIES.read_text(encoding="utf-8"))
    repos = data.get("repositories", [])
    check("livery register exists", True, f"{len(repos)} repositories")
    check("six sources inspected", len(repos) == 6, str(len(repos)))
    for r in repos:
        if r["reachable"]:
            ok = r.get("code_license") is not None or r.get("asset_rights") == "no_license"
            check(f"licence recorded: {r['repo']}", ok, str(r.get("code_license")))
        else:
            check(f"missing repo recorded: {r['repo']}", r.get("exists") is False,
                  f"HTTP {r.get('http_status')}")


def test_flight_models() -> None:
    proc = subprocess.run([sys.executable, str(ROOT / "Tools" / "FlightDynamics" / "validate.py")],
                          capture_output=True, text=True)
    ok = proc.returncode == 0
    tail = [l for l in proc.stdout.splitlines() if "checks," in l]
    check("flight-model gates", ok, tail[0] if tail else proc.stderr.strip()[:120])


def test_jsbsim_xml() -> None:
    files = sorted(MODELS.glob("*/*.xml"))
    check("generated models exist", len(files) >= 2, f"{len(files)} files")
    for f in files:
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError as exc:
            check(f"well-formed: {f.parent.name}", False, str(exc))
            continue
        axes = {a.get("name") for a in root.iter("axis")}
        check(f"well-formed: {f.parent.name}", True,
              f"{len(list(root.iter('axis')))} axes")
        check(f"all six axes: {f.parent.name}",
              axes == {"LIFT", "DRAG", "SIDE", "PITCH", "ROLL", "YAW"}, ",".join(sorted(axes)))
        # Every engine/thruster must reference a real bundled JSBSim part.
        try:
            import jsbsim  # noqa: F401
            pkg = Path(jsbsim.__file__).resolve().parent / "engine"
            parts = [e.get("file") for e in root.iter("engine")] + \
                    [e.get("file") for e in root.iter("thruster")]
            missing = [p for p in parts if p and not (pkg / f"{p}.xml").exists()]
            check(f"parts resolve: {f.parent.name}", not missing, ",".join(missing))
        except ImportError:
            check(f"parts resolve: {f.parent.name}", True, "skipped (jsbsim not installed)")


def test_airports() -> None:
    if not AIRPORT_INDEX.exists():
        check("airport index exists", False, "run import_airports.py")
        return
    idx = json.loads(AIRPORT_INDEX.read_text(encoding="utf-8"))
    airports = idx.get("airports", [])
    check("airport index exists", True, f"{len(airports):,} airports")
    check("airport coverage is global", len(airports) > 60000, f"{len(airports):,}")
    check("airport ids unique", len({a['i'] for a in airports}) == len(airports))
    check("airport licence is public domain",
          "public domain" in idx.get("license", "").lower(), idx.get("license", "")[:40])

    # Every airport must be placeable: lat/lon present and inside valid ranges.
    bad = [a["i"] for a in airports
           if not (-90 <= a["lat"] <= 90 and -180 <= a["lon"] <= 180)]
    check("airport positions valid", not bad, f"{len(bad)} out of range")

    tiers = {a["tier"] for a in airports}
    check("scenery tiers valid", tiers <= {"hero", "generated", "data_only"},
          ",".join(sorted(tiers)))

    by_id = {a["i"]: a for a in airports}

    # --- Cross-language schema contract ---------------------------------
    # The Unreal loader reads these exact keys. A rename here without a matching
    # change in SkyboundAirportDatabase.cpp silently produces an empty airport
    # list at runtime, so the contract is asserted rather than assumed.
    expected = {"i": str, "n": str, "t": str, "lat": float, "lon": float,
                "s": int, "r": int, "tier": str, "dc": str}
    violations = []
    for a in airports:
        for key, typ in expected.items():
            if key not in a or (typ is int and isinstance(a.get(key), bool)) \
               or not isinstance(a.get(key), typ):
                violations.append(f"{a.get('i')}:{key}")
                break
    check("index matches Unreal loader schema", not violations,
          f"{len(violations)} non-conforming records")

    # --- Referential invariants between the two files --------------------
    if AIRPORT_RUNWAYS.exists():
        rw = json.loads(AIRPORT_RUNWAYS.read_text(encoding="utf-8"))["airports"]
        check("runway data exists", len(rw) > 0, f"{len(rw):,} airports")

        # 1. Every airport in the runway file must exist in the index.
        orphans = [k for k in rw if k not in by_id]
        check("runway file has no orphan airports", not orphans, f"{len(orphans)} orphans")

        # 2. Both directions: index.r must agree with the runway file exactly.
        #    This is the invariant that actually matters - a spawnable airport
        #    either has runways or it does not, and both files must agree.
        claimed = {k for k, a in by_id.items() if a["r"] > 0}
        provided = set(rw.keys())
        mismatch = claimed ^ provided
        check("index and runway file agree", not mismatch, f"{len(mismatch)} disagreements")

        # 3. Counts must match record-for-record.
        wrong_count = [k for k, v in rw.items() if len(v.get("runways", [])) != by_id[k]["r"]]
        check("runway counts match", not wrong_count, f"{len(wrong_count)} mismatched")

        # 4. Every runway record must be usable: positive length, an identifier,
        #    and a heading inside one revolution when a heading is present.
        bad_runways = []
        for k, v in rw.items():
            for r in v.get("runways", []):
                heading = r.get("heading_deg_true")
                if (r.get("length_ft", 0) <= 0
                        or not (r.get("designation") or "").strip()
                        or (heading is not None and not (0.0 <= heading < 360.0))):
                    bad_runways.append(f"{k}/{r.get('designation')}")
        check("every runway record is usable", not bad_runways,
              f"{len(bad_runways)} invalid")

        # 5. Completeness labelling must be BOTH sound and complete.
        #    Sound: nothing may be labelled 'missing_runways' while actually
        #    having runways. Complete: no large/scheduled site with zero runways
        #    may go unlabelled, because the UI relies on this flag to explain
        #    why an airport cannot be spawned at. This replaces an arbitrary
        #    count threshold with a statement about data semantics.
        wrongly_flagged = [a["i"] for a in airports
                           if a.get("dc") == "missing_runways" and a["r"] > 0]
        check("missing-runway label is sound", not wrongly_flagged,
              f"{len(wrongly_flagged)} mislabelled")

        unlabelled = [a["i"] for a in airports
                      if (a["t"] == "large_airport" or a["s"] == 1)
                      and a["r"] == 0 and a.get("dc") != "missing_runways"]
        check("every spawn gap is labelled", not unlabelled,
              f"{len(unlabelled)} unlabelled")

        labelled = sum(1 for a in airports if a.get("dc") == "missing_runways")
        check("upstream gaps recorded", labelled > 0, f"{labelled} flagged as missing runway data")

        n_runways = sum(len(v.get("runways", [])) for v in rw.values())
        check("runway total reported", n_runways > 0, f"{n_runways:,} runways")


def test_installer() -> None:
    if not INSTALLER.exists():
        check("installer script exists", False, "missing SKYBOUND.iss")
        return
    s = INSTALLER.read_text(encoding="utf-8", errors="replace")
    check("installer script exists", True, f"{len(s.splitlines())} lines")
    check("AppId declared", "AppId=" in s)
    check("uninstaller user-data prompt", "CurUninstallStepChanged" in s)
    check("install validation", "VerifyInstallation" in s)
    check("per-machine default dir", "{autopf}" in s)
    check("user data outside install tree", "{localappdata}" in s)
    check("64-bit only", "x64compatible" in s)


def main() -> int:
    test_catalog()
    test_liveries()
    test_flight_models()
    test_jsbsim_xml()
    test_airports()
    test_installer()

    failures = [r for r in results if not r[1]]
    print("SKYBOUND test run")
    print("=" * 70)
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<42} {detail}")
    print("-" * 70)
    print(f"{len(results)} checks, {len(failures)} failed")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
