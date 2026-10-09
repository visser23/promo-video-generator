"""groove.py - a tiny step sequencer on top of synth.add(): swung grids, Euclidean / string patterns with accents and ghost notes, humanised timing.

WHY: a score built from `for i in range(n): add(kick(), t0 + i*B)` loops sounds like a metronome and takes 30 lines per section.  This gives a groove in one line each,
with the three things that make a loop feel played rather than pasted: swing (late off-16ths), velocity (accents / ghost notes) and micro-timing jitter.

    import synth as S, groove as G
    g = G.Grid(C['bpm'], swing=0.12)                       # 16th-note grid, 12% swing
    G.play(g, 'x...x...x...x..x', lambda v: S.kick(0.8 * v), 0, 64, gain=1, send=0.05)        # 4 bars; x = accent, o = ghost (0.45), . = rest
    G.play(g, G.euclid(7, 16), lambda v: S.hat(0.18 * v), 0, 64, rng=rng, ms=4)               # 7 hits spread evenly over 16 steps
    G.play(g, '....x.......x...', lambda v: S.clap(0.3 * v), 0, 64)                            # backbeat
    t = g.time(37)                                                                            # seconds of 16th step 37 (swing included)

`make(v)` is called with the velocity 0..1 of each hit and returns a mono array (any synth.py / sonic.py instrument).  Nothing here is random unless you pass an `rng`.
"""
import numpy as np
import synth as S

ACCENT, GHOST = 1.0, 0.45


class Grid:
    """steps per beat (default 4 = 16ths), tempo, swing (0 = straight; 0.33 = triplet feel: every odd step is pushed later by swing * step), and a start offset in seconds."""

    def __init__(self, bpm, swing=0.0, per_beat=4, t0=0.0):
        self.bpm, self.swing, self.per_beat, self.t0 = float(bpm), float(swing), int(per_beat), float(t0)
        self.step = 60.0 / self.bpm / self.per_beat

    def time(self, i): return self.t0 + i * self.step + (self.swing * self.step if i % 2 else 0.0)

    def step_at(self, t): return int(round((t - self.t0) / self.step))


def euclid(k, n, rot=0):
    """Euclidean rhythm: k hits spread as evenly as possible over n steps (3,8 = tresillo; 5,8 = cinquillo; 7,16 = a busy hat).  Returns a list of 0/1."""
    k = max(0, min(int(k), int(n))); pat = [1 if (i * k) % n < k else 0 for i in range(n)]
    r = int(rot) % n; return pat[-r:] + pat[:-r] if r else pat


def _vel(c):
    if isinstance(c, str): return {'x': ACCENT, 'X': ACCENT, 'o': GHOST, 'O': GHOST}.get(c, 0.0)
    return float(c)


def play(grid, pattern, make, start, stop, gain=1.0, pan=0.0, send=0.0, rng=None, ms=0.0, vel=None, name=None, anchor=False):
    """place `make(v)` on every active step of `pattern` (a string of x o . , a list of 0/1/velocities; it repeats) for grid steps start..stop-1.
    ms: +/- timing jitter in milliseconds (needs rng).  vel: optional f(step) -> multiplier (build-ups: lambda i: i / 64).  Returns the number of hits placed.
    anchor=True: the pattern starts at `start` (its first character lands on step `start`) instead of being locked to the global bar line - for sections that begin off the bar."""
    n, hits = len(pattern), 0
    for i in range(int(start), int(stop)):
        v = _vel(pattern[(i - int(start)) % n if anchor else i % n])
        if v <= 0: continue
        if vel: v *= float(vel(i))
        if v <= 0: continue
        t = grid.time(i) + ((rng.uniform(-ms, ms) / 1000.0) if (rng is not None and ms) else 0.0)
        S.add(make(min(v, 1.0)), max(0.0, t), gain, pan, send, name=name); hits += 1
    return hits


def fill(grid, step, make, n=4, gain=1.0, pan=0.0, send=0.0, rise=True, name=None):
    """a drum fill: n quick hits on the last steps before `step`, getting louder (rise) - e.g. the bar before a drop."""
    for j in range(n):
        v = (0.45 + 0.55 * (j + 1) / n) if rise else 1.0
        S.add(make(v), max(0.0, grid.time(step - n + j)), gain, pan, send, name=name)
    return n
