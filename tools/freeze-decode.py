#!/usr/bin/env python3
"""Save the HTML string returned by tools/freeze-page.js when it came out of the Cursor browser.

Cursor writes large CDP results to ~/.cursor/browser-logs/cdp-response-Runtime.evaluate-*.json instead of returning them inline.
This picks the NEWEST such dump (or a file you name) and writes the string it contains.

    python3 tools/freeze-decode.py projects/my-film/frozen/home.html           # newest dump
    python3 tools/freeze-decode.py projects/my-film/frozen/home.html dump.json  # a specific dump
"""
import glob, json, os, sys

def newest_dump():
    files = sorted(glob.glob(os.path.expanduser('~/.cursor/browser-logs/cdp-response-Runtime.evaluate-*.json')), key=os.path.getmtime)
    if not files: sys.exit('no cdp-response-Runtime.evaluate-*.json found in ~/.cursor/browser-logs (run __pvFreeze() through Runtime.evaluate first)')
    return files[-1]

def main(argv):
    if not argv: sys.exit(__doc__)
    out, src = argv[0], (argv[1] if len(argv) > 1 else newest_dump())
    d = json.load(open(src))
    while isinstance(d, dict) and 'result' in d: d = d['result']
    html = d['value'] if isinstance(d, dict) else d
    if not isinstance(html, str) or '<html' not in html[:2000].lower(): sys.exit(f'{src} does not look like a frozen page (got {type(html).__name__}); was awaitPromise/returnByValue set?')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'w').write(html)
    print(f'wrote {out} ({len(html):,} chars) from {src}')

if __name__ == '__main__': main(sys.argv[1:])
