#!/usr/bin/env python3
"""Tests for tools/clip.py: filter building + a real scan/cut on a synthetic ffmpeg video. Run by tests/shorts.js."""
import os, sys, json, subprocess, tempfile, shutil, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..'))
spec = importlib.util.spec_from_file_location('clip', os.path.join(REPO, 'tools', 'clip.py'))
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
def eq(a, b, msg=''): assert a == b, f'{msg}: expected {b!r}, got {a!r}'

eq(C.fmt_ts(0), '0:00.0'); eq(C.fmt_ts(75.25), '1:15.2'); eq(C.fmt_ts(3600 + 5), '60:05.0')
eq(C.parse_crop('640:360:0:60'), (640, 360, 0, 60)); eq(C.parse_crop(None), None)
try: C.parse_crop('1:2:3'); raise SystemExit('bad crop accepted')
except ValueError: pass
vf = C.build_filter(fps=24, crop=(640, 360, 0, 60), scale=2, deint=True, denoise=2, sharpen=True)
for part in ('yadif', 'crop=640:360:0:60', 'hqdn3d', 'scale=iw*2:ih*2', 'lanczos', 'unsharp', 'fps=24'):
    assert part in vf, (part, vf)
assert 'yadif' not in C.build_filter(fps=24), 'no deinterlace unless asked'
iv = C.build_filter(ivtc=True, scale=1.5); assert iv.startswith('fieldmatch,yadif=deint=interlaced,decimate'), iv; assert 'yadif=0' not in iv, 'ivtc replaces plain deinterlacing'
assert vf.index('crop=') < vf.index('scale='), 'crop before scale'

# ---- real ffmpeg round trip on a synthetic clip -------------------------------------------------------------------------
P = os.path.join(REPO, 'projects', '_cliptest'); OUT = os.path.join(REPO, 'out', '_cliptest')
shutil.rmtree(P, ignore_errors=True); shutil.rmtree(OUT, ignore_errors=True); os.makedirs(os.path.join(P, 'raw'))
try:
    src = os.path.join(P, 'raw', 'src.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=25:duration=4', '-pix_fmt', 'yuv420p', src], check=True)
    info = C.probe(src); eq((info['w'], info['h']), (320, 240)); assert abs(info['fps'] - 25) < 0.01 and abs(info['duration'] - 4) < 0.1, info
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'clip.py'), 'cut', P, 'raw/src.mp4', '--id', 'a', '--start', '1', '--end', '2.5', '--scale', '2'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    meta = json.load(open(os.path.join(P, 'assets', 'clips', 'a', 'clip.json')))
    eq(meta['fps'], 25, 'fps is the source rate by default'); assert abs(meta['n'] - 37) <= 1, meta   # 1.5 s * 25
    eq((meta['w'], meta['h']), (640, 480), 'scaled 2x'); eq(meta['pattern'], '%05d.jpg')
    files = sorted(f for f in os.listdir(os.path.join(P, 'assets', 'clips', 'a')) if f.endswith('.jpg')); eq(len(files), meta['n'], 'frame files match clip.json'); eq(files[0], '00001.jpg')
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'clip.py'), 'cut', P, 'raw/src.mp4', '--id', 'b', '--start', '3', '--end', '9'], capture_output=True, text=True)
    assert r.returncode == 0 and 'clamped' in r.stdout, 'a range past the end is clamped and says so: ' + r.stdout + r.stderr
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'clip.py'), 'scan', P, 'raw/src.mp4', '--every', '1', '--cols', '2'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    sheets = [f for f in os.listdir(os.path.join(OUT, 'scan')) if f.endswith('.jpg')]; assert sheets, 'scan wrote a contact sheet'
    from PIL import Image
    im = Image.open(os.path.join(OUT, 'scan', sheets[0])); assert im.width > 300 and im.height > 100, im.size
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'clip.py'), 'cut', P, 'raw/src.mp4', '--id', 'c', '--start', '5', '--end', '6'], capture_output=True, text=True)
    assert r.returncode != 0 and 'beyond' in (r.stdout + r.stderr), 'a range wholly past the end must fail clearly'
    # inverse telecine: a 24 fps film put through 3:2 pulldown comes back as 24 (23.976) clean frames per second, not 29.97
    tel = os.path.join(P, 'raw', 'tel.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=24000/1001:duration=6', '-vf', 'telecine=pattern=23,setfield=tff', '-flags', '+ilme+ildct', '-pix_fmt', 'yuv420p', tel], check=True)
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'clip.py'), 'cut', P, 'raw/tel.mp4', '--id', 'iv', '--start', '1', '--end', '4', '--ivtc'], capture_output=True, text=True); assert r.returncode == 0, r.stdout + r.stderr
    m = json.load(open(os.path.join(P, 'assets', 'clips', 'iv', 'clip.json'))); assert abs(m['fps'] - 23.976) < 0.01, m; assert abs(m['n'] - 3 * 23.976) <= 3, ('3 s of film should be ~72 frames, not ~90', m['n'])
    # labels must be the frames' REAL times even when the file does not start at 0 (the DOE film starts at 0.997 s and the labels drifted by ~0.6 s)
    flip = os.path.join(P, 'raw', 'flip.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=black:s=160x120:r=25:d=1.5', '-f', 'lavfi', '-i', 'color=white:s=160x120:r=25:d=1.5', '-filter_complex', '[0][1]concat=n=2:v=1:a=0,setpts=PTS+1.0/TB[v]', '-map', '[v]', '-pix_fmt', 'yuv420p', '-muxdelay', '0', flip], check=True)
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        got = C.scan_frames(flip, 0.0, 3.0, 0.5, 80, tmp); assert len(got) >= 5, got
        for t, path in got:
            from PIL import ImageStat; lum = ImageStat.Stat(Image.open(path).convert('L')).mean[0]
            expect_white = t >= 1.5 - 0.02
            assert (lum > 128) == expect_white, ('label %.2f says %s but the frame is %s (luma %.0f)' % (t, 'white' if expect_white else 'black', 'white' if lum > 128 else 'black', lum))
        assert abs(got[1][0] - got[0][0] - 0.5) < 0.06, 'spacing is ~every seconds: %s' % [round(t, 2) for t, _ in got]
    print('ok')
finally:
    shutil.rmtree(P, ignore_errors=True); shutil.rmtree(OUT, ignore_errors=True)
