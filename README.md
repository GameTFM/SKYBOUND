# SKYBOUND

A native Windows flight simulator built on Unreal Engine 5, Cesium for Unreal and
JSBSim, targeting global-scale geography with validated flight dynamics.

> **Status: foundation phase. This repository is not yet a playable simulator.**
> Read [Current status](#current-status) before drawing conclusions from the
> architecture. Every claim below is either measured by a script in `Tests/` or
> explicitly marked as not yet done.

---

## What exists today (verified)

| Component | State | Evidence |
|---|---|---|
| Aircraft catalog ingestion | **Working** | 714 aircraft imported from the MSFS Addons reference list; every category total matches the publisher's own count (`Content/Data/AircraftCatalog/import_report.md`) |
| Livery-source research | **Working** | 6 GeoFS repositories inspected via the GitHub API; licences recorded, 1 repo confirmed missing (HTTP 404) (`livery_sources.json`) |
| Airport database | **Working** | **86,377 airports** worldwide with real identifiers, positions, elevations and 40,746 runway sets (46,902 runways) from public-domain OurAirports data (`Content/Data/Airports/`) |
| Airport loader (Unreal) | **Written, not compiled** | `USkyboundAirportSubsystem` parses the index on a worker thread at startup; `USkyboundAirportSearchWidget` provides search and runway lookup |
| Airport scenery | **Not started** | No airport buildings modelled; 59 major hubs scheduled for hand-modelling (`Documentation/AIRPORTS.md`) |
| Flight-model validation | **Working** | 23/23 gates pass against published C172S / A320-200 data (`Build/reports/flight_model_validation.json`) |
| JSBSim aircraft definitions | **Generated, partially verified** | Both load in JSBSim 1.3.3 and report weight-on-wheels at t=0; **they still diverge under integration** — open defect DL-004 |
| UE5 project scaffold | **Written, not compiled** | No Unreal Engine or C++ toolchain on this machine (see `BUILD_GUIDE.md`) |
| Windows installer | **Script written** | `Build/Installer/SKYBOUND.iss`; requires a packaged UE build |
| Playable build | **Not yet** | Blocked on UE 5.6 + Visual Studio 2022 |

## Current status

The honest one-line summary: **the data pipelines and the flight model are real
and tested; the simulator itself is not built, because this machine has no
Unreal Engine, no C++ compiler, and an integrated GPU (Intel Iris Xe, 2 GB
shared) that could not render a Lumen/Nanite target anyway.**

What that means concretely:

* `Tools/` and `Tests/` run today and produce the numbers quoted above.
* `Source/`, `Plugins/` and `Config/` are real UE 5.6 project files, written to
  compile — but they have **never been compiled**, so treat compile errors as
  expected first-run work.
* No aircraft model, livery texture, cockpit, terrain asset or sound ships here.
  None has been fabricated to make the project look further along than it is.

## Quick start (works right now)

```bash
python Tools/AircraftCatalogImporter/import_catalog.py      # refresh the catalog
python Tools/LiveryCatalogInspector/inspect_github_sources.py
python Tools/FlightDynamics/validate.py                     # flight-model gates
python Tools/FlightDynamics/export_jsbsim.py                # emit aircraft XML
pip install jsbsim                                          # required for the next line
python Tests/test_jsbsim_models.py                          # engine integration
```

To build the simulator itself you need Unreal Engine 5.6 and Visual Studio 2022 —
see `Documentation/BUILD_GUIDE.md`.

## Documentation

| File | Contents |
|---|---|
| `Documentation/ARCHITECTURE.md` | Module layout, data flow, licensing boundary |
| `Documentation/FLIGHT_PHYSICS.md` | FDM design, validation method, measured results |
| `Documentation/AIRCRAFT_IMPORT_GUIDE.md` | Adding an aircraft to the catalog |
| `Documentation/LIVERY_IMPORT_GUIDE.md` | Livery pipeline and rights handling |
| `Documentation/AIRPORTS.md` | Airport coverage, scenery tiers, building pipeline |
| `Documentation/WORLD_STREAMING.md` | Cesium streaming design and budgets |
| `Documentation/GRAPHICS_SETTINGS.md` | Quality presets and what each option does |
| `Documentation/INSTALLATION.md` | Installer behaviour, repair, uninstall |
| `Documentation/BUILD_GUIDE.md` | Toolchain, build and packaging steps |
| `Documentation/TROUBLESHOOTING.md` | Known failures and fixes |
| `Documentation/LICENSES_AND_ATTRIBUTION.md` | Every third-party component and its terms |
| `Documentation/DEVELOPMENT_ROADMAP.md` | Phases, exit criteria, catalog status |
| `Documentation/DEVELOPMENT_LOG.md` | What is done, broken and next |

## Third-party components

Unreal Engine 5.6 (Epic EULA) · Cesium for Unreal v2.31 (Apache-2.0) ·
JSBSim 1.3.x (**LGPL-2.1, dynamically linked**) · MSFS Addons catalog (reference
only, no asset rights) · GeoFS livery repositories (code MIT where stated,
artwork not licensed).

Full details and the reasoning behind the LGPL dynamic-linking boundary are in
`Documentation/LICENSES_AND_ATTRIBUTION.md`.
