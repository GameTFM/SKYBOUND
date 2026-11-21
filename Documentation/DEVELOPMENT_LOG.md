# SKYBOUND — Development Log

Chronological record of what is complete, what is broken, what remains, and which
tests passed or failed. Updated at the end of each work session.

---

## Session 1 — environment verification and foundation

### Environment (measured, not assumed)

* Windows 11 build 26200, 32 GB RAM, Intel Core i7-1185G7 (4C/8T).
* GPU: **Intel Iris Xe, 2 GB shared** — an integrated GPU. It cannot validate a
  Lumen/Nanite target.
* 129 GB free disk.
* Python 3.12, Node 26, Git 2.56, `winget` 1.29.
* **Absent:** Unreal Engine, Visual Studio, .NET SDK, CMake, MSVC, any C++ compiler.

### Decisions taken

1. **UE 5.6**, because Cesium for Unreal v2.31 supports only 5.6/5.7/5.8 and 5.6 is
   the oldest supported (maximum plugin compatibility). UE 5.5 is not an option.
2. **JSBSim loaded as a replaceable DLL** behind a C-ABI shim, because LGPL-2.1 and
   the UE EULA together forbid any other arrangement.
3. **Python reference model + published-data gates** as the physics evidence while
   no engine exists. Without this, aircraft data would be unverifiable.

### Completed

* Aircraft catalog importer — **714 aircraft**, every one of the nine category
  counts matches the publisher's own figure (203/53/116/22/149/16/73/55/27).
* Livery-source inspector — 6 repos: 4 MIT (code only), 1 unlicensed,
  1 confirmed non-existent (`Ariakim-Taiyo/LiveryChanger`, HTTP 404).
* Reference FDM: ISA atmosphere, drag polar, propeller/turbofan thrust models,
  ground roll, airborne segment, ROC, trim solver.
* Validation suite: **23 checks, 0 failures**.
* JSBSim exporter: generates aircraft XML from the same specs.
* UE 5.6 project scaffold: uproject, target files, module, flight-state structs,
  fixed-step subsystem, FDM backend interface, dynamic JSBSim loader, plugin,
  engine/game config.
* Inno Setup installer script + packaging script.

### Measured results

```
Cessna 172S: stall 48.07 kt (pub 48), takeoff roll 252 m (pub 293),
             takeoff to 50 ft 435 m (pub 497), climb 718 fpm (pub 730)
A320-200   : stall 120.9 kt (pub 121), takeoff to 50 ft 1373 m (pub 2200),
             climb 2581 fpm (pub 2500), cruise L/D 16.9
```

### Bugs found and fixed by the validation suite (kept as a record)

| # | Bug | Symptom | Fix |
|---|---|---|---|
| B-01 | Ground-effect factor divided instead of multiplied | Induced drag *increased* near the ground | Multiply induced drag by the factor |
| B-02 | Prop thrust used `ηP/V` with a 35 m/s floor | Takeoff roll 160 m vs 293 m published; climb 1218 vs 730 fpm | Momentum-theory static thrust, documented value, net η = 0.58 |
| B-03 | Mach drag-rise term `0.02·Δ²·100` | Cruise L/D crushed to 12.9 | Cubic term above M0.78 only |
| B-04 | A320 "clean stall" anchor was a landing-config figure | Stall gate compared 1.50 CLmax to a 2.6 CLmax number | Per-aircraft `published_v_stall_config` |
| B-05 | ROC compared an optimised best-rate speed to a POH climb schedule | False 2.6× climb failure | Evaluate ROC at the published climb speed |
| B-06 | Airborne takeoff segment ignored ground effect | Airborne distance doubled | Apply ground effect below one wingspan |
| B-07 | JSBSim axis functions multiplied by q̄·S as well as returning a coefficient | Double counting; `aero/cl-squared` = 0/0 → NaN at t=0 | Return coefficients only |
| B-08 | Gear contact Z sign inverted | `gear/wow` = 0 at startup, aircraft free-fell | Negative Z (matches bundled c172x) |
| B-09 | `Cm_alpha` table had a double negative | Model longitudinally unstable | Remove second negation |

### Broken / open

* **DL-004 (open, highest priority).** Both generated JSBSim definitions load and
  report weight-on-wheels at t=0, but diverge to NaN within a few seconds under
  full throttle. Progress: the axis-coefficient, gear-sign and `Cm_alpha` issues
  above are fixed; the remaining cause is not isolated. Until this is closed, the
  JSBSim path must not be called working.
* `Tests/test_jsbsim_models.py` spawns one process per model to survive native
  crashes; under concurrent BLAS thread pools it can hit an OpenBLAS allocation
  error, so it runs with `OPENBLAS_NUM_THREADS=1`.
* No C++ has been compiled. Compile errors are expected on first build.
* No performance measurement exists.
* `SKYBOUND.iss` has not produced a game installer because no packaged UE build exists.

### Dependencies required to continue

UE 5.6 (~100 GB), Visual Studio 2022 with C++ workload (~40 GB), a DX12 GPU with
~12 GB VRAM for fidelity validation, Cesium ion token, and later a navdata licence.

### Installer

Inno Setup 6.7.3 was installed (`winget install JRSoftware.InnoSetup`, per-user
location) and `Build/Installer/SKYBOUND.iss` was compiled for real:

```
Successful compile (1.922 sec).
Build/Output/SKYBOUND-Setup-0.1.0.exe  (2.0 MB)
```

Compilation validates the wizard, file staging, prerequisite check, install
validation and uninstall-data-prompt logic. It does **not** validate a game
payload, because none exists: the script detects the missing `SKYBOUND.exe`,
prints a testing-only warning and shows the user an explicit "built without a
packaged payload" message. Notes from the build:

* `SetupIconFile` was removed — Inno aborts when a referenced icon is missing, and
  no `skybound.ico` exists yet. Re-add both together.
* All installer warnings cleared (unused variables removed, `RunOnceId` added).

### Tests passed

| Runner | Result |
|---|---|
| `Tests/run_all.py` | **29 checks, 0 failed** |
| `Tools/FlightDynamics/validate.py` | **23 checks, 0 failed** |
| `Tools/AircraftCatalogImporter` | 714 aircraft, per-category counts match publisher |
| `Tools/LiveryCatalogInspector` | 6 repositories classified |
| `Tools/FlightDynamics/export_jsbsim.py` | 2 definitions, well-formed, all six axes, parts resolve |
| Inno Setup compile | successful, 2.0 MB installer |

### Tests failed

`Tests/test_jsbsim_models.py` — models do not stay numerically stable (DL-004).
This is the one test in the repository that does not pass, and it is left failing
rather than skipped or loosened.

---

---

## Session 2 — global airport database

### Request

"Every airport from MSFS, HD/4K, looking exactly like the reference screenshots."

### What was possible, and what was not

* MSFS airport assets are proprietary (Asobo/Microsoft + payware). They cannot be
  extracted or redistributed. Ruled out on legal grounds, not technical ones.
* Hand-modelling 4K buildings at every airport is not what MSFS does either: it
  uses real runway data + streamed imagery + generated buildings, with hand-crafted
  detail for a few dozen showcase airports. SKYBOUND adopts the same architecture
  because it is the only one that scales.
* Complete *airport coverage* is achievable legally, so that is what was built.

### Completed

`Tools/AirportCatalogImporter/import_airports.py` ingests the public-domain
OurAirports dataset and emits a compact runtime pair (a 72 MB single-file version
was rejected as unloadable at startup):

| Output | Size | Contents |
|---|---:|---|
| `Content/Data/Airports/airports_index.json` | 15 MB | 86,377 sites: id, name, type, ICAO/IATA, position, elevation, country, runway count, scenery tier |
| `Content/Data/Airports/airports_runways.json` | 23 MB | runway detail for the 40,954 airports that have one |

Measured coverage: **86,377 sites**, 40,954 with runway data, **38,416 runways
>= 500 ft**, 10,742 with ICAO, 9,053 with IATA, 4,336 with scheduled service,
247 countries. Types: 1,174 large, 4,108 medium, 42,800 small, 23,291 heliports,
1,274 seaplane bases, 62 balloon ports, 13,668 closed (flagged).

Runway records carry designation, reciprocal, length, width, surface, lighting,
true heading and threshold elevation — sufficient to spawn an aircraft on a real
runway and compute takeoff performance.

Scenery tiers assigned: 59 `hero` (hand-modelling scheduled), 40,895 `generated`
(real runways + procedural buildings), 45,423 `data_only`. **Every airport's
`scenery_status` is `not_started`** — the database is real; the scenery is not.

### Tests

`Tests/run_all.py` now covers the airport database: coverage count, unique IDs,
public-domain licence, valid coordinates, tier vocabulary, non-empty runway
records, and usable-runway count.
Result: **38 checks, 0 failed**. Flight-model gates unchanged at **23/23**.

### Bugs found and fixed

| # | Bug | Fix |
|---|---|---|
| B-10 | Report generator referenced a renamed variable after the file split (`NameError`) | Use the index payload's timestamp |
| B-11 | Usable-runway test threshold guessed at 40,000; actual is 38,416 | Bound set to a defensible 30,000 and the real figure recorded |
| B-12 | Ad-hoc check read UTF-8 JSON with Windows' cp1252 default | Specify `encoding="utf-8"`; runtime loader must do the same |

### Open

* No airport scenery exists. The building pipeline (OSM footprints, ODbL
  attribution) is designed but not implemented.
* Still blocked on UE 5.6 + VS 2022 for anything runnable; DL-004 remains open.

---

## Session 3 — principled invariants + Unreal airport loader

### Replaced the arbitrary test threshold

Session 2 ended with a usable-runway count gate set to 30,000 because the real
figure (38,416) did not match a guess. That was a magic number, and it passed
while real defects sat in the data. It has been replaced with invariants that
express what the data must *mean*:

| Invariant | Result |
|---|---|
| Index records match the exact keys/types the Unreal loader reads | 0 non-conforming |
| No orphan airports in the runway file | 0 |
| `index.r > 0` and runway-file membership agree exactly, both directions | 0 disagreements |
| Per-airport runway counts match record-for-record | 0 mismatched |
| Every runway has an identifier, positive length, heading in [0,360) | 0 invalid |
| `missing_runways` label is sound (nothing labelled has runways) | 0 mislabelled |
| Label is complete (no large/scheduled site with zero runways is unlabelled) | 0 unlabelled |

### Defects the new invariants exposed (all real, all fixed)

| # | Defect | Resolution |
|---|---|---|
| B-13 | 235 runway rows with no designation (40–98 ft stubs) | Rejected at import with an explicit reason and counted |
| B-14 | 227 runway rows with non-positive length | Rejected at import, counted |
| B-15 | 27 runways with heading 360° (outside [0,360)) | Normalised modulo one revolution |
| B-16 | 319 large/scheduled sites with no runway rows at all | Labelled `missing_runways`, surfaced in the UI, selection refused |

The label is *bidirectionally* asserted, so a future data refresh that introduces
a new gap fails the suite instead of quietly producing an unspawnable airport.

### Unreal-side loader (written, not compiled)

* `Source/SKYBOUND/Data/SkyboundAirportDatabase.{h,cpp}` — `USkyboundAirportSubsystem`:
  * parses `airports_index.json` (17 MB, 86,377 records) on the thread pool at
    game-instance initialisation, then adopts the result on the game thread and
    broadcasts `OnDatabaseReady`; a weak pointer prevents use after teardown,
  * builds one pre-folded search key per airport so a query is a single substring
    test instead of four case-folded comparisons,
  * ranks exact ICAO/IATA/id matches first,
  * parses the 24 MB runway file lazily on first `GetRunways()` and logs the time,
  * reports load errors through `GetLoadError()` instead of returning an empty
    list that looks like "no airports exist".
* `Source/SKYBOUND/UI/SkyboundAirportSearchWidget.{h,cpp}` — abstract UUserWidget:
  query/type/country/scheduled/require-runway filters, result list, runway lookup,
  loading and failure states via Blueprint events, and `SelectResult()` which
  refuses airports without a runway.
* `DefaultGame.ini` — `[SkyboundAirportSubsystem] DataDirectory` override and
  `bPreloadAirportsAtStartup`.

Not done: the UMG widget asset itself (binary `.uasset`, must be authored in the
editor from the C++ base), and compilation — still no UE/VS.

### Tests

`Tests/run_all.py`: **45 checks, 0 failed**.
`Tools/FlightDynamics/validate.py`: **23 checks, 0 failed**.

## Next session



1. Isolate DL-004: step one model with instrumentation on pitch rate, alpha and
   contact forces; bisect by removing gear contacts, then moment axes.
2. Compile the UE project and fix first-build errors.
3. Author the MainMenu/Flight maps and a Cesium georeference level.
4. Measure baseline performance on real hardware; replace the proposed budgets in
   `WORLD_STREAMING.md` with measured numbers.
