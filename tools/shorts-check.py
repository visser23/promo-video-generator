#!/usr/bin/env python3
"""shorts-check.py - does this mp4 meet what a YouTube Short needs?   python3 tools/shorts-check.py out/<name>/<name>.mp4
Checks (E = error, exit 1; W = warning): vertical or square (E), at most 3 minutes (E), has an audio stream (E), h264 + aac + yuv420p (W),
integrated loudness around -14 LUFS (W below -22 / above -9), true peak under -1 dBFS (W), a black first frame (W: it wastes the hook), tiny frame size (W).
It measures; it cannot tell you the film is good: still watch it."""
import os, sys, re, json, subprocess


def P(level, code, msg): return {'level': level, 'code': code, 'msg': msg}


def _probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate:format=duration,size', '-of', 'json', path], capture_output=True, text=True)
    if r.returncode: raise SystemExit('ffprobe failed on %s: %s' % (path, r.stderr.strip()))
    return json.loads(r.stdout)


def _loudness(path):
    r = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', path, '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True)
    i = re.findall(r'I:\s+(-?[\d.]+) LUFS', r.stderr); p = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', r.stderr)
    return (float(i[-1]) if i else None), (float(p[-1]) if p else None)


def _first_luma(path):
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-frames:v', '1', '-vf', 'scale=16:16,format=gray', '-f', 'rawvideo', '-'], capture_output=True)
    return sum(r.stdout) / len(r.stdout) if r.stdout else None


def check(path):
    """-> (facts, problems)"""
    d = _probe(path); v = next((s for s in d['streams'] if s['codec_type'] == 'video'), None); a = next((s for s in d['streams'] if s['codec_type'] == 'audio'), None)
    if not v: raise SystemExit('no video stream in ' + path)
    num, den = v['r_frame_rate'].split('/'); fps = float(num) / float(den) if float(den) else 0
    lufs, tp = _loudness(path) if a else (None, None)
    facts = {'width': int(v['width']), 'height': int(v['height']), 'duration': float(d['format']['duration']), 'fps': round(fps, 2), 'vcodec': v['codec_name'], 'pix_fmt': v.get('pix_fmt'),
             'has_audio': bool(a), 'acodec': a['codec_name'] if a else None, 'lufs': lufs, 'true_peak': tp, 'size_mb': round(int(d['format'].get('size', 0)) / 1e6, 2), 'first_luma': _first_luma(path)}
    out = []
    if facts['height'] < facts['width']: out.append(P('error', 'not-vertical', '%dx%d is landscape: a Short must be vertical (9:16) or square' % (facts['width'], facts['height'])))
    if facts['duration'] > 180: out.append(P('error', 'too-long', '%.1f s: a Short is at most 3 minutes' % facts['duration']))
    if not a: out.append(P('error', 'no-audio', 'no audio stream'))
    if min(facts['width'], facts['height']) < 720: out.append(P('warn', 'small', '%dx%d is small; 1080x1920 is the target' % (facts['width'], facts['height'])))
    if facts['vcodec'] != 'h264' or facts['pix_fmt'] != 'yuv420p': out.append(P('warn', 'codec', 'video is %s/%s; h264/yuv420p is the safe choice' % (facts['vcodec'], facts['pix_fmt'])))
    if a and facts['acodec'] != 'aac': out.append(P('warn', 'audio-codec', 'audio is %s; aac is the safe choice' % facts['acodec']))
    if lufs is not None:
        if lufs > -9: out.append(P('warn', 'too-loud', 'integrated loudness %.1f LUFS: YouTube will turn it down (target about -14)' % lufs))
        if lufs < -22: out.append(P('warn', 'too-quiet', 'integrated loudness %.1f LUFS: very quiet next to other Shorts (target about -14)' % lufs))
    if tp is not None and tp > -1.0: out.append(P('warn', 'true-peak', 'true peak %.1f dBFS: may clip after re-encoding (keep under -1)' % tp))
    if facts['first_luma'] is not None and facts['first_luma'] < 8: out.append(P('warn', 'black-start', 'first frame is black (mean luma %.1f): the hook starts at frame 0' % facts['first_luma']))
    return facts, out


def main(argv):
    if len(argv) != 1 or argv[0] in ('-h', '--help'): raise SystemExit(__doc__)
    if not os.path.isfile(argv[0]): raise SystemExit('shorts-check: no such file: %s' % argv[0])
    facts, ps = check(argv[0])
    print('%dx%d  %.2f s  %s fps  %s/%s  audio %s  %s LUFS  peak %s dBFS  %.1f MB  first-frame luma %s' % (facts['width'], facts['height'], facts['duration'], facts['fps'], facts['vcodec'], facts['pix_fmt'], facts['acodec'] or 'NONE',
          facts['lufs'], facts['true_peak'], facts['size_mb'], None if facts['first_luma'] is None else round(facts['first_luma'], 1)))
    for p in ps: print('%-5s %-12s %s' % (p['level'].upper(), p['code'], p['msg']))
    errs = [p for p in ps if p['level'] == 'error']; print('FAIL: %d error(s)' % len(errs) if errs else 'ok: %d warning(s)' % len(ps)); return 1 if errs else 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
