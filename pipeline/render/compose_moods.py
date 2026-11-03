"""Mood music library: original, synthesised loops (owned outright — never claimed), one per kind of story.
The editor picks a mood per reel (`music`); the mixer loops it under the voice and ducks it whenever Rohan speaks.

  suspense  — 96 BPM minor: ticking hats, staccato pizzicato bass walk, low drone, stabs (scams, hacks, privacy, heists)
  upbeat    — 118 BPM major: bright pluck arpeggio, claps, bouncy bass (productivity wins, tools, shortcuts)
  groove    — 100 BPM minor-7th: funky muted bass, snaps, soft keys (money, careers, business)
  warning   — 84 BPM: heartbeat kick, dark drone, high bell (mistakes, "stop doing this", risks)
  chill     — 82 BPM: warm keys, soft kick, vinyl crackle (explainers, calm how-tos)

python -m pipeline.render.compose_moods   -> pipeline/render/music/<mood>.mp3
"""
import os, subprocess, wave
import numpy as np

SR = 44100
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")
MOODS = ("suspense", "upbeat", "groove", "warning", "chill")


def hz(m): return 440.0 * 2 ** ((m - 69) / 12)


def env(n, a=0.004, r=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / r)


def lp(x, cutoff):
    """one-pole low-pass via exponential smoothing in blocks (vectorised enough for a few seconds of audio)"""
    k = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x); acc = 0.0
    for i in range(0, len(x), 4096):
        seg = x[i:i + 4096]; out = np.empty_like(seg)
        for j, v in enumerate(seg):
            acc += k * (v - acc); out[j] = acc
        y[i:i + 4096] = out
    return y


class Song:
    def __init__(self, bpm, bars, seed):
        self.beat = 60 / bpm; self.bar = 4 * self.beat; self.n = int(bars * self.bar * SR)
        self.buf = np.zeros(self.n); self.rng = np.random.default_rng(seed)

    def put(self, sig, t, g=1.0):
        i = int(t * SR) % self.n; e = i + len(sig)
        if e <= self.n: self.buf[i:e] += sig * g
        else: k = self.n - i; self.buf[i:] += sig[:k] * g; self.buf[:e - self.n] += sig[k:] * g

    # instruments
    def kick(self, soft=False):
        n = int(0.32 * SR); t = np.arange(n) / SR
        return np.sin(2 * np.pi * (48 + 110 * np.exp(-t * 32)) * t) * env(n, 0.001, 0.14 if soft else 0.2)

    def hat(self, open_=False):
        n = int((0.12 if open_ else 0.035) * SR); x = self.rng.normal(0, 1, n)
        return (x - lp(x, 6000)) * env(n, 0.0005, 0.05 if open_ else 0.01)

    def clap(self):
        n = int(0.18 * SR); x = self.rng.normal(0, 1, n)
        e = sum(env(n, 0.0005, 0.012) * (np.arange(n) >= int(d * SR)) for d in (0, 0.011, 0.022))
        return (x - lp(x, 900)) * (e + env(n, 0.001, 0.07) * 0.6) * 0.6

    def pluck(self, f, d=0.25, bright=4000):
        n = int(d * SR); t = np.arange(n) / SR
        x = 2 * ((t * f) % 1) - 1
        return lp(x, bright) * env(n, 0.002, d * 0.35)

    def pizz(self, f):
        n = int(0.22 * SR); t = np.arange(n) / SR
        return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t)) * env(n, 0.002, 0.06)

    def bass(self, f, d, sub=True):
        n = int(d * SR); t = np.arange(n) / SR
        x = np.sin(2 * np.pi * f * t) + (0.3 * np.sign(np.sin(2 * np.pi * f * t)) if not sub else 0)
        return lp(x, 400) * env(n, 0.005, d * 0.6)

    def pad(self, fs, d, bright=1200):
        n = int(d * SR); t = np.arange(n) / SR
        x = sum(sum(np.sin(2 * np.pi * f * (1 + det) * t + self.rng.uniform(0, 6)) for det in (-0.004, 0, 0.005)) for f in fs) / (3 * len(fs))
        a = np.minimum(1, t / (d * 0.3)) * np.minimum(1, (d - t) / (d * 0.3))
        return lp(x, bright) * a

    def keys(self, fs, d):
        n = int(d * SR); t = np.arange(n) / SR
        x = sum(np.sin(2 * np.pi * f * t) * (1 + 0.25 * np.sin(2 * np.pi * 5 * t)) + 0.3 * np.sin(4 * np.pi * f * t) * np.exp(-t * 6) for f in fs) / len(fs)
        return x * env(n, 0.004, d * 0.5)

    def bell(self, f, d=1.2):
        n = int(d * SR); t = np.arange(n) / SR
        return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 4)) * env(n, 0.002, d * 0.4)


def suspense():
    s = Song(96, 8, 1); b, B = s.beat, s.bar
    walk = [38, 38, 41, 40, 38, 38, 43, 41]                      # D minor sneaky walk
    for bar in range(8):
        for i in range(8):                                        # staccato pizzicato bass on 8ths
            m = walk[(bar + (i // 2)) % 8] + (12 if i % 4 == 3 else 0)
            s.put(s.pizz(hz(m)), bar * B + i * b / 2, 0.55 if i % 2 == 0 else 0.35)
        for i in range(16): s.put(s.hat(), bar * B + i * b / 4, 0.18 if i % 4 else 0.3)   # ticking clock
        s.put(s.kick(True), bar * B, 0.7); s.put(s.kick(True), bar * B + 2.5 * b, 0.5)
        if bar % 2 == 1: s.put(s.pluck(hz(74), 0.18, 2500), bar * B + 3.5 * b, 0.35); s.put(s.pluck(hz(73), 0.18, 2500), bar * B + 3.75 * b, 0.3)
    s.put(s.pad([hz(38), hz(45)], 8 * B, 500), 0, 0.35)
    return s.buf


def upbeat():
    s = Song(118, 8, 2); b, B = s.beat, s.bar
    prog = [[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 67]]   # Cmaj7 Am7 Fmaj7 G
    for bar in range(8):
        ch = prog[bar % 4]
        for i in range(16):
            s.put(s.pluck(hz(ch[[0, 1, 2, 3, 2, 1, 3, 2][i % 8]] + 12), 0.2, 5000), bar * B + i * b / 4, 0.28)
        for i in range(4): s.put(s.kick(), bar * B + i * b, 0.8)
        for i in (1, 3): s.put(s.clap(), bar * B + i * b, 0.55)
        for i in range(8): s.put(s.hat(i % 2 == 1), bar * B + i * b / 2, 0.2)
        for i, off in enumerate((0, 0.75, 1.5, 2.5, 3)): s.put(s.bass(hz(ch[0] - 24), 0.3), bar * B + off * b, 0.6)
    return s.buf


def groove():
    s = Song(100, 8, 3); b, B = s.beat, s.bar
    prog = [[50, 53, 57, 60], [55, 58, 62, 65], [48, 52, 55, 58], [53, 57, 60, 64]]   # Dm7 Gm7 C7 Fmaj7
    for bar in range(8):
        ch = prog[bar % 4]
        s.put(s.keys([hz(m + 12) for m in ch], 1.6 * b), bar * B + 0.5 * b, 0.32); s.put(s.keys([hz(m + 12) for m in ch], 1.2 * b), bar * B + 2.75 * b, 0.25)
        for off, oct_ in ((0, 0), (0.75, 12), (1.5, 0), (2, 7), (2.75, 12), (3.5, 0)): s.put(s.bass(hz(ch[0] - 24 + oct_), 0.22, False), bar * B + off * b, 0.5)
        s.put(s.kick(), bar * B, 0.8); s.put(s.kick(), bar * B + 2.25 * b, 0.6)
        for i in (1, 3): s.put(s.clap(), bar * B + i * b, 0.4)
        for i in range(16): s.put(s.hat(), bar * B + i * b / 4, 0.12 + 0.08 * (i % 2))
    return s.buf


def warning():
    s = Song(84, 8, 4); b, B = s.beat, s.bar
    for bar in range(8):
        s.put(s.kick(True), bar * B, 0.9); s.put(s.kick(True), bar * B + 0.35 * b, 0.6)        # heartbeat
        s.put(s.kick(True), bar * B + 2 * b, 0.9); s.put(s.kick(True), bar * B + 2.35 * b, 0.6)
        if bar % 2 == 0: s.put(s.bell(hz(86) if bar % 4 == 0 else hz(85), 1.6), bar * B + 1 * b, 0.12)
        for i in range(8): s.put(s.hat(), bar * B + i * b / 2, 0.08)
    s.put(s.pad([hz(37), hz(44), hz(49)], 8 * B, 380), 0, 0.5)
    return s.buf


def chill():
    s = Song(82, 8, 5); b, B = s.beat, s.bar
    prog = [[57, 60, 64, 67], [53, 57, 60, 64], [48, 52, 55, 59], [55, 59, 62, 65]]   # Am7 Fmaj7 Cmaj7 G7
    for bar in range(8):
        ch = prog[bar % 4]
        s.put(s.keys([hz(m) for m in ch], 3.6 * b), bar * B, 0.3)
        s.put(s.kick(True), bar * B, 0.55); s.put(s.kick(True), bar * B + 2.5 * b, 0.4)
        for i in (1, 3): s.put(s.clap() * 0.5, bar * B + i * b, 0.35)
        for i in range(8): s.put(s.hat(), bar * B + i * b / 2 + (0.03 if i % 2 else 0), 0.1)
        s.put(s.bass(hz(ch[0] - 24), 1.5 * b), bar * B, 0.45); s.put(s.bass(hz(ch[0] - 24 + 7), 1.0 * b), bar * B + 2 * b, 0.35)
    crackle = (s.rng.random(s.n) > 0.9993) * s.rng.normal(0, 0.6, s.n)
    s.buf += lp(crackle, 3000) * 0.4
    return s.buf


def write(name, x):
    x = x / (np.abs(x).max() + 1e-9) * 0.8
    os.makedirs(DIR, exist_ok=True)
    wav = os.path.join(DIR, f"{name}.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype(np.int16).tobytes())
    mp3 = wav[:-4] + ".mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-b:a", "128k", mp3], check=True)
    os.remove(wav)
    return mp3


if __name__ == "__main__":
    for m in MOODS:
        print(write(m, globals()[m]()))
