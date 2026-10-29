"""Claude picks the news (single / roundup / skip), Sonnet writes the script, Opus edits the video (scene plan).
Every number in the script and on screen is fact-checked against the articles that were read."""
import datetime as dt, json, os, re
from pathlib import Path
import anthropic

ROOT = Path(__file__).resolve().parent.parent
SELECT_MODEL = os.environ.get("SELECT_MODEL") or os.environ.get("SCRIPT_MODEL") or "claude-sonnet-5-5"  # picks the news
SCRIPT_MODEL = os.environ.get("SCRIPT_MODEL") or "claude-sonnet-5-5"   # writes the script
EDIT_MODEL = os.environ.get("EDIT_MODEL") or "claude-opus-5-5"         # edits the video: scenes, cards, timing, mascot
SINGLE_MIN = int(os.environ.get("SINGLE_MIN_IMPORTANCE") or 8)
ROUNDUP_MIN = int(os.environ.get("ROUNDUP_MIN_IMPORTANCE") or 5)
HANDLE = "@" + (os.environ.get("IG_HANDLE") or "youraccount").lstrip("@")

FORMATS = {
    "single": """ONE story, told properly (45–60 seconds spoken; ~110–150 words).
1. **Cold open (0–4s)**: 2–3 ultra-short dramatic fragments, each a stated fact from the sources. Start the voiceover with `[slow, deep, dramatic]`.
2. **What happened (4–15s)**: who did what, in one or two sentences, with the most striking number. `[intrigued, building energy]`.
3. **The details**: 2–3 fast beats — what it can do / how much / who it affects. Tags like `[excited, fast]`, `[serious]`, `[punchy]`, `[amused]`.
4. **Why it matters to YOU**: the practical consequence for a normal viewer (their job, their phone, their money, their privacy). `[confident]`.
5. **Share trigger (last line)**: "Send this to the friend who …" naming someone specific to the topic. `[playful, warm]`.""",
    "roundup": """A combined reel of {N} stories (55–70 seconds spoken; ~140–180 words).
1. **Cold open (0–4s)**: 2–3 ultra-short fragments teasing the stories ("{N} AI stories. 24 hours. …"). Start with `[slow, deep, dramatic]`.
2. **Story 1 … Story {N}**: start each with "Story 1." / "Story 2." …, then what happened + the one number or detail that makes it interesting,
   in 2–3 sentences. Most important first. Vary the tags (`[excited, fast]`, `[serious]`, `[amused]`, `[punchy]`).
3. **So what**: one line tying them together or telling the viewer what to do / try / watch. `[confident]`.
4. **Share trigger (last line)**: "Send this to the friend who …". `[playful, warm]`.""",
}


class FactCheckError(Exception):
    pass


def _chat(model, system, msgs, max_tokens=8000):
    resp = anthropic.Anthropic().messages.create(model=model, max_tokens=max_tokens, system=system, messages=msgs)
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    return re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()


def _ask_json(model, system, user, check, attempts=3):
    """Call Claude, parse JSON, run `check`; on any problem send it back with the error to fix."""
    msgs = [{"role": "user", "content": user}]
    err = None
    for _ in range(attempts):
        raw = _chat(model, system, msgs)
        try:
            data = json.loads(raw)
            check(data)
            return data
        except (ValueError, FactCheckError) as e:
            err = e
            msgs += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": f"Problem: {e}. Fix it and return the full corrected JSON only."}]
    raise FactCheckError(f"{model} output rejected after {attempts} attempts: {err}")


# ----------------------------------------------------------------------------- 1) pick the news
def select(candidates, recently_covered):
    sys0 = (ROOT / "prompts" / "news_editor.md").read_text(encoding="utf-8") \
        .replace("{SINGLE_MIN}", str(SINGLE_MIN)).replace("{ROUNDUP_MIN}", str(ROUNDUP_MIN))
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    slim = [{k: c[k] for k in ("id", "headline", "source", "time", "summary", "trend")} for c in candidates]
    user = (f"NOW: {now}\n\nRECENTLY COVERED (last 3 days):\n" + ("\n".join(f"- {h}" for h in recently_covered) or "- (nothing yet)")
            + f"\n\nCANDIDATES ({len(slim)}):\n{json.dumps(slim, ensure_ascii=False, indent=0)}\n\nReturn only the JSON.")
    ids = {c["id"] for c in candidates}

    def check(d):
        if d.get("decision") not in ("single", "roundup", "skip"): raise ValueError("decision must be single, roundup or skip")
        st = d.get("stories") or []
        if d["decision"] == "single" and len(st) != 1: raise ValueError("single needs exactly 1 story")
        if d["decision"] == "roundup" and not 2 <= len(st) <= 4: raise ValueError("roundup needs 2-4 stories")
        for s in st:
            bad = [x for x in s.get("candidate_ids", []) if x not in ids]
            if bad or not s.get("candidate_ids"): raise ValueError(f"unknown or missing candidate_ids {bad}")
    d = _ask_json(SELECT_MODEL, sys0, user, check)
    # enforce the thresholds in code too, so a generous model can't post filler
    imp = lambda s: int(s.get("importance") or 0)
    if d["decision"] == "single" and imp(d["stories"][0]) < SINGLE_MIN:
        d["decision"], d["reason"] = "skip", f"single story only importance {imp(d['stories'][0])} (< {SINGLE_MIN}); " + d.get("reason", "")
    if d["decision"] == "roundup":
        d["stories"] = [s for s in d["stories"] if imp(s) >= ROUNDUP_MIN]
        if len(d["stories"]) == 1:
            d["decision"] = "single" if imp(d["stories"][0]) >= SINGLE_MIN else "skip"
        elif not d["stories"]:
            d["decision"] = "skip"
    if d["decision"] == "skip": d["stories"] = []
    return d


# ----------------------------------------------------------------------------- fact check
_MULT = {"thousand": 1e3, "k": 1e3, "million": 1e6, "mn": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9, "trillion": 1e12, "tn": 1e12, "t": 1e12}


def _digits(s):
    """All numbers in a string, normalised (commas removed, trailing .0 dropped)."""
    out = set()
    for n in re.findall(r"\d[\d,]*(?:\.\d+)?", s or ""):
        n = n.replace(",", "")
        if "." in n: n = n.rstrip("0").rstrip(".")
        out.add(n)
    return out


def _scaled(s):
    """'$2 billion' / '2.5B' / '300 million' -> '2000000000', '2500000000', '300000000' (for counters)."""
    out = set()
    for num, unit in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(thousand|million|billion|trillion|bn|mn|tn|[kmbt])\b", s or "", re.I):
        try: out.add(str(int(round(float(num.replace(",", "")) * _MULT[unit.lower()]))))
        except Exception: pass
    return out


def fact_check(plan, sources):
    src = _digits(sources) | _scaled(sources)
    year = dt.datetime.now().year
    allowed = src | {str(i) for i in range(0, 11)} | {"24", "60", str(year)}  # counting words, "24 hours", "60 seconds"
    used = _digits(plan.get("voiceover", "")) | _digits(json.dumps(plan.get("scenes", []), ensure_ascii=False)) \
        | _digits(json.dumps(plan.get("cold_open", []), ensure_ascii=False)) | _digits(json.dumps(plan.get("title", []), ensure_ascii=False))
    bad = sorted(n for n in used if n not in allowed)
    if bad:
        raise FactCheckError(f"numbers not found in the sources: {', '.join(bad)}")


def _spoken(voiceover):
    from pipeline.render.engine import _norm
    txt = re.sub(r"\[[^\]]*\]", " ", voiceover)
    return [_norm(w).lower() for w in txt.split() if _norm(w)]


def _check_cues(plan, voiceover):
    from pipeline.render.engine import _norm
    joined = " " + " ".join(_spoken(voiceover)) + " "
    bad = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if (k == "at" or k.endswith("_at")) and isinstance(v, str):
                    toks = [_norm(x).lower() for x in v.split() if _norm(x)]
                    if toks and (" " + " ".join(toks) + " ") not in joined: bad.append(v)
                else: walk(v)
        elif isinstance(o, list):
            for x in o: walk(x)
    walk(plan.get("cold_open", [])); walk(plan.get("scenes", []))
    if bad:
        raise ValueError("these cue words are not in the voiceover exactly as written: " + " | ".join(bad[:8]))


# ----------------------------------------------------------------------------- 2) script, 3) edit
def write(decision, pack):
    """decision: output of select(); pack: news.fetch_articles() output. Returns the full plan."""
    example = json.loads((ROOT / "prompts" / "example_plan.json").read_text(encoding="utf-8"))
    n = len(decision["stories"])
    fmt = FORMATS[decision["decision"]].replace("{N}", str(n))
    sys1 = (ROOT / "prompts" / "script_writer.md").read_text(encoding="utf-8") \
        .replace("{FORMAT}", fmt).replace("{HANDLE}", HANDLE) \
        .replace("{EXAMPLE}", json.dumps({k: example[k] for k in ("voiceover", "ig_caption", "hashtags")}, ensure_ascii=False, indent=1))
    sources = "\n\n".join(f"=== STORY {i + 1}: {p['story']}\n{p['text']}" for i, p in enumerate(pack))
    stories = "\n".join(f"{i + 1}. {s['headline']} — {s.get('why', '')}" for i, s in enumerate(decision["stories"]))
    user1 = (f"FORMAT: {decision['decision']} ({n} stor{'y' if n == 1 else 'ies'})\n\nSTORIES (in this order):\n{stories}\n\n"
             f"SOURCES (the only facts you may use):\n{sources}\n\nReturn only the JSON.")
    # translate the user-facing handle so captions/scripts mention the right account
    sys1 = sys1.replace("@youraccount", HANDLE)

    def check1(d):
        if not d.get("voiceover"): raise ValueError("missing 'voiceover'")
        fact_check({"voiceover": d["voiceover"]}, sources)
    script = _ask_json(SCRIPT_MODEL, sys1, user1, check1)

    sys2 = (ROOT / "prompts" / "video_editor.md").read_text(encoding="utf-8").replace(
        "{EXAMPLE}", json.dumps({k: example[k] for k in ("voiceover", "series_tag", "title_line1", "title_line2", "cold_open", "scenes")}, ensure_ascii=False, indent=1))
    user2 = (f"FORMAT: {decision['decision']} ({n} stor{'y' if n == 1 else 'ies'})\nSTORIES:\n{stories}\n\n"
             f"VOICEOVER (already recorded — cue words must match it exactly):\n{script['voiceover']}\n\n"
             "Return only the JSON with `series_tag`, `title_line1`, `title_line2`, `cold_open` and `scenes`.")

    def check2(d):
        if not d.get("scenes") or not d.get("cold_open"): raise ValueError("missing 'scenes' or 'cold_open'")
        _check_cues(d, script["voiceover"])
        if not d.get("title_line1") or not d.get("title_line2"): raise ValueError("missing title_line1 / title_line2")
        fact_check({"voiceover": script["voiceover"], "scenes": d["scenes"], "cold_open": d["cold_open"],
                    "title": [d.get("title_line1"), d.get("title_line2")]}, sources)
    edit = _ask_json(EDIT_MODEL, sys2, user2, check2)

    return {**script, "cold_open": edit["cold_open"], "scenes": edit["scenes"],
            "series_tag": edit.get("series_tag") or "AI NEWS", "title_line1": edit["title_line1"], "title_line2": edit["title_line2"],
            "decision": decision, "sources": [{"story": p["story"], "urls": p["urls"]} for p in pack],
            "models": {"select": SELECT_MODEL, "script": SCRIPT_MODEL, "edit": EDIT_MODEL}}
