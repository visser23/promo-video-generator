# AGENTS.md - how an AI should use this repo

You are going to make a short promo / motion-graphics video (an MP4) by writing a small web page, not by editing video.
The page is a **pure function of time**; Chrome photographs it at any moment you ask; ffmpeg turns the photographs into a file.
Read this whole file once, then follow the workflow. Humans: see `README.md`; if you want to brief an AI, see `docs/PROMPTING.md`.

## The idea in 6 lines

1. A project is a folder `projects/<name>/` with `index.html`, `scene.js`, `cues.json`, `sound.py`, `fonts/`, and optional `assets/`.
2. `scene.js` defines `window.seek(t)`. Calling `seek(7.25)` must place every element exactly as it should look at 7.25 s. No timers, no `requestAnimationFrame`, no CSS animations or transitions, no `Math.random()`.
3. `cues.json` is the **single source of timing** (fps, duration, and the named moments: `"hit": 2.45`). `scene.js` reads it for the picture, `sound.py` reads it for the sound, so they cannot drift.
4. `tools/render.js` calls `seek()` for every frame (4 sub-frames per frame by default) and screenshots it.
5. `tools/build.sh` averages the sub-frames (real motion blur), encodes H.264, muxes the soundtrack.
6. Because it is deterministic you can **preview any second as a still in about a second**. Do that constantly.

## Setup (once)

```bash
npm install
node tools/doctor.js          # must end with "All good" - needs node 18+, Chrome, ffmpeg (libx264 + aac), python3 + numpy + scipy
```

If Chrome is missing: `PV_CHANNEL="" npx playwright-core install chromium` and prefix commands with `PV_CHANNEL=""`.

## Optional Tesseract tools

Read [docs/TESSERACT.md](docs/TESSERACT.md) if native editing, an editable `.tsrct` document or asset preparation would help the brief. You may choose Mirage Tesseract; it is not mandatory and its absence must not block the HTML workflow. Review its terms and use matching v0.3.1 skills/CLI. Discover `tsrct` and verify its version using that guide before use; do not install an OCR package, invent an npm dependency or automatically download binaries.

Keep `seek(t)` deterministic when importing prepared assets. Tesseract cannot run our DOM/CSS scenes or automatically consume `cues.json`. For a separate native production, explain the choice, retain editable source in `projects/<name>/`, place generated output in `out/<name>/`, and follow upstream native preview/export guidance. Our doctor and smoke tests do not validate its renderer. Verify the actual native export and report checks you could not perform. The workflow below applies to the existing HTML pipeline.

## Workflow (do these in order)

### 0. Brief - decide before you build
Write down (in your reply or a scratch file): the product, audience, **duration** (15 s is a good default; 6-30 s), 3-5 beats (one idea each), the one line the viewer must remember, brand colours and fonts, the end card (name / tagline / URL), and which **claims** you will make. Only claim what is true and checkable - ask if unsure. No made-up stats, logos, testimonials or features.

### 1. Storyboard into `cues.json`
Give every beat a start time. Rough budget for a 15 s film: spark/hook 0-3, beat 2 3-6, beat 3 6-9, beat 4 9-12, end card 12-15 with a 2 s hold. Name cues for what happens (`"hit"`, `"cursorClick"`, `"urlStart"`), not for numbers. Keep `fps: 60`, `subframes: 4` unless you have a reason.

### 2. Get real pictures
A promo about software is only convincing with the **real product on screen**. Photograph it (see `examples/pitchcraft/capture-assets.js`): Playwright screenshots at device scale factor 2 for slides/cards, a 1920x1080 screenshot per UI state, and the bounding rects of elements you will point at (so a fake cursor lands on the real button). Save to `projects/<name>/assets/`. Never use the user's private data, real accounts or apps (do not script PowerPoint, Keynote, etc.), and avoid anything on the user's screen: use headless only.

### 3. Scaffold and write the scene
```bash
bash tools/new-project.sh my-launch        # copies templates/starter -> projects/my-launch (a working 6 s film)
node tools/render.js projects/my-launch --stills 1,3,5     # -> out/my-launch/stills/t1.00.png ...
```
Read `templates/starter/scene.js` (80 lines, every pattern) and `examples/pitchcraft/promo.js` (a full 15 s film). Then `docs/API.md` for `PV.*`.

### 4. Review loop (the most important step)
After every meaningful change render stills **just before, at, and just after each cue** and around each transition, tile them (`python3 tools/sheet.py out/x/sheet.png out/x/stills/*.png`) and look. Check:
- nothing overlaps wrongly (titles vs panels), nothing is cut off, safe margin >= 80 px;
- leftovers from a previous scene are gone (see gotcha 2);
- every number/text is final when it is meant to be read (a counter that is still counting when it fades is a bug);
- type is readable: >= 60 px for headlines, >= 34 px for supporting text at 1080p; hold a line ~0.25 s per word, min 0.8 s;
- motion principles: ease **out** to arrive, ease **in** to leave, overshoot/spring on things that "land", stagger groups by 0.03-0.15 s, anticipation before big moves, camera shake only on impacts, an end card held >= 1.5 s.

**Vision descriptions of images are unreliable** (they invent or miss details). When it matters, measure: `page.evaluate(() => el.getBoundingClientRect())`, pixel statistics with Pillow/numpy (is the left edge dark? is anything bright where nothing should be?), pixel-diff two stills. Treat "looks fine" as a hint, numbers as truth.

### 5. Sound
Copy `templates/starter/sound.py` and place sounds at `C['cue']` times with `lib/synth.py` (`docs/API.md`). Pattern that works: a drone under everything, a riser into each big moment, a reverse-hit just before it, a boom + kick on it, bells/blips for UI pops, `tick()` per typed character, whooshes for transitions, a pad + bells on the end card, quieter before the drop than after. `master()` sets loudness (~-15 dBFS RMS body, -1 dBFS peak). `python3 projects/<name>/sound.py` -> `out/<name>/score.wav`. You cannot listen, so verify with numbers: per-second RMS/peak, `ffmpeg -i x.mp4 -af volumedetect -f null -`, no clipping, silence only where intended.

### 6. Full render and build
```bash
node tools/render.js projects/my-launch --frames      # 900 frames x 4 sub-frames = 3,600 JPEGs; ~1-5 minutes
bash tools/build.sh projects/my-launch                # -> out/my-launch/my-launch.mp4
```
These are long-running: start them in the background (in Cursor: `block_until_ms: 0`, then await) and poll; do not sleep-loop. Do a quick `--only 300-360` render to spot-check a range first.

### 7. Verify the **mp4**, not just the stills
`ffprobe` it: h264, `yuv420p`, `tv` range, expected width/height/fps, `duration` == cues duration, an `aac` stream. Extract frames from the mp4 (`ffmpeg -ss 8.5 -i x.mp4 -frames:v 1 f.png`) at 8-10 key times and review them as in step 4. Check the file size (15 s at 1080p60 should be ~10-30 MB; if it is >60 MB raise `CRF`).

### 8. Deliver
Tell the user: the mp4 path, duration/resolution, a beat-by-beat description, how to re-render (the three commands), what is committed vs ignored, and anything you could not verify (e.g. you could not listen to the audio). Do not commit/push unless asked.

## Hard rules

- **Determinism.** `seek(t)` is a pure function of `t` (and of constants/seeded `PV.rng`). Same `t` -> the same picture (rendering the same sequence twice is byte-identical; `npm test` checks this). Never put `will-change` on animated elements - see `docs/LESSONS.md`.
- **Fonts are bundled.** Put `.woff2` files in `projects/<name>/fonts/` and `@font-face` them. System fonts differ per machine and break reproducibility. Use OFL / licensed fonts only.
- **Hide scenes with `display:none`** (`PV.show(el, on)`), not `visibility:hidden` on a parent - a child with `visibility:visible` shows through it.
- **Move things with `PV.put()`**, not ad-hoc styles; it hides elements at opacity ~0 so nothing leaks between scenes.
- **No network at render time.** Everything is local; remote images/fonts/CDN scripts will break reproducibility.
- **Tell the truth.** Nothing in the video may claim something the product does not do.
- **Clean up.** `render.js` starts and stops its own server and browser. If a run is killed, look for orphaned Playwright Chrome processes (command line contains `--remote-debugging-pipe`) and kill **those PIDs only**. Never `pkill chrome` - that closes the user's real browser.
- **Outputs stay in `out/`** (git-ignored). Do not commit frames, wavs or mp4s (except a deliberate `examples/**` film).
- Keep `lib/` general; project-specific code lives in the project folder.

## Gotchas learned the hard way

1. **`tmix` averages the trailing window**, so the frame to keep is `n % S == S-1`. `build.sh` does this; if you hand-roll ffmpeg, remember it (keeping `n%S==0` blends sub-frames from the neighbouring frames, so motion is smeared into the wrong time - it was measurably further from the true sub-frame average).
2. **Container visibility.** See rule above; the symptom is a ghost of the previous scene on the end card.
3. **JPEG frames are full range.** Without the `scale=in_range=full:out_range=tv` step ffmpeg produces `yuvj420p`, which some players show with wrong contrast. `build.sh` handles it.
4. **Fonts not loaded at t=0.** Faces only used later are not loaded when you measure text. Pass them to `PV.loaded([...])`.
5. **Measure text after fonts load**, then position (`getBoundingClientRect`), or lockups drift.
6. **Backdrop-filter and big blurs are slow** in headless Chrome. Keep `.glass` panels few; render time scales with it.
7. **Playwright screenshot timeouts** (30 s) usually mean the machine is starved: lower `--workers`, quit other heavy apps, or kill orphaned Chromes.
8. **A counter must finish before its element fades.** Time the count to end ~0.2 s before the exit.
9. **Spinning/3D carousels:** put `perspective` on a parent and `transform-style: preserve-3d`; hide the whole container (`display:none`) when out of range.
10. **Don't trust prose descriptions of images** - measure.

## Repo map

```
lib/motion.js       browser toolkit: easings, spring, seeded rng, put/mk, kinetic type, shake        (docs/API.md)
lib/motion.css      optional base CSS (.abs .line .ch .glass .persp)
lib/synth.py        procedural sound studio: instruments, add(), master()                          (docs/API.md)
tools/render.js     scene -> stills / sub-frames          tools/build.sh   sub-frames (+wav) -> mp4
tools/doctor.js     dependency check                      tools/new-project.sh   scaffold a project
tools/sheet.py      contact sheets for reviewing stills
templates/starter/  working 6 s project to copy
examples/pitchcraft/  a full 15 s film made with this toolkit (+ its mp4), the best reference for quality
projects/           YOUR projects (git-ignored)           out/   all generated output (git-ignored)
tests/smoke.js      end-to-end test (npm test)
docs/               API.md  PROMPTING.md  LESSONS.md
```
