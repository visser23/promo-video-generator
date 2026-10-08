/* Exercise optional helpers in real Chrome, including backwards seeks. */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({ channel: process.env.PV_CHANNEL ?? 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 320, height: 180 } });
    await page.setContent('<canvas width="320" height="180"></canvas>');
    for (const file of ['motion.js', 'timing.js']) await page.addScriptTag({ path: path.join(__dirname, '../lib', file) });
    await page.evaluate(() => {
      const canvas = document.querySelector('canvas'), ctx = canvas.getContext('2d');
      const position = PV.keyframes([[0, 30], [1, 240]], PV.eio3);
      const clock = PV.beatClock(120);
      const track = PV.shots([[0, '#112233'], [0.5, '#334455']], 1);
      window.seek = t => {
        ctx.clearRect(0, 0, 320, 180);
        ctx.fillStyle = track(t)?.value || '#000000'; ctx.fillRect(0, 0, 320, 180);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(position(t), 60 + 3 * PV.boil(t, 'card'), 20 + 8 * clock.pulse(t), 40);
      };
    });
    const frame = async t => { await page.evaluate(t => window.seek(t), t); return page.screenshot(); };
    const a = await frame(0.6);
    const b = await frame(0.2);
    assert(!a.equals(b));
    assert(a.equals(await frame(0.6)), 'Backwards/out-of-order seeks changed pixels');
    const boundary = await frame(0.5);
    await frame(0.99);
    assert(boundary.equals(await frame(0.5)), 'Shot boundary changed pixels');
    console.log('PASS timing browser: actual Chrome pixels stable after out-of-order seeks');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
