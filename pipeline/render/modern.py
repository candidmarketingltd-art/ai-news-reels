"""Modern AI-news look (RENDER_STYLE=modern, the default).

Deep navy canvas with slow-moving colour blobs and a dot grid, a thin progress bar, a glass "LIVE · AI NEWS" pill,
a big left-aligned hook with a gradient accent word, one frosted-glass panel for the cards (cards slide/fade in,
numbers glow), Rohan in a rounded "host cam" bottom-left whose ring lights up while he talks, and TikTok-style
captions with the spoken word on an accent highlight. Inter / Space Grotesk / JetBrains Mono.
Everything important stays out of Instagram's UI zones (right-side buttons, bottom caption area).
"""
import functools, math, os, re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from engine import Reel, mascot, MOOD_REST, PARTICLES, FPS, WIDTH, HEIGHT, HANDLE, CURRENCY, _norm  # noqa: F401

FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# ------------------------------------------------------------------ palette
BG = (8, 10, 20)
WHITE = (246, 248, 252); SOFT = (203, 210, 225); MUTED = (128, 140, 165); DIM = (70, 80, 102)
AMBER = (251, 191, 36); BLUE = (96, 165, 250); GREEN = (52, 211, 153); RED = (248, 113, 113)
ICE = (165, 243, 252); VIOLET = (167, 139, 250); CYAN = (34, 211, 238); PINK = (244, 114, 182)
COLORS = {"gold": AMBER, "white": WHITE, "red": RED, "green": GREEN, "blue": BLUE, "muted": MUTED, "ice": ICE}
# tint -> (accent, accent2) for gradients / glows
TINTS = {"warm": (VIOLET, PINK), "cold": (CYAN, BLUE), "red": (RED, (251, 146, 60)), "green": (GREEN, CYAN)}

# ------------------------------------------------------------------ layout (1080x1920; IG UI keeps right ~110px of the
# lower half and the bottom ~330px busy, so nothing important lives there)
M = 64
TOP = 150                                  # header row (below Instagram's own top bar)
PANEL = (M, 560, WIDTH - M, 1300)
CAM = (M, 1330, M + 290, 1620)
CAP = (CAM[2] + 34, 1330, WIDTH - 120, 1620)


@functools.lru_cache(None)
def F(kind, size):
    name = {"black": "Inter-Black.ttf", "xbold": "Inter-ExtraBold.ttf", "bold": "Inter-Bold.ttf", "med": "Inter-Medium.ttf",
            "num": "SpaceGrotesk-Bold.ttf", "mono": "JetBrainsMono-Bold.ttf", "monom": "JetBrainsMono-Medium.ttf"}[kind]
    return ImageFont.truetype(os.path.join(FD, name), max(8, int(size)), layout_engine=ImageFont.Layout.RAQM)


def col(c, default=WHITE):
    if isinstance(c, (list, tuple)): return tuple(c)
    return COLORS.get(c or "", default)


def clamp(x): return max(0.0, min(1.0, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def ease_io(x): x = clamp(x); return 3 * x * x - 2 * x * x * x
def spring(x):
    x = clamp(x); return 1 - math.exp(-6 * x) * math.cos(9 * x)


def fit(d, s, kind, size, maxw, minsize=20):
    f = F(kind, size); w = d.textlength(s, font=f)
    if w > maxw: f = F(kind, max(minsize, size * maxw / w))
    return f


def wrap(d, s, font, maxw, max_lines=4):
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]; lines[-1] = lines[-1].rstrip(".,") + "…"
    return lines


# ------------------------------------------------------------------ drawing primitives
def gradient(w, h, c1, c2, angle=0.0):
    """RGB gradient image, c1 -> c2 along `angle` (radians, 0 = left->right)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    t = (x * math.cos(angle) + y * math.sin(angle))
    t = (t - t.min()) / max(1e-6, t.max() - t.min())
    a = np.array(c1, np.float32); b = np.array(c2, np.float32)
    return Image.fromarray((a + (b - a) * t[..., None]).astype(np.uint8), "RGB")


def text_layer(s, font, fill=WHITE):
    """Tight RGBA image of a string (for gradients/glows/transforms)."""
    l, t, r, b = font.getbbox(s)
    im = Image.new("RGBA", (max(1, r - l + 8), max(1, b - t + 8)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - l, 4 - t), s, font=font, fill=fill)
    return im


def lighten(c, k=0.35): return tuple(int(v + (255 - v) * k) for v in c)


def grad_text(s, font, c1, c2):
    c1, c2 = lighten(c1, 0.15), lighten(c2, 0.15)
    m = text_layer(s, font, (255, 255, 255, 255))
    g = gradient(m.width, m.height, c1, c2, 0.35).convert("RGBA")
    g.putalpha(m.getchannel("A"))
    return g


def paste(img, layer, xy, anchor="mm", alpha=1.0, dy=0.0, scale=1.0, glow=None, glow_r=22):
    """Composite `layer` at xy with anchor (l/m/r + t/m/b), fade, vertical offset, scale and optional glow."""
    if alpha <= 0.01: return
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.BICUBIC)
    w, h = layer.size
    x = {"l": xy[0], "m": xy[0] - w / 2, "r": xy[0] - w}[anchor[0]]
    y = {"t": xy[1], "m": xy[1] - h / 2, "b": xy[1] - h}[anchor[1]] + dy
    if glow:
        pad = glow_r * 3
        g = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        mask = layer.getchannel("A").point(lambda v: int(v * 0.85))
        g.paste(Image.new("RGBA", (w, h), glow + (255,)), (pad, pad), mask)
        g = g.filter(ImageFilter.GaussianBlur(glow_r))
        if alpha < 1: g.putalpha(g.getchannel("A").point(lambda v: int(v * alpha)))
        img.alpha_composite(g, (int(x - pad), int(y - pad)))
    if alpha < 1:
        layer = layer.copy(); layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(layer, (int(x), int(y)))


def rise(img, xy, s, font, fill, t0, t, anchor="mm", dur=0.4, dist=34, glow=None, maxw=None):
    """Text that slides up + fades in from t0."""
    if t0 is None or t < t0 or not s: return
    p = ease((t - t0) / dur)
    lay = text_layer(s, font, fill + (255,) if len(fill) == 3 else fill)
    if maxw and lay.width > maxw: lay = lay.resize((int(maxw), int(lay.height * maxw / lay.width)), Image.BICUBIC)
    paste(img, lay, xy, anchor, alpha=p, dy=(1 - p) * dist, glow=glow)


def pill(img, xy, s, font, fg, bg, t0=None, t=None, anchor="mm", pad=(30, 16), border=None, dot=None, radius=None):
    if t0 is not None and (t is None or t < t0 or not s): return
    p = 1.0 if t0 is None else ease((t - t0) / 0.35)
    d0 = ImageDraw.Draw(img)
    tw = d0.textlength(s, font=font); l, tp, r, b = font.getbbox("Hg")
    th = b - tp
    extra = (th * 0.55 + 14) if dot else 0
    w = tw + 2 * pad[0] + extra; h = th + 2 * pad[1]
    lay = Image.new("RGBA", (int(w) + 4, int(h) + 4), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle((1, 1, w + 1, h + 1), radius or int(h / 2), fill=bg, outline=border, width=2 if border else 0)
    x = pad[0] + 1
    if dot:
        r_ = th * 0.28; cy = h / 2 + 1
        d.ellipse((x, cy - r_, x + 2 * r_, cy + r_), fill=dot); x += extra
    d.text((x, h / 2 + 1), s, font=font, fill=fg, anchor="lm")
    paste(img, lay, xy, anchor, alpha=p, dy=(1 - p) * 18)
    return w


# ------------------------------------------------------------------ icons (flat, no outlines)
def icon(img, name, cx, cy, s, acc, t):
    lay = Image.new("RGBA", (int(420 * s), int(420 * s)), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    c = lay.width / 2; k = s
    if name == "chip":
        w = 120 * k
        for i in range(4):
            o = -w * 0.75 + i * w * 0.5
            for (a, b_) in ((c + o, c - w - 34 * k), (c + o, c + w + 6 * k)):
                d.rounded_rectangle((a - 9 * k, b_, a + 9 * k, b_ + 28 * k), 5, fill=acc + (200,))
            for (a, b_) in ((c - w - 34 * k, c + o), (c + w + 6 * k, c + o)):
                d.rounded_rectangle((a, b_ - 9 * k, a + 28 * k, b_ + 9 * k), 5, fill=acc + (200,))
        d.rounded_rectangle((c - w, c - w, c + w, c + w), int(34 * k), fill=(24, 28, 46, 255), outline=acc + (255,), width=int(5 * k))
        d.text((c, c), "AI", font=F("num", 96 * k), fill=acc + (255,), anchor="mm")
    elif name == "robot":
        d.line((c, c - 150 * k, c, c - 110 * k), fill=SOFT + (255,), width=int(8 * k))
        d.ellipse((c - 16 * k, c - 172 * k, c + 16 * k, c - 140 * k), fill=acc + (255,))
        d.rounded_rectangle((c - 140 * k, c - 110 * k, c + 140 * k, c + 120 * k), int(56 * k), fill=(232, 236, 245, 255))
        d.rounded_rectangle((c - 108 * k, c - 70 * k, c + 108 * k, c + 60 * k), int(40 * k), fill=(20, 24, 40, 255))
        blink = 0.15 if (t % 3.1) < 0.12 else 1
        for ex in (-48, 48):
            d.rounded_rectangle((c + (ex - 18) * k, c - (24 * blink + 4) * k, c + (ex + 18) * k, c + (24 * blink - 4) * k), int(14 * k), fill=acc + (255,))
    elif name == "globe":
        r = 140 * k
        d.ellipse((c - r, c - r, c + r, c + r), fill=(30, 58, 110, 255), outline=acc + (255,), width=int(5 * k))
        for kk in (0.38, 0.75):
            d.ellipse((c - r * kk, c - r, c + r * kk, c + r), outline=acc + (150,), width=int(4 * k))
        for yy in (-0.5, 0, 0.5):
            hw = r * math.sqrt(1 - yy * yy); d.line((c - hw, c + yy * r, c + hw, c + yy * r), fill=acc + (150,), width=int(4 * k))
    elif name == "phone":
        d.rounded_rectangle((c - 92 * k, c - 170 * k, c + 92 * k, c + 170 * k), int(34 * k), fill=(24, 28, 46, 255), outline=SOFT + (180,), width=int(4 * k))
        d.rounded_rectangle((c - 26 * k, c - 154 * k, c + 26 * k, c - 140 * k), 7, fill=SOFT + (120,))
        for i in range(3):
            y0 = c - 100 * k + i * 70 * k
            d.rounded_rectangle((c - 66 * k, y0, c + (52 - i * 22) * k, y0 + 44 * k), int(16 * k), fill=(acc if i != 1 else SOFT) + (255,))
    elif name in ("coin",):
        d.ellipse((c - 120 * k, c - 120 * k, c + 120 * k, c + 120 * k), fill=AMBER + (255,))
        d.ellipse((c - 96 * k, c - 96 * k, c + 96 * k, c + 96 * k), outline=(180, 120, 10, 255), width=int(5 * k))
        d.text((c, c), CURRENCY[:1], font=F("num", 130 * k), fill=(90, 60, 5, 255), anchor="mm")
    elif name in ("plane", "share"):
        pts = [(c - 130 * k, c + 10 * k), (c + 130 * k, c - 110 * k), (c + 40 * k, c + 120 * k), (c - 10 * k, c + 40 * k)]
        d.polygon(pts, fill=acc + (255,))
        d.line((c - 10 * k, c + 40 * k, c + 130 * k, c - 110 * k), fill=BG + (255,), width=int(7 * k))
    else:
        return
    a = ease((t) / 0.5) if t is not None else 1
    paste(img, lay, (cx, cy), "mm", alpha=a, dy=(1 - a) * 40, glow=acc, glow_r=28)


# ------------------------------------------------------------------ backgrounds (precomputed)
def _base():
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    v = np.clip(1 - np.sqrt(((x - 540) / 1100) ** 2 + ((y - 760) / 1300) ** 2), 0, 1)
    rgb = np.stack([BG[0] + 10 * v, BG[1] + 12 * v, BG[2] + 22 * v], -1)
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    for gy in range(40, HEIGHT, 48):           # dot grid
        for gx in range(28, WIDTH, 48):
            d.ellipse((gx - 1.6, gy - 1.6, gx + 1.6, gy + 1.6), fill=(255, 255, 255, 16))
    return img


BASE = _base()


@functools.lru_cache(None)
def blob(color, r):
    im = Image.new("RGBA", (r * 4, r * 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((r, r, 3 * r, 3 * r), fill=color + (120,))
    return im.filter(ImageFilter.GaussianBlur(r * 0.55))


_rng = np.random.default_rng(5)
GRAIN = [Image.fromarray(_rng.normal(128, 18, (HEIGHT // 2, WIDTH // 2)).clip(0, 255).astype(np.uint8)).resize((WIDTH, HEIGHT)) for _ in range(4)]


@functools.lru_cache(None)
def panel_shell(accent):
    """Frosted-glass panel: translucent fill, light border, top sheen, soft coloured shadow."""
    x0, y0, x1, y1 = PANEL
    w, h = x1 - x0, y1 - y0; pad = 80
    lay = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad + 30, pad + 50, pad + w - 30, pad + h + 10), 56, fill=accent + (60,))
    lay.alpha_composite(sh.filter(ImageFilter.GaussianBlur(46)))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((pad, pad, pad + w, pad + h), 52, fill=(22, 26, 44, 205), outline=(255, 255, 255, 34), width=2)
    sheen = gradient(w, 240, (255, 255, 255), (255, 255, 255), 1.57).convert("RGBA")
    sheen.putalpha(Image.fromarray((np.linspace(22, 0, 240)[:, None] * np.ones((1, w))).astype(np.uint8)))
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), 52, fill=255)
    top = Image.new("RGBA", (w, h), (0, 0, 0, 0)); top.paste(sheen, (0, 0))
    top.putalpha(Image.fromarray(np.minimum(np.array(top.getchannel("A")), np.array(m))))
    lay.alpha_composite(top, (pad, pad))
    return lay, (x0 - pad, y0 - pad)


@functools.lru_cache(None)
def cam_shell(accent, accent2):
    x0, y0, x1, y1 = CAM; w, h = x1 - x0, y1 - y0
    g = gradient(w, h, tuple(int(c * 0.45) for c in accent), tuple(int(c * 0.25) for c in accent2), 1.0).convert("RGBA")
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), 48, fill=255)
    g.putalpha(m)
    return g, m


@functools.lru_cache(None)
def host(md, mouth, eyes, arm):
    """Rohan cropped to head + shoulders for the host cam."""
    big = mascot(md, mouth, eyes, arm, 440)       # 440 x 660
    x0 = (big.width - 300) // 2
    return big.crop((x0, 40, x0 + 300, 340))


# ------------------------------------------------------------------ footage (official images, logos, stock clips)
@functools.lru_cache(None)
def panel_mask():
    x0, y0, x1, y1 = PANEL
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), 52, fill=255)
    return m


@functools.lru_cache(None)
def _image(path):
    return Image.open(path).convert("RGB")


@functools.lru_cache(None)
def _video(path, frames):
    pw, ph = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
    return np.memmap(path, dtype=np.uint8, mode="r", shape=(frames, ph, pw, 3))


@functools.lru_cache(None)
def _bottom_shade(h_frac=0.55, strength=230):
    pw, ph = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
    a = np.zeros((ph, pw), np.uint8)
    start = int(ph * (1 - h_frac))
    a[start:] = (np.linspace(0, 1, ph - start) ** 1.4 * strength).astype(np.uint8)[:, None]
    sh = Image.new("RGBA", (pw, ph), BG + (0,)); sh.putalpha(Image.fromarray(a))
    return sh


def media_frame(item, t_rel, span):
    """RGB image of the panel size for a media item at t_rel seconds into its scene (span = scene length)."""
    pw, ph = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
    if item["kind"] == "video":
        mm = _video(item["path"], int(item["frames"]))
        n = len(mm); i = int(t_rel * FPS)
        i = i % (2 * n - 2) if n > 2 else 0          # ping-pong instead of a hard loop jump
        if i >= n: i = 2 * n - 2 - i
        return Image.fromarray(np.asarray(mm[i]))
    im = _image(item["path"])
    # cover-crop, then a slow Ken Burns push-in with a gentle drift
    sc = max(pw / im.width, ph / im.height) * 1.12
    w, h = im.width * sc, im.height * sc
    p = ease_io(clamp(t_rel / max(1.0, span)))
    z = 1.0 + 0.10 * p
    cw, ch = pw / z, ph / z
    cx = w / 2 + (w - cw) * 0.18 * (p - 0.5); cy = h / 2
    box = ((cx - cw / 2) / sc, (cy - ch / 2) / sc, (cx + cw / 2) / sc, (cy + ch / 2) / sc)
    return im.resize((pw, ph), Image.BICUBIC, box=box)


def draw_media(img, item, t_rel, span, alpha=1.0, dim=0.0, scale=1.0):
    x0, y0, x1, y1 = PANEL
    fr = media_frame(item, t_rel, span).convert("RGBA")
    if dim > 0:
        fr.alpha_composite(Image.new("RGBA", fr.size, BG + (int(255 * dim),)))
    if scale != 1.0:
        w, h = fr.size
        fr = fr.resize((int(w * scale), int(h * scale)), Image.BICUBIC).crop(
            (int((w * scale - w) / 2), int((h * scale - h) / 2), int((w * scale - w) / 2) + w, int((h * scale - h) / 2) + h))
    m = panel_mask()
    if alpha < 1: m = m.point(lambda v: int(v * alpha))
    fr.putalpha(m)
    img.alpha_composite(fr, (x0, y0))


@functools.lru_cache(None)
def _logo_disc(path, size):
    lg = Image.open(path).convert("RGBA")
    disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(disc).ellipse((0, 0, size - 1, size - 1), fill=(255, 255, 255, 255))
    inner = int(size * 0.66)
    lg = lg.resize((inner, inner), Image.LANCZOS)
    disc.alpha_composite(lg, ((size - inner) // 2, (size - inner) // 2))
    m = Image.new("L", (size, size), 0); ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=255)
    disc.putalpha(Image.fromarray(np.minimum(np.array(disc.getchannel("A")), np.array(m))))
    return disc


# ------------------------------------------------------------------ the renderer
class ModernReel(Reel):
    def __init__(self, plan, words, duration):
        super().__init__(plan, words, duration)
        # caption chunks: max 3 words, break on punctuation/pauses
        self.chunks, cur = [], []
        for i, (w, s, e) in enumerate(words):
            cur.append(i)
            nxt = words[i + 1][1] if i + 1 < len(words) else 1e9
            if len(cur) >= 3 or w.endswith((".", "?", "!", ",", ":", "…")) or nxt - e > 0.3:
                self.chunks.append(cur); cur = []
        if cur: self.chunks.append(cur)
        self.blobs = [(VIOLET, 360, 0.0), (CYAN, 300, 2.1), (PINK, 260, 4.2)]
        self.media = {m["id"]: m for m in plan.get("media", []) if m.get("path") and os.path.exists(m["path"])}
        self._hook_setup()

    # -------------------------------------------------------------- fast hook
    def _hook_setup(self):
        """No separate intro screen: the reel is in its normal layout from frame 1. The hook = first sentence; its key words
        (cold_open items) slam inside the panel until the first scene starts."""
        words = self.words
        self.hook_end = self.scenes[0]["_t"] if self.scenes else 0.0
        self.hook_items = []
        for k, ln in enumerate(self.open[:3]):
            at = 0.0 if k == 0 else self.tl.at(ln.get("at"))
            if at is None: continue
            self.hook_items.append((max(0.0, at - 0.05), str(ln.get("text", "")).upper()))
        self.hook_items.sort()
        self.open_end = 0.0
        if self.cuts: self.cuts[0] = 0.0
        self.moods = sorted([(0.0, "shocked", False)] + [m for m in self.moods if m[0] > 0.05])

    def hook_card(self, img, t, acc, acc2):
        if not self.hook_items: return
        cur = [h for h in self.hook_items if h[0] <= t] or self.hook_items[:1]
        t0, txt = cur[-1]
        dt = t - t0 if t0 > 0 else t + 0.5  # the first item is fully on screen at frame 1 (cover)
        x0, y0, x1, y1 = PANEL; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        d = ImageDraw.Draw(img)
        pill(img, (cx, y0 + 90), "JUST IN", F("mono", 30), WHITE + (255,), RED + (230,), pad=(24, 14), radius=14,
             dot=WHITE + (int(255 * (0.5 + 0.5 * math.sin(t * 9))),))
        f = fit(d, txt, "black", 170, x1 - x0 - 100)
        lines = [txt]
        if d.textlength(txt, font=F("black", 170)) > (x1 - x0 - 100) * 1.25 and " " in txt:
            ws = txt.split(); h = (len(ws) + 1) // 2
            lines = [" ".join(ws[:h]), " ".join(ws[h:])]
            f = F("black", min(170, min(170 * (x1 - x0 - 100) / max(1, d.textlength(l, font=F("black", 170))) for l in lines)))
        punch = 1.0 + 0.28 * (1 - ease(dt / 0.14))
        fl = max(0.0, 1 - dt / 0.12)
        if fl > 0:
            m = Image.new("RGBA", (x1 - x0, y1 - y0), acc + (int(60 * fl),))
            mk = Image.new("L", m.size, 0); ImageDraw.Draw(mk).rounded_rectangle((0, 0, m.width - 1, m.height - 1), 52, fill=int(60 * fl))
            m.putalpha(mk); img.alpha_composite(m, (x0, y0))
        lh = f.size * 1.05
        for k, ln in enumerate(lines):
            yy = cy + 20 + (k - (len(lines) - 1) / 2) * lh
            if dt < 0.09:
                for off, tint in ((-12, (255, 40, 90)), (12, (40, 220, 255))):
                    paste(img, text_layer(ln, f, tint + (150,)), (cx + off, yy), "mm", alpha=0.8, scale=punch)
            paste(img, grad_text(ln, f, acc, acc2), (cx, yy), "mm", scale=punch, glow=acc, glow_r=30)

    # -------------------------------------------------------------- frame
    def frame(self, i):
        t = i / FPS
        sc = None
        for s in self.scenes:
            if s["_t"] <= t < s["_end"]: sc = s
        tint = (sc or {}).get("tint", "warm")
        acc, acc2 = TINTS.get(tint, TINTS["warm"])
        img = BASE.copy()
        # drifting colour blobs (accent-coloured)
        for k, (c0, r, ph) in enumerate(self.blobs):
            c = acc if k == 0 else (acc2 if k == 1 else c0)
            bx = 540 + 380 * math.sin(t * 0.13 + ph) - 2 * r
            by = [620, 1350, 1000][k] + 220 * math.cos(t * 0.11 + ph * 1.3) - 2 * r
            img.alpha_composite(blob(c, r), (int(bx), int(by)))
        cold = t < self.open_end
        if cold:
            self.cold_open(img, t, acc, acc2)
        else:
            self.chrome(img, t, acc, acc2)
            lay, pos = panel_shell(acc)
            paste(img, lay, pos, "lt")
            if sc: self.card(img, sc, t, acc, acc2)
            elif t < self.hook_end: self.hook_card(img, t, acc, acc2)
            self.host_cam(img, t, acc, acc2)
            self.captions(img, t, acc)
        # progress bar
        d = ImageDraw.Draw(img)
        p = clamp(t / max(0.1, self.duration))
        d.rounded_rectangle((M, 34, WIDTH - M, 40), 3, fill=(255, 255, 255, 30))
        if p > 0:
            bar = gradient(max(1, int((WIDTH - 2 * M) * p)), 6, acc, acc2).convert("RGBA")
            img.alpha_composite(bar, (M, 34))
        rgb = img.convert("RGB")
        g = GRAIN[i % len(GRAIN)]
        rgb = Image.blend(rgb, Image.merge("RGB", (g, g, g)), 0.035)
        if t > self.duration + 0.3:
            rgb = Image.blend(rgb, Image.new("RGB", rgb.size, BG), min(1, (t - self.duration - 0.3) / 0.5))
        return rgb.tobytes()

    # -------------------------------------------------------------- header + hook
    def chrome(self, img, t, acc, acc2):
        p = self.plan
        pulse = 0.55 + 0.45 * math.sin(t * 5)
        tag = (p.get("series_tag") or "AI NEWS").upper()[:18]
        w = pill(img, (M, TOP), "LIVE", F("mono", 26), WHITE + (255,), (255, 255, 255, 18), anchor="lm",
                 pad=(22, 14), border=(255, 255, 255, 40), dot=RED + (int(255 * pulse),))
        pill(img, (M + w + 16, TOP), tag, F("mono", 26), acc + (255,), acc + (40,), anchor="lm", pad=(22, 14), border=acc + (90,))
        if p.get("episode"):
            ImageDraw.Draw(img).text((WIDTH - M, TOP), f"EP {int(p['episode']):02d}", font=F("mono", 28), fill=MUTED + (255,), anchor="rm")
        l1 = p.get("title_line1") or ""; l2 = p.get("title_line2") or ""
        d = ImageDraw.Draw(img)
        size = 96
        for s_ in (l1, l2):
            ww = d.textlength(s_.replace("*", ""), font=F("black", size))
            if ww > WIDTH - 2 * M: size = size * (WIDTH - 2 * M) / ww
        f = F("black", size)
        for k, s_ in enumerate((l1, l2)):
            if not s_: continue
            ak = 1.0
            x = M; y = TOP + 76 + k * (size * 1.08)
            for part in re.split(r"(\*[^*]+\*)", s_):
                if not part: continue
                txt = part.strip("*")
                lay = grad_text(txt, f, acc, acc2) if part.startswith("*") else text_layer(txt, f, WHITE + (255,))
                paste(img, lay, (x - 4, y), "lt", alpha=ak, dy=(1 - ak) * 30,
                      glow=acc if part.startswith("*") else None, glow_r=18)
                x += d.textlength(txt, font=f)

    # -------------------------------------------------------------- host cam
    def host_cam(self, img, t, acc, acc2):
        x0, y0, x1, y1 = CAM
        a = 1.0
        _, md, point = self.mood(t)
        v = self.viseme(t)
        ph = (t + 0.7) % 3.4
        bgc, mask = cam_shell(acc, acc2)
        frame = bgc.copy()
        h = host(md, v or MOOD_REST.get(md, "closed"), "blink" if ph < 0.12 else None, "down")
        bob = int(3 * math.sin(t * 2.2) + (2 if v else 0) * math.sin(t * 17))
        frame.alpha_composite(h, (0, 4 + bob))
        frame.putalpha(Image.fromarray(np.minimum(np.array(frame.getchannel("A")), np.array(mask))))
        lay = Image.new("RGBA", (x1 - x0 + 40, y1 - y0 + 40), (0, 0, 0, 0))
        lay.alpha_composite(frame, (20, 20))
        d = ImageDraw.Draw(lay)
        speak = 1.0 if v else 0.0
        ring = tuple(int(c) for c in acc) + (int(90 + 140 * speak),)
        d.rounded_rectangle((18, 18, x1 - x0 + 21, y1 - y0 + 21), 50, outline=ring, width=4)
        paste(img, lay, (x0 - 20, y0 - 20), "lt", alpha=a, dy=(1 - a) * 40,
              glow=acc if v else None, glow_r=16)
        pill(img, (x0 + 18, y1 - 18), "ROHAN · AI", F("mono", 20), WHITE + (255,), (8, 10, 20, 170), anchor="lb", pad=(14, 9))

    # -------------------------------------------------------------- captions
    def captions(self, img, t, acc):
        ch = None
        for c in self.chunks:
            s = self.words[c[0]][1]; e = self.words[c[-1]][2] + 0.25
            if s - 0.05 <= t < e: ch = c; break
        if not ch: return
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = CAP; maxw = x1 - x0
        ws = [self.words[i][0].strip("\"“”") for i in ch]
        size = 76
        f = F("black", size)
        lines = wrap(d, " ".join(ws), f, maxw, 3)
        while (len(lines) > 2 or any(d.textlength(l, font=f) > maxw for l in lines)) and size > 50:
            size -= 4; f = F("black", size); lines = wrap(d, " ".join(ws), f, maxw, 3)
        lh = size * 1.25
        cy = (y0 + y1) / 2 - (len(lines) - 1) * lh / 2
        k = 0
        start = self.words[ch[0]][1]
        a = ease((t - start + 0.05) / 0.18)
        for li, line in enumerate(lines):
            x = x0; y = cy + li * lh
            for w in line.split():
                idx = ch[min(k, len(ch) - 1)]; k += 1
                ws_, we_ = self.words[idx][1], self.words[idx][2]
                active = ws_ <= t < we_ + 0.06
                tw = d.textlength(w, font=f)
                if active:
                    pa = ease((t - ws_) / 0.12)
                    padx, pady = 12, size * 0.14
                    d.rounded_rectangle((x - padx, y - size * 0.58 - pady * pa, x + tw + padx, y + size * 0.52 + pady * pa), 16,
                                        fill=acc + (int(255 * pa),))
                fill = (BG if active else (WHITE if t >= ws_ else SOFT))
                lay = text_layer(w, f, fill + (255,))
                paste(img, lay, (x - 4, y), "lm", alpha=a, dy=(1 - a) * 16)
                x += tw + size * 0.28

    # -------------------------------------------------------------- cold open
    def cold_open(self, img, t, acc, acc2):
        """Kinetic hook: each 1–2 word beat slams in on the beat it is spoken (punch-zoom, RGB split, flash);
        key words (numbers, names, FREE…) are huge in the accent gradient."""
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, WIDTH, HEIGHT), fill=BG + (120,))
        beat = None
        for k, bt in enumerate(self.beats):
            st = self.words[bt[0]][1] - 0.04
            en = self.words[self.beats[k + 1][0]][1] - 0.04 if k + 1 < len(self.beats) else self.open_end
            if st <= t < en: beat = (k, bt, st)
        pill(img, (540, 300), "BREAKING · AI", F("mono", 30), WHITE + (255,), RED + (220,), pad=(26, 14),
             dot=WHITE + (int(255 * (0.5 + 0.5 * math.sin(t * 9))),))
        if beat is None: return
        k, bt, st = beat
        dt = t - st
        toks = [self.words[i][0].strip("\"“”") for i in bt]
        key = any(_norm(x) in self.keys for x in toks)
        txt = " ".join(toks)
        if key: txt = txt.upper().rstrip(".,!?")
        size = 200 if key else 150
        f = fit(d, txt, "black", size, WIDTH - 2 * M)
        lay = grad_text(txt, f, acc, acc2) if key else text_layer(txt, f, WHITE + (255,))
        if lay.width > WIDTH - 2 * M:
            lay = lay.resize((WIDTH - 2 * M, int(lay.height * (WIDTH - 2 * M) / lay.width)), Image.BICUBIC)
        punch = 1.0 + 0.32 * (1 - ease(dt / 0.14))
        sh = (10 * math.sin(t * 70) * max(0, 1 - dt / 0.18)) if key else 0
        cy = 900 + (0 if k % 2 == 0 else 40)
        # flash on every beat
        fl = max(0.0, 1 - dt / 0.12)
        if fl > 0:
            img.alpha_composite(Image.new("RGBA", img.size, (acc if key else (255, 255, 255)) + (int(70 * fl),)))
        # RGB split for the first frames of a beat
        if dt < 0.09:
            for off, tint in ((-14, (255, 40, 90)), (14, (40, 220, 255))):
                ghost = text_layer(txt, f, tint + (150,))
                if ghost.width > WIDTH - 2 * M:
                    ghost = ghost.resize((WIDTH - 2 * M, int(ghost.height * (WIDTH - 2 * M) / ghost.width)), Image.BICUBIC)
                paste(img, ghost, (540 + off + sh, cy), "mm", alpha=0.8, scale=punch)
        paste(img, lay, (540 + sh, cy), "mm", scale=punch, glow=acc if key else None, glow_r=30)
        # Rohan reacting under the words (shocked on key beats), round cam with a speaking ring
        v = self.viseme(t)
        hm = host("shocked" if key else "smirk", v or "O", None, "down")
        r = 150
        circ = Image.new("RGBA", (2 * r, 2 * r), (0, 0, 0, 0))
        bgc = gradient(2 * r, 2 * r, tuple(int(c * 0.5) for c in acc), tuple(int(c * 0.3) for c in acc2), 1.0).convert("RGBA")
        circ.alpha_composite(bgc)
        circ.alpha_composite(hm, (0, 6))
        m = Image.new("L", (2 * r, 2 * r), 0); ImageDraw.Draw(m).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
        circ.putalpha(m)
        ImageDraw.Draw(circ).ellipse((2, 2, 2 * r - 3, 2 * r - 3), outline=acc + (255,), width=5)
        pop = 1.0 + 0.06 * (1 - ease(dt / 0.14)) * (1 if key else 0)
        paste(img, circ, (540, 1330), "mm", scale=pop, glow=acc, glow_r=22)
        if self.open_end - t < 0.35:
            a = ease((t - (self.open_end - 0.35)) / 0.3)
            d.rectangle((0, 0, WIDTH, HEIGHT), fill=BG + (int(160 * a),))

    # -------------------------------------------------------------- cards
    def card(self, img, sc, t, acc, acc2):
        c = sc["_resolved"]; typ = c.get("type", "headline")
        t0 = sc["_t"]
        x0, y0, x1, y1 = PANEL
        cx = (x0 + x1) / 2; L = x0 + 56; R = x1 - 56; W = R - L
        d = ImageDraw.Draw(img)
        if c.get("icon") and typ not in ("cta", "news"):
            icon(img, c["icon"], cx, y0 + 200, 0.9, acc, t - t0)
            top = y0 + 380
        else:
            top = y0 + 110

        if typ == "footage":
            item = self.media.get(c.get("media"))
            if item:
                span = sc["_end"] - t0
                a = ease((t - t0) / 0.25)
                draw_media(img, item, t - t0, span, alpha=a, scale=1.04 - 0.04 * a)
                img.alpha_composite(_bottom_shade(), (x0, y0))
                if item.get("credit"):
                    pill(img, (R + 30, y0 + 40), item["credit"].upper(), F("monom", 18), SOFT + (255,), (8, 10, 20, 170),
                         anchor="rm", pad=(14, 8))
                if c.get("caption"):
                    ca = c.get("caption_at", t0)
                    rise(img, (L, y1 - 80), c["caption"], fit(d, c["caption"], "black", 64, W), WHITE, ca, t, anchor="lm", glow=None)
                return
            typ = "headline"; c = dict(c, title=c.get("caption", ""))     # media missing -> fall back to text

        if typ == "news":
            bg = self.media.get(c.get("bg_media"))
            if bg:
                draw_media(img, bg, t - t0, sc["_end"] - t0, alpha=ease((t - t0) / 0.3), dim=0.62)
                img.alpha_composite(_bottom_shade(1.0, 200), (x0, y0))
                if bg.get("credit"):
                    pill(img, (R + 30, y0 + 40), bg["credit"].upper(), F("monom", 18), SOFT + (255,), (8, 10, 20, 170), anchor="rm", pad=(14, 8))
            pill(img, (L, y0 + 76), str(c.get("tag") or "AI NEWS").upper(), F("mono", 30), WHITE + (255,),
                 col(c.get("tag_color"), RED) + (230,), c.get("tag_at", t0), t, anchor="lm", pad=(24, 14), radius=14)
            ha = c.get("at", t0)
            if ha is not None and t >= ha:
                f = F("xbold", 78); lines = wrap(d, c.get("title", ""), f, W, 4)
                if len(lines) > 3: f = F("xbold", 66); lines = wrap(d, c.get("title", ""), f, W, 4)
                for k, ln in enumerate(lines):
                    rise(img, (L, y0 + 210 + k * f.size * 1.18), ln, f, WHITE, ha + k * 0.09, t, anchor="lt")
            sa = c.get("source_at")
            if sa is not None and t >= sa:
                p = ease((t - sa) / 0.35)
                src = str(c.get("source", "")).replace("via ", "")
                yy = y1 - 110
                lay = Image.new("RGBA", (W, 90), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
                lg = self.media.get(c.get("logo"))
                if lg:
                    lay.alpha_composite(_logo_disc(lg["path"], 64), (0, 13))
                else:
                    ld.ellipse((0, 13, 64, 77), fill=acc + (255,))
                    ld.text((32, 45), (src[:1] or "•").upper(), font=F("black", 34), fill=BG, anchor="mm")
                ld.text((86, 30), src, font=F("bold", 36), fill=WHITE, anchor="lm")
                ld.text((86, 66), "SOURCE · VERIFIED REPORT", font=F("monom", 20), fill=MUTED, anchor="lm")
                paste(img, lay, (L, yy), "lm", alpha=p, dy=(1 - p) * 20)
            d.line((L, y1 - 170, R, y1 - 170), fill=(255, 255, 255, 22), width=2)

        elif typ == "headline":
            rise(img, (cx, top + 40), c.get("title", ""), fit(d, c.get("title", ""), "black", 104, W), col(c.get("color"), WHITE), c.get("at", t0), t)
            if c.get("sub"):
                lay_t = c.get("sub_at")
                if lay_t is not None and t >= lay_t:
                    p = ease((t - lay_t) / 0.4)
                    paste(img, grad_text(c["sub"], fit(d, c["sub"], "xbold", 70, W), acc, acc2), (cx, top + 170), alpha=p, dy=(1 - p) * 30)

        elif typ == "big_number":
            if c.get("label"):
                rise(img, (cx, y0 + 120), str(c["label"]).upper(), fit(d, str(c["label"]).upper(), "mono", 34, W), MUTED, t0, t)
            va = c.get("value_at", t0)
            if va is not None and t >= va:
                p = spring((t - va) / 0.7)
                f = fit(d, c.get("value", ""), "num", 300, W)
                paste(img, grad_text(c.get("value", ""), f, col(c.get("color"), acc) if c.get("color") not in (None, "gold") else acc, acc2),
                      (cx, y0 + 380), alpha=clamp((t - va) / 0.15), scale=0.7 + 0.3 * p, glow=acc, glow_r=34)
            if c.get("note"): rise(img, (cx, y0 + 590), c["note"], fit(d, c["note"], "bold", 60, W), SOFT, c.get("note_at"), t)

        elif typ == "split":
            rise(img, (cx, y0 + 110), c.get("title", ""), fit(d, c.get("title", ""), "xbold", 64, W), WHITE, c.get("title_at", t0), t)
            Lc, Rc = c.get("left", {}), c.get("right", {})
            tw = (W - 70) / 2; ty = y0 + 220; th = 230
            for k, side in enumerate((Lc, Rc)):
                at = side.get("at")
                if at is None or t < at: continue
                p = ease((t - at) / 0.4)
                bx = L + k * (tw + 70)
                lay = Image.new("RGBA", (int(tw), th), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
                cc = col(side.get("color"), BLUE if k == 0 else AMBER)
                ld.rounded_rectangle((0, 0, tw - 1, th - 1), 36, fill=cc + (34,), outline=cc + (160,), width=3)
                ff = fit(ld, side.get("text", ""), "xbold", 62, tw - 40)
                ld.text((tw / 2, th / 2), side.get("text", ""), font=ff, fill=WHITE, anchor="mm")
                paste(img, lay, (bx, ty), "lt", alpha=p, dy=(1 - p) * 30)
            if Lc.get("at") is not None and t >= Lc["at"]:
                d.ellipse((cx - 38, ty + th / 2 - 38, cx + 38, ty + th / 2 + 38), fill=(30, 34, 54, 255), outline=(255, 255, 255, 50), width=2)
                d.text((cx, ty + th / 2), "VS", font=F("mono", 26), fill=MUTED, anchor="mm")
            ra = c.get("result_at")
            if c.get("result"):
                pill(img, (cx, y0 + 590), c["result"], fit(d, c["result"], "xbold", 56, W - 80), BG + (255,), col(c.get("result_color"), GREEN) + (255,), ra, t, pad=(36, 20))

        elif typ == "counter":
            if c.get("label"): rise(img, (cx, y0 + 130), str(c["label"]).upper(), fit(d, str(c["label"]).upper(), "mono", 34, W), MUTED, t0, t)
            at = c.get("at", t0)
            pr = ease((t - at) / 1.1) if t >= at else 0
            to = float(c.get("to", 0)); v = to * pr
            s = c.get("prefix", "") + (f"{int(round(v)):,}" if abs(to) >= 1000 else str(int(round(v)))) + c.get("suffix", "")
            if t >= at - 0.2:
                paste(img, grad_text(s, fit(d, s, "num", 190, W), acc, acc2), (cx, y0 + 360), glow=acc, glow_r=26)
            if c.get("done_text"):
                pill(img, (cx, y0 + 560), c["done_text"], fit(d, c["done_text"], "xbold", 52, W - 80), BG + (255,), GREEN + (255,), c.get("done_at"), t, pad=(34, 18))

        elif typ == "percent":
            at = c.get("at", t0); val = float(c.get("value", 0))
            pr = ease((t - at) / 1.0) if t >= at else 0
            r = 190; ccx, ccy = cx, y0 + 320
            d.ellipse((ccx - r, ccy - r, ccx + r, ccy + r), outline=(255, 255, 255, 26), width=28)
            if pr > 0:
                ring = Image.new("RGBA", (2 * r + 40, 2 * r + 40), (0, 0, 0, 0))
                ImageDraw.Draw(ring).arc((20, 20, 2 * r + 20, 2 * r + 20), -90, -90 + 360 * val / 100 * pr, fill=acc + (255,), width=28)
                paste(img, ring, (ccx, ccy), glow=acc, glow_r=18)
            s = f"{int(val * pr)}%"
            paste(img, grad_text(s, F("num", 130), WHITE, SOFT), (ccx, ccy))
            if c.get("label"): rise(img, (cx, y0 + 600), c["label"], fit(d, c["label"], "xbold", 60, W), WHITE, c.get("label_at", at), t)

        elif typ == "compare_arrow":
            rise(img, (cx, y0 + 100), str(c.get("title", "")).upper(), fit(d, str(c.get("title", "")).upper(), "mono", 32, W), MUTED, c.get("title_at", t0), t)
            pill(img, (cx, y0 + 230), c.get("from_text", ""), fit(d, c.get("from_text", ""), "xbold", 60, W - 80), SOFT + (255,), (255, 255, 255, 22), c.get("from_at"), t, pad=(40, 22), border=(255, 255, 255, 50))
            ta = c.get("to_at")
            if ta is not None and t >= ta - 0.4:
                p = ease((t - ta + 0.4) / 0.4)
                d.line((cx, y0 + 300, cx, y0 + 300 + 70 * p), fill=acc + (255,), width=8)
                if p > 0.9: d.polygon([(cx - 22, y0 + 362), (cx + 22, y0 + 362), (cx, y0 + 392)], fill=acc + (255,))
            if c.get("to_text") and ta is not None and t >= ta:
                p = ease((t - ta) / 0.4)
                paste(img, grad_text(c["to_text"], fit(d, c["to_text"], "num", 120, W), acc, acc2), (cx, y0 + 470), alpha=p, scale=0.85 + 0.15 * p, glow=acc)
            if c.get("result"): rise(img, (cx, y0 + 620), c["result"], fit(d, c["result"], "xbold", 58, W), GREEN, c.get("result_at"), t)

        elif typ == "strike_list":
            rise(img, (L, y0 + 100), c.get("title", ""), fit(d, c.get("title", ""), "xbold", 64, W), col(c.get("color"), WHITE), c.get("title_at", t0), t, anchor="lm")
            for k, it in enumerate(c.get("items", [])[:4]):
                at = it.get("at")
                if at is None or t < at - 0.2: continue
                yy = y0 + 220 + k * 120
                p = ease((t - at + 0.2) / 0.35)
                lay = Image.new("RGBA", (W, 96), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
                ld.rounded_rectangle((0, 0, W - 1, 95), 28, fill=(255, 255, 255, 14), outline=(255, 255, 255, 30), width=2)
                ld.text((34, 48), it.get("text", ""), font=fit(ld, it.get("text", ""), "bold", 50, W - 80), fill=WHITE, anchor="lm")
                paste(img, lay, (L, yy), "lt", alpha=p, dy=(1 - p) * 24)
                if it.get("strike", True) and t >= at:
                    q = ease((t - at) / 0.3)
                    d.line((L + 24, yy + 48, L + 24 + (W - 48) * q, yy + 48), fill=RED + (255,), width=7)

        elif typ == "checklist":
            rise(img, (L, y0 + 100), c.get("title", ""), fit(d, c.get("title", ""), "black", 72, W), WHITE, t0, t, anchor="lm")
            for k, it in enumerate(c.get("items", [])[:4]):
                at = it.get("at")
                if at is None or t < at: continue
                p = ease((t - at) / 0.35); yy = y0 + 230 + k * 125
                lay = Image.new("RGBA", (W, 100), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
                ld.rounded_rectangle((0, 0, W - 1, 99), 30, fill=(255, 255, 255, 14), outline=(255, 255, 255, 30), width=2)
                ld.ellipse((22, 22, 78, 78), fill=acc + (255,))
                ld.line((36, 51, 47, 62, 66, 39), fill=BG, width=7, joint="curve")
                ld.text((104, 50), it.get("text", ""), font=fit(ld, it.get("text", ""), "bold", 50, W - 140), fill=WHITE, anchor="lm")
                paste(img, lay, (L, yy), "lt", alpha=p, dy=(1 - p) * 24)
            if c.get("final"):
                pill(img, (cx, y1 - 90), c["final"], fit(d, c["final"], "xbold", 50, W - 80), BG + (255,), GREEN + (255,), c.get("final_at"), t, pad=(34, 18))

        elif typ == "warning":
            p = ease((t - t0) / 0.4)
            tri = Image.new("RGBA", (160, 140), (0, 0, 0, 0)); td = ImageDraw.Draw(tri)
            td.rounded_rectangle((0, 0, 1, 1), 1)
            td.polygon([(80, 6), (154, 134), (6, 134)], fill=RED + (255,))
            td.text((80, 90), "!", font=F("black", 80), fill=BG, anchor="mm")
            paste(img, tri, (cx, y0 + 130), alpha=p, glow=RED, glow_r=20, dy=6 * math.sin(t * 40) * max(0, 1 - (t - t0) * 3))
            rise(img, (cx, y0 + 270), c.get("title", ""), fit(d, c.get("title", ""), "black", 72, W), RED, c.get("title_at", t0), t)
            if c.get("sub"): rise(img, (cx, y0 + 360), c["sub"], fit(d, c["sub"], "bold", 54, W), WHITE, c.get("sub_at", t0 + 0.2), t)
            chips = c.get("chips", [])[:3]
            for k, it in enumerate(chips):
                xs = [cx - 230, cx + 230, cx][k] if len(chips) == 3 else [cx - 200, cx + 200][k] if len(chips) == 2 else cx
                ys = [y0 + 470, y0 + 470, y0 + 570][k]
                cc = col(it.get("color"), BLUE)
                pill(img, (xs, ys), it.get("text", ""), fit(d, it.get("text", ""), "bold", 44, 400), WHITE + (255,), cc + (60,), it.get("at"), t, pad=(28, 16), border=cc + (180,))
            if c.get("big"):
                ba = c.get("big_at")
                if ba is not None and t >= ba:
                    q = spring((t - ba) / 0.6)
                    paste(img, grad_text(c["big"], fit(d, c["big"], "num", 130, W), col(c.get("big_color"), RED), PINK), (cx, y1 - 100), scale=0.7 + 0.3 * q, glow=RED)

        elif typ == "money_rain":
            sym = str(c.get("symbol") or CURRENCY)[:3]
            for k in range(12):
                ph = (t * 0.55 + k * 0.29) % 1.0
                bx = L + (k * 157) % (W - 120); by = y0 + 20 + ph * (y1 - y0 - 140)
                note = Image.new("RGBA", (150, 74), (0, 0, 0, 0)); nd = ImageDraw.Draw(note)
                nd.rounded_rectangle((0, 0, 149, 73), 14, fill=(52, 211, 153, 210))
                nd.rounded_rectangle((8, 8, 141, 65), 10, outline=(6, 78, 59, 160), width=3)
                nd.text((75, 37), sym, font=F("num", 40), fill=(6, 78, 59), anchor="mm")
                note = note.rotate((k * 37 + t * 50) % 360, expand=True, resample=Image.BICUBIC)
                a = min(1, ph * 6, (1 - ph) * 6)
                paste(img, note, (bx, by), "lt", alpha=a * 0.9)
            la = c.get("line1_at", t0)
            if la is not None and t >= la:
                p = spring((t - la) / 0.6)
                paste(img, grad_text(c.get("line1", ""), fit(d, c.get("line1", ""), "num", 150, W), GREEN, CYAN), (cx, y0 + 320), scale=0.75 + 0.25 * p, glow=GREEN)
            rise(img, (cx, y0 + 480), c.get("line2", ""), fit(d, c.get("line2", ""), "xbold", 62, W), WHITE, c.get("line2_at"), t)

        elif typ == "title_slam":
            at = c.get("at", t0)
            if at is not None and t >= at:
                p = spring((t - at) / 0.55)
                sh = 8 * math.sin(t * 60) * max(0, 1 - (t - at) * 3)
                cc = col(c.get("color"), acc)
                paste(img, grad_text(c.get("title", ""), fit(d, c.get("title", ""), "black", 230, W), cc, acc2),
                      (cx + sh, (y0 + y1) / 2 - 20), scale=1.25 - 0.25 * p, alpha=clamp((t - at) / 0.12), glow=cc, glow_r=36)

        elif typ == "cta":
            icon(img, "share", cx, y0 + 190, 0.85, acc, t - t0)
            rise(img, (cx, y0 + 380), c.get("line1", ""), fit(d, c.get("line1", ""), "black", 86, W), WHITE, c.get("line1_at", t0 + 0.2), t)
            la2 = c.get("line2_at")
            if c.get("line2") and la2 is not None and t >= la2:
                p = ease((t - la2) / 0.4)
                paste(img, grad_text(c["line2"], fit(d, c["line2"], "xbold", 64, W), acc, acc2), (cx, y0 + 480), alpha=p, dy=(1 - p) * 26)
            if t >= t0 + 0.8:
                g = gradient(560, 96, acc, acc2).convert("RGBA")
                m = Image.new("L", (560, 96), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, 559, 95), 48, fill=255); g.putalpha(m)
                ImageDraw.Draw(g).text((280, 48), f"Follow {HANDLE}", font=fit(ImageDraw.Draw(g), f"Follow {HANDLE}", "black", 40, 500), fill=BG, anchor="mm")
                p = ease((t - t0 - 0.8) / 0.4)
                paste(img, g, (cx, y1 - 110), alpha=p, dy=(1 - p) * 20, glow=acc, glow_r=20)
