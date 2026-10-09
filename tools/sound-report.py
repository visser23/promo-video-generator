#!/usr/bin/env python3
"""sound-report.py - do my films all sound the same?  Numbers instead of ears.

  python3 tools/sound-report.py out/a/score.events.json [out/b/score.events.json ...] [--threshold 0.98] [--fail-above 0.6] [--json]

lib/synth.py logs a small spectral fingerprint of EVERY sound a score places (add()) and master() writes it to <score>.events.json.  This tool compares them:
  * within one film   - how many sounds are near-identical to another sound in the same film ("twins"), and how many DISTINCT timbres the film really has;
  * across films      - what share of film B's sounds have a twin in film A (the "same noises in every video" effect), for every ordered pair.
A fingerprint is a 16-band log-spectrum of the first 0.4 s, level-independent, so 'cosine >= 0.98' means 'same instrument/sample, just louder or quieter'.
Typical numbers: two films built with the same seed and the same few instruments share 70-90 % of their sounds; a film that uses lib/sonic.py palettes with different seeds shares well under 30 %.
--fail-above X  exit 1 if the share of a film's sounds that have a twin in an EARLIER film (arguments are in chronological order) exceeds X (CI guard for a channel).
Ticks/clicks that are meant to repeat (a typewriter, a clock, a geiger counter) are fine: judge the cross-film figure and the number of distinct timbres first."""
import json, os, sys
import numpy as np


def load_events(path):
    """events with a fingerprint, from a *.events.json written by synth.master()"""
    with open(path) as f: d = json.load(f)
    return [e for e in d['events'] if e.get('fp')]


def _mat(events): return np.array([e['fp'] for e in events], dtype=float) if events else np.zeros((0, 16))


def twin_ratio(events, threshold=0.98):
    """share of events that have another event in the same film with cosine similarity >= threshold"""
    m = _mat(events)
    if len(m) < 2: return 0.0
    s = m @ m.T; np.fill_diagonal(s, -1)
    return float((s.max(1) >= threshold).mean())


def clusters(events, threshold=0.98):
    """greedy timbre clusters: list of lists of event indices (the first member is the cluster's exemplar)"""
    m = _mat(events); out = []; ex = []
    for i in range(len(m)):
        for k, j in enumerate(ex):
            if float(m[i] @ m[j]) >= threshold: out[k].append(i); break
        else: ex.append(i); out.append([i])
    return out


def shared_ratio(b, a, threshold=0.98):
    """share of film b's sounds that have a twin in film a"""
    mb, ma = _mat(b), _mat(a)
    if not len(mb) or not len(ma): return 0.0
    return float(((mb @ ma.T).max(1) >= threshold).mean())


def summarize(path, events, threshold):
    cl = clusters(events, threshold); big = sorted(cl, key=len, reverse=True)[:3]
    print('%s: %d sounds, %d distinct timbres, %.0f%% have a twin inside the film' % (path, len(events), len(cl), 100 * twin_ratio(events, threshold)))
    for c in big:
        if len(c) > 2:
            names = sorted({events[i].get('name') or '?' for i in c}); ts = [events[i]['t'] for i in c]
            print('    x%-3d %-28s first at %.1fs, last at %.1fs' % (len(c), '/'.join(names)[:28], min(ts), max(ts)))


def main(argv):
    th = 0.98; fail = None; as_json = '--json' in argv; args = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--threshold': th = float(argv[i + 1]); i += 1
        elif a == '--fail-above': fail = float(argv[i + 1]); i += 1
        elif not a.startswith('--'): args.append(a)
        i += 1
    if not args: print(__doc__); return 2
    films = []
    for p in args:
        if not os.path.exists(p): print('missing: ' + p); return 2
        films.append((p, load_events(p)))
    rep = {'threshold': th, 'films': [], 'shared': []}
    for p, ev in films:
        if not as_json: summarize(p, ev, th)
        rep['films'].append({'path': p, 'sounds': len(ev), 'timbres': len(clusters(ev, th)), 'twin_inside': twin_ratio(ev, th)})
    worst = 0.0
    for j in range(1, len(films)):
        for k in range(j):
            r = shared_ratio(films[j][1], films[k][1], th); rep['shared'].append({'film': films[j][0], 'earlier': films[k][0], 'share': r}); worst = max(worst, r)
            if not as_json: print('  %.0f%% of the sounds in %s have a twin in %s' % (100 * r, films[j][0], films[k][0]))
    if as_json: print(json.dumps(rep, indent=1))
    if fail is not None and worst > fail:
        print("FAIL: %.0f%% of a film's sounds repeat an earlier film (limit %.0f%%). Use a different sonic.Palette seed/mood, swap instruments, or vary the hits." % (100 * worst, 100 * fail)); return 1
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
