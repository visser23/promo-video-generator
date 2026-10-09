# Shorts starter

A 1080x1920, 30 fps, ~12 s vertical film: archival footage, a three-line hook, word-timed captions, an end card that loops back to the first frame.
`bash tools/new-project.sh my-short shorts` copies it to `projects/my-short`. The workflow is in `docs/SHORTS.md`; the short version:

1. `python3 tools/footage.py search "..."` then `fetch projects/my-short ia:<id>` (rights are classified; only public-domain / attribution is usable).
2. `python3 tools/clip.py scan projects/my-short raw/<file>`, look at the sheets, `clip.py cut ... --id demo --start S --end E [--ivtc] [--scale 1.5]`, then list the shots in `cues.json`.
3. Write the script in `vo.json`, run `python3 tools/voiceover.py projects/my-short --align` (captions come from it), put picture cues on the aligned word times.
4. `node tools/render.js projects/my-short --stills 1,3,5`, review (`tools/sheet.py` keeps the 9:16 shape), `node tools/safe-area.js projects/my-short --every 0.5 --min-font 24`.
5. `python3 projects/my-short/sound.py`, `node tools/render.js projects/my-short --frames`, `CRF=26 bash tools/build.sh projects/my-short`, `python3 tools/shorts-check.py out/my-short/my-short.mp4`.
6. `thumb.html` -> `node tools/thumb.js projects/my-short`; fill `meta.json` -> `python3 tools/shorts-meta.py projects/my-short`.
