#!/usr/bin/env python3
"""Unit tests for the pure helpers in tools/voiceover.py: emphasis markup and script-to-Whisper caption alignment. Run by tests/shorts.js."""
import os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('voiceover', os.path.join(HERE, '..', 'tools', 'voiceover.py'))
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)
def eq(a, b, msg=''): assert a == b, f'{msg}: expected {b!r}, got {a!r}'

# ---- markup: *emphasis* is shown in captions but never spoken ---------------------------------------------------------------
spoken, toks = V.strip_markup('Hans Bethe had calculated it was *almost* impossible.')
eq(spoken, 'Hans Bethe had calculated it was almost impossible.', 'asterisks are not spoken')
eq([t['t'] for t in toks], 'Hans Bethe had calculated it was almost impossible.'.split(), 'tokens keep punctuation')
eq([t['t'] for t in toks if t['emph']], ['almost'], 'one emphasised word')
spoken, toks = V.strip_markup('It would *burn the sky* tonight')
eq([t['t'] for t in toks if t['emph']], ['burn', 'the', 'sky'], 'multi-word emphasis')
eq(V.strip_markup('plain words')[0], 'plain words'); assert not any(t['emph'] for t in V.strip_markup('plain words')[1])

# punctuation glued to an emphasised word stays with it (no stray '?' token); emphasis may cover just part of a token
sp, tk = V.strip_markup('Would you have taken the *bet*? *Almost.* Then *New Mexico*, or all')
eq([t['t'] for t in tk], ['Would', 'you', 'have', 'taken', 'the', 'bet?', 'Almost.', 'Then', 'New', 'Mexico,', 'or', 'all'], 'punctuation stays attached')
eq([t['t'] for t in tk if t['emph']], ['bet?', 'Almost.', 'New', 'Mexico,'], 'emphasis flags')
eq(sp, 'Would you have taken the bet? Almost. Then New Mexico, or all', 'spoken text has no asterisks and normal spacing')

# ---- alignment ---------------------------------------------------------------------------------------------------------------
heard = [{'w': 'In', 'start': 10.0, 'end': 10.2}, {'w': '1945', 'start': 10.2, 'end': 10.9}, {'w': 'Fermi', 'start': 11.0, 'end': 11.3}, {'w': 'took', 'start': 11.3, 'end': 11.5}, {'w': 'bets', 'start': 11.5, 'end': 11.9}]
script = [{'t': w, 'emph': False} for w in 'In 1945, Fermi took bets.'.split()]
caps = V.align_captions(script, heard, 10.0, 11.9)
eq([c['t'] for c in caps], ['In', '1945,', 'Fermi', 'took', 'bets.'], 'script spelling and punctuation win')
eq([round(c['start'], 2) for c in caps], [10.0, 10.2, 11.0, 11.3, 11.5], 'times come from whisper')

# a misheard name still gets its own time (fuzzy match), and a word whisper dropped is interpolated between its neighbours
heard2 = [{'w': 'Before', 'start': 0.0, 'end': 0.4}, {'w': 'Fermie', 'start': 0.4, 'end': 0.9}, {'w': 'bets', 'start': 1.5, 'end': 1.9}]
script2 = [{'t': w, 'emph': False} for w in 'Before Enrico Fermi bets'.split()]
caps2 = V.align_captions(script2, heard2, 0.0, 1.9)
eq(len(caps2), 4); eq(caps2[2]['start'], 0.4, 'Fermi matched Fermie'); assert 0.4 <= caps2[1]['start'] <= caps2[2]['start'] or caps2[1]['start'] < caps2[2]['start'], caps2
for i in range(1, 4): assert caps2[i]['start'] >= caps2[i - 1]['start'], ('times must never go backwards', caps2)
for c in caps2: assert c['end'] >= c['start'], c

# emphasis survives alignment
sc3 = [{'t': 'it', 'emph': False}, {'t': 'burn', 'emph': True}]
caps3 = V.align_captions(sc3, [{'w': 'it', 'start': 0, 'end': .2}, {'w': 'burn', 'start': .2, 'end': .6}], 0, .6); eq([c['emph'] for c in caps3], [False, True])

# no heard words at all (alignment off, or whisper failed): spread evenly over the line so captions still work
caps4 = V.align_captions(script, [], 5.0, 10.0)
eq(len(caps4), 5); eq(round(caps4[0]['start'], 2), 5.0); assert abs(caps4[-1]['end'] - 10.0) < 1e-6, caps4
assert all(caps4[i]['start'] <= caps4[i + 1]['start'] for i in range(4)), 'even spread is monotonic'
# longer words take proportionally longer than short ones
cs = V.align_captions([{'t': 'a', 'emph': False}, {'t': 'extraordinarily', 'emph': False}], [], 0, 4.0)
assert (cs[1]['end'] - cs[1]['start']) > 3 * (cs[0]['end'] - cs[0]['start']), cs
print('ok')
