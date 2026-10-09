/* footage.js - archival film as a pure function of time.  Load after motion.js.

   A <video> element seeks asynchronously and may land on a neighbouring frame, so scenes never use one.  tools/clip.py turns a shot into numbered
   JPEGs (+ clip.json); this maps t -> frame number and shows exactly that file, so seek(5.2) is the same picture on every machine, every run.

     const fire = await PV.footage.load('assets/clips/fireball');          // reads clip.json, preloads nothing yet
     world.appendChild(fire.el);                                           // or fire.mount(parent, 'left:0;top:0;width:1080px;height:810px;')
     in seek(t):   fire.at(t - 12.0, { speed: 1, blend: true });           // sync DOM work; the image decode is queued
                   ...                                                     // do ALL other DOM updates first (so safe-area.js, which does not await, sees them)
                   await PV.footage.settle();                              // LAST line of an `async` seek: waits until every shown frame has decoded
   at(local, opts): opts.speed (1 = real time; 0.5 = slow motion; negative = backwards), opts.offset (seconds into the clip to start from),
                    opts.loop (wrap around), opts.blend (cross-fade the two nearest frames: smoother slow motion, soft ghosting on fast action),
                    opts.hold (default true: clamp to the first/last frame outside the clip).  Returns the fractional frame it displayed.
   The two <img> are position:absolute, inset 0, object-fit: cover (change with CSS on .pv-clip img).  Style the element however you like
   (filter, mix-blend-mode, mask, transform via PV.put) - it is an ordinary div. */
(function (root) {
  'use strict';
  const pending = [];

  const pad = (i, n) => String(i).padStart(n, '0');
  /* frameAt(clip, local, opts) -> fractional frame index (0-based).  Pure; unit-tested in node. */
  function frameAt(c, local, o) {
    o = o || {}; const speed = o.speed === undefined ? 1 : o.speed;
    let f = (local * speed + (o.offset || 0)) * c.fps;
    if (o.loop) { f = ((f % c.n) + c.n) % c.n; return f; }
    return Math.max(0, Math.min(c.n - 1, f));
  }

  function show(img, c, idx) {
    if (img.__idx === idx) return;
    img.__idx = idx; img.src = c.dir + '/' + pad(idx + 1, 5) + '.jpg';
    pending.push(img.decode ? img.decode().catch(() => 0) : Promise.resolve());
  }

  async function load(dir) {
    dir = dir.replace(/\/$/, ''); const meta = await (await fetch(dir + '/clip.json')).json();
    const c = Object.assign({ dir }, meta), el = document.createElement('div'); el.className = 'pv-clip abs'; el.style.cssText = 'overflow:hidden;';
    const mk = () => { const i = document.createElement('img'); i.draggable = false; i.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;object-fit:cover;'; el.appendChild(i); return i; };
    const A = mk(), B = mk(); B.style.opacity = 0;
    c.el = el; c.A = A; c.B = B;
    c.mount = (parent, css) => { if (css) el.style.cssText += css; (parent || root.PV.world).appendChild(el); return c; };
    c.at = (local, o) => {
      o = o || {}; const f = frameAt(c, local, o), i = Math.floor(f), k = f - i;
      show(A, c, i);
      if (o.blend && k > 0.03 && i + 1 < c.n) { show(B, c, i + 1); B.style.opacity = k.toFixed(3); } else B.style.opacity = 0;
      return f;
    };
    c.duration = c.n / c.fps;
    show(A, c, 0); await Promise.all(pending.splice(0));                    // the first frame is ready before the scene reports ready
    return c;
  }

  /* settle(): resolves when every frame shown since the last call has decoded.  Await it at the end of an async seek(). */
  const settle = () => Promise.all(pending.splice(0));

  const api = { load, settle, frameAt };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root.PV) root.PV.footage = api;
})(typeof window !== 'undefined' ? window : globalThis);
