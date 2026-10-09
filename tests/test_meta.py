#!/usr/bin/env python3
"""Tests for the upload-side tools: tools/shorts-meta.py (metadata rules + files), tools/shorts-check.py (spec check of an mp4), tools/yt-research.py (offline statistics)."""
import os, sys, json, shutil, subprocess, tempfile, importlib.util

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, 'tools', fn)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


META = load('shorts_meta', 'shorts-meta.py'); CHECK = load('shorts_check', 'shorts-check.py'); RES = load('yt_research', 'yt-research.py')
codes = lambda ps, level=None: sorted(p['code'] for p in ps if level is None or p['level'] == level)

# ── shorts-meta: the rules ────────────────────────────────────────────────────────────────────────
good = {'title': 'They bet on the end of the world', 'summary': 'Before the first atomic test, physicists placed bets.', 'hashtags': ['#Shorts', '#History'], 'tags': ['trinity test', 'history'],
        'category': 'Education', 'ai': {'voice': True, 'music': True, 'visuals': False}}
assert codes(META.validate(good), 'error') == [], META.validate(good)
assert 'title-long' in codes(META.validate(dict(good, title='x' * 101)), 'error'), 'YouTube titles are 100 characters at most'
assert 'title-missing' in codes(META.validate(dict(good, title='  ')), 'error')
assert 'angle-brackets' in codes(META.validate(dict(good, title='a < b')), 'error'), 'YouTube rejects < and > in titles and descriptions'
assert 'angle-brackets' in codes(META.validate(dict(good, summary='x > y')), 'error')
assert 'title-caps' in codes(META.validate(dict(good, title='THEY BET ON THE END OF THE WORLD')), 'warn'), 'all-caps titles read as spam'
assert 'title-short-truncates' in codes(META.validate(dict(good, title='A ' * 40 + 'end')), 'warn'), 'long titles are cut off in the Shorts feed'
assert 'hashtags-too-many' in codes(META.validate(dict(good, hashtags=['#a%d' % i for i in range(16)])), 'error'), 'YouTube ignores ALL hashtags when there are more than 15'
assert 'hashtag-format' in codes(META.validate(dict(good, hashtags=['History'])), 'error'), 'a hashtag starts with #'
assert 'hashtag-format' in codes(META.validate(dict(good, hashtags=['#two words'])), 'error')
assert 'tags-too-long' in codes(META.validate(dict(good, tags=['t' * 30] * 20)), 'error'), 'tags are 500 characters in total'
assert 'category-unknown' in codes(META.validate(dict(good, category='Cooking')), 'error')
assert 'ai-undisclosed' in codes(META.validate(dict(good, ai=None)), 'warn'), 'say whether AI was used - we recommend disclosing'
assert META.CATEGORIES['Education'] == '27' and META.CATEGORIES['Entertainment'] == '24'
long = dict(good, summary='word ' * 1100); assert 'description-long' in codes(META.validate(long), 'error'), 'description is 5000 bytes at most'
assert 'description-long' in codes(META.validate(dict(good, summary='é' * 2600)), 'error'), 'the limit is bytes, not characters'
assert 'duration-long' in codes(META.validate(good, duration=200), 'error'), 'a Short is at most 3 minutes'
assert 'duration-long' not in codes(META.validate(good, duration=48.8))

# ── shorts-meta: the description and the API body ─────────────────────────────────────────────────
prov = [{'key': 'ia:x', 'title': 'Nuclear Test Film - Trinity Shot', 'creator': 'Department of Energy', 'year': '1945', 'rights_class': 'public-domain', 'landing': 'https://archive.org/details/gov.doe.0800001', 'license': 'x'},
        {'key': 'commons:File:Y.jpg', 'title': 'File:Y.jpg', 'creator': 'A. Photographer', 'year': '1945', 'rights_class': 'attribution', 'landing': 'https://commons.wikimedia.org/wiki/File:Y.jpg', 'license': 'CC BY 4.0'}]
m = dict(good, sources=[{'label': 'Trinity (nuclear test)', 'url': 'https://en.wikipedia.org/wiki/Trinity_(nuclear_test)'}], facts=['Fermi offered to take wagers.'])
d = META.build_description(m, prov)
assert d.startswith('Before the first atomic test'), d[:60]
assert 'https://archive.org/details/gov.doe.0800001' in d and 'https://en.wikipedia.org/wiki/Trinity_(nuclear_test)' in d, 'every source is linked'
assert 'A. Photographer' in d and 'CC BY 4.0' in d, 'attribution-class material is credited with its licence'
assert d.rstrip().endswith('#Shorts #History'), 'hashtags last: the first three are shown above the title'
assert '- Fermi offered to take wagers.' in d
only = META.build_description(dict(m, credits=['ia:x']), prov); assert 'archive.org/details/gov.doe.0800001' in only and 'A. Photographer' not in only, 'meta.json "credits" limits the credit list to what the film actually uses'
assert META.build_description(dict(m, credits=[]), prov).count('Y.jpg') == 0, 'an empty list credits no provenance entries'
assert 'rights' not in codes(META.validate(dict(good, credits=['ia:x']), prov + [{'key': 'unused', 'title': 'U', 'rights_class': 'restricted', 'landing': 'u'}]), 'error'), 'an unused (restricted) asset does not block the upload'
assert 'credits-unknown' in codes(META.validate(dict(good, credits=['nope']), prov), 'error'), 'a credits key that is not in provenance.json is a typo'
body = META.build_upload(m, prov, duration=48.8)
sn, st = body['snippet'], body['status']
assert sn['title'] == good['title'] and sn['categoryId'] == '27' and sn['tags'] == good['tags'], sn
assert st['privacyStatus'] == 'private', 'never public by accident'
assert st['selfDeclaredMadeForKids'] is False and st['containsSyntheticMedia'] is True, st
assert META.build_upload(dict(m, ai={'voice': False, 'music': False, 'visuals': False}), prov)['status']['containsSyntheticMedia'] is False
bad = prov + [{'key': 'web:z', 'title': 'Z', 'rights_class': 'restricted', 'landing': 'https://example.com/z'}]
assert 'rights' in codes(META.validate(good, bad), 'error'), 'restricted footage in the provenance blocks the upload metadata'
assert 'rights' in codes(META.validate(good, prov + [{'key': 'q', 'title': 'Q', 'rights_class': 'unknown', 'landing': 'u'}]), 'error')

# ── shorts-meta: the CLI writes upload.json + upload.md ───────────────────────────────────────────
tmp = tempfile.mkdtemp(); proj = os.path.join(REPO, 'projects', '_metatest'); out = os.path.join(REPO, 'out', '_metatest')
try:
    os.makedirs(proj, exist_ok=True); json.dump(dict(m), open(os.path.join(proj, 'meta.json'), 'w')); json.dump(prov, open(os.path.join(proj, 'provenance.json'), 'w'))
    json.dump({'fps': 30, 'duration': 40, 'width': 1080, 'height': 1920}, open(os.path.join(proj, 'cues.json'), 'w'))
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'shorts-meta.py'), proj], capture_output=True, text=True); assert r.returncode == 0, r.stdout + r.stderr
    up = json.load(open(os.path.join(out, 'upload.json'))); assert up['snippet']['title'] == good['title']; md = open(os.path.join(out, 'upload.md')).read()
    assert good['title'] in md and 'https://archive.org/details/gov.doe.0800001' in md and 'Disclose' in md, md[:400]
    json.dump(dict(m, title='x' * 120), open(os.path.join(proj, 'meta.json'), 'w'))
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'shorts-meta.py'), proj], capture_output=True, text=True); assert r.returncode == 1 and 'title-long' in r.stdout, 'errors exit 1: ' + r.stdout
finally:
    shutil.rmtree(proj, ignore_errors=True); shutil.rmtree(out, ignore_errors=True); shutil.rmtree(tmp, ignore_errors=True)

# ── shorts-check: a real mp4 ──────────────────────────────────────────────────────────────────────
def mk(path, w, h, dur, audio=True, vol=0.1, start_black=False):
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=%dx%d:rate=30:duration=%s' % (w, h, dur)]
    if audio: cmd += ['-f', 'lavfi', '-i', 'sine=frequency=220:duration=%s' % dur, '-af', 'volume=%s' % vol, '-c:a', 'aac']
    vf = 'fade=t=in:st=0:d=0.5,format=yuv420p' if start_black else 'format=yuv420p'
    subprocess.run(cmd + ['-vf', vf, '-c:v', 'libx264', '-shortest', path], check=True)

with tempfile.TemporaryDirectory() as t:
    ok_v = os.path.join(t, 'ok.mp4'); mk(ok_v, 540, 960, 4, vol=1.6)       # lavfi's sine is -18 dBFS already: x1.6 lands near -17 LUFS
    facts, ps = CHECK.check(ok_v); assert facts['width'] == 540 and facts['height'] == 960 and abs(facts['duration'] - 4) < 0.2 and facts['has_audio'], facts
    assert 'not-vertical' not in codes(ps) and 'no-audio' not in codes(ps) and 'too-long' not in codes(ps), ps
    assert facts['lufs'] is not None and -22 < facts['lufs'] < -9, facts; assert 'too-quiet' not in codes(ps) and 'too-loud' not in codes(ps), ps
    wide = os.path.join(t, 'wide.mp4'); mk(wide, 960, 540, 3); assert 'not-vertical' in codes(CHECK.check(wide)[1], 'error'), 'a Short is vertical or square'
    sq = os.path.join(t, 'sq.mp4'); mk(sq, 540, 540, 3); assert 'not-vertical' not in codes(CHECK.check(sq)[1]), 'square is allowed'
    na = os.path.join(t, 'na.mp4'); mk(na, 540, 960, 3, audio=False); assert 'no-audio' in codes(CHECK.check(na)[1], 'error')
    loud = os.path.join(t, 'loud.mp4'); mk(loud, 540, 960, 3, vol=7.9); assert any(c in codes(CHECK.check(loud)[1]) for c in ('too-loud', 'true-peak')), CHECK.check(loud)
    quiet = os.path.join(t, 'quiet.mp4'); mk(quiet, 540, 960, 3, vol=0.05); assert 'too-quiet' in codes(CHECK.check(quiet)[1], 'warn'), CHECK.check(quiet)
    longv = os.path.join(t, 'long.mp4'); mk(longv, 90, 160, 185, audio=False); assert 'too-long' in codes(CHECK.check(longv)[1], 'error'), 'over 3 minutes is not a Short'
    blk = os.path.join(t, 'blk.mp4'); mk(blk, 540, 960, 3, start_black=True); assert 'black-start' in codes(CHECK.check(blk)[1], 'warn'), 'a black first frame wastes the hook'
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'shorts-check.py'), wide], capture_output=True, text=True); assert r.returncode == 1 and 'not-vertical' in r.stdout, r.stdout
    r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'shorts-check.py'), ok_v], capture_output=True, text=True); assert r.returncode == 0, r.stdout + r.stderr

# ── yt-research: statistics on search results (offline) ───────────────────────────────────────────
E = lambda i, dur, views, ch: {'id': 'v%d' % i, 'title': 't%d' % i, 'duration': dur, 'view_count': views, 'channel': ch}
rows = [E(1, 30, 1000, 'a'), E(2, 45, 5000, 'a'), E(3, 59, 20000, 'b'), E(4, 600, 9_000_000, 'c'), E(5, None, 10, 'd'), E(6, 20, None, 'e'), E(7, 55, 1_000_000, 'f')]
s = RES.summarise(rows, max_duration=90)
assert s['n'] == 4, 'only Shorts-length results with a view count are counted: ' + str(s)
assert s['median'] == 12500 and s['max'] == 1_000_000 and s['p75'] >= 20000, s
assert s['top_channel_share'] == 0.5, s       # channel 'a' made 2 of the 4
assert RES.summarise([], 90)['n'] == 0 and RES.summarise([], 90)['median'] == 0
assert RES.summarise(rows, 90)['hits'] == 1, 'hits = results above 20x the median is a quick "does this topic spike" signal'
order = RES.rank({'x': RES.summarise(rows, 90), 'y': RES.summarise(rows[:2], 90)}); assert order[0][0] == 'x', order
assert RES.parse_entries('\n'.join(json.dumps(e) for e in rows[:2]) + '\nnot json\n')[1]['id'] == 'v2', 'bad lines are skipped'
print('ok')
