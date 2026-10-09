#!/usr/bin/env python3
"""sheet.py - tile images into one labelled contact sheet so a whole scene can be reviewed at a glance.
   python3 tools/sheet.py out.png in1.png in2.png ... [--cols N] [--width W]        (needs Pillow: pip install pillow)
   Cells keep the aspect ratio of the first image (16:9 -> 3 columns of 640 px; 9:16 shorts -> 5 columns of 270 px) unless --cols / --width say otherwise."""
import sys


def cell_size(w, h, n, cols=None, width=None):
    """-> (cell width, cell height, columns) that keep w:h.  Landscape: 640 px wide, 3 columns.  Portrait / square: 480 px tall, 5 columns."""
    landscape = w >= h * 1.2
    if width: cw = int(width)
    else: cw = 640 if landscape else max(1, round(480 * w / h))
    ch = max(1, round(cw * h / w)); c = int(cols) if cols else (3 if landscape else 5)
    return cw, ch, max(1, min(c, max(n, 1)) if not cols else c)


def main(argv):
    from PIL import Image, ImageDraw
    a = list(argv); opts = {}
    for k in ('--cols', '--width'):
        if k in a: i = a.index(k); opts[k[2:]] = a[i + 1]; del a[i:i + 2]
    if len(a) < 2: raise SystemExit(__doc__)
    out, files = a[0], a[1:]
    w0, h0 = Image.open(files[0]).size; cw, ch, cols = cell_size(w0, h0, len(files), **opts)
    rows = (len(files) + cols - 1) // cols
    S = Image.new('RGB', (cols * (cw + 6), rows * (ch + 6)), 'white')
    for i, f in enumerate(files):
        im = Image.open(f).convert('RGB').resize((cw, ch)); d = ImageDraw.Draw(im)
        d.rectangle((0, 0, min(cw, 150), 26), fill='black'); d.text((6, 6), f.split('/')[-1].rsplit('.', 1)[0], fill='white')
        S.paste(im, ((i % cols) * (cw + 6), (i // cols) * (ch + 6)))
    S.save(out); print('wrote', out, S.size)


if __name__ == '__main__': main(sys.argv[1:])
