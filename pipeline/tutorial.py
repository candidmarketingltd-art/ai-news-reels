"""Tutorial / helpful reels for @ihackgrowth.

1. pool()      — the top recent AI & tech reels on Instagram (Apify: hashtags + creator accounts), cached once a day
2. pick()      — Claude picks a proven, teachable topic (3 ranked picks, never one we covered recently)
3. transcript  — what the original reel actually says (Apify transcript add-on, only for the picked reel)
4. research()  — Sonnet + web search verifies the tool, the exact steps and every number (official sources first)
5. write()     — Sonnet writes a very conversational script (negative/contrarian angles allowed when true)
6. edit()      — Opus plans the AI HACKS motion-graphics edit (HISAAB renderer + tutorial elements)
Every number on screen or in the voice must be in the research notes.
"""
import datetime as dt, json, math, os, re
from pathlib import Path

import requests

from pipeline.script_writer import _ask_json, _chat, FactCheckError, _digits, _scaled, _word_numbers, _check_cues, SCRIPT_MODEL, EDIT_MODEL, SELECT_MODEL, HANDLE
import anthropic

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "logs" / "reel_pool.json"
HASHTAGS = [h.strip().lstrip("#") for h in (os.environ.get("IG_HASHTAGS") or
            "aitools,chatgpt,aihacks,chatgpttips,claudeai,techtips,productivityhacks,aitips,canvatips,techhacks").split(",") if h.strip()]
ACCOUNTS = [a.strip().lstrip("@") for a in (os.environ.get("IG_SOURCE_ACCOUNTS") or "").split(",") if a.strip()]
PER_TAG = int(os.environ.get("REELS_PER_TAG") or 20)
AUTO_ACCOUNTS = int(os.environ.get("AUTO_ACCOUNTS") or 6)
RESEARCH_MODEL = os.environ.get("RESEARCH_MODEL") or SCRIPT_MODEL
MAX_WORDS = int(os.environ.get("MAX_WORDS_TUTORIAL") or 165)


# ---------------------------------------------------------------------------------- 1) the pool of top reels
def _apify(actor, payload, timeout=300):
    tok = os.environ.get("APIFY_TOKEN")
    if not tok: raise RuntimeError("APIFY_TOKEN is not set")
    r = requests.post(f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items",
                      params={"token": tok}, json=payload, timeout=timeout + 30)
    if r.status_code >= 400: raise RuntimeError(f"apify {actor}: {r.status_code} {r.text[:200]}")
    return r.json()


def _norm_item(x, source):
    try: ts = dt.datetime.fromisoformat(str(x.get("timestamp")).replace("Z", "+00:00"))
    except Exception: return None
    plays = x.get("videoPlayCount") or x.get("videoViewCount") or x.get("igPlayCount") or 0
    return {"url": x.get("url"), "code": x.get("shortCode"), "owner": x.get("ownerUsername"), "plays": int(plays or 0),
            "likes": int(x.get("likesCount") or 0), "comments": int(x.get("commentsCount") or 0), "dur": round(float(x.get("videoDuration") or 0)),
            "at": ts.isoformat(), "caption": (x.get("caption") or "")[:700], "source": source}


def _score(it, now):
    age = max(0.3, (now - dt.datetime.fromisoformat(it["at"])).total_seconds() / 86400)
    return round((it["plays"] + 8 * it["likes"] + 40 * it["comments"]) / age ** 0.6)


def pool(force=False):
    today = dt.date.today().isoformat()
    try:
        cached = json.loads(POOL.read_text())
        if cached.get("date") == today and cached.get("items") and not force:
            print(f"      reel pool: {len(cached['items'])} reels (cached today)", flush=True)
            return cached["items"]
    except Exception:
        pass
    now = dt.datetime.now(dt.timezone.utc)
    items = {}
    try:
        raw = _apify("apify/instagram-hashtag-scraper", {"hashtags": HASHTAGS, "resultsType": "reels", "resultsLimit": PER_TAG})
        for x in raw:
            it = _norm_item(x, "#" + str(x.get("inputUrl", "")).rstrip("/").rsplit("/", 1)[-1])
            if it and it["url"]: items[it["url"]] = it
        print(f"      hashtags: {len(raw)} reels from {len(HASHTAGS)} tags", flush=True)
    except Exception as e:
        print(f"      hashtag scrape failed: {str(e)[:200]}", flush=True)
    # creator accounts: the ones you named + the best-performing English-captioned creators from the hashtags
    ranked = sorted(items.values(), key=lambda i: -_score(i, now))
    auto = []
    for it in ranked:
        if it["owner"] and it["owner"] not in ACCOUNTS + auto and re.search(r"[A-Za-z]{4,}.*\b(the|you|your|this|how|to)\b", it["caption"], re.I):
            auto.append(it["owner"])
        if len(auto) >= AUTO_ACCOUNTS: break
    accounts = ACCOUNTS + auto
    if accounts:
        try:
            raw = _apify("apify/instagram-reel-scraper", {"username": accounts, "resultsLimit": 8, "onlyPostsNewerThan": "21 days", "skipPinnedPosts": True})
            for x in raw:
                it = _norm_item(x, "@" + str(x.get("ownerUsername")))
                if it and it["url"]: items[it["url"]] = it
            print(f"      accounts: {len(raw)} reels from {', '.join('@' + a for a in accounts)}", flush=True)
        except Exception as e:
            print(f"      account scrape failed: {str(e)[:200]}", flush=True)
    out = []
    for it in items.values():
        age = (now - dt.datetime.fromisoformat(it["at"])).days
        if age > 30 or it["dur"] < 12 or len(it["caption"]) < 15: continue
        it["score"] = _score(it, now); out.append(it)
    out.sort(key=lambda i: -i["score"])
    out = out[:80]
    if out:
        POOL.parent.mkdir(parents=True, exist_ok=True)
        POOL.write_text(json.dumps({"date": today, "items": out}, ensure_ascii=False, indent=0))
    elif POOL.exists():  # scrape failed: fall back to the last pool rather than not posting
        out = json.loads(POOL.read_text()).get("items", [])
        print("      using the last saved reel pool", flush=True)
    print(f"      reel pool: {len(out)} reels", flush=True)
    return out


# ---------------------------------------------------------------------------------- 2) pick
def pick(items, recent_topics):
    sysp = (ROOT / "prompts" / "tutorial_picker.md").read_text(encoding="utf-8")
    rows = "\n".join(f"[{i}] @{it['owner']} · {it['plays']:,} views · {it['likes']:,} likes · {it['comments']:,} comments · "
                     f"{it['dur']}s · {it['at'][:10]} · caption: {re.sub(r'\s+', ' ', it['caption'])[:400]}" for i, it in enumerate(items))
    user = (f"TODAY: {dt.date.today()}\n\nRECENTLY COVERED (don't repeat):\n" + ("\n".join(f"- {t}" for t in recent_topics) or "- (nothing yet)")
            + f"\n\nTOP REELS ({len(items)}):\n{rows}\n\nReturn only the JSON.")

    def check(d):
        p = d.get("picks") or []
        if not p: raise ValueError("no picks")
        for x in p:
            if not isinstance(x.get("index"), int) or not 0 <= x["index"] < len(items): raise ValueError(f"bad index {x.get('index')}")
            if not x.get("topic"): raise ValueError("each pick needs a topic")
    return _ask_json(SELECT_MODEL, sysp, user, check)["picks"]


# ---------------------------------------------------------------------------------- 3) transcript
def transcript(url):
    try:
        raw = _apify("apify/instagram-reel-scraper", {"username": [url], "includeTranscript": True}, timeout=240)
        x = raw[0] if raw else {}
        comments = [c.get("text", "") for c in (x.get("latestComments") or [])][:15]
        return (x.get("transcript") or "").strip(), comments
    except Exception as e:
        print(f"      transcript failed: {str(e)[:200]}", flush=True)
        return "", []


# ---------------------------------------------------------------------------------- 4) research (web search)
def research(p, item, tr, comments):
    sysp = (ROOT / "prompts" / "tutorial_research.md").read_text(encoding="utf-8")
    user = (f"TODAY: {dt.date.today()}\nTOPIC WE PLAN: {p['topic']}\nTOOL: {p.get('tool', '')}\nANGLE: {p.get('angle', '')}\n\n"
            f"POPULAR REEL by @{item['owner']} ({item['plays']:,} views)\nCAPTION: {item['caption']}\nTRANSCRIPT: {tr or '(not available)'}\n"
            f"TOP COMMENTS: {' | '.join(comments) or '(none)'}\n\nVerify with web search, then return only the JSON.")
    client = anthropic.Anthropic()
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": int(os.environ.get("RESEARCH_SEARCHES") or 6)}]
    try:
        msgs = [{"role": "user", "content": user}]
        for _ in range(4):   # server tool loop may pause ("pause_turn") on long searches
            resp = client.messages.create(model=RESEARCH_MODEL, max_tokens=6000, system=sysp, messages=msgs, tools=tools)
            if resp.stop_reason != "pause_turn": break
            msgs = [{"role": "user", "content": user}, {"role": "assistant", "content": resp.content}]
        raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        searched = sum(1 for b in resp.content if getattr(b, "type", "") == "server_tool_use")
        m = re.search(r"\{.*\}", raw, re.S)
        notes = json.loads(m.group(0)) if m else {}
        notes["_searched"] = searched
    except Exception as e:
        print(f"      web research unavailable ({str(e)[:160]}); using the transcript only, conservatively", flush=True)
        notes = {"verdict": "adjust", "tool": p.get("tool", ""), "steps": [], "facts": [], "do_not_claim": [],
                 "notes": "Not web-verified: use only general, well-known steps; avoid every number, price and limit.", "_searched": 0}
    return notes


def notes_text(notes, item, tr):
    keep = {k: v for k, v in notes.items() if not k.startswith("_")}
    return json.dumps(keep, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------------------------- checks
HOOK_BANNED = re.compile(r"^(hey|hi\b|hello|welcome|did you know|here'?s how|in today'?s|in this video|\d+\s+(ai\s+)?(tools|apps|hacks|tips|things))", re.I)


def _spoken_text(vo):
    return re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", " ", vo)).strip()


def check_script(d, sources):
    vo = d.get("voiceover") or ""
    if not vo: raise ValueError("missing 'voiceover'")
    first = re.split(r"(?<=[.!?])\s", _spoken_text(vo))[0]
    if HOOK_BANNED.search(first): raise ValueError(f"the hook starts with a banned opener ('{first[:40]}…'); open with the pain, mistake or claim")
    if len(first.split()) > 16: raise ValueError(f"the hook (first sentence) is {len(first.split())} words; keep it ≤ 14")
    n = len(_spoken_text(vo).split())
    if n > MAX_WORDS: raise ValueError(f"the voiceover is {n} words; keep it under {MAX_WORDS} (cut the weakest line)")
    if n < 90: raise ValueError(f"the voiceover is only {n} words; aim for 120–160")
    if re.search(r"\b(dm (you|me)|i'?ll (send|dm)|link in (my )?bio)\b", vo, re.I): raise ValueError("don't promise DMs/links")
    fact_check(vo, sources)


def fact_check(text, sources):
    src = _digits(sources) | _scaled(sources) | _word_numbers(sources)
    allowed = src | {str(i) for i in range(0, 11)} | {"30", "60", "24", str(dt.date.today().year)}
    bad = sorted(x for x in _digits(text) if x not in allowed)
    if bad: raise FactCheckError(f"numbers not in the research notes: {', '.join(bad)} — remove them or use only numbers from the notes")


TYPES = {"pill": ["text"], "label": ["text"], "headline": ["text"], "stat_row": ["cards"], "big_number": ["value"], "split_bar": ["parts"],
         "vs": ["left", "right"], "arrow_pair": ["left", "right"], "strike_list": ["items"], "steps": ["items"], "title_slam": ["text"],
         "illustration": ["name"], "prompt": ["text"], "keys": ["keys"], "toggle": ["text"], "app": ["name"], "before_after": ["left", "right"],
         "screen": ["steps"], "footage": ["media"]}

VIEW_LABELS = lambda v: ([*(v.get("sidebar") or [])] + list(v.get("input_buttons") or []) + list(v.get("top_buttons") or []) + ([v["profile"]] if v.get("profile") else []) + (["input"] if "input" in v else [])
                         + list((v.get("menu") or {}).get("items") or []) + list((v.get("panel") or {}).get("nav") or [])
                         + [r.get("label", "") for r in (v.get("panel") or {}).get("rows") or []] + (["back"] if (v.get("panel") or {}).get("back") else []))


def _norm_label(x):
    return re.sub(r"[^a-z0-9]+", "", str(x).lower()) or str(x).strip()


def check_screen(e, bad):
    steps = e.get("steps") or []
    if not 1 <= len(steps) <= 7: bad.append("screen needs 1–7 steps"); return
    if e.get("device") not in ("web", "phone"): bad.append("screen.device must be web or phone")
    for k, st in enumerate(steps):
        v = st.get("view")
        if not isinstance(v, dict) or not v: bad.append(f"screen step {k + 1} needs a view"); continue
        if "at" not in st: bad.append(f"screen step {k + 1} needs 'at'")
        a = st.get("action")
        if a:
            labels = [_norm_label(x) for x in VIEW_LABELS(v)]
            t = _norm_label(a.get("target"))
            if not t or not any(t == l or l.startswith(t) or t.startswith(l) for l in labels if l):
                bad.append(f"screen step {k + 1}: action target '{a.get('target')}' is not a label in that step's view ({', '.join(VIEW_LABELS(v))[:160]})")
            if a.get("kind") not in ("click", "type", "toggle", "point"): bad.append(f"screen step {k + 1}: action.kind must be click/type/toggle/point")
            if a.get("kind") == "type" and not a.get("text"): bad.append(f"screen step {k + 1}: type needs text")


def _catalog():
    return json.loads((ROOT / "remotion" / "illustrations.json").read_text())


def check_plan(d, voiceover, sources, media_ids=()):
    for k in ("scenes", "cta"):
        if not d.get(k): raise ValueError(f"missing '{k}'")
    cat = set(_catalog()); bad = []
    for i, sc in enumerate(d["scenes"]):
        if not sc.get("elements"): bad.append(f"scene {i + 1} has no elements")
        for e in sc.get("elements", []):
            t = e.get("type")
            if t not in TYPES: bad.append(f"unknown element type '{t}'"); continue
            for f in TYPES[t]:
                if f not in e: bad.append(f"{t} needs '{f}'")
            if "at" not in e and t != "stat_row": bad.append(f"{t} needs 'at'")
            if t in ("vs", "arrow_pair", "before_after") and "at" not in (e.get("right") or {}): bad.append(f"{t}.right needs 'at'")
            if t == "illustration" and e.get("name") not in cat: bad.append(f"illustration '{e.get('name')}' is not in the list")
            if t == "keys" and not (isinstance(e.get("keys"), list) and 1 <= len(e["keys"]) <= 4): bad.append("keys needs 1–4 keys")
            if t == "prompt" and len(e.get("text", "")) > 120: bad.append("prompt text must be ≤ 120 characters")
            if t == "screen": check_screen(e, bad)
            if t == "footage" and e.get("media") not in media_ids:
                bad.append(f"footage media '{e.get('media')}' is not in AVAILABLE MEDIA ({', '.join(media_ids) or 'none'})")

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "ill" and isinstance(v, str) and v not in cat: bad.append(f"illustration '{v}' is not in the list")
                    else: walk(v)
            elif isinstance(o, list):
                for x in o: walk(x)
        walk(sc.get("elements", []))
    if bad: raise ValueError("; ".join(dict.fromkeys(bad))[:900])
    _check_cues({"scenes": d["scenes"], "cold_open": [d["cta"]]}, voiceover)
    fact_check(json.dumps(d["scenes"], ensure_ascii=False), sources + " " + voiceover)


# ---------------------------------------------------------------------------------- 5) script, 6) edit
def write(p, item, notes, tr):
    sources = notes_text(notes, item, tr)
    sysp = (ROOT / "prompts" / "tutorial_writer.md").read_text(encoding="utf-8").replace("{HANDLE}", HANDLE)
    user = (f"TOPIC: {p['topic']}\nTOOL: {notes.get('tool') or p.get('tool', '')}\nFORMAT: {p.get('format', 'tutorial')}\n"
            f"ANGLE (use it or improve it; negative is fine if TRUE): {p.get('angle', '')}\n\n"
            f"RESEARCH NOTES (the only facts, steps and numbers you may use):\n{sources}\n\n"
            f"FOR INSPIRATION ONLY — the popular reel's transcript (don't copy its wording; don't trust facts that aren't in the notes):\n"
            f"{(tr or item['caption'])[:2500]}\n\nReturn only the JSON.")
    return _ask_json(SCRIPT_MODEL, sysp, user, lambda d: check_script(d, sources)), sources


def footage(script, notes, workdir, extra=()):
    """Official image/logo of the tool + 2 Pexels clips for the writer's b-roll ideas (+ any of the owner's own recordings)."""
    from pipeline import media
    h = script.get("media_hints") or {}
    if isinstance(h, list): h = h[0] if h else {}
    from pipeline import broll
    out = list(extra) + broll.items()
    try:
        out += media.collect([{"story": 1, "company": notes.get("tool") or "", "domain": h.get("domain") or "", "broll": h.get("broll") or []}],
                             [{"urls": notes.get("sources") or []}], workdir, raw=False)
    except Exception as e:
        print(f"      (footage step failed, continuing without: {str(e)[:150]})", flush=True)
    return [m for m in out if m["kind"] in ("image", "video")]


def edit(script, p, sources, notes=None, media=(), note=""):
    example = json.loads((ROOT / "prompts" / "tutorial_example.json").read_text(encoding="utf-8"))
    groups = {}
    for name, g in _catalog().items(): groups.setdefault(g, []).append(name)
    ill = "\n".join(f"- {g}: " + ", ".join(sorted(v)) for g, v in sorted(groups.items()))
    sysp = (ROOT / "prompts" / "tutorial_editor.md").read_text(encoding="utf-8").replace("{ILLUSTRATIONS}", ill) \
        .replace("{EXAMPLE}", json.dumps(example, ensure_ascii=False)) \
        .replace("{SCREEN_EXAMPLE}", (ROOT / "prompts" / "tutorial_screen_example.json").read_text(encoding="utf-8"))
    ids = [m["id"] for m in media]
    menu = "\n".join(f"- {m['id']} ({m['kind']}): {m['desc']}" for m in media) or "- (none)"
    ui = json.dumps((notes or {}).get("ui") or {}, ensure_ascii=False)
    user = (f"REEL TOPIC: {p['topic']} (tool: {p.get('tool', '')})\n\nUI NOTES (for screen recreations): {ui}\n"
            f"WHAT THE VIEWER SHOULD SEE: {(notes or {}).get('visuals', '')}\n\nAVAILABLE MEDIA:\n{menu}\n\n"
            f"{note}VOICEOVER (already recorded — cue words must match it exactly):\n{script['voiceover']}\n\nReturn only the JSON.")
    return _ask_json(EDIT_MODEL, sysp, user, lambda d: check_plan(d, script["voiceover"], sources, ids), attempts=4)


def make_plan(recent_topics, skip_urls=(), workdir="out/media", on_manual=None):
    """Returns the full plan. Tries the picks in order until one survives research + fact-check.
    If the editor says a pick needs a real recording, on_manual(plan) files the request and the next pick is tried."""
    print("[1/6] top AI & tech reels", flush=True)
    items = [i for i in pool() if i["url"] not in set(skip_urls)]
    if not items: raise RuntimeError("no reels to learn from (Apify scrape empty)")
    print("[2/6] picking the topic", flush=True)
    picks = pick(items[:60], recent_topics)
    for p in picks[:3]:
        item = items[p["index"]]
        print(f"      → {p['topic']}  ({p.get('format')}, from @{item['owner']}, {item['plays']:,} views) — {p.get('why', '')[:160]}", flush=True)
        tr, comments = transcript(item["url"])
        print(f"[3/6] research ({len(tr.split())} transcript words)", flush=True)
        notes = research(p, item, tr, comments)
        print(f"      verdict {notes.get('verdict')} · {notes.get('_searched', 0)} web searches · {len(notes.get('steps') or [])} steps · "
              f"{len(notes.get('sources') or [])} sources", flush=True)
        if notes.get("verdict") == "reject":
            print(f"      rejected: {notes.get('notes', '')[:200]}", flush=True); continue
        try:
            print("[4/6] script + edit", flush=True)
            script, sources = write(p, item, notes, tr)
            media = footage(script, notes, workdir)
            plan = edit(script, p, sources, notes, media)
        except FactCheckError as e:
            print(f"      couldn't write it cleanly ({str(e)[:200]}); next pick", flush=True); continue
        full = {**script, **plan, "media": media, "sources_text": sources, "style": "hisaab", "topic": p["topic"], "pick": p,
                "inspired_by": {k: item[k] for k in ("url", "owner", "plays", "likes", "comments")},
                "research": {k: v for k, v in notes.items()}, "models": {"pick": SELECT_MODEL, "research": RESEARCH_MODEL, "script": SCRIPT_MODEL, "edit": EDIT_MODEL}}
        if plan.get("manual_request") and on_manual:
            print(f"      needs a real recording: {plan['manual_request'].get('why', '')[:160]} -> asking the owner, next pick", flush=True)
            on_manual(full); continue
        return full
    raise RuntimeError("none of the 3 picks survived research and fact-checking")
