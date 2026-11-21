# SKYBOUND — Architecture

## Design constraints that drive everything

1. **Native Windows application.** Unreal Engine 5.6 packaged build, DX12,
   installed via a real installer. No browser anywhere in the runtime path.
2. **Physics independent of frame rate.** The flight model steps at a fixed rate;
   rendering interpolates. Nothing gameplay-related reads a variable `DeltaTime`.
3. **Data-driven aircraft.** Adding an aircraft is adding data + assets, never
   editing engine code (spec 26.9, 26.11).
4. **One auditable LGPL boundary.** JSBSim is the only LGPL dependency, and it is
   reached through exactly one DLL interface.

## Module layout

```
SKYBOUND.uproject                UE 5.6 project (Cesium, FlightSimulation plugins)
Config/                          DefaultEngine/Game/Input ini
Content/Data/
  AircraftCatalog/               aircraft_catalog.json, livery_sources.json, reports
  FlightModels/                  generated JSBSim aircraft XML (one folder per aircraft)
Source/SKYBOUND/                 game module (no LGPL code)
  Core/                          game mode, save game, settings, log categories
  FlightPhysics/                 fixed-step subsystem + state structs + backend interface
  Aircraft/                      pawn that renders FDM state through Cesium
  Avionics/ Navigation/ Airports/ Weather/ Audio/ Cameras/ Input/ UI/ Data/ Utilities/
    Data/SkyboundAirportDatabase       airport index + runway loader, search
    UI/SkyboundAirportSearchWidget     search screen (C++ logic, UMG visuals)
Plugins/FlightSimulation/        the ONLY module that can touch JSBSim
  Public/SkyboundFdmBackend.h    abstract backend the game talks to
  Private/JSBSimBackend.cpp      loads SkbJsbsimShim.dll at runtime
Tools/                           Python pipelines (run today)
Tests/                           executable checks (run today)
Build/Installer/                 Inno Setup script
Scripts/                         packaging + shim build
Documentation/                   this set
```

## Runtime data flow

```
Input (keyboard/joystick/autopilot)
        │  FSkyboundControlInputs
        ▼
USkyboundFlightModelSubsystem            fixed 120 Hz accumulator
        │  FSKYFdmInputs
        ▼
ISkyboundFdmBackend  ──►  JSBSimBackend  ──►  SkbJsbsimShim.dll  ──►  jsbsim.dll
        │  FSKYFdmState (SI units, WGS84)                              (LGPL-2.1)
        ▼
ASkyboundAircraftPawn  ──►  CesiumGeoreference  ──►  Unreal world transform
        │
        ├──► Avionics (PFD/ND consume the same state)
        ├──► Audio (engine/speed driven)
        └──► Cameras
```

### Why the FDM lives behind an interface

* Gameplay code never includes a JSBSim header, so the LGPL surface cannot leak
  into the rest of the project.
* A deterministic test double can be substituted for tests and CI.
* Swapping FDMs (or adding a second one for comparison) touches one file.

### Why physics is a fixed-step accumulator

`USkyboundFlightModelSubsystem` accumulates real time and runs the FDM in
`1/120 s` steps, capped at 8 steps per frame to avoid a death spiral. Rendered
state is interpolated between the last two physics samples. This keeps handling
identical at 30 fps and 144 fps — a requirement, not a nicety (spec 3.3).

## Geographic positioning

The FDM works in WGS84 geodetic coordinates (latitude, longitude, ellipsoid
height). `ASkyboundAircraftPawn` asks the level's `ACesiumGeoreference` to convert
those into Unreal world space. This means:

* the FDM never sees Unreal's float coordinates, so no origin-shift artefacts,
* the same state numbers are valid anywhere on Earth,
* restarting near a different airport does not require simulator changes.

## Airport data path

```
OurAirports (public domain)
        │  Tools/AirportCatalogImporter/import_airports.py
        ▼
Content/Data/Airports/
  airports_index.json     86,377 sites, compact keys (i,n,t,ic,ia,lat,lon,el,c,m,s,r,tier,dc)
  airports_runways.json   runway geometry for 40,746 airports
        │
        ▼  USkyboundAirportSubsystem (game-instance subsystem)
  Initialize() ──► worker thread parses the 17 MB index ──► game thread adopts
        │                                                   └─ OnDatabaseReady
        ▼
  SearchAirports(filter)  exact ICAO/IATA matches ranked first, then substring
        │                  over one pre-folded key per airport
        ▼
  USkyboundAirportSearchWidget  (C++ logic, UMG visuals)
        │  SelectResult() rejects airports with no runway
        ▼
  spawn request → ACesiumGeoreference + FDM start position
```

**Why the index is parsed off the game thread:** 86,377 records is ~17 MB of JSON.
Blocking the game thread on that at startup would stall the first frame. The
subsystem parses on the thread pool and adopts the result on the game thread; the
search screen shows a loading state until `OnDatabaseReady` fires, and a failure
shows the actual error instead of an empty list.

**Why runway data is lazy:** it is 24 MB and only needed once an airport is
chosen. `GetRunways()` parses it on first call and logs the elapsed time.

**Why the field names are asserted:** the index uses short keys to keep 86k
records manageable. `Tests/run_all.py` asserts that every record matches the
schema `SkyboundAirportDatabase.cpp` reads, so a rename in either language fails
the suite instead of silently producing an empty airport list in-game.

## Data-driven catalog

`aircraft_catalog.json` holds every aircraft the project knows about. It is
generated, not hand-typed, by `Tools/AircraftCatalogImporter`. Each record
carries an `implementation_status` and `skybound_capability`:

* `catalogued` + `catalog_only` → shown in the browser as reference material,
  **not selectable for flight** (spec 32.9),
* `playable` → requires a validated flight model, a licensed/original model and a
  tested cockpit. Nothing has reached `playable` yet.

## Persistence

* Install directory: `C:\Program Files\SKYBOUND` (binaries, content) — read-only
  for the user.
* User data: `%LOCALAPPDATA%\SKYBOUND` — settings, saves, control profiles,
  favourites, downloaded content, logs, cache.
* The installer never deletes user data without an explicit prompt (spec 31.3,
  31.7). Updates never touch it.

## Error handling philosophy

Missing content must degrade visibly, never silently substitute something fake.
If `jsbsim.dll` or the shim is absent, the backend reports
`IsAvailable() == false` with an actionable message and the UI says flight
dynamics are unavailable. It does not fall back to a toy flight model
(spec 26.2, 26.14).
