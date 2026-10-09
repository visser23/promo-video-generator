#!/usr/bin/env node
/* render.js - step a scene through time with headless Chrome and save screenshots.

   node tools/render.js <project> --stills 0.5,3.2,9      PNG stills at those seconds           -> out/<name>/stills/t<sec>.png
   node tools/render.js <project> --frames                every sub-frame as JPEG               -> out/<name>/frames/NNNNNN.jpg
        [--workers N]      parallel Chrome pages (default: cores - 2, max 6)
        [--only 120-180]   render just frames 120..180 (quick spot-checks; still wipes the frames dir unless --keep)
        [--keep]           do not wipe the frames dir first
   node tools/render.js <project> --events                write window.__events (moments the picture derived at load: cursor clicks, typed text...) -> out/<name>/events.json
        so sound.py can read them instead of re-deriving the same arithmetic (scenes publish with:  (window.__events = window.__events || {}).name = {...})
   <project> is a folder (under this repo) containing index.html and cues.json.  Optional env: PV_CHANNEL=chrome (default) | "" for bundled Chromium.

   Frame f, sub-frame s of S is rendered at   t = (f + (s/(S-1) - 0.5) * shutter) / fps   (shutter = fraction of a frame the "camera" is open, default 0.5).
   tools/build.sh averages the S sub-frames of each frame, so anything that moves during the shutter is blurred like real film. */
const { chromium } = require('playwright-core');
const http = require('http'), fs = require('fs'), path = require('path'), os = require('os');
const REPO = path.join(__dirname, '..');
const MIME = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.json': 'application/json', '.mp4': 'video/mp4', '.gif': 'image/gif' };
const arg = n => { const i = process.argv.indexOf('--' + n); return i < 0 ? null : (process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[i + 1] : true); };

const projectArg = process.argv[2] && !process.argv[2].startsWith('--') ? process.argv[2] : null;
if (!projectArg || !(arg('stills') || arg('frames') || arg('events'))) { console.log('usage: node tools/render.js <project-dir> (--stills 1,2.5 | --frames [--workers N] [--only a-b] [--keep] | --events)'); process.exit(2); }
const PROJECT = path.resolve(projectArg);
if (!PROJECT.startsWith(REPO + path.sep)) { console.error('The project folder must live inside this repo (so ../../lib/motion.js resolves). Try projects/<name>.'); process.exit(2); }
if (!fs.existsSync(path.join(PROJECT, 'index.html'))) { console.error('No index.html in ' + PROJECT); process.exit(2); }
const NAME = path.basename(PROJECT), OUT = path.join(REPO, 'out', NAME);
const CUES = JSON.parse(fs.readFileSync(path.join(PROJECT, 'cues.json'), 'utf8'));
const FPS = CUES.fps || 60, DUR = CUES.duration, S = CUES.subframes || 4, SHUTTER = CUES.shutter === undefined ? 0.5 : CUES.shutter, W = CUES.width || 1920, H = CUES.height || 1080, DPR = CUES.dpr || 1;
if (!DUR) { console.error('cues.json needs "duration" (seconds)'); process.exit(2); }

(async () => {
  const srv = http.createServer((q, r) => {
    let p = path.join(REPO, decodeURIComponent(q.url.split('?')[0])); if (!p.startsWith(REPO)) { r.statusCode = 403; return r.end(); } if (p.endsWith(path.sep)) p += 'index.html';
    fs.readFile(p, (e, d) => { if (e) { r.statusCode = 404; r.end(); } else { r.setHeader('content-type', MIME[path.extname(p)] || 'application/octet-stream'); r.end(d); } });
  }).listen(0, '127.0.0.1');
  await new Promise(r => srv.on('listening', r));
  const url = `http://127.0.0.1:${srv.address().port}/${path.relative(REPO, PROJECT).split(path.sep).join('/')}/index.html`;
  const channel = process.env.PV_CHANNEL === undefined ? 'chrome' : process.env.PV_CHANNEL;
  const b = await chromium.launch({ channel: channel || undefined, args: ['--disable-gpu-vsync', '--force-color-profile=srgb'] });
  let failed = false;
  const open = async () => {
    const ctx = await b.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: DPR }), pg = await ctx.newPage();
    pg.on('pageerror', e => { failed = true; console.log('PAGE ERROR:', e.message); });
    pg.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) console.log('console.error:', m.text()); });
    pg.on('response', r => { if (r.status() >= 400 && !r.url().endsWith('favicon.ico')) { failed = true; console.log(`HTTP ${r.status()} (missing file?): ${r.url()}`); } });
    await pg.goto(url);
    try { await pg.waitForFunction(() => window.__ready === true, null, { timeout: 60000 }); }
    catch (e) { console.error('Scene never set window.__ready - check the console errors above (missing file, JS error, or PV.ready() not called).'); await b.close(); srv.close(); process.exit(1); }
    return pg;
  };
  if (arg('events')) {
    fs.mkdirSync(OUT, { recursive: true }); const pg = await open();
    const ev = await pg.evaluate(() => window.__events || {});
    fs.writeFileSync(OUT + '/events.json', JSON.stringify(ev, null, 1)); console.log(`events: ${Object.keys(ev).join(', ') || '(none published)'} -> ${path.relative(REPO, OUT)}/events.json`);
  } else if (arg('stills')) {
    fs.mkdirSync(OUT + '/stills', { recursive: true }); const pg = await open();
    for (const t of String(arg('stills')).split(',').map(Number)) { await pg.evaluate(t => window.seek(t), t); await pg.screenshot({ path: `${OUT}/stills/t${t.toFixed(2)}.png` }); console.log('still', t); }
  } else {
    const N = Math.round(FPS * DUR), total = N * S, workers = Number(arg('workers')) || Math.max(2, Math.min(6, os.cpus().length - 2));
    if (!arg('keep')) fs.rmSync(OUT + '/frames', { recursive: true, force: true }); fs.mkdirSync(OUT + '/frames', { recursive: true });
    const only = arg('only') ? String(arg('only')).split('-').map(Number) : null;
    const todo = []; for (let f = 0; f < N; f++) { if (only && (f < only[0] || f > only[1])) continue; for (let s = 0; s < S; s++) todo.push([f, s]); }
    let next = 0, done = 0; const t0 = Date.now();
    const run = async () => {
      const pg = await open();
      for (;;) {
        const i = next++; if (i >= todo.length) break; const [f, s] = todo[i], off = S === 1 ? 0 : (s / (S - 1) - 0.5) * SHUTTER, t = Math.max(0, Math.min(DUR, (f + off) / FPS));
        await pg.evaluate(t => window.seek(t), t);
        await pg.screenshot({ path: `${OUT}/frames/${String(f * S + s).padStart(6, '0')}.jpg`, type: 'jpeg', quality: 95 });
        if (++done % 200 === 0) console.log(`${done}/${todo.length}  ${Math.round((Date.now() - t0) / 1000)}s`);
      }
    };
    await Promise.all(Array.from({ length: workers }, run)); console.log(`frames done: ${todo.length} in ${Math.round((Date.now() - t0) / 1000)}s -> ${path.relative(REPO, OUT)}/frames`);
  }
  await b.close(); srv.close(); if (failed) { console.error('Finished with errors (see above).'); process.exit(1); }
})();
