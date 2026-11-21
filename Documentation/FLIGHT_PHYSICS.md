# SKYBOUND — Flight Physics

## What the runtime uses

JSBSim (6-DOF rigid body, LGPL-2.1) integrated at a fixed 120 Hz. JSBSim is not
compiled into the game: it ships as `jsbsim.dll` plus a SKYBOUND-owned C-ABI shim
(`SkbJsbsimShim.dll`) and is loaded at runtime. See
`LICENSES_AND_ATTRIBUTION.md` for why this is mandatory, not a preference.

## What actually validated the numbers

This machine has no C++ toolchain and no Unreal Engine, so a flight model cannot
be "flown and felt" here. Rather than assert quality, the project ships an
independent longitudinal performance model and **gates the aircraft data against
published figures**:

```
Tools/FlightDynamics/fdm.py       ISA atmosphere, drag polar, thrust lapse,
                                  ground roll + airborne segment, ROC, trim
Tools/FlightDynamics/validate.py  23 published-data gates (exit code 1 on failure)
```

### Measured results (last run, reproducible)

| Check | Cessna 172S | Reference | Airbus A320-200 | Reference |
|---|---:|---:|---:|---:|
| 1g stall speed | 48.07 kt | 48 kt (POH) | 120.9 kt | 121 kt (landing cfg) |
| Takeoff ground roll | 252 m | 293 m | — | (field length only) |
| Takeoff to 50 ft | 435 m | 497 m | 1373 m | 2200 m |
| Sea-level climb | 718 fpm | 730 fpm | 2581 fpm | 2500 fpm |
| Cruise L/D | 9.5 | 8–13 band | 16.9 | 14–20 band |
| Trim lift residual | 0 N | < 1e-3 N | 0 N | < 1e-3 N |

`python Tools/FlightDynamics/validate.py --json Build/reports/flight_model_validation.json`

### What these numbers do and do not prove

**Proven:** mass, wing area, CLmax, drag polar and thrust are mutually consistent
and reproduce the published stall, climb and takeoff figures within stated
tolerances. The model is not "vibes-based".

**Not proven:** lateral-directional behaviour, spin, wake turbulence, ground
handling on contaminated runways, or that the *JSBSim* implementation of these
same numbers flies well. Those require the engine and a pilot-in-the-loop.

### Deliberate modelling choices, and why

| Choice | Reason |
|---|---|
| CLmax derived from published Vs | It is how CLmax is derived in practice. Stated openly rather than presented as an independent prediction. |
| Prop thrust = min(static, ηP/V), η = 0.58 | Net installed efficiency, back-solved from the POH climb figure. Using the textbook 0.78 overpredicted climb by 36%. |
| Turbofan lapse `σ^0.7·(1−0.75M)^1.5` | A linear lapse made the A320 climb ~2.7× too fast. |
| ROC compared at the *published* climb speed | Comparing an optimised best-rate speed to a POH climb-schedule figure is not like-for-like. |
| Ground effect applied below one wingspan | Physically correct on the takeoff segment; omitting it doubled the airborne distance. |

Each of those was a **bug found by the suite**, not a preference — the first
version of the model failed 8 of 23 gates.

## Aircraft definitions (JSBSim XML)

`Tools/FlightDynamics/export_jsbsim.py` generates `Content/Data/FlightModels/*`.
Both models are accepted by JSBSim 1.3.3 and report weight-on-wheels at t=0.

**Open defect DL-004:** both models diverge to NaN within a few seconds of
integration under full throttle. Fixed so far: axis functions now return
coefficients (JSBSim applies q̄·S itself), the pitch-stability table sign was
inverted, and the gear contact Z convention was corrected. The remaining cause is
not yet isolated. Until it is fixed, the shipped flight model must **not** be
described as working.

## Stability derivatives: estimated, not measured

`Cm_alpha`, `Cl_beta`, `Cn_beta` and the control-power terms are computed from
tail-volume geometry. They are labelled `ESTIMATED` in every generated file and
in the catalog. Deriving real values needs wind-tunnel or OEM data, which is not
public. This is the single biggest fidelity gap in the current aircraft data.

## Realism settings

Realism level (Beginner → Realistic) will gate: failures, turbulence intensity,
engine damage, icing, and whether the FDM is allowed to exceed limiting loads.
No failure simulation is presented as active unless it is actually running
(spec 18).
