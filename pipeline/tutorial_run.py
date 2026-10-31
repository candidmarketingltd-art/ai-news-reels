"""One tutorial reel for @ihackgrowth: top reels → pick → research → script → edit → voice → render (AI HACKS style) → Buffer.

python -m pipeline.tutorial_run              # scheduled run (posts)
python -m pipeline.tutorial_run --dry-run    # everything except posting
"""
import csv, datetime as dt, json, os, sys, tempfile, traceback
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import tutorial, voice, recordings  # noqa: E402
from pipeline.render import remo  # noqa: E402
from pipeline.run import post, _Tee  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
LOGS = ROOT / "logs"
SLOTS = LOGS / "tutorial_slots.json"
COVERED = LOGS / "tutorial_covered.json"
EPISODE = LOGS / "tutorial_episode.json"
RUNLOG = LOGS / "tutorial_runs.csv"
PLANS = LOGS / "plans"
OUT = ROOT / "out"
POST_TIMES = sorted(t.strip() for t in (os.environ.get("POST_TIMES") or "13:00,20:00").split(",") if t.strip())


def slot_key(now=None):
    """Posting windows start at POST_TIMES (IST); a window lasts until the next one. Key = '<date>-<HHMM>'."""
    now = now or dt.datetime.now(IST)
    starts = []
    for d in (now.date() - dt.timedelta(days=1), now.date()):
        for t in POST_TIMES:
            h, m = map(int, t.split(":"))
            starts.append(dt.datetime(d.year, d.month, d.day, h, m, tzinfo=IST))
    s = max(x for x in starts if x <= now)
    return f"{s:%Y-%m-%d-%H%M}"


def _load(p, default):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default


def _save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def log(status, topic="", note=""):
    new = not RUNLOG.exists()
    with open(RUNLOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(["run_at_ist", "topic", "status", "note"])
        w.writerow([dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M"), topic, status, note])


def caption_of(plan):
    tags = " ".join(plan.get("hashtags") or ["#AItools", "#AIhacks"])
    return f"{plan.get('ig_caption') or plan.get('title', '')}\n\n{tags}"[:2150]


def main():
    LOGS.mkdir(exist_ok=True)
    _log = open(LOGS / "last_run.log", "w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, _log); sys.stderr = _Tee(sys.__stderr__, _log)
    dry = "--dry-run" in sys.argv or os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "APIFY_TOKEN", "BUFFER_API_KEY", "BUFFER_CHANNEL_ID"):
        print(f"  {k}: {'set' if os.environ.get(k) else 'MISSING'}", flush=True)
    key = slot_key()
    slots = _load(SLOTS, {})
    if os.environ.get("SLOT_GUARD") == "1" and slots.get(key, {}).get("status") == "posted" and not dry:
        print(f"window {key} already has its reel — nothing to do"); return
    print(f"window {key} | posting times {', '.join(POST_TIMES)} IST | dry_run={dry}", flush=True)

    covered = [c for c in _load(COVERED, []) if c.get("at", "") >= (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()]
    stamp = dt.datetime.now(IST).strftime("%Y-%m-%d_%H%M")
    mdir = str(OUT / "media" / stamp)
    plan, pending = None, None
    try:
        # 1) a reel whose real recording the owner has uploaded goes first
        for pend, rec in recordings.ready(mdir):
            try:
                pl = pend["plan"]
                print(f"[4/6] re-editing '{pl['topic'][:80]}' around your recording", flush=True)
                media = [rec] + tutorial.footage(pl, pl.get("research") or {}, mdir)
                ed = tutorial.edit(pl, pl["pick"], pl.get("sources_text") or "", pl.get("research"), media,
                                   note="The owner recorded a REAL video for this reel (media id `your_recording`). Show it with `footage` "
                                        "(tall: true) for the moments it covers — it replaces any recreation of the same thing. Do not set manual_request.\n\n")
                ed.pop("manual_request", None)
                plan, pending = {**pl, **ed, "media": media}, pend
                plan.pop("manual_request", None)
                break
            except Exception as e:
                print(f"      couldn't use recording #{pend['issue']}: {str(e)[:200]}", flush=True)
        # 2) otherwise a fresh topic (requests a recording if one is needed, then moves on)
        if not plan:
            plan = tutorial.make_plan([c["topic"] for c in covered[-40:]], skip_urls=[c.get("url") for c in covered]
                                      + [json.loads(f.read_text()).get("plan", {}).get("inspired_by", {}).get("url") for f in recordings.PENDING.glob("*.json")],
                                      workdir=mdir, on_manual=None if dry else recordings.request)
    except Exception as e:
        traceback.print_exc(); log("error", "", str(e)[:300]); sys.exit(1)
    ep = _load(EPISODE, {}).get("last", 0) + 1
    plan["episode"] = ep
    PLANS.mkdir(parents=True, exist_ok=True)
    _save(PLANS / f"tutorial_{stamp}.json", {k: v for k, v in plan.items() if k != "sources_text"})

    with tempfile.TemporaryDirectory() as wd:
        try:
            print("[5/6] voice + render", flush=True)
            mp3 = f"{wd}/vo.mp3"
            words, model = voice.synthesize(plan["voiceover"], mp3)
            dur = max(e for _, _, e in words) + 0.1
            print(f"      {len(words)} words, {dur:.1f}s, voice {model}", flush=True)
            OUT.mkdir(exist_ok=True)
            mp4 = str(OUT / f"{stamp}.mp4")
            remo.render(plan, words, dur, mp3, mp4, wd, episode=ep)
        except Exception as e:
            traceback.print_exc(); log("error", plan["topic"], str(e)[:300]); sys.exit(1)
        caption = caption_of(plan)
        if dry:
            print(f"DRY RUN — reel at {mp4}\n--- caption ---\n{caption}"); log("dry_run", plan["topic"], mp4); return
        print("[6/6] publish", flush=True)
        try:
            pid, link = post(mp4, caption, stamp)
        except Exception as e:
            traceback.print_exc(); log("publish_error", plan["topic"], str(e)[:300]); sys.exit(1)
    if pending: recordings.done(pending, link)
    covered.append({"topic": plan["topic"], "url": plan["inspired_by"]["url"], "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    _save(COVERED, covered)
    _save(EPISODE, {"last": ep})
    slots[key] = {"status": "posted", "at": dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M"), "post": str(pid), "topic": plan["topic"]}
    _save(SLOTS, {k: slots[k] for k in sorted(slots)[-120:]})
    log("posted", plan["topic"], f"{pid} {link}")
    print(f"POSTED {pid} {link}")


if __name__ == "__main__":
    main()
