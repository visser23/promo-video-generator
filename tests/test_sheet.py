#!/usr/bin/env python3
"""sheet.py must keep the aspect ratio of what it tiles (a 9:16 short used to be squashed into 16:9 cells)."""
import os, sys, tempfile, subprocess
from PIL import Image
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, os.path.join(REPO, 'tools'))
import sheet as S

cw, ch, cols = S.cell_size(1920, 1080, 6); assert abs(cw / ch - 1920 / 1080) < 0.01 and cols == 3, (cw, ch, cols)
cw, ch, cols = S.cell_size(1080, 1920, 6); assert abs(cw / ch - 1080 / 1920) < 0.01 and cols >= 4, (cw, ch, cols)
assert S.cell_size(1080, 1920, 6, cols=2)[2] == 2, '--cols wins'
assert S.cell_size(1000, 1000, 6, width=200)[0] == 200, '--width sets the cell width'

with tempfile.TemporaryDirectory() as tmp:
    fs = []
    for i, col in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        p = os.path.join(tmp, 'p%d.png' % i); im = Image.new('RGB', (90, 160), col); im.putpixel((0, 0), (255, 255, 255)); im.save(p); fs.append(p)
    out = os.path.join(tmp, 's.png'); r = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'sheet.py'), out] + fs, capture_output=True, text=True); assert r.returncode == 0, r.stderr
    sh = Image.open(out); assert sh.height > sh.width * 0.3, sh.size                    # portrait cells, not a thin landscape strip
    cw, ch, cols = S.cell_size(90, 160, 3); x = 6 + 0 * (cw + 6)
    mid = sh.getpixel((x + cw // 2, 6 + ch // 2)); assert mid[0] > 200 and mid[1] < 60, mid  # first cell is red where we expect it
print('ok')
