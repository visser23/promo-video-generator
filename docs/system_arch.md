# System architecture (Shorts pipeline)

```
            research                 source                    clip                      script / voice
  tools/yt-research.py   tools/footage.py search      tools/clip.py scan|cut     projects/<n>/vo.json
        (topic stats)    fetch -> raw/ + provenance   -> assets/clips/<id>/       tools/voiceover.py --align
                         audit / credits                 NNNNN.jpg + clip.json    -> out/<n>/vo/*.wav + manifest.json (caps)
                                \                              |                          |
                                 \                             v                          v
                                  +----------> projects/<n>/scene.js  <--- cues.json (timing, shots, end card)
                                               lib/motion.js  lib/footage.js  lib/captions.js
                                               window.seek(t)  (pure function of t)
                                                     |                       \
                                                     v                        v
                                      tools/render.js --frames        projects/<n>/sound.py (lib/synth.py)
                                      (Chrome, 4 sub-frames)          voice bus + music + limiter -> out/<n>/score.wav
                                                     \                        /
                                                      v                      v
                                                    tools/build.sh  (tmix, H.264, AAC)  ->  out/<n>/<n>.mp4
                                                                  |
                           +--------------------------------------+---------------------------+
                           v                                      v                           v
                tools/shorts-check.py            tools/thumb.js (thumb.html)      tools/shorts-meta.py (meta.json + provenance)
                (spec, LUFS, true peak)          -> thumb-9x16.jpg, thumb-16x9.jpg  -> upload.json (private) + upload.md
                                                                  |
                                                       HUMAN uploads (Studio): disclose synthetic media, private first
```

## Rules the design enforces
- One timing source: `cues.json` + `vo/manifest.json`; picture, captions and sound read the same numbers.
- Footage is frames, not `<video>`: determinism (see `docs/SHORTS.md`).
- Nothing leaves the machine except source downloads and research queries (`footage.py`, `yt-research.py`); render is offline.
- Rights gate: `shorts-meta.py` refuses footage that is not public-domain/attribution; `.gitignore` keeps media, models and secrets out of commits.
- No tool uploads or commits; the human publishes.
