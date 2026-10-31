"""Reels that need a real screen recording from the owner.

When the editor decides a reel can't be explained with recreated screens or stock footage, the run opens a GitHub issue
("🎥 Recording needed: …") describing exactly what to record, saves the script in logs/pending/, and moves on to another topic.
The owner records it on their phone/computer and drags the video into a comment on that issue. Every later run checks the open
requests first: when a video is there, that reel is edited around the recording, posted, and the issue is closed.
"""
import datetime as dt, json, os, re, subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
PENDING = ROOT / "logs" / "pending"
API = "https://api.github.com"
VIDEO_URL = re.compile(r"https://(?:github\.com/user-attachments/assets/[\w-]+|[^\s)\"']+\.(?:mp4|mov|m4v|webm))", re.I)
MAX_AGE_DAYS = 10


def _repo():
    return os.environ.get("GITHUB_REPOSITORY") or "candidmarketingltd-art/ai-news-reels"


def _h():
    tok = os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"} if tok else {}


def request(plan):
    """Open an issue asking for the recording; keep the plan to finish later."""
    mr = plan.get("manual_request") or {}
    spoken = re.sub(r"\[[^\]]*\]", "", plan["voiceover"]).strip()
    body = (f"**A reel needs a real recording from you.**\n\n**Topic:** {plan['topic']}\n\n**Why:** {mr.get('why', '')}\n\n"
            f"**What to record:**\n{mr.get('what', '')}\n\n"
            "**How:** record it (phone screen recording or computer screen, portrait or landscape, 10–40 s, no audio needed), "
            "then drag the video file into a comment on this issue. The next scheduled run picks it up, edits the reel around it "
            "and posts it. Close this issue to skip the reel.\n\n"
            f"<details><summary>Script</summary>\n\n{spoken}\n\n</details>")
    try:
        r = requests.post(f"{API}/repos/{_repo()}/issues", headers=_h(), timeout=30,
                          json={"title": f"🎥 Recording needed: {plan.get('title') or plan['topic'][:60]}", "body": body, "labels": ["needs-recording"]})
        r.raise_for_status()
        num = r.json()["number"]
    except Exception as e:
        print(f"      (couldn't open the recording request: {str(e)[:160]})", flush=True)
        return None
    PENDING.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in plan.items() if k not in ("media",)}
    (PENDING / f"{num}.json").write_text(json.dumps({"issue": num, "at": dt.datetime.now(dt.timezone.utc).isoformat(), "plan": keep},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"      recording request: issue #{num}", flush=True)
    return num


def _download(url, path):
    for hdr in ({}, _h()):
        try:
            with requests.get(url, headers=hdr, stream=True, timeout=180, allow_redirects=True) as r:
                if r.status_code != 200 or "text/html" in r.headers.get("content-type", ""): continue
                with open(path, "wb") as f:
                    for c in r.iter_content(1 << 20): f.write(c)
                return True
        except Exception:
            continue
    return False


def ready(workdir):
    """Pending requests whose recording has arrived -> [(pending_dict, media_item)]. Drops closed/old requests."""
    out = []
    if not PENDING.exists(): return out
    for f in sorted(PENDING.glob("*.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        num = p["issue"]
        try:
            iss = requests.get(f"{API}/repos/{_repo()}/issues/{num}", headers=_h(), timeout=30).json()
            if iss.get("state") == "closed" or (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(p["at"])).days > MAX_AGE_DAYS:
                print(f"      recording request #{num}: {'closed' if iss.get('state') == 'closed' else 'too old'} — dropped", flush=True)
                f.unlink(); continue
            comments = requests.get(f"{API}/repos/{_repo()}/issues/{num}/comments", headers=_h(), timeout=30).json()
        except Exception as e:
            print(f"      (couldn't check issue #{num}: {str(e)[:120]})", flush=True); continue
        urls = [u for c in comments if isinstance(c, dict) for u in VIDEO_URL.findall(c.get("body") or "")]
        if not urls:
            print(f"      recording request #{num}: still waiting for the video", flush=True); continue
        os.makedirs(workdir, exist_ok=True)
        raw, mp4 = os.path.join(workdir, f"rec{num}_raw"), os.path.join(workdir, f"rec{num}.mp4")
        if not _download(urls[-1], raw):
            print(f"      recording #{num}: couldn't download {urls[-1][:80]}", flush=True); continue
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-an", "-vf", "scale='min(1080,iw)':-2,fps=30", "-c:v", "libx264", "-crf", "20",
                        "-preset", "veryfast", "-pix_fmt", "yuv420p", mp4], check=True)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4],
                                   capture_output=True, text=True).stdout.strip() or 0)
        what = (p["plan"].get("manual_request") or {}).get("what", "")
        out.append((p, {"id": "your_recording", "kind": "video", "path": mp4, "mp4": mp4, "credit": "",
                        "desc": f"the owner's REAL recording ({dur:.0f}s) of: {what[:300]}"}))
        print(f"      recording #{num} arrived ({dur:.0f}s)", flush=True)
    return out


def done(p, link):
    num = p["issue"]
    try:
        requests.post(f"{API}/repos/{_repo()}/issues/{num}/comments", headers=_h(), timeout=30, json={"body": f"Posted ✅ {link}"})
        requests.patch(f"{API}/repos/{_repo()}/issues/{num}", headers=_h(), timeout=30, json={"state": "closed"})
    except Exception:
        pass
    (PENDING / f"{num}.json").unlink(missing_ok=True)
