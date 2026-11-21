# SKYBOUND — Licenses and Attribution

This file is a legal-facing document. It records what is used, under what terms,
and what SKYBOUND may and may not redistribute.

## Summary

| Component | Version | Licence | Redistributable in SKYBOUND? |
|---|---|---|---|
| Unreal Engine 5 | 5.6 | Epic Games EULA | Yes, as a packaged product, per EULA terms |
| Cesium for Unreal | 2.31 | Apache-2.0 | Yes |
| Cesium ion content | — | Cesium terms + data-provider terms | Only via the user's own ion account/token |
| JSBSim | 1.3.x | **LGPL-2.1** | Yes, **only** as a replaceable dynamic library |
| MSFS Addons aircraft list | — | Site copyright | Metadata only — no assets |
| GeoFS livery repositories | — | MIT (code) / none | Code metadata only — **not** airline artwork |
| Aircraft models, liveries, sounds | — | TBD per asset | **Nothing ships yet** |

## JSBSim (LGPL-2.1) — the binding constraint

Two separate obligations must both be satisfied:

1. **LGPL-2.1** requires that a user be able to replace the library with a
   modified version and re-run the application.
2. **The Unreal Engine EULA** does not permit statically linked LGPL code in a
   packaged UE product.

Therefore JSBSim is:

* **not** compiled into `SKYBOUND.exe` or any UE module,
* built as `jsbsim.dll`,
* reached through a SKYBOUND-owned C-ABI shim (`SkbJsbsimShim.dll`) that is the
  only code including JSBSim headers,
* installed next to the executable and replaceable by the user,
* accompanied by this notice and a link to the JSBSim source.

SKYBOUND's own code is not a derivative work of JSBSim under this arrangement.
If JSBSim is modified, those modifications must be published under LGPL-2.1.

**Action required before release:** ship `jsbsim.dll`'s corresponding source
reference and confirm the exact version string in the About screen.

## Verified findings from the livery-source inspection

Produced by `Tools/LiveryCatalogInspector` against the live GitHub API
(`Content/Data/AircraftCatalog/livery_sources.json`):

| Repository | Code licence | Asset rights |
|---|---|---|
| kolos26/GEOFS-LiverySelector | MIT | Code only — airline artwork is third-party |
| GeofsExplorer/GeoFS-LiverySelector | MIT | Code only |
| RoqueDJ/GEOFS-LiverySelectorUltimate | MIT | Code only |
| iuhairways/GEOFS-LiverySelector-by-kolos26 | MIT | Code only |
| Spice9/Geofs-Multiliveries | none | Nothing may be reused |
| Ariakim-Taiyo/LiveryChanger | — | **Repository does not exist (HTTP 404)** |

An MIT licence on the *repository* does not licence the airline trademarks or
third-party paint artwork inside it. No SKYBOUND livery may be derived from these
repositories without per-asset permission.

## MSFS Addons aircraft list

Used as a **reference catalog only**. It supplies aircraft names, developers and
article links. It grants no rights to any aircraft model, texture, sound or code.
Section 32.5 of the specification is explicit on this, and the importer enforces
it: every imported record is written with `asset_license: "unknown"` and
`implementation_status: "catalogued"`.

## Assets: current position

No aircraft model, livery, cockpit, sound or terrain asset is present in this
repository. When assets are added, each must record:

`asset_source`, `asset_license`, creator attribution, and the permission basis
(licence path A–D from spec 32.5).

## Cesium ion

World terrain, imagery and 3D Tiles come from Cesium ion and require the user's
own access token. The token is **never** committed: it is read at runtime from
the user's settings or the `CESIUM_ION_TOKEN` environment variable. Cesium's
attribution requirements (data providers) must remain visible in-sim.

## Fonts, icons and audio

Any font, icon set or sound effect added later must be recorded here with its
licence before it is included in a build.

## Reporting

If you believe SKYBOUND includes material used without permission, contact the
address in `README.md`; the asset will be removed pending review.
