/* captions.js - word-timed subtitles for short vertical films.  Load after motion.js.  Pure functions of t, like everything else.

   words: [{t:'Fermi', start:11.0, end:11.3, emph:false}, ...]    (voiceover.py writes them: out/<name>/vo/manifest.json -> [line].caps)
   const cap = PV.captions(words, { parent, css: 'left:60px;top:1180px;width:900px;', maxWords: 4, maxChars: 22 });
   in seek(t):  cap.update(t);              // shows the phrase being spoken, highlights the current word
   cap.groups                               // [{words, start, end}]  - the phrases, so a test (or the scene) can inspect them

   Phrases break after . ? ! , ; : (a spoken pause), after maxWords / maxChars, and at a silence longer than `gap` seconds.
   Needs CSS for .cap-g (the phrase), .cap-w (a word), .cap-w.on (the current word), .cap-w.emph (marked with *asterisks* in vo.json); see templates/shorts. */
(function (root) {
  'use strict';
  const END = /[.?!…]["')\]]*$/, PAUSE = /[,;:—–-]["')\]]*$/;

  function groups(words, o) {
    o = Object.assign({ maxWords: 4, maxChars: 22, gap: 0.45 }, o || {}); const out = []; let cur = [];
    const flush = () => { if (cur.length) { out.push({ words: cur, start: cur[0].start, end: cur[cur.length - 1].end }); cur = []; } };
    words.forEach((w, i) => {
      const chars = cur.reduce((n, x) => n + x.t.length + 1, 0) + w.t.length;
      if (cur.length && (cur.length >= o.maxWords || chars > o.maxChars || w.start - cur[cur.length - 1].end > o.gap)) flush();
      cur.push(w);
      if (END.test(w.t) || (PAUSE.test(w.t) && cur.length >= 2)) flush();
    });
    flush();
    // never leave a one-word orphan when it can join the previous phrase without breaking the limits (but not across a sentence end)
    for (let i = 1; i < out.length; i++) {
      const g = out[i], p = out[i - 1];
      if (g.words.length === 1 && !END.test(p.words[p.words.length - 1].t) && p.words.length < o.maxWords && p.words.reduce((n, x) => n + x.t.length + 1, 0) + g.words[0].t.length <= o.maxChars && g.start - p.end <= o.gap) {
        p.words = p.words.concat(g.words); p.end = g.end; out.splice(i, 1); i--;
      }
    }
    return out;
  }

  function create(words, o) {
    const PV = root.PV; o = Object.assign({ maxWords: 4, maxChars: 22, gap: 0.45, hold: 0.3, lead: 0.05, css: '', cls: '' }, o || {});
    const gs = groups(words, o), host = PV.mk('', o.css, o.parent, 'abs cap ' + o.cls);
    const els = gs.map(g => {
      const e = document.createElement('div'); e.className = 'cap-g'; e.style.display = 'none';
      g.spans = g.words.map((w, i) => { const s = document.createElement('span'); s.className = 'cap-w' + (w.emph ? ' emph' : ''); s.textContent = w.t; e.appendChild(s); if (i < g.words.length - 1) e.appendChild(document.createTextNode(' ')); return s; });
      host.appendChild(e); return e;
    });
    function update(t) {
      let active = -1;
      for (let i = 0; i < gs.length; i++) {                               // the last phrase that has begun and not yet been replaced / held out
        const next = gs[i + 1], until = Math.min(gs[i].end + o.hold, next ? next.start - o.lead : Infinity);
        if (t >= gs[i].start - o.lead && t < until) { active = i; break; }
      }
      els.forEach((e, i) => { if (i !== active && e.style.display !== 'none') e.style.display = 'none'; });
      if (active < 0) return -1;
      const g = gs[active], e = els[active]; e.style.display = '';
      const a = PV.eo4(PV.P(t, g.start - o.lead, g.start - o.lead + 0.14));               // phrase pops in
      PV.put(e, { y: (1 - a) * 22, s: 0.9 + 0.1 * a, o: Math.min(1, a * 1.6) * (1 - PV.P(t, g.end + o.hold - 0.12, g.end + o.hold)) });
      g.words.forEach((w, i) => {
        const on = t >= w.start && t < w.end + 0.06, done = t >= w.end + 0.06, s = g.spans[i];
        s.classList.toggle('on', on); s.style.opacity = (on || done || w.emph) ? 1 : 0.5;
        const k = on ? PV.eoB(PV.P(t, w.start, w.start + 0.12), 2.2) : 0; s.style.transform = on ? 'scale(' + (1 + 0.12 * k).toFixed(3) + ')' : 'none';
      });
      return active;
    }
    return { el: host, groups: gs, update };
  }

  const api = { groups, create };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root.PV) { root.PV.captions = create; root.PV.captionGroups = groups; }
})(typeof window !== 'undefined' ? window : globalThis);
