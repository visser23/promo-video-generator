#!/usr/bin/env node
/* safe-area.js - check that visible text stays inside the crop-safe area (and measure how small it is), at any moments you choose.

   node tools/safe-area.js <project> [--times 2,5.5,12] [--every 0.5] [--min-font 24] [--ignore ".app *"]
   Reads cues.json:  "safe": {"x": 72, "y": 130, "w": 936, "h": 1090}  (defaults: 6% margin).  For each time it calls seek(t), walks every element that directly
   contains text, skips anything effectively invisible (display none, visibility hidden, opacity < 0.5 along the ancestor chain, off-screen entirely) and reports
     OUTSIDE  text whose box crosses the safe area (with the distance in px)     SMALL  text rendered smaller than --min-font px (after CSS transforms)
   Exit code 1 if anything is reported, so it can sit in a check script.  Numbers, not eyeballing: a viewer on a phone cannot zoom. */
const { chromium } = require('playwright-core');
const http = require('http'), fs = require('fs'), path = require('path');
const REPO = path.join(__dirname, '..');
const arg = (n, d) => { const i = process.argv.indexOf('--' + n); return i < 0 ? d : (process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[i + 1] : true); };
const MIME = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.json': 'application/json', '.webp': 'image/webp' };
const proj = path.resolve(process.argv[2] || ''); if (!fs.existsSync(path.join(proj, 'index.html'))) { console.log('usage: node tools/safe-area.js <project> [--times a,b] [--every s] [--min-font px]'); process.exit(2); }
const C = JSON.parse(fs.readFileSync(path.join(proj, 'cues.json'), 'utf8')), W = C.width || 1920, H = C.height || 1080;
const safe = C.safe || { x: Math.round(W * 0.06), y: Math.round(H * 0.06), w: Math.round(W * 0.88), h: Math.round(H * 0.88) };
const minFont = Number(arg('min-font', 0)), every = Number(arg('every', 0));
let times = arg('times', null) ? String(arg('times')).split(',').map(Number) : [];
if (every) for (let t = 0; t <= C.duration; t += every) times.push(+t.toFixed(3));
if (!times.length) times = [0, C.duration / 2, C.duration - 0.1];

(async () => {
  const srv = http.createServer((q, r) => { const p = path.join(REPO, decodeURIComponent(q.url.split('?')[0])); fs.readFile(p, (e, d) => { if (e) { r.statusCode = 404; r.end(); } else { r.setHeader('content-type', MIME[path.extname(p)] || 'application/octet-stream'); r.end(d); } }); }).listen(0, '127.0.0.1');
  await new Promise(r => srv.on('listening', r));
  const b = await chromium.launch({ channel: process.env.PV_CHANNEL === undefined ? 'chrome' : process.env.PV_CHANNEL || undefined });
  const pg = await (await b.newContext({ viewport: { width: W, height: H } })).newPage();
  await pg.goto(`http://127.0.0.1:${srv.address().port}/${path.relative(REPO, proj).split(path.sep).join('/')}/index.html`);
  await pg.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
  let bad = 0;
  for (const t of times) {
    const hits = await pg.evaluate(([t, safe, W, H]) => {
      window.seek(t); const out = [];
      const walker = document.createTreeWalker(document.getElementById('v'), NodeFilter.SHOW_TEXT);
      for (let n; (n = walker.nextNode());) {
        const txt = n.textContent.trim(); if (!txt) continue; const el = n.parentElement; let o = 1, hidden = false;
        for (let e = el; e && e.id !== 'v'; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') { hidden = true; break; } o *= parseFloat(cs.opacity); }
        if (hidden || o < 0.5) continue;
        const rg = document.createRange(); rg.selectNodeContents(n); const r = rg.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue;
        if (r.right < 0 || r.left > W || r.bottom < 0 || r.top > H) continue;                         // entirely off-screen: not visible
        const cs = getComputedStyle(el); const m = new DOMMatrix(getComputedStyle(el).transform === 'none' ? undefined : getComputedStyle(el).transform);
        let scale = 1; for (let e = el; e && e.id !== 'v'; e = e.parentElement) { const tr = getComputedStyle(e).transform; if (tr && tr !== 'none') scale *= Math.sqrt(Math.abs(new DOMMatrix(tr).a * new DOMMatrix(tr).d) || 1); }
        out.push({ txt: txt.slice(0, 40), l: r.left, t: r.top, r: r.right, b: r.bottom, font: parseFloat(cs.fontSize) * scale });
      }
      return out;
    }, [t, safe, W, H]);
    for (const h of hits) {
      const dx = Math.max(safe.x - h.l, h.r - (safe.x + safe.w), 0), dy = Math.max(safe.y - h.t, h.b - (safe.y + safe.h), 0);
      if (dx > 1 || dy > 1) { bad++; console.log(`t=${t.toFixed(2)} OUTSIDE by ${Math.max(dx, dy).toFixed(0)}px: "${h.txt}" [${h.l.toFixed(0)},${h.t.toFixed(0)} - ${h.r.toFixed(0)},${h.b.toFixed(0)}]`); }
      if (minFont && h.font < minFont) { bad++; console.log(`t=${t.toFixed(2)} SMALL ${h.font.toFixed(1)}px: "${h.txt}"`); }
    }
  }
  console.log(bad ? `${bad} issue(s) over ${times.length} moments (safe area x ${safe.x}..${safe.x + safe.w}, y ${safe.y}..${safe.y + safe.h})` : `ok: all visible text inside the safe area at ${times.length} moments (x ${safe.x}..${safe.x + safe.w}, y ${safe.y}..${safe.y + safe.h})`);
  await b.close(); srv.close(); process.exit(bad ? 1 : 0);
})();
