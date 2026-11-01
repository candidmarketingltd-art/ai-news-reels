"""The owner's B-roll library (AI-generated clips from Google Flow, or anything else they film).

Drop video files into media/broll/ (any file names). Each run indexes new files: three frames go to Claude, which writes a
short description + tags; the result is kept in media/broll/library.json. The video editor sees the library as AVAILABLE
MEDIA and picks clips that fit the voiceover. Clips used in the last few reels are held back so the feed doesn't repeat itself.
"""
import base64, datetime as dt, json, os, re, subprocess, tempfile
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "media" / "broll"
LIB = DIR / "library.json"
EXT = (".mp4", ".mov", ".m4v", ".webm")
MODEL = os.environ.get("SELECT_MODEL") or "claude-sonnet-5-5"
REST_REELS = int(os.environ.get("BROLL_REST_REELS") or 3)    # a clip sits out this many reels after it's used


def _load():
    try: return json.loads(LIB.read_text(encoding="utf-8"))
    except Exception: return {"clips": {}, "uses": []}


def _save(d):
    LIB.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", str(p)], capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    st = (j.get("streams") or [{}])[0]
    return float((j.get("format") or {}).get("duration") or 0), int(st.get("width") or 0), int(st.get("height") or 0)


def _describe(p, dur):
    with tempfile.TemporaryDirectory() as td:
        imgs = []
        for k, t in enumerate((dur * 0.15, dur * 0.5, dur * 0.85)):
            f = f"{td}/{k}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(p), "-frames:v", "1", "-vf", "scale=512:-2", f], check=True)
            imgs.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                     "data": base64.b64encode(open(f, "rb").read()).decode()}})
    msg = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=400, messages=[{"role": "user", "content": imgs + [{"type": "text", "text":
        "Three frames (start, middle, end) of one short B-roll clip for AI/tech tutorial reels. Return ONLY JSON: "
        '{"desc": "what the clip shows and the mood, one sentence, no guessing brands", "tags": ["5-8 short tags"], '
        '"use_for": "the kind of line in a script this clip illustrates, e.g. \'frustration with slow work\'", '
        '"problems": "visible text, logos, watermarks, distorted hands/faces, or \'none\'"}'}]}])
    raw = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"\{.*\}", raw, re.S)
    return json.loads(m.group(0)) if m else {"desc": p.stem.replace("_", " "), "tags": [], "use_for": "", "problems": "unknown"}


def index():
    """Describe any new clips in media/broll/. Returns the number of clips in the library."""
    if not DIR.exists(): return 0
    lib = _load(); changed = False
    files = {f.name: f for f in DIR.iterdir() if f.suffix.lower() in EXT}
    for name in list(lib["clips"]):
        if name not in files: lib["clips"].pop(name); changed = True
    for name, f in sorted(files.items()):
        if name in lib["clips"]: continue
        try:
            dur, w, h = _probe(f)
            if dur < 2: continue
            info = _describe(f, dur)
            lib["clips"][name] = {**info, "duration": round(dur, 1), "w": w, "h": h, "added": dt.date.today().isoformat()}
            print(f"      b-roll indexed: {name} — {info.get('desc', '')[:100]}", flush=True); changed = True
        except Exception as e:
            print(f"      (couldn't index {name}: {str(e)[:120]})", flush=True)
    if changed: _save(lib)
    return len(lib["clips"])


def items():
    """Library clips as media items, minus those used in the last REST_REELS reels and ones with visible problems."""
    lib = _load()
    recent = {c for u in lib.get("uses", [])[-REST_REELS:] for c in u}
    out = []
    for name, c in sorted(lib["clips"].items()):
        if name in recent: continue
        prob = str(c.get("problems") or "none").lower()
        if any(k in prob for k in ("watermark", "logo", "distort")) and "none" not in prob: continue
        p = DIR / name
        if not p.exists(): continue
        out.append({"id": "lib_" + re.sub(r"[^a-z0-9]+", "_", Path(name).stem.lower())[:40], "kind": "video", "path": str(p), "mp4": str(p),
                    "credit": "", "file": name, "frames": int(c.get("duration", 7) * 30),
                    "desc": f"B-roll ({c.get('duration')}s, {'VERTICAL 9:16 — best as full: true' if c.get('h', 0) > c.get('w', 0) else 'landscape'}): "
                            f"{c.get('desc', '')} Good for: {c.get('use_for', '')}"})
    return out


def mark_used(plan):
    used = sorted({m["file"] for m in plan.get("media") or [] if m.get("file")
                   for sc in plan.get("scenes", []) for e in sc.get("elements", []) if e.get("type") == "footage" and e.get("media") == m["id"]})
    if not used: return
    lib = _load(); lib.setdefault("uses", []).append(used); lib["uses"] = lib["uses"][-30:]; _save(lib)
