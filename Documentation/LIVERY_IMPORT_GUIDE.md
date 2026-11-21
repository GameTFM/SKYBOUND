# SKYBOUND — Livery Import Guide

## First, the rights reality

An **MIT licensed repository does not license airline artwork.** The inspection
in `livery_sources.json` records this explicitly: the code may be MIT while the
liveries inside are third-party trademarks and paint work. SKYBOUND therefore
does not ship any livery from those repositories.

No livery enters the game without a recorded permission or an original paint.

## A livery record

```json
{
  "livery_id": "a320-delta-n301dn",
  "aircraft_id": "airbus-a320-200",
  "operator": "Delta Air Lines",
  "livery_name": "Current",
  "registration": "N301DN",
  "country": "US",
  "texture_set": ["T_A320_Fuselage_BC.png", "T_A320_Fuselage_N.png"],
  "preview_image": "previews/a320-delta.png",
  "creator": "…",
  "source": "…",
  "license": "permission: <reference> | original | CC-BY-4.0",
  "permission_reference": "…",
  "compatibility": "verified"
}
```

`compatibility` values: `verified`, `unverified`, `incompatible`. Only `verified`
liveries may be selected in-game. "The names look similar" is not compatibility
(spec 32.10).

## Compatibility validation checklist

- [ ] model UV layout matches the target aircraft
- [ ] texture dimensions are power-of-two and within budget
- [ ] material assignments resolved for every mesh slot
- [ ] registration and operator correct for the scheme
- [ ] creator attribution recorded
- [ ] licence permits redistribution in a packaged product

## Texture pipeline

Source (PNG/TGA, 4K max) → sRGB base colour + linear normal/roughness/metal →
import to `/Game/Liveries/<aircraft_id>/<livery_id>/` → build a material instance
from the aircraft's master material → assign to the livery data asset.

Guidance: 4K for fuselage, 2K for wings/tail. Keep total VRAM per livery under
~250 MB; larger sets must be a separate downloadable pack.

## Attribution in-game

Every livery's detail panel shows creator, source and licence, and the About
screen credits all contributors. Attribution text is stored in the record, not
hard-coded in UI (spec 6.4).

## Research sources

`Tools/LiveryCatalogInspector` records the six specified repositories: five exist,
one (`Ariakim-Taiyo/LiveryChanger`) returns 404 and is recorded as unavailable
rather than assumed. Re-run it periodically; the output is a research register,
never an asset library.
