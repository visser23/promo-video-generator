# Example: the Pitchcraft launch film

A 15-second, 1920x1080, 60 fps promo for [Pitchcraft](https://visser23.github.io/pitchcraft/) (a zero-install presentation studio), made entirely with this toolkit. The finished file is [`pitchcraft-promo.mp4`](pitchcraft-promo.mp4).

## Story (cues in `cues.json`)

| time | beat |
|---|---|
| 0.0 - 3.4 | **Describe it.** A spark blooms into a glass prompt bar; "A launch deck for Halo, a calmer inbox" types in with a tick per key; Enter fires a shockwave and the bass drops. |
| 3.4 - 5.0 | A 3D carousel of real Pitchcraft slides spins in; a whip-wipe leaves. |
| 5.0 - 9.3 | **Edit it.** The real editor floats in; a cursor clicks the headline, then steps through four themes; counters land on "5 themes · 23 layouts · 50+ fonts". |
| 9.3 - 12.1 | **Present it. *anywhere.*** Fullscreen slide, PowerPoint and PDF tiles, and a share link that types itself in, with a lock click. |
| 12.1 - 15.0 | Collapse into the logo, particle burst, wordmark, "Presentations, *crafted.*", URL pill, sparkle tail. |

## What to study

- `promo.js` - one scene function per beat plus shared helpers from `lib/motion.js`: kinetic type, a spring-driven prompt card, a CSS-3D carousel, a circular clip-path reveal, a camera that zooms toward a point, cursor choreography aligned to real element rectangles (`assets/editor.json`), a dot grid that ripples with each impact, particle bursts and camera shake on four cues.
- `sound.py` - a complete score: drone, riser, reverse-hit, a groove from the drop to the collapse, UI ticks and blips on every on-screen event, an end-card chord and bells.
- `capture-assets.js` - how the real product pictures were photographed (slides at 2x, the editor in five themes, and element rectangles). You need a copy of the Pitchcraft app to re-run it (`PITCHCRAFT_DIR=/path/to/pitchcraft`); the captured `assets/` are committed, so rendering does not need it.

## Rebuild

```bash
node tools/render.js examples/pitchcraft --frames --workers 5
python3 examples/pitchcraft/sound.py
bash tools/build.sh examples/pitchcraft        # -> out/pitchcraft/pitchcraft.mp4
```

## Optional tools

This example uses the HTML/Chrome/ffmpeg pipeline only; Tesseract is not needed to rebuild it. For new projects, agents may choose the separate Mirage Tesseract tools where native editing or asset preparation helps. Read [setup and integration limits](../../docs/TESSERACT.md) first: Tesseract cannot directly render `promo.js` or consume this example's `cues.json`.
