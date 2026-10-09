#!/usr/bin/env python3
"""lib/synth.py master(): the output must be true-peak safe (inter-sample peaks, not just sample peaks), because AAC/player resampling turns overshoots into clipping."""
import os, sys, subprocess, tempfile, re
import numpy as np
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, os.path.join(REPO, 'lib'))
import synth as S
from scipy import signal

def tp(x): return np.abs(signal.resample_poly(x, 4, 1, axis=0)).max()      # 4x oversampled peak, linear

# the limiter itself
ceil = 10 ** (-1 / 20)
quiet = 0.2 * np.sin(2 * np.pi * 440 * np.arange(44100) / 44100)[:, None] * np.ones((1, 2))
assert np.array_equal(S.limit_true_peak(quiet.copy(), ceil), quiet), 'a signal under the ceiling is untouched, bit for bit'
x = quiet.copy(); n0 = 30000; x[n0:n0 + 600] += 0.9 * np.sin(2 * np.pi * 9000 * np.arange(600) / 44100)[:, None]       # an overshoot, inter-sample content
x = np.clip(x, -0.89, 0.89) * 1.0                                                                                   # sample peak safe, true peak not
assert tp(x) > ceil * 1.01, 'fixture: sample-peak-safe but true-peak-unsafe (%.3f)' % tp(x)
y = S.limit_true_peak(x.copy(), ceil); assert tp(y) <= ceil * 1.005, (tp(y), ceil)
assert np.array_equal(y[:n0 - 4000], x[:n0 - 4000]) and np.array_equal(y[n0 + 4600:], x[n0 + 4600:]), 'only the neighbourhood of the overshoot is touched'
assert np.abs(y).max() <= 1.0 and y.shape == x.shape

# master(): a deliberately violent mix
S.init(3.0)
S.add(S.boom(1.8, 1.0), 0.5, 1, 0, 0.3); S.add(S.kick(1.0), 0.5); S.add(S.noise_sweep(1.0, 9000, 300, 1.0, False), 0.5)
with tempfile.TemporaryDirectory() as t:
    path = os.path.join(t, 'm.wav'); S.master(path, body=(0.3, 2.5), target_rms=-12.0)
    r = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', path, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True)
    peak = float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS', r.stderr)[-1]); assert peak <= -0.9, 'true peak %.2f dBTP (ffmpeg ebur128)' % peak
print('ok')
