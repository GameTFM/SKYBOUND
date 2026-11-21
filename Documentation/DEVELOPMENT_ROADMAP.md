# SKYBOUND — Development Roadmap

Status keys: **[done]** verified by a run · **[written]** code exists, not compiled
· **[open]** not started · **[blocked]** needs hardware/credentials.

## Phase 0 — environment and dependency verification

| Task | Status | Evidence |
|---|---|---|
| Inspect environment | **[done]** | No UE, no VS, no C++ compiler, Iris Xe iGPU |
| Verify Cesium/UE compatibility | **[done]** | Cesium v2.31 supports UE 5.6/5.7/5.8 → UE 5.6 chosen |
| Verify JSBSim licensing approach | **[done]** | LGPL-2.1 + UE EULA ⇒ dynamic DLL boundary |
| Inspect all six GeoFS repositories | **[done]** | 5 reachable, 1 missing (404), licences recorded |
| Ingest the full MSFS Addons catalog | **[done]** | 714 aircraft, counts match publisher |

## Phase 1 — foundation

| Task | Status |
|---|---|
| UE 5.6 project + modules + config | **[written]** |
| Cesium integration | **[written]** (plugin enabled; level actors not authored) |
| Geographic coordinate handling | **[written]** |
| Fixed-step FDM subsystem | **[written]** |
| JSBSim dynamic DLL boundary | **[written]** |
| Compile and launch a Windows build | **[blocked]** — needs UE 5.6 + VS 2022 |

**Exit criterion:** launch the Windows build and fly over a real location. Not met.

## Phase 2 — flight simulation

| Task | Status |
|---|---|
| Performance model + validation gates | **[done]** 23/23 |
| C172S / A320-200 data definitions | **[done]** |
| JSBSim XML generation | **[done]** |
| JSBSim definitions fly stably | **[open]** defect DL-004 |
| Ground handling, gear, brakes | **[open]** |
| Instruments fed from FDM state | **[open]** |

## Phase 3 — visual world

Terrain/imagery streaming configuration, atmospheric lighting, volumetric clouds,
water, day/night: **[open]**. All of it depends on a running build.

## Phase 4 — aircraft ecosystem

Catalog ingestion **[done]**; livery register **[done]**; model pipeline, livery
pipeline, aircraft browser: **[open]**.

## Phase 5 — airports and navigation

Airport database, runways, navdata, flight planning: **[open]**. Requires a
licensed navdata source (see below).

## Phase 6 — weather and audio

Weather presets affecting the FDM: **[open]**. Audio: **[open]**.

## Phase 7 — cockpits and avionics

**[open]**. No aircraft has a functional cockpit. None will be described as
having one until every control does something.

## Phase 8 — final application

Installer script **[written]**; save system, settings UI, content manager, update
system, repair: **[open]**.

## Catalog coverage

714 aircraft catalogued. **0 playable.** That ratio is the honest headline of the
project. Promotion path per aircraft is defined in
`AIRCRAFT_IMPORT_GUIDE.md`; nothing reaches `playable` without a legal basis, a
real model, a validated flight model and a tested cockpit.

## Dependencies that need a decision or a credential

| Need | Blocking what | Notes |
|---|---|---|
| Unreal Engine 5.6 + VS 2022 (~140 GB) | everything runtime | no workaround |
| GPU capable of Lumen/Nanite | visual validation | current iGPU cannot |
| Cesium ion token (user's own) | world streaming | never committed |
| Navdata licence (e.g. ARINC 424) | airports, approaches | commercial; do not scrape |
| Live weather provider | live weather mode | optional, must be clearly labelled |
| Code-signing certificate | signed installer/updates | needed before public release |
