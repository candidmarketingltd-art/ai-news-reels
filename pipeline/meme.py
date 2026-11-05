"""Text-on-B-roll reels: one relatable meme / quote line over a B-roll clip, posted with a trending song.

The format (the "POV / me when / quote over aesthetic footage" reels that rack up replays and shares):
  - 6–8 s, loops cleanly, so most viewers watch it 2–3 times
  - one line of text in Instagram's own look (black on a white box for memes, white with a soft shadow for quotes),
    sitting in the upper third so the footage still reads
  - the footage does half the joke (a man staring at his laptop + "claude after I say 'make it pop'")
  - the SOUND is a currently trending Instagram audio — that's what pushes these to new viewers. Instagram only lets you
    attach its music library inside the app, so these go out as a Buffer *reminder*: you get a notification, the video and
    caption are ready, you pick the suggested song in the app and post (~30 seconds). The song suggestion comes in the
    reminder note at the top of the caption (marked to delete) and in logs/meme_runs.csv.
"""
import datetime as dt, json, os, random, re, subprocess, textwrap
from pathlib import Path

from pipeline import broll
from pipeline.script_writer import _ask_json, SCRIPT_MODEL

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "remotion_editorial" / "public" / "fonts"
W, H = 1080, 1920


def _research():
    """What's trending this week: Instagram audio lists + Claude/AI news worth riffing on."""
    import anthropic
    sysp = ("You prepare an Instagram meme reel for @ihackgrowth (business, marketing, tech, vibe coding, AI tools — audience: founders, devs, marketers, "
            "freelancers who use Claude/ChatGPT at work). Use web search for (1) this week's trending Instagram Reels audio lists "
            "(SocialPilot, Later, Metricool, Buffer, Hootsuite publish weekly lists) and (2) what tech / startup / vibe-coding / AI-tools "
            "people are joking about this week (launches, outages, viral takes, new lingo). Return ONLY JSON: "
            '{"songs": [{"title", "artist", "mood": "funny|chill|dramatic|hype|sad|wholesome", "trend": "how creators use it, one line", '
            '"source": "url", "list_date": "date of the list"}], "news": ["one-line fact with source url"]}. 8–15 songs, only from lists '
            "dated within the last 3 weeks; never invent a song.")
    client = anthropic.Anthropic()
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]
    user = f"Today is {dt.date.today()}. Research and return the JSON."
    msgs = [{"role": "user", "content": user}]
    for _ in range(4):
        resp = client.messages.create(model=SCRIPT_MODEL, max_tokens=8000, system=sysp, messages=msgs, tools=tools)
        if resp.stop_reason != "pause_turn": break
        msgs = [{"role": "user", "content": user}, {"role": "assistant", "content": resp.content}]
    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    try:
        return json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    except Exception:
        return _ask_json(SCRIPT_MODEL, "Convert into one valid JSON object, keep everything, add nothing.", raw[-20000:], lambda d: None, attempts=2)


def write(recent, clips, trend):
    sysp = (ROOT / "prompts" / "meme_writer.md").read_text(encoding="utf-8")
    lib = "\n".join(f"- {c['id']}: {c['desc'][:220]}" for c in clips)
    user = (f"RECENT MEME REELS (don't repeat the joke or the clip):\n" + ("\n".join(f"- {r}" for r in recent) or "- none") +
            f"\n\nB-ROLL CLIPS:\n{lib}\n\nTRENDING THIS WEEK:\n{json.dumps(trend, ensure_ascii=False)[:6000]}\n\nReturn only the JSON.")
    ids = {c["id"] for c in clips}
    songs = {(s.get("title") or "").lower() for s in trend.get("songs", [])}

    def check(d):
        shots = d.get("shots") or []
        if not 1 <= len(shots) <= 3: raise ValueError("shots: 1–3")
        for sh in shots:
            if sh.get("clip") not in ids: raise ValueError("every shot's clip must be one of the B-ROLL CLIPS ids")
            if not sh.get("text") or len(sh["text"].split()) > 16: raise ValueError("each shot's text: 1–16 words")
        if sum(float(sh.get("seconds") or 0) for sh in shots) > 9.5: raise ValueError("total under 9.5 s")
        d["text"] = " / ".join(sh["text"] for sh in shots); d["clip"] = ",".join(sh["clip"] for sh in shots)
        if d.get("style") not in ("meme", "quote"): raise ValueError("style: meme or quote")
        s = (d.get("song") or {}).get("title", "").lower()
        if songs and s not in songs: raise ValueError("song must be one of the TRENDING songs, title exactly as listed")
        used = [r.split("· song:")[-1].strip().lower() for r in recent[-6:] if "· song:" in r]
        if s in used and len(songs - set(used)) > 2: raise ValueError("that song was used in the last few meme reels — pick a different trending song")
        if not d.get("caption"): raise ValueError("caption missing")
    return _ask_json(SCRIPT_MODEL, sysp, user, check)


def _font(name, size):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / name), size)


def _faces(clip, seconds):
    """Union of face boxes (in the 1080x1920 cover-cropped frame) over a few frames of the clip; None if no face."""
    import cv2
    cap = cv2.VideoCapture(clip)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
    det = [cv2.CascadeClassifier(str(ROOT / "pipeline" / "models" / f)) for f in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")]
    boxes = []
    for k in (0.1, 0.3, 0.5, 0.7, 0.9):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * k * min(1, seconds * 30 / n)))
        ok, fr = cap.read()
        if not ok: continue
        h, w = fr.shape[:2]
        sc = max(W / w, H / h); ox, oy = (w * sc - W) / 2, (h * sc - H) / 2
        g = cv2.equalizeHist(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY))
        found = []
        for d in det:   # frontal first; profile only if no frontal face
            found = list(d.detectMultiScale(g, 1.1, 8, minSize=(int(w * 0.1), int(w * 0.1))))
            if found: break
        if not found: continue
        x, y, fw, fh = max(found, key=lambda r: r[2] * r[3])   # the main face only
        boxes.append((x * sc - ox - fw * sc * 0.2, y * sc - oy - fh * sc * 0.5, (x + fw) * sc - ox + fw * sc * 0.2, (y + fh) * sc - oy + fh * sc * 0.3))
    box = None
    if boxes:
        import statistics as st
        box = tuple(st.median(b[i] for b in boxes) for i in range(4))
    cap.release()
    return box


SAFE_TOP, SAFE_BOTTOM = 230, H - 430   # keep clear of Instagram's top bar and the caption/buttons at the bottom


def _place(block_h, face):
    """Top y for a text block: in the free band above or below the head, never over it."""
    if not face: return int(H * 0.17)
    above = (SAFE_TOP, face[1] - 40)
    below = (face[3] + 40, SAFE_BOTTOM)
    for lo, hi in (above, below):
        if hi - lo >= block_h: return int(lo if (lo, hi) == above else lo + min(60, (hi - lo - block_h) / 3))
    lo, hi = max(above, below, key=lambda r: r[1] - r[0])   # tight: biggest band, may touch the hairline, never the eyes
    return int(max(SAFE_TOP, min(lo, hi - block_h)))


def _overlay(text, style, png, face):
    """Edits-template look: small clean Instagram-style text in the empty part of the frame."""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if style == "meme":
        f, lh, wrap = _font("Inter-Medium.ttf", 44), 62, 34
    else:
        f, lh, wrap = _font("Inter-Bold.ttf", 50), 66, 28
    lines = textwrap.wrap(text, wrap)
    y0 = _place(len(lines) * lh, face)
    if style == "meme":
        for i, ln in enumerate(lines):
            l, t, r, b = d.textbbox((0, 0), ln, font=f)
            x = (W - (r - l)) // 2; y = y0 + i * lh
            d.rounded_rectangle((x - 20, y - 8, x + (r - l) + 20, y + lh - 6), radius=14, fill=(255, 255, 255, 245))
            d.text((x, y - t + 6), ln, font=f, fill=(0, 0, 0, 255))
    else:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        for i, ln in enumerate(lines):
            w = d.textlength(ln, font=f); sd.text(((W - w) / 2, y0 + i * lh + 3), ln, font=f, fill=(0, 0, 0, 210))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(8))); d = ImageDraw.Draw(im)
        for i, ln in enumerate(lines):
            w = d.textlength(ln, font=f); d.text(((W - w) / 2, y0 + i * lh), ln, font=f, fill=(255, 255, 255, 255))
    im.save(png)


def _segment(clip, text, style, dur, out, workdir, k):
    png = os.path.join(workdir, f"meme_text_{k}.png")
    try:
        face = _faces(clip, dur)
    except Exception as e:   # no detector: assume a centred head and keep text in the lower third
        print(f"      (face check skipped: {str(e)[:100]})", flush=True); face = (200, 150, 880, 1150)
    _overlay(text, style, png, face)
    dark = "eq=brightness=-0.06:saturation=0.92," if style == "quote" else ""
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},{dark}fps=30,trim=0:{dur},setpts=PTS-STARTPTS,"
          f"zoompan=z='min(1.0+0.0008*on,1.06)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps=30[v];"
          f"[1:v]format=rgba,fade=t=in:st=0.12:d=0.18:alpha=1[t];[v][t]overlay=0:0:shortest=1,format=yuv420p[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", clip, "-loop", "1", "-t", str(dur), "-i", png,
                    "-filter_complex", vf, "-map", "[out]", "-t", str(dur), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", out], check=True)


def render(plan, clips_by_id, out_mp4, workdir, with_music=False):
    """plan["shots"]: 1–3 shots (clip + its line) — e.g. setup on shot 1, punchline on the cut to shot 2, like Edits templates."""
    shots = plan["shots"]
    durs = [float(s.get("seconds") or (7.0 / len(shots))) for s in shots]
    parts = []
    for k, (sh, du) in enumerate(zip(shots, durs)):
        out = os.path.join(workdir, f"meme_part_{k}.mp4")
        _segment(clips_by_id[sh["clip"]], sh["text"], plan["style"], du, out, workdir, k); parts.append(out)
    lst = os.path.join(workdir, "meme_parts.txt")
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    total = sum(durs)
    audio_in = (["-stream_loop", "-1", "-i", __import__("pipeline.render.audio", fromlist=["x"]).mood_path("chill")] if with_music
                else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"])   # silent: the trending song is added in the Instagram app
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, *audio_in, "-map", "0:v", "-map", "1:a",
                    "-t", f"{total:.2f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", out_mp4], check=True)
    return out_mp4


def make(recent, workdir):
    os.makedirs(workdir, exist_ok=True)
    clips = [c for c in broll.items() if "VERTICAL" in c["desc"]] or broll.items()
    print(f"[1/3] trending audio + Claude news this week", flush=True)
    trend = _research()
    print(f"      {len(trend.get('songs', []))} trending songs, {len(trend.get('news', []))} news items", flush=True)
    print(f"[2/3] meme line", flush=True)
    plan = write(recent, clips, trend)
    plan["clip_paths"] = {c["id"]: c["path"] for c in clips if c["id"] in {sh["clip"] for sh in plan["shots"]}}
    song = next((s for s in trend.get("songs", []) if s.get("title", "").lower() == plan["song"]["title"].lower()), plan["song"])
    plan["song"] = {**song, **{k: v for k, v in plan["song"].items() if v}}
    print(f"      “{plan['text']}” on {plan['clip']} · song: {plan['song'].get('title')} — {plan['song'].get('artist')}", flush=True)
    return plan
