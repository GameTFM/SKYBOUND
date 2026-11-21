# SKYBOUND — Troubleshooting

Every entry here is a failure that actually occurred during development, with the
fix that worked. Speculative entries are omitted.

## Tooling / Python

### `import_catalog.py` exits 3: "No aircraft category headings found"

The MSFS Addons page changed its markup. The parser matches `<h2>` headings whose
text equals a known category, optionally followed by a live count
(`Airlines 116`). Fix: inspect a saved copy and update `CATEGORY_MAP` in
`Tools/AircraftCatalogImporter/import_catalog.py`.

```bash
python Tools/AircraftCatalogImporter/import_catalog.py --html Build/cache/msfs-aircraft-list.html
```

### Importer reports `INTEGRITY: <category>: parsed N rows but page states M`

The publisher's own count disagrees with what was parsed — usually a layout change
or a duplicated section. Trust the message, not the JSON. Do not "fix" it by
editing the expected number.

### `validate.py` fails a gate

That is the gate working. Investigate the physics, not the tolerance. Tolerances
encode what the model is allowed to get wrong; widening one to make a test pass
is exactly the behaviour the suite exists to prevent.

## JSBSim integration

### `JSBSim failed to open the configuration file: .../site-packages/jsbsim/Content/...`

A relative aircraft path. JSBSim resolves relative paths against its own package
directory. Always pass an absolute path to `set_aircraft_path`.

### `could not open file` / model loads but `engines 0`

The aircraft folder must be `set_aircraft_path/<model_name>/<model_name>.xml`.
A missing or half-written XML (e.g. an interrupted export) causes this. Re-run
`export_jsbsim.py` and verify with `xml.etree.ElementTree.parse`.

### `A proper axis type has NOT been selected`

The `<aerodynamics>` block failed to parse — commonly because the file was
truncated mid-write. Validate well-formedness first.

### Aircraft reports `alt = nan` immediately

In order of likelihood, all of which have been hit here:

1. **Gear contact Z sign.** Gear legs below the reference point take **negative**
   Z in JSBSim's model convention (as in the bundled `c172x`). Positive Z makes
   the aircraft free-fall; `gear/wow` is 0 at startup.
2. **Axis functions returning forces instead of coefficients.** Functions inside
   `<axis>` must return coefficients; JSBSim applies q̄·S itself. Referencing
   `aero/cl-squared` at zero airspeed yields 0/0 = NaN.
3. **Sign of `Cm_alpha`.** Must be negative for static stability. A double
   negative makes the model diverge within seconds.

### `OpenBLAS error: Memory allocation still failed after 10 retries`

Seen when several JSBSim processes started at once. Set
`OPENBLAS_NUM_THREADS=1` and run models sequentially, or isolate each in its own
process (`Tests/test_jsbsim_models.py` does the latter).

## Unreal build

### `CesiumRuntime` module not found

Cesium for Unreal is not installed into the engine version being used. Install the
build matching UE 5.6, then regenerate project files.

### Project will not open / "modules are out of date"

Compile the editor target first (see `BUILD_GUIDE.md`). The project is a C++
project; it cannot be opened before its modules are built.

### Flight dynamics unavailable in-sim

`jsbsim.dll` or `SkbJsbsimShim.dll` is missing from `Binaries\Win64`. This is a
reported state, not a silent failure — build the shim with
`Scripts/build_jsbsim_shim.ps1`.

## Installer

### `Scripts/package.ps1` warns "Staging DOCUMENTATION ONLY"

No `-PackagedBuild` was supplied. The resulting installer is for pipeline testing
and is **not** a playable game. Package the UE build first.

### `Inno Setup 6 not found`

`winget install JRSoftware.InnoSetup` (installs to `Program Files (x86)\Inno Setup 6`).

## Performance

No performance numbers are published for SKYBOUND because none have been measured
on target hardware. Do not quote figures from this repository; measure on the
machine in question and record FPS, frame time, VRAM and streaming behaviour
(spec 24).
