#!/usr/bin/env python3
"""lib/lush.py + tools/key-check.py: instruments are finite / click-free / deterministic / in tune, harmony helpers stay in key, pump ducks, groove anchor, and key-check can tell an in-key
chord from one with a wrong note and an in-tune chord from a flat one."""
import importlib.util, os, subprocess, sys, tempfile, wave
import numpy as np
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, os.path.join(REPO, 'lib'))
import synth as S, sonic as SN, groove as G, lush as LU

SR = S.SR
S.init(4.0, seed=5)


def peak_hz(x, lo=30, hi=4000):
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x)), 1 << 18)); fr = np.fft.rfftfreq(1 << 18, 1 / SR); m = (fr > lo) & (fr < hi); return fr[m][np.argmax(sp[m])]


def cents(f, ref): return 1200 * np.log2(f / ref)


# every instrument: finite, bounded, ends silent (no click), deterministic for the same rng
r = lambda: np.random.default_rng(11)
makers = {'pad': lambda: LU.pad([57, 61, 64], 3.0, 0.2, r()), 'keys': lambda: LU.keys(69, 1.5, 0.2, r()), 'stab': lambda: LU.stab([57, 61, 64], 0.3, 0.2, r()), 'sub': lambda: LU.sub(33, 1.0, 0.3),
          'kick': lambda: LU.kick(0.8, 55, r()), 'shaker': lambda: LU.shaker(0.2, r()), 'clap': lambda: LU.clap(0.3, r()), 'impact': lambda: LU.impact(3.0, 0.6, 33, r()), 'air': lambda: LU.air(1.5, 0.3, True, r())}
for k, f in makers.items():
    x = f(); assert np.isfinite(x).all() and len(x) > 100, k
    assert 0.5 * {'pad': .2, 'keys': .2, 'stab': .2, 'sub': .3, 'kick': .8, 'shaker': .2, 'clap': .3, 'impact': .6, 'air': .3}[k] <= np.abs(x).max() <= 1.2 * {'pad': .2, 'keys': .2, 'stab': .2, 'sub': .3, 'kick': .8, 'shaker': .2, 'clap': .3, 'impact': .6, 'air': .3}[k] + 1e-9, (k, np.abs(x).max())
    assert abs(x[0]) < 0.01 and abs(x[-1]) < 0.01, (k, 'click at the ends')
    assert np.array_equal(x, f()), (k, 'not deterministic')

# in tune: the pad's strongest partial, the kick's body and the sub sit on the pitch they were given (A3 = 220 Hz, A1 = 55 Hz)
assert abs(cents(peak_hz(LU.pad([57], 3.0, 0.2, r(), attack=0.3), 100, 400), 220.0)) < 12
assert abs(cents(peak_hz(LU.keys(69, 1.5, 0.2, r()), 200, 1000), 440.0)) < 8
assert abs(cents(peak_hz(LU.sub(33, 1.0, 0.3), 30, 80), 55.0)) < 5
assert abs(cents(peak_hz(LU.kick(0.8, 55, r())[int(0.08 * SR):], 30, 120), 55.0)) < 20
# keys are harmonic (no mallet-style inharmonic partial): energy near 2.76 x and 4 x the fundamental is small next to the integer harmonics
k = LU.keys(57, 2.0, 0.2, r()); sp = np.abs(np.fft.rfft(k * np.hanning(len(k)), 1 << 17)); fr = np.fft.rfftfreq(1 << 17, 1 / SR); band = lambda f: sp[(fr > f * 0.97) & (fr < f * 1.03)].max()
assert band(220 * 2.76) < 0.12 * band(220) and band(220 * 3) > 0.03 * band(220)

# harmony: chords are in the key, voice_lead keeps pitch classes and moves little
A = LU.chord(57, 'ionian', 0); assert A == [57, 61, 64] and LU.chord(57, 'ionian', 5) == [66, 69, 73] and LU.chord(57, 'ionian', 0, 3, add=(8,)) == [57, 61, 64, 71]
scale = {(9 + s) % 12 for s in SN.MODES['ionian']}
for deg in range(7): assert all(n % 12 in scale for n in LU.chord(57, 'ionian', deg, 4)), deg
prev = LU.voice_lead(None, A); assert all(52 <= n <= 79 for n in prev) and sorted(n % 12 for n in prev) == sorted(n % 12 for n in A)
nxt = LU.voice_lead(prev, LU.chord(57, 'ionian', 4)); assert {n % 12 for n in nxt} == {n % 12 for n in LU.chord(57, 'ionian', 4)} and max(abs(a - b) for a, b in zip(prev, nxt)) <= 7, (prev, nxt)
assert LU.quantize(70, 9, 'ionian') in (69, 71) and LU.quantize(66.4, 9, 'ionian') == 66 and LU.quantize(61, 9, 'ionian') == 61

# pump: gain dips at a hit and recovers; untouched far from hits; no hits = identity
x = np.ones(SR * 2); y = LU.pump(x, 10.0, [10.5, 11.5], depth=0.6, release=0.3)
assert y[int(0.49 * SR)] > 0.99 and y[int(0.52 * SR)] < 0.6 and y[int(0.95 * SR)] > 0.97 and y[int(1.2 * SR)] > 0.99 and np.array_equal(LU.pump(x, 0, []), x)

# add_wide: two takes, left and right, different but reproducible
S.init(4.0, seed=5); LU.add_wide(lambda g: LU.pad([57, 64], 1.0, 0.2, g), 0.5, rng=np.random.default_rng(1)); assert len(S.EVENTS) == 2 and np.abs(S.L).max() > 0 and np.abs(S.R).max() > 0

# groove anchor: a pattern starts where the section starts, not on the global bar line
g = G.Grid(120); S.init(4.0, seed=5); seen = []
G.play(g, 'x...', lambda v: (seen.append(1), np.ones(10) * 0.1)[1], 2, 14, anchor=True); ts = [e['t'] for e in S.EVENTS]; assert ts == [0.25, 0.75, 1.25], ts
S.init(4.0, seed=5); G.play(g, 'x...', lambda v: np.ones(10) * 0.1, 2, 14); ts = [e['t'] for e in S.EVENTS]; assert ts == [0.5, 1.0, 1.5], ts

# tools/key-check.py: separates in-key from wrong-note, in-tune from flat
spec = importlib.util.spec_from_file_location('keycheck', os.path.join(REPO, 'tools', 'key-check.py')); KC = importlib.util.module_from_spec(spec); spec.loader.exec_module(KC)
t = np.arange(SR * 3) / SR; sine = lambda m, off=0.0: np.sin(2 * np.pi * 440 * 2 ** ((m + off - 69) / 12) * t)
pcs = KC.scale_pcs('A', 'ionian'); assert pcs == {9, 11, 1, 2, 4, 6, 8}
good = sum(sine(m) for m in (57, 61, 64, 69)) / 4; wrong = good + 0.8 * sine(58); flat = sum(sine(m, -0.4) for m in (57, 61, 64, 69)) / 4
sg, sw, sf = (KC.tonal_peaks(x, SR, pcs) for x in (good, wrong, flat))
assert sg['off'] / sg['w'] < 0.02 and sg['bad'] / sg['w'] < 0.02 and abs(sg['cents'] / sg['w']) < 8, sg
assert sw['off'] / sw['w'] > 0.25, sw                                       # the A# (a note outside A major) is a big share of the energy
assert sf['bad'] / sf['w'] > 0.9 and sf['cents'] / sf['w'] < -30, sf          # 40 cents flat: every tone is out of tune and the mean offset is negative
bd = KC.bands(sine(33) + sine(57), SR); assert bd[0] > 40 and bd[2] < 60
# CLI: a wav in, a table out, --fail-off gates
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, 's.wav')
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((wrong * 0.3 * 32767).astype('<i2').tobytes())
    o = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'key-check.py'), p, '--key', 'A', '--mode', 'ionian', '--window', '3'], capture_output=True, text=True); assert o.returncode == 0 and 'ALL' in o.stdout, o.stdout + o.stderr
    o = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'key-check.py'), p, '--key', 'A', '--mode', 'ionian', '--fail-off', '0.1'], capture_output=True, text=True); assert o.returncode == 1 and 'FAIL' in o.stdout, o.stdout
    o = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'key-check.py'), '-h'], capture_output=True, text=True); assert o.returncode == 0 and 'key-check' in o.stdout
print('test_lush: ok')
