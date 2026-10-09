#!/usr/bin/env python3
"""key-check.py - does the score stay in tune and in key?  Numbers instead of ears.

  python3 tools/key-check.py out/x/score.wav --key A --mode ionian [--window 5] [--sections hit,how,ledger] [--cues projects/x/cues.json] [--events out/x/score.events.json]
                                                                  [--fail-off 0.12] [--fail-cents 0.2] [--json]

You cannot listen, but you can look at what the spectrum says.  For every window (default 5 s, or the spans between named cues) it finds the tonal peaks (60-2000 Hz, at least 12 dB over
the local floor), converts each to a fractional MIDI note, and reports, weighted by peak energy:
  off-scale  share of tonal energy on pitch classes that are NOT in --key/--mode (an 'ominous' or 'sour' score shows up here: a minor third in a major score, a gliding sine, a bell with an
             inharmonic partial, two sections in different keys)
  out-of-tune  share of tonal energy more than 25 cents from the nearest semitone (a sine glide, a detuned sample, a gong), and
  cents      the energy-weighted mean offset (negative = flat), so a systematically flat score is visible
plus the loudest-band split (sub <80 Hz / low 80-250 / mid 250-2k / high >2k as % of energy), RMS in dBFS, and, with --events (score.events.json from synth.master), how many sounds start per second.
Percussion and noise leave a few spurious peaks, so read the numbers as a comparison between versions and as a gate (--fail-off X: exit 1 if the whole film's off-scale share is over X).
Typical: a clean diatonic synth score is 3-10 % off-scale; a score that mixes dorian, aeolian and ionian pads, gliding sines and inharmonic bells is 20-35 %."""
import json, os, sys, wave
import numpy as np
from scipy import signal

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, os.path.join(REPO, 'lib'))
from sonic import MODES

NAMES = {'C': 0, 'C#': 1, 'DB': 1, 'D': 2, 'D#': 3, 'EB': 3, 'E': 4, 'F': 5, 'F#': 6, 'GB': 6, 'G': 7, 'G#': 8, 'AB': 8, 'A': 9, 'A#': 10, 'BB': 10, 'B': 11}
NFFT, HOP = 8192, 4096


def read_wav(path):
    with wave.open(path, 'rb') as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), '<i2').astype(np.float64) / 32768
    return (x.reshape(-1, ch).mean(1) if ch > 1 else x), sr


def scale_pcs(key, mode):
    k = NAMES[key.upper()] if isinstance(key, str) else int(key) % 12
    return {(k + s) % 12 for s in MODES[mode]}


def tonal_peaks(x, sr, pcs, lo=60.0, hi=2000.0):
    """-> dict with energy-weighted stats over the whole signal x: {'w': total weight, 'off': weight off-scale, 'bad': weight >25 cents out, 'cents': sum(w*cents)}"""
    out = {'w': 0.0, 'off': 0.0, 'bad': 0.0, 'cents': 0.0, 'peaks': 0}
    if len(x) < NFFT: return out
    win = np.hanning(NFFT); fr = np.fft.rfftfreq(NFFT, 1 / sr); sel = (fr >= lo) & (fr <= hi)
    for i in range(0, len(x) - NFFT + 1, HOP):
        mag = np.abs(np.fft.rfft(x[i:i + NFFT] * win))[sel]; f = fr[sel]
        if mag.max() < 1e-4: continue
        floor = signal.medfilt(mag, 101) + 1e-9
        pk, _ = signal.find_peaks(mag, height=mag.max() * 0.02)
        for p in pk:
            if p < 1 or p >= len(mag) - 1 or mag[p] < 4 * floor[p]: continue
            a, b, c = np.log(mag[p - 1] + 1e-12), np.log(mag[p] + 1e-12), np.log(mag[p + 1] + 1e-12)
            d = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0                    # parabolic interpolation of the true peak
            fh = f[p] + d * (f[1] - f[0]); m = 69 + 12 * np.log2(fh / 440.0); r = round(m); cents = (m - r) * 100; w = float(mag[p]) ** 2
            out['w'] += w; out['cents'] += w * cents; out['peaks'] += 1
            if int(r) % 12 not in pcs: out['off'] += w
            if abs(cents) > 25: out['bad'] += w
    return out


def bands(x, sr):
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2; fr = np.fft.rfftfreq(len(x), 1 / sr); t = sp.sum() + 1e-18
    return [100 * sp[(fr >= a) & (fr < b)].sum() / t for a, b in ((0, 80), (80, 250), (250, 2000), (2000, 1e9))]


def analyse(x, sr, spans, pcs, events=None):
    rows = []
    for name, a, b in spans:
        seg = x[int(a * sr):int(b * sr)]
        if len(seg) < sr * 0.5: continue
        s = tonal_peaks(seg, sr, pcs); w = max(s['w'], 1e-18)
        ev = [e for e in (events or []) if a <= e['t'] < b and not str(e.get('name') or '').startswith('bed')]
        rows.append({'name': name, 't0': round(a, 2), 't1': round(b, 2), 'rms_db': round(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12), 1), 'off': round(s['off'] / w, 3),
                     'out_of_tune': round(s['bad'] / w, 3), 'cents': round(s['cents'] / w, 1), 'bands': [round(v) for v in bands(seg, sr)], 'sounds_per_s': round(len(ev) / (b - a), 2) if events is not None else None,
                     'tonal': s['peaks']})
    return rows


def main(argv):
    opt = {'--key': 'A', '--mode': 'ionian', '--window': '5', '--sections': '', '--cues': '', '--events': '', '--fail-off': '', '--fail-cents': ''}
    args = []; i = 0
    while i < len(argv):
        if argv[i] in opt: opt[argv[i]] = argv[i + 1]; i += 2
        elif argv[i] == '--json': opt['--json'] = '1'; i += 1
        else: args.append(argv[i]); i += 1
    if not args or args[0] in ('-h', '--help'): print(__doc__); return 0 if args else 2
    if opt['--key'].upper() not in NAMES or opt['--mode'] not in MODES: print('unknown --key/--mode (keys: %s; modes: %s)' % (' '.join(NAMES), ' '.join(MODES))); return 2
    x, sr = read_wav(args[0]); dur = len(x) / sr; pcs = scale_pcs(opt['--key'], opt['--mode'])
    if opt['--sections']:
        cues = json.load(open(opt['--cues'])); names = [s for s in opt['--sections'].split(',') if s]
        spans = [(n, cues[n], cues[names[k + 1]] if k + 1 < len(names) else dur) for k, n in enumerate(names)]
    else:
        w = float(opt['--window']); spans = [('%gs' % (k * w), k * w, min(dur, (k + 1) * w)) for k in range(int(np.ceil(dur / w)))]
    events = json.load(open(opt['--events']))['events'] if opt['--events'] else None
    rows = analyse(x, sr, spans, pcs, events); whole = analyse(x, sr, [('ALL', 0, dur)], pcs, events)[0]
    if '--json' in opt: print(json.dumps({'rows': rows, 'all': whole}, indent=1))
    else:
        print('%s  key %s %s  (%d s)' % (args[0], opt['--key'], opt['--mode'], dur))
        print('%-10s %12s %7s %8s %9s %7s   %-17s %s' % ('section', 'span', 'rms dB', 'off-key', 'out-tune', 'cents', 'sub/low/mid/high%', 'sounds/s'))
        for r in rows + [whole]:
            print('%-10s %5.1f-%-6.1f %7.1f %7.0f%% %8.0f%% %7.1f   %-17s %s' % (r['name'], r['t0'], r['t1'], r['rms_db'], 100 * r['off'], 100 * r['out_of_tune'], r['cents'], '/'.join(map(str, r['bands'])), r['sounds_per_s'] if r['sounds_per_s'] is not None else '-'))
    bad = []
    if opt['--fail-off'] and whole['off'] > float(opt['--fail-off']): bad.append('off-key share %.0f%% > %.0f%%' % (100 * whole['off'], 100 * float(opt['--fail-off'])))
    if opt['--fail-cents'] and whole['out_of_tune'] > float(opt['--fail-cents']): bad.append('out-of-tune share %.0f%% > %.0f%%' % (100 * whole['out_of_tune'], 100 * float(opt['--fail-cents'])))
    if bad: print('FAIL: ' + '; '.join(bad)); return 1
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
