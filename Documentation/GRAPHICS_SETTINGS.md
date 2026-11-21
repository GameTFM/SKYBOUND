# SKYBOUND — Graphics Settings

## Principle

The default configuration targets **maximum fidelity** (spec 2.2). Lower presets
exist for weaker hardware; they are not the design target. `Config/DefaultEngine.ini`
requests DX12, Lumen GI + reflections, Virtual Shadow Maps, Nanite, TSR,
volumetric clouds and volumetric fog.

Nothing in that file guarantees a feature is *active*: the engine and driver
decide. The settings UI must read back what is actually enabled rather than
displaying a wish list.

## Presets

| Option | Ultra | High | Medium | Low | Custom |
|---|---|---|---|---|---|
| Global illumination | Lumen HWRT | Lumen | Lumen (SW) | Off / baked sky | user |
| Reflections | Lumen HWRT | Lumen | Lumen (SW) | SSR | user |
| Shadows | VSM, 4 cascades | VSM | CSM | CSM low | user |
| Geometry | Nanite | Nanite | Nanite | traditional LODs | user |
| Anti-aliasing | TSR | TSR | TSR | FXAA | user |
| Volumetric clouds | Full | Full | Reduced | Off | user |
| Volumetric fog | On | On | Reduced | Off | user |
| View distance | 1.0 | 0.9 | 0.7 | 0.5 | user |
| Texture quality | Epic | High | Medium | Low | user |
| Streaming pool | 6000 MB | 4000 MB | 2500 MB | 1500 MB | user |

## Individual settings exposed to the user

Resolution and window mode, resolution scale, anti-aliasing method, texture
quality, terrain quality, object detail, cloud quality, shadow quality,
reflection quality, view distance, ambient occlusion, global illumination,
ray tracing (only offered when the GPU reports support), motion blur, V-sync,
frame-rate limit, HUD scale.

## Hardware detection

On first run, read adapter name, dedicated VRAM, feature level and driver
version, then pick a starting preset. **Let the user override it and remember the
choice.** A wrong automatic pick must never lock someone out of the settings menu.

If VRAM cannot be determined reliably, assume the lower tier and say so in the UI.

## Honest reporting

The settings screen shows detected hardware and the *actual* active feature set,
so a user on an integrated GPU can see "Lumen: off (unsupported)" rather than a
checkbox that appears on and does nothing.

## Performance evidence

None yet. No FPS, frame-time, VRAM or streaming measurements exist for this
project because the build has not run on target hardware. `DEVELOPMENT_LOG.md`
tracks this as an open item; do not publish performance claims until numbers are
recorded with the hardware and scene named.
