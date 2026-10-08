# Changelog

## Unreleased

- Document optional Mirage Tesseract v0.3.1 setup, platform and usage limits, and separate native/asset workflows for humans and coding agents. The HTML pipeline and dependencies are unchanged.

## 1.0.0 - 2026-10-02
- First release, extracted from the Pitchcraft repository where the toolkit was built for its launch film.
- `lib/motion.js` + `lib/motion.css` (browser toolkit), `lib/synth.py` (procedural audio), `tools/` (render, build, doctor, new-project, sheet), `templates/starter`, `examples/pitchcraft`, `tests/smoke.js`, docs and AI operating manual.
- Differences from the original in-repo tools: generic projects with their own `cues.json` (size, fps, sub-frames, shutter), sound refactored into a reusable library, `will-change: transform` removed from the base CSS (it made rendering order-dependent), ephemeral server port, missing-file and page-error reporting.
