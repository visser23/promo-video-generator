# Project plan - Shorts channel prototype

Goal: prove a toolkit-only, end-to-end path from idea to an uploadable YouTube Short built on free-to-use archival footage, then decide whether a private channel repo is worth creating.

## Done (2026-10-08)
- [x] Review repo, `git pull`, read AGENTS.md / API.md.
- [x] Topic research (Trinity test, 16 Jul 1945: "the bet") and platform-policy research (monetisation thresholds, inauthentic-content policy, AI disclosure, thumbnail rules).
- [x] Tools: footage (rights + provenance), clip (scan/cut/ivtc), voiceover (Kokoro + aligned captions), captions, thumb, shorts-meta, shorts-check, yt-research, true-peak limiter, sheet aspect fix.
- [x] `.gitignore` guard rails (vendored repos, models, secrets, media) with a test.
- [x] Film `projects/trinity-bet` (48.8 s, 1080x1920, 43 MB, -14.2 LUFS, -2.1 dBFS), thumbnails, upload metadata.
- [x] `templates/shorts`, `docs/SHORTS.md`, API/AGENTS/CHANGELOG updates, tests in `npm test`.

## Next (needs the human)
- [ ] Human review: watch + listen to the mp4 on a phone (the agent never heard the audio); open each source landing page once to confirm the rights claims.
- [ ] Upload privately, set the synthetic-media disclosure, attach the 9:16 thumbnail in desktop Studio, publish.
- [ ] After 48 h compare retention and swipe-away against `yt-research.py` expectations; decide on a series format.
- [ ] If continuing: create the private channel repo (this toolkit as a dependency, topic backlog, rights ledger, upload runbook).

## Risks
- YouTube "inauthentic content" policy for repetitive/templated uploads: vary scripts, footage and graphics per video.
- Monetisation thresholds change on 1 Feb 2027; re-check YouTube Help.
- Derivatives of old footage (colourised/upscaled) can carry their own copyright: use originals.
