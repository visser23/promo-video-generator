# promo-video-generator

**Make cinematic motion-graphics promo videos from code - and let an AI do it for you.**

A small, dependency-light toolkit that turns a web page into an MP4: 1080p, 60 fps, true motion blur, with a synthesised soundtrack locked to the picture. You (or an AI coding agent) write the scene as HTML/CSS/JS, Chrome photographs it frame by frame, and ffmpeg encodes the result. It was built to make the launch film for [Pitchcraft](https://visser23.github.io/pitchcraft/), and that film is included as a worked example.

▶ **Example output:** [`examples/pitchcraft/pitchcraft-promo.mp4`](examples/pitchcraft/pitchcraft-promo.mp4) (15 s, 1920x1080, 60 fps, H.264 + AAC, 18 MB)

![Contact sheet of the Pitchcraft promo](docs/img/pitchcraft-contact-sheet.jpg)

## Why this approach

| | |
|---|---|
| **Deterministic** | A scene is a pure function `seek(t)`. Ask for second 7.25 and you get exactly that frame, every time. No timers, no recording a live page. |
| **Fast to iterate** | Any second of the film is a one-second still render. Review a storyboard as a contact sheet before spending minutes on a full render. |
| **Real motion blur** | Each frame is built from 4 sub-frames sampled across a 180-degree shutter and averaged, so fast moves smear the way a camera sees them. |
| **Picture and sound locked** | One `cues.json` holds every timestamp. The scene reads it; the synthesiser reads it. Change a cue and both follow. |
| **Real product on screen** | Capture screenshots of your actual app with Playwright and animate those, instead of faking UI. |
| **No licensing headaches** | The soundtrack is synthesised from code (numpy + scipy). No samples, no stock music. Fonts are bundled and OFL. |
| **AI-ready** | [`AGENTS.md`](AGENTS.md) is a full operating manual for an AI agent, and [`docs/PROMPTING.md`](docs/PROMPTING.md) tells you how to brief one. |

## Quick start

Requirements: **Node 18+**, **Google Chrome** (or Playwright's Chromium), **ffmpeg** with libx264 + aac, **Python 3** with `numpy` and `scipy` (and optionally `pillow` for contact sheets).

```bash
git clone https://github.com/visser23/promo-video-generator.git
cd promo-video-generator
npm install
node tools/doctor.js                  # checks everything above; prints the fix for anything missing

# make a project from the starter (a working 6 s film) and preview it
bash tools/new-project.sh hello
node tools/render.js projects/hello --stills 1,2.5,4,5.5       # -> out/hello/stills/*.png  (seconds)

# full pipeline
node tools/render.js projects/hello --frames                   # 360 frames x 4 sub-frames
python3 projects/hello/sound.py                                # -> out/hello/score.wav
bash tools/build.sh projects/hello                             # -> out/hello/hello.mp4
```

Re-create the included example from scratch:

```bash
node tools/render.js examples/pitchcraft --frames --workers 5   # 3,600 sub-frames, 1-5 minutes
python3 examples/pitchcraft/sound.py
bash tools/build.sh examples/pitchcraft                         # -> out/pitchcraft/pitchcraft.mp4
```

`npm test` runs an end-to-end smoke test (stills, determinism, sub-frames, sound, mp4 probe, error handling) in about a minute.

## Optional Mirage Tesseract tools

Agents may also choose [Mirage Tesseract](https://github.com/mirage-hq/Tesseract) for native footage editing, motion graphics or static assets when useful. It is a separate CLI and skill bundle, not an npm dependency or a replacement for `seek(t)`. The existing pipeline and included example do not require it.

See [optional setup and workflow guidance](docs/TESSERACT.md) for the version-matched **v0.3.1** release, supported platforms, checksum verification, usage terms and integration limits. No Tesseract binaries or skills are bundled or installed automatically.

## How it works

```
 projects/<name>/                         tools/                               out/<name>/ (git-ignored)
 ├─ cues.json  ── timing, fps, size ──┐
 ├─ index.html + scene.js (seek(t)) ──┼─► render.js ─► stills/*.png, frames/*.jpg ─┐
 ├─ assets/ fonts/                    │    (headless Chrome, 4 sub-frames/frame)   ├─► build.sh ─► <name>.mp4
 └─ sound.py (lib/synth.py) ──────────┴─► score.wav ───────────────────────────────┘   (tmix blur, H.264, AAC)
```

1. **`cues.json`** - `duration`, `fps`, `subframes`, size, and your named moments (`"hit": 2.45`).
2. **`scene.js`** - sets `window.seek = t => ...`, positioning every element for time `t` with the helpers in `lib/motion.js`: easings, springs, seeded random, `put()`, per-letter kinetic type, camera shake.
3. **`render.js`** - serves the repo on a private local port, opens the scene in headless Chrome (several parallel pages), steps `t`, screenshots. Sub-frame `s` of `S` for frame `f` is sampled at `t = (f + (s/(S-1) - 0.5) * shutter) / fps`.
4. **`sound.py`** - places synthesised instruments (`lib/synth.py`) at cue times and masters the result (reverb, loudness, soft limiter).
5. **`build.sh`** - averages sub-frames with ffmpeg `tmix` (that average is the motion blur), converts to TV-range BT.709 `yuv420p`, encodes H.264 + AAC with `+faststart`.

## What is in the box

```
lib/motion.js         browser toolkit (window.PV): maths, easings, spring, rng, put/mk, kinetic type, shake     docs/API.md
lib/motion.css        optional base CSS: .abs .line .ch .glass .persp
lib/synth.py          procedural sound studio: kick, hat, clap, bass, pluck, bell, pad, tick, whoosh, riser, boom, master()
tools/render.js       scene -> stills / sub-frames            tools/build.sh      sub-frames + wav -> mp4
tools/doctor.js       dependency check                        tools/new-project.sh   scaffold from the starter
tools/sheet.py        contact sheet for reviewing stills
templates/starter/    a working 6 s project: kinetic title, glass card, impact, particles, shake, CTA, scored
examples/pitchcraft/  a complete 15 s film (scene, cues, score, captured assets, bundled fonts, the finished mp4)
tests/smoke.js        end-to-end test
docs/                 API.md  PROMPTING.md  LESSONS.md
AGENTS.md             operating manual for AI agents
```

## Using it with an AI (recommended)

Open this repo in an AI-enabled editor (Cursor, VS Code with an agent, Claude Code, Codex CLI...) and give it a brief. The agent reads [`AGENTS.md`](AGENTS.md), which tells it the workflow (brief -> storyboard in `cues.json` -> capture real assets -> scene -> review stills -> score -> render -> verify the MP4), the hard rules, and the traps to avoid.

Start with the paste-ready kickoff prompt in [`docs/PROMPTING.md`](docs/PROMPTING.md#3-paste-ready-kickoff-prompt) and fill in your product, audience, beats, look, assets and the claims you allow. In short, a great brief has: **product, audience, length, the one thing to remember, 3-5 beats, look and feel, real assets, allowed claims, end card, sound**.

## Writing a scene by hand

```js
// projects/hello/scene.js
(async function () {
  const { P, lerp, eo4, spring, mk, put, kinetic, kUpdate } = PV;
  const world = PV.createWorld(document.getElementById('v'), document.getElementById('bg'));
  const title = kinetic('Hello', 'left:150px;top:150px;font-size:180px;');
  const card  = mk('<h3>It moves</h3>', 'left:150px;top:500px;', world, 'abs glass card');

  window.seek = t => {
    kUpdate(title, t, 0.4, 4.8);                                 // letters rise from 0.4 s, drop out at 4.8 s
    const a = spring(t, 1.5);                                    // 0 -> overshoots -> 1
    put(card, { y: (1 - a) * 200, s: lerp(0.9, 1, a), o: t < 1.5 ? 0 : 1 });
  };
  await PV.loaded(); window.seek(0); PV.ready();                 // fonts + images ready, first frame placed, tell the renderer
})();
```

Every animation is `easing(P(t, start, end))`. `P` gives 0..1 progress through a time window; the easing shapes it. That is the whole mental model. The full list of helpers and recipes (staggers, camera moves, circular reveals, typed text, counters, cursors, particles, 3D carousels) is in [`docs/API.md`](docs/API.md).

## Output, git and cleanliness

All generated files go to `out/` (git-ignored): stills, thousands of sub-frame JPEGs, wavs, mp4s. `.gitignore` also ignores `*.mp4`, `*.wav`, `*.mov`, `frames/`, `stills/` everywhere, and your own work in `projects/` (this repo is a toolkit; remove the `projects/*` lines if you want to version your videos here). The only committed film is the example, via the `!examples/**/*.mp4` exception.

## Troubleshooting

| symptom | cause / fix |
|---|---|
| `Scene never set window.__ready` | JS error or missing file - read the lines above it (`PAGE ERROR`, `HTTP 404 ...`). Ensure the scene ends with `await PV.loaded(); window.seek(0); PV.ready();` |
| `page.screenshot: Timeout 30000ms` | machine starved or an orphaned Chrome is hogging it. Lower `--workers`, quit heavy apps. Kill only leftover Playwright Chrome PIDs (command line has `--remote-debugging-pipe`), never `pkill chrome`. |
| Ghost of an earlier scene visible | a hidden parent with a `visibility:visible` child. Hide containers with `display:none` (`PV.show`). |
| Colours look washed out / `yuvj420p` | you bypassed `build.sh`; keep the `scale=in_range=full:out_range=tv` step. |
| Text looks soft or flickers between frames | do not use `will-change: transform`; Chrome then keeps a stale raster scale. See `docs/LESSONS.md`. |
| `Expected N frames ... found M` | the render was interrupted; re-run `--frames` (it wipes and restarts). |
| Fonts differ from your machine | bundle `.woff2` in `projects/<name>/fonts` and `@font-face` them; don't rely on installed fonts. |
| File too big | raise `CRF` (`CRF=22 bash tools/build.sh ...`) or lower `subframes`. Film grain is expensive to compress. |
| Different aspect ratio | set `width`/`height` in `cues.json` (verified: 1080x1920 renders at that size), the same size on `#v` in CSS, the `<canvas>` width/height attributes, the `W`/`H` constants in the scene, and `PV.createWorld(stage, canvas, w, h)`. Then re-lay-out your elements - the starter's positions assume 1920x1080. |

## Limits and honesty

- Audio is synthesised and verified by measurement (levels, clipping, timing); it is tuned by the numbers, not by ear. Listen before you publish.
- Renders need a real Chrome (GPU-less headless works). Backdrop blurs and big canvases make renders slower.
- Rendering is reproducible for a given machine and Chrome version; tiny anti-aliasing differences between machines or between different frame orders on glyphs that are mid-transform are normal.
- The `examples/pitchcraft` scene is a showcase, not a framework: it is dense and specific. Start from `templates/starter`.

## Licence

MIT (see [`LICENSE`](LICENSE)). The bundled example fonts (Inter, Bricolage Grotesque, Instrument Serif, JetBrains Mono) are licensed under the SIL Open Font License 1.1; see [`examples/pitchcraft/fonts/LICENSES.md`](examples/pitchcraft/fonts/LICENSES.md). The Pitchcraft screenshots and logo in the example belong to that project.
