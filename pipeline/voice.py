"""ElevenLabs voiceover with word timings (Rohan voice speaking English, Eleven v4 with audio tags).
Falls back to a free Microsoft English voice when ElevenLabs credits run out."""
import base64, os
import requests

API = "https://api.elevenlabs.io/v1"
VOICE = (os.environ.get("ELEVENLABS_VOICE_ID") or "dVIifp6W0jifqeThgNN0")  # "Rohan"
# "Natural" delivery: mid stability lets Rohan sound conversational instead of flat. Set ELEVENLABS_STABILITY="" to send no settings.
STABILITY = os.environ.get("ELEVENLABS_STABILITY", "0.5")
MODELS = [m for m in ((os.environ.get("ELEVENLABS_MODEL") or "eleven_v4"), "eleven_v3", "eleven_multilingual_v2") if m]


def _hdr():
    return {"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}


def _words_from_alignment(al):
    chars, starts, ends = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur, cs, ce, depth = [], "", None, None, 0
    for ch, s, e in zip(chars, starts, ends):
        if ch == "[": depth += 1
        if depth:
            if ch == "]": depth -= 1
            continue
        if ch.isspace():
            if cur: words.append((cur, cs, ce)); cur = ""
            continue
        if not cur: cs = s
        cur += ch; ce = e
    if cur: words.append((cur, cs, ce))
    return [w for w in words if any(c.isalnum() for c in w[0])]


def _stt_words(mp3_path):
    with open(mp3_path, "rb") as f:
        r = requests.post(f"{API}/speech-to-text", headers=_hdr(), data={"model_id": "scribe_v1", "timestamps_granularity": "word"},
                          files={"file": ("vo.mp3", f, "audio/mpeg")}, timeout=300)
    r.raise_for_status()
    out = []
    for w in r.json().get("words", []):
        if w.get("type") == "word" and not w["text"].startswith("["):
            out.append((w["text"], float(w["start"]), float(w["end"])))
    return out


EDGE_VOICE = os.environ.get("EDGE_VOICE") or "en-IN-PrabhatNeural"


def _edge(text, mp3_path):
    """Free Microsoft neural voice (via edge-tts) with word timings. Audio tags are removed."""
    import asyncio, re
    import edge_tts
    clean = re.sub(r"\[[^\]]*\]", " ", text)
    clean = re.sub(r"[ \t]+", " ", clean).strip()
    words = []

    async def go():
        try:
            comm = edge_tts.Communicate(clean, EDGE_VOICE, rate="+6%", boundary="WordBoundary")
        except TypeError:  # older edge-tts versions emit word boundaries by default
            comm = edge_tts.Communicate(clean, EDGE_VOICE, rate="+6%")
        with open(mp3_path, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    s = chunk["offset"] / 1e7; d = chunk["duration"] / 1e7
                    words.append((chunk["text"], s, s + d))
    asyncio.run(go())
    words = [w for w in words if any(c.isalnum() for c in w[0])]
    if len(words) < 20:
        raise RuntimeError("edge-tts returned no word timings")
    return words


def _quota_error(status, body):
    b = body.lower()
    return status in (400, 401, 402, 429) and any(k in b for k in ("quota", "credit", "limit", "subscription", "payment"))


def synthesize(text, mp3_path):
    """Returns (words, voice_used). Uses ElevenLabs (Rohan) while credits last, else the free Microsoft voice."""
    if os.environ.get("VOICE_PROVIDER", "").lower() == "edge" or not os.environ.get("ELEVENLABS_API_KEY"):
        return _edge(text, mp3_path), f"edge:{EDGE_VOICE}"
    try:
        return _eleven(text, mp3_path)
    except QuotaError as e:
        print(f"      ElevenLabs out of credits ({e}) -> using free voice {EDGE_VOICE}", flush=True)
        return _edge(text, mp3_path), f"edge:{EDGE_VOICE}"


class QuotaError(RuntimeError):
    pass


_RESOLVED = {}


def _find_by_name():
    """The configured voice id isn't in this key's workspace -> find the workspace's own voice named ELEVENLABS_VOICE_NAME."""
    want = (os.environ.get("ELEVENLABS_VOICE_NAME") or "Rohan").lower()
    voices = []
    for url, params in ((f"{API.replace('/v1', '/v2')}/voices", {"search": want, "page_size": 100}), (f"{API}/voices", {})):
        r = requests.get(url, headers=_hdr(), params=params, timeout=60)
        if r.status_code == 200:
            voices = r.json().get("voices", []); break
        print(f"      [eleven] list voices {url.split('/')[-2]}: {r.status_code} {r.text[:160]}", flush=True)
    if not voices:
        raise RuntimeError("ElevenLabs: the saved voice id isn't in this workspace and this API key can't list voices. Either give the "
                           "key the 'Voices: Read' permission, or add a GitHub variable ELEVENLABS_VOICE_ID with the Rohan voice's ID.")
    own = [v for v in voices if v.get("category") in ("cloned", "generated", "professional") and not v.get("is_library_voice")]
    match = [v for v in own if v["name"].strip().lower() == want] or [v for v in own if v["name"].lower().startswith(want)] \
        or [v for v in voices if v["name"].strip().lower() == want]
    print("      [eleven] workspace voices: " + ", ".join(f"{v['name']} ({v['voice_id']}, {v.get('category')})" for v in voices[:20]), flush=True)
    if not match:
        raise RuntimeError(f"ElevenLabs: no voice named '{want}' in this workspace")
    print(f"      [eleven] using {match[0]['name']} ({match[0]['voice_id']})", flush=True)
    return match[0]["voice_id"]


def _voice_id():
    """The Rohan voice: ELEVENLABS_VOICE_ID if this key's workspace has it, else the workspace's own voice named "Rohan"."""
    if "id" in _RESOLVED: return _RESOLVED["id"]
    r = requests.get(f"{API}/voices/{VOICE}", headers=_hdr(), timeout=60)
    if r.status_code == 200:
        _RESOLVED["id"] = VOICE; return VOICE
    if r.status_code in (400, 404) or "not_found" in r.text:
        _RESOLVED["id"] = _find_by_name(); return _RESOLVED["id"]
    _RESOLVED["id"] = VOICE      # key can't read voices -> try the configured id; a 404 at TTS time triggers the name lookup
    return VOICE


def _diagnose():
    """Write what this ElevenLabs key can do into the run log (no secrets)."""
    try:
        u = requests.get(f"{API}/user/subscription", headers=_hdr(), timeout=30)
        print(f"      [eleven] subscription: {u.status_code} {u.text[:300]}", flush=True)
        m = requests.get(f"{API}/models", headers=_hdr(), timeout=30)
        ids = [x.get("model_id") for x in m.json()] if m.status_code == 200 else m.text[:200]
        print(f"      [eleven] models: {m.status_code} {ids}", flush=True)
    except Exception as e:
        print(f"      [eleven] diagnose failed: {e}", flush=True)


def _payload(text, model, with_settings=True):
    js = {"text": text, "model_id": model}
    if with_settings and STABILITY not in ("", None):
        js["voice_settings"] = {"stability": float(STABILITY), "similarity_boost": 0.8, "use_speaker_boost": True}
    return js


def _post(url, text, model, **kw):
    """POST with voice settings; if the model rejects the settings, retry once without them."""
    r = requests.post(url, headers=_hdr(), json=_payload(text, model), timeout=600, **kw)
    if r.status_code in (400, 422) and "voice_settings" in _payload(text, model) and not _quota_error(r.status_code, r.text):
        print(f"      [eleven] {model} rejected voice settings ({r.text[:120]}); retrying without", flush=True)
        r = requests.post(url, headers=_hdr(), json=_payload(text, model, False), timeout=600, **kw)
    return r


def _eleven(text, mp3_path):
    last = None
    vid = _voice_id()
    _diagnose()
    for model in MODELS:
        r = _post(f"{API}/text-to-speech/{vid}/with-timestamps", text, model, params={"output_format": "mp3_44100_128"})
        if r.status_code == 404 and "voice_not_found" in r.text and not _RESOLVED.get("looked_up"):
            _RESOLVED["looked_up"] = True
            print(f"      [eleven] voice {vid} isn't in this workspace -> looking for its own Rohan voice", flush=True)
            vid = _RESOLVED["id"] = _find_by_name()
            r = _post(f"{API}/text-to-speech/{vid}/with-timestamps", text, model, params={"output_format": "mp3_44100_128"})
        if r.status_code >= 400:
            last = f"{model}: {r.status_code} {r.text[:300]}"
            print(f"      [eleven] with-timestamps {model}: {r.status_code} {r.text[:200]}", flush=True)
            if _quota_error(r.status_code, r.text): raise QuotaError(last)
            if r.status_code in (400, 404, 422): continue  # model not available for this voice/account -> try next
            r.raise_for_status()
        js = r.json()
        with open(mp3_path, "wb") as f:
            f.write(base64.b64decode(js["audio_base64"]))
        al = js.get("normalized_alignment") or js.get("alignment")
        words = _words_from_alignment(al) if al else []
        if len(words) < 20:  # alignment missing/odd -> transcribe the audio instead
            words = _stt_words(mp3_path)
        return words, model
    for model in MODELS:  # fallback: standard endpoint (no timestamps), timings via speech-to-text
        r = _post(f"{API}/text-to-speech/{vid}", text, model, params={"output_format": "mp3_44100_128"})
        print(f"      [eleven] plain TTS {model}: {r.status_code} {'' if r.ok else r.text[:200]}", flush=True)
        if r.ok:
            with open(mp3_path, "wb") as f: f.write(r.content)
            return _stt_words(mp3_path), model
        last = f"{model}: {r.status_code} {r.text[:300]}"
        if _quota_error(r.status_code, r.text): raise QuotaError(last)
    raise RuntimeError(f"ElevenLabs TTS failed: {last}")
