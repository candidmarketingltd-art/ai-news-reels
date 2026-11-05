"""Sync the Rohan voice with the current ElevenLabs API key (no speech generated, no credits spent).

1. a known Rohan voice id already usable by this key -> use it
2. a voice named "Rohan" in this key's workspace     -> use it
3. Rohan in the public Voice Library                 -> add it to this workspace, use it
Writes logs/voice_sync.json; pipeline/voice.py reads the id from there.
"""
import datetime as dt, json, os, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "logs" / "voice_sync.json"
API = "https://api.elevenlabs.io/v1"
NAME = (os.environ.get("ELEVENLABS_VOICE_NAME") or "Rohan").strip()
KNOWN = [v for v in (os.environ.get("ELEVENLABS_VOICE_ID"), "IcsYcP26eMwajlgx2SDe", "dVIifp6W0jifqeThgNN0") if v]
H = {"xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "")}


def get(path, **params):
    r = requests.get(f"{API}{path}", headers=H, params=params, timeout=60)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)


def main():
    rep = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "name_wanted": NAME}
    if not H["xi-api-key"]:
        rep["error"] = "ELEVENLABS_API_KEY secret is empty"; return rep
    s, sub = get("/user/subscription")
    rep["subscription"] = ({k: sub.get(k) for k in ("tier", "character_count", "character_limit", "next_character_count_reset_unix", "status")}
                           if s == 200 else f"{s} {str(sub)[:200]}")
    # 1) known ids
    for vid in KNOWN:
        s, v = get(f"/voices/{vid}")
        if s == 200:
            rep.update(voice_id=vid, voice_name=v.get("name"), category=v.get("category"), how="already in this workspace"); return rep
    # 2) workspace voices
    s, d = get("/voices")
    if s == 200:
        voices = d.get("voices", [])
        rep["workspace_voices"] = [f"{v['name']} ({v['voice_id']}, {v.get('category')})" for v in voices][:40]
        m = [v for v in voices if v["name"].strip().lower() == NAME.lower()] or [v for v in voices if v["name"].lower().startswith(NAME.lower())]
        own = [v for v in m if v.get("category") in ("cloned", "generated", "professional")] or m
        if own:
            v = own[0]; rep.update(voice_id=v["voice_id"], voice_name=v["name"], category=v.get("category"), how="found by name in this workspace"); return rep
    else:
        rep["workspace_voices"] = f"{s} {str(d)[:200]} (key may lack 'Voices: Read')"
    # 3) public Voice Library -> add to this workspace
    s, d = get("/shared-voices", search=NAME, page_size=100)
    if s != 200:
        rep["error"] = f"library search failed: {s} {str(d)[:200]}"; return rep
    lib = d.get("voices", [])
    rep["library_matches"] = [f"{v.get('name')} ({v.get('voice_id')}, {v.get('language')}, {v.get('accent')})" for v in lib][:20]
    pick = [v for v in lib if v.get("voice_id") in KNOWN] or [v for v in lib if (v.get("name") or "").strip().lower().startswith(NAME.lower())]
    if not pick:
        rep["error"] = f"no '{NAME}' voice in this workspace or the Voice Library"; return rep
    v = pick[0]
    r = requests.post(f"{API}/voices/add/{v['public_owner_id']}/{v['voice_id']}", headers=H, json={"new_name": NAME}, timeout=60)
    if r.status_code >= 400:
        rep["error"] = f"adding library voice failed: {r.status_code} {r.text[:200]} (key may lack 'Voices: Write')"; return rep
    rep.update(voice_id=r.json().get("voice_id", v["voice_id"]), voice_name=NAME, category="library", how=f"added from Voice Library ({v.get('name')})")
    return rep


if __name__ == "__main__":
    rep = main()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    sys.exit(0 if rep.get("voice_id") else 1)
