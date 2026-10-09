/* freeze-page.js - turn the page you are looking at into ONE standalone, script-free HTML string, so it can be photographed later
   by headless Chrome (assets, stills, a fake cursor landing on a real button) without a login, a network or the live site.

   It runs INSIDE a page.  Typical use (Cursor browser, see docs/FREEZE.md):
       Runtime.evaluate { expression: "<contents of this file>;  __pvFreeze({ scroll: true })", awaitPromise: true, returnByValue: true }
   or in Playwright:  await page.addScriptTag({ path: 'tools/freeze-page.js' }); const html = await page.evaluate(() => __pvFreeze());

   What it does: (1) optionally scrolls to the bottom and back so lazy / reveal-on-scroll content mounts; (2) inlines every readable stylesheet
   (and its url() assets) and every same-origin <img>/<source> as data: URIs; (3) removes <script>, <link rel=preload|modulepreload|prefetch> and inline
   event handlers; (4) removes anything matching opts.mask (CSS selectors; default: avatars / account links) so private data never reaches disk.
   It returns the HTML string.  It never sends anything anywhere.  Cross-origin images that the page itself cannot read are left as-is (they will 404 offline).
   Use only on pages you are allowed to capture and DO NOT keep the result if it contains personal data (the output is git-ignored territory: projects/<name>/frozen/). */
(function () {
  const blobToDataUri = b => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(b); });
  async function toData(url) {
    try { const r = await fetch(url, { credentials: 'same-origin' }); if (!r.ok) return null; return await blobToDataUri(await r.blob()); } catch (e) { return null; }
  }
  async function inlineCssUrls(css, base) {
    const re = /url\(\s*(['"]?)(?!data:|#)([^'")]+)\1\s*\)/g, seen = new Map(), jobs = [];
    css.replace(re, (m, q, u) => { if (!seen.has(u)) { seen.set(u, null); jobs.push(toData(new URL(u, base).href).then(d => seen.set(u, d))); } return m; });
    await Promise.all(jobs);
    return css.replace(re, (m, q, u) => seen.get(u) ? `url("${seen.get(u)}")` : m);
  }
  window.__pvFreeze = async function (opts = {}) {
    const mask = opts.mask || ['img[alt*="avatar" i]', '[class*="avatar" i]', 'a[href*="account" i]', 'a[href*="settings" i]'];
    if (opts.scroll) {
      const step = Math.max(200, innerHeight * 0.8), end = document.documentElement.scrollHeight;
      for (let y = 0; y < end; y += step) { scrollTo(0, y); await new Promise(r => setTimeout(r, opts.settleMs || 120)); }
      scrollTo(0, 0); await new Promise(r => setTimeout(r, 200));
    }
    const doc = document.documentElement.cloneNode(true);
    /* stylesheets: read rules from the live sheets (works for cssRules-readable ones), fall back to fetching the href */
    const styles = [];
    for (const sh of Array.from(document.styleSheets)) {
      let css = null, base = sh.href || location.href;
      try { css = Array.from(sh.cssRules).map(r => r.cssText).join('\n'); } catch (e) { if (sh.href) { try { css = await (await fetch(sh.href, { credentials: 'same-origin' })).text(); } catch (e2) { css = null; } } }
      if (css) styles.push(await inlineCssUrls(css, base));
    }
    doc.querySelectorAll('link[rel~="stylesheet"], style').forEach(n => n.remove());
    doc.querySelectorAll('script, noscript, link[rel~="preload"], link[rel~="modulepreload"], link[rel~="prefetch"]').forEach(n => n.remove());
    const head = doc.querySelector('head'), st = document.createElement('style'); st.textContent = styles.join('\n'); head.appendChild(st);
    doc.querySelectorAll('*').forEach(n => { for (const a of Array.from(n.attributes)) if (/^on/i.test(a.name)) n.removeAttribute(a.name); });
    /* images: the clone has the same order as the live document */
    const live = Array.from(document.querySelectorAll('img')), cl = Array.from(doc.querySelectorAll('img'));
    await Promise.all(cl.map(async (im, i) => {
      const src = live[i] && (live[i].currentSrc || live[i].src); if (!src || src.startsWith('data:')) return;
      const d = await toData(src); if (d) { im.setAttribute('src', d); im.removeAttribute('srcset'); im.removeAttribute('loading'); }
    }));
    if (mask.length) doc.querySelectorAll(mask.join(',')).forEach(n => n.remove());
    doc.querySelectorAll('base').forEach(n => n.remove());
    return '<!doctype html>\n' + doc.outerHTML;
  };
})();
