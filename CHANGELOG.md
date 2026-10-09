# Changelog

## 1.3.0 - 2026-10-09
Sound variety: films scored with `synth.py` alone all shared the same noises (74% of film 2's sounds had a twin in film 1).
- `lib/sonic.py`: ~40 seeded instruments (incl. `glass_shatter`, `skid`), 6 rooms, 6 moods, `Palette(seed, mood, episode=)` and `Palette.bed()`. See `docs/API.md`.
- `lib/synth.py`: `add(..., name=)` logs a spectral fingerprint per sound; `master()` writes `score.events.json`; `synth.ROOM` hook for selectable reverbs. Defaults unchanged.
- `tools/sound-report.py`: counts distinct timbres, within-film and cross-film twins; `--fail-above` gate.
- `lib/lush.py` (harmonic in-key instruments) and `tools/key-check.py` (off-scale / out-of-tune share of a score). Test: `tests/test_lush.py`.
- `Palette.bass` folds notes below A1 (55 Hz) up an octave.
- `lib/groove.py`: swung step sequencer on top of `synth.add()` (`Grid`, `euclid`, `play` with accents / ghost notes / humanised timing / velocity ramps, `fill`). Test: `tests/test_groove.py`.
- `tools/freeze-page.js`, `tools/freeze-decode.py`, `docs/FREEZE.md`, `tests/freeze.js`: freeze a logged-in page into a standalone HTML file for headless screenshots.
- Tests: `tests/test_sonic.py` (every instrument finite/length/level/click-free/deterministic, palette rotation, rooms, event log, report), run by `npm test`.

## 1.2.0 - 2026-10-08
(Docs addendum, same day: `docs/SHORTS.md` section 11 describes layering a channel repo on the toolkit via symlinks into `projects/`; the true-peak ceiling advice is now `-3`, or `-6` when AAC overshoot still exceeds -1 dBTP.)
Archival-footage YouTube Shorts workflow, proven end to end on `projects/trinity-bet` (48.8 s, 1080x1920, public-domain film, AI voice + score). See `docs/SHORTS.md`.
- `tools/footage.py`: search Internet Archive / Wikimedia Commons, classify rights (public-domain | attribution | check | restricted | unknown), fetch into `raw/`, keep `provenance.json`, `credits`, `audit`.
- `tools/clip.py`: `scan` (contact sheets labelled with real frame times), `cut` (frame sequences + `clip.json`; `--ivtc` inverse telecine, `--deint`, `--scale`, `--crop`, `--denoise`), `scenes`.
- `lib/footage.js` (time -> frame, frame blending, `settle()` before screenshots) and `lib/captions.js` (word-timed phrases, emphasis).
- `tools/voiceover.py`: Kokoro and `say` engines, `*emphasis*` markup, `caps` = the script's own words with aligned times.
- `tools/thumb.js` (9:16 + 16:9 thumbnails, <= 2 MB, safe-zone check), `tools/shorts-meta.py` (upload metadata + validation, always `private`, synthetic-media flag), `tools/shorts-check.py` (Shorts spec + loudness + black first frame), `tools/yt-research.py` (topic view statistics via yt-dlp).
- `lib/synth.py`: `limit_true_peak()` (4x oversampled) now part of `master()`; use `ceiling=-3` before AAC.
- `tools/sheet.py`: aspect-preserving cells, `--cols`, `--width`. `tools/new-project.sh <name> [starter|shorts]`; new `templates/shorts`.
- `.gitignore`: guard rails for vendored repos, model weights, secrets/cookies/tokens, downloaded media and archives.
- Tests: `tests/shorts.js`, `test_clip.py`, `test_footage.py`, `test_voiceover.py`, `test_meta.py`, `test_sheet.py`, `test_synth.py` (all run by `npm test`).

## 1.1.0 - 2026-10-07
- `tools/voiceover.py`: offline neural TTS (Piper) per line from `vo.json`, optional Whisper word alignment + WER, pace report.
- `tools/safe-area.js`: reports visible text outside a crop-safe area or below a minimum size, at any moments; `cues.json` `safe` rect.
- `tools/render.js --events`: scenes publish `window.__events`, written to `out/<name>/events.json` for `sound.py`.
- `lib/synth.py`: voiceover bus (`add_voice`, `read_wav`) with presence EQ, compression, music ducking and a balance report; soft UI sounds (`click pop swish thud glide`); `master(unit_reverb=True)` option. Defaults for existing scores are unchanged.
- First portrait (1080x1350, 25 fps) film built with the toolkit: `projects/servita-sme` (git-ignored).

## Unreleased

- Document optional Mirage Tesseract v0.3.1 setup, platform and usage limits, and separate native/asset workflows for humans and coding agents. The HTML pipeline and dependencies are unchanged.

## 1.0.0 - 2026-10-02
- First release, extracted from the Pitchcraft repository where the toolkit was built for its launch film.
- `lib/motion.js` + `lib/motion.css` (browser toolkit), `lib/synth.py` (procedural audio), `tools/` (render, build, doctor, new-project, sheet), `templates/starter`, `examples/pitchcraft`, `tests/smoke.js`, docs and AI operating manual.
- Differences from the original in-repo tools: generic projects with their own `cues.json` (size, fps, sub-frames, shutter), sound refactored into a reusable library, `will-change: transform` removed from the base CSS (it made rendering order-dependent), ephemeral server port, missing-file and page-error reporting.
