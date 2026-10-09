#!/usr/bin/env python3
"""lib/sonic.py: palettes are deterministic per seed but differ between seeds/episodes; every instrument is finite, the right length/level and click-free;
repeated calls are never identical; rooms are long enough for master(); synth.add() logs fingerprints that tools/sound-report.py can compare."""
import os, sys, json, subprocess, tempfile
import numpy as np
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, os.path.join(REPO, 'lib')); sys.path.insert(0, os.path.join(REPO, 'tools'))
import synth as S, sonic as SN
SR = S.SR; R = lambda: np.random.default_rng(5)

# seeds
assert SN.seed_of('a', 1) == SN.seed_of('a', 1) and SN.seed_of('a', 1) != SN.seed_of('a', 2) and 0 <= SN.seed_of('x') < 2 ** 31

# every instrument: finite, expected duration, peak ~ vol, no click at either end
inst = {
    'strings': (lambda: SN.strings([45, 52, 57], 2.0, 0.3, 0.8, R()), 2.0), 'choir': (lambda: SN.choir([45, 52], 2.0, 0.3, 'o', 0.8, R()), 2.0), 'bowed': (lambda: SN.bowed(40, 1.5, 0.3, R()), 1.5),
    'organ': (lambda: SN.organ([45, 52], 1.5, 0.3, R()), 1.5), 'glass': (lambda: SN.glass([57], 2.0, 0.3, R()), 2.0), 'drone': (lambda: SN.drone(33, 3.0, 0.3, R()), 3.0),
    'ks': (lambda: SN.ks(52, 1.0, 0.5, R()), 1.0), 'fm_bell': (lambda: SN.fm_bell(76, 1.0, 0.5, R()), 1.0), 'epiano': (lambda: SN.epiano(60, 1.0, 0.5, R()), 1.0),
    'frame_drum': (lambda: SN.frame_drum(0.6, R()), 0.7), 'taiko': (lambda: SN.taiko(0.7, R()), 1.6), 'gong': (lambda: SN.gong(2.0, 0.5, R()), 2.0), 'anvil': (lambda: SN.anvil(0.5, R()), 1.2),
    'stamp': (lambda: SN.stamp(0.8, R()), 0.55), 'wood_knock': (lambda: SN.wood_knock(0.4, R()), 0.18), 'sub_drop': (lambda: SN.sub_drop(1.0, 0.6), 1.0),
    'typewriter_key': (lambda: SN.typewriter_key(0.4, R()), 0.09), 'typewriter_return': (lambda: SN.typewriter_return(0.5, R()), 0.9), 'paper_slide': (lambda: SN.paper(0.4, 'slide', 0.4, R()), 0.4),
    'paper_rustle': (lambda: SN.paper(0.6, 'rustle', 0.4, R()), 0.6), 'paper_turn': (lambda: SN.paper(0.5, 'turn', 0.4, R()), 0.5), 'pen': (lambda: SN.pen_scratch(0.8, 0.3, R()), 0.8),
    'shutter': (lambda: SN.camera_shutter(0.4, R()), 0.16), 'glass_shatter': (lambda: SN.glass_shatter(0.5, R()), 0.9), 'skid': (lambda: SN.skid(1.6, 0.4, R()), 1.6), 'sonar': (lambda: SN.sonar_ping(0.3, R()), 2.0), 'geiger': (lambda: SN.geiger(2.0, (5, 30), 0.4, R()), 2.0), 'static': (lambda: SN.static(2.0, 0.3, R()), 2.0),
    'clock': (lambda: SN.clock(2.0, 60, 0.3, R()), 2.0), 'projector': (lambda: SN.projector(2.0, 0.3, R()), 2.0), 'hiss': (lambda: SN.tape_hiss(1.0, 0.1, R()), 1.0), 'wind': (lambda: SN.wind(3.0, 0.3, R()), 3.0),
    'prop': (lambda: SN.prop_drone(2.0, 0.3, 2400, 3, R()), 2.0), 'rumble': (lambda: SN.rumble(2.0, 0.3, R()), 2.0), 'shepard': (lambda: SN.shepard(2.0, 0.3, True), 2.0), 'pitch_riser': (lambda: SN.pitch_riser(2.0, 0.4, R()), 2.0)}
for mat in ('wood', 'glass', 'metal', 'musicbox', 'vibes'): inst['mallet_' + mat] = ((lambda m=mat: SN.mallet(72, 1.0, 0.5, m, R())), 1.0)
for k, (f, d) in inst.items():
    x = f(); assert np.all(np.isfinite(x)) and abs(len(x) / SR - d) < 0.02, (k, len(x) / SR, d)
    pk = np.abs(x).max(); assert 0.05 < pk < 1.05, (k, pk)
    assert abs(x[0]) < 0.03 * pk + 1e-9 and abs(x[-1]) < 0.03 * pk + 1e-9, (k, 'click at an end', abs(x[0]) / pk, abs(x[-1]) / pk)
    assert np.array_equal(f(), x), (k, 'same generator seed must give the same sound')
assert abs(len(SN.morse('e', 20, 640, 0.2)) / SR - (1.2 / 20 * (1 + 1 + 2 + 4) + 0.05)) < 0.02, 'morse timing: dit + gaps'
# geiger: Poisson clicks at the requested rate
x = SN.geiger(10, 20, 0.5, np.random.default_rng(1)); idx = np.nonzero(np.abs(x) > 0.3 * np.abs(x).max())[0]; n = 1 + int((np.diff(idx) > 0.005 * SR).sum()); assert 120 < n < 280, ('geiger ~20 clicks/s over 10 s', n)

# palettes: determinism, variation, rotation
P1, P2 = SN.Palette(SN.seed_of('a'), 'grave'), SN.Palette(SN.seed_of('a'), 'grave')
assert repr(P1) == repr(P2) and np.array_equal(P1.stamp if False else P1.hit(0.5), P2.hit(0.5)), 'same seed = same palette = same first hit'
a, b = P1.hit(0.5), P1.hit(0.5); assert not (len(a) == len(b) and np.array_equal(a, b)), 'the second hit differs from the first'
assert repr(SN.Palette(SN.seed_of('a'), 'grave')) != repr(SN.Palette(SN.seed_of('b'), 'eerie'))
for mood in SN.MOODS:
    for ep in range(1, 13):
        v1, v2 = SN.Palette(7, mood, episode=ep).voice, SN.Palette(7, mood, episode=ep + 1).voice
        for role in v1: assert v1[role] != v2[role], ('consecutive episodes share the %s in role %s' % (v1[role], role), mood, ep)
for mood, m in SN.MOODS.items():
    P = SN.Palette(3, mood); assert P.mode in SN.MODES and all(k in P.voice for k in ('pad', 'bell', 'pulse', 'hit'))
    sc = {(P.root + i) % 12 for i in SN.MODES[P.mode]}; assert all(n % 12 in sc for n in P.chord(2, 4)), 'chords stay in the mode'
    for kind in ('pad', 'bell', 'hit', 'pulse', 'bass'):
        y = {'pad': lambda: P.pad([45, 52], 1.0), 'bell': lambda: P.bell(72), 'hit': lambda: P.hit(0.5), 'pulse': lambda: P.pulse(0.4), 'bass': lambda: P.bass(33, 1.0)}[kind](); assert np.all(np.isfinite(y)) and np.abs(y).max() > 0.01, (mood, kind)

# rooms and bed
for kind in SN._ROOMS:
    ir = SN.room(kind, 3); assert ir.shape[0] == 2 and ir.shape[1] >= int(1.3 * SR) and np.all(np.isfinite(ir)), kind
    assert np.array_equal(ir, SN.room(kind, 3)) and not np.array_equal(ir, SN.room(kind, 4)), kind
assert not np.array_equal(SN.room('hall', 1)[:, :4000], SN.room('tin', 1)[:, :4000])
S.init(20.0, seed=3); P = SN.Palette(3, 'warm'); P.bed(0, 20, 0.6); assert 5 <= len(S.EVENTS) < 80 and max(e['t'] for e in S.EVENTS) < 20, len(S.EVENTS)

# bass never goes below A1 (55 Hz): a bass at MIDI 19 (25 Hz) is energy without pitch, so it folds up by octaves (19 -> 43), notes at/above 33 are untouched
S.init(4.0, seed=3); bs = lambda m: SN.Palette(3, 'grave', root=31, mode='aeolian').bass(m, 2.0, 0.3)       # a new palette each time: P.rng() advances per call by design
assert np.allclose(bs(19), bs(43)) and np.allclose(bs(33), bs(33)) and np.allclose(bs(21), bs(33)) and not np.allclose(bs(33), bs(45)), 'bass folds up to >= MIDI 33'

# event log: fingerprints are level independent, master() writes score.events.json, ROOM is honoured, sound-report reads it
S.init(4.0, seed=1); x = SN.mallet(72, 1.0, 0.5, 'glass', R()); S.add(x, 0.5, 1.0, name='a'); S.add(x * 0.2, 2.0, 1.0, name='quiet'); S.add(SN.gong(2.0, 0.5, R()), 2.5, name='gong')
fa, fq, fg = [e['fp'] for e in S.EVENTS]; assert abs(np.dot(fa, fq) - 1) < 1e-3 and np.dot(fa, fg) < 0.97, 'same timbre at a different level = same fingerprint; different timbre = different'
S.ROOM = SN.room('tin', 2)
with tempfile.TemporaryDirectory() as t:
    p = os.path.join(t, 'score.wav'); S.master(p, body=(0.3, 3.5)); ev = os.path.join(t, 'score.events.json'); assert os.path.exists(ev) and len(json.load(open(ev))['events']) == 3
    import importlib.util; spec = importlib.util.spec_from_file_location('sr', os.path.join(REPO, 'tools', 'sound-report.py')); SR_ = importlib.util.module_from_spec(spec); spec.loader.exec_module(SR_)
    E = SR_.load_events(ev); assert len(E) == 3 and abs(SR_.twin_ratio(E, 0.98) - 2 / 3) < 1e-9 and len(SR_.clusters(E, 0.98)) == 2, 'a + the same sound 14 dB quieter are twins; the gong is not'
    assert SR_.shared_ratio(E, E, 0.98) == 1.0 and SR_.shared_ratio(E[2:], E[:2], 0.98) == 0.0
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'sound-report.py'), ev, ev, '--fail-above', '0.5'], capture_output=True, text=True); assert r.returncode == 1 and 'FAIL' in r.stdout, r.stdout
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'sound-report.py'), ev, ev, '--fail-above', '1.0'], capture_output=True, text=True); assert r.returncode == 0, r.stdout
S.ROOM = None
print('ok')
