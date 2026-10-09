# Making a YouTube Short from archival footage

The recipe proven on `projects/trinity-bet` (48.8 s, 1080x1920, 30 fps; public-domain film, AI voice, synthesised score, motion graphics).
Read `AGENTS.md` first; this file is only what is different for a vertical, footage-led, voiced Short.

```
research -> source -> clip -> script -> picture -> sound -> render -> check -> thumbnail -> metadata
yt-research  footage.py  clip.py  vo.json   scene.js   sound.py  render/build  shorts-check  thumb.js  shorts-meta
```

## 0. Setup (once)

`python3 -m pip install kokoro-onnx faster-whisper yt-dlp Pillow numpy scipy` and download `kokoro-v1.0.onnx` + `voices-v1.0.bin` to `~/.cache/kokoro` (URL in the `Kokoro` docstring of `tools/voiceover.py`; models are never committed). `node tools/doctor.js` checks the rest.

## 1. Choose a topic (and be honest about the algorithm)

- `python3 tools/yt-research.py search "<query>" --max-duration 60` summarises Shorts-length results for a query (count, median / p75 / max views, "hits" > 20x median, how much one channel dominates). Put 3-5 candidate topics in a text file (one per line) and rank them with `python3 tools/yt-research.py compare topics.txt`. It reads public metadata through yt-dlp; it does not predict anything.
- What the data and the platform say: Shorts are judged on **stayed-to-watch vs swiped-away** in the first seconds and on **loops/replays**. So: a claim or question on frame 0, no logo/intro card, one idea per 3-5 s, and an ending that returns to the first frame (the film opens and closes on a white flash so the loop is seamless).
- Pick a topic with a **primary-source film that really exists in the public domain**, a hook that is a *fact* (not a vague teaser), a concrete number or object, and a closing question that invites comments. Avoid anything you cannot verify from two sources.
- Do not mass-produce one template. YouTube's "inauthentic content" policy targets repetitive, templated uploads; every video needs its own script, footage selection and graphics.

## 2. Source footage legally

```bash
python3 tools/footage.py search "trinity test 1945" --source ia          # --source ia|commons|all, --kind video|image; verdict per hit
python3 tools/footage.py info ia:gov.doe.0800001                          # licence verdict + files on offer
python3 tools/footage.py fetch projects/<name> ia:gov.doe.0800001        # downloads to raw/, writes provenance.json
python3 tools/footage.py audit projects/<name>                           # every file used needs a rights class and a source URL
python3 tools/footage.py credits projects/<name>                         # attribution lines for the description
```

- Only **public-domain** or **attribution** classes pass `shorts-meta.py`. A work of the US federal government is public domain; "free to view" is not free to reuse; "no known copyright" needs a reason.
- Photos (portraits, tower) come from Commons: record author, licence and URL in `provenance.json`. Check the licence once on the file page - tools classify, a human confirms.
- Raw downloads, `*.mkv/*.mp4/*.ogv`, models and secrets are git-ignored (see `.gitignore`); `projects/` is ignored wholesale.

## 3. Clip it

```bash
python3 tools/clip.py scan projects/<name> raw/film.mp4 --from 0 --to 600 --every 10     # contact sheets of REAL frame times
python3 tools/clip.py cut  projects/<name> raw/film.mp4 --id tower --start 83 --end 100 --scale 1.5   # frames + clip.json
```

- Film transferred to video is often **telecined** (a "combing" pattern on motion): add `--ivtc` (fieldmatch + yadif + decimate -> 23.976 fps). `cut` prints a note when the source is flagged interlaced.
- Landscape film in a 9:16 frame: scale the clip up and pick `pos` (`object-position`) so the subject is in the safe area; do not letterbox.
- `scan` labels each thumbnail with the true time from ffmpeg's showinfo (an old fps filter labelled the wrong frame). Look at the sheet; do not guess from the file name.
- `lib/footage.js` maps time to frame: `clip.at(t, {speed, offset, blend})`. Slow motion (0.3-0.6x) with `blend` cross-fades frames so film from 24 fps does not stutter. `await PV.footage.settle()` is the **last line** of an async `seek`; without it a screenshot can beat the decode.
- Show exactly **one** live shot at a time (`SHOTS.find(...)`). Several shots sharing one clip element once hid each other.

## 4. Script, voice, captions

- `vo.json` -> `python3 tools/voiceover.py projects/<name> --align` (offline Kokoro voice, Whisper alignment). Words-per-minute: keep Shorts around 150-170 wpm; the tool prints the pace and the alignment word-error-rate. `*word*` marks an emphasis word that is coloured in the captions.
- `out/<name>/vo/manifest.json` gives each line `caps: [{t,start,end,emph}]`. Put picture cues **on the spoken word** (`wd('l5','exploded').start`), not on guessed numbers.
- `lib/captions.js` groups words into 1-3 word phrases (breaks at sentence ends, commas, silences) and highlights the current word. Centre captions on the safe rect, not the screen.
- Fact-check every sentence and write the checkable claims into `meta.json` `facts`. Where sources disagree (Trinity yield: 18.6, 21, 24.8 kt) say "over twenty thousand", not a number you cannot defend. A graphic that is a reconstruction (a clock, a wager slip) must say so on screen.

## 5. Picture

- Start from `bash tools/new-project.sh <name> shorts`. `cues.json` drives shots, hook lines and the end card; copy `projects/trinity-bet/scene.js` for bespoke cards (typed slips, stamps, charts).
- Frame-0 rule: something must be legible and moving at t=0 (the template opens at 80% white flash decaying over 0.4 s with the hook already animating).
- Safe area: keep text inside `{x:60,y:230,w:900,h:1250}`. The Shorts UI covers the top ~220 px, the bottom ~380 px and the right ~160 px. Run `node tools/safe-area.js projects/<name> --every 0.5 --min-font 24`.
- Film look that survives compression: low-amplitude grain (heavy grain tripled the file size), slight sepia, vignette, flicker, gate weave, a slow push. Camera shake only on impacts.
- Review loop: stills at, just before and just after each cue; tile with `python3 tools/sheet.py out/x/sheet.png out/x/stills/*.png --width 2400` (aspect is preserved; use `--cols`). Then **measure** anything that matters.

## 6. Sound

- **Give every film its own sound**: seed from the slug, build a `sonic.Palette(seed, mood, episode=n)`, pick a room, then run `tools/sound-report.py` across your films' `score.events.json` (API.md, `lib/sonic.py`). Keep only deliberate brand sounds (sign-off, end-card sting) constant.
- `projects/trinity-bet/sound.py` is the reference: voice bus + ducked music, riser -> reverse hit -> boom on the key moment, ticks for typed text, whooshes on transitions, a pad on the end card.
- **Headroom for AAC.** The encoder overshoots by ~2 dB, so a -1.5 dBTP master measured +0.6 dBTP after AAC. `master()` now ends with a 4x-oversampled true-peak limiter; use `ceiling=-3.0`. Aim for about -14 LUFS integrated.
- A quiet beat right before the big hit makes it land. Verify with numbers (per-second RMS, `shorts-check.py`); you cannot listen.

## 7. Render, build, check

```bash
node tools/render.js projects/<name> --frames           # 48.8 s x 30 fps x 4 sub-frames ~ 5,900 JPEGs, ~2 min on an M-series Mac
CRF=26 bash tools/build.sh projects/<name>              # 57 MB at CRF 24 with heavy grain; ~35-50 MB at CRF 26
python3 tools/shorts-check.py out/<name>/<name>.mp4     # vertical, <=180 s, h264/aac, loudness, true peak, not black on frame 0
```

Run long renders in the background and poll; never `pkill chrome` (see AGENTS.md).

## 8. Thumbnail

`projects/<name>/thumb.html?v=vertical|wide` -> `node tools/thumb.js projects/<name>` writes `thumb-9x16.jpg` (2160x3840) and `thumb-16x9.jpg` (2560x1440), each <= 2 MB (YouTube's limit), and fails if any `[data-key]` element leaves the safe zone. Practice: one subject, <= 3-4 words at huge size, high contrast, a face or the key object, no tiny text. Custom Shorts thumbnails can only be set from desktop YouTube Studio (9:16 recommended); the frame the feed shows is otherwise chosen from the video.

## 9. Metadata and upload

`python3 tools/shorts-meta.py projects/<name>` validates `meta.json` against provenance and writes `out/<name>/upload.json` (private, `containsSyntheticMedia` set) and `upload.md` (a paste-ready checklist). It fails on: title > 100 chars, `<` `>` in text, description > 5000 bytes, bad hashtags, tags > 500 chars, an unknown category, a duration > 180 s, footage whose rights class is not public-domain/attribution.

- **Disclose synthetic media**: AI voice and AI music are "realistic" altered/synthetic content - tick the disclosure in Studio. Keep `Made for kids: No`.
- Upload **private** first, watch it on a phone, then publish. Hashtags in the description; at most 3 show above the title.
- Links in Shorts descriptions may not be clickable; put the source names in plain text too and use a pinned comment for the main link.
- Monetisation context (checked Oct 2026): Partner Programme at 1,000 subscribers + 4,000 public watch hours or 10 M Shorts views in 90 days; from 1 Feb 2027 new creators face 8,000 hours / 20 M views and Shorts revenue share needs 10 M qualified Shorts views. Re-check YouTube Help before relying on any number.

## 10. Lessons (details in docs/scratchpad.md)

| Symptom | Cause | Fix |
|---|---|---|
| Stray `-` clip names, negative durations | ffmpeg read the shell loop's stdin | `-nostdin` + `stdin=DEVNULL` in `clip.py` |
| 9:16 stills squashed in contact sheets | fixed cell aspect | `sheet.py` preserves aspect |
| Footage invisible after the shot changed | a later inactive shot hid the shared element | one active shot via `find` |
| Flash looked like a grey screen | an overlay hid the cut | cut to the cloud at the reveal with a decaying white overlay |
| +4.5 dBFS after AAC | encoder overshoot | true-peak limiter; `ceiling=-3`, or `-6` if `shorts-check` still reports > -1 dBTP (overshoot is 2-5 dB and content-dependent) |
| 160 MB mp4 | heavy full-frame grain at CRF 18 | grain opacity .4, CRF 24-26 |
| Fixture "-18 dB" tests failing | lavfi `sine` is already -18 dBFS | set volumes from that baseline |

## 11. A channel on top of this toolkit

This toolkit stays general. A branded channel (house style, episodes, prompting, rights policy) belongs in its **own repo** that treats this one as a tool:
the channel's `episodes/<slug>` are symlinked into this repo's git-ignored `projects/` (render.js only accepts projects inside the toolkit; outputs land in `out/<slug>/`),
and `sound.py` must be run via the symlinked path with `os.path.normpath` (the OS resolves `..` through symlinks). Worked example: the private *The Footnote Files* repo
(`bin/ff` wraps everything; `brand/ff.js` builds a whole branded episode from `cues.json` + the aligned voice manifest).
