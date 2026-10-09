#!/usr/bin/env python3
"""footage.py - find, vet and fetch archival footage / photos, and keep a provenance record for every file you use.

  python3 tools/footage.py search "trinity test" [--source ia|commons|all] [--kind video|image] [--rows 20]
  python3 tools/footage.py info   ia:gov.doe.0800001                       # licence verdict + the files on offer
  python3 tools/footage.py fetch  <project> ia:gov.doe.0800001 [--file NAME] [--max-mb 400] [--as raw-name]
  python3 tools/footage.py fetch  <project> "commons:File:Trinity_test.ogv"
  python3 tools/footage.py credits <project> [--only key1,key2]           # -> out/<name>/credits.md (paste into the description)
  python3 tools/footage.py audit  <project>                               # exit 1 if any item is restricted / unknown / needs a human check

Every verdict is one of  public-domain | attribution | check | restricted | unknown.  Only the first two may go in a monetised video without a
human decision.  `check` = derivative of old footage (colourised, restored, upscaled, "AI enhanced"): the underlying film may be free but the
derivative can carry its own copyright - go back to the original source.  The tool reads *metadata the uploader entered*; it cannot prove it, so
the audit also prints the landing page for you to open.  Files land in projects/<name>/raw/ (git-ignored); the record is projects/<name>/provenance.json.
No API key needed.  Be polite: one request at a time, identifying User-Agent."""
import os, sys, re, json, time, hashlib, datetime, urllib.parse, urllib.request, urllib.error

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
UA = 'promo-video-generator/1.1 (archival footage research; https://github.com/visser23/promo-video-generator)'
PD, BY, CHECK, RESTRICTED, UNKNOWN = 'public-domain', 'attribution', 'check', 'restricted', 'unknown'
DERIVATIVE = re.compile(r'colou?ri[sz]ed|\brestor(?:ed|ation)\b|remaster|upscal|\bupres\b|\bAI\b|\benhanced\b|\bHD color\b|\b4K\b|\bUHD\b|deoldify|interpolat', re.I)


# ---------------------------------------------------------------------------------------------------------- rights
def is_derivative(text):
    """True when a title/description says the media was colourised / restored / upscaled / AI-enhanced (its own copyright may apply)."""
    return bool(DERIVATIVE.search(text or ''))


def classify_license_url(url):
    u = (url or '').lower()
    if not u: return UNKNOWN
    if 'publicdomain' in u: return PD                                   # /publicdomain/zero/, /publicdomain/mark/, /licenses/publicdomain/
    if re.search(r'/licenses/by-(nc|nd|sa)', u): return RESTRICTED       # NonCommercial / NoDerivatives / ShareAlike: not usable in a monetised edit
    if re.search(r'/licenses/by/', u): return BY
    return UNKNOWN


def classify_ia(meta):
    """archive.org item metadata -> (class, reason)."""
    lic = meta.get('licenseurl'); base = classify_license_url(lic)
    cols = meta.get('collection') or []; cols = [cols] if isinstance(cols, str) else cols
    text = ' '.join(str(meta.get(k) or '') for k in ('title', 'description'))
    gov = str(meta.get('identifier', '')).startswith('gov.') and any(c in cols for c in ('usgovfilms', 'FedFlix'))
    if base in (RESTRICTED,): return RESTRICTED, f'licence {lic}'
    if base == UNKNOWN and gov: base, lic = PD, 'US-government work (no licence field; US federal works have no copyright - still check for third-party material in it)'
    if base == UNKNOWN: return UNKNOWN, 'no licence information on the item: do not use without finding the original source'
    if is_derivative(text): return CHECK, f'derivative (colourised / restored / upscaled?) - the original may be free, this version may carry its own copyright; licence field says {lic}'
    return base, str(lic)


def classify_commons(extmeta):
    """Wikimedia Commons extmetadata -> (class, reason)."""
    g = lambda k: ((extmeta or {}).get(k) or {}).get('value') or ''
    lic = (g('LicenseShortName') or g('UsageTerms')).strip(); l = lic.lower()
    if not lic: return UNKNOWN, 'no licence on the file page'
    if re.search(r'-sa|\bsa\b|-nc|-nd|gfdl|fair use', l): return RESTRICTED, lic
    if l.startswith(('public domain', 'pd', 'cc0', 'no restrictions')) or g('Copyrighted').lower() == 'false' and 'cc by' not in l: return PD, lic
    if l.startswith('cc by'): return BY, lic
    return UNKNOWN, lic


# ---------------------------------------------------------------------------------------------------------- archive.org files
VIDEO_FORMATS = ('mpeg4', 'h.264', 'mpeg2', 'ogg video', 'matroska', 'quicktime', 'avi', 'ia', 'webm', 'mp4')


def pick_ia_file(files, max_mb=400, prefer=None):
    """Choose the video file to download: an explicit name wins; otherwise the largest *picture* (height) whose size fits max_mb."""
    if prefer:
        for f in files:
            if f.get('name') == prefer: return f
        return None
    best = None
    for f in files:
        fmt = (f.get('format') or '').lower(); name = f.get('name', '').lower()
        if not (any(k in fmt for k in VIDEO_FORMATS) or name.endswith(('.mp4', '.mpeg', '.mpg', '.ogv', '.mkv', '.avi', '.webm', '.mov'))): continue
        if 'gif' in fmt or 'thumb' in fmt: continue
        size = int(f.get('size') or 0)
        if size > max_mb * 1e6: continue
        key = (int(f.get('height') or 0), size)
        if best is None or key > best[0]: best = (key, f)
    return best[1] if best else None


# ---------------------------------------------------------------------------------------------------------- provenance
def record(path, entry):
    """Add or update (by key) one entry in the provenance file."""
    data = json.load(open(path)) if os.path.exists(path) else []
    for e in data:
        if e['key'] == entry['key']: e.update(entry); break
    else: data.append(entry)
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    json.dump(data, open(path, 'w'), indent=1); return data


def credits_markdown(data):
    lines = []
    for e in data:
        who = e.get('creator') or 'unknown creator'; yr = f" ({e['year']})" if e.get('year') else ''
        lic = e.get('license') or e.get('rights_class') or ''
        lines.append(f"- {e.get('title', e['key'])} - {who}{yr}. {e.get('landing', '')} [{lic}]")
    return '\n'.join(lines) + ('\n' if lines else '')


def problems(data):
    return [(e['key'], e.get('rights_class', UNKNOWN), e.get('license') or e.get('rights_note') or '') for e in data if e.get('rights_class', UNKNOWN) not in (PD, BY)]


# ---------------------------------------------------------------------------------------------------------- network
def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)


def ia_search(q, rows=20):
    p = [('q', q + ' AND mediatype:movies'), ('rows', rows), ('sort[]', 'downloads desc'), ('output', 'json')] + [('fl[]', f) for f in ('identifier', 'title', 'year', 'creator', 'licenseurl', 'collection', 'description', 'downloads')]
    return get_json('https://archive.org/advancedsearch.php?' + urllib.parse.urlencode(p))['response']['docs']


def ia_meta(ident):
    d = get_json('https://archive.org/metadata/' + urllib.parse.quote(ident))
    if not d.get('metadata'): raise SystemExit(f'archive.org has no item {ident!r}')
    return d


def commons_search(q, kind='video', rows=20):
    flt = 'filetype:video' if kind == 'video' else 'filetype:bitmap'
    p = {'action': 'query', 'list': 'search', 'srsearch': f'{q} {flt}', 'srnamespace': 6, 'srlimit': rows, 'format': 'json'}
    return [x['title'] for x in get_json('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(p))['query']['search']]


def commons_info(title):
    p = {'action': 'query', 'titles': title, 'prop': 'imageinfo', 'iiprop': 'url|size|mime|extmetadata|sha1', 'format': 'json'}
    pages = get_json('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(p))['query']['pages']
    pg = list(pages.values())[0]
    if 'imageinfo' not in pg: raise SystemExit(f'Commons has no file {title!r}')
    return pg['imageinfo'][0]


def strip_html(s): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()


def download(url, dest, expect=None):
    """Download with resume + a progress line; returns sha256."""
    os.makedirs(os.path.dirname(dest), exist_ok=True); have = os.path.getsize(dest) if os.path.exists(dest) else 0
    if expect and have == expect: pass
    else:
        req = urllib.request.Request(url, headers={'User-Agent': UA, **({'Range': f'bytes={have}-'} if have else {})})
        try: r = urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            if e.code == 416: r = None           # already complete
            else: raise
        if r is not None:
            total = int(r.headers.get('Content-Length') or 0) + (have if r.status == 206 else 0); mode = 'ab' if r.status == 206 else 'wb'; got = have if r.status == 206 else 0; t0 = time.time()
            tty = sys.stderr.isatty(); step = 0                  # a terminal gets a live line; a log gets one line per 25%
            with open(dest, mode) as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b); got += len(b)
                    if total and tty: print(f'\r  {got / 1e6:8.1f} / {total / 1e6:.1f} MB', end='', file=sys.stderr)
                    elif total and got * 4 // total > step: step = got * 4 // total; print(f'  {got / 1e6:.0f} / {total / 1e6:.0f} MB ({step * 25}%)', file=sys.stderr)
            if tty: print(file=sys.stderr)
    h = hashlib.sha256()
    with open(dest, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------------------- commands
def flag(name, default=None):
    a = sys.argv
    if '--' + name in a:
        i = a.index('--' + name); return a[i + 1] if i + 1 < len(a) else True
    return default


def project_dir(arg):
    p = os.path.abspath(arg)
    if not p.startswith(REPO + os.sep): raise SystemExit('project must live inside this repo (projects/<name>)')
    return p


def cmd_search():
    q = sys.argv[2]; src = flag('source', 'all'); kind = flag('kind', 'video'); rows = int(flag('rows', 20))
    if src in ('ia', 'all'):
        print(f'== archive.org: {q}')
        for d in ia_search(q, rows):
            cls, why = classify_ia(d); print(f"  [{cls:13}] ia:{d['identifier']}  | {str(d.get('title'))[:60]} | {d.get('year')} | {str(d.get('creator'))[:24]} | {d.get('downloads')} dl")
    if src in ('commons', 'all'):
        print(f'== commons: {q} ({kind})')
        for t in commons_search(q, kind, rows):
            try: cls, why = classify_commons(commons_info(t).get('extmetadata'))
            except Exception as e: cls, why = UNKNOWN, str(e)
            print(f'  [{cls:13}] commons:{t}  | {why}')


def describe(key):
    kind, _, ident = key.partition(':')
    if kind == 'ia':
        d = ia_meta(ident); m = d['metadata']; cls, why = classify_ia(m)
        return {'key': key, 'title': m.get('title'), 'creator': m.get('creator'), 'year': str(m.get('year') or m.get('date') or ''), 'license': m.get('licenseurl'), 'rights_class': cls, 'rights_note': why,
                'landing': 'https://archive.org/details/' + ident, 'description': strip_html(m.get('description'))[:500]}, d['files']
    if kind == 'commons':
        i = commons_info(ident); em = i.get('extmetadata', {}); cls, why = classify_commons(em); g = lambda k: strip_html((em.get(k) or {}).get('value'))
        return {'key': key, 'title': ident, 'creator': g('Artist'), 'year': g('DateTimeOriginal')[:4], 'license': g('LicenseShortName'), 'rights_class': cls, 'rights_note': why,
                'landing': 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(ident.replace(' ', '_')), 'description': g('ImageDescription')[:500], 'credit': g('Credit')[:300]}, [i]
    raise SystemExit('key must start with ia: or commons:')


def cmd_info():
    e, files = describe(sys.argv[2]); print(json.dumps(e, indent=1))
    if e['key'].startswith('ia:'):
        for f in files:
            if pick_ia_file([f], 10 ** 6): print(f"  file {f['name']}  {f.get('format')}  {int(f.get('size') or 0) / 1e6:.1f} MB  {f.get('width')}x{f.get('height')}  {f.get('length', '')}s")
    else: print('  file', files[0]['url'], files[0].get('width'), 'x', files[0].get('height'), files[0].get('size'))
    print('\nVERDICT:', e['rights_class'], '-', e['rights_note'])


def cmd_fetch():
    proj = project_dir(sys.argv[2]); key = sys.argv[3]; e, files = describe(key)
    print(f"{key}: {e['title']}  [{e['rights_class']}] {e['rights_note']}")
    if e['rights_class'] in (RESTRICTED, UNKNOWN) and '--force' not in sys.argv: raise SystemExit('refusing to fetch: ' + e['rights_class'] + ' (use --force only to *look*; the audit will still flag it)')
    if key.startswith('ia:'):
        f = pick_ia_file(files, float(flag('max-mb', 400)), flag('file'))
        if not f: raise SystemExit('no suitable video file (raise --max-mb or name one with --file); run `info` to list them')
        url = f"https://archive.org/download/{urllib.parse.quote(key[3:])}/{urllib.parse.quote(f['name'])}"; size = int(f.get('size') or 0); name = f['name']
    else:
        f = files[0]; url = f['url'].split('?')[0]; size = int(f.get('size') or 0); name = urllib.parse.unquote(url.rsplit('/', 1)[-1])
    out = os.path.join(proj, 'raw', flag('as', name))
    sha = download(url, out, size or None)
    e.update({'file': os.path.relpath(out, proj), 'file_url': url, 'bytes': os.path.getsize(out), 'sha256': sha, 'retrieved': datetime.date.today().isoformat()})
    record(os.path.join(proj, 'provenance.json'), e); print('saved', os.path.relpath(out, REPO), f"({e['bytes'] / 1e6:.1f} MB), provenance recorded")


def load_prov(proj):
    p = os.path.join(proj, 'provenance.json')
    if not os.path.exists(p): raise SystemExit(f'no provenance.json in {proj}: fetch footage with `footage.py fetch` so every file is recorded')
    return json.load(open(p))


def cmd_credits():
    proj = project_dir(sys.argv[2]); data = load_prov(proj); only = flag('only')
    if only: data = [e for e in data if e['key'] in only.split(',')]
    md = credits_markdown(data); out = os.path.join(REPO, 'out', os.path.basename(proj)); os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'credits.md'), 'w').write(md); print(md, end=''); print(f'-> out/{os.path.basename(proj)}/credits.md')


def cmd_audit():
    proj = project_dir(sys.argv[2]); data = load_prov(proj); bad = problems(data)
    for e in data: print(f"  [{e.get('rights_class', UNKNOWN):13}] {e['key']}  {e.get('landing', '')}")
    if bad:
        print('\nNEEDS A HUMAN DECISION BEFORE PUBLISHING:'); [print('  -', *b) for b in bad]; sys.exit(1)
    print('\nall recorded sources are public-domain or attribution-only (open each landing page once to confirm the uploader\'s claim).')


if __name__ == '__main__':
    cmds = {'search': cmd_search, 'info': cmd_info, 'fetch': cmd_fetch, 'credits': cmd_credits, 'audit': cmd_audit}
    need = {'search': 3, 'info': 3, 'fetch': 4, 'credits': 3, 'audit': 3}
    if any(a in ('-h', '--help') for a in sys.argv[1:]): print(__doc__); sys.exit(0)
    if len(sys.argv) < 2 or sys.argv[1] not in cmds or len(sys.argv) < need[sys.argv[1]]: print(__doc__); sys.exit(2)
    cmds[sys.argv[1]]()
