/* Optional deterministic timing tools. Load after motion.js. No renderer dependencies. */
(function () {
  'use strict';
  if (!window.PV) throw new Error('Load motion.js before timing.js');
  const finite = (x, name) => {
    if (!Number.isFinite(x)) throw new TypeError(`${name} must be finite`);
    return x;
  };
  const positive = (x, name) => {
    finite(x, name);
    if (x <= 0) throw new RangeError(`${name} must be positive`);
    return x;
  };
  function ordered(entries) {
    if (!Array.isArray(entries) || !entries.length) throw new TypeError('Expected a non-empty list');
    return entries.map((entry, i) => {
      if (!Array.isArray(entry) || entry.length !== 2) throw new TypeError('Expected [time, value] pairs');
      finite(entry[0], 'time');
      if (i && entry[0] <= entries[i - 1][0]) throw new RangeError('Times must strictly increase');
      return entry.slice();
    });
  }
  // Validate and snapshot once, then evaluate scalar or fixed-width vector keyframes.
  function keyframes(entries, easing = x => x) {
    const keys = ordered(entries);
    if (typeof easing !== 'function') throw new TypeError('Easing must be a function');
    const vector = Array.isArray(keys[0][1]);
    const width = vector ? keys[0][1].length : 0;
    if (vector && !width) throw new TypeError('Vectors must not be empty');
    for (const key of keys) {
      const v = key[1];
      if (vector) {
        if (!Array.isArray(v) || v.length !== width) throw new TypeError('Vector dimensions must match');
        key[1] = v.map(x => finite(x, 'value'));
      } else finite(v, 'value');
    }
    const copy = v => vector ? v.slice() : v;
    return t => {
      finite(t, 'time');
      if (t <= keys[0][0]) return copy(keys[0][1]);
      for (let i = 1; i < keys.length; i++) {
        if (t < keys[i][0]) {
          const [a, from] = keys[i - 1], [b, to] = keys[i];
          const k = finite(easing((t - a) / (b - a)), 'easing result');
          const blend = (x, y) => x + (y - x) * k;
          return vector ? from.map((x, j) => blend(x, to[j])) : blend(from, to);
        }
      }
      return copy(keys[keys.length - 1][1]);
    };
  }
  function beatClock(bpm, offset = 0) {
    const seconds = 60 / positive(bpm, 'bpm');
    finite(offset, 'offset');
    return Object.freeze({
      seconds,
      time: beat => offset + finite(beat, 'beat') * seconds,
      position: t => (finite(t, 'time') - offset) / seconds,
      pulse(t, subdivision = 1, decay = 6) {
        finite(t, 'time'); positive(subdivision, 'subdivision'); positive(decay, 'decay');
        if (t < offset) return 0;
        const p = (t - offset) / seconds * subdivision;
        // Snap floating-point values very close to an exact beat.
        const nearest = Math.round(p);
        const phase = Math.abs(p - nearest) < 1e-10 ? 0 : p - Math.floor(p);
        return Math.exp(-phase * decay);
      }
    });
  }
  // Address each random sample by time bucket, object/channel identity and seed.
  // Unlike a mutable RNG, call order cannot change the result.
  function boil(t, id, rate = 12, seed = 0) {
    finite(t, 'time'); positive(rate, 'rate'); finite(seed, 'seed');
    if (typeof id !== 'string' && !Number.isFinite(id)) throw new TypeError('id must be a string or finite number');
    const text = JSON.stringify([Math.floor(t * rate), id, seed]);
    let h = 2166136261;
    for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
    return window.PV.rng(h >>> 0)() * 2 - 1;
  }
  // Half-open shots: the new shot owns the cut, and the end belongs to no shot.
  function shots(entries, end) {
    const keys = ordered(entries);
    finite(end, 'end');
    if (end <= keys[keys.length - 1][0]) throw new RangeError('End must follow the final shot');
    return t => {
      finite(t, 'time');
      if (t < keys[0][0] || t >= end) return null;
      let i = keys.length - 1;
      while (t < keys[i][0]) i--;
      return { value: keys[i][1], index: i, start: keys[i][0], local: t - keys[i][0],
        duration: (i + 1 < keys.length ? keys[i + 1][0] : end) - keys[i][0] };
    };
  }
  Object.assign(window.PV, { keyframes, beatClock, boil, shots });
})();
