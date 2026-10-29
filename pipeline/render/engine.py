"""AI-news reel renderer (forked from the Paisa Decode renderer).

Inputs
  plan  : dict produced by the script writer (see prompts/script_writer.md for the schema)
  words : list of (text, start, end) for the spoken words of the voiceover
Output
  video-only MP4, 1080x1920 @ 30 fps

The look: dark cinematic grade, gold accents, film grain, letterbox cold open,
punch-in cuts, Rohan mascot lip-syncing in the lower half, template cards up top,
word-by-word English captions with the spoken word in gold.
"""
import functools, io, math, os, re, subprocess, sys
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cairosvg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rohan import rohan  # noqa: E402

WIDTH, HEIGHT, FPS = 1080, 1920, 30
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
GOLD = (242, 182, 48); WHITE = (250, 247, 240); RED = (232, 72, 60); GREEN = (120, 210, 140)
BLUE = (130, 200, 245); INK = (14, 12, 16); MUTED = (170, 160, 150); ICE = (170, 210, 255)
COLORS = {"gold": GOLD, "white": WHITE, "red": RED, "green": GREEN, "blue": BLUE, "muted": MUTED, "ice": ICE}
OPEN_END = None  # set per render
_H = (os.environ.get("IG_HANDLE") or "ihackgrowth").strip().lstrip("@")
HANDLE = ("@" + _H) if _H else (os.environ.get("BRAND_NAME") or "AI NEWS")
CURRENCY = os.environ.get("CURRENCY_SYMBOL") or "$"

# =====================================================================  helpers
@functools.lru_cache(None)
def F(name, size):
    path = {"bold": "Mukta-ExtraBold.ttf", "semi": "Mukta-Bold.ttf", "disp": "YatraOne-Regular.ttf", "latin": "Poppins-Bold.ttf"}[name]
    return ImageFont.truetype(os.path.join(FD, path), max(8, int(size)), layout_engine=ImageFont.Layout.RAQM)


def col(c, default=WHITE):
    if isinstance(c, (list, tuple)): return tuple(c)
    return COLORS.get(c or "", default)


def ease_out(x): x = max(0., min(1., x)); return 1 - (1 - x) ** 3
def ease_back(x):
    x = max(0., min(1., x)); c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def fit_font(d, s, name, size, maxw):
    f = F(name, size)
    w = d.textlength(s, font=f)
    if w > maxw: f = F(name, size * maxw / w)
    return f


def text(d, xy, s, font, fill, anchor="mm", stroke=0, sfill=INK):
    d.text(xy, s, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sfill)


def pop_text(img, xy, s, fname, size, fill, t0, t, stroke=6, dur=0.28, maxw=980):
    if t0 is None or t < t0 or not s: return
    k = ease_back((t - t0) / dur)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    f = fit_font(d, s, fname, size * (0.4 + 0.6 * k), maxw)
    a = min(1, (t - t0) / 0.12)
    text(d, xy, s, f, fill + (int(255 * a),), stroke=stroke)
    img.alpha_composite(layer)


def chip(img, cx, cy, s, fg, bg, t0, t, size=72, minw=0, maxw=960):
    if t0 is None or t < t0 or not s: return
    k = ease_back((t - t0) / 0.3)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    f = fit_font(d, s, "bold", size, maxw - 70)
    tw = max(minw, d.textlength(s, font=f) + 70)
    hw, hh = tw / 2 * k, size * 0.95 * k
    d.rounded_rectangle((cx - hw, cy - hh, cx + hw, cy + hh), int(40 * k + 1), fill=bg, outline=INK, width=6)
    if k > 0.5: text(d, (cx, cy + 4), s, f, fg)
    img.alpha_composite(layer)


def strike(d, x0, y0, x1, y1, p, c=RED, w=12):
    if p <= 0: return
    p = min(p, 1); d.line((x0, y0, x0 + (x1 - x0) * p, y0 + (y1 - y0) * p), fill=c, width=w)


# =====================================================================  icons
def icon_jar(d, cx, cy, s=1.0, level=1.0):
    w, h = 170 * s, 230 * s
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), int(46 * s), fill=(150, 205, 245), outline=INK, width=max(2, int(7 * s)))
    top = cy + h / 2 - h * level * 0.92
    d.rounded_rectangle((cx - w / 2 + 10 * s, top, cx + w / 2 - 10 * s, cy + h / 2 - 10 * s), int(36 * s), fill=(70, 150, 225))
    d.rectangle((cx - 34 * s, cy - h / 2 - 34 * s, cx + 34 * s, cy - h / 2 + 4 * s), fill=(40, 90, 200), outline=INK, width=max(2, int(6 * s)))


def icon_chai(d, cx, cy, s=1.0):
    d.polygon([(cx - 60 * s, cy - 70 * s), (cx + 60 * s, cy - 70 * s), (cx + 44 * s, cy + 70 * s), (cx - 44 * s, cy + 70 * s)], fill=(235, 235, 240), outline=INK)
    d.polygon([(cx - 54 * s, cy - 40 * s), (cx + 54 * s, cy - 40 * s), (cx + 44 * s, cy + 66 * s), (cx - 44 * s, cy + 66 * s)], fill=(190, 120, 60))
    for k in (-24, 0, 24):
        d.arc((cx + k - 12 * s, cy - 130 * s, cx + k + 12 * s, cy - 80 * s), 90, 270, fill=(230, 230, 230), width=int(5 * s))


def icon_plane(d, cx, cy, s=1.0):
    d.polygon([(cx - 90 * s, cy), (cx + 90 * s, cy - 70 * s), (cx + 30 * s, cy + 70 * s), (cx, cy + 20 * s)], fill=GOLD, outline=INK)
    d.line((cx, cy + 20 * s, cx + 90 * s, cy - 70 * s), fill=INK, width=int(5 * s))


def icon_coin(d, cx, cy, s=1.0):
    d.ellipse((cx - 90 * s, cy - 90 * s, cx + 90 * s, cy + 90 * s), fill=GOLD, outline=(201, 142, 18), width=int(10 * s))
    text(d, (cx, cy + 6 * s), "₹", F("latin", 110 * s), INK)


def icon_shop(d, cx, cy, s=1.0):
    d.rectangle((cx - 150 * s, cy - 40 * s, cx + 150 * s, cy + 120 * s), fill=(80, 76, 92), outline=INK, width=int(7 * s))
    for k in range(6):
        c = RED if k % 2 == 0 else WHITE
        d.polygon([(cx - 170 * s + k * 57 * s, cy - 110 * s), (cx - 113 * s + k * 57 * s, cy - 110 * s), (cx - 113 * s + k * 57 * s, cy - 40 * s), (cx - 170 * s + k * 57 * s, cy - 40 * s)], fill=c, outline=INK)
    d.rectangle((cx - 40 * s, cy + 10 * s, cx + 40 * s, cy + 120 * s), fill=GOLD, outline=INK, width=int(5 * s))


def icon_calc(d, cx, cy, s=1.0, display=""):
    x0, y0 = cx - 230 * s, cy - 220 * s
    d.rounded_rectangle((x0, y0, x0 + 460 * s, y0 + 440 * s), int(40 * s), fill=(44, 44, 54), outline=INK, width=int(8 * s))
    d.rounded_rectangle((x0 + 30 * s, y0 + 30 * s, x0 + 430 * s, y0 + 170 * s), int(20 * s), fill=(160, 200, 120), outline=INK, width=int(6 * s))
    if display: text(d, (x0 + 410 * s, y0 + 100 * s), display, F("latin", 96 * s), (30, 50, 20), anchor="rm")
    for r in range(2):
        for c in range(4):
            bx = x0 + 40 * s + c * 100 * s; by = y0 + 210 * s + r * 105 * s
            d.rounded_rectangle((bx, by, bx + 80 * s, by + 80 * s), int(16 * s), fill=GOLD if (r, c) == (1, 3) else (90, 90, 104), outline=INK, width=int(5 * s))


def icon_chip(d, cx, cy, s=1.0):
    """AI chip: square die with pins and 'AI' on it."""
    w = 170 * s
    for k in range(5):
        o = (-w * 0.8 + k * w * 0.4)
        for (x0, y0, x1, y1) in ((cx + o - 8 * s, cy - w - 40 * s, cx + o + 8 * s, cy - w),
                                 (cx + o - 8 * s, cy + w, cx + o + 8 * s, cy + w + 40 * s),
                                 (cx - w - 40 * s, cy + o - 8 * s, cx - w, cy + o + 8 * s),
                                 (cx + w, cy + o - 8 * s, cx + w + 40 * s, cy + o + 8 * s)):
            d.rectangle((x0, y0, x1, y1), fill=GOLD, outline=INK)
    d.rounded_rectangle((cx - w, cy - w, cx + w, cy + w), int(26 * s), fill=(44, 44, 58), outline=INK, width=int(8 * s))
    d.rounded_rectangle((cx - w * 0.62, cy - w * 0.62, cx + w * 0.62, cy + w * 0.62), int(18 * s), outline=GOLD, width=int(6 * s))
    text(d, (cx, cy + 6 * s), "AI", F("latin", 120 * s), GOLD)


def icon_robot(d, cx, cy, s=1.0):
    d.line((cx, cy - 190 * s, cx, cy - 130 * s), fill=INK, width=int(10 * s))
    d.ellipse((cx - 24 * s, cy - 220 * s, cx + 24 * s, cy - 172 * s), fill=RED, outline=INK, width=int(5 * s))
    d.rounded_rectangle((cx - 170 * s, cy - 130 * s, cx + 170 * s, cy + 140 * s), int(60 * s), fill=(200, 210, 225), outline=INK, width=int(8 * s))
    d.rounded_rectangle((cx - 130 * s, cy - 80 * s, cx + 130 * s, cy + 60 * s), int(40 * s), fill=(30, 34, 48), outline=INK, width=int(6 * s))
    for ex in (-60, 60):
        d.ellipse((cx + ex * s - 26 * s, cy - 36 * s, cx + ex * s + 26 * s, cy + 16 * s), fill=BLUE)
    d.rounded_rectangle((cx - 60 * s, cy + 82 * s, cx + 60 * s, cy + 110 * s), int(10 * s), fill=(90, 96, 110))


def icon_globe(d, cx, cy, s=1.0):
    r = 170 * s
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(60, 120, 200), outline=INK, width=int(8 * s))
    for k in (0.35, 0.72):
        d.ellipse((cx - r * k, cy - r, cx + r * k, cy + r), outline=(190, 225, 255), width=int(5 * s))
    for y in (-0.5, 0, 0.5):
        hw = r * math.sqrt(1 - y * y)
        d.line((cx - hw, cy + y * r, cx + hw, cy + y * r), fill=(190, 225, 255), width=int(5 * s))


def icon_phone(d, cx, cy, s=1.0):
    d.rounded_rectangle((cx - 110 * s, cy - 200 * s, cx + 110 * s, cy + 200 * s), int(36 * s), fill=(30, 30, 40), outline=INK, width=int(8 * s))
    d.rounded_rectangle((cx - 92 * s, cy - 172 * s, cx + 92 * s, cy + 172 * s), int(22 * s), fill=(70, 130, 220))
    for k in range(3):
        d.rounded_rectangle((cx - 70 * s, cy - 130 * s + k * 70 * s, cx + (40 - k * 20) * s, cy - 92 * s + k * 70 * s), int(14 * s), fill=WHITE if k % 2 else GOLD)


ICONS = {"jar": icon_jar, "chai": icon_chai, "plane": icon_plane, "coin": icon_coin, "shop": icon_shop,
         "chip": icon_chip, "robot": icon_robot, "globe": icon_globe, "phone": icon_phone}


def wrap(d, s, font, maxw, max_lines=3):
    """Greedy word wrap; returns lines (last one ellipsised if it overflows)."""
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]; lines[-1] = lines[-1].rstrip(".,") + "…"
    return lines


# =====================================================================  timing
def _norm(w):
    return re.sub(r"[\s\"'“”‘’.,!?।:;…()\-–—]+", "", w).replace("़", "").lower()


class Timeline:
    def __init__(self, words, duration):
        self.words = words; self.duration = duration
        self.norm = [_norm(w) for w, _, _ in words]

    def at(self, phrase, after=0.0):
        """Start time of the first occurrence of `phrase` (spoken words) at or after `after`."""
        if phrase is None: return None
        if isinstance(phrase, (int, float)): return float(phrase)
        toks = [_norm(x) for x in str(phrase).split() if _norm(x)]
        if not toks: return None
        n = len(toks)
        for i in range(len(self.words)):
            if self.words[i][1] + 1e-3 < after: continue
            if self.norm[i:i + n] == toks:
                return self.words[i][1]
        for i in range(len(self.words)):  # fuzzy: first token only
            if self.words[i][1] + 1e-3 >= after and self.norm[i] == toks[0]:
                return self.words[i][1]
        return None


# =====================================================================  background / mascot
def make_bg(tint=(0, 0, 0)):
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    d1 = np.sqrt(((x - 540) / 620) ** 2 + ((y - 1250) / 760) ** 2)
    spot = np.clip(1 - d1, 0, 1) ** 1.6
    base = np.stack([20 + 46 * spot, 16 + 30 * spot, 24 + 18 * spot], -1) + np.array(tint, np.float32)
    vig = np.clip(1.15 - np.sqrt(((x - 540) / 700) ** 2 + ((y - 960) / 1100) ** 2) * 0.55, 0.35, 1)
    return Image.fromarray(np.clip(base * vig[..., None], 0, 255).astype(np.uint8)).convert("RGBA")


BGS = {"warm": make_bg(), "cold": make_bg((-6, 4, 26)), "red": make_bg((26, -4, -6)), "green": make_bg((-6, 16, -2))}
_rng = np.random.default_rng(3)
GRAIN = [Image.fromarray(_rng.normal(128, 22, (HEIGHT // 2, WIDTH // 2)).clip(0, 255).astype(np.uint8)).resize((WIDTH, HEIGHT)) for _ in range(6)]
PARTICLES = [(_rng.uniform(0, WIDTH), _rng.uniform(0, HEIGHT), _rng.uniform(1.5, 4), _rng.uniform(8, 30), _rng.uniform(0, 6.28)) for _ in range(46)]

MASCOT_W = 920


@functools.lru_cache(None)
def mascot(expr, mouth, eyes, arm, width=MASCOT_W):
    png = cairosvg.svg2png(bytestring=rohan(expr=expr, mouth=mouth, eyes=eyes, arm=arm).encode(), output_width=width)
    return Image.open(io.BytesIO(png)).convert("RGBA")


VOWEL = {"ा": "A", "आ": "A", "अ": "A", "ि": "E", "ी": "E", "े": "E", "ै": "E", "इ": "E", "ई": "E", "ए": "E",
         "ो": "O", "ौ": "O", "ु": "O", "ू": "O", "उ": "O", "ऊ": "O", "ओ": "O", "ं": "MBP", "म": "MBP", "ब": "MBP", "प": "MBP", "भ": "MBP",
         "a": "A", "e": "E", "i": "E", "o": "O", "u": "O", "m": "MBP", "b": "MBP", "p": "MBP"}
MOOD_REST = {"neutral": "smile", "smirk": "smirk", "shocked": "O", "serious": "closed"}


# =====================================================================  "panel" style
# Minimal dark explainer look: category tag + episode number on top, a bold two-line hook with an accent word,
# the visual inside a framed glowing panel, a small mascot in the bottom-right corner, wordmark at the bottom.
STYLE = (os.environ.get("RENDER_STYLE") or "modern").lower()    # "modern" (default), "panel" or "classic" (Paisa Decode look)
ACCENT = {"warm": GOLD, "cold": BLUE, "red": RED, "green": GREEN}
PANEL = (64, 470, 1016, 1330)                                    # x0, y0, x1, y1
CARD_CROP = (0, 80, 1080, 1000)                                  # region of a classic card that goes into the panel
SMALL_W = 330                                                    # corner mascot width
PANEL_BG = (9, 9, 12)


def _panel_bg(accent):
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    lift = np.clip(1 - np.sqrt(((x - 540) / 900) ** 2 + ((y - 900) / 1000) ** 2), 0, 1) ** 2
    base = np.stack([PANEL_BG[0] + 10 * lift, PANEL_BG[1] + 10 * lift, PANEL_BG[2] + 14 * lift], -1)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGBA")
    # soft accent glow behind the panel
    from PIL import ImageFilter
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    x0, y0, x1, y1 = PANEL
    gd.rounded_rectangle((x0 + 30, y0 + 40, x1 - 30, y1 - 10), 60, fill=accent + (38,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(PANEL, 38, fill=(15, 15, 19), outline=(58, 58, 68), width=3)
    d.rounded_rectangle((x0 + 3, y0 + 3, x1 - 3, y0 + 6), 2, fill=accent + (90,))     # thin lit edge on top
    return img


PANEL_BGS = {k: _panel_bg(v) for k, v in ACCENT.items()}


def _accent_line(d, xy, s, font, base, accent):
    """Draw a line where *starred words* are in the accent colour (centred)."""
    parts = re.split(r"(\*[^*]+\*)", s)
    segs = [(p.strip("*"), accent if p.startswith("*") else base) for p in parts if p]
    total = sum(d.textlength(t, font=font) for t, _ in segs)
    x = xy[0] - total / 2
    for t_, c in segs:
        d.text((x, xy[1]), t_, font=font, fill=c, anchor="lm")
        x += d.textlength(t_, font=font)


# =====================================================================  the renderer
class Reel:
    def __init__(self, plan, words, duration):
        self.plan = plan; self.words = words; self.duration = duration
        self.tl = Timeline(words, duration)
        self.open = plan.get("cold_open", [])
        self.open_end = 0.0
        if self.open:
            # the cold open ends right before the first word after the last open line
            last = self.open[-1].get("at", "")
            st = self.tl.at(last) or 0.0
            n = max(1, len([x for x in str(last).split() if _norm(x)]))
            idx = next((i for i, w in enumerate(words) if abs(w[1] - st) < 1e-6), 0)
            after = idx + n
            self.open_end = (words[after][1] - 0.1) if after < len(words) else words[-1][2] + 0.2
        # resolve scenes
        self.scenes = []
        prev = self.open_end
        for sc in plan["scenes"]:
            st = self.tl.at(sc.get("at"), after=max(0, prev - 0.3))
            if st is None: st = prev + 0.5
            st = max(st, prev + 0.05)
            self.scenes.append(dict(sc, _t=st)); prev = st
        for i, sc in enumerate(self.scenes):
            sc["_end"] = self.scenes[i + 1]["_t"] if i + 1 < len(self.scenes) else duration + 1
            sc["_resolved"] = self._resolve(sc.get("card", {}), sc["_t"])
        self.cuts = [self.open_end] + [s["_t"] for s in self.scenes[1:]]
        # mood beats
        self.moods = []
        for sc in self.scenes:
            self.moods.append((sc["_t"], sc.get("mood", "neutral"), bool(sc.get("point"))))
            for b in sc.get("beats", []):
                bt = self.tl.at(b.get("at"), after=sc["_t"] - 0.1)
                if bt is not None: self.moods.append((bt, b.get("mood", "neutral"), bool(b.get("point", sc.get("point")))))
        self.moods.sort()
        # caption chunks
        self.chunks, cur = [], []
        for i, (w, s, e) in enumerate(words):
            cur.append(i)
            nxt = words[i + 1][1] if i + 1 < len(words) else 1e9
            if len(cur) >= 3 or w.endswith(("।", "?", ",", ".", "...", "\"", ":", "!")) or nxt - e > 0.35:
                self.chunks.append(cur); cur = []
        if cur: self.chunks.append(cur)

    # every "*_at" / "at" key inside a card becomes an absolute time
    def _resolve(self, obj, after):
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if k == "at" or k.endswith("_at"):
                    out[k] = self.tl.at(v, after=after - 0.2)
                    if out[k] is None: out[k] = after + 0.3
                else:
                    out[k] = self._resolve(v, after)
            return out
        if isinstance(obj, list):
            return [self._resolve(x, after) for x in obj]
        return obj

    # ------------------------------------------------------------- mouth / mood
    def viseme(self, t):
        for w, s, e in self.words:
            if s <= t < e:
                shapes = [VOWEL[c] for c in w.lower() if c in VOWEL] or ["A"]
                seq = []
                for sh in shapes: seq += [sh, "A" if sh == "MBP" else sh]
                i = int((t - s) / max(e - s, 1e-3) * len(seq))
                return seq[min(i, len(seq) - 1)]
        return None

    def mood(self, t):
        cur = (0, "neutral", False)
        for m in self.moods:
            if t >= m[0]: cur = m
        return cur

    # ------------------------------------------------------------- cards
    def card(self, img, sc, t):
        c = sc["_resolved"]; typ = c.get("type", "headline")
        d = ImageDraw.Draw(img)
        t0 = sc["_t"]
        if c.get("icon") in ICONS and typ not in ("cta",):
            a = ease_out((t - t0) / 0.45)
            ICONS[c["icon"]](d, 540, 420 - (1 - a) * 300, 1.2)
        if typ == "news":
            # breaking-news style: tag strip, wrapped headline, source chip
            tag = c.get("tag") or "AI NEWS"
            ta = c.get("tag_at", t0)
            if ta is not None and t >= ta:
                p = ease_out((t - ta) / 0.35)
                lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
                ft = fit_font(ld, tag, "latin", 54, 700)
                tw = ld.textlength(tag, font=ft) + 80
                x0 = 540 - tw / 2; x1 = x0 + tw * p
                ld.rectangle((x0, 108, x1, 196), fill=col(c.get("tag_color"), RED) + (255,))
                ld.rectangle((x0, 196, x1, 206), fill=GOLD + (255,))
                if p > 0.7: text(ld, (540, 154), tag, ft, WHITE)
                img.alpha_composite(lay)
            ha = c.get("at", t0)
            if ha is not None and t >= ha:
                lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
                ft = F("bold", 96); lines = wrap(ld, c.get("title", ""), ft, 960, 3)
                if any(ld.textlength(l, font=ft) > 960 for l in lines): ft = F("bold", 80); lines = wrap(ld, c.get("title", ""), ft, 960, 3)
                for k, ln in enumerate(lines):
                    lt = ha + k * 0.12
                    if t < lt: continue
                    a = ease_out((t - lt) / 0.3)
                    text(ld, (540 - (1 - a) * 60, 330 + k * 118), ln, ft, col(c.get("color"), WHITE) + (int(255 * a),), stroke=7)
                img.alpha_composite(lay)
            chip(img, 540, 330 + 3 * 118 + 40, c.get("source", ""), INK, col(c.get("source_color"), GOLD), c.get("source_at"), t, size=50, maxw=900)
        elif typ == "headline":
            pop_text(img, (540, 300 if not c.get("icon") else 680), c.get("title", ""), "bold", 110, col(c.get("color"), WHITE), c.get("at", t0), t, stroke=8)
            pop_text(img, (540, 470 if not c.get("icon") else 800), c.get("sub", ""), "bold", 80, col(c.get("sub_color"), GOLD), c.get("sub_at"), t)
        elif typ == "big_number":
            if c.get("label"): text(d, (540, 200), c["label"], fit_font(d, c["label"], "bold", 76, 960), WHITE, stroke=6)
            pop_text(img, (540, 470), c.get("value", ""), "latin", 260, col(c.get("color"), GOLD), c.get("value_at", t0), t, stroke=12, dur=0.4)
            pop_text(img, (540, 720), c.get("note", ""), "bold", 68, WHITE, c.get("note_at"), t)
        elif typ == "split":
            pop_text(img, (540, 160), c.get("title", ""), "bold", 76, WHITE, c.get("title_at", t0), t)
            L, R = c.get("left", {}), c.get("right", {})
            cy = 700 if c.get("icon") else 420
            chip(img, 290, cy, L.get("text", ""), INK, col(L.get("color"), BLUE), L.get("at"), t, minw=380, maxw=500)
            chip(img, 790, cy, R.get("text", ""), INK, col(R.get("color"), GOLD), R.get("at"), t, minw=380, maxw=500)
            if L.get("at") is not None and t >= L["at"]: text(d, (540, cy), "vs", F("latin", 56), MUTED)
            pop_text(img, (540, cy + 220 if cy == 420 else 860), c.get("result", ""), "bold", 84, col(c.get("result_color"), GREEN), c.get("result_at"), t, stroke=8)
        elif typ == "counter":
            if c.get("label"): text(d, (540, 300), c["label"], fit_font(d, c["label"], "semi", 64, 960), MUTED)
            at = c.get("at", t0)
            p = ease_out((t - at) / 0.9) if t >= at else 0
            to = float(c.get("to", 0)); v = to * p
            s = c.get("prefix", "") + western(v, to) + c.get("suffix", "")
            text(d, (540, 470), s, fit_font(d, s, "latin", 140, 980), GOLD, stroke=8)
            chip(img, 540, 680, c.get("done_text", ""), INK, GREEN, c.get("done_at"), t)
        elif typ == "percent":
            at = c.get("at", t0); v = int(min(1, max(0, (t - at + 1.0) / 1.0)) * float(c.get("value", 0)))
            a = ease_out((t - t0) / 0.4)
            icon_calc(d, 540, 420 - (1 - a) * 300, 1.1, f"{v}%")
            pop_text(img, (540, 760), c.get("label", ""), "bold", 92, GOLD, c.get("label_at", at), t)
        elif typ == "compare_arrow":
            pop_text(img, (540, 170), c.get("title", ""), "bold", 72, MUTED, c.get("title_at", t0), t)
            chip(img, 270, 420, c.get("from_text", ""), INK, BLUE, c.get("from_at"), t, size=80, minw=360, maxw=470)
            ta = c.get("to_at")
            if ta is not None and t >= ta - 0.5:
                p = ease_out((t - (ta - 0.5)) / 0.45)
                d.line((480, 420, 480 + 120 * p, 420), fill=GOLD, width=14)
                if p > 0.9: d.polygon([(600, 395), (640, 420), (600, 445)], fill=GOLD)
            chip(img, 820, 420, c.get("to_text", ""), INK, GOLD, ta, t, size=86, minw=300, maxw=400)
            pop_text(img, (540, 660), c.get("result", ""), "bold", 88, GREEN, c.get("result_at"), t, stroke=8)
        elif typ == "strike_list":
            pop_text(img, (540, 170), c.get("title", ""), "bold", 88, col(c.get("color"), WHITE), c.get("title_at", t0), t)
            items = c.get("items", [])[:4]
            for k, it in enumerate(items):
                y = 340 + k * 135; at = it.get("at")
                if at is None: continue
                pop_text(img, (540, y), it.get("text", ""), "bold", 90, WHITE, at - 0.25, t, maxw=860)
                if it.get("strike", True):
                    strike(d, 280, y + 4, 800, y + 4, (t - at) / 0.25, c=GOLD, w=10)
        elif typ == "checklist":
            text(d, (540, 150), c.get("title", ""), fit_font(d, c.get("title", ""), "disp", 96, 960), GOLD)
            for k, it in enumerate(c.get("items", [])[:4]):
                at = it.get("at")
                if at is None or t < at: continue
                a = ease_out((t - at) / 0.3)
                s = f"{k + 1}. {it.get('text', '')}"
                text(d, (90 - (1 - a) * 80, 300 + k * 125), s, fit_font(d, s, "bold", 72, 900), WHITE, anchor="lm", stroke=6)
            chip(img, 540, 800, c.get("final", ""), INK, GREEN, c.get("final_at"), t, size=74)
        elif typ == "warning":
            sh = 10 * math.sin(t * 60) * max(0, 1 - (t - t0) * 3)
            pop_text(img, (540 + sh, 170), c.get("title", ""), "bold", 84, RED, c.get("title_at", t0), t, stroke=6)
            pop_text(img, (540, 320), c.get("sub", ""), "bold", 80, WHITE, c.get("sub_at", t0 + 0.2), t)
            for k, it in enumerate(c.get("chips", [])[:3]):
                chip(img, [270, 810, 540][k], [520, 520, 660][k], it.get("text", ""), INK, col(it.get("color"), BLUE), it.get("at"), t, size=62, maxw=500)
            pop_text(img, (540, 800), c.get("big", ""), "latin", 130, col(c.get("big_color"), RED), c.get("big_at"), t, stroke=8)
        elif typ == "money_rain":
            for i in range(14):
                ph = (t * 1.4 + i * 0.37) % 1.0
                x = 120 + (i * 137) % 860; y = -80 + ph * 900
                note = Image.new("RGBA", (190, 90), (0, 0, 0, 0)); nd = ImageDraw.Draw(note)
                nd.rounded_rectangle((0, 0, 189, 89), 12, fill=(120, 185, 110), outline=INK, width=4)
                text(nd, (95, 45), str(c.get("symbol") or CURRENCY)[:3], fit_font(nd, str(c.get("symbol") or CURRENCY)[:3], "latin", 56, 160), (40, 80, 40))
                img.alpha_composite(note.rotate((i * 31 + t * 60) % 360, expand=True), (int(x), int(y)))
            pop_text(img, (540, 420), c.get("line1", ""), "bold", 130, WHITE, c.get("line1_at", t0), t, stroke=10)
            pop_text(img, (540, 580), c.get("line2", ""), "bold", 130, GOLD, c.get("line2_at"), t, stroke=10)
        elif typ == "title_slam":
            sh = 10 * math.sin(t * 60) * max(0, 1 - (t - (c.get("at") or t0)) * 3)
            pop_text(img, (540 + sh, 430), c.get("title", ""), "disp", 220, col(c.get("color"), RED), c.get("at", t0), t, stroke=10)
        elif typ == "cta":
            a = ease_out((t - t0) / 0.4)
            icon_plane(d, 540 + (1 - a) * -500 + 20 * math.sin(t * 4), 280, 1.3)
            pop_text(img, (540, 520), c.get("line1", ""), "bold", 100, WHITE, c.get("line1_at", t0 + 0.2), t, stroke=8)
            pop_text(img, (540, 660), c.get("line2", ""), "bold", 62, GOLD, c.get("line2_at"), t, stroke=6)
            if t >= t0 + 0.8:  # follow tag under the share line
                chip(img, 540, 800, f"Follow {HANDLE}", INK, GOLD, t0 + 0.8, t, size=52)

    # ------------------------------------------------------------- cold open
    def cold_open(self, img, t):
        d = ImageDraw.Draw(img)
        n = len(self.open[:3]); y0 = 900 - (n - 1) * 85
        for k, ln in enumerate(self.open[:3]):
            t0 = self.tl.at(ln.get("at")) if ln.get("at") is not None else k * 1.5
            if t0 is None or t < t0: continue
            s = ln.get("text", "")
            m = int(len(s) * min(1, (t - t0) / 0.45)) or 1
            while m < len(s) and ("ा" <= s[m] <= "्" or s[m] in "ंँ़"):
                m += 1
            f = fit_font(d, s, "disp", 128, 960)
            text(d, (540, y0 + k * 170), s[:m], f, col(ln.get("color"), WHITE if k < n - 1 else GOLD), stroke=4)
        if t > 0.5:
            text(d, (540, 1350), HANDLE.upper(), F("latin", 34), (120, 110, 100))

    # ------------------------------------------------------------- captions
    def captions(self, img, t, y=1770, cx=WIDTH / 2, maxw=980, size=104):
        if t < self.open_end + 0.05: return
        for ch in self.chunks:
            s = self.words[ch[0]][1]; e = self.words[ch[-1]][2] + 0.25
            if s - 0.05 <= t < e: break
        else:
            return
        d = ImageDraw.Draw(img)
        ws = [self.words[i][0].strip("\"“”") for i in ch]
        f = F("bold", size)
        widths = [d.textlength(w, font=f) for w in ws]; gap = 26
        total = sum(widths) + gap * (len(ws) - 1)
        if total > maxw:
            f = F("bold", size * maxw / total); widths = [d.textlength(w, font=f) for w in ws]
            total = sum(widths) + gap * (len(ws) - 1)
        x = cx - total / 2
        pill = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle((x - 30, y - size * 0.75, x + total + 30, y + size * 0.71), 36, fill=(10, 8, 12, 150))
        img.alpha_composite(pill)
        for i, w, wd in zip(ch, ws, widths):
            active = self.words[i][1] <= t < self.words[i][2] + 0.08
            text(d, (x + wd / 2, y - (10 if active else 0)), w, f, GOLD if active else WHITE, stroke=8)
            x += wd + gap

    # ------------------------------------------------------------- panel style
    def panel_frame(self, sc, t):
        tint = (sc or {}).get("tint", "warm"); acc = ACCENT.get(tint, GOLD)
        img = PANEL_BGS.get(tint, PANEL_BGS["warm"]).copy()
        # drifting dots
        over = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0)); od = ImageDraw.Draw(over)
        for x, y, r, sp, ph in PARTICLES[:28]:
            yy = (y - t * sp * 0.6) % HEIGHT; xx = x + 12 * math.sin(t * 0.5 + ph)
            od.ellipse((xx - r * 0.7, yy - r * 0.7, xx + r * 0.7, yy + r * 0.7), fill=acc + (max(0, int(40 + 50 * math.sin(t * 1.3 + ph))),))
        img.alpha_composite(over)
        self.header(img, t, acc)
        # the card, drawn on its own layer and fitted into the panel
        if sc:
            lay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            self.card(lay, sc, t)
            crop = lay.crop(CARD_CROP)
            x0, y0, x1, y1 = PANEL
            sc_ = min((x1 - x0 - 30) / crop.width, (y1 - y0 - 40) / crop.height)
            crop = crop.resize((int(crop.width * sc_), int(crop.height * sc_)), Image.LANCZOS)
            img.alpha_composite(crop, (int((x0 + x1 - crop.width) / 2), int(y0 + 24)))
        # corner mascot
        _, md, point = self.mood(t)
        v = self.viseme(t)
        ph = (t + 0.7) % 3.4
        m = mascot(md, v or MOOD_REST.get(md, "closed"), "blink" if ph < 0.12 else None, "point" if point else "down", SMALL_W)
        rise = ease_out((t - self.open_end) / 0.5)
        bob = 4 * math.sin(t * 2.2) + (3 if v else 0) * math.sin(t * 17)
        mh = m.height
        img.alpha_composite(m, (WIDTH - SMALL_W - 26, int(PANEL[3] - mh * 0.42 + (1 - rise) * 600 + bob)))
        self.captions(img, t, y=1520, cx=410, maxw=700, size=78)
        # wordmark
        d = ImageDraw.Draw(img)
        text(d, (540, 1850), HANDLE, F("latin", 40), WHITE + (235,))
        return img

    def header(self, img, t, acc):
        d = ImageDraw.Draw(img)
        p = self.plan
        tag = (p.get("series_tag") or "AI NEWS").upper()[:18]
        f = F("latin", 30)
        tw = d.textlength(tag, font=f)
        d.rounded_rectangle((60, 80, 60 + tw + 92, 140), 14, fill=(26, 26, 32), outline=(62, 62, 72), width=2)
        d.rounded_rectangle((78, 96, 106, 124), 7, fill=acc)
        text(d, (122, 111), tag, f, (220, 218, 226), anchor="lm")
        ep = p.get("episode")
        right = 1020
        if p.get("part"):
            pt = f"PART {p['part']}"; pw = d.textlength(pt, font=f) + 36
            d.rounded_rectangle((right - pw, 84, right, 136), 10, fill=GOLD); text(d, (right - pw / 2, 111), pt, f, INK)
            right -= pw + 18
        if ep:
            text(d, (right, 111), f"EP {ep}", f, acc, anchor="rm")
        l1 = p.get("title_line1") or ""; l2 = p.get("title_line2") or ""
        if l1 or l2:
            a = ease_out((t - self.open_end) / 0.45)
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
            ft = F("latin", 84)
            for s_ in (l1, l2):
                w = ld.textlength(s_.replace("*", ""), font=ft)
                if w > 960: ft = F("latin", 84 * 960 / w)
            _accent_line(ld, (540, 252 - (1 - a) * 30), l1, ft, WHITE + (int(255 * a),), acc + (int(255 * a),))
            _accent_line(ld, (540, 360 - (1 - a) * 30), l2, ft, WHITE + (int(255 * a),), acc + (int(255 * a),))
            img.alpha_composite(lay)

    # ------------------------------------------------------------- frame
    def frame(self, i):
        t = i / FPS
        cold = t < self.open_end
        sc = None
        for s in self.scenes:
            if s["_t"] <= t < s["_end"]: sc = s
        tint = (sc or {}).get("tint", "warm")
        img = Image.new("RGBA", (WIDTH, HEIGHT), (6, 5, 8, 255)) if cold else BGS.get(tint, BGS["warm"]).copy()
        if not cold and STYLE == "panel":
            img = self.panel_frame(sc, t)
        elif cold:
            self.cold_open(img, t)
        else:
            over = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0)); od = ImageDraw.Draw(over)
            for x, y, r, sp, ph in PARTICLES:
                yy = (y - t * sp) % HEIGHT; xx = x + 18 * math.sin(t * 0.6 + ph)
                od.ellipse((xx - r, yy - r, xx + r, yy + r), fill=GOLD + (max(0, int(90 + 80 * math.sin(t * 1.3 + ph))),))
            img.alpha_composite(over)
            _, md, point = self.mood(t)
            v = self.viseme(t)
            ph = (t + 0.7) % 3.4
            m = mascot(md, v or MOOD_REST.get(md, "closed"), "blink" if ph < 0.12 else None, "point" if point else "down")
            rise = ease_out((t - self.open_end) / 0.5)
            bob = 6 * math.sin(t * 2.2) + (4 if v else 0) * math.sin(t * 17)
            img.alpha_composite(m, ((WIDTH - MASCOT_W) // 2, int(860 + (1 - rise) * 700 + bob)))
            if sc: self.card(img, sc, t)
            self.captions(img, t)
            text(ImageDraw.Draw(img), (60, 70), HANDLE, F("latin", 30), GOLD + (210,), anchor="lm")
        z = 1.0
        for p in self.cuts:
            if p <= t < p + 0.3: z = 1 + 0.07 * (1 - (t - p) / 0.3)
        if cold and self.open_end > 0: z = 1.0 + 0.04 * (t / self.open_end)
        if z != 1.0:
            w2, h2 = int(WIDTH / z), int(HEIGHT / z)
            img = img.crop(((WIDTH - w2) // 2, (HEIGHT - h2) // 2, (WIDTH + w2) // 2, (HEIGHT + h2) // 2)).resize((WIDTH, HEIGHT), Image.BILINEAR)
        for p in self.cuts[1:]:
            if p <= t < p + 0.1:
                img.alpha_composite(Image.new("RGBA", img.size, (255, 240, 210, int(110 * (1 - (t - p) / 0.1)))))
        lb = 0
        if t < self.open_end: lb = 230
        elif t < self.open_end + 0.55: lb = int(230 * (1 - ease_out((t - self.open_end) / 0.55)))
        rgb = img.convert("RGB")
        if lb:
            dd = ImageDraw.Draw(rgb); dd.rectangle((0, 0, WIDTH, lb), fill=(0, 0, 0)); dd.rectangle((0, HEIGHT - lb, WIDTH, HEIGHT), fill=(0, 0, 0))
        g = GRAIN[i % len(GRAIN)]
        rgb = Image.blend(rgb, Image.merge("RGB", (g, g, g)), 0.06)
        if t > self.duration + 0.3:
            rgb = Image.blend(rgb, Image.new("RGB", rgb.size, (0, 0, 0)), min(1, (t - self.duration - 0.3) / 0.5))
        return rgb.tobytes()

    def sfx_cues(self):
        """Times for the sound designer: cuts, number pops and slams."""
        pops = []
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if (k == "at" or k.endswith("_at")) and isinstance(v, (int, float)): pops.append(v)
                    else: walk(v)
            elif isinstance(o, list):
                for x in o: walk(x)
        for s in self.scenes: walk(s["_resolved"])
        opens = [self.tl.at(l.get("at")) for l in self.open[:3]]
        return {"open_lines": [x for x in opens if x is not None], "open_end": self.open_end,
                "cuts": self.cuts[1:], "pops": sorted(set(round(p, 2) for p in pops)), "duration": self.duration}


_REEL = None


def make_reel(plan, words, duration):
    if STYLE == "modern":
        from modern import ModernReel
        return ModernReel(plan, words, duration)
    return Reel(plan, words, duration)


def _init(plan, words, duration):
    global _REEL; _REEL = make_reel(plan, words, duration)
def _frame(i): return _REEL.frame(i)


def western(v, to):
    v = int(round(v))
    return str(v) if abs(to) < 1000 else f"{v:,}"


def indian(v, to):
    v = int(round(v))
    if abs(to) < 1000: return str(v)
    s = str(v)
    if len(s) <= 3: return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2: parts.insert(0, head[-2:]); head = head[:-2]
    if head: parts.insert(0, head)
    return ",".join(parts + [tail])


def render(plan, words, duration, out_path, workers=None):
    reel = make_reel(plan, words, duration)
    n = int(math.ceil((duration + 0.9) * FPS))
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS),
                           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", out_path], stdin=subprocess.PIPE)
    with Pool(workers or os.cpu_count() or 2, initializer=_init, initargs=(plan, words, duration)) as pool:
        for k, b in enumerate(pool.imap(_frame, range(n), chunksize=8)):
            ff.stdin.write(b)
            if k % 300 == 0: print(f"  frame {k}/{n}", flush=True)
    ff.stdin.close()
    if ff.wait() != 0: raise RuntimeError("ffmpeg encode failed")
    return reel.sfx_cues()


def preview(plan, words, duration, times, out_dir):
    reel = make_reel(plan, words, duration)
    os.makedirs(out_dir, exist_ok=True)
    for t in times:
        Image.frombytes("RGB", (WIDTH, HEIGHT), reel.frame(int(t * FPS))).save(os.path.join(out_dir, f"t{t:05.1f}.png"))
    return reel
