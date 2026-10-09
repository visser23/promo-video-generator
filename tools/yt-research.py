#!/usr/bin/env python3
"""yt-research.py - a quick, honest read on whether a topic gets watched as a Short.  Needs yt-dlp (pip install yt-dlp); it reads public search results only.

  python3 tools/yt-research.py search "Trinity test first atomic bomb"           # Shorts-length results: how many, median / p75 / max views, who dominates
  python3 tools/yt-research.py compare topics.txt                                 # one topic per line, ranked by median views
  options: --n 30 (results per query)   --max-duration 90   --suffix "#shorts"   --json (machine output)

What the numbers mean: `median` is what a typical video on the topic gets, `p75`/`max` the upside, `hits` how many are over 20x the median (a spike: the topic CAN go
viral), `top_channel_share` how much of the result list one channel owns (high = hard to break in).  View counts are lifetime views, not per-day, and search
order is YouTube's, so treat this as a smell test, not a forecast."""
import sys, json, subprocess, statistics, concurrent.futures as cf


def parse_entries(text):
    out = []
    for line in text.splitlines():
        try: out.append(json.loads(line))
        except ValueError: continue
    return out


def summarise(entries, max_duration=90):
    use = [e for e in entries if e.get('duration') and e['duration'] <= max_duration and e.get('view_count') is not None]
    if not use: return {'n': 0, 'median': 0, 'p75': 0, 'max': 0, 'hits': 0, 'top_channel_share': 0.0}
    v = sorted(e['view_count'] for e in use); med = statistics.median(v); chans = {}
    for e in use: chans[e.get('channel') or e.get('channel_id') or '?'] = chans.get(e.get('channel') or e.get('channel_id') or '?', 0) + 1
    return {'n': len(use), 'median': int(med), 'p75': v[max(0, int(len(v) * 0.75) - 1)], 'max': v[-1], 'hits': sum(1 for x in v if med and x > 20 * med), 'top_channel_share': round(max(chans.values()) / len(use), 2)}


def rank(summaries): return sorted(summaries.items(), key=lambda kv: (-kv[1]['median'], -kv[1]['n']))


def search(query, n=30, suffix='#shorts'):
    p = subprocess.run(['yt-dlp', '--flat-playlist', '--dump-json', '--no-warnings', 'ytsearch%d:%s %s' % (n, query, suffix)], capture_output=True, text=True)
    if p.returncode and not p.stdout: raise SystemExit('yt-dlp failed (is it installed? pip install yt-dlp): ' + p.stderr[-300:])
    return parse_entries(p.stdout)


def _opt(a, name, default):
    return type(default)(a[a.index(name) + 1]) if name in a else default


def main(argv):
    if len(argv) < 2 or argv[0] not in ('search', 'compare'): raise SystemExit(__doc__)
    n, md, suffix = _opt(argv, '--n', 30), _opt(argv, '--max-duration', 90), _opt(argv, '--suffix', '#shorts')
    topics = [argv[1]] if argv[0] == 'search' else [l.strip() for l in open(argv[1]) if l.strip() and not l.startswith('#')]
    with cf.ThreadPoolExecutor(4) as ex: res = dict(zip(topics, ex.map(lambda t: summarise(search(t, n, suffix), md), topics)))
    if '--json' in argv: print(json.dumps(res, indent=1)); return 0
    print('%-44s %4s %10s %10s %11s %5s %6s' % ('topic', 'n', 'median', 'p75', 'max', 'hits', 'top-ch'))
    for t, s in rank(res): print('%-44s %4d %10d %10d %11d %5d %5d%%' % (t[:44], s['n'], s['median'], s['p75'], s['max'], s['hits'], round(100 * s['top_channel_share'])))
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
