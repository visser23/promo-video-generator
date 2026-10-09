#!/usr/bin/env python3
"""clip.py - choose shots from archival film and turn them into frame sequences a deterministic scene can step through.

  python3 tools/clip.py scan <project> <raw/file> [--every 2] [--cols 6] [--rows 5] [--width 300] [--from 0] [--to 120]
        contact sheets with a timestamp on every thumbnail -> out/<name>/scan/<file>_NN.jpg   (look at them, pick the shots, note the times)
  python3 tools/clip.py cut  <project> <raw/file> --id fireball --start 12.5 --end 18 [--fps 24] [--scale 2] [--crop W:H:X:Y]
        [--ivtc | --deint] [--denoise 2] [--no-sharpen] [--q 2]
        -> projects/<name>/assets/clips/<id>/00001.jpg ... and clip.json {id, fps, n, w, h, pattern}
  python3 tools/clip.py scenes <project> <raw/file> [--threshold 0.35]       # likely cut points (seconds)

Why frames and not a <video>: a scene must be a pure function of time. A <video> element seeks asynchronously and its decoder can land on a
neighbouring frame; a numbered JPEG sequence cannot (lib/footage.js maps t -> frame number).  Default fps is the source's own rate.
`--scale 2` upsamples with Lanczos + a light unsharp so 480p film is not mushy when it fills a phone screen; `--crop` cuts black bars / burnt-in
slates; `--ivtc` for film transferred to video with 3:2 pulldown (check: ffmpeg -vf idet shows TFF but `-vf fieldmatch,decimate` drops 1 frame in 5) gives clean 23.976 fps frames; `--deint` for genuinely interlaced video; `--denoise` is hqdn3d luma strength (0 = off)."""
import os, sys, re, json, math, shutil, subprocess, tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def fmt_ts(s):
    m, sec = divmod(float(s), 60); return f'{int(m)}:{int(sec):02d}.{int((sec - int(sec)) * 10)}'


def parse_crop(s):
    if not s: return None
    p = [int(x) for x in str(s).split(':')]
    if len(p) != 4: raise ValueError('--crop is W:H:X:Y')
    return tuple(p)


def build_filter(fps=None, crop=None, scale=1, deint=False, denoise=0, sharpen=False, ivtc=False):
    f = []
    if ivtc: f.append('fieldmatch,yadif=deint=interlaced,decimate')  # film that went through 3:2 pulldown -> its own 23.976 clean frames
    elif deint: f.append('yadif=0')
    if crop: f.append('crop=%d:%d:%d:%d' % crop)
    if denoise: f.append('hqdn3d=%s:%s:3:3' % (denoise, denoise))
    if fps: f.append('fps=%s' % fps)
    if scale and scale != 1: f.append('scale=iw*%s:ih*%s:flags=lanczos' % (scale, scale))
    if sharpen: f.append('unsharp=5:5:0.6:5:5:0.0')
    return ','.join(f) if f else 'null'


def run(cmd, **kw):
    if cmd[0] == 'ffmpeg': cmd = ['ffmpeg', '-nostdin'] + cmd[1:]  # never read the caller's stdin (it ate a `while read` loop)
    return subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, **kw)


def probe(path):
    r = run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,avg_frame_rate,r_frame_rate,field_order:format=duration', '-of', 'json', path])
    if r.returncode: raise SystemExit('ffprobe failed on %s: %s' % (path, r.stderr.strip()))
    d = json.loads(r.stdout); s = d['streams'][0]
    num, den = (s.get('avg_frame_rate') or s['r_frame_rate']).split('/'); fps = float(num) / float(den) if float(den) else 0
    return {'w': int(s['width']), 'h': int(s['height']), 'fps': round(fps, 3), 'duration': float(d['format']['duration']), 'field_order': s.get('field_order', 'unknown')}


def flag(name, default=None):
    a = sys.argv
    if '--' + name in a:
        i = a.index('--' + name); return a[i + 1] if i + 1 < len(a) and not a[i + 1].startswith('--') else True
    return default


def locate(proj, rel):
    p = os.path.abspath(proj)
    if not p.startswith(REPO + os.sep): raise SystemExit('project must live inside this repo (projects/<name>)')
    f = os.path.join(p, rel)
    if not os.path.exists(f): raise SystemExit('no such file: %s' % f)
    return p, f


def cmd_cut():
    proj, src = locate(sys.argv[2], sys.argv[3]); cid = flag('id')
    if not cid or flag('start') is None or flag('end') is None: raise SystemExit('cut needs --id, --start, --end')
    info = probe(src); start = float(flag('start')); end = float(flag('end'))
    if start >= info['duration']: raise SystemExit('--start %.2f is beyond the end of the film (%.2f s)' % (start, info['duration']))
    if end > info['duration']: print('clamped --end %.2f to the film length %.2f' % (end, info['duration'])); end = info['duration']
    if info['field_order'] not in ('progressive', 'unknown') and not flag('deint') and not flag('ivtc'): print('note: source is interlaced (%s); consider --ivtc (telecined film) or --deint' % info['field_order'])
    ivtc = bool(flag('ivtc')); crop = parse_crop(flag('crop')); scale = float(flag('scale', 1)); fps = flag('fps'); out_fps = float(fps) if fps else (round(info['fps'] * 0.8, 3) if ivtc else info['fps'])
    vf = build_filter(fps=fps, crop=crop, scale=scale, deint=bool(flag('deint')), ivtc=ivtc, denoise=float(flag('denoise', 0)), sharpen=not flag('no-sharpen') and scale > 1)
    d = os.path.join(proj, 'assets', 'clips', cid); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    r = run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(start), '-i', src, '-t', str(end - start), '-an', '-vf', vf, '-q:v', str(flag('q', 2)), os.path.join(d, '%05d.jpg')])
    if r.returncode: raise SystemExit('ffmpeg failed: ' + r.stderr)
    files = sorted(f for f in os.listdir(d) if f.endswith('.jpg'))
    if not files: raise SystemExit('ffmpeg wrote no frames (check --start/--end)')
    from PIL import Image
    w, h = Image.open(os.path.join(d, files[0])).size
    meta = {'id': cid, 'src': os.path.relpath(src, proj), 'start': start, 'end': end, 'fps': out_fps, 'n': len(files), 'w': w, 'h': h, 'pattern': '%05d.jpg', 'filter': vf}
    json.dump(meta, open(os.path.join(d, 'clip.json'), 'w'), indent=1)
    print('%s: %d frames, %dx%d @ %s fps, %.2f s (%s -> %s)  -> %s' % (cid, len(files), w, h, out_fps, len(files) / out_fps, fmt_ts(start), fmt_ts(end), os.path.relpath(d, REPO)))


def scan_frames(src, t0, t1, every, width, outdir):
    """Thumbnails roughly every `every` seconds, each paired with the REAL time of its frame -> [(seconds, jpg path)].
    (ffmpeg's fps filter keeps the last frame of each rounding window, up to half an interval late, so labels derived from the index drift; this selects real frames
    and reads their timestamps. Times follow the same convention as `-ss`, i.e. seconds from the start of the file's own timeline.)"""
    expr = "select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,%s)',showinfo,scale=%d:-2" % (every, width)
    r = run(['ffmpeg', '-y', '-loglevel', 'info', '-ss', str(t0), '-i', src, '-t', str(t1 - t0), '-an', '-vf', expr, '-fps_mode', 'vfr', '-q:v', '3', os.path.join(outdir, 't%05d.jpg')])
    if r.returncode: raise SystemExit('ffmpeg failed: ' + r.stderr[-400:])
    times = [float(m) for m in re.findall(r'pts_time:\s*(-?[\d.]+)', r.stderr)]; files = sorted(f for f in os.listdir(outdir) if f.endswith('.jpg'))
    return [(t0 + max(0.0, t), os.path.join(outdir, f)) for t, f in zip(times, files)]


def cmd_scan():
    proj, src = locate(sys.argv[2], sys.argv[3]); every = float(flag('every', 2)); cols = int(flag('cols', 6)); rows = int(flag('rows', 5)); tw = int(flag('width', 300))
    t0 = float(flag('from', 0)); info = probe(src); t1 = float(flag('to', info['duration']))
    from PIL import Image, ImageDraw, ImageFont
    name = os.path.basename(proj); stem = re.sub(r'\W+', '_', os.path.splitext(os.path.basename(src))[0]) + '_%ds' % t0; out = os.path.join(REPO, 'out', name, 'scan'); os.makedirs(out, exist_ok=True)
    for old in os.listdir(out):
        if old.startswith(stem + '_'): os.unlink(os.path.join(out, old))
    with tempfile.TemporaryDirectory() as tmp:
        frames = scan_frames(src, t0, t1, every, tw, tmp); per = cols * rows
        try: font = ImageFont.load_default(size=max(12, tw // 14))
        except TypeError: font = ImageFont.load_default()
        for si in range(0, len(frames), per):
            batch = frames[si:si + per]; ims = [Image.open(p) for _, p in batch]; th = ims[0].height
            sheet = Image.new('RGB', (cols * tw, math.ceil(len(ims) / cols) * th), (12, 12, 12)); dr = ImageDraw.Draw(sheet)
            for i, (im, (t, _)) in enumerate(zip(ims, batch)):
                x, y = (i % cols) * tw, (i // cols) * th; sheet.paste(im, (x, y)); label = fmt_ts(t)
                dr.rectangle([x, y, x + len(label) * (tw // 20) + 10, y + tw // 11], fill=(0, 0, 0)); dr.text((x + 4, y + 1), label, fill=(255, 220, 90), font=font)
            path = os.path.join(out, '%s_%02d.jpg' % (stem, si // per + 1)); sheet.save(path, quality=88)
            print('%s  (%s -> %s)' % (os.path.relpath(path, REPO), fmt_ts(batch[0][0]), fmt_ts(batch[-1][0])))


def cmd_scenes():
    proj, src = locate(sys.argv[2], sys.argv[3]); th = float(flag('threshold', 0.35))
    r = run(['ffmpeg', '-i', src, '-an', '-vf', "select='gt(scene,%s)',showinfo" % th, '-f', 'null', '-'])
    ts = [float(m.group(1)) for m in re.finditer(r'pts_time:([\d.]+)', r.stderr)]
    print('%d likely cuts:' % len(ts), ', '.join(fmt_ts(t) for t in ts))


if __name__ == '__main__':
    cmds = {'cut': cmd_cut, 'scan': cmd_scan, 'scenes': cmd_scenes}
    if len(sys.argv) < 4 or sys.argv[1] not in cmds: print(__doc__); sys.exit(2)
    cmds[sys.argv[1]]()
