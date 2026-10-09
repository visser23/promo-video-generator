#!/usr/bin/env node
/* thumb.js - render a project's thumbnail(s) from projects/<name>/thumb.html.

     node tools/thumb.js projects/<name> [--only vertical|wide] [--no-safe-check]
       -> out/<name>/thumb-9x16.jpg   2160x3840  (1080x1920 at 2x) - what a Short's custom thumbnail wants (set in YouTube Studio on desktop; the Shorts feed itself plays the video)
          out/<name>/thumb-16x9.jpg   2560x1440  (1280x720 at 2x)  - for the watch page / search / embeds, where a Short may be shown as a landscape card
   Both are JPEGs at the highest quality that fits under YouTube's 2 MB limit.

   thumb.html is a normal page (bundled fonts, local images, no network).  It is opened as thumb.html?v=vertical or thumb.html?v=wide and must call `window.__ready = true`
   once fonts/images are loaded.  Mark the things that MUST survive cropping with a `data-key` attribute (the headline, the face): in the vertical variant they must sit inside the
   safe rectangle - clear of the top ~220 px (status bar / search), the bottom ~380 px (title, channel, buttons) and the right ~160 px (like/comment/share column) - or the run fails (exit 1)
   unless you pass --no-safe-check.  Override the rectangle with "thumbSafe": {x,y,w,h} in cues.json.  Wide variant: inside 60 px of every edge and clear of the bottom-right timestamp badge. */
const fs = require('fs'), path = require('path'), http = require('http');
const { chromium } = require('playwright-core');
const REPO = path.join(__dirname, '..');
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2', '.svg': 'image/svg+xml' };
const arg = n => process.argv.includes('--' + n), val = n => { const i = process.argv.indexOf('--' + n); return i > 0 ? process.argv[i + 1] : null; };
const projectArg = process.argv[2];
if (!projectArg || projectArg.startsWith('--')) { console.log('usage: node tools/thumb.js <project-dir> [--only vertical|wide] [--no-safe-check]'); process.exit(2); }
const PROJECT = path.resolve(projectArg), NAME = path.basename(PROJECT), OUT = path.join(REPO, 'out', NAME);
if (!PROJECT.startsWith(REPO + path.sep)) { console.error('The project folder must live inside this repo (so ../../lib resolves). Try projects/<name>.'); process.exit(2); }
if (!fs.existsSync(path.join(PROJECT, 'thumb.html'))) { console.error('No thumb.html in ' + PROJECT); process.exit(2); }
const cues = fs.existsSync(path.join(PROJECT, 'cues.json')) ? JSON.parse(fs.readFileSync(path.join(PROJECT, 'cues.json'), 'utf8')) : {};
const MAX = 2000000;
const VARIANTS = {
  vertical: { w: 1080, h: 1920, dpr: 2, file: 'thumb-9x16.jpg', safe: cues.thumbSafe || { x: 40, y: 220, w: 880, h: 1320 } },
  wide: { w: 1280, h: 720, dpr: 2, file: 'thumb-16x9.jpg', safe: { x: 60, y: 60, w: 1160, h: 540 } }
};

(async () => {
  const only = val('only'); if (only && !VARIANTS[only]) { console.error('--only is vertical or wide'); process.exit(2); }
  const srv = http.createServer((q, r) => {
    const p = path.join(REPO, decodeURIComponent(q.url.split('?')[0])); if (!p.startsWith(REPO)) { r.statusCode = 403; return r.end(); }
    fs.readFile(p, (e, d) => { if (e) { r.statusCode = 404; r.end(); } else { r.setHeader('content-type', MIME[path.extname(p)] || 'application/octet-stream'); r.end(d); } });
  }).listen(0, '127.0.0.1');
  await new Promise(r => srv.on('listening', r));
  const base = `http://127.0.0.1:${srv.address().port}/${path.relative(REPO, PROJECT).split(path.sep).join('/')}/thumb.html`;
  const channel = process.env.PV_CHANNEL === undefined ? 'chrome' : process.env.PV_CHANNEL;
  const b = await chromium.launch({ channel: channel || undefined, args: ['--force-color-profile=srgb'] });
  fs.mkdirSync(OUT, { recursive: true }); let failed = false;
  for (const [name, v] of Object.entries(VARIANTS)) {
    if (only && only !== name) continue;
    const ctx = await b.newContext({ viewport: { width: v.w, height: v.h }, deviceScaleFactor: v.dpr }), pg = await ctx.newPage();
    pg.on('pageerror', e => { failed = true; console.log('PAGE ERROR:', e.message); });
    pg.on('response', r => { if (r.status() >= 400 && !r.url().endsWith('favicon.ico')) { failed = true; console.log(`HTTP ${r.status()} (missing file?): ${r.url()}`); } });
    await pg.goto(base + '?v=' + name);
    try { await pg.waitForFunction(() => window.__ready === true, null, { timeout: 30000 }); } catch (e) { console.error('thumb.html never set window.__ready = true'); await b.close(); srv.close(); process.exit(1); }
    if (!arg('no-safe-check')) {
      const rects = await pg.evaluate(() => [...document.querySelectorAll('[data-key]')].map(e => { const r = e.getBoundingClientRect(); return { t: (e.textContent || e.tagName).trim().slice(0, 30), x: r.left, y: r.top, r: r.right, b: r.bottom }; }));
      const s = v.safe; if (!rects.length) console.log(`(${name}: no [data-key] elements, so nothing to check against the safe area)`);
      for (const r of rects) { const out = Math.max(s.x - r.x, r.r - (s.x + s.w), s.y - r.y, r.b - (s.y + s.h)); if (out > 1) { failed = true; console.log(`${name}: OUTSIDE the safe area by ${Math.round(out)}px: "${r.t}" [${Math.round(r.x)},${Math.round(r.y)} - ${Math.round(r.r)},${Math.round(r.b)}]  (safe x ${s.x}..${s.x + s.w}, y ${s.y}..${s.y + s.h})`); } }
    }
    let q = 94, buf; for (; q >= 50; q -= 4) { buf = await pg.screenshot({ type: 'jpeg', quality: q }); if (buf.length <= MAX * 0.97) break; }
    if (buf.length > MAX) { failed = true; console.log(`${name}: still ${buf.length} bytes at quality ${q}: simplify the image (less grain/noise)`); }
    fs.writeFileSync(path.join(OUT, v.file), buf); console.log(`${name}: out/${NAME}/${v.file}  ${v.w * v.dpr}x${v.h * v.dpr}  ${(buf.length / 1e6).toFixed(2)} MB  (jpeg quality ${q})`);
    await ctx.close();
  }
  await b.close(); srv.close(); process.exit(failed ? 1 : 0);
})();
