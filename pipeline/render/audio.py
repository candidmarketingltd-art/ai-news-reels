"""Original sound design + final mix. Everything is synthesised, so nothing can be claimed or muted.

cues: dict from engine.render() -> open_lines, open_end, cuts, pops, duration
"""
import subprocess, wave
import numpy as np

SR = 44100


def _env(n, a=0.005, r=0.3):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / r)


def _lp(x, k):
    # one-pole low-pass, vectorised with an IIR via cumulative trick (good enough for noise shaping)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += k * (x[i] - acc); y[i] = acc
    return y


def build_sfx(cues, path, seed=1):
    rng = np.random.default_rng(seed)
    dur = cues["duration"] + 1.2
    N = int(dur * SR); out = np.zeros(N, np.float32)

    def add(sig, t, g):
        i = int(max(0, t) * SR); j = min(N, i + len(sig)); out[i:j] += sig[: j - i] * g

    def boom(d=2.0):
        t = np.arange(int(d * SR)) / SR
        return np.sin(2 * np.pi * np.cumsum(34 + 50 * np.exp(-t * 6)) / SR) * _env(len(t), 0.004, 0.7)

    noise_bank = _lp(rng.normal(0, 1, int(1.6 * SR)).astype(np.float32), 0.12)
    low_bank = _lp(noise_bank, 0.08)

    def whoosh(d=0.45):
        n = int(d * SR); x = noise_bank[:n] - _lp(noise_bank[:n], 0.01)
        return x * np.sin(np.linspace(0, np.pi, n)) ** 2 * 0.9

    def riser(d=1.4):
        n = int(d * SR); t = np.arange(n) / SR
        s = np.sin(2 * np.pi * np.cumsum(200 + 600 * (t / d) ** 2) / SR) * (t / d) ** 3 * 0.25
        return low_bank[:n] * (t / d) ** 2 * 0.8 + s

    def pop(f):
        t = np.arange(int(0.12 * SR)) / SR
        return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t)) * _env(len(t), 0.002, 0.04)

    def thud():
        t = np.arange(int(0.5 * SR)) / SR
        return np.sin(2 * np.pi * (60 + 80 * np.exp(-t * 20)) * t) * _env(len(t), 0.002, 0.15)

    t = np.arange(N) / SR
    pad = np.zeros(N, np.float32)
    for f, g in ((55, .5), (110, .35), (164.8, .22), (220, .15), (261.6, .1)):
        pad += g * np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 0.07 * t * f / 55))
    pad *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t) ** 2
    oe = cues.get("open_end", 0)
    pad *= np.clip((t - max(0, oe - 0.7)) / 1.5, 0, 1) * np.clip((cues["duration"] + 0.8 - t) / 1.0, 0, 1)
    if not cues.get("music"):
        out += pad * 0.05  # only when no theme music is used

    for k, ot in enumerate(cues.get("open_lines", [])):
        add(boom(2.0 if k == 0 else 1.6), ot - 0.06, [0.9, 0.5, 0.65][min(k, 2)])
    if oe > 1.5:
        add(riser(), oe - 1.3, 0.35)
    add(thud(), oe, 0.8)
    for c in cues.get("cuts", []):
        add(whoosh(), c - 0.2, 0.28)
    tones = [880, 990, 1180, 1320, 660]
    for k, p in enumerate(cues.get("pops", [])):
        add(pop(tones[k % len(tones)]), p, 0.16)

    out /= max(1e-6, np.abs(out).max()) / 0.5
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32767).astype(np.int16).tobytes())


MUSIC_DIR = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "music")


def theme_path():
    import os
    for n in ("theme_loop.wav", "theme_loop.mp3"):
        p = os.path.join(MUSIC_DIR, n)
        if os.path.exists(p): return p
    return None


def mix(video, voice, sfx, out, workdir, music_start=0.0, music_gain=0.30, duck_sfx=True, sfx_gain=0.9):
    """Voice on top; signature theme (+ sound design when duck_sfx) underneath, ducked whenever Rohan speaks.
    duck_sfx=False keeps UI hits at full level over the voice (Hisaab style)."""
    vo = f"{workdir}/vo_proc.wav"; mixed = f"{workdir}/mix.wav"
    run = lambda *a: subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)
    run("-i", voice, "-af", "aresample=48000,highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,loudnorm=I=-15:TP=-1.5:LRA=9", "-ar", "48000", vo)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video], capture_output=True, text=True, check=True).stdout.strip())
    theme = theme_path()
    ins = ["-i", vo, "-i", sfx]
    fx = f"[1:a]aresample=48000,volume={sfx_gain}[fx];"
    if theme:
        ms = max(0.0, music_start - 0.4)
        ins += ["-stream_loop", "-1", "-i", theme]
        mus = (f"[2:a]aresample=48000,atrim=0:{dur - ms:.2f},afade=t=in:d=0.8,afade=t=out:st={max(0, dur - ms - 1.8):.2f}:d=1.8,"
               f"volume={music_gain},adelay={int(ms * 1000)}:all=1[mus];")
        bed = mus + fx + ("[mus][fx]amix=inputs=2:duration=longest:normalize=0[bed];" if duck_sfx else "[mus]anull[bed];")
    else:
        bed = fx + ("[fx]anull[bed];" if duck_sfx else "anullsrc=r=48000:cl=mono,atrim=0:1[bed];")
    tail = ("[vo][duck]amix=inputs=2:duration=longest:normalize=0" if duck_sfx else "[vo][duck][fx]amix=inputs=3:duration=longest:normalize=0")
    if not duck_sfx:
        bed = bed.replace(fx, "") ; bed = fx + bed
    run(*ins, "-filter_complex",
        bed + f"[0:a]apad=whole_dur={dur:.3f},asplit=2[vo][sc];"
        "[bed][sc]sidechaincompress=threshold=0.03:ratio=10:attack=8:release=300[duck];"
        + tail + ",alimiter=limit=0.95", "-t", f"{dur:.3f}", mixed)
    run("-i", video, "-i", mixed, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", "-movflags", "+faststart", out)


# ---------------------------------------------------------------- UI sound design for the Remotion ("Hisaab") style
def build_ui_sfx(hits, duration, path, seed=5):
    """A crisp sound on every visual event: pop (element in), tick (counters/strikes), thud (reveals),
    ding (payoff), whoosh (scene change). `hits` = [(seconds, kind)]."""
    sr = 48000
    n_total = int(duration * sr); out = np.zeros(n_total, np.float32)
    rng = np.random.default_rng(seed)

    def env(n, a, r):
        t = np.arange(n) / sr
        return np.minimum(1, t / a) * np.exp(-t / r)

    def pop():
        n = int(0.07 * sr); t = np.arange(n) / sr
        return np.sin(2 * np.pi * np.cumsum(900 + 600 * np.exp(-t * 60)) / sr) * env(n, 0.002, 0.018)

    def tick():
        n = int(0.02 * sr); t = np.arange(n) / sr
        return (np.sin(2 * np.pi * 2600 * t) * 0.6 + rng.normal(0, 0.4, n)) * env(n, 0.0005, 0.004)

    def thud():
        n = int(0.35 * sr); t = np.arange(n) / sr
        return np.sin(2 * np.pi * (60 + 90 * np.exp(-t * 25)) * t) * env(n, 0.002, 0.12) + rng.normal(0, 1, n) * env(n, 0.0005, 0.006) * 0.3

    def ding():
        n = int(0.6 * sr); t = np.arange(n) / sr
        return (np.sin(2 * np.pi * 1568 * t) + 0.5 * np.sin(2 * np.pi * 2349 * t)) * env(n, 0.002, 0.16) * 0.6

    def whoosh():
        n = int(0.4 * sr); x = rng.normal(0, 1, n).astype(np.float32)
        k = np.exp(-np.linspace(3, 0.2, n)); y = np.empty_like(x); acc = 0.0
        for i in range(n):
            acc += k[i] * 0.25 * (x[i] - acc); y[i] = acc
        return y * np.sin(np.linspace(0, np.pi, n)) ** 2 * 1.6

    def impact():   # cinematic hit for the very first frame: sub drop + noise burst + short tail
        n = int(0.9 * sr); t = np.arange(n) / sr
        sub = np.sin(2 * np.pi * (45 + 120 * np.exp(-t * 18)) * t) * env(n, 0.001, 0.35)
        hiss = rng.normal(0, 1, n) * env(n, 0.0005, 0.05) * 0.5
        return sub + hiss

    def swish():    # short airy swipe for keep-alive beats
        n = int(0.22 * sr); x = rng.normal(0, 1, n).astype(np.float32)
        hp = np.diff(np.concatenate([[0], x]))
        return hp * np.sin(np.linspace(0, np.pi, n)) ** 3 * 0.9

    def sweep(f0, f1, dur, harm=True):   # tonal glide (zap / riser / drop)
        n = int(dur * sr); t = np.arange(n) / sr
        f = f0 * (f1 / f0) ** (t / dur); ph = 2 * np.pi * np.cumsum(f) / sr
        y = np.sin(ph) + (0.35 * np.sin(2 * ph) if harm else 0)
        return y * np.sin(np.linspace(0, np.pi, n)) ** 1.5

    def click():    # mouse click: two tiny transients
        n = int(0.06 * sr); y = np.zeros(n); t = np.arange(int(0.012 * sr)) / sr
        k = (np.sin(2 * np.pi * 3200 * t) + rng.normal(0, 0.6, len(t))) * np.exp(-t / 0.0018)
        y[:len(k)] += k; y[int(0.028 * sr):int(0.028 * sr) + len(k)] += k * 0.55
        return y

    def key():      # keyboard key (randomised pitch per hit at build time)
        n = int(0.035 * sr); t = np.arange(n) / sr
        return (np.sin(2 * np.pi * 1900 * t) * 0.4 + rng.normal(0, 0.7, n)) * np.exp(-t / 0.006)

    def blip():     # soft UI blip for highlighted words
        n = int(0.09 * sr); t = np.arange(n) / sr
        return np.sin(2 * np.pi * 1320 * t) * env(n, 0.003, 0.03) + np.sin(2 * np.pi * 1980 * t) * env(n, 0.003, 0.02) * 0.4

    def glitch():   # digital stutter for screen changes
        n = int(0.14 * sr); y = rng.normal(0, 1, n)
        hold = np.repeat(y[::90], 90)[:n]; gate = (np.floor(np.arange(n) / (0.018 * sr)) % 2)
        return hold * gate * np.exp(-np.arange(n) / (0.07 * sr)) * 0.8

    def chime():    # bright two-note bell for idents and big payoffs
        n = int(0.9 * sr); t = np.arange(n) / sr
        a = np.sin(2 * np.pi * 1760 * t) * env(n, 0.002, 0.25); b = np.sin(2 * np.pi * 2637 * t) * env(n, 0.002, 0.2)
        b[: int(0.09 * sr)] = 0
        return (a + 0.8 * b) * 0.55

    def whoomp():   # low swoosh for scene cuts
        n = int(0.32 * sr); x = rng.normal(0, 1, n); acc = 0.0; y = np.empty(n)
        for i in range(n):
            acc += 0.02 * (x[i] - acc); y[i] = acc
        return (y / (np.abs(y).max() + 1e-9)) * np.sin(np.linspace(0, np.pi, n)) ** 2 + sweep(160, 70, 0.32, False) * 0.5

    def flash():    # bright hit for white-flash cuts
        n = int(0.25 * sr); t = np.arange(n) / sr
        return rng.normal(0, 1, n) * env(n, 0.0005, 0.03) * 0.7 + np.sin(2 * np.pi * (90 + 200 * np.exp(-t * 30)) * t) * env(n, 0.001, 0.08)

    def toggle():
        return np.concatenate([click()[: int(0.02 * sr)], blip() * 0.8])

    def rattle():   # object shake
        n = int(0.35 * sr); y = np.zeros(n)
        for k in range(7):
            i = int(k * 0.045 * sr); m = key() * (1 - k / 8)
            y[i:i + len(m)] += m[: max(0, min(len(m), n - i))]
        return y

    bank = {"impact": (impact(), 0.75),
            "riser": (sweep(250, 1400, 0.5) * 0.6 + rng.normal(0, 1, int(0.5 * sr)) * np.linspace(0, 0.25, int(0.5 * sr)), 0.18),
            "zap": (sweep(500, 2600, 0.22), 0.16), "drop": (sweep(900, 140, 0.3), 0.18),
            "click": (click(), 0.35), "key": (key(), 0.13), "blip": (blip(), 0.07), "glitch": (glitch(), 0.16),
            "chime": (chime(), 0.22), "whoomp": (whoomp(), 0.3), "flash": (flash(), 0.4), "toggle": (toggle(), 0.22), "rattle": (rattle(), 0.25), "swish": (swish(), 0.16), "pop": (pop(), 0.22), "tick": (tick(), 0.10), "thud": (thud(), 0.5), "ding": (ding(), 0.20), "whoosh": (whoosh(), 0.25)}
    for t, kind in hits:
        if kind not in bank: continue
        sig, g = bank[kind]
        if kind in ("key", "click", "blip"):   # small random variation so repeated hits don't sound robotic
            r = rng.uniform(0.85, 1.18); idx = np.clip((np.arange(int(len(sig) / r)) * r).astype(int), 0, len(sig) - 1)
            sig = sig[idx]; g = g * rng.uniform(0.75, 1.1)
        i = int(max(0, t) * sr); j = min(n_total, i + len(sig))
        if j > i: out[i:j] += sig[: j - i] * g
    out /= max(1e-6, np.abs(out).max()) / 0.6
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((out * 32767).astype(np.int16).tobytes())
