"""lush.py - warm, consonant instruments for product / brand films: soft pads, felt keys, chord stabs, a tuned sub-bass and kick, sidechain 'pump', and key-safe voicing helpers.

WHY: lib/sonic.py's pitched voices (mallets, bells, Karplus-Strong plucks, gongs, sine glides, riser tones) are inharmonic or unpitched on purpose; in a bright product film they read as
'xylophone' and, when two palettes in different modes overlap, as flat or sour notes.  Everything here is HARMONIC (partials at exact integer multiples) and sits on a pitch YOU pass in,
so a whole score can live in one key: build every chord with chord() and voice_lead(), tune the kick and sub to the key (kick(f=55) for A), and use noise (not tones) for risers.
Check the result with tools/key-check.py (off-key share, out-of-tune share, sub-bass share, sounds per second).

    import synth as S, sonic as SN, lush as LU
    ch = LU.chord(57, 'ionian', 0, 3, add=(8,))            # A major add9 from A3: [A3, C#4, E4, B4]
    ch = LU.voice_lead(prev_ch, ch)                        # nearest voicing to the previous chord (smooth, no jumps)
    LU.add_wide(lambda r: LU.pad(ch, 4.0, 0.14, r, attack=1.0), t, send=0.4)        # a pad rendered twice (different phases) left / right
    S.add(LU.pump(LU.pad(ch, 4.0, 0.14, r), t, kick_times), t, ...)                  # duck the pad on every kick
    S.add(LU.keys(76, 1.6, 0.2, r), t); S.add(LU.sub(33, 1.0, 0.3), t); S.add(LU.kick(0.7, f=55), t)

Instruments (mono arrays, peak ~ vol, click-free):  pad(ms,d,vol,rng,attack,release,bright)  keys(m,d,vol,rng,tone)  stab(ms,d,vol,rng,cutoff)  sub(m,d,vol,harm)
  kick(vol,f,rng)  shaker(vol,rng,open_)  clap(vol,rng)  impact(d,vol,m,rng)  air(d,vol,up,rng)
Helpers: chord(root,mode,degree,size,octave,add)  voice_lead(prev,notes,lo,hi)  pump(x,t0,hits,depth,release)  add_wide(make,t,...)  quantize(m,root,mode)
"""
import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d
import synth as S
import sonic as SN

SR = S.SR
TAU = 2 * np.pi
_default = np.random.default_rng(2024)


def _g(r): return r if r is not None else _default


def _norm(x, vol, a=0.002, r=0.01):
    """peak-normalise to vol and fade the ends (no clicks)"""
    x = np.nan_to_num(np.asarray(x, dtype=float)); m = np.max(np.abs(x))
    if m <= 1e-12: return x
    x = x * (vol / m); n = len(x); na = min(n // 2, int(a * SR)); nr = min(n // 2, int(r * SR))
    if na > 1: x[:na] *= np.linspace(0, 1, na)
    if nr > 1: x[-nr:] *= np.linspace(1, 0, nr)
    return x


# ───────────────────────── harmony helpers ─────────────────────────
def chord(root, mode, degree, size=3, octave=0, add=()):
    """MIDI notes of a chord built on scale `degree` of root/mode: stacked thirds (size 3 = triad, 4 = seventh) plus extra scale steps above the chord root in `add` (add=(8,) = the 9th, (3,) = sus4).
    chord(57, 'ionian', 0) = A major [57, 61, 64]; degree 5 = the vi chord (F# minor) - same notes, all in the key."""
    return [SN.scale_note(root, mode, degree + 2 * i) + 12 * octave for i in range(size)] + [SN.scale_note(root, mode, degree + a) + 12 * octave for a in add]


def quantize(m, root, mode):
    """the nearest MIDI note that is in the scale (a glide or a random value, snapped into the key)"""
    pcs = {(root + s) % 12 for s in SN.MODES[mode]}
    cands = [m + d for d in (0, -1, 1, -2, 2) if int(round(m + d)) % 12 in pcs]
    return int(round(min(cands, key=lambda c: abs(c - m))))


def voice_lead(prev, notes, lo=52, hi=79):
    """re-voice `notes` (same pitch classes, any octave) so each tone moves the shortest way from the previous chord, inside lo..hi.  First chord (prev=None): centred in the range."""
    pcs = sorted({int(n) % 12 for n in notes}); mid = (lo + hi) / 2
    cand = {pc: [m for m in range(lo, hi + 1) if m % 12 == pc] for pc in pcs}
    if not prev: return sorted(min(cand[pc], key=lambda m: abs(m - mid)) for pc in pcs)
    ref = float(np.mean(prev)); out = []
    for pc in pcs:
        near = [min(cand[pc], key=lambda m, p=p: abs(m - p)) for p in prev]
        out.append(min(near, key=lambda m: abs(m - ref)))
    return sorted(set(out)) if len(set(out)) == len(out) else sorted(min(cand[pc], key=lambda m: abs(m - ref)) for pc in pcs)


# ───────────────────────── tones ─────────────────────────
def pad(ms, d, vol=0.15, rng=None, attack=0.9, release=1.0, bright=0.5, detune=0.07):
    """a warm synth pad: per note three saws detuned +-`detune` semitones (7 cents: a gentle chorus) over an exactly tuned sine, through a low-pass that opens as the swell arrives.
    `attack` / `release` in seconds (cosine swell), bright 0..1 = how open the filter gets.  No vibrato, no inharmonic partials."""
    r = _g(rng); t = S.tt(d); x = np.zeros(len(t))
    for m in ms:
        for k in (-1, 0, 1): x += signal.sawtooth(TAU * S.midi(m + k * detune) * t + r.uniform(0, TAU))
        x += 1.2 * np.sin(TAU * S.midi(m) * t)
    sw = np.clip(t / max(attack, 0.05), 0, 1); cut = (450 + 2900 * bright) * (0.5 + 0.5 * sw)
    x = S.lp(x, cut, 2)
    e = (0.5 - 0.5 * np.cos(np.pi * sw)) * np.clip((d - t) / max(release, 0.02), 0, 1)
    return _norm(x * e, vol, 0.001, 0.005)


def keys(m, d=1.4, vol=0.2, rng=None, tone=0.5):
    """felt piano / soft electric piano: harmonic partials 1-5 (exact multiples) that die away faster the higher they are, two voices a few cents apart, a muted hammer thump.
    NOT a mallet: no inharmonic partials, a 6 ms attack and a long natural decay, so it reads as 'keys' rather than 'xylophone'.  tone 0..1 = brighter."""
    r = _g(rng); t = S.tt(d); f = S.midi(m); x = np.zeros(len(t))
    for det in (-0.035, 0.04):
        for k, (a, tau) in enumerate(((1.0, 0.55), (0.42, 0.34), (0.2, 0.21), (0.09, 0.13), (0.04, 0.09)), 1):
            if f * k < 8000: x += 0.5 * a * np.sin(TAU * f * 2 ** (det / 12) * k * t + r.uniform(0, TAU)) * np.exp(-t / (tau * d))
    x = S.lp(x, 1800 + 3200 * tone, 2)
    thump = S.lp(r.standard_normal(len(t)), 900 + 600 * tone, 2) * S.expdecay(len(t), 0.012) * 0.22 * np.max(np.abs(x))
    return _norm((x + thump) * np.minimum(1, t / 0.006), vol, 0.001, 0.05)


def stab(ms, d=0.3, vol=0.12, rng=None, cutoff=2400):
    """a short chord stab (two detuned saws per note, low-pass that closes as it plays): rhythmic harmony without a plucked-bar sound"""
    r = _g(rng); t = S.tt(d); x = np.zeros(len(t))
    for m in ms:
        for k in (-1, 1): x += signal.sawtooth(TAU * S.midi(m + k * 0.06) * t + r.uniform(0, TAU))
    x = S.lp(x, 350 + cutoff * np.exp(-t / (d * 0.45)), 2)
    return _norm(x * np.minimum(1, t / 0.004) * S.expdecay(len(t), d * 0.5) * np.clip((d - t) / 0.03, 0, 1), vol, 0.001, 0.01)


def sub(m, d, vol=0.3, harm=0.5):
    """a tuned bass note: a sine with a little 2nd / 3rd harmonic (so it still speaks on laptop speakers), soft attack, gentle decay.  Keep m >= 33 (55 Hz)."""
    t = S.tt(d); f = S.midi(m)
    x = np.sin(TAU * f * t) + harm * 0.55 * np.sin(TAU * 2 * f * t) + harm * 0.3 * np.sin(TAU * 3 * f * t)
    x = np.tanh(1.3 * x) * np.minimum(1, t / 0.012) * (0.7 + 0.3 * np.exp(-t / (0.4 * max(d, 0.1)))) * np.clip((d - t) / 0.04, 0, 1)
    return _norm(x, vol, 0.002, 0.01)


# ───────────────────────── drums ─────────────────────────
def kick(vol=0.8, f=55.0, rng=None):
    """a round, tuned kick: a sine that falls onto `f` Hz (55 = A1) in ~40 ms, a soft beater tap.  Tune f to the key's root so the kick and the sub-bass agree."""
    r = _g(rng); t = S.tt(0.4); fr = f * (1 + 2.6 * np.exp(-t * 42)); ph = TAU * np.cumsum(fr) / SR
    x = np.sin(ph) * np.exp(-t / 0.14) + 0.16 * S.lp(r.standard_normal(len(t)), 2200, 2) * S.expdecay(len(t), 0.004)
    return _norm(np.tanh(1.25 * x), vol, 0.0006, 0.02)


def shaker(vol=0.1, rng=None, open_=False):
    """a soft shaker / closed hat: high noise with a 6 ms swell and a short tail (no metallic ring)"""
    r = _g(rng); d = 0.13 if open_ else 0.05; n = int(SR * d); t = np.arange(n) / SR
    x = S.bp(r.standard_normal(n), 5500, 13000, 2) * np.minimum(1, t / 0.006) * np.exp(-t / (d * 0.32))
    return _norm(x, vol, 0.0005, 0.01)


def clap(vol=0.3, rng=None):
    """a soft hand clap: three close noise bursts band-limited to 800-3200 Hz and a short tail"""
    r = _g(rng); n = int(SR * 0.2); x = S.bp(r.standard_normal(n), 800, 3200, 2); b = np.zeros(n)
    for k in (0.0, 0.009, 0.019):
        i = int(k * SR); b[i:] += S.expdecay(n - i, 0.009)
    return _norm(x * (0.7 * b + S.expdecay(n, 0.05)), vol, 0.0005, 0.02)


def impact(d=3.0, vol=0.6, m=33, rng=None):
    """a resolving 'arrival': the root (and its octave) settling onto pitch within ~50 ms, a breath of soft noise.  Tonal, so it lands IN the key; no gong, no sub rumble."""
    r = _g(rng); t = S.tt(d); f = S.midi(m)
    fr = f * (1 + 0.25 * np.exp(-t * 40)); ph = TAU * np.cumsum(fr) / SR
    x = np.sin(ph) * np.exp(-t / (d * 0.22)) + 0.35 * np.sin(2 * ph) * np.exp(-t / (d * 0.14)) + 0.12 * np.sin(3 * ph) * np.exp(-t / (d * 0.1))
    x += 0.5 * S.lp(r.standard_normal(len(t)), 3200, 2) * np.exp(-t / 0.35) * np.minimum(1, t / 0.004)
    return _norm(np.tanh(x), vol, 0.001, 0.05)


def air(d=1.5, vol=0.3, up=True, rng=None):
    """a smooth noise swell (riser) or fall: filtered noise only - never a pitched sweep, so it cannot sound flat or sharp against the key"""
    r = _g(rng); t = S.tt(d); n = r.standard_normal(len(t)); f = np.geomspace(500, 9000, len(t)) if up else np.geomspace(9000, 500, len(t))
    x = S.lp(S.hp(n, 300, 2), f, 2); e = (t / d) ** 2.2 if up else (1 - t / d) ** 1.8
    return _norm(x * e * np.minimum(1, (d - t) / 0.02), vol, 0.0005, 0.02)


# ───────────────────────── mix helpers ─────────────────────────
def pump(x, t0, hits, depth=0.55, release=0.3):
    """sidechain 'pump': duck x (which starts at t0 seconds) by `depth` (0..1) on every time in `hits`, recovering over ~`release` s.  Makes pads/bass breathe with the kick and leaves room for it."""
    hits = np.sort(np.asarray(hits, dtype=float))
    if not len(hits) or depth <= 0: return x
    t = t0 + np.arange(len(x)) / SR; idx = np.searchsorted(hits, t, side='right') - 1
    since = np.where(idx >= 0, t - hits[np.clip(idx, 0, None)], 1e9)
    g = 1 - depth * np.exp(-since / (release / 3.0))
    return x * uniform_filter1d(g, max(1, int(0.003 * SR)))


def add_wide(make, t, gain=1.0, send=0.0, spread=0.5, name=None, rng=None):
    """place a sound with width: `make(rng)` is called twice with different randomness (phases, chorus) and the two takes go left and right.  Returns nothing (uses synth.add)."""
    r = _g(rng)
    for p in (-spread, spread): S.add(make(np.random.default_rng(int(r.integers(1 << 31)))), t, gain * 0.72, p, send, name=name)
