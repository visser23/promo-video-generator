#!/usr/bin/env python3
"""lib/groove.py: swung grid timing, Euclidean patterns, string patterns (accent / ghost / rest), velocity ramps, deterministic jitter, fills."""
import os, sys
import numpy as np
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, os.path.join(REPO, 'lib'))
import synth as S, groove as G

g = G.Grid(120, swing=0.0)                                     # 120 bpm -> 16th = 0.125 s
assert abs(g.step - 0.125) < 1e-9 and abs(g.time(4) - 0.5) < 1e-9 and g.step_at(0.5) == 4
gs = G.Grid(120, swing=0.2); assert abs(gs.time(1) - (0.125 + 0.025)) < 1e-9 and abs(gs.time(2) - 0.25) < 1e-9      # only odd steps are pushed late
assert abs(G.Grid(120, t0=1.0).time(0) - 1.0) < 1e-9

assert G.euclid(3, 8) == [1, 0, 0, 1, 0, 0, 1, 0] and sum(G.euclid(7, 16)) == 7 and sum(G.euclid(0, 8)) == 0 and sum(G.euclid(9, 8)) == 8
r = G.euclid(3, 8, 1); assert r == [0, 1, 0, 0, 1, 0, 0, 1] and sorted(r) == sorted(G.euclid(3, 8))

# play(): hits land on the right steps, with the right velocities
S.init(4.0, seed=3); seen = []
blip = lambda v: (seen.append(v), np.ones(100) * 0.1)[1]
n = G.play(g, 'x.o.', blip, 0, 16); assert n == 8 and seen[:2] == [1.0, G.GHOST], seen[:4]
ev = [e['t'] for e in S.EVENTS]; assert abs(ev[0] - 0.0) < 1e-3 and abs(ev[1] - 0.25) < 1e-3 and abs(ev[2] - 0.5) < 1e-3, ev[:3]
S.init(4.0, seed=3); seen.clear(); G.play(g, [1, 1], blip, 0, 8, vel=lambda i: i / 8); assert seen == [i / 8 for i in range(1, 8)], seen     # step 0 has velocity 0 -> skipped
S.init(4.0, seed=3); assert G.play(g, '....', blip, 0, 32) == 0 and len(S.EVENTS) == 0

# jitter: bounded, reproducible for the same rng seed, absent without ms
def times(seed, ms):
    S.init(4.0, seed=3); G.play(g, 'x', blip, 0, 16, rng=np.random.default_rng(seed), ms=ms); return [e['t'] for e in S.EVENTS]
a, b, c = times(1, 8), times(1, 8), times(2, 8)
assert a == b and a != c and all(abs(t - round(i * 0.125, 3)) <= 0.0081 for i, t in enumerate(a)), a[:4]
assert times(1, 0) == [round(i * 0.125, 3) for i in range(16)]

# fill: n hits, rising
S.init(4.0, seed=3); seen.clear(); assert G.fill(g, 16, blip, n=4) == 4 and seen == sorted(seen) and seen[-1] == 1.0
print('test_groove: ok')
