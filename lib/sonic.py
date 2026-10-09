"""sonic.py - a bigger, seeded sound palette on top of synth.py.  numpy + scipy only; nothing sampled, nothing to license.

WHY: synth.py's instruments are a handful of fixed timbres and init() reseeds to 7 for every film, so every film you build sounds like the last
(measure it: tools/sound-report.py).  sonic.py fixes that at three levels:
  1. a Palette(seed, mood) chooses a key, a mode, and WHICH instrument plays each role (pad / bell / pulse / hit) from the seed, so film A and film B differ;
  2. every instrument takes a numpy Generator and the Palette hands out a NEW one on every call, so ten stamps in one film are ten different stamps;
  3. a much larger instrument and foley list (below), distinct rooms (use_room), and a generative bed composer (Palette.bed).

    import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lib'))
    from synth import *; import sonic as SN
    C = load_cues(HERE); seed = SN.seed_of('my-film'); init(C['duration'], seed=seed)
    P = SN.Palette(seed, 'grave')                  # moods: grave eerie wonder tense warm machine
    SN.use_room('chamber', seed)                   # reverb character (hall plate chamber cathedral tin tape)
    P.bed(0.0, 40.0, intensity=0.5)                # a generative chord bed: progression, voice-leading, bass, sparse motif notes - all from the seed
    add(P.hit(0.8), 12.0, 1, 0, 0.4)               # the palette's 'hit' instrument (stamp / taiko / gong / anvil ...), different every call
    add(SN.geiger(6, (3, 40), 0.3, P.rng('geiger')), 20.0)
    master(default_out(HERE))

Instruments (all return mono float arrays whose PEAK is about `vol`; `rng` is a numpy Generator - pass P.rng('name') or leave None for a fixed one):
  pads/tones  strings(ms,d,vol,swell,rng)  choir(ms,d,vol,vowel,swell,rng)  bowed(m,d,vol,rng)  organ(ms,d,vol,rng)  glass(ms,d,vol,rng)  drone(m,d,vol,rng)
  plucks/bells  ks(m,d,vol,rng,damp)  fm_bell(m,d,vol,rng)  mallet(m,d,vol,material,rng)  epiano(m,d,vol,rng)
  drums/hits  frame_drum(vol,rng)  taiko(vol,rng)  gong(d,vol,rng)  anvil(vol,rng)  stamp(vol,rng,surface)  wood_knock(vol,rng)  sub_drop(d,vol)  heartbeat(vol,rng)
  foley   typewriter_key(vol,rng)  typewriter_return(vol,rng)  paper(d,kind,vol,rng)  pen_scratch(d,vol,rng)  camera_shutter(vol,rng)  sonar_ping(vol,rng)
  texture   geiger(d,rate,vol,rng)  static(d,vol,rng)  morse(text,wpm,f,vol)  clock(d,bpm,vol,rng)  projector(d,vol,rng)  tape_hiss(d,vol,rng)  wind(d,vol,rng)
            prop_drone(d,vol,rpm,blades,rng)  rumble(d,vol,rng)
  risers    shepard(d,vol,up)  pitch_riser(d,vol,rng)
Helpers: seed_of(*parts), MODES, Palette, use_room(kind, seed), jitter(rng, ms), scale_note(root, mode, degree).
"""
import zlib
import contextlib
import numpy as np
from scipy import signal
import synth as S

SR = S.SR
TAU = 2 * np.pi


def seed_of(*parts):
    """a stable 31-bit integer from any strings/numbers: seed_of('003-the-pig-war').  (Python's hash() is salted per process, so it is NOT used.)"""
    return zlib.crc32('|'.join(str(p) for p in parts).encode('utf-8')) & 0x7fffffff


_default_rng = np.random.default_rng(12345)


def _g(rng): return rng if rng is not None else _default_rng


def _norm(x, vol):
    """scale to a peak of `vol` and give the ends a 0.3 ms / 2 ms fade so no instrument ever starts or stops with a click"""
    x = np.nan_to_num(np.asarray(x, dtype=float)); m = np.max(np.abs(x))
    if m <= 1e-12: return x
    x = x * (vol / m); n = len(x); a = min(n // 2, int(0.0003 * SR)); b = min(n // 2, int(0.002 * SR))
    if a > 1: x[:a] *= np.linspace(0, 1, a)
    if b > 1: x[-b:] *= np.linspace(1, 0, b)
    return x


def _fade(n, a=0.005, r=0.02):
    e = np.ones(n); na = min(n, max(1, int(a * SR))); nr = min(n, max(1, int(r * SR)))
    e[:na] = np.linspace(0, 1, na) ** 1.5; e[-nr:] *= np.linspace(1, 0, nr) ** 1.5
    return e


def _sat(x, k=1.0): return np.tanh(x * k) / np.tanh(k) if k > 0 else x


def _noise(n, rng): return _g(rng).standard_normal(n)


def _phase(f): return TAU * np.cumsum(f) / SR


def _vibrato(t, rng, depth=0.004, rate=(4.6, 5.8), delay=0.4):
    r = _g(rng); return 1 + depth * np.sin(TAU * r.uniform(*rate) * t + r.uniform(0, 6.28)) * np.clip((t - delay) / 0.8, 0, 1)


@contextlib.contextmanager
def _borrow(r):
    """synth's thud/bell/noise_sweep draw from its module-global rng; lend them this instrument's own generator so the result depends only on `rng` (and the global stream is left untouched)"""
    saved = S.rng.bit_generator.state; S.rng.bit_generator.state = r.bit_generator.state
    try: yield
    finally: r.bit_generator.state = S.rng.bit_generator.state; S.rng.bit_generator.state = saved


def jitter(rng, ms=12.0):
    """a small random time offset in seconds (humanise a grid of hits): add(x, t + jitter(r, 15))"""
    return float(_g(rng).uniform(-ms, ms)) / 1000.0


# ───────────────────────── music theory ─────────────────────────
MODES = {'ionian': [0, 2, 4, 5, 7, 9, 11], 'dorian': [0, 2, 3, 5, 7, 9, 10], 'phrygian': [0, 1, 3, 5, 7, 8, 10], 'lydian': [0, 2, 4, 6, 7, 9, 11],
         'mixolydian': [0, 2, 4, 5, 7, 9, 10], 'aeolian': [0, 2, 3, 5, 7, 8, 10], 'locrian': [0, 1, 3, 5, 6, 8, 10], 'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
         'phrygian_dominant': [0, 1, 4, 5, 7, 8, 10], 'whole_tone': [0, 2, 4, 6, 8, 10, 12], 'minor_pentatonic': [0, 3, 5, 7, 10, 12, 15]}


def scale_note(root, mode, degree):
    """midi note for scale degree `degree` (0 = root, 7 = octave up, -1 = the 7th below ...)"""
    sc = MODES[mode]; o, d = divmod(degree, len(sc)); return root + 12 * o + sc[d]


# ───────────────────────── pads and tones ─────────────────────────
def strings(ms, d, vol=0.15, swell=1.5, rng=None, bright=1.0):
    """an ensemble: four detuned saws per note with their own vibrato, a slowly breathing filter.  Different seeds give a different 'section'."""
    r = _g(rng); t = S.tt(d); x = np.zeros(len(t))
    for m in ms:
        for _ in range(4):
            f = S.midi(m + r.uniform(-0.13, 0.13)) * _vibrato(t, r, 0.003, (4.2, 5.6), 0.5)
            x += signal.sawtooth(_phase(f) + r.uniform(0, 6.28))
    cut = (600 + 2400 * bright * np.clip(t / max(swell, 0.05), 0, 1) ** 2) * (1 + 0.25 * np.sin(TAU * r.uniform(0.05, 0.2) * t + r.uniform(0, 6.28)))
    x = S.lp(x, cut, 2)
    return _norm(x, 1) * vol * np.minimum(1, t / swell) * np.minimum(1, (d - t) / 0.7).clip(0, 1) * 1.0


_FORMANTS = {'a': (800, 1150, 2900), 'e': (400, 1700, 2600), 'i': (270, 2100, 3000), 'o': (450, 800, 2830), 'u': (325, 700, 2700)}


def choir(ms, d, vol=0.15, vowel='a', swell=1.5, rng=None):
    """a sung vowel pad: vibrato saws through formant filters + a little breath.  vowel in a e i o u (pass a string like 'aou' to morph is NOT supported; pick one)"""
    r = _g(rng); t = S.tt(d); x = np.zeros(len(t))
    for m in ms:
        for _ in range(3): x += signal.sawtooth(_phase(S.midi(m + r.uniform(-0.1, 0.1)) * _vibrato(t, r, 0.006, (5, 6), 0.3)) + r.uniform(0, 6.28))
    x = x / max(1, len(ms)); out = np.zeros(len(t))
    for f, g in zip(_FORMANTS[vowel], (1.0, 0.55, 0.25)): out += g * S.bp(x, f * 0.93, f * 1.07, 2)
    out += 0.05 * S.bp(_noise(len(t), r), 1500, 5000)
    return _norm(out, 1) * vol * np.minimum(1, t / swell) * np.clip(np.minimum(1, (d - t) / 0.8), 0, 1)


def bowed(m, d, vol=0.2, rng=None):
    """a single bowed string (cello/viola-ish): saw + rosin noise, vibrato that arrives after the note starts"""
    r = _g(rng); t = S.tt(d); f = S.midi(m) * _vibrato(t, r, 0.005, (4.8, 5.6), 0.45)
    x = signal.sawtooth(_phase(f), 0.85) + 0.5 * signal.sawtooth(_phase(f * 1.003)) + 0.09 * _noise(len(t), r)
    x = S.lp(x, 1500 + 900 * np.clip(t / 0.8, 0, 1), 2)
    return _norm(x, 1) * vol * np.minimum(1, t / 0.4) ** 1.2 * np.clip(np.minimum(1, (d - t) / 0.5), 0, 1)


def organ(ms, d, vol=0.15, rng=None):
    """drawbar organ: sine partials, leslie-ish tremolo, a breath of key chiff on each start"""
    r = _g(rng); t = S.tt(d); x = np.zeros(len(t)); bars = (1, 0.0, 0.7, 0.45, 0.0, 0.3, 0.0, 0.18)
    for m in ms:
        for k, a in enumerate(bars, 1):
            if a: x += a * np.sin(TAU * S.midi(m) * k * t + r.uniform(0, 6.28)) / k ** 0.3
    x *= 1 + 0.1 * np.sin(TAU * r.uniform(5.2, 6.4) * t)
    chiff = S.bp(_noise(len(t), r), 1800, 4200) * S.expdecay(len(t), 0.03) * 0.5
    return _norm(x + chiff * np.max(np.abs(x)), 1) * vol * np.minimum(1, t / 0.06) * np.clip(np.minimum(1, (d - t) / 0.25), 0, 1)


def glass(ms, d, vol=0.12, rng=None):
    """glass-harmonica / bowed-crystal pad: pure partials that beat against slightly detuned twins and shimmer"""
    r = _g(rng); t = S.tt(d); x = np.zeros(len(t))
    for m in ms:
        for k, a in ((1, 1.0), (2.005, 0.34), (3.01, 0.17), (5.02, 0.07)):
            for det in (-0.04, 0.05):
                x += a * np.sin(TAU * S.midi(m + det) * k * t + r.uniform(0, 6.28)) * (0.75 + 0.25 * np.sin(TAU * r.uniform(0.15, 0.5) * t + r.uniform(0, 6.28)))
    return _norm(S.lp(x, 6500, 1), 1) * vol * np.minimum(1, t / 1.2) * np.clip(np.minimum(1, (d - t) / 1.0), 0, 1)


def drone(m, d, vol=0.2, rng=None):
    """a living low drone: two near-unison sines that beat slowly + a filtered saw whose cutoff wanders + a fifth above, very quiet"""
    r = _g(rng); t = S.tt(d); f = S.midi(m)
    x = np.sin(TAU * f * t) + np.sin(TAU * f * (1 + r.uniform(0.0015, 0.004)) * t) + 0.35 * signal.sawtooth(TAU * f * 2 * t)
    x = S.lp(x, 380 + 260 * (0.5 + 0.5 * np.sin(TAU * r.uniform(0.04, 0.11) * t + r.uniform(0, 6.28))), 2) + 0.18 * np.sin(TAU * f * 1.5 * t) * (0.5 + 0.5 * np.sin(TAU * 0.07 * t))
    return _norm(x, 1) * vol * np.minimum(1, t / 2.0) * np.clip(np.minimum(1, (d - t) / 1.5), 0, 1)


# ───────────────────────── plucks and bells ─────────────────────────
def ks(m, d=1.2, vol=0.3, rng=None, damp=0.5):
    """Karplus-Strong plucked string (a physical model: a noise burst circulating in a loop that loses highs each pass).  damp 0 = bright and long, 1 = dull and short"""
    r = _g(rng); f = S.midi(m); n = int(d * SR); N = max(8, int(round(SR / f)))
    g = 0.9965 - 0.0045 * damp; a = np.zeros(N + 2); a[0] = 1; a[N] = -g * 0.5; a[N + 1] = -g * 0.5
    exc = np.zeros(n); b = r.standard_normal(N); exc[:N] = S.lp(b, 2500 + 6000 * (1 - damp), 1)
    x = signal.lfilter([1.0], a, exc)
    return _norm(x, 1) * vol * _fade(n, 0.001, 0.05)


def fm_bell(m, d=2.0, vol=0.25, rng=None):
    """FM bell: a modulator at a random inharmonic ratio whose depth decays - each call is a slightly different bell"""
    r = _g(rng); t = S.tt(d); f = S.midi(m); ratio = r.choice([1.4, 2.0, 2.756, 3.5, 3.14, 5.04]) * r.uniform(0.995, 1.005); idx = r.uniform(2.5, 6.0)
    mod = np.sin(TAU * f * ratio * t) * idx * np.exp(-t * r.uniform(2.5, 5)); x = np.sin(TAU * f * t + mod)
    return _norm(x, 1) * vol * S.expdecay(len(t), d * r.uniform(0.22, 0.38)) * _fade(len(t), 0.001, 0.08)


_MALLET = {'wood': ((1, 3.9, 9.2), (1, 0.32, 0.12), (1, 0.35, 0.15)), 'glass': ((1, 2.32, 4.25, 6.63), (1, 0.6, 0.35, 0.18), (1, 0.7, 0.5, 0.3)),
           'metal': ((1, 2.76, 5.4, 8.93), (1, 0.55, 0.3, 0.15), (1, 0.6, 0.4, 0.25)), 'musicbox': ((1, 3.01, 5.2, 7.35), (1, 0.4, 0.25, 0.12), (1, 0.4, 0.3, 0.2)),
           'vibes': ((1, 4.0, 10.0), (1, 0.45, 0.15), (1, 0.4, 0.2))}


def mallet(m, d=1.5, vol=0.25, material='glass', rng=None):
    """struck bar: a few inharmonic partials with their own decays; material in wood glass metal musicbox vibes"""
    r = _g(rng); t = S.tt(d); f = S.midi(m); ratios, amps, taus = _MALLET[material]; x = np.zeros(len(t))
    for q, a, tau in zip(ratios, amps, taus):
        fq = f * q * r.uniform(0.998, 1.002)
        if fq < SR / 2 - 500: x += a * np.sin(TAU * fq * t + r.uniform(0, 6.28)) * np.exp(-t / (d * 0.3 * tau))
    x += 0.15 * S.bp(_noise(len(t), r), f * 2, f * 6) * S.expdecay(len(t), 0.004)
    if material == 'vibes': x *= 1 + 0.25 * np.sin(TAU * 5 * t)
    return _norm(x, 1) * vol * _fade(len(t), 0.0008, 0.06)


def epiano(m, d=1.6, vol=0.25, rng=None):
    """Rhodes-ish electric piano: FM with a decaying 1:1 body and a short 14:1 'tine'"""
    r = _g(rng); t = S.tt(d); f = S.midi(m)
    x = np.sin(TAU * f * t + (1.4 + r.uniform(-0.3, 0.3)) * np.exp(-t * 3) * np.sin(TAU * f * t) + 0.35 * np.exp(-t * 25) * np.sin(TAU * f * 14 * t))
    return _norm(x, 1) * vol * S.expdecay(len(t), d * 0.33) * _fade(len(t), 0.002, 0.08)


# ───────────────────────── drums, hits, stamps ─────────────────────────
def frame_drum(vol=0.5, rng=None, pitch=None):
    """a hand/frame drum: pitch-dropping skin + a soft slap; pitch differs per call"""
    r = _g(rng); f0 = pitch or r.uniform(70, 115); t = S.tt(0.7); f = f0 * (1 + 0.8 * np.exp(-t * 30)); x = np.sin(_phase(f)) * S.expdecay(len(t), r.uniform(0.09, 0.15))
    x += 0.5 * S.bp(_noise(len(t), r), 180, 900) * S.expdecay(len(t), 0.03) + 0.25 * S.bp(_noise(len(t), r), 1500, 5000) * S.expdecay(len(t), 0.006)
    return _norm(_sat(x, 1.3), vol)


def taiko(vol=0.7, rng=None):
    """a big drum: low sine with a long skin ring, wide noise body, and a rumble tail"""
    r = _g(rng); t = S.tt(1.6); f = r.uniform(48, 62) * (1 + 0.9 * np.exp(-t * 14)); x = np.sin(_phase(f)) * S.expdecay(len(t), r.uniform(0.35, 0.5))
    x += 0.5 * S.bp(_noise(len(t), r), 120, 700) * S.expdecay(len(t), 0.08) + 0.3 * S.bp(_noise(len(t), r), 2000, 7000) * S.expdecay(len(t), 0.01)
    x += 0.2 * np.sin(_phase(f * 2.4)) * S.expdecay(len(t), 0.25)
    return _norm(_sat(x, 1.4), vol)


def gong(d=4.0, vol=0.4, rng=None, pitch=None):
    """a tam-tam/gong: a dense cluster of inharmonic partials that swell and beat"""
    r = _g(rng); t = S.tt(d); f0 = pitch or r.uniform(70, 130); x = np.zeros(len(t))
    for q in (1, 1.47, 2.09, 2.56, 3.14, 3.89, 4.62, 5.35, 6.7):
        q2 = q * r.uniform(0.985, 1.015); a = 1 / q ** 0.6
        x += a * np.sin(TAU * f0 * q2 * t + r.uniform(0, 6.28)) * np.exp(-t / (d * r.uniform(0.18, 0.4) / q ** 0.35)) * (0.7 + 0.3 * np.sin(TAU * r.uniform(0.5, 3) * t))
    x += 0.4 * S.bp(_noise(len(t), r), 400, 5000) * S.expdecay(len(t), 0.05)
    return _norm(x, 1) * vol * np.minimum(1, t / 0.012)


def anvil(vol=0.5, rng=None):
    """a struck piece of steel: bright inharmonic ring with a hard tap"""
    r = _g(rng); t = S.tt(1.2); f0 = r.uniform(520, 900); x = np.zeros(len(t))
    for q, a, tau in ((1, 1, 0.5), (2.74, 0.7, 0.35), (5.4, 0.5, 0.2), (8.93, 0.35, 0.12), (13.3, 0.2, 0.07)):
        x += a * np.sin(TAU * f0 * q * r.uniform(0.997, 1.003) * t + r.uniform(0, 6.28)) * np.exp(-t / tau)
    x += 0.8 * S.bp(_noise(len(t), r), 2000, 9000) * S.expdecay(len(t), 0.004)
    return _norm(x, vol)


_SURF = {'wood': (210, 5200, 0.05), 'leather': (150, 2400, 0.04), 'desk': (95, 3800, 0.07), 'stone': (320, 7000, 0.03)}


def stamp(vol=0.9, rng=None, surface=None):
    """a rubber stamp hitting a surface: body thump + paper slap + a short resonance.  surface wood/leather/desk/stone (random per call if None)"""
    r = _g(rng); surface = surface or r.choice(list(_SURF)); f0, hi, tau = _SURF[surface]; f0 *= r.uniform(0.85, 1.2); t = S.tt(0.55)
    x = np.sin(_phase(f0 * (1 + 1.1 * np.exp(-t * 45)))) * S.expdecay(len(t), tau * r.uniform(0.9, 1.5)) + 0.7 * S.bp(_noise(len(t), r), 700, hi) * S.expdecay(len(t), 0.018)
    x += 0.25 * np.sin(TAU * f0 * 2.9 * r.uniform(0.95, 1.05) * t) * S.expdecay(len(t), 0.09) + 0.35 * S.lp(_noise(len(t), r), 400) * S.expdecay(len(t), 0.06)
    return _norm(_sat(x, 1.5), vol)


def wood_knock(vol=0.4, rng=None):
    r = _g(rng); t = S.tt(0.18); f = r.uniform(330, 620)
    x = np.sin(TAU * f * t) * S.expdecay(len(t), 0.02) + 0.6 * S.bp(_noise(len(t), r), 900, 3500) * S.expdecay(len(t), 0.006)
    return _norm(x, vol)


def sub_drop(d=1.6, vol=0.6):
    """a pure sub-bass drop (a held breath before/after a reveal)"""
    t = S.tt(d); f = 90 * np.exp(-t * 1.9) + 28; return _norm(np.sin(_phase(f)) * np.exp(-t * 1.1), vol) * _fade(len(t), 0.01, 0.1)


def heartbeat(vol=0.5, rng=None):
    """lub-dub: two soft low thumps, each a little different"""
    r = _g(rng); f1, f2, v2 = r.uniform(46, 58), r.uniform(42, 52), r.uniform(0.55, 0.75)
    with _borrow(r): a = S.thud(vol, f1); b = S.thud(vol * v2, f2)
    out = np.zeros(int(SR * 0.62)); out[:len(a)] += a; k = int(r.uniform(0.15, 0.2) * SR); out[k:k + len(b)] += b
    return out


# ───────────────────────── foley ─────────────────────────
def typewriter_key(vol=0.3, rng=None):
    """one keystroke on a manual typewriter: type-bar click + a soft platen thock; pitch and weight vary per key"""
    r = _g(rng); n = int(SR * 0.09); t = np.arange(n) / SR; f = r.uniform(170, 260)
    x = 3.0 * S.bp(_noise(n, r), r.uniform(1800, 2600), r.uniform(4200, 6500)) * S.expdecay(n, 0.0022) + 0.7 * np.sin(TAU * f * t) * S.expdecay(n, 0.016) + 0.9 * S.bp(_noise(n, r), 400, 1200) * S.expdecay(n, 0.012)
    return _norm(x, vol)


def typewriter_return(vol=0.4, rng=None):
    """carriage return: the slide-along whirr, then the bell, then the clunk"""
    r = _g(rng); n = int(SR * 0.9); x = np.zeros(n); sl = S.bp(_noise(int(0.28 * SR), r), 1500, 4500) * np.linspace(0.3, 1, int(0.28 * SR)) * 0.5
    x[:len(sl)] += sl; bm = int(r.choice([96, 97, 95]))
    with _borrow(r): b = S.bell(bm, 0.6, 0.45); c = S.thud(0.5, 110)
    k = int(0.3 * SR); x[k:k + len(b)] += b
    x[int(0.28 * SR):int(0.28 * SR) + len(c)] += c
    return _norm(x, vol)


def paper(d=0.3, kind='slide', vol=0.3, rng=None):
    """paper: kind 'slide' (a sheet pulled across a desk), 'rustle' (handling), 'turn' (a page: lift, flick, settle)"""
    r = _g(rng); n = int(SR * d); t = np.arange(n) / SR
    if kind == 'rustle':
        grains = S.lp(np.abs(S.bp(_noise(n, r), 30, 90, 1)), 40, 1); grains = grains / (grains.max() + 1e-9)
        x = S.bp(_noise(n, r), 2500, 9000) * (grains ** 1.5) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 0.5
    elif kind == 'turn':
        x = S.bp(_noise(n, r), 1200, 7000) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2 * (0.4 + 0.6 * np.exp(-((t - d * 0.55) / 0.04) ** 2))
    else:
        f0, f1, up = r.uniform(900, 1600), r.uniform(4500, 8000), bool(r.integers(0, 2))
        with _borrow(r): x = S.noise_sweep(d, f0, f1, 1.0, up) if d >= 0.06 else np.zeros(n)
        x = x[:n] * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.3
    return _norm(x, vol)


def pen_scratch(d=0.8, vol=0.2, rng=None):
    """a pen / pencil on paper: noisy strokes - several quick bursts of high-passed noise with irregular gaps"""
    r = _g(rng); n = int(SR * d); t = np.arange(n) / SR; x = S.bp(_noise(n, r), 2200, 8000)
    env = np.zeros(n)
    for _ in range(max(2, int(d * r.uniform(5, 9)))):
        c = r.uniform(0, d); w = r.uniform(0.04, 0.14); env += np.exp(-0.5 * ((t - c) / (w / 2.5)) ** 2) * r.uniform(0.4, 1)
    return _norm(x * np.clip(env, 0, 1.2) * _fade(n, 0.03, 0.08), vol)


def camera_shutter(vol=0.4, rng=None):
    r = _g(rng); n = int(SR * 0.16); x = np.zeros(n)
    for k, a in ((0.0, 1.0), (0.055, 0.7)):
        i = int(k * SR); m = min(n - i, int(0.025 * SR)); x[i:i + m] += a * S.bp(_noise(m, r), 1500, 7000) * S.expdecay(m, 0.004) + a * 0.5 * np.sin(TAU * r.uniform(700, 1100) * np.arange(m) / SR) * S.expdecay(m, 0.006)
    return _norm(x, vol)


def glass_shatter(vol=0.5, rng=None):
    """a pane breaking: one bright crack, then a scatter of short high tinkles that thins out over ~0.8 s (different every call)"""
    r = _g(rng); n = int(SR * 0.9); x = 0.9 * S.hp(_noise(n, r), 2500, 2) * S.expdecay(n, 0.03)
    times = np.sort(r.exponential(0.16, int(r.integers(30, 46)))); times = times[times < 0.8]
    for tt in times:
        d = float(r.uniform(0.02, 0.09)); m = int(SR * d); f = float(r.uniform(2800, 9500)); i = int(tt * SR)
        ping = np.sin(TAU * f * np.arange(m) / SR) * S.expdecay(m, d / 4) * float(r.uniform(0.15, 0.6)); k = max(0, min(m, n - i)); x[i:i + k] += ping[:k]
    return _norm(x, vol)


def skid(d=1.5, vol=0.4, rng=None):
    """a belly sliding to a halt on hard ground: low scraping noise with irregular grabs that darkens and slows as it stops"""
    r = _g(rng); n = int(SR * d); t = np.arange(n) / SR; jit = S.lp(_noise(n, r), 14); jit = jit / (np.abs(jit).max() + 1e-9)
    x = S.lp(_noise(n, r), np.geomspace(2200, 260, n), 2) * np.clip(0.55 + 0.45 * jit, 0, 1) * np.clip(1 - t / d, 0, 1) ** 0.7
    x = x + 0.4 * S.lp(_noise(n, r), 140, 2) * np.clip(1 - t / d, 0, 1)
    return _norm(x, vol) * np.minimum(1, t / 0.08)


def sonar_ping(vol=0.3, rng=None):
    r = _g(rng); t = S.tt(2.0); f = r.uniform(900, 1500); x = np.sin(TAU * f * t) * np.exp(-t * 3.5) * np.minimum(1, t / 0.004)
    return _norm(x + 0.25 * np.sin(TAU * f * 2 * t) * np.exp(-t * 7), vol)


# ───────────────────────── textures (loop-length beds) ─────────────────────────
def geiger(d, rate=(5, 25), vol=0.3, rng=None):
    """a Geiger counter: a Poisson process of tiny clicks.  rate = clicks per second, a number or (start, end) to ramp"""
    r = _g(rng); n = int(SR * d); x = np.zeros(n); r0, r1 = (rate, rate) if np.isscalar(rate) else rate; t = 0.0
    click = S.bp(r.standard_normal(int(0.004 * SR)), 1200, 5000) * S.expdecay(int(0.004 * SR), 0.0007)
    while True:
        cur = r0 + (r1 - r0) * min(1, t / d); t += r.exponential(1.0 / max(cur, 0.1))
        if t >= d: break
        i = int(t * SR); m = min(len(click), n - i)
        if m > 0: x[i:i + m] += click[:m] * r.uniform(0.3, 1.0) * (1 if r.random() > 0.15 else 1.8)
    return _norm(x, vol)


def static(d, vol=0.2, rng=None):
    """radio static: band-limited hiss, crackle bursts, and a faint heterodyne whistle drifting through"""
    r = _g(rng); n = int(SR * d); t = np.arange(n) / SR; x = S.bp(_noise(n, r), 400, 7000) * (0.5 + 0.5 * S.lp(np.abs(_noise(n, r)), 6, 1) * 4)
    for _ in range(int(d * 14)):
        i = int(r.uniform(0, max(1, n - 400))); m = int(r.uniform(40, 400)); x[i:i + m] += r.standard_normal(min(m, n - i)) * r.uniform(1, 3)
    x += 0.25 * np.sin(_phase(900 + 700 * np.sin(TAU * r.uniform(0.05, 0.15) * t))) * (0.5 + 0.5 * np.sin(TAU * 0.3 * t))
    return _norm(x, vol)


def morse(text, wpm=18, f=640, vol=0.2):
    """CW morse code of `text` (letters, digits, spaces) at `wpm`; deterministic, soft-edged"""
    code = {'a': '.-', 'b': '-...', 'c': '-.-.', 'd': '-..', 'e': '.', 'f': '..-.', 'g': '--.', 'h': '....', 'i': '..', 'j': '.---', 'k': '-.-', 'l': '.-..', 'm': '--', 'n': '-.', 'o': '---', 'p': '.--.', 'q': '--.-',
            'r': '.-.', 's': '...', 't': '-', 'u': '..-', 'v': '...-', 'w': '.--', 'x': '-..-', 'y': '-.--', 'z': '--..', '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....',
            '6': '-....', '7': '--...', '8': '---..', '9': '----.'}
    u = 1.2 / wpm; segs = []
    for w in text.lower().split(' '):
        for ch in w:
            for sym in code.get(ch, ''): segs.append((u if sym == '.' else 3 * u, True)); segs.append((u, False))
            segs.append((2 * u, False))
        segs.append((4 * u, False))
    out = np.zeros(int(SR * (sum(s for s, _ in segs) + 0.05))); i = 0
    for dur, on in segs:
        m = int(dur * SR)
        if on: tt_ = np.arange(m) / SR; out[i:i + m] += np.sin(TAU * f * tt_) * _fade(m, 0.004, 0.004)
        i += m
    return out * vol


def clock(d, bpm=60, vol=0.25, rng=None):
    """a ticking clock for `d` seconds: alternating tick / tock, never exactly the same twice"""
    r = _g(rng); n = int(SR * d); x = np.zeros(n); step = 60.0 / bpm; k = 0
    while k * step < d:
        f = (2300 if k % 2 == 0 else 1700) * r.uniform(0.94, 1.06); m = int(0.05 * SR); i = int((k * step + jitter(r, 2)) * SR) if k else 0; i = max(0, i)
        tick = (S.bp(_noise(m, r), f * 0.7, f * 1.5) * S.expdecay(m, 0.003) + 0.5 * np.sin(TAU * f * 0.45 * np.arange(m) / SR) * S.expdecay(m, 0.008)) * r.uniform(0.8, 1.0)
        x[i:i + m] += tick[:max(0, min(m, n - i))]; k += 1
    return _norm(x, vol)


def projector(d, vol=0.2, rng=None):
    """a 16 mm film projector: motor hum, gate flutter at 24 fps, a little rattle"""
    r = _g(rng); n = int(SR * d); t = np.arange(n) / SR; hum = np.sin(TAU * 50 * t) + 0.5 * np.sin(TAU * 100 * t) + 0.25 * np.sin(TAU * 150 * t)
    flutter = np.zeros(n); step = int(SR / 24)
    for i in range(0, n - 200, step):
        k = min(200, n - i); flutter[i:i + k] += S.bp(_noise(k, r), 600, 3500)[:k] * np.exp(-np.arange(k) / 40.0) * r.uniform(0.7, 1.0)
    return _norm(0.5 * hum + 1.2 * flutter + 0.12 * S.bp(_noise(n, r), 3000, 8000), vol) * np.minimum(1, t / 0.2) * np.clip(np.minimum(1, (d - t) / 0.2), 0, 1)


def tape_hiss(d, vol=0.05, rng=None):
    r = _g(rng); n = int(SR * d); return _norm(S.hp(_noise(n, r), 2500, 1) * (1 + 0.3 * np.sin(TAU * 0.4 * np.arange(n) / SR)), vol)


def wind(d, vol=0.2, rng=None):
    """wind: noise through a slowly wandering low-pass, with gusts"""
    r = _g(rng); n = int(SR * d); t = np.arange(n) / SR; cut = 250 + 700 * (0.5 + 0.5 * np.sin(TAU * r.uniform(0.05, 0.14) * t + r.uniform(0, 6.28)))
    gust = 0.55 + 0.45 * np.sin(TAU * r.uniform(0.07, 0.2) * t + r.uniform(0, 6.28)) ** 2
    return _norm(S.lp(_noise(n, r), cut, 2) * gust, vol) * np.minimum(1, t / 1.5) * np.clip(np.minimum(1, (d - t) / 1.5), 0, 1)


def prop_drone(d, vol=0.25, rpm=2400, blades=3, rng=None):
    """a propeller aircraft / engine: the blade-pass frequency (rpm * blades / 60) and its harmonics, two engines beating, with a little drift and air noise"""
    r = _g(rng); n = int(SR * d); t = np.arange(n) / SR; f0 = rpm * blades / 60.0; x = np.zeros(n)
    for eng in (0.0, r.uniform(0.7, 2.2)):
        f = (f0 + eng) * (1 + 0.004 * np.sin(TAU * r.uniform(0.1, 0.4) * t + r.uniform(0, 6.28)))
        for k in range(1, 14): x += np.sin(_phase(f * k) + r.uniform(0, 6.28)) / k ** 1.15
    x = S.lp(x, 2400, 2) + 0.12 * S.bp(_noise(n, r), 300, 2500)
    return _norm(x, vol) * np.minimum(1, t / 0.8) * np.clip(np.minimum(1, (d - t) / 0.8), 0, 1)


def rumble(d, vol=0.3, rng=None):
    r = _g(rng); n = int(SR * d); t = np.arange(n) / SR; return _norm(S.lp(_noise(n, r), 70, 2) * (0.6 + 0.4 * np.sin(TAU * r.uniform(0.2, 0.5) * t)), vol) * np.minimum(1, t / 1.0) * np.clip(np.minimum(1, (d - t) / 1.0), 0, 1)


# ───────────────────────── risers ─────────────────────────
def shepard(d, vol=0.2, up=True, base=110):
    """a Shepard tone: an endless rising (or falling) glissando - the classic 'it keeps getting more tense' sound"""
    n = int(SR * d); t = np.arange(n) / SR; x = np.zeros(n); nv = 7; rate = 1.0 / d * (1 if up else -1)
    for k in range(nv):
        pos = ((k / nv) + rate * t) % 1.0; f = base * 2 ** (pos * nv); amp = np.sin(np.pi * pos) ** 2; x += amp * np.sin(_phase(f))
    return _norm(x, vol) * np.minimum(1, t / 0.3) * np.clip(np.minimum(1, (d - t) / 0.15), 0, 1)


def _sweep(r, d):
    with _borrow(r): return S.noise_sweep(d, 300, 7000, 1.0, True)


def pitch_riser(d, vol=0.3, rng=None):
    """a saw sweeping up through an opening filter, doubled an octave up, with a noise bed - a 'melodic' riser (vs synth.riser's pure noise)"""
    r = _g(rng); n = int(SR * d); t = np.arange(n) / SR; f = np.geomspace(r.uniform(70, 110), r.uniform(700, 1100), n)
    x = signal.sawtooth(_phase(f)) + 0.5 * signal.sawtooth(_phase(f * 2.005)); x = S.lp(x, np.geomspace(300, 8000, n), 2) + 0.25 * _sweep(r, d)[:n]
    return _norm(x, vol) * (t / d) ** 1.8 * np.clip(np.minimum(1, (d - t) / 0.02), 0, 1)


# ───────────────────────── rooms ─────────────────────────
_ROOMS = {  # (length s, decay rate, predelay s, lowpass Hz, early-reflection count)
    'chamber': (1.6, 3.6, 0.008, 5200, 6), 'hall': (2.8, 1.9, 0.02, 4600, 8), 'cathedral': (4.2, 1.1, 0.035, 3600, 5), 'plate': (2.2, 2.6, 0.0, 9000, 0),
    'tin': (1.5, 3.2, 0.004, 7800, 10), 'tape': (1.7, 3.0, 0.0, 3000, 3)}


def room(kind='chamber', seed=7):
    """a stereo impulse response of a given character, deterministic per (kind, seed).  Always >= 1.3 s long (master() slices the voice room from it)"""
    ln, dec, pre, cut, er = _ROOMS[kind]; r = np.random.default_rng(seed_of('room', kind, seed)); n = int(ln * SR); t = np.arange(n) / SR
    ir = (r.standard_normal((2, n)) * np.exp(-t * dec)) * (1 - np.exp(-t * 90)); ir = np.stack([S.lp(ir[0], cut, 1), S.lp(ir[1], cut, 1)])
    for _ in range(er):
        i = int(r.uniform(0.004, 0.06) * SR); ir[r.integers(0, 2), i] += r.uniform(0.5, 1.5)
    if kind == 'tape': ir[:, int(0.11 * SR)] += 0.8; ir[:, int(0.22 * SR)] += 0.45                          # slap echoes
    if pre: ir = np.concatenate([np.zeros((2, int(pre * SR))), ir], 1)
    if ir.shape[1] < int(1.5 * SR): ir = np.concatenate([ir, np.zeros((2, int(1.5 * SR) - ir.shape[1]))], 1)
    return ir


def use_room(kind='chamber', seed=7):
    """make synth.master() use this room's reverb (call once, anywhere before master())"""
    S.ROOM = room(kind, seed)


# ───────────────────────── palette ─────────────────────────
MOODS = {
    'grave':   dict(modes=['aeolian', 'phrygian', 'dorian'], roots=(31, 41), pad=['strings', 'bowed', 'choir', 'organ'], bell=['glass', 'fm', 'musicbox', 'vibes'], pulse=['heartbeat', 'frame_drum', 'clock'], hit=['stamp', 'taiko', 'gong'], prog=[[0, 5, 3, 4], [0, 3, 6, 4], [0, 4, 5, 3]], bright=0.55),
    'eerie':   dict(modes=['locrian', 'phrygian_dominant', 'whole_tone'], roots=(33, 44), pad=['glass', 'choir', 'strings'], bell=['musicbox', 'glass', 'fm'], pulse=['clock', 'geiger', 'heartbeat'], hit=['gong', 'anvil', 'stamp'], prog=[[0, 1, 0, 6], [0, 4, 1, 5], [0, 2, 4, 1]], bright=0.7),
    'wonder':  dict(modes=['lydian', 'mixolydian', 'ionian'], roots=(36, 46), pad=['strings', 'glass', 'organ', 'choir'], bell=['glass', 'vibes', 'fm', 'wood'], pulse=['frame_drum', 'clock', 'heartbeat'], hit=['taiko', 'gong', 'stamp'], prog=[[0, 4, 5, 3], [0, 3, 4, 0], [0, 1, 4, 3]], bright=1.0),
    'tense':   dict(modes=['phrygian', 'harmonic_minor', 'locrian'], roots=(31, 40), pad=['strings', 'bowed', 'organ'], bell=['metal', 'fm', 'musicbox'], pulse=['clock', 'geiger', 'heartbeat', 'frame_drum'], hit=['anvil', 'taiko', 'stamp'], prog=[[0, 1, 0, 5], [0, 5, 4, 1], [0, 3, 1, 0]], bright=0.8),
    'warm':    dict(modes=['ionian', 'mixolydian', 'dorian'], roots=(38, 48), pad=['strings', 'organ', 'glass'], bell=['vibes', 'wood', 'glass', 'musicbox'], pulse=['frame_drum', 'clock'], hit=['stamp', 'gong', 'taiko'], prog=[[0, 3, 4, 0], [0, 5, 3, 4], [0, 4, 5, 3]], bright=0.9),
    'machine': dict(modes=['dorian', 'minor_pentatonic', 'aeolian'], roots=(33, 43), pad=['organ', 'glass', 'strings'], bell=['metal', 'fm', 'wood'], pulse=['clock', 'geiger', 'frame_drum'], hit=['anvil', 'stamp', 'taiko'], prog=[[0, 0, 3, 4], [0, 2, 3, 5], [0, 4, 0, 6]], bright=0.75),
}


class Palette:
    """a film's sonic identity, derived from a seed: key, mode, and which instrument plays each role (pad, bell, pulse, hit).  Same seed = same palette; any other seed = a different one.
    P.rng(name) hands out a NEW generator for every call with the same name, so repeated hits are never identical but always reproducible."""

    def __init__(self, seed, mood='grave', root=None, mode=None, episode=None, **voices):
        """episode: the film's number in a series.  With it, each role cycles through its instrument list in order (offset by the seed), so CONSECUTIVE films can never use the
        same instrument for the same role (pad, bell, pulse, hit all change every episode).  Without it the choice is a seeded random pick (two seeds can collide by chance)."""
        self.seed = seed if isinstance(seed, int) else seed_of(seed); self.mood = mood; m = MOODS[mood]; r = np.random.default_rng(self.seed)
        self.root = int(root if root is not None else r.integers(m['roots'][0], m['roots'][1])); self.mode = mode or str(r.choice(m['modes'])); self.scale = MODES[self.mode]
        pick = lambda k: str(r.choice(m[k])) if episode is None else m[k][(seed_of('role', k) + int(episode)) % len(m[k])]
        self.voice = {k: voices.get(k) or pick(k) for k in ('pad', 'bell', 'pulse', 'hit')}; self.prog = [list(p) for p in m['prog']][int(r.integers(0, len(m['prog'])))]
        self.bright = m['bright']; self.count = {}; self.vowel = str(r.choice(list('aouae')))

    def __repr__(self): return 'Palette(%s, root=%d %s, %s)' % (self.mood, self.root, self.mode, self.voice)

    def rng(self, name='x'):
        k = self.count.get(name, 0); self.count[name] = k + 1; return np.random.default_rng([self.seed, seed_of(name), k])

    def note(self, degree, octave=0): return scale_note(self.root, self.mode, degree) + 12 * octave

    def chord(self, degree, size=3, octave=0):
        """stacked thirds in the mode on a degree (size 2 = open fifth-ish, 3 = triad, 4 = seventh)"""
        return [self.note(degree + 2 * i, octave) for i in range(size)]

    # --- role instruments (the palette's choice, new variation every call) ---
    def pad(self, ms, d, vol=0.15, swell=1.5):
        r = self.rng('pad'); v = self.voice['pad']
        if v == 'strings': return strings(ms, d, vol, swell, r, self.bright)
        if v == 'choir': return choir(ms, d, vol, self.vowel, swell, r)
        if v == 'organ': return organ(ms, d, vol, r) * np.minimum(1, S.tt(d) / swell) ** 0.5
        if v == 'glass': return glass(ms, d, vol, r)
        x = sum(bowed(m, d, vol / max(1, len(ms)) * 1.4, r) for m in ms)                                   # bowed
        return x

    def bell(self, m, d=1.6, vol=0.2):
        r = self.rng('bell'); v = self.voice['bell']
        if v == 'fm': return fm_bell(m, d, vol, r)
        return mallet(m, d, vol, v, r)

    def hit(self, vol=0.8):
        r = self.rng('hit'); v = self.voice['hit']
        return {'stamp': lambda: stamp(vol, r), 'taiko': lambda: taiko(vol, r), 'gong': lambda: gong(3.5, vol * 0.7, r), 'anvil': lambda: anvil(vol, r)}[v]()

    def pulse(self, vol=0.4):
        """one beat of the palette's pulse instrument (clock tick, heartbeat, drum): place it repeatedly with growing vol/tempo for tension"""
        r = self.rng('pulse'); v = self.voice['pulse']
        if v == 'heartbeat': return heartbeat(vol, r)
        if v == 'frame_drum': return frame_drum(vol, r)
        if v == 'geiger': return geiger(0.4, 18, vol * 0.5, r)
        return clock(0.12, 60, vol * 0.6, r)

    def bass(self, m, d, vol=0.25):
        while m < 33: m += 12                                                                           # never below A1 (55 Hz): lower is energy without pitch
        r = self.rng('bass'); return bowed(m, d, vol, r) if self.voice['pad'] in ('strings', 'bowed', 'choir') else drone(m, d, vol, r)

    def motif(self, length=5, octave=1):
        """a short melodic cell in the mode, as (degree, beats) - always starts on the root/3rd/5th and ends on a stable degree, shape from the seed"""
        r = self.rng('motif'); deg = [int(r.choice([0, 2, 4]))]
        for _ in range(length - 2): deg.append(max(-2, min(9, deg[-1] + int(r.choice([-2, -1, 1, 1, 2, 3])))))
        deg.append(int(r.choice([0, 2, 4])) + (7 if r.random() < 0.3 else 0)); return [(d, float(r.choice([1, 1, 2, 3]))) for d in deg]

    def bed(self, a, b, intensity=0.5, vol=0.14, chord_len=(5.0, 9.0), notes=True, bass=True, send=0.5):
        """compose and place a generative bed from time a to b: a chord progression from the mood (changing every `chord_len` s, voice-led), a bass note on each root,
        and (if `notes`) sparse motif notes from the bell voice.  intensity 0..1 = how thick/loud/busy (more chord tones, more notes).  Call it per section with a different intensity/mood
        (e.g. grave bed, then P2 = Palette(seed, 'warm') for the resolution).  Everything is placed with synth.add()."""
        r = self.rng('bed'); t = a; k = int(r.integers(0, len(self.prog))); prev = None; size = 2 if intensity < 0.25 else (3 if intensity < 0.75 else 4)
        while t < b - 0.5:
            d = min(b - t, float(r.uniform(*chord_len))) + 1.2; deg = self.prog[k % len(self.prog)]; ch = self.chord(deg, size, 0)
            if prev:                                                                                   # voice-leading: move each tone the shortest way
                ch = [min((c + 12 * o for o in (-1, 0, 1)), key=lambda x, p=p: abs(x - p)) for c, p in zip(ch, prev)]
            ch = [c + 12 if c < self.root + 10 else c for c in ch]; ch = [c - 12 if c > self.root + 28 else c for c in ch]; prev = ch
            S.add(self.pad(ch, d, vol * (0.55 + 0.9 * intensity), swell=min(2.5, d * 0.45)), t, 1, float(r.uniform(-0.15, 0.15)), send, name='bed-pad')
            if bass: S.add(self.bass(self.root - 12 + (self.note(deg) - self.root), d, vol * (0.7 + 0.5 * intensity) * 0.9), t, 1, 0, send * 0.4, name='bed-bass')
            if notes and intensity > 0.2:
                m = self.motif(); tt_ = t + float(r.uniform(0.8, 2.0)); step = 0.55 - 0.3 * intensity
                for degr, beats in m:
                    if tt_ > min(b - 1.0, t + d - 1.0): break
                    if r.random() < 0.35 + 0.5 * intensity: S.add(self.bell(self.note(degr, 2), 1.8, vol * (0.55 + 0.4 * intensity)), tt_, 1, float(r.uniform(-0.5, 0.5)), 0.6, name='bed-note')
                    tt_ += beats * step * float(r.uniform(0.9, 1.15))
            t += d - 1.2; k += 1
