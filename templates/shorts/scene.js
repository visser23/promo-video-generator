/* Shorts starter: archival film + captions + a three-line hook + an end card, all driven by cues.json (shots, title, end) and the voiceover's aligned words.
   A pure function of t, like everything here.  The things to change are in cues.json; copy trinity-bet's scene.js for bespoke graphics (cards, charts, stamps).
   Works with nothing but this folder: no shots -> a dark gradient; "vo": false -> demo captions. */
(async function () {
  'use strict';
  const C = await (await fetch('cues.json')).json();
  const name = location.pathname.split('/').filter(Boolean).slice(-2)[0];
  const M = C.vo ? await (await fetch('../../out/' + name + '/vo/manifest.json')).json() : null;
  const { P, lerp, eo3, eo4, ei3, eio3, mk, put, show, kinetic, kUpdate } = PV;
  const V = document.getElementById('v'), foot = document.getElementById('foot'), W = 1080, H = 1920, DUR = C.duration;
  const world = PV.createWorld(V, null, W, H); world.insertBefore(foot, world.firstChild);

  /* film: one element per distinct clip; exactly one shot is live at a time */
  const clips = {};
  for (const s of C.shots || []) if (!clips[s.clip]) {
    const c = await PV.footage.load('assets/clips/' + s.clip); c.mount(foot, 'left:0;top:0;width:' + W + 'px;height:' + H + 'px;'); clips[s.clip] = c;
  }
  mk('', '', world, 'abs').id = 'vig'; mk('', '', world, 'abs').id = 'scrim';

  /* hook + end card */
  const T = C.title, tag = mk(T.tag, 'left:70px;top:250px;', world, 'abs tag');
  const hook = T.lines.map((l, i) => kinetic(l, 'left:70px;top:' + (312 + i * (T.px + 10)) + 'px;font-size:' + T.px + 'px;padding:.06em .02em;', i === T.lines.length - 1 ? 'linear-gradient(180deg,#fff0a8,#ff5a1f)' : 'linear-gradient(180deg,#fff,#e9e3d3)'));
  const E = C.end, endLines = E.lines.map((l, i) => kinetic(l, 'left:70px;top:' + (450 + i * 200) + 'px;font-size:182px;padding:.06em .02em;', i === E.lines.length - 1 ? 'linear-gradient(180deg,#fff0a8,#ff5a1f)' : 'linear-gradient(180deg,#fff,#e9e3d3)'));
  const pill = mk(E.cta, '', world, 'abs pill'), credit = mk(E.credit, '', world, 'abs credit');

  /* captions from the aligned words (script-accurate; *emphasis* from vo.json) */
  const words = M ? M.flatMap(l => l.caps.map(c => ({ t: c.t, start: c.start, end: c.end, emph: c.emph }))) :
    [['A', 0.4], ['SHORT,', 0.7], ['SPECIFIC', 1.2], ['OPENING', 1.8], ['LINE', 2.3]].map(([t, s]) => ({ t, start: s, end: s + 0.4 }));
  const cap = PV.captions(words, { parent: world, maxWords: 3, maxChars: 17, hold: 0.22, lead: 0.04 });
  const flashEl = mk('', '', world, 'abs'); flashEl.id = 'flash';

  window.seek = async function (t) {
    const cur = (C.shots || []).find(s => clips[s.clip] && t >= s.a && t < s.b);
    Object.keys(clips).forEach(n => show(clips[n].el, !!cur && cur.clip === n));
    if (cur) {
      const c = clips[cur.clip], el = c.el; c.at(t - cur.a, { speed: cur.speed, offset: cur.off, blend: true });
      el.style.setProperty('--pos', cur.pos); el.style.transformOrigin = cur.pos;
      el.style.filter = 'sepia(.22) saturate(.75) contrast(1.12) brightness(' + (cur.dim * (1 + 0.05 * Math.sin(t * 53))).toFixed(3) + ')';   // film flicker
      put(el, { s: lerp(cur.z[0], cur.z[1], eio3(P(t, cur.a, cur.b))), x: Math.sin(t * 7.3) * 1.4, y: Math.sin(t * 5.1 + 1) * 1.1 });  // gate weave + slow push
    }
    const sh = PV.shake(t, C.flashAt ? [[C.flashAt, 34]] : []); world.style.transform = 'translate3d(' + sh.x.toFixed(2) + 'px,' + sh.y.toFixed(2) + 'px,0)';
    put(tag, { y: (1 - eo4(P(t, T.in - 0.15, T.in + 0.25))) * 24, o: Math.min(P(t, T.in - 0.15, T.in + 0.15), 1 - P(t, T.out, T.out + 0.2)) });
    hook.forEach((k, i) => kUpdate(k, t, T.in + 0.22 * i, T.out + 0.06 * i, 0.03));
    endLines.forEach((k, i) => kUpdate(k, t, E.in + 0.2 * i, null, 0.03));
    const pa = PV.spring(t, E.ctaIn, 2.0, 7); put(pill, { y: (1 - Math.min(pa, 1.08)) * 160, s: lerp(0.8, 1, Math.min(pa, 1.06)), o: t < E.ctaIn ? 0 : 1 }); put(credit, { o: P(t, E.in + 0.3, E.in + 0.7) * (t >= E.in ? 1 : 0) });
    const f = Math.max(C.flashAt ? (t < C.flashAt ? 0 : Math.exp(-(t - C.flashAt) * 4.5)) : 0, 0.8 * (1 - eo3(P(t, 0, 0.4))), eio3(P(t, C.loopFlash, DUR)));   // opens and closes on a white flash: a seamless loop
    flashEl.style.opacity = f.toFixed(3); flashEl.style.visibility = f < 0.002 ? 'hidden' : 'visible';
    cap.update(t);
    await PV.footage.settle();
  };
  await PV.loaded(['400 100px Anton', '700 40px "Courier Prime"', '700 40px Inter']);
  await window.seek(0); PV.ready();
})();
