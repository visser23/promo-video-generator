#!/usr/bin/env node
/* freeze.js - tools/freeze-page.js turns a live page into a standalone, script-free, offline-renderable HTML string.
   Serves a tiny page (css with a url() asset, an <img>, a script, an inline handler, an avatar) -> freezes it -> stops the server -> opens the result from disk.  node tests/freeze.js */
const http = require('http'), fs = require('fs'), path = require('path'), assert = require('assert'), os = require('os');
const { chromium } = require('playwright-core');
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==', 'base64');
const PAGE = `<!doctype html><html><head><meta charset=utf-8><link rel=stylesheet href=/s.css><script>window.x=1</script></head>
<body><h1 id=h onclick="alert(1)">Hello</h1><img id=pic src=/p.png width=40 height=40><img alt="User avatar" src=/p.png><div id=bg style="height:50px"></div><script>document.title='live'</script></body></html>`;
const CSS = '#bg{background:url(/p.png) repeat;} h1{color:rgb(1,2,3)}';
let pass = 0; const ok = (n, c) => { assert(c, n); pass++; console.log('PASS', n); };
(async () => {
  const srv = http.createServer((q, r) => { if (q.url === '/') { r.setHeader('content-type', 'text/html'); r.end(PAGE); } else if (q.url === '/s.css') { r.setHeader('content-type', 'text/css'); r.end(CSS); } else if (q.url === '/p.png') { r.setHeader('content-type', 'image/png'); r.end(PNG); } else { r.statusCode = 404; r.end(); } });
  await new Promise(r => srv.listen(0, '127.0.0.1', r)); const url = `http://127.0.0.1:${srv.address().port}/`;
  const ch = process.env.PV_CHANNEL === undefined ? 'chrome' : process.env.PV_CHANNEL || undefined;
  const b = await chromium.launch({ channel: ch }); const p = await b.newPage({ viewport: { width: 400, height: 300 } });
  await p.goto(url); await p.addScriptTag({ path: path.join(__dirname, '..', 'tools', 'freeze-page.js') });
  const html = await p.evaluate(() => __pvFreeze({ scroll: true, settleMs: 20 }));
  await new Promise(r => srv.close(r));                                                  // from here on, no network
  ok('returns a doctype html string', typeof html === 'string' && html.startsWith('<!doctype html>'));
  ok('scripts and inline handlers are gone', !/<script/i.test(html) && !/onclick/i.test(html));
  ok('no stylesheet link left; css inlined', !/rel="?stylesheet/i.test(html) && /rgb\(1, 2, 3\)/.test(html));
  ok('images and css url() assets became data URIs', !/src="\/p\.png"/.test(html) && !/url\("?\/p\.png/.test(html) && (html.match(/data:image\/png;base64/g) || []).length >= 2);
  ok('masked avatar removed', !/User avatar/.test(html));
  const f = path.join(os.tmpdir(), 'pv-freeze-test.html'); fs.writeFileSync(f, html);
  const p2 = await b.newPage({ viewport: { width: 400, height: 300 } }); await p2.goto('file://' + f);
  const r = await p2.evaluate(() => ({ x: typeof window.x, h: getComputedStyle(document.getElementById('h')).color, w: document.getElementById('pic').naturalWidth, bg: getComputedStyle(document.getElementById('bg')).backgroundImage.slice(0, 22) }));
  ok('frozen page renders offline: styled, image decoded, background present, nothing executed', r.h === 'rgb(1, 2, 3)' && r.w === 1 && r.bg.startsWith('url("data:image/png') && r.x === 'undefined');
  await b.close(); fs.rmSync(f, { force: true }); console.log(`\n${pass} passed`);
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
