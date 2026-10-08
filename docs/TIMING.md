# Optional shot, rhythm and hand-drawn timing

Load `../../lib/timing.js` after `../../lib/motion.js` in a project's HTML. This adds four helpers to `PV` without changing the renderer, starter or soundtrack. Use them for multi-shot films, music-led motion, multi-stop paths or gently changing hand-drawn edges. A simple entrance still only needs `PV.P` and an easing.

## Keyframes

Compile a path once, outside `seek`. Times must increase strictly. Values are finite numbers or equal-length numeric arrays. Evaluation clamps outside the path; the default easing is linear. Returned arrays are fresh copies. An easing may overshoot.

```js
const camera = PV.keyframes([
  [C.hook, [0, 0, 1]],
  [C.product, [-120, -40, 1.2]],
  [C.endCard, [0, 0, 1]]
], PV.eio3);
// In seek(t):
const [x, y, s] = camera(t);
PV.put(cameraLayer, { x, y, s });
```

## Beat clock

Keep `bpm` and `beatOffset` in `cues.json`. The offset is the time of beat zero, in seconds, not a phase fraction. Use `clock.time(n)` to place matching audio events from the same timing data; in Python the equivalent is `C['beatOffset'] + n * 60 / C['bpm']`. Do not guess the tempo or timing of a supplied song.

```js
const clock = PV.beatClock(C.bpm, C.beatOffset);
// In seek(t): small emphasis, not a constant camera shake.
PV.put(accent, { s: 1 + 0.04 * clock.pulse(t) });
```

`seconds` is the beat length; `position(t)` returns fractional beats (negative before the offset). `pulse(t, subdivision=1, decay=6)` returns 1 at each beat and decays exponentially through its phase; it returns 0 before beat zero. Subdivision 2 gives eighth notes, 4 gives sixteenths. BPM, subdivision and decay must be positive. This is a constant-tempo clock, not an audio analyser.

## Hand-drawn boil

`PV.boil(t, id, rate=12, seed=0)` returns a repeatable value in [-1, 1], held for each `1/rate`-second bucket. Use stable string or numeric identities for each object and axis. Calls in a different order produce the same result. Unlike `PV.rng`, no random-generator state survives a seek.

```js
// In seek(t), after clearing a canvas or resetting all DOM transforms:
const dx = 2 * PV.boil(t, 'outline:x', 12, 7);
const dy = 2 * PV.boil(t, 'outline:y', 12, 7);
PV.put(outline, { x: dx, y: dy });
```

Keep text, logos and real UI steady. Use small offsets on decorative outlines or shapes. Avoid whole-frame random grain: it costs compression quality. A boil changes abruptly at bucket boundaries; sub-frame averaging may blend those boundaries. Review with the final shutter setting, or choose `subframes: 1` deliberately for a stepped look.

## Shot routing

`PV.shots([[start, value], ...], end)` compiles an ordered shot list. Values can be names, functions or scene objects. Evaluation returns `{value, index, start, local, duration}` or `null` outside the list. Each interval is half-open: the new shot owns the exact cut; `end` selects nothing. End must follow the last start.

```js
const layers = [hookLayer, productLayer, endLayer];
const track = PV.shots([
  [C.hook, 0], [C.product, 1], [C.endCard, 2]
], C.duration);
window.seek = t => {
  const shot = track(t);
  layers.forEach((layer, i) => PV.show(layer, shot !== null && i === shot.value));
  if (shot) drawShot[shot.value](t, shot.local, shot.duration);
  // Reset/update shared overlays here on EVERY seek, including outside shots.
};
```

Callbacks must set their complete scene state on every call. For canvas shots, clear and repaint the entire canvas, including background. Do not rely on a previous frame or mutate timing arrays. Keep fonts/images ready before calling `PV.ready()` as usual.

## Workflow for larger scenes

Partition scene work by shot or chapter module with private helpers. Give each worker its time window, cue names, palette, focal action, shared API and writable file list. Keep the shared scene bootstrap and cue file under one owner. Agree on outgoing and incoming compositions at cuts before parallel work. Test exact cuts and adjacent frames after combining the modules.

A transition overlay can hide a hard cut: cover the old scene completely at the cue, switch scenes underneath, then uncover the new scene. Use an existing DOM/CSS wipe or circular reveal, not a second renderer. Reset the overlay on every seek and test full coverage at the cut. Keep subtitles or other persistent overlays in screen space and reserve their layout band in every shot.

## Provenance and selection

These helpers were independently implemented after reviewing [PDoomVideo](https://github.com/JohnHeibel/PDoomVideo) at `fa546a38092e75f2b079e6a86d6abc54dd525d17`. The useful ideas were multi-shot routing with local time, scalar/vector paths, constant-tempo pulses, time-bucketed drawing variation and chapter-specific work boundaries. No upstream code, prose, palettes, characters, lyrics, music, fonts or assets were copied.

PDoomVideo's package metadata declares ISC, but the reviewed checkout has no standalone licence text or copyright grant. Treat copying as unverified rather than assuming that field licenses all artwork and audio. Its direct dependencies declare p5 LGPL-2.1, p5.brush MIT and puppeteer-core Apache-2.0 in its lockfile; transitive dependencies have further licences. None were added here. This project's MIT licence continues to cover the new implementation. Existing Playwright is Apache-2.0, NumPy and SciPy are BSD-3-Clause, and Pillow uses HPND. ffmpeg's applicable licence depends on its build; libx264 is GPL-2.0-or-later. No binaries are redistributed by this change.

Rejected overlap: pure-time rendering, seeded randomness, easing, camera movement/shake, contact sheets, screenshot review, parallel render workers, frame retention and ffmpeg encoding already exist here. Excluded: p5/WebGL watercolour rendering and its dependency tree, project-specific characters and karaoke, automatic audio analysis, bundled media and another live-preview UI. Their value does not justify replacing or expanding the existing pipeline for this addition.
