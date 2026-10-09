# API reference

Everything a scene or soundtrack can call. Source of truth: `lib/motion.js`, `lib/synth.py`, `tools/render.js`, `tools/build.sh`.

## cues.json (per project)

The single source of timing for picture **and** sound.

| key | default | meaning |
|---|---|---|
| `duration` | required | seconds |
| `fps` | 60 | output frame rate |
| `subframes` | 4 | sub-frames averaged per frame (motion blur quality; 1 = no blur, fastest) |
| `shutter` | 0.5 | fraction of a frame the virtual shutter is open (0.5 = 180 degrees, the film look) |
| `width`, `height` | 1920, 1080 | output size. Also set the same size on `#v` in your CSS, on the `<canvas>`, and in `PV.createWorld(stage, canvas, w, h)`; positions in your scene are yours to re-lay-out |
| `dpr` | 1 | device scale factor (2 renders at 2x then encodes at the larger size - slow) |
| anything else | | your named moments in seconds: `"hit": 2.45`. Strings and numbers are fine (e.g. the typed text) |

## Scene contract (browser)

`index.html` must load `../../lib/motion.js` and your scene file, and the scene must:

1. define `window.seek = t => { ... }` (pure function of `t`),
2. call `window.seek(0); PV.ready();` once fonts and images are loaded (`await PV.loaded([...])` first).

`render.js` waits up to 60 s for `window.__ready === true`, fails on any `pageerror`, and reports any HTTP 4xx (a missing image or font) with its URL.

### `PV` - maths

| | |
|---|---|
| `P(t, a, b)` | progress of `t` through `[a, b]`, clamped 0..1. **Every animation is `ease(P(t, start, end))`.** |
| `lerp(a, b, k)`, `clamp(x, a=0, b=1)` | |
| `eo3 eo4 eoE` | ease **out** (cubic, quartic, exponential): arrive softly. `eo4` is the default for entrances. |
| `ei3` | ease **in** (cubic): for exits |
| `eio3 eio4` | ease in-out: for moves between two resting places (camera, wipes) |
| `eoB(x, s=1.9)` | ease out with back-overshoot: things that "pop" |
| `spring(t, start, freq=2.2, damping=6.5)` | 0 before `start`, then a damped oscillation to 1 (overshoots ~10%). `freq` 2 = bouncy, 1.4 = floaty; `damping` 6-8 settles in ~0.5 s. Use for anything that lands. |
| `rng(seed)` | returns a seeded random function (mulberry32). Create once at the top; never `Math.random()`. |
| `hex('#rrggbb')`, `mixc(hexA, hexB, k)` | colour helpers; `mixc` returns `rgb(...)` |

### `PV` - DOM

| | |
|---|---|
| `createWorld(stageEl, canvasEl?, w=1920, h=1080)` | makes the layer everything lives in (so the camera/shake moves it as one) and sets `PV.world` |
| `mk(html, css, parent?, className='abs')` | create an absolutely positioned div (default parent: the world). Position with `left/top` **once**, animate with `put`. |
| `put(el, {x, y, z, rx, ry, r, s, sx, sy, o})` | the one way to move things: translate (px), rotate X/Y/Z (deg), scale, opacity. `o` <= 0.002 hides the element entirely. |
| `show(el, bool)` | `display:none` toggle for whole scene containers |
| `img(src, css)` | `<img>` markup string |
| `kinetic(text, css, gradient?, parent?)` | a clipped line with one span per letter. Needs `.line`/`.ch` CSS (`lib/motion.css`). |
| `kUpdate(k, t, tin, tout, gap=0.035)` | letters rise + straighten one by one from `tin`; if `tout` is set they drop out from `tout`. Hidden before/after. |
| `shake(t, [[time, px], ...])` | `{x, y}` damped camera shake after each impact; apply to the world's `translate3d` |
| `loaded(fontSpecs?)` / `ready()` | await fonts+images, then flag `window.__ready` |

### Recipes (all pure functions of `t`)

- **Entrance:** `put(el, { y: (1 - eo4(P(t, 1.0, 1.5))) * 80, o: P(t, 1.0, 1.3) })`
- **Landing with bounce:** `const a = spring(t, 1.0); put(el, { s: lerp(0.8, 1, Math.min(a, 1.08)), o: t < 1 ? 0 : 1 })`
- **Stagger:** `items.forEach((e, i) => put(e, { y: (1 - eo4(P(t, 1 + i * 0.08, 1.5 + i * 0.08))) * 60, o: P(t, 1 + i * 0.08, 1.2 + i * 0.08) }))`
- **Camera move:** wrap content in a div with `transform-origin: 0 0`; `put(cam, { s: lerp(1, 1.6, eio4(P(t, 8, 9))), x: -fx * (s - 1), y: -fy * (s - 1) })` to zoom toward point `(fx, fy)`.
- **Circular reveal:** `el.style.clipPath = 'circle(' + r + 'px at ' + cx + 'px ' + cy + 'px)'` with `r = 2000 * eio3(P(t, a, b))`.
- **Typed text:** `el.textContent = full.slice(0, Math.floor(full.length * P(t, a, b)))`; add a blinking caret with `Math.floor(t * 2) % 2`.
- **Counter:** `Math.round(target * eo3(P(t, a, b)))`, finishing before the element fades.
- **Cursor path:** interpolate between element rects (captured from the real UI) with `eio3`; add a click ring (a circle scaled 0 -> 1 with fading opacity) at the click cue.
- **Particles:** precompute velocities with `PV.rng`; position at time `d` since burst: `x0 + vx * (1 - exp(-d*k)) / k`, `y0 + vy * ... + g * d * d`.
- **3D carousel:** parent `perspective: 2400px`, cards `transform: rotateY(a) translateZ(R)` via `put({ry, z})`.
- **Painted background:** a `<canvas>` redrawn from scratch in every `seek` (gradients with `globalCompositeOperation = 'lighter'`, dot grid, vignette, seeded grain).

## Optional timing helpers

Load `lib/timing.js` after `motion.js` to add `keyframes(entries, easing?)`, `beatClock(bpm, offset?)`, `boil(t, id, rate?, seed?)` and `shots(entries, end)`. See [contracts and complete usage recipes](TIMING.md). They are pure-time helpers, not a second renderer.

## `lib/synth.py`

```python
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'lib'))
from synth import *
C = load_cues(HERE); init(C['duration'])
add(kick(), C['hit'])
master(default_out(HERE))        # -> out/<project>/score.wav
```

| function | notes |
|---|---|
| `init(duration, seed=7)` | start a mix; reseeds the noise generator so results are reproducible |
| `add(sound, t, gain=1, pan=0, send=0)` | place a mono array at time `t`; `pan` -1..1; `send` 0..1 feeds the reverb |
| `master(path, body=None, target_rms=-15, ceiling=-1, reverb_mix=0.5, tail=0.9)` | reverb, level the `body=(start,end)` seconds to `target_rms` dBFS, tanh soft-limit at `ceiling`, then a 4x-oversampled true-peak limiter (`limit_true_peak(x, ceil)`), fade out `tail` s, write 16-bit stereo wav. For anything that goes through AAC use `ceiling=-3` (the encoder overshoots by ~2 dB) |
| `load_cues(dir)`, `default_out(dir)` | read cues.json; `out/<project>/score.wav` (or `argv[1]`) |
| `kick(vol)` `hat(vol, open_)` `clap(vol)` `boom(d, vol)` | drums / impact |
| `bass(midi, d, vol)` `pluck(midi, d, vol, bright)` `bell(midi, d, vol)` `blip(midi, vol, d)` `pad([midi...], d, vol, swell)` | tonal |
| `tick(vol, freq)` | keyboard / click; call once per typed letter |
| `whoosh(d, vol, up, f0, f1)` `riser(d, vol)` `reverse_hit(d, vol)` `noise_sweep(d, f0, f1, vol, up)` | movement and tension |
| `click(vol, f)` `pop(midi, vol, d)` `swish(d, vol, up, f0, f1)` `thud(vol, f)` `glide(f0, f1, d, vol)` | soft product-UI sounds: rounded click, 'bubble' note, page/card moving through air, gentle settle, quiet sine glide (a bar filling, a line drawing) |
| `add_voice(x, t, gain)` `read_wav(path)` | voiceover bus. `master()` then high-passes + adds presence + compresses (2.6:1) the voice, **ducks the music** under it (`duck_db=-7`, fast attack, ~0.35 s release), adds a little room (`voice_reverb`), and prints how many dB the voice sits above the music |
| `master(..., duck_db=-7, voice_db=0, voice_reverb=0.1, unit_reverb=False)` | `unit_reverb=True` normalises the music reverb so a `send` of 0.3 means wet is ~10 dB under dry (the legacy default is much wetter) |
| `tt(d)` `midi(m)` `lp hp bp` `env` `expdecay` | building blocks for your own instruments: return `np.array` mono at 44.1 kHz |

Musical shortcuts: MIDI 45 = A2, 57 = A3, 69 = A4, 81 = A5, 93 = A6. A minor / C major pentatonic notes always sound fine over each other. A groove: kick every beat, hat on the off-beat, clap on 2 and 4, 16th-note `pluck` arpeggio through a 4-chord loop, `bass` on 8ths. `examples/pitchcraft/sound.py` is a complete 15 s score.

### `lib/sonic.py` - per-film sound palettes (use this so films stop sounding alike)

`synth.py` has one fixed timbre per instrument, so two films scored with it share their sounds. `sonic.py` adds ~40 instruments (pads, bells, hits, foley, textures, risers), 6 reverb rooms, and a `Palette` that gives each film its own key, mode, instruments and room. Everything takes an `rng` and is deterministic for it; call `P.rng('name')` for a fresh generator each time so repeats differ (reproducibly).

```python
from synth import *; import synth as S; import sonic as SN
seed = SN.seed_of('my-film'); init(C['duration'], seed=seed)          # per-film seed (never hash(): Python salts it)
P = SN.Palette(seed, 'grave', episode=3)       # moods: grave eerie wonder tense warm machine. episode= makes CONSECUTIVE films use different instruments in every role
SN.use_room('plate', seed)                      # chamber hall cathedral plate tin tape (sets synth.ROOM; master() uses it)
P.bed(0, C['duration'], intensity=0.5)          # chord progression + bass + sparse motif in the palette's key/pad voice
add(P.hit(0.7), C['hit'], send=0.3, name='hit') # hit/bell/pulse/pad/bass/motif follow the palette
add(SN.typewriter_key(0.3, P.rng('key')), t, name='key'); add(SN.geiger(6, (4, 40), 0.3, P.rng('g')), t0)
```

Families: pads `strings choir bowed organ glass drone`; plucks/bells `ks fm_bell mallet(wood|glass|metal|musicbox|vibes) epiano`; hits `frame_drum taiko gong anvil stamp(wood|leather|desk|stone) wood_knock sub_drop heartbeat`; foley `typewriter_key typewriter_return paper(slide|rustle|turn) pen_scratch camera_shutter sonar_ping glass_shatter skid`; textures `geiger static morse clock projector tape_hiss wind prop_drone rumble`; risers `shepard pitch_riser`. All ends are click-free (0.3 ms / 2 ms fades) and peak at about `vol`.

### `lib/lush.py` + `tools/key-check.py` - harmonic, in-key instruments (for bright product films) and the check that proves it
`sonic.py`'s pitched voices (mallets, bells, gongs, glides) are inharmonic on purpose and sound sour in a bright film when palettes overlap. `lush.py` has harmonic pads, felt keys, stabs, a tuned sub and kick, `pump()` sidechain, `chord()`/`voice_lead()`, so a whole score can stay in one key (docstring has the recipe). `python3 tools/key-check.py out/x/score.wav --key A --mode ionian [--fail-off 0.12]` reports off-scale and out-of-tune energy, band split and sounds per second. Tests: `tests/test_lush.py`.

### `lib/groove.py` - a step sequencer for grooves that feel played, not pasted

```python
import synth as S, groove as G
g = G.Grid(C['bpm'], swing=0.10)                                           # 16th-note grid; odd steps pushed late by swing * step
G.play(g, 'x...x...x..ox...', lambda v: S.kick(0.5 * v), a, z)             # x = accent, o = ghost (0.45), . = rest; the pattern repeats; a..z are grid steps
G.play(g, G.euclid(9, 16, 1), lambda v: S.hat(0.17 * v), a, z, rng=rng, ms=4)   # Euclidean 9-of-16, +/-4 ms timing jitter (reproducible per rng)
G.play(g, [1] * 16, make, a, z, vel=lambda i: (i - a) / (z - a))           # build-up: velocity ramp
G.fill(g, z, make, n=4)                                                    # a rising fill into step z;  g.time(i), g.step_at(t) convert between steps and seconds
```
`make(v)` receives the hit velocity 0..1 and returns a mono array (any `synth.py` / `sonic.py` instrument). Mix tip learned the hard way: keep `Palette(root=...)` at MIDI 45 or higher - `bed()` puts its bass an octave below the root and a root of 33 puts it at 27 Hz, where it is energy without pitch (the whole mix turned to sub and sat 6 dB under where it should). Check with a band split of the wav, not by feel.

**Measuring "same noises"**: `synth.add(..., name=)` logs a level-independent spectral fingerprint per sound and `master()` writes `score.events.json` next to the wav. Then

```bash
python3 tools/sound-report.py out/a/score.events.json out/b/score.events.json [--threshold 0.98] [--fail-above 0.4] [--json]
```

prints per film the distinct-timbre count and the share of sounds with a twin (cosine >= 0.98), the most repeated sounds, and for each film the share that repeats an earlier film. `--fail-above X` exits 1 if a film's cross-film share exceeds X (use it as a gate). Caveat: the fingerprint is a level-independent 16-band spectrum, so broadband noise (paper, wind) and sub-bass (booms, drops) look alike to it and cluster even when they sound different; read those clusters as a hint, and treat a falling cross-film share as the real signal. Baseline before sonic: film 2 repeated 74% of film 1; with `Palette(episode=n)` consecutive films share 20-40%, mostly the deliberate brand sounds.

## tools

```bash
node tools/doctor.js                                      # check dependencies
bash  tools/new-project.sh <name> [starter|shorts]         # scaffold projects/<name> from templates/<starter|shorts>
node  tools/render.js <project> --stills 1,2.5,9          # PNG stills -> out/<name>/stills/
node  tools/render.js <project> --frames [--workers N] [--only 120-180] [--keep]
python3 tools/voiceover.py <project> [--align] [--report]  # vo.json -> out/<name>/vo/*.wav + manifest.json (see below)
node  tools/render.js <project> --events                  # window.__events published by the scene -> out/<name>/events.json
node  tools/safe-area.js <project> [--every 0.5] [--min-font 24]   # text outside the crop-safe area / too small, at many moments
python3 <project>/sound.py                                # -> out/<name>/score.wav
bash  tools/build.sh <project> [out.mp4]                  # CRF=18 PRESET=slow by default
python3 tools/sheet.py out/sheet.png a.png b.png ... [--cols N] [--width PX]   # contact sheet, aspect preserved (needs Pillow)
npm test                                                  # end-to-end smoke test (~30 s)
```

Environment: `PV_CHANNEL=chrome` (default) or `PV_CHANNEL=""` for Playwright's bundled Chromium.

Timing, for planning: the 15 s example is 3,600 JPEG screenshots and takes about 1-5 minutes on a modern laptop; a 6 s starter about a third of that. `subframes: 2` halves it with a lighter blur; `subframes: 1` is the fast draft mode.

## Voiceover: `tools/voiceover.py`

Neural text-to-speech on the Mac, no cloud. `pip install piper-tts faster-whisper` (the latter only for `--align`). Voices are downloaded once to `~/.cache/piper-voices`.
`projects/<name>/vo.json`:

```json
{ "engine": "piper", "voice": "en_GB-cori-high", "length_scale": 1.0, "noise_scale": 0.5, "noise_w_scale": 0.6,
  "lines": [ { "id": "l0", "text": "Before spending money on AI, ...", "at": 0.5 },
             { "id": "l1", "text": "...takes about 15 minutes.", "say": "...takes about fifteen minutes.", "at": "cardIn" } ] }
```

`at` is seconds or a cue name from `cues.json`; `say` is an optional respelling for the engine (numbers, brand names) while `text` stays the on-screen/script wording; `fit` (optional) squeezes the line into a window by changing `length_scale`.
Output: `out/<name>/vo/<id>.wav` (mono 44.1 kHz, silence-trimmed, peak -3 dBFS) and `manifest.json` (`start end dur nwords wpm`, plus `words[{w,start,end}]` and `wer` with `--align`).
`--align` transcribes each line with Whisper to get **word times** (put a picture cue exactly on the word) and a word-error-rate (a quick intelligibility check; Whisper hears 'Servita' as 'Savita', that is not a TTS fault).
`--report` prints the pace. In `sound.py`: `for l in manifest: add_voice(read_wav('out/<name>/vo/%s.wav' % l['id']), l['start'])`.
**Arithmetic first:** words / minutes. 86 words in 30 s is ~170-185 wpm; a brief that asks for 140-150 wpm needs ~70 words. Say so before building.

## Archival footage and Shorts (full workflow: `docs/SHORTS.md`)

```bash
python3 tools/footage.py search "<q>" [--source ia|commons|all] [--kind video|image]   # rights verdict per hit: public-domain | attribution | check | restricted | unknown
python3 tools/footage.py info|fetch|credits|audit ...      # fetch -> projects/<name>/raw/ + provenance.json; audit exits 1 unless everything is usable; credits -> out/<name>/credits.md
python3 tools/clip.py scan <project> raw/f.mp4 [--from S --to S --every S]   # contact sheets labelled with REAL frame times
python3 tools/clip.py cut  <project> raw/f.mp4 --id a --start S --end S [--ivtc|--deint] [--scale 1.5] [--crop W:H:X:Y]   # -> assets/clips/a/00001.jpg + clip.json
python3 tools/clip.py scenes <project> raw/f.mp4           # likely cut points
node    tools/thumb.js <project> [--only vertical|wide] [--no-safe-check]    # thumb.html?v=vertical|wide -> out/<name>/thumb-9x16.jpg (2160x3840), thumb-16x9.jpg (2560x1440), <= 2 MB; exit 1 if a [data-key] element leaves the safe zone
python3 tools/shorts-meta.py <project>                     # meta.json + provenance.json -> out/<name>/upload.json (private, synthetic-media flag) + upload.md; exit 1 on errors
python3 tools/shorts-check.py out/<name>/<name>.mp4        # vertical, <=180 s, audio, codecs, LUFS, true peak, black first frame
python3 tools/yt-research.py search "<q>" | compare topics.txt   # needs yt-dlp; Shorts-length view statistics (a smell test, not a forecast)
```

Browser side (load after `motion.js`; both are pure functions of `t`):

```js
const clip = await PV.footage.load('assets/clips/tower');           // reads clip.json
clip.mount(parentEl, 'left:0;top:0;width:1080px;height:1920px;');     // two <img> layers (A, B) for frame blending
// in an async seek(t):  clip.at(t - shotStart, { speed: 0.5, offset: 2.0, loop: false, blend: true });  ...  await PV.footage.settle();   // settle() is the LAST line
PV.footage.frameAt({fps, n}, t, {speed, offset, loop})              // pure t -> fractional frame index (clamps to the clip; negative speed plays backwards)
const cap = PV.captions(words, { parent, maxWords: 3, maxChars: 17, hold: 0.22, lead: 0.04 });  cap.update(t);   // words = manifest[line].caps [{t,start,end,emph}]; CSS: .cap-g .cap-w .cap-w.on .cap-w.emph
PV.captionGroups(words, opts)                                       // the phrase grouping alone (breaks at . ? ! , ; : and silences)
```

`vo.json` may mark `*emphasis*`; `voiceover.py --align` then writes `caps` (the script's own words with Whisper's times) next to `words` (what Whisper heard). Engines: `piper`, `kokoro` (`bm_george`; model files in `~/.cache/kokoro`), `say`.

## Scenes publishing moments: `window.__events`

When the picture derives times (cursor clicks along a path, typing windows), do not copy the arithmetic into `sound.py`. Publish them from the scene
(`(window.__events = window.__events || {}).consult = { clicks: [5.2, 5.5], typing: [[5.77, 6.09]] }`), run `node tools/render.js <project> --events`
and read `out/<name>/events.json` in `sound.py`. One source of truth, so the click sound is on the frame where the ring appears.

## Checking text placement: `tools/safe-area.js`

`cues.json` may contain `"safe": {"x": 72, "y": 130, "w": 936, "h": 1090}` (the area that survives a platform crop; 4:5 on LinkedIn / Instagram).
`node tools/safe-area.js projects/x --every 0.5 --min-font 24` calls `seek(t)` at each moment, finds every visible text node (display, visibility and opacity checked up the tree)
and prints `OUTSIDE by N px` / `SMALL N px`. Exit code 1 when something is reported. Expect transient hits while things slide in or the camera moves, and note that the font size it
reports is the CSS size, not the size after an ancestor's scale transform (miniature UI thumbnails are reported small on purpose).

## Portrait / 25 fps

`cues.json` accepts `width`, `height`, `fps` (any), so a 1080x1350 25 fps film is just `{"width":1080,"height":1350,"fps":25}`. Everything else (render, build, sheet) follows.
