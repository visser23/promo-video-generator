#!/usr/bin/env python3
"""voiceover.py - synthesise a voiceover, line by line, and write a timing manifest the picture and the mix can both read.

  python3 tools/voiceover.py projects/<name>            # reads projects/<name>/vo.json -> out/<name>/vo/<id>.wav + manifest.json
  python3 tools/voiceover.py projects/<name> --report   # only print the pace report from the last run

vo.json:
  {
    "engine": "piper",                      // "piper" | "kokoro" (more natural; see class Kokoro) | "say" (macOS built-in voices)
    "voice": "en_GB-cori-high",             // piper: a model name in ~/.cache/piper-voices (auto-downloaded from rhasspy/piper-voices)
                                            // say:   a voice name from `say -v '?'`, e.g. "Daniel"
    "length_scale": 1.0,                    // piper: >1 slower, <1 faster (default pace for lines without "fit")
    "noise_scale": 0.55, "noise_w_scale": 0.65,   // piper: lower = steadier, calmer delivery
    "lead": 0.0,                            // seconds of room tone kept before each line's first sound
    "lines": [
      { "id": "hook", "text": "Before spending money on AI, ...",
        "say": "optional respelling the engine reads instead of text (e.g. 'fifteen' for '15')",
        "at": 0.25,                         // start time in seconds, or the NAME of a cue in cues.json
        "fit": [0.25, 4.1] }                // optional window: the line is re-synthesised slower/faster until it lasts (end - start)
    ]
  }

--align (optional, needs `pip install faster-whisper`): transcribes every rendered line with Whisper to (a) store word-level times in the manifest
("words": [{"w", "start", "end"}] (and "nwords" is the script word count), absolute seconds) so the picture can key on spoken words, and (b) print a word-error rate against the script, which is
the closest thing to "listening" an agent can do: a line Whisper cannot recognise will not be understood by a viewer either.

Markup: in a line's "text", *asterisks* mark words the captions emphasise (never spoken).  The manifest also holds "caps": [{t, emph, start, end}] - the SCRIPT's
words (correct spelling/punctuation) on Whisper's clock (evenly spread when --align is off), which lib/captions.js turns into word-timed subtitles.

A line is trimmed of leading/trailing silence, so "at" is the moment the first word is heard.  The manifest reports start / end / words / wpm per line,
so you can see at a glance whether the cadence is calm (140-150 wpm) or hurried (> 175 wpm), and the scene can key on-screen text to the spoken words.
The wav files are mono, 44.1 kHz, peak-normalised to -3 dBFS; lib/synth.py (add_voice) places them in the mix and ducks the music under them.
"""
import json, os, re, subprocess, sys, tempfile, urllib.request, wave
import numpy as np
from scipy import signal

SR = 44100
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CACHE = os.path.expanduser('~/.cache/piper-voices')
HF = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/'


def read_wav(path):
    with wave.open(path, 'rb') as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), '<i2').astype(np.float64) / 32768
    if ch > 1: x = x.reshape(-1, ch).mean(1)
    return x, sr


def write_wav(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())


def trim(x, sr, thresh_db=-42.0, keep=0.0):
    """strip leading/trailing silence (frame RMS under thresh_db relative to the line's own peak); keep `keep` seconds of lead"""
    if len(x) == 0: return x
    hop = int(sr * 0.005); fr = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, 'same'))
    ok = np.where(fr > np.max(np.abs(x)) * 10 ** (thresh_db / 20))[0]
    if len(ok) == 0: return x
    a = max(0, ok[0] - int(sr * 0.012) - int(keep * sr)); b = min(len(x), ok[-1] + int(sr * 0.04))
    y = x[a:b].copy(); f = int(sr * 0.006); y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
    return y


def ensure_piper_model(voice):
    onnx = os.path.join(CACHE, voice + '.onnx')
    if os.path.exists(onnx) and os.path.exists(onnx + '.json'): return onnx
    lang, rest = voice.split('-', 1)[0], voice.split('-', 1)[1]      # en_GB-cori-high -> en/en_GB/cori/high/en_GB-cori-high
    name, quality = rest.rsplit('-', 1)
    base = f'{HF}{lang.split("_")[0]}/{lang}/{name}/{quality}/{voice}'
    os.makedirs(CACHE, exist_ok=True)
    for ext in ('.onnx', '.onnx.json'):
        print(f'downloading {voice}{ext} ...'); urllib.request.urlretrieve(base + ext, os.path.join(CACHE, voice + ext))
    return onnx


class Piper:
    def __init__(self, cfg):
        from piper import PiperVoice, SynthesisConfig
        self.SC = SynthesisConfig; self.v = PiperVoice.load(ensure_piper_model(cfg['voice']))
        self.cfg = cfg
    def say(self, text, length_scale):
        sc = self.SC(length_scale=length_scale, noise_scale=self.cfg.get('noise_scale', 0.55), noise_w_scale=self.cfg.get('noise_w_scale', 0.65), normalize_audio=True)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f: p = f.name
        with wave.open(p, 'wb') as w: self.v.synthesize_wav(text, w, syn_config=sc)
        x, sr = read_wav(p); os.unlink(p); return x, sr


class Kokoro:
    """Kokoro-82M (Apache-2.0) via kokoro-onnx: markedly more natural than Piper for narration.  pip install kokoro-onnx; model files in ~/.cache/kokoro
    (kokoro-v1.0.onnx + voices-v1.0.bin from github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0).
    vo.json: {"engine": "kokoro", "voice": "bm_george", "lang": "en-gb", "sentence_gap": 0.22}.  British: bf_emma bf_isabella bm_george bm_fable bm_lewis bm_daniel;  US: af_heart af_bella am_michael am_fenrir ..."""
    DIR = os.path.expanduser('~/.cache/kokoro')
    def __init__(self, cfg):
        from kokoro_onnx import Kokoro as K
        m, v = os.path.join(self.DIR, 'kokoro-v1.0.onnx'), os.path.join(self.DIR, 'voices-v1.0.bin')
        if not (os.path.exists(m) and os.path.exists(v)): sys.exit(f'kokoro model files missing in {self.DIR} (see the Kokoro docstring in tools/voiceover.py)')
        self.k = K(m, v); self.cfg = cfg
    def say(self, text, length_scale):
        parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+', text) if p.strip()]; gap = self.cfg.get('sentence_gap', 0.22); out = []; sr = 24000
        for i, p in enumerate(parts):
            x, sr = self.k.create(p, voice=self.cfg['voice'], speed=1.0 / length_scale, lang=self.cfg.get('lang', 'en-gb'))
            out.append(x.astype(np.float64))
            if i < len(parts) - 1: out.append(np.zeros(int(sr * gap * length_scale)))
        return np.concatenate(out), sr


class MacSay:
    def __init__(self, cfg): self.cfg = cfg
    def say(self, text, length_scale):
        rate = int(round(self.cfg.get('wpm', 175) / length_scale))
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f: p = f.name
        subprocess.run(['say', '-v', self.cfg['voice'], '-r', str(rate), '--data-format=LEI16@44100', '-o', p, text], check=True)
        x, sr = read_wav(p); os.unlink(p); return x, sr


def strip_markup(text):
    """'a *b c* d' -> ('a b c d', [{'t':'a','emph':False}, {'t':'b','emph':True}, ...]).  *asterisks* mark words the captions emphasise; they are never spoken."""
    toks, cur, cur_emph, emph = [], '', False, False         # a word ends at whitespace only, so '*bet*?' is one token 'bet?'
    for ch in text:
        if ch == '*': emph = not emph; continue
        if ch.isspace():
            if cur: toks.append({'t': cur, 'emph': cur_emph}); cur, cur_emph = '', False
            continue
        cur += ch; cur_emph = cur_emph or emph
    if cur: toks.append({'t': cur, 'emph': cur_emph})
    return ' '.join(t['t'] for t in toks), toks


def _alnum(s): return re.sub(r'[^a-z0-9]', '', s.lower())


def align_captions(script, heard, start, end):
    """Give every word of the SCRIPT (correct spelling, punctuation, emphasis) a time.  Times come from Whisper's `heard` words
    ([{'w','start','end'}], absolute seconds) matched by a fuzzy global alignment; script words Whisper dropped or mangled are interpolated
    between their neighbours (by length); with nothing heard the words are spread over [start, end] by length."""
    import difflib
    n, m = len(script), len(heard)
    a = [_alnum(t['t']) for t in script]; b = [_alnum(h['w']) for h in heard]
    sim = lambda i, j: (difflib.SequenceMatcher(None, a[i], b[j]).ratio() if a[i] and b[j] else 0.0)
    GAP = -0.55; S = [[0.0] * (m + 1) for _ in range(n + 1)]; bt = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1): S[i][0] = i * GAP; bt[i][0] = 1
    for j in range(1, m + 1): S[0][j] = j * GAP; bt[0][j] = 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = sim(i - 1, j - 1); diag = S[i - 1][j - 1] + (s if s >= 0.6 else -1.0)
            up, left = S[i - 1][j] + GAP, S[i][j - 1] + GAP
            best = max(diag, up, left); S[i][j] = best; bt[i][j] = 0 if best == diag else (1 if best == up else 2)
    match = {}; i, j = n, m
    while i > 0 or j > 0:
        mv = bt[i][j] if i > 0 and j > 0 else (1 if i > 0 else 2)
        if mv == 0:
            if sim(i - 1, j - 1) >= 0.6: match[i - 1] = j - 1
            i -= 1; j -= 1
        elif mv == 1: i -= 1
        else: j -= 1
    caps = [None] * n
    for i, j in match.items(): caps[i] = (float(heard[j]['start']), float(heard[j]['end']))
    i = 0
    while i < n:                                            # fill each run of unmatched words between the nearest matched neighbours
        if caps[i] is not None: i += 1; continue
        k = i
        while k < n and caps[k] is None: k += 1
        t0 = caps[i - 1][1] if i > 0 else float(start); t1 = caps[k][0] if k < n else float(end); t1 = max(t1, t0)
        w = [len(script[x]['t']) + 1 for x in range(i, k)]; tot = float(sum(w)); acc = t0
        for x in range(i, k):
            d = (t1 - t0) * w[x - i] / tot; caps[x] = (acc, acc + d); acc += d
        i = k
    out = []; prev = float(start)
    for t, (s0, s1) in zip(script, caps):
        s0 = max(s0, prev); s1 = max(s1, s0); out.append({'t': t['t'], 'emph': t['emph'], 'start': round(s0, 3), 'end': round(s1, 3)}); prev = s0
    return out


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'): print(__doc__); sys.exit(0 if len(sys.argv) > 1 else 2)
    proj = os.path.abspath(sys.argv[1]); name = os.path.basename(proj)
    out = os.path.join(REPO, 'out', name, 'vo'); man_path = os.path.join(out, 'manifest.json')
    if '--report' in sys.argv: return report(json.load(open(man_path)))
    if not os.path.exists(os.path.join(proj, 'vo.json')): print(f'no vo.json in {proj} (see the docstring: engine, voice, lines[{{id, text, at}}])'); sys.exit(2)
    cfg = json.load(open(os.path.join(proj, 'vo.json'))); cues = json.load(open(os.path.join(proj, 'cues.json')))
    eng = {'piper': Piper, 'say': MacSay, 'kokoro': Kokoro}[cfg.get('engine', 'piper')](cfg)
    base = cfg.get('length_scale', 1.0); lead = cfg.get('lead', 0.0); manifest = []
    for ln in cfg['lines']:
        text, _ = strip_markup(ln.get('say') or ln['text']); plain, disp = strip_markup(ln['text'])
        at = ln.get('at', 0); at = cues[at] if isinstance(at, str) else float(at)
        def render(ls):
            x, sr = eng.say(text, ls)
            if sr != SR: g = np.gcd(sr, SR); x = signal.resample_poly(x, SR // g, sr // g)
            return trim(x, SR, keep=lead)
        ls = ln.get('length_scale', base); x = render(ls)
        if 'fit' in ln:                              # converge on the requested duration (speech duration is ~linear in length_scale)
            want = ln['fit'][1] - ln['fit'][0]; at = ln['fit'][0]
            for _ in range(4):
                have = len(x) / SR
                if abs(have - want) < 0.03: break
                ls *= want / have; x = render(ls)
            if len(x) / SR > want + 0.05: print(f'  WARN {ln["id"]}: {len(x)/SR:.2f}s does not fit {want:.2f}s even at length_scale {ls:.2f}')
        x = x / max(1e-9, np.max(np.abs(x))) * 10 ** (-3 / 20)
        write_wav(os.path.join(out, ln['id'] + '.wav'), x)
        words = len(disp); dur = len(x) / SR
        manifest.append({'id': ln['id'], 'text': plain, 'tokens': disp, 'start': round(at, 3), 'end': round(at + dur, 3), 'dur': round(dur, 3), 'nwords': words, 'wpm': round(words / dur * 60), 'length_scale': round(ls, 3)})
        manifest[-1]['caps'] = align_captions(disp, [], at, at + dur)      # even spread; --align replaces it with Whisper's word times
        print(f'  {ln["id"]:<8} {at:6.2f} -> {at + dur:6.2f}  ({dur:4.2f}s, {words:2d} words, {words / dur * 60:3.0f} wpm, length_scale {ls:.2f})')
    if '--align' in sys.argv: align(manifest, out)
    json.dump(manifest, open(man_path, 'w'), indent=1); report(manifest)


NUM = {'15': 'fifteen', '90': 'ninety', '5': 'five', '30': 'thirty', '60': 'sixty'}
def norm(t): return [NUM.get(w, w) for w in re.sub(r"[^a-z0-9' ]", ' ', t.lower().replace('-', ' ')).split()]


def align(manifest, out):
    from faster_whisper import WhisperModel
    m = WhisperModel('base.en', device='cpu', compute_type='int8')
    for ln in manifest:
        segs, _ = m.transcribe(os.path.join(out, ln['id'] + '.wav'), word_timestamps=True, language='en')
        ws = [w for s in segs for w in s.words]
        ln['words'] = [{'w': w.word.strip(), 'start': round(ln['start'] + float(w.start), 3), 'end': round(ln['start'] + float(w.end), 3)} for w in ws]
        ref, hyp = norm(ln['text']), norm(' '.join(w['w'] for w in ln['words']))
        d = [[i + j if i * j == 0 else 0 for j in range(len(hyp) + 1)] for i in range(len(ref) + 1)]       # Levenshtein over words
        for i in range(1, len(ref) + 1):
            for j in range(1, len(hyp) + 1): d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
        ln['wer'] = round(d[-1][-1] / max(1, len(ref)), 3)
        ln['caps'] = align_captions(ln['tokens'], ln['words'], ln['start'], ln['end'])               # script words on Whisper's clock (for captions)
        print(f'  heard [{ln["id"]}] wer {ln["wer"]:.2f}: {" ".join(w["w"] for w in ln["words"])}')


def report(m):
    w = sum(x['nwords'] for x in m); span = m[-1]['end'] - m[0]['start']; speech = sum(x['dur'] for x in m)
    print(f'voiceover: {w} words, speech {speech:.1f}s, span {span:.1f}s -> {w / speech * 60:.0f} wpm while speaking, {w / span * 60:.0f} wpm including pauses')


if __name__ == '__main__': main()
