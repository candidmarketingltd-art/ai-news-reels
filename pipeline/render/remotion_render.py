"""Editorial motion-graphics renderer (RENDER_STYLE=remotion): builds props from the plan + word timings and renders
remotion/src (React + Remotion) to a silent 1080x1920 MP4. Audio (voice, theme, sfx) is mixed afterwards by audio.mix.

Timing reuses the existing engine: ModernReel resolves every cue phrase ("at"/"*_at") to seconds, the hook key words,
Rohan's mood + lip-sync (viseme) per frame — so the editor prompt and plan schema stay the same.
"""
import json, math, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import FPS, _norm  # noqa: E402
from modern import ModernReel, MOOD_REST  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
RDIR = os.path.join(ROOT, "remotion_editorial")
MOUTHS = {"closed", "smile", "smirk", "A", "O", "E", "MBP"}


def _phrases(words, max_words=14):
    """Group words into headline phrases: break at sentence ends, long pauses or ~9 words."""
    out, cur = [], []
    for i, (w, s, e) in enumerate(words):
        cur.append(i)
        nxt = words[i + 1][1] if i + 1 < len(words) else 1e9
        if w.endswith((".", "!", "?", "…")) or len(cur) >= max_words or (nxt - e > 0.6 and len(cur) >= 6) or \
                (w.endswith((",", ":", "—")) and len(cur) >= 10):
            out.append(cur); cur = []
    if cur: out.append(cur)
    res = []
    for k, ph in enumerate(out):
        s = words[ph[0]][1]
        e = words[out[k + 1][0]][1] - 0.02 if k + 1 < len(out) else words[ph[-1]][2] + 0.6
        res.append({"s": round(s, 3), "e": round(e, 3), "from": ph[0], "to": ph[-1]})
    return res


def _highlights(plan, words):
    """Which spoken words get the red italic-serif treatment: numbers/money/percent, the hook's key words,
    the title's *starred* words and proper names (capitalised, not starting a sentence)."""
    keys = set()
    for ln in plan.get("cold_open", []):
        keys |= {_norm(x) for x in str(ln.get("text", "")).split()}
    for m in re.findall(r"\*([^*]+)\*", f"{plan.get('title_line1', '')} {plan.get('title_line2', '')}"):
        keys |= {_norm(x) for x in m.split()}
    keys.discard("")
    stop = {"i", "the", "a", "an", "and", "it", "its", "this", "that", "so", "okay", "wait", "but", "now", "send", "meanwhile",
            "your", "you", "my", "our", "to", "of", "in", "for", "is", "are", "ai", "sees", "just", "can"}
    hl, prev = [], "."
    for w, _, _ in words:
        n = _norm(w)
        is_num = bool(re.search(r"\d", w)) or w.startswith(("$", "₹", "€", "£"))
        proper = w[:1].isupper() and not prev.endswith((".", "!", "?", "…")) and n not in stop and len(n) > 2
        hl.append(bool(is_num or (n in keys and n not in stop) or proper))
        prev = w
    return hl


def build_props(plan, words, duration, public_run):
    reel = ModernReel(plan, words, duration)
    n_frames = int(math.ceil((duration + 0.9) * FPS))
    # scenes with every cue already in seconds
    scenes = []
    for sc in reel.scenes:
        scenes.append({"start": round(sc["_t"], 3), "end": round(min(sc["_end"], duration + 1), 3),
                       "mood": sc.get("mood", "neutral"), "tint": sc.get("tint"), "card": sc["_resolved"]})
    # Rohan sprite per frame (mood + lip-sync + blink)
    sprites, index, track = [], {}, []
    for i in range(n_frames):
        t = i / FPS
        _, md, _ = reel.mood(t)
        md = md if md in ("neutral", "smirk", "shocked", "serious") else "neutral"
        v = reel.viseme(t)
        mouth = v or MOOD_REST.get(md, "closed")
        mouth = mouth if mouth in MOUTHS else "closed"
        eyes = "blink" if ((t + 0.7) % 3.4) < 0.12 else "open"
        name = f"{md}_{mouth}_{eyes}.png"
        if name not in index: index[name] = len(sprites); sprites.append(name)
        track.append(index[name])
    # media -> remotion/public/run/<...>
    os.makedirs(public_run, exist_ok=True)
    rel_root = os.path.relpath(public_run, os.path.join(RDIR, "public"))
    media = {}
    for m in plan.get("media", []):
        src = m.get("mp4") or (m["path"][:-4] + ".mp4" if m["kind"] == "video" else m["path"])
        if not os.path.exists(src): continue
        dst = os.path.join(public_run, m["id"] + os.path.splitext(src)[1])
        shutil.copyfile(src, dst)
        media[m["id"]] = {"kind": m["kind"], "src": f"{rel_root}/{os.path.basename(dst)}", "credit": m.get("credit", "")}
    hl = _highlights(plan, words)
    topic = plan.get("topic", "ai")
    return reel, {
        "durationFrames": n_frames, "fps": FPS,
        "words": [{"t": w, "s": round(s, 3), "e": round(e, 3), "hl": h} for (w, s, e), h in zip(words, hl)],
        "phrases": _phrases(words),
        "scenes": scenes,
        "hook": {"end": round(getattr(reel, "hook_end", 0.0), 3), "items": [{"t": round(t, 3), "text": x} for t, x in getattr(reel, "hook_items", [])]},
        "meta": {"tag": plan.get("series_tag") or "AI NEWS", "ep": int(plan.get("episode") or 1),
                 "kicker": "ai news" if topic == "ai" else "tech & business",
                 "handle": "@" + (os.environ.get("IG_HANDLE") or "ihackgrowth").lstrip("@"), "topic": topic},
        "mascot": {"sprites": sprites, "track": track},
        "media": media,
    }


def render(plan, words, duration, out_path, workdir=None):
    """Render the silent video; returns the sound-design cues (same as engine.render)."""
    workdir = workdir or os.path.dirname(os.path.abspath(out_path))
    run_id = os.path.splitext(os.path.basename(out_path))[0]
    public_run = os.path.join(RDIR, "public", "run", run_id)
    reel, props = build_props(plan, words, duration, public_run)
    props_path = os.path.join(workdir, "remotion_props.json")
    with open(props_path, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False)
    cmd = ["npx", "remotion", "render", "src/index.ts", "Reel", os.path.abspath(out_path), f"--props={props_path}",
           "--muted", "--log=error", f"--concurrency={os.environ.get('REMOTION_CONCURRENCY') or os.cpu_count() or 2}"]
    if os.environ.get("REMOTION_BROWSER"):
        cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    print("      remotion:", " ".join(cmd[3:6]), flush=True)
    try:
        subprocess.run(cmd, cwd=RDIR, check=True)
    finally:
        shutil.rmtree(public_run, ignore_errors=True)
    return reel.sfx_cues()
