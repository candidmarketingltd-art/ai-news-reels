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
        t = d.get("text") or ""
        if not t or len(t.split()) > 22: raise ValueError("text: one line, max 22 words")
        if d.get("clip") not in ids: raise ValueError("clip must be one of the B-ROLL CLIPS ids")
        if d.get("style") not in ("meme", "quote"): raise ValueError("style: meme or quote")
        s = (d.get("song") or {}).get("title", "").lower()
        if songs and s not in songs: raise ValueError("song must be one of the TRENDING songs, title exactly as listed")
        if not d.get("caption"): raise ValueError("caption missing")
    return _ask_json(SCRIPT_MODEL, sysp, user, check)


def _font(name, size):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / name), size)


def _overlay(text, style, png):
    """Instagram-native text: black on white rounded boxes per line (meme) or white with soft shadow (quote)."""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if style == "meme":
        f = _font("Inter-Medium.ttf", 58)
        lines = textwrap.wrap(text, 26)
        y = int(H * 0.22)
        for ln in lines:
            l, t, r, b = d.textbbox((0, 0), ln, font=f)
            w, h = r - l, 58
            x = (W - w) // 2
            d.rounded_rectangle((x - 26, y - 14, x + w + 26, y + h + 22), radius=18, fill=(255, 255, 255, 255))
            d.text((x, y - t + 4), ln, font=f, fill=(0, 0, 0, 255))
            y += h + 36
    else:
        f = _font("Inter-Bold.ttf", 66)
        lines = textwrap.wrap(text, 22)
        total = len(lines) * 86
        y0 = int(H * 0.40) - total // 2
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        for i, ln in enumerate(lines):
            w = d.textlength(ln, font=f)
            sd.text(((W - w) / 2, y0 + i * 86 + 4), ln, font=f, fill=(0, 0, 0, 200))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(10)))
        d = ImageDraw.Draw(im)
        for i, ln in enumerate(lines):
            w = d.textlength(ln, font=f)
            d.text(((W - w) / 2, y0 + i * 86), ln, font=f, fill=(255, 255, 255, 255))
    im.save(png)


def render(plan, clip, out_mp4, workdir, seconds=7.0, with_music=False):
    png = os.path.join(workdir, "meme_text.png")
    _overlay(plan["text"], plan["style"], png)
    dark = "eq=brightness=-0.08:saturation=0.9," if plan["style"] == "quote" else ""
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},{dark}fps=30,"
          f"trim=0:{seconds},setpts=PTS-STARTPTS[v];[v][1:v]overlay=0:0,format=yuv420p[out]")
    cmd = ["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", clip["path"], "-loop", "1", "-i", png]
    if with_music:
        from pipeline.render import audio
        cmd += ["-stream_loop", "-1", "-i", audio.mood_path("chill")]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]   # silent: the trending song is added in the Instagram app
    cmd += ["-filter_complex", vf, "-map", "[out]", "-map", "2:a", "-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "19", "-c:a", "aac", "-b:a", "128k", "-shortest", out_mp4]
    subprocess.run(cmd, check=True)
    return out_mp4


def make(recent, workdir):
    os.makedirs(workdir, exist_ok=True)
    clips = [c for c in broll.items() if "VERTICAL" in c["desc"]] or broll.items()
    print(f"[1/3] trending audio + Claude news this week", flush=True)
    trend = _research()
    print(f"      {len(trend.get('songs', []))} trending songs, {len(trend.get('news', []))} news items", flush=True)
    print(f"[2/3] meme line", flush=True)
    plan = write(recent, clips, trend)
    plan["clip_path"] = next(c["path"] for c in clips if c["id"] == plan["clip"])
    song = next((s for s in trend.get("songs", []) if s.get("title", "").lower() == plan["song"]["title"].lower()), plan["song"])
    plan["song"] = {**song, **{k: v for k, v in plan["song"].items() if v}}
    print(f"      “{plan['text']}” on {plan['clip']} · song: {plan['song'].get('title')} — {plan['song'].get('artist')}", flush=True)
    return plan
