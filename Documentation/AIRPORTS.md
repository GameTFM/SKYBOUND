# SKYBOUND — Airports

## The goal, and what is actually possible

The ask is "every airport from MSFS, in HD/4K, looking exactly like the
reference screenshots". Three parts of that need to be separated, because two of
them are impossible and one is now done.

| Ask | Verdict |
|---|---|
| Every airport exists | **Done** — 86,377 airports worldwide, with real identifiers, positions, elevations and runway geometry |
| Hand-modelled 4K buildings at every airport | **Not achievable** — and not what MSFS does either |
| Look exactly like the screenshots | **Requires hand-crafted assets + high-end GPU**; can be approached, not guaranteed |

### Why MSFS airport assets cannot be copied

MSFS airports are proprietary: Asobo/Microsoft first-party content and paid
third-party add-ons. Extracting their models, textures, photogrammetry or
layouts into another simulator is a licence violation, and it is explicitly
forbidden by this project's own rules (spec 26.8, 32.5). The correct path is the
one taken here: build from open data.

### Why "4K at every airport" is not a real target

MSFS itself does **not** hand-model 37,000+ airports. It stores real runway and
taxiway data, streams satellite/photogrammetry for the ground, and generates
generic buildings — with hand-crafted detail for a small set of showcase
airports. SKYBOUND follows the same architecture because it is the only one that
scales. A 4K texture per building across 86,377 sites would be petabytes.

What "HD" legitimately means here: **4K textures for the assets you actually
model** (hero airports, aircraft, cockpits) and real-world data plus generated
geometry everywhere else. That is a fidelity budget, not a global checkbox.

## What is imported (verified)

`python Tools/AirportCatalogImporter/import_airports.py` — OurAirports dataset,
**public domain** (commercial and non-commercial use permitted):

| Metric | Count |
|---|---:|
| Airports / sites | 86,377 |
| With usable runway data | 40,746 |
| Individual runways accepted | 46,902 |
| Upstream sites with no runway data (flagged) | 322 |
| With ICAO code | 10,742 |
| With IATA code | 9,053 |
| With scheduled airline service | 4,336 |
| Countries / territories | 247 |
| Large airports | 1,174 |
| Medium airports | 4,108 |
| Small airports | 42,800 |
| Heliports | 23,291 |
| Seaplane bases | 1,274 |
| Balloon ports | 62 |
| Closed sites (flagged, not flyable) | 13,668 |

Runway records carry designation, reciprocal, length, width, surface, lighting,
true heading and threshold elevation — enough to place an aircraft, compute
takeoff distance and draw a correct runway.

Output files:

* `Content/Data/Airports/airports_index.json` — compact search index (id, name,
  type, ICAO/IATA, position, elevation, country, runway count, scenery tier)
* `Content/Data/Airports/airports_runways.json` — runway detail for the 40,954
  airports that have one

## Scenery tiers

| Tier | Count | Meaning |
|---|---:|---|
| `hero` | 59 | Scheduled for hand-modelled terminal, jetbridges, signage, 4K materials. **Not built yet.** |
| `generated` | 40,687 | Real runways + procedural buildings from OSM footprints (ODbL). **Not built yet.** |
| `data_only` | 45,631 | Correct position and identifiers; no 3D structures yet |

## Data-quality rules (asserted, not assumed)

A runway row is accepted only if it has an **identifier**, a **positive length**
and a **heading inside one revolution**. This is a rule about what a runway is,
not a size threshold picked to make a test pass. Measured rejects:

| Reject reason | Rows |
|---|---:|
| No runway designation (40–98 ft stubs, not real runways) | 235 |
| Non-positive length | 227 |
| Heading of exactly 360°, normalised to 0° | 27 (fixed, not rejected) |

**Completeness labelling.** A site that airlines serve, or that OurAirports calls
a large airport, but which has no usable runway row, is an **upstream gap**. It is
labelled `missing_runways` (322 sites) rather than being silently presented as a
normal airport. The UI uses that flag to explain why the site cannot be spawned
at, and `SelectResult()` refuses the selection instead of failing later.

The test suite asserts both directions of that label: nothing with runways may be
flagged, and no large/scheduled site with zero runways may go unlabelled. An
earlier version of this test used a fixed count threshold, which passed while
252 malformed runway rows and 319 spawn gaps sat in the data unnoticed.

The hero list is chosen by real-world traffic significance (major hubs and
capitals), not by screenshot appeal. `scenery_status` is `not_started` for every
airport — the database is real, the scenery is not.

## Building generation path (planned)

1. **Runways/taxiways** — from the imported geometry, extruded as PBR asphalt
   with markings driven by designation, width and lighting.
2. **Buildings** — OpenStreetMap footprints (ODbL: attribution and share-alike on
   the derived database), extruded with height tags; licensed, and legal to ship
   with attribution.
3. **Ground** — satellite imagery via Cesium ion (user's token) or OSM landuse.
4. **Clutter** — windsocks, signs, apron vehicles placed by rules.

This is how the reference screenshots become reachable *without* copying
anything: real layout + real buildings + good materials + good lighting.

## Attribution obligations

* OurAirports: public domain; attribution appreciated.
* OpenStreetMap (when used): "© OpenStreetMap contributors", ODbL — must be
  visible in-sim and in `LICENSES_AND_ATTRIBUTION.md`.
* Cesium ion imagery: provider attribution must remain visible.

## What to check before claiming an airport "looks like" the screenshots

The reference images are judged on: golden-hour directional light, wet apron
reflections, aircraft material response, shallow depth of field, volumetric
cloud structure, and cockpit display legibility at night. Those are rendering and
asset-quality problems, not database problems — and none can be validated on this
machine's integrated GPU. See `GRAPHICS_SETTINGS.md`.
