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
from pipeline import news, script_writer, voice, publish  # noqa: E402
from pipeline.render import engine, audio  # noqa: E402

OUT = ROOT / "out"; PLANS = ROOT / "logs" / "plans"
RUNLOG = ROOT / "logs" / "runs.csv"
COVERED = ROOT / "logs" / "covered.json"
EPISODE = ROOT / "logs" / "episode.json"
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
    for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "BUFFER_API_KEY", "BUFFER_CHANNEL_ID", "IG_HANDLE"):
        print(f"  {k}: {'set' if os.environ.get(k) else 'MISSING'}", flush=True)
    stamp = dt.datetime.now(IST).strftime("%Y-%m-%d_%H%M")
    covered = load_covered()

    print(f"[1/6] news — last {LOOKBACK}h | dry_run={dry}", flush=True)
    cands = news.candidates(LOOKBACK, [c["id"] for c in covered])
    if not cands:
        print("no new AI stories found"); log({}, "skip", "no candidates"); return
    by_id = {c["id"]: c for c in cands}

    print(f"[2/6] editor — {len(cands)} candidates", flush=True)
    recent = [c["headline"] for c in covered if c.get("at", "") >= (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)).isoformat()]
    decision = script_writer.select(cands, recent)
    print(f"      decision: {decision['decision']} — {decision.get('reason', '')}", flush=True)
    for s in decision.get("stories", []):
        print(f"      • [{s.get('importance')}] {s['headline']}", flush=True)
    if decision["decision"] == "skip":
        log(decision, "skip", decision.get("reason", "")[:300]); return

    print("[3/6] reading articles + writing script", flush=True)
    pack = news.fetch_articles(decision["stories"], by_id)
    for p in pack:
        print(f"      {p['articles_read']} article(s) read for: {p['story']}", flush=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    def mark(status):
        for s in decision["stories"]:
            for cid in s.get("candidate_ids", []):
                covered.append({"id": cid, "headline": s["headline"], "at": now, "status": status})
        save_covered(covered)

    try:
        plan = script_writer.write(decision, pack)
    except script_writer.FactCheckError as e:
        print("SKIPPED (fact-check):", e); log(decision, "skipped_factcheck", str(e)[:300])
        if not dry: mark("skipped_factcheck")
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
    mark("posted")
    EPISODE.write_text(json.dumps({"last": plan["episode"]}))
    log(decision, "posted", f"{pid} {link}")
    print(f"POSTED {pid} {link}")


if __name__ == "__main__":
    main()
