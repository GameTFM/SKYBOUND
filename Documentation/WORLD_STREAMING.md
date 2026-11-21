# SKYBOUND — World Streaming

## Model

Cesium for Unreal streams 3D Tiles around the camera: terrain (quantized-mesh),
imagery, and — where licensed and available — photogrammetry and OSM buildings.
SKYBOUND does not attempt to load the Earth into memory (spec 4.4). It maintains a
working set around the aircraft and lets distant tiles evict.

## Requirements and how they are met

| Requirement | Approach |
|---|---|
| Load scenery around the aircraft | Cesium tileset with the georeference origin following the aircraft |
| Prioritise direction of travel | Bias tileset load priority toward the velocity vector at cruise |
| Multiple LODs | Provided by the 3D Tiles hierarchy |
| Memory ceiling | `r.Streaming.PoolSize` + Cesium's per-tileset cache budget |
| Avoid pop-in | Preload ahead of the aircraft at high speed; raise screen-space error when fast |
| Handle network loss | Degrade to last-good tiles; surface a visible "world data offline" state |
| Cache recently visited scenery | Cesium's disk cache, capped and evictable |

## Geographic origin

The `ACesiumGeoreference` origin moves with the aircraft. Two consequences that
must be handled explicitly:

1. **No drift.** Actor positions must be recomputed from geodetic coordinates
   through the georeference each time the origin shifts — never accumulated.
2. **FDM independence.** The flight model only ever sees lat/lon/altitude, so an
   origin shift cannot perturb physics.

## Budgets (proposed, not yet measured)

| Item | Target |
|---|---|
| Terrain tile cache | 2 GB |
| Imagery cache | 1 GB |
| 3D Tiles (buildings) | 2 GB |
| Streaming pool | 6000 MB (Ultra) |
| Disk cache | 20 GB, LRU-evicted |

These are design targets. **No measurement exists** because the build has not run
on target hardware. Treat them as starting values for the first profiling pass,
not as results.

## Data sources and licensing

* Cesium World Terrain + Bing imagery via Cesium ion — requires the user's own
  token; never committed.
* Google Photorealistic 3D Tiles — only where the terms permit SKYBOUND's use;
  do not assume blanket availability.
* Where photogrammetry does not exist, fall back to terrain + imagery + plausible
  procedural detail. Never present a procedural city as real (spec 4.3, 26.7).

Attribution required by data providers must remain visible in-sim.

## Quality tiers

Low/Medium presets reduce maximum screen-space error and the cache budget, and
disable 3D Tiles above a distance threshold. The aircraft's own geometry always
stays at full detail — the thing you are looking at from the cockpit must not
degrade.
