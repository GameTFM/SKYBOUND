# SKYBOUND — Aircraft Import Guide

## The two-track rule

Everything in the reference catalog is **catalogued**. Almost nothing is
**flyable**. These are different states and the UI must never blur them
(spec 32.9).

Adding a flyable aircraft requires four things, in order:

1. **Legal basis** for the assets (spec 32.5, paths A–D)
2. **A model** that meets the modelling standard
3. **A validated flight model**
4. **A tested cockpit**

Skipping a step does not produce an aircraft; it produces a placeholder, which
spec 26.4 explicitly forbids shipping as complete.

## Step 1 — legal basis

Choose one and record it in the catalog record:

| Path | Meaning | Required fields |
|---|---|---|
| A | Licensed integration from the developer | written permission reference |
| B | Original model built in Blender from reference material | author, date |
| C | Openly licensed asset | licence name + URL + attribution text |
| D | Developer partnership | agreement reference |

`asset_license: "unknown"` blocks promotion to `playable`. This is enforced by
`Tests/run_all.py`.

## Step 2 — the model

Required: correct proportions, wing geometry, fuselage, engines, gear, control
surfaces (separated, named), windows, doors where applicable, PBR materials,
UVs, and LODs. Export FBX or glTF; import to `/Game/Aircraft/<id>/`.

Reject criteria: silhouette wrong, flat/plastic materials, missing gear, control
surfaces fused into the wing, no LODs.

## Step 3 — the flight model

Add an entry to `Tools/FlightDynamics/aircraft_specs.py`:

```python
MY_AIRCRAFT = AircraftSpec(
    aircraft_id="maker-model",
    name="Maker Model",
    mtow_kg=..., empty_kg=..., wing_area_m2=..., span_m=..., mean_chord_m=...,
    cd0=..., oswald_e=..., cl_max_clean=..., cl_max_takeoff=..., cl_max_landing=...,
    engine_type="piston_prop", engine_count=1,
    power_kw=..., prop_efficiency=..., static_thrust_n=...,
    published_v_stall_kt=..., published_v_stall_config="clean",
    published_climb_speed_kt=..., published_takeoff_roll_m=...,
    published_roc_fpm=..., published_cruise_ktas=..., published_cruise_alt_ft=...,
    sources=["POH page/tables used"],
    assumptions=["anything estimated and why"],
)
```

Then:

```bash
python Tools/FlightDynamics/validate.py      # must pass every gate
python Tools/FlightDynamics/export_jsbsim.py # regenerates the JSBSim XML
```

**Do not invent specifications.** If a figure is unknown: leave the anchor at 0
(its check is skipped), estimate the modelling parameter, and record it in
`assumptions`. Never copy another aircraft's values across a materially different
design (spec 32.7).

## Step 4 — the catalog record

Update `aircraft_catalog.json` for the aircraft, keeping source-owned fields
intact:

```json
{
  "implementation_status": "testing",
  "skybound_capability": "flyable",
  "flight_model_status": "validated",
  "model_status": "imported",
  "cockpit_status": "not_started",
  "asset_license": "original",
  "skybound_version": "0.1.0"
}
```

`skybound_capability: "flyable"` is only permitted when the flight model passed
`validate.py` **and** the model is imported. The test suite enforces this.

## Step 5 — cockpit

A cockpit is only "implemented" when every visible control does something or is
explicitly marked inoperative (spec 8, 26.5). A static mesh with painted gauges
is not a cockpit.

## Refresh discipline

`import_catalog.py` never overwrites SKYBOUND-owned implementation fields with
source data; it only updates name/developer/URL/release status and reports the
diff. Review `import_report.md` after each refresh.
