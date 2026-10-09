#!/usr/bin/env python3
"""Shorts starter score: voice (from out/<name>/vo) + a drone + a few cue-timed sounds.  Replace the blocks below with your film's moments.
   python3 tools/voiceover.py projects/<name> --align   then   python3 projects/<name>/sound.py   ->  out/<name>/score.wav"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'lib'))
from synth import *

C = load_cues(HERE); init(C['duration'])
VO = os.path.join(HERE, '..', '..', 'out', os.path.basename(HERE), 'vo')
if os.path.exists(os.path.join(VO, 'manifest.json')):
    for l in json.load(open(os.path.join(VO, 'manifest.json'))): add_voice(read_wav(os.path.join(VO, l['id'] + '.wav')), l['start'])
add(pad([38, 45, 50], C['duration'] - 0.5, 0.15, 2.0), 0.3, 1, 0, 0.5)                      # a low drone under everything
t = C['title']; add(boom(1.4, 0.45), 0.0, 1, 0, 0.5)                                         # a low hit on frame 0 (also the loop point)
for k, line in enumerate(t['lines']):
    for i, ch in enumerate(line):
        if ch != ' ': add(tick(0.2, 2100 + 450 * (i % 4)), t['in'] + 0.22 * k + i * 0.03, 1, -0.2, 0.06)
if C.get('flashAt'): add(boom(3.0, 1.0), C['flashAt'], 1, 0, 0.5); add(kick(1.0), C['flashAt'])
add(pop(88, 0.24), C['end']['ctaIn'], 1, 0.2, 0.5)
master(default_out(HERE), body=(1.0, C['duration'] - 1.0), target_rms=-15.0, ceiling=-3.0, duck_db=-8.0, voice_db=0.5, unit_reverb=True)   # ceiling -3: AAC adds ~2 dB of overshoot
