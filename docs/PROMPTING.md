# Prompting an AI to make your promo video

This repo is built to be driven by a coding AI (Cursor, Claude Code, Codex, etc.) that can run shell commands. You give it a brief; it writes the scene, previews stills, scores it, renders and hands back an MP4. The better the brief, the better the film. Below: what to give it, a paste-ready prompt, and follow-ups that work.

## 1. Before you start

- Open this repo as the workspace so the AI sees `AGENTS.md` (Cursor loads it through `.cursor/rules`; for other tools say "read AGENTS.md first").
- Pick an AI that can run commands **and** look at images. The workflow depends on rendering stills and reviewing them.
- Give it your real material: screenshots, a running local copy of your app, logo SVG, brand colours, font files (`.woff2`), the exact tagline and URL. Without real material it will invent a generic look.

## 2. What a good brief contains

| | example |
|---|---|
| **Product** | "Halo, a calmer email client for Mac" |
| **Audience / channel** | "founders on X and LinkedIn; autoplay without sound, so text must carry it" |
| **Length + ratio** | "15 s, 16:9 (or 9:16 for stories)" |
| **The one thing to remember** | "Inbox zero in two minutes" |
| **Beats** | "1 hook: cluttered inbox collapses. 2 how: three gestures. 3 proof: '4.9' and a testimonial I will supply. 4 end card." |
| **Look + feel** | "dark, glassy, violet to coral gradient, Bricolage Grotesque headlines, confident, fast, with weight - think Apple keynote meets Linear" |
| **Real assets** | "app at http://localhost:3000, logo in assets/logo.svg, fonts in fonts/" |
| **Claims allowed** | "only: 'works offline', '4.9 on the App Store' (true). Nothing else." |
| **End card** | "Halo - Email, calmed. halo.app" |
| **Sound** | "punchy electronic score, ticks when UI types, big hit on the logo reveal; or silent" |
| **Do not** | "no stock footage, no emoji, no fake testimonials" |

Rules of thumb you can state: one idea per beat; 3-5 beats in 15 s; text on screen at least 0.8 s; hold the end card at least 1.5 s; the most impressive moment should be the one you can screen-capture best.

## 3. Paste-ready kickoff prompt

> Read `AGENTS.md` and `docs/API.md` in this repo, and look at `examples/pitchcraft/` (video + code) as the quality bar. Run `node tools/doctor.js` and fix anything missing.
>
> Make a **{N}-second {16:9 | 9:16} motion-graphics promo** for **{product}**: {one-line description}. Audience: {who}. The one thing viewers should remember: **{message}**.
>
> Storyboard (confirm or improve it before you build): {beat 1}; {beat 2}; {beat 3}; end card "{name} - {tagline} - {url}".
> Look and feel: {style words, colours, fonts}. Real assets: {paths / URL}. Capture the real product with Playwright at 2x for anything shown on screen. Allowed claims: {list}. Do not claim anything else.
>
> Process: scaffold `projects/{name}` with `tools/new-project.sh`; write all timings into `cues.json` first; build the scene as a pure `seek(t)`; review stills before/at/after every cue and around every transition, and **measure** layout (bounding rects, pixel checks) instead of trusting your read of an image; synthesise a soundtrack locked to `cues.json` and verify it numerically; render all frames in the background; build the MP4; then verify the MP4 itself with ffprobe and frames extracted from it.
>
> Do not come back until you are proud of it: motion should have easing, overshoot, stagger, depth, camera shake only on impacts, and nothing should overlap or be cut off. Deliver the MP4 path, a beat-by-beat description, and the commands to re-render. Do not commit or push.

## 4. Follow-up prompts that work

**Direction**
- "The hook is too slow. Get to the first strong visual by 0.8 s and cut the intro whoosh."
- "Make the impact at the logo bigger: stronger shake, a shockwave ring, particles that travel further, and a deeper boom."
- "Use more depth: put the product on a 3D plane that tilts toward the cursor, with a soft shadow, and parallax the background grid."
- "The type feels timid. Go to 200 px for headlines, tighter tracking, and add a one-word emphasis in the accent gradient."
- "Add anticipation: before each big move, pull back 12 px for 0.12 s."

**Fixes**
- "At 6.9 s the title overlaps the window. Measure both rects at that time and fix it, then show before/after stills."
- "There is a ghost of the previous scene on the end card. Find the element that is still visible and hide the scene with `display:none`."
- "The counters are still counting when they fade. Finish them 0.2 s before the exit."
- "The audio is too hot in the last 3 seconds. Report per-second RMS/peak before and after."

**Variants**
- "Make a 9:16 version for stories: set width/height in `cues.json` and the `#v` CSS, re-layout, same cues."
- "Make a 6-second cut-down for ads from the same project (new cues file, reuse scenes)."
- "Draft mode: render with `subframes: 1` at 30 fps so I can approve motion quickly, then do the final at 60 fps / 4 sub-frames."

## 5. Quality checklist to ask the AI to run before it replies

- [ ] `node tools/doctor.js` clean; `npm test` passes
- [ ] stills reviewed around each cue and transition; no overlaps, clipping, or leftovers; margins >= 80 px
- [ ] all claims true and supplied by you; names, URLs, numbers spelled exactly as given
- [ ] text readable (>= 60 px headlines, >= 34 px support) and on screen long enough
- [ ] hit/impact moments have: sound, shake, particle or flash, all on the same cue
- [ ] end card held >= 1.5 s with name, tagline and URL
- [ ] audio verified numerically (no clipping, intended silences only); you know it was not listened to
- [ ] MP4 probed: h264, yuv420p, correct size, fps and duration, aac stream present; frames extracted from the MP4 look right
- [ ] no orphaned Chrome/Node processes left running; nothing committed unless you asked

## 6. Tips

- **Show it a reference.** Describe or attach a film you like and say which qualities to copy ("the rhythm of the first 3 s", "the type treatment").
- **Iterate in stills.** Ask for a contact sheet of 9 stills before asking for a full render; most mistakes are visible there.
- **Lock the cues.** If you change timing, change `cues.json` only; the picture and sound follow.
- **Be specific about feelings, not just objects.** "Calm confidence that snaps into energy at the drop" beats "make it cool".
- **It cannot listen.** Audio is verified by numbers. Give feedback by ear ("the riser is too harsh, lower and slower") and let it adjust.
- **Ask for the commit last.** The AI should not commit or push unless you tell it to.

## 7. Optional Tesseract brief

The kickoff prompt above uses the existing HTML pipeline. If useful, add: "You may choose Mirage Tesseract for native editing or asset preparation. Read `docs/TESSERACT.md` first, explain the selected workflow and check the matching CLI/skills and terms. Do not make it a required dependency or convert the HTML scene implicitly. Deliver any native editable source alongside the verified output and its own re-render commands."
