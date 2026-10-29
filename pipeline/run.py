"""One run = one news check (every 6 hours):
gather AI news (Google Trends worldwide + AI news feeds) -> Claude decides single / roundup / skip ->
read the articles -> Sonnet writes the script -> Opus edits the video -> fact-check -> voice -> render -> post.

python -m pipeline.run              # normal scheduled run
python -m pipeline.run --dry-run    # everything except posting
"""
import csv, datetime as dt, json, os, sys, tempfile, traceback
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import news, script_writer, voice, publish, media  # noqa: E402
from pipeline.render import engine, audio  # noqa: E402

OUT = ROOT / "out"; PLANS = ROOT / "logs" / "plans"
RUNLOG = ROOT / "logs" / "runs.csv"
COVERED = ROOT / "logs" / "covered.json"
EPISODE = ROOT / "logs" / "episode.json"
SLOTS = ROOT / "logs" / "slots.json"
MUST_POST = (os.environ.get("MUST_POST") or "1") != "0"          # 1 reel every 6 hours = 4 a day
WIDEN = [int(x) for x in (os.environ.get("WIDEN_HOURS") or "24,48").split(",") if x.strip()]
MAX_TRIES = 3


SLOT_HOURS = int(os.environ.get("SLOT_HOURS") or 2)                 # 2 -> 12 reels a day
ROTATION = [t.strip() for t in (os.environ.get("TOPIC_ROTATION") or "ai,tech").split(",") if t.strip()]


def slot_key(now=None):
    """The window this run belongs to (IST). Windows are SLOT_HOURS long and start at 01:00 IST
    (2h: 01–03, 03–05, … 23–01 → 12 a day)."""
    now = now or dt.datetime.now(IST)
    shifted = now - dt.timedelta(hours=1)
    return f"{shifted:%Y-%m-%d}-{shifted.hour // SLOT_HOURS:02d}"


def slot_topic(key):
    """Alternate topics by window: ai, tech, ai, tech, … (TOPIC_ROTATION); TOPIC overrides."""
    if os.environ.get("TOPIC"): return os.environ["TOPIC"]
    return ROTATION[int(key.rsplit("-", 1)[1]) % len(ROTATION)]


def load_slots():
    try: return json.loads(SLOTS.read_text())
    except Exception: return {}


def save_slot(key, info):
    sl = load_slots(); sl[key] = info
    keep = sorted(sl)[-200:]                      # ~2 weeks
    SLOTS.parent.mkdir(parents=True, exist_ok=True)
    SLOTS.write_text(json.dumps({k: sl[k] for k in keep}, indent=1))
IST = ZoneInfo("Asia/Kolkata")
LOOKBACK = int(os.environ.get("LOOKBACK_HOURS") or 8)   # a little more than the 6-hour cadence, so nothing falls between runs


class _Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, x):
        for st in self.streams: st.write(x)
    def flush(self):
        for st in self.streams: st.flush()


def load_covered():
    try:
        items = json.loads(COVERED.read_text(encoding="utf-8"))
    except Exception:
        items = []
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat()
    return [x for x in items if x.get("at", "") >= cutoff]


def save_covered(items):
    COVERED.parent.mkdir(parents=True, exist_ok=True)
    COVERED.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def log(decision, status, note=""):
    RUNLOG.parent.mkdir(parents=True, exist_ok=True)
    new = not RUNLOG.exists()
    with open(RUNLOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(["run_at_ist", "decision", "stories", "status", "note"])
        w.writerow([dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M"), decision.get("decision", ""),
                    " || ".join(f"{s.get('headline', '')} [{s.get('importance', '')}]" for s in decision.get("stories", [])),
                    status, note])


def caption_of(plan):
    cap = plan.get("ig_caption") or "AI news"
    tags = " ".join(plan.get("hashtags", []) or ["#AI", "#AInews"])
    return f"{cap}\n\n{tags}"[:2150]


def make_reel(plan, stamp, workdir):
    print("[4/6] voice", flush=True)
    mp3 = f"{workdir}/vo.mp3"
    words, model = voice.synthesize(plan["voiceover"], mp3)
    dur = max(e for _, _, e in words) + 0.1
    print(f"      {len(words)} words, {dur:.1f}s, voice {model}", flush=True)
    print("[5/6] render", flush=True)
    vid_only = f"{workdir}/video_only.mp4"
    cues = engine.render(plan, words, dur, vid_only)
    cues["music"] = bool(audio.theme_path())
    sfx = f"{workdir}/sfx.wav"; audio.build_sfx(cues, sfx)
    OUT.mkdir(exist_ok=True)
    final = str(OUT / f"{stamp}.mp4")
    audio.mix(vid_only, mp3, sfx, final, workdir, music_start=cues["open_end"])
    return final


def post(mp4, caption, stamp):
    if (os.environ.get("POSTING_MODE") or "buffer").lower() == "buffer":
        from pipeline import buffer
        url = buffer.host_video(mp4, f"reel-{stamp}")
        if (os.environ.get("BUFFER_MODE") or "").lower() == "queue":
            return buffer.add_to_queue(url, caption), url
        return buffer.publish_soon(url, caption), url
    return publish.publish_reel(mp4, caption)


def main():
    (ROOT / "logs").mkdir(exist_ok=True)
    _log = open(ROOT / "logs" / "last_run.log", "w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, _log); sys.stderr = _Tee(sys.__stderr__, _log)
    dry = "--dry-run" in sys.argv or os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "BUFFER_API_KEY", "BUFFER_CHANNEL_ID", "IG_HANDLE", "PEXELS_API_KEY"):
        print(f"  {k}: {'set' if os.environ.get(k) else 'MISSING'}", flush=True)
    stamp = dt.datetime.now(IST).strftime("%Y-%m-%d_%H%M")
    key = slot_key()
    if os.environ.get("SLOT_GUARD") == "1" and load_slots().get(key, {}).get("status") == "posted" and not dry:
        print(f"slot {key} already has its reel ({load_slots()[key].get('at')}) — nothing to do"); return
    topic = slot_topic(key)
    print(f"slot {key} | topic={topic} ({news.TOPICS.get(topic, topic)}) | must_post={MUST_POST} | dry_run={dry}", flush=True)
    covered = load_covered()
    skip_ids = {c["id"] for c in covered}
    recent = [c["headline"] for c in covered if c.get("at", "") >= (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)).isoformat()]
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    def mark(decision, status):
        for st in decision["stories"]:
            for cid in st.get("candidate_ids", []):
                covered.append({"id": cid, "headline": st["headline"], "at": now, "status": status})
        save_covered(covered)

    # find news: normal window first, then widen (24h, 48h) so a reel is always possible
    plan = decision = None
    for hours in [LOOKBACK] + (WIDEN if MUST_POST else []):
        print(f"[1/6] news — last {hours}h", flush=True)
        cands = news.candidates(hours, skip_ids, topic=topic)
        if not cands:
            print("      nothing new in this window", flush=True); continue
        by_id = {c["id"]: c for c in cands}
        for attempt in range(MAX_TRIES):
            pool = [c for c in cands if c["id"] not in skip_ids]
            if not pool: break
            print(f"[2/6] editor — {len(pool)} candidates (attempt {attempt + 1})", flush=True)
            decision = script_writer.select(pool, recent, must_post=MUST_POST, topic=topic)
            print(f"      decision: {decision['decision']} — {decision.get('reason', '')}", flush=True)
            for st in decision.get("stories", []):
                print(f"      • [{st.get('importance')}] {st['headline']}", flush=True)
            if decision["decision"] == "skip": break
            print("[3/6] reading articles + writing script", flush=True)
            pack = news.fetch_articles(decision["stories"], by_id)
            for p in pack:
                print(f"      {p['articles_read']} article(s) read for: {p['story']}", flush=True)
            try:
                mdir = str(OUT / "media" / stamp)
                plan = script_writer.write(decision, pack, topic=topic,
                                           get_media=lambda script: media.collect(script.get("media_hints"), pack, mdir)); break
            except script_writer.FactCheckError as e:
                # couldn't write it without unsupported facts -> drop these stories and pick the next best
                print("      fact-check failed, trying the next best story:", str(e)[:200], flush=True)
                log(decision, "skipped_factcheck", str(e)[:300])
                for st in decision["stories"]: skip_ids.update(st.get("candidate_ids", []))
                if not dry: mark(decision, "skipped_factcheck")
                decision = None
        if plan or (decision and decision["decision"] == "skip" and not MUST_POST): break
    if not plan:
        msg = "no usable AI story found in the last %dh" % max([LOOKBACK] + WIDEN)
        print(("::error::" if MUST_POST else "") + msg); log(decision or {}, "skip", msg)
        if MUST_POST and not dry: sys.exit(1)       # red run -> the backup run in this window tries again
        return

    try: ep = json.loads(EPISODE.read_text())["last"] + 1
    except Exception: ep = int(os.environ.get("FIRST_EPISODE") or 1)
    plan["episode"] = ep
    PLANS.mkdir(parents=True, exist_ok=True)
    (PLANS / f"{stamp}.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")

    with tempfile.TemporaryDirectory() as wd:
        try:
            mp4 = make_reel(plan, stamp, wd)
        except Exception as e:
            traceback.print_exc(); log(decision, "error", str(e)[:300]); sys.exit(1)
        caption = caption_of(plan)
        if dry:
            print(f"DRY RUN — reel at {mp4}\n--- caption ---\n{caption}"); log(decision, "dry_run", mp4); return
        print("[6/6] publish", flush=True)
        try:
            pid, link = post(mp4, caption, stamp)
        except Exception as e:
            traceback.print_exc(); log(decision, "publish_error", str(e)[:300]); sys.exit(1)
    mark(decision, "posted")
    EPISODE.write_text(json.dumps({"last": plan["episode"]}))
    save_slot(key, {"status": "posted", "topic": topic, "at": dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M"), "post": str(pid),
                    "decision": decision["decision"], "stories": [st["headline"] for st in decision["stories"]]})
    log(decision, "posted", f"{pid} {link}")
    print(f"POSTED {pid} {link}")


if __name__ == "__main__":
    main()
