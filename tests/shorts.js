#!/usr/bin/env node
/* shorts.js - tests for the archival-footage / Shorts tooling:
     .gitignore    models, vendored repos, secrets and big media are ignored; the new tool sources are NOT ignored
     python        tools/footage.py (rights verdicts, provenance), tools/clip.py (cut/scan on a synthetic film), tools/voiceover.py (caption alignment),
                   tools/shorts-meta.py (upload metadata rules), tools/shorts-check.py (spec checks on an mp4)
     lib/captions  phrase grouping (pure)       lib/footage  t -> frame mapping (pure) + real Chrome: out-of-order seeks give identical pixels
   npm test */
const { execSync, spawnSync } = require('child_process'), fs = require('fs'), path = require('path'), assert = require('assert');
const REPO = path.join(__dirname, '..'), P = path.join(REPO, 'projects', '_shortstest'), OUT = path.join(REPO, 'out', '_shortstest');
const run = (cmd, args) => spawnSync(cmd, args, { cwd: REPO, encoding: 'utf8' });
const cleanup = () => { fs.rmSync(P, { recursive: true, force: true }); fs.rmSync(OUT, { recursive: true, force: true }); };
let pass = 0; const ok = (name, fn) => { try { fn(); pass++; console.log('PASS', name); } catch (e) { console.log('FAIL', name, '\n', e.stack || e.message); cleanup(); process.exit(1); } };

ok('.gitignore protects against stray models, vendored repos, secrets and media', () => {
  for (const f of ['vendor/some-repo/a.js', 'third_party/x/y', 'external/z', 'tools/vendor/q', 'models/kokoro.onnx', 'voice.onnx', 'w.safetensors', '.env', '.env.local', 'cookies.txt', 'client_secret_123.json', 'token.json', 'a.mkv', 'a.mp3', 'a.mpeg', 'a.zip', 'projects/x/raw/a.ogv', 'out/x/y.png', 'projects/x/anything']) {
    assert.strictEqual(run('git', ['check-ignore', '-q', f]).status, 0, f + ' should be ignored');
  }
  for (const f of ['tools/footage.py', 'tools/clip.py', 'lib/footage.js', 'lib/captions.js', 'tests/shorts.js', 'docs/SHORTS.md', 'templates/shorts/scene.js', 'tools/thumb.js', 'tools/shorts-meta.py']) {
    assert.strictEqual(run('git', ['check-ignore', '-q', f]).status, 1, f + ' must not be ignored');
  }
});

for (const t of ['test_footage.py', 'test_clip.py', 'test_voiceover.py', 'test_meta.py', 'test_sheet.py', 'test_synth.py', 'test_sonic.py', 'test_groove.py', 'test_lush.py']) {
  if (!fs.existsSync(path.join(__dirname, t))) continue;
  ok('python: ' + t, () => { const r = run('python3', [path.join(__dirname, t)]); assert(/ok\s*$/.test(r.stdout), r.stdout + r.stderr); });
}

ok('captions: phrases break at sentence ends, pauses, silence and size limits', () => {
  const C = require('../lib/captions.js');
  const w = (t, s, e, emph) => ({ t, start: s, end: e, emph: !!emph });
  const w6 = [w('Before', 0, .3), w('the', .3, .4), w('first', .4, .7), w('atomic', .7, 1), w('test,', 1, 1.3), w('scientists', 1.3, 1.8), w('placed', 1.8, 2.1), w('bets.', 2.1, 2.6)];
  const g1 = C.groups([w('Before', 0, .3), w('the', .3, .4), w('first', .4, .7), w('atomic', .7, 1), w('test,', 1, 1.3), w('scientists', 1.3, 1.8), w('placed', 1.8, 2.1), w('bets.', 2.1, 2.6)], { maxWords: 4, maxChars: 22 });
  assert.deepStrictEqual(g1.map(g => g.words.map(x => x.t).join(' ')), ['Before the first', 'atomic test,', 'scientists placed', 'bets.'], 'size limit, then a comma pause, then the sentence end (23 chars > 22, so "bets." wraps)');
  for (const [mw, mc] of [[3, 18], [4, 24], [5, 30], [2, 12]]) {                     // invariants for any limits
    const g = C.groups(w6, { maxWords: mw, maxChars: mc }); assert.deepStrictEqual(g.flatMap(x => x.words.map(y => y.t)), w6.map(y => y.t), 'nothing lost or reordered');
    assert(g.every(x => x.words.length <= mw), 'maxWords respected for ' + mw); assert(g.every(x => x.words.length === 1 || x.words.reduce((n, y) => n + y.t.length + 1, 0) - 1 <= mc), 'maxChars respected for ' + mc);
    assert(g.every((x, i) => i === 0 || x.start >= g[i - 1].end - 1e-9), 'phrases are in time order');
  }
  assert(g1.every(g => g.start === g.words[0].start && g.end === g.words[g.words.length - 1].end), 'phrase times follow their words');
  assert(g1[g1.length - 1].words[g1[g1.length - 1].words.length - 1].t === 'bets.', 'sentence end closes a phrase');
  const flat = g1.flatMap(g => g.words.map(x => x.t)); assert.deepStrictEqual(flat, ['Before', 'the', 'first', 'atomic', 'test,', 'scientists', 'placed', 'bets.'], 'no word lost or reordered');
  const g2 = C.groups([w('one', 0, .2), w('two', 2, 2.2)], { gap: .45 }); assert.strictEqual(g2.length, 2, 'a long silence starts a new phrase');
  assert.strictEqual(C.groups([]).length, 0);
  const g3 = C.groups([w('Almost.', 0, .5), w('The', .6, .8), w('end.', .8, 1.2)]); assert.strictEqual(g3[0].words.length, 1, 'a sentence-final word is not glued to the next sentence');
});

ok('footage: t -> frame mapping (clamp, speed, offset, loop)', () => {
  const F = require('../lib/footage.js'), c = { fps: 24, n: 48 };
  assert.strictEqual(F.frameAt(c, 0), 0); assert.strictEqual(F.frameAt(c, 1), 24); assert.strictEqual(F.frameAt(c, -3), 0, 'before the clip holds the first frame');
  assert.strictEqual(F.frameAt(c, 99), 47, 'after the clip holds the last frame'); assert.strictEqual(F.frameAt(c, 1, { speed: .5 }), 12, 'slow motion');
  assert.strictEqual(F.frameAt(c, 1, { offset: 0.5 }), 36); assert.strictEqual(F.frameAt(c, 2.5, { loop: true }), 12, 'loop wraps'); assert.strictEqual(F.frameAt(c, -0.5, { loop: true }), 36, 'loop wraps backwards');
  assert.strictEqual(F.frameAt(c, 1, { speed: -1, offset: 2 }), 24, 'reverse');
});

cleanup(); fs.mkdirSync(path.join(P, 'raw'), { recursive: true });
fs.writeFileSync(path.join(P, 'cues.json'), JSON.stringify({ fps: 25, duration: 2, subframes: 1, width: 270, height: 480 }));
let browserReady = false;
ok('footage + captions in Chrome: out-of-order seeks give identical pixels, the right frame and the right word', () => {
  assert.strictEqual(run('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=25:duration=2', '-pix_fmt', 'yuv420p', path.join(P, 'raw', 's.mp4')]).status, 0);
  const r = run('python3', ['tools/clip.py', 'cut', 'projects/_shortstest', 'raw/s.mp4', '--id', 'a', '--start', '0', '--end', '2']); assert.strictEqual(r.status, 0, r.stdout + r.stderr);
  const words = [{ t: 'Alpha', start: 0.2, end: 0.6 }, { t: 'Fermi', start: 0.7, end: 1.1, emph: true }, { t: 'bets.', start: 1.2, end: 1.6 }];
  fs.writeFileSync(path.join(P, 'index.html'), `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="../../lib/motion.css">
<style>#v{width:270px;height:480px;background:#000;color:#fff;font:700 30px sans-serif}.cap-g{text-align:center}.cap-w.on{color:#fc0}</style></head>
<body><div id="v"></div><script src="../../lib/motion.js"></script><script src="../../lib/footage.js"></script><script src="../../lib/captions.js"></script><script>
(async () => {
  const world = PV.createWorld(document.getElementById('v'), null, 270, 480);
  const clip = await PV.footage.load('assets/clips/a'); clip.mount(world, 'left:0;top:0;width:270px;height:360px;');
  const cap = PV.captions(${JSON.stringify(words)}, { parent: world, css: 'left:10px;top:380px;width:250px;' });
  window.__clip = clip;
  window.seek = async t => { cap.update(t); clip.at(t, { blend: true }); await PV.footage.settle(); };
  await PV.loaded(); await window.seek(0); PV.ready();
})();</script></body></html>`);
  const still = ts => { const r = run('node', ['tools/render.js', 'projects/_shortstest', '--stills', ts]); assert.strictEqual(r.status, 0, r.stdout + r.stderr); };
  const png = t => fs.readFileSync(path.join(OUT, 'stills', `t${t.toFixed(2)}.png`));
  still('0.5'); const a1 = Buffer.from(png(0.5)); still('1.5,0.8,0.5'); const a2 = png(0.5), b = png(1.5);
  assert(a1.equals(a2), 'the same time must render the same pixels after seeking elsewhere (decode finished before the screenshot)');
  assert(!a1.equals(b), 'a different time shows a different frame');
  const probe = spawnSync('node', ['-e', `
    const { chromium } = require('playwright-core'), http = require('http'), fs = require('fs'), path = require('path');
    const REPO = ${JSON.stringify(REPO)}; const srv = http.createServer((q, r) => { const p = path.join(REPO, decodeURIComponent(q.url.split('?')[0])); fs.readFile(p, (e, d) => { if (e) { r.statusCode = 404; r.end(); } else r.end(d); }); }).listen(0, '127.0.0.1');
    srv.on('listening', async () => {
      const b = await chromium.launch({ channel: process.env.PV_CHANNEL === undefined ? 'chrome' : process.env.PV_CHANNEL || undefined }), pg = await b.newPage({ viewport: { width: 270, height: 480 } });
      await pg.goto('http://127.0.0.1:' + srv.address().port + '/projects/_shortstest/index.html'); await pg.waitForFunction(() => window.__ready === true);
      const out = {};
      await pg.evaluate(() => window.seek(0.81)); out.on = await pg.evaluate(() => [...document.querySelectorAll('.cap-w.on')].map(e => e.textContent));
      out.frameSrc = await pg.evaluate(() => window.__clip.A.src.split('/').pop()); out.decoded = await pg.evaluate(() => window.__clip.A.naturalWidth);
      await pg.evaluate(() => window.seek(0.82)); out.blendOpacity = await pg.evaluate(() => +window.__clip.B.style.opacity);
      await pg.evaluate(() => window.seek(2.0)); out.after = await pg.evaluate(() => [...document.querySelectorAll('.cap-g')].filter(e => e.style.display !== 'none').length);
      console.log(JSON.stringify(out)); await b.close(); srv.close();
    });`], { cwd: REPO, encoding: 'utf8' });
  assert.strictEqual(probe.status, 0, probe.stdout + probe.stderr); const o = JSON.parse(probe.stdout.trim().split('\n').pop());
  assert.deepStrictEqual(o.on, ['Fermi'], 'the current word is highlighted'); assert.strictEqual(o.frameSrc, '00021.jpg', 't=0.81 at 25 fps is frame index 20 -> 00021.jpg'); assert(o.decoded > 0, 'image decoded');
  assert(o.blendOpacity > 0 && o.blendOpacity < 1, 'blend shows a fraction of the next frame: ' + o.blendOpacity); assert.strictEqual(o.after, 0, 'captions vanish after the last word + hold');
});

ok('thumb.js: renders a 9:16 and a 16:9 thumbnail under 2 MB and flags key content outside the safe area', () => {
  const page = (box) => `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0}body{font:700 80px sans-serif;color:#fff;background:linear-gradient(135deg,#c00,#fc0)}
.v{width:1080px;height:1920px}.w{width:1280px;height:720px}#k{position:absolute;${box};background:#000;padding:10px}</style></head>
<body><div id="stage"><div id="k" data-key>THE END</div></div><script>
const v = new URLSearchParams(location.search).get('v'); document.getElementById('stage').className = v === 'wide' ? 'w' : 'v'; window.__ready = true;</script></body></html>`;
  fs.mkdirSync(P, { recursive: true });
  fs.writeFileSync(path.join(P, 'thumb.html'), page('left:200px;top:300px;'));
  let r = run('node', ['tools/thumb.js', 'projects/_shortstest']); assert.strictEqual(r.status, 0, r.stdout + r.stderr);
  const dims = f => { const o = run('ffprobe', ['-v', 'error', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path.join(OUT, f)]).stdout.trim(); return o; };
  assert.strictEqual(dims('thumb-9x16.jpg'), '2160,3840', 'vertical is 2160x3840 (1080x1920 at 2x)'); assert.strictEqual(dims('thumb-16x9.jpg'), '2560,1440', 'wide is 2560x1440 (1280x720 at 2x)');
  for (const f of ['thumb-9x16.jpg', 'thumb-16x9.jpg']) assert(fs.statSync(path.join(OUT, f)).size <= 2000000, f + ' must be at most 2 MB (YouTube limit)');
  fs.writeFileSync(path.join(P, 'thumb.html'), page('left:900px;top:1700px;'));                        // right edge + bottom: under the Shorts buttons and caption
  r = run('node', ['tools/thumb.js', 'projects/_shortstest', '--only', 'vertical']); assert.strictEqual(r.status, 1, 'unsafe key content must fail: ' + r.stdout); assert(/OUTSIDE/.test(r.stdout), r.stdout);
  r = run('node', ['tools/thumb.js', 'projects/_shortstest', '--only', 'vertical', '--no-safe-check']); assert.strictEqual(r.status, 0, '--no-safe-check renders anyway: ' + r.stdout + r.stderr);
});

ok('templates/shorts: scaffolds with new-project.sh and renders with no console/404 errors; unknown templates are refused', () => {
  const name = '_shortstpl', dest = path.join(REPO, 'projects', name), out = path.join(REPO, 'out', name);
  fs.rmSync(dest, { recursive: true, force: true });
  try {
    let r = run('bash', ['tools/new-project.sh', name, 'shorts']); assert.strictEqual(r.status, 0, r.stdout + r.stderr);
    for (const f of ['cues.json', 'index.html', 'scene.js', 'sound.py', 'vo.json', 'meta.json', 'fonts/anton-400.woff2', 'fonts/LICENSES.md']) assert(fs.existsSync(path.join(dest, f)), 'template file ' + f);
    r = run('bash', ['tools/new-project.sh', name, 'nope']); assert.strictEqual(r.status, 2, 'unknown template is a usage error'); assert(/no template 'nope'/.test(r.stdout), r.stdout);
    r = run('node', ['tools/render.js', 'projects/' + name, '--stills', '1,9']); assert(r.status === 0 && !/error|404/i.test(r.stdout + r.stderr), r.stdout + r.stderr);
    const dims = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path.join(out, 'stills', 't1.00.png')], { encoding: 'utf8' }).stdout.trim(); assert.strictEqual(dims, '1080,1920');
  } finally { fs.rmSync(dest, { recursive: true, force: true }); fs.rmSync(out, { recursive: true, force: true }); }
});

cleanup(); console.log(`\n${pass} passed`);
