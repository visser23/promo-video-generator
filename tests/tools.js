#!/usr/bin/env node
/* tools.js - tests for the tools added for voiceover / portrait / crop-safe work (no TTS model needed):
     lib/synth.py   voice bus: music is ducked while the voice speaks, round-trips through read_wav, no clipping, soft UI sounds are finite
     render.js      --events writes what the scene published in window.__events
     safe-area.js   exits 1 and names text outside the safe area / below the minimum size, exits 0 when everything is fine
     voiceover.py   fails with a clear message (exit 2) when vo.json is missing
   npm test */
const { execSync, spawnSync } = require('child_process'), fs = require('fs'), path = require('path'), assert = require('assert');
const REPO = path.join(__dirname, '..'), P = path.join(REPO, 'projects', '_toolstest'), OUT = path.join(REPO, 'out', '_toolstest');
const sh = c => execSync(c, { cwd: REPO, stdio: ['ignore', 'pipe', 'pipe'] }).toString();
const run = (cmd, args) => spawnSync(cmd, args, { cwd: REPO, encoding: 'utf8' });
const cleanup = () => { fs.rmSync(P, { recursive: true, force: true }); fs.rmSync(OUT, { recursive: true, force: true }); };
let pass = 0; const ok = (name, fn) => { try { fn(); pass++; console.log('PASS', name); } catch (e) { console.log('FAIL', name, '\n', e.message); cleanup(); process.exit(1); } };

cleanup(); fs.mkdirSync(P, { recursive: true });
fs.writeFileSync(path.join(P, 'cues.json'), JSON.stringify({ fps: 25, duration: 1, subframes: 1, width: 400, height: 500, safe: { x: 40, y: 40, w: 320, h: 420 } }));
fs.writeFileSync(path.join(P, 'index.html'), `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="../../lib/motion.css"></head>
<body><div id="v" style="width:400px;height:500px;background:#000;color:#fff;font-family:sans-serif">
<div id="ok" style="position:absolute;left:60px;top:100px;font-size:30px">Inside</div>
<div id="bad" style="position:absolute;left:5px;top:300px;font-size:30px">Outside</div>
<div id="tiny" style="position:absolute;left:60px;top:200px;font-size:10px">Tiny</div></div>
<script src="../../lib/motion.js"></script><script>
window.__events = { demo: { clicks: [0.25, 0.5] } };
window.seek = t => {}; PV.loaded().then(() => PV.ready());</script></body></html>`);

ok('render --events writes window.__events', () => {
  sh('node tools/render.js projects/_toolstest --events'); const e = JSON.parse(fs.readFileSync(path.join(OUT, 'events.json'), 'utf8'));
  assert.deepStrictEqual(e.demo.clicks, [0.25, 0.5]);
});
ok('safe-area reports outside + small text and exits 1', () => {
  const r = run('node', ['tools/safe-area.js', 'projects/_toolstest', '--times', '0.5', '--min-font', '24']); const o = r.stdout;
  assert.strictEqual(r.status, 1, o); assert(/OUTSIDE.*Outside/.test(o), o); assert(/SMALL.*Tiny/.test(o), o); assert(!/OUTSIDE.*Inside/.test(o), o);
});
ok('safe-area exits 0 when the text is fine', () => {
  fs.writeFileSync(path.join(P, 'index.html'), fs.readFileSync(path.join(P, 'index.html'), 'utf8').replace(/<div id="bad".*?<\/div>/, '').replace(/<div id="tiny".*?<\/div>/, ''));
  const r = run('node', ['tools/safe-area.js', 'projects/_toolstest', '--times', '0.5', '--min-font', '24']); assert.strictEqual(r.status, 0, r.stdout);
});
ok('voiceover.py fails clearly without vo.json', () => {
  const r = run('python3', ['tools/voiceover.py', 'projects/_toolstest']); assert.notStrictEqual(r.status, 0); assert(/vo\.json/.test(r.stdout + r.stderr), r.stdout + r.stderr);
});

fs.writeFileSync(path.join(P, 'synthtest.py'), `
import sys, os, numpy as np; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lib'))
from synth import *
import synth as SY
init(4)
for fn, a in ((click, ()), (pop, (72,)), (swish, ()), (thud, ()), (glide, (300, 900, 0.4))):
    x = fn(*a); assert np.all(np.isfinite(x)) and len(x) > 100 and np.max(np.abs(x)) > 0.01, fn.__name__
# a constant music bed for 4 s, a 440 Hz 'voice' between 1 s and 2 s
add(np.sin(2 * np.pi * 220 * tt(4)) * 0.3, 0)
v = np.sin(2 * np.pi * 440 * tt(1)) * 0.3; add_voice(v, 1.0)
out = master(sys.argv[1], body=(0.2, 3.8), duck_db=-10, ceiling=-1.0)
rms = lambda a, b: np.sqrt(np.mean(out[int(a * SR):int(b * SR), 0] ** 2))
# music alone (0.2-0.8 s) vs music under the voice: bass band only, via a low-pass
lowl = lp(out[:, 0], 300, 4); r = lambda a, b: np.sqrt(np.mean(lowl[int(a * SR):int(b * SR)] ** 2))
assert r(1.3, 1.8) < 0.5 * r(0.3, 0.8), ('music was not ducked', r(1.3, 1.8), r(0.3, 0.8))
assert r(3.0, 3.6) > 0.8 * r(0.3, 0.8), 'music did not come back after the voice'
assert np.max(np.abs(out)) < 0.9, 'clipping'
import wave, os
w = wave.open(sys.argv[2], 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes((np.sin(2 * np.pi * 300 * np.arange(11025) / 22050) * 16000).astype('<i2').tobytes()); w.close()
y = read_wav(sys.argv[2]); assert abs(len(y) / SR - 0.5) < 0.01 and 0.4 < np.max(np.abs(y)) < 0.6, 'read_wav resample'
print('ok')
`);
ok('synth voice bus ducks the music, read_wav resamples, UI sounds are finite', () => {
  fs.mkdirSync(OUT, { recursive: true }); const r = run('python3', [path.join(P, 'synthtest.py'), path.join(OUT, 'm.wav'), path.join(OUT, 'v.wav')]);
  assert(/ok\s*$/.test(r.stdout), r.stdout + r.stderr);
});
cleanup(); console.log(`\n${pass} passed`);
