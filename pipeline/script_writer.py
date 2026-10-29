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
HANDLE = "@" + (os.environ.get("IG_HANDLE") or "ihackgrowth").lstrip("@")

FORMATS = {
    "single": """ONE story, told properly (40–55 seconds spoken; 110–145 words — hard limit 150).
1. **Hook (0–3s)**: see HOOK RULES. It is the first sentence of the first paragraph; the story continues in the SAME paragraph.
2. **What happened (3–15s)**: who did what, in one or two sentences, with the most striking number. `[intrigued, building energy]`.
3. **The details**: 2–3 fast beats — what it can do / how much / who it affects. Tags like `[excited, fast]`, `[serious]`, `[punchy]`, `[amused]`.
4. **Why it matters to YOU**: the practical consequence for a normal viewer (their job, their phone, their money, their privacy). `[confident]`.
5. **Share trigger (last line)**: "Send this to the friend who …" naming someone specific to the topic. `[playful, warm]`.""",
    "roundup": """A combined reel of {N} stories (50–65 seconds spoken; 140–170 words — hard limit 175).
1. **Hook (0–3s)**: see HOOK RULES — about the FIRST (most important) story, and that story continues right after it in the
   same paragraph. No "here are {N} stories" line, ever.
2. **The {N} stories**: one paragraph each, most important first: what happened + the one number or detail that makes it
   interesting, in 2–3 sentences. Move between stories like a person talking — "Meanwhile, …", "And over at Google, …",
   "And in Europe, …" — NEVER "Story 1." / "Story 2." / "Next story". Vary the tags (`[amused]`, `[serious]`, `[curious]`, `[playful]`).
3. **So what**: one line tying them together or telling the viewer what to do / try / watch. `[confident]`.
4. **Share trigger (last line)**: "Send this to the friend who …". `[playful, warm]`.""",
}


MAX_WORDS = {"single": int(os.environ.get("MAX_WORDS_SINGLE") or 150), "roundup": int(os.environ.get("MAX_WORDS_ROUNDUP") or 175)}


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
FLOOR = int(os.environ.get("MIN_IMPORTANCE") or 3)   # never post anything weaker than this, even when a reel is required

MUST_POST_NOTE = """

## THIS RUN MUST PRODUCE A REEL ("skip" is not allowed — the account posts every 6 hours)
- A story with importance >= {SINGLE_MIN} → `single`.
- Otherwise → `roundup` of the 2–4 best stories (prefer importance >= {ROUNDUP_MIN}; if fewer qualify, use the best available
  with importance >= {FLOOR}).
- Only one decent story at all → `single` on it, told as a useful explainer (what it is, why it matters to the viewer).
- Never re-cover a RECENTLY COVERED story unless there is a genuinely new development."""


TOPIC_BRIEF = {
    "ai": ("AI", "AI news: models, AI products and features, AI companies, chips/compute for AI, AI funding, AI rules and safety."),
    "tech": ("Tech & Business", "tech and business news that is NOT mainly about AI (AI gets its own reels): big-tech products and "
             "launches (phones, gadgets, apps, EVs, space), startups and funding, IPOs, acquisitions, earnings and market-moving "
             "company news, layoffs, founders/CEOs' business moves, outages and hacks, tech policy, Indian startup/business news "
             "with global interest. No general stock tips, no politics without a tech/business angle."),
}


def select(candidates, recently_covered, must_post=True, topic="ai"):
    name, brief = TOPIC_BRIEF.get(topic, TOPIC_BRIEF["ai"])
    sys0 = (ROOT / "prompts" / "news_editor.md").read_text(encoding="utf-8").replace("{TOPIC}", name).replace("{TOPIC_BRIEF}", brief)
    if must_post: sys0 += MUST_POST_NOTE
    sys0 = sys0.replace("{SINGLE_MIN}", str(SINGLE_MIN)).replace("{ROUNDUP_MIN}", str(ROUNDUP_MIN)).replace("{FLOOR}", str(FLOOR))
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    slim = [{k: c[k] for k in ("id", "headline", "source", "time", "summary", "trend")} for c in candidates]
    user = (f"NOW: {now}\n\nRECENTLY COVERED (last 3 days):\n" + ("\n".join(f"- {h}" for h in recently_covered) or "- (nothing yet)")
            + f"\n\nCANDIDATES ({len(slim)}):\n{json.dumps(slim, ensure_ascii=False, indent=0)}\n\nReturn only the JSON.")
    ids = {c["id"] for c in candidates}

    def check(d):
        if d.get("decision") not in ("single", "roundup", "skip"): raise ValueError("decision must be single, roundup or skip")
        if must_post and d["decision"] == "skip" and candidates:
            raise ValueError("skip is not allowed in this run — pick the best single story or a roundup")
        st = d.get("stories") or []
        if d["decision"] == "single" and len(st) != 1: raise ValueError("single needs exactly 1 story")
        if d["decision"] == "roundup" and not 2 <= len(st) <= 4: raise ValueError("roundup needs 2-4 stories")
        for s in st:
            bad = [x for x in s.get("candidate_ids", []) if x not in ids]
            if bad or not s.get("candidate_ids"): raise ValueError(f"unknown or missing candidate_ids {bad}")
    d = _ask_json(SELECT_MODEL, sys0, user, check)
    imp = lambda s: int(s.get("importance") or 0)
    if must_post:
        # a reel is required: keep the editor's choice, only drop real junk (below FLOOR)
        d["stories"] = [s for s in d.get("stories") or [] if imp(s) >= FLOOR]
        if d["decision"] == "roundup" and len(d["stories"]) == 1: d["decision"] = "single"
        if not d["stories"]: d["decision"] = "skip"
    else:
        # optional mode (MUST_POST=0): enforce the thresholds so a generous model can't post filler
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
    # model / product names with small numbers ("M5", "GPT-5", "Gemini 3", "iPhone 17") must match the sources exactly
    norm = lambda x: re.sub(r"[\s\-]", "", x).lower()
    src_n = norm(sources)
    text = " ".join([plan.get("voiceover", ""), json.dumps(plan.get("scenes", []), ensure_ascii=False),
                     json.dumps(plan.get("cold_open", []), ensure_ascii=False), json.dumps(plan.get("title", []), ensure_ascii=False)])
    names = {m.group(0) for m in re.finditer(r"\b(?:[A-Z][A-Za-z]{0,9}|i[A-Z][a-z]+)[- ]?\d{1,3}\b", text)}
    names = {n for n in names if not re.match(r"(?i)(story|update|part|ep|top|in|by|on|at|and|for|of|the|from|to|up)[- ]?\d", n)}
    wrong = sorted(n for n in names if norm(n) not in src_n)
    if wrong:
        raise FactCheckError(f"names/versions not found in the sources (check the exact model/chip/version): {', '.join(wrong)}")


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


STORY_LABEL = re.compile(r"\b(story|update|news)\s*(#|no\.?|number)?\s*(\d|one|two|three|four)\b[.:]", re.I)
BANNED_TAGS = re.compile(r"\[[^\]]*\b(urgent|dramatic|deep|announcer|robotic|news anchor)\b[^\]]*\]", re.I)
BANNED_HOOK = re.compile(r"^(\d+\s+(ai\s+)?(stories|updates|news|things)|\d+\s+hours|here'?s|here is|big news|breaking news|ai news|"
                         r"let'?s talk|today in ai|in today'?s|welcome|hey|hi\b|did you (hear|know))", re.I)


def check_hook(voiceover):
    """The first paragraph is the hook: short, fast, starts with a fact, no counting/teaser intro."""
    if STORY_LABEL.search(voiceover):
        raise ValueError("don't label stories ('Story 1.', 'Story 2.'); move between stories naturally ('Meanwhile, …', 'And in Europe, …')")
    if BANNED_TAGS.search(voiceover):
        raise ValueError("don't use announcer tags like [urgent]/[dramatic]/[deep]; use natural ones like [excited, conversational], [curious], [amused]")
    para = re.sub(r"\[[^\]]*\]", " ", voiceover.strip().split("\n\n")[0]).strip()
    first = re.split(r"(?<=[.!?])\s", para)[0]
    n = len(first.split())
    if BANNED_HOOK.search(first):
        raise ValueError(f"the hook starts with a banned slow/teaser opener ('{first[:40]}…'). Open with the most surprising concrete fact")
    if n > 18:
        raise ValueError(f"the hook (first sentence) is {n} words; it must be at most ~12–16 words so it lands in under 3 seconds")


# ----------------------------------------------------------------------------- 2) script, 3) edit
def write(decision, pack, get_media=None, topic="ai"):
    """decision: output of select(); pack: news.fetch_articles() output.
    get_media(script) -> media list (official images, logos, stock clips) the editor can cut in. Returns the full plan."""
    example = json.loads((ROOT / "prompts" / "example_plan.json").read_text(encoding="utf-8"))
    n = len(decision["stories"])
    fmt = FORMATS[decision["decision"]].replace("{N}", str(n))
    sys1 = (ROOT / "prompts" / "script_writer.md").read_text(encoding="utf-8") \
        .replace("{FORMAT}", fmt).replace("{HANDLE}", HANDLE).replace("{TOPIC}", TOPIC_BRIEF.get(topic, TOPIC_BRIEF["ai"])[0]) \
        .replace("{EXAMPLE}", json.dumps({k: example[k] for k in ("voiceover", "ig_caption", "hashtags")}, ensure_ascii=False, indent=1))
    sources = "\n\n".join(f"=== STORY {i + 1}: {p['story']}\n{p['text']}" for i, p in enumerate(pack))
    stories = "\n".join(f"{i + 1}. {s['headline']} — {s.get('why', '')}" for i, s in enumerate(decision["stories"]))
    user1 = (f"FORMAT: {decision['decision']} ({n} stor{'y' if n == 1 else 'ies'})\n\nSTORIES (in this order):\n{stories}\n\n"
             f"SOURCES (the only facts you may use):\n{sources}\n\nReturn only the JSON.")
    # translate the user-facing handle so captions/scripts mention the right account
    sys1 = sys1.replace("@youraccount", HANDLE)

    def check1(d):
        if not d.get("voiceover"): raise ValueError("missing 'voiceover'")
        check_hook(d["voiceover"])
        n_words = len(re.sub(r"\[[^\]]*\]", " ", d["voiceover"]).split())
        limit = MAX_WORDS[decision["decision"]]
        if n_words > limit:
            raise ValueError(f"the voiceover is {n_words} words (~{n_words / 2.7:.0f} s); keep it under {limit} words — cut the weakest "
                             "detail, keep the hook, the key numbers and the share line")
        fact_check({"voiceover": d["voiceover"]}, sources)
    script = _ask_json(SCRIPT_MODEL, sys1, user1, check1)
    media = []
    if get_media:
        try:
            media = get_media(script) or []
        except Exception as e:
            print(f"      (media step failed, continuing without footage: {str(e)[:150]})", flush=True)
    ids = {m["id"] for m in media}
    menu = "\n".join(f"- {m['id']} ({m['kind']}): {m['desc']}" for m in media) or "- (none — use cards only)"

    sys2 = (ROOT / "prompts" / "video_editor.md").read_text(encoding="utf-8") \
        .replace("{TAG_SUFFIX}", ".AI" if topic == "ai" else ".TECH or .BIZ").replace(
        "{EXAMPLE}", json.dumps({k: example[k] for k in ("voiceover", "series_tag", "title_line1", "title_line2", "cold_open", "scenes")}, ensure_ascii=False, indent=1))
    user2 = (f"FORMAT: {decision['decision']} ({n} stor{'y' if n == 1 else 'ies'})\nSTORIES:\n{stories}\n\n"
             f"VOICEOVER (already recorded — cue words must match it exactly):\n{script['voiceover']}\n\n"
             f"AVAILABLE MEDIA (use only these ids):\n{menu}\n\n"
             "Return only the JSON with `series_tag`, `title_line1`, `title_line2`, `cold_open` and `scenes`.")

    def check2(d):
        if not d.get("scenes") or not d.get("cold_open"): raise ValueError("missing 'scenes' or 'cold_open'")
        _check_cues(d, script["voiceover"])
        for sc in d["scenes"]:
            c = sc.get("card") or {}
            for k in ("media", "bg_media", "logo"):
                if c.get(k) and c[k] not in ids:
                    raise ValueError(f"card uses media '{c[k]}' which is not in AVAILABLE MEDIA ({', '.join(sorted(ids)) or 'none'})")
            if c.get("type") == "footage" and not c.get("media"):
                raise ValueError("a footage card needs a `media` id")
        if not d.get("title_line1") or not d.get("title_line2"): raise ValueError("missing title_line1 / title_line2")
        fact_check({"voiceover": script["voiceover"], "scenes": d["scenes"], "cold_open": d["cold_open"],
                    "title": [d.get("title_line1"), d.get("title_line2")]}, sources)
    edit = _ask_json(EDIT_MODEL, sys2, user2, check2)

    return {**script, "cold_open": edit["cold_open"], "scenes": edit["scenes"],
            "series_tag": edit.get("series_tag") or "AI NEWS", "title_line1": edit["title_line1"], "title_line2": edit["title_line2"],
            "decision": decision, "sources": [{"story": p["story"], "urls": p["urls"]} for p in pack],
            "media": media, "media_hints": script.get("media_hints", []), "topic": topic,
            "models": {"select": SELECT_MODEL, "script": SCRIPT_MODEL, "edit": EDIT_MODEL}}
