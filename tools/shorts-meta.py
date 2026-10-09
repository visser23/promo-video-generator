#!/usr/bin/env python3
"""shorts-meta.py - turn projects/<name>/meta.json (+ provenance.json) into upload metadata, and refuse the obvious mistakes first.

  python3 tools/shorts-meta.py projects/<name>        -> out/<name>/upload.json (YouTube Data API `videos.insert` body) + out/<name>/upload.md (what to paste / check)
  exit code 1 if there is any error (warnings are printed but do not fail)

meta.json:
  { "title": "They bet on the end of the world", "summary": "first lines of the description (what the viewer needs to know)",
    "facts": ["optional bullet", "..."], "sources": [{"label": "Trinity (nuclear test)", "url": "https://..."}],     // extra reading; footage credits are added from provenance.json
    "hashtags": ["#Shorts", "#History"],            // the first 3 are shown above the title; more than 15 and YouTube ignores all of them
    "tags": ["trinity test", "..."], "category": "Education", "language": "en",
    "ai": {"voice": true, "music": true, "visuals": false} }   // what is synthetic; any true => containsSyntheticMedia (YouTube's altered/synthetic disclosure)

Nothing here uploads anything: the body is written `private` so a human decides when it goes public (and whether to use the Studio UI or the API)."""
import os, sys, json

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CATEGORIES = {'Film & Animation': '1', 'Autos & Vehicles': '2', 'Music': '10', 'Pets & Animals': '15', 'Sports': '17', 'Travel & Events': '19', 'Gaming': '20', 'People & Blogs': '22',
              'Comedy': '23', 'Entertainment': '24', 'News & Politics': '25', 'Howto & Style': '26', 'Education': '27', 'Science & Technology': '28', 'Nonprofits & Activism': '29'}
OK_RIGHTS = ('public-domain', 'attribution')


def P(level, code, msg): return {'level': level, 'code': code, 'msg': msg}


def validate(meta, prov=None, duration=None):
    """-> [{'level': 'error'|'warn', 'code', 'msg'}]  (pure; tested in tests/test_meta.py)"""
    out = []; title = (meta.get('title') or '').strip(); all_prov = prov or []; prov = used(meta, all_prov); desc = build_description(meta, all_prov)
    for k in (meta.get('credits') or []):
        if k not in {e.get('key') for e in all_prov}: out.append(P('error', 'credits-unknown', 'meta.json credits %r is not a key in provenance.json' % k))
    if not title: out.append(P('error', 'title-missing', 'title is empty'))
    if len(title) > 100: out.append(P('error', 'title-long', 'title is %d characters (YouTube allows 100)' % len(title)))
    elif len(title) > 70: out.append(P('warn', 'title-short-truncates', 'title is %d characters; the Shorts feed cuts titles off after roughly 70' % len(title)))
    letters = [c for c in title if c.isalpha()]
    if len(title) > 12 and letters and all(c.isupper() for c in letters): out.append(P('warn', 'title-caps', 'all-caps title reads as spam'))
    if '<' in title or '>' in title or '<' in desc or '>' in desc: out.append(P('error', 'angle-brackets', 'YouTube rejects < and > in titles and descriptions'))
    if len(desc.encode('utf-8')) > 5000: out.append(P('error', 'description-long', 'description is %d bytes (limit 5000)' % len(desc.encode('utf-8'))))
    tags = meta.get('hashtags') or []
    if len(tags) > 15: out.append(P('error', 'hashtags-too-many', '%d hashtags: YouTube ignores ALL of them above 15' % len(tags)))
    for h in tags:
        if not h.startswith('#') or len(h) < 2 or any(c.isspace() for c in h): out.append(P('error', 'hashtag-format', 'bad hashtag %r (starts with #, no spaces)' % h))
    tl = sum(len(t) + (2 if ' ' in t else 0) for t in meta.get('tags') or []) + max(0, len(meta.get('tags') or []) - 1)
    if tl > 500: out.append(P('error', 'tags-too-long', 'tags total %d characters (limit 500)' % tl))
    if (meta.get('category') or 'Education') not in CATEGORIES: out.append(P('error', 'category-unknown', 'category %r is not one of: %s' % (meta.get('category'), ', '.join(CATEGORIES))))
    if meta.get('ai') is None: out.append(P('warn', 'ai-undisclosed', 'say whether AI was used (meta.json "ai": {voice, music, visuals}); we recommend disclosing'))
    if duration is not None and duration > 180: out.append(P('error', 'duration-long', 'video is %.1f s: a Short is at most 3 minutes' % duration))
    for e in prov or []:
        if e.get('rights_class') not in OK_RIGHTS: out.append(P('error', 'rights', '%s is %r: clear it or remove it before uploading' % (e.get('key') or e.get('title'), e.get('rights_class'))))
    return out


def used(meta, prov):
    """the provenance entries the film actually uses: meta.json "credits": [keys] (absent = all of provenance.json)"""
    if meta.get('credits') is None: return list(prov or [])
    return [e for e in prov or [] if e.get('key') in meta['credits']]


def _clean_title(t): return t[5:] if t.startswith('File:') else t


def build_description(meta, prov):
    prov = used(meta, prov)
    parts = [(meta.get('summary') or '').strip()]
    if meta.get('facts'): parts.append('\n'.join('- ' + f for f in meta['facts']))
    src = []
    for s in meta.get('sources') or []: src.append('- %s: %s' % (s['label'], s['url']))
    for e in prov or []:
        who = ', '.join(x for x in (e.get('creator'), str(e.get('year') or '')) if x); lic = (' [%s]' % e['license']) if e.get('rights_class') == 'attribution' and e.get('license') else ''
        src.append('- %s%s%s: %s' % (_clean_title(e.get('title') or e.get('key') or ''), (' (%s)' % who) if who else '', lic, e.get('landing') or ''))
    if src: parts.append('Sources & credits:\n' + '\n'.join(src))
    if meta.get('hashtags'): parts.append(' '.join(meta['hashtags']))
    return '\n\n'.join(p for p in parts if p).strip() + '\n'


def build_upload(meta, prov, duration=None):
    ai = meta.get('ai') or {}; lang = meta.get('language', 'en')
    return {'snippet': {'title': (meta.get('title') or '').strip(), 'description': build_description(meta, prov), 'tags': meta.get('tags') or [],
                        'categoryId': CATEGORIES.get(meta.get('category') or 'Education', '27'), 'defaultLanguage': lang, 'defaultAudioLanguage': lang},
            'status': {'privacyStatus': 'private', 'selfDeclaredMadeForKids': False, 'containsSyntheticMedia': any(bool(v) for v in ai.values()), 'license': 'youtube', 'embeddable': True}}


def checklist(meta, body, problems, name):
    ai = meta.get('ai') or {}; used = [k for k, v in ai.items() if v]
    lines = ['# Upload checklist: %s' % name, '', '## Title', body['snippet']['title'], '', '## Description (paste as is)', '```', body['snippet']['description'].rstrip(), '```', '',
             '## Tags', ', '.join(body['snippet']['tags']) or '(none)', '', '## Settings',
             '- Category: %s (id %s)' % (meta.get('category') or 'Education', body['snippet']['categoryId']),
             '- Audience: not made for kids', '- Visibility: private first; switch to public/scheduled after a human watch-through',
             '- Disclose altered/synthetic content: %s%s' % ('YES' if used else 'No', (' (' + ', '.join(used) + ')') if used else ''),
             '- Shorts links: links in Shorts descriptions may not be clickable on mobile; verify on a real phone and keep the credits as plain text anyway', '',
             '## Checks']
    lines += ['- [%s] %s: %s' % ('x' if p['level'] == 'warn' else ' ', p['code'], p['msg']) for p in problems] or ['- none']
    return '\n'.join(lines) + '\n'


def main(argv):
    if len(argv) < 1 or argv[0] in ('-h', '--help'): raise SystemExit(__doc__)
    proj = os.path.abspath(argv[0]); name = os.path.basename(proj)
    if not os.path.exists(os.path.join(proj, 'meta.json')): raise SystemExit('shorts-meta: no meta.json in %s (copy templates/shorts/meta.json)' % proj)
    meta = json.load(open(os.path.join(proj, 'meta.json')))
    prov = json.load(open(os.path.join(proj, 'provenance.json'))) if os.path.exists(os.path.join(proj, 'provenance.json')) else []
    duration = json.load(open(os.path.join(proj, 'cues.json'))).get('duration') if os.path.exists(os.path.join(proj, 'cues.json')) else None
    problems = validate(meta, prov, duration)
    for p in problems: print('%-5s %-22s %s' % (p['level'].upper(), p['code'], p['msg']))
    errors = [p for p in problems if p['level'] == 'error']
    if errors: print('%d error(s): fix meta.json first (nothing written)' % len(errors)); return 1
    body = build_upload(meta, prov, duration); out = os.path.join(REPO, 'out', name); os.makedirs(out, exist_ok=True)
    json.dump(body, open(os.path.join(out, 'upload.json'), 'w'), indent=1, ensure_ascii=False); open(os.path.join(out, 'upload.md'), 'w').write(checklist(meta, body, problems, name))
    print('wrote out/%s/upload.json and upload.md  (%d warning(s), %d sources credited, visibility private)' % (name, len(problems), len(used(meta, prov)) + len(meta.get('sources') or []))); return 0


if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
