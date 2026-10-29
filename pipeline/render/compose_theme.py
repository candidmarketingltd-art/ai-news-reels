"""Compose the AI-news signature theme (original, synthesised — owned outright, never claimable).

112 BPM, D minor, "tech pulse": a filtered saw arpeggio, sub bass on the beat, soft kick + hats, an airy pad.
Written to be talked over: nothing busy in the voice's 1–3 kHz pocket.
Output: music/theme_loop.wav — an 8-bar seamless loop. The mixer loops it under every reel.

python -m pipeline.render.compose_theme
To use a different track instead (e.g. one made in ElevenLabs Music), drop it at music/theme_loop.wav (or .mp3).
"""
import os, wave
import numpy as np

SR = 44100; BPM = 112; BEAT = 60 / BPM; BAR = 4 * BEAT; BARS = 8
N = int(BARS * BAR * SR)
rng = np.random.default_rng(7)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music", "theme_loop.wav")


def hz(midi): return 440.0 * 2 ** ((midi - 69) / 12)


def place(buf, sig, t):
    i = int(t * SR) % N; end = i + len(sig)
    if end <= N: buf[i:end] += sig
    else: k = N - i; buf[i:] += sig[:k]; buf[:end - N] += sig[k:]


def env(n, a=0.005, r=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / r)


def lowpass(x, k):
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += k * (x[i] - acc); y[i] = acc
    return y


def saw(f, d):
    t = np.arange(int(d * SR)) / SR
    return 2 * ((t * f) % 1.0) - 1


def main():
    mus = np.zeros(N, np.float32)
    # chords (root midi): Dm - Bb - F - C, two bars each
    roots = [50, 46, 41, 48]
    triads = {50: (0, 3, 7), 46: (0, 4, 7), 41: (0, 4, 7), 48: (0, 4, 7)}
    for bar in range(BARS):
        r = roots[(bar // 2) % 4]; tri = triads[r]; t0 = bar * BAR
        # pad
        pad = sum(np.sin(2 * np.pi * hz(r + 12 + iv) * np.arange(int(BAR * SR)) / SR) for iv in tri) / 3
        place(mus, (pad * np.sin(np.linspace(0, np.pi, len(pad))) ** 0.5 * 0.10).astype(np.float32), t0)
        # arpeggio 16ths, filtered saw
        pattern = [0, 1, 2, 1, 2, 0, 2, 1] * 2
        for k, p in enumerate(pattern):
            note = r + 24 + tri[p] + (12 if k % 8 == 7 else 0)
            s = saw(hz(note), BEAT / 4 * 0.9)
            s = lowpass(s.astype(np.float32), 0.10 + 0.05 * np.sin(bar)) * env(len(s), 0.003, 0.09)
            place(mus, (s * 0.10).astype(np.float32), t0 + k * BEAT / 4)
        # sub bass + kick + hats
        for b in range(4):
            tb = t0 + b * BEAT
            n = int(BEAT * 0.9 * SR); tt = np.arange(n) / SR
            place(mus, (np.sin(2 * np.pi * hz(r - 12) * tt) * env(n, 0.01, 0.35) * 0.22).astype(np.float32), tb)
            nk = int(0.35 * SR); tk = np.arange(nk) / SR
            kick = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-tk * 30)) / SR) * env(nk, 0.001, 0.12)
            place(mus, (kick * 0.35).astype(np.float32), tb)
            for h in (0.5,):
                nh = int(0.05 * SR); hat = rng.normal(0, 1, nh); hat = hat - lowpass(hat.astype(np.float32), 0.3)
                place(mus, (hat * env(nh, 0.001, 0.015) * 0.06).astype(np.float32), tb + h * BEAT)
    mus /= np.abs(mus).max() / 0.8
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    st = np.stack([mus, np.roll(mus, int(0.012 * SR))], -1)  # tiny Haas widening
    with wave.open(OUT, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())
    print("wrote", OUT, f"{N / SR:.1f}s")


if __name__ == "__main__":
    main()
