"""Listen back to the voiceover before it's used: transcribe it (faster-whisper, runs on the GitHub runner) and compare with
the script. Catches mispronounced or swallowed words ("run" heard as "ran", a missing "not") so a bad take is re-recorded."""
import difflib, re

_MODEL = {}
SKIP = {"a", "an", "the", "and", "to", "of", "uh", "um"}


def _norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))


def _num(w):  # "two" vs "2"
    m = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
    return m.get(w, w)


def _same(x, y):
    return x == y or (len(min(x, y, key=len)) >= 2 and (x.startswith(y) or y.startswith(x)))


def _key(w):
    """Rough sound-alike key: macs/max, cs/x, ph/f, double letters, silent final e. Vowels are kept, so run != ran."""
    w = w.replace("'", "")
    for x, y in (("ph", "f"), ("ck", "k"), ("cs", "x"), ("ks", "x"), ("c", "k"), ("z", "s")):
        w = w.replace(x, y)
    w = re.sub(r"(.)\1+", r"\1", w)
    return w[:-1] if len(w) > 3 and w.endswith("e") else w


def _ignorable(sa, sb):
    """Differences that aren't a mispronunciation worth a re-record."""
    toks = sa + sb
    if any(re.search(r"\d", t) for t in toks):          # 8gb / 8 gigabytes, q4km, 27b — whisper writes these its own way
        return True
    if not sa or not sb:                                # one side empty: a long gap is whisper dropping a chunk, not the voice
        return len(sa or sb) > 4
    if len(sa) == len(sb) and all(_same(_key(x), _key(y)) for x, y in zip(sa, sb)):
        return True
    return _key("".join(sa)) == _key("".join(sb))


def check(mp3, script):
    """Returns (mismatches, heard_text). mismatches = [(script_words, heard_words)] for content words that differ."""
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        print(f"      (voice check unavailable: {e})", flush=True); return [], ""
    if "m" not in _MODEL:
        _MODEL["m"] = WhisperModel("base.en", device="cpu", compute_type="int8")
    import subprocess, numpy as np   # decode with ffmpeg (avoids PyAV version issues), 16 kHz mono float
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    segs, _ = _MODEL["m"].transcribe(audio, beam_size=5, initial_prompt=re.sub(r"\[[^\]]*\]", " ", script)[:220])
    heard = " ".join(s.text for s in segs)
    a = [_num(_norm(w)) for w in re.sub(r"\[[^\]]*\]", " ", script).split() if _norm(w)]
    b = [_num(_norm(w)) for w in heard.split() if _norm(w)]
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal": continue
        sa, sb = [w for w in a[i1:i2] if w not in SKIP], [w for w in b[j1:j2] if w not in SKIP]
        if not sa and not sb: continue
        # ignore spelling-only differences ("ok"/"okay", "email"/"emails", "ai"/"a.i.", "wifi"/"wi-fi")
        if sa and sb and len(sa) == len(sb) and all(_same(x, y) for x, y in zip(sa, sb)): continue
        if sa and sb and _same("".join(sa), "".join(sb)): continue
        if _ignorable(sa, sb): continue
        out.append((" ".join(a[i1:i2]), " ".join(b[j1:j2])))
    return out, heard
