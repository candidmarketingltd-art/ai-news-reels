"""Gather the latest AI news.

Two kinds of input, merged into one candidate list:
  1. Google Trends "Trending now" RSS, polled across many countries (Google has no worldwide feed, so we
     build one: an AI story trending in 5 countries beats one trending in 1). This is the importance signal.
  2. AI news RSS feeds from major outlets + official AI-lab blogs. These catch stories that matter to
     AI followers before (or without) becoming a mass-search trend, and give direct article links.

Then `fetch_articles` pulls the article text for the stories the editor picks, so the script writer and the
fact-checker work from real reporting, not just headlines.
"""
import datetime as dt, email.utils, hashlib, html, json, os, re
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET
import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}
HT = "{https://trends.google.com/trending/rss}"

# Countries polled for Google Trends (variable TREND_GEOS overrides). A broad, English-heavy mix plus big AI markets.
GEOS = [g.strip().upper() for g in (os.environ.get("TREND_GEOS") or
        "US,GB,IN,CA,AU,IE,NZ,SG,PH,MY,ZA,NG,KE,AE,SA,DE,FR,NL,ES,IT,SE,PL,JP,KR,TW,HK,ID,BR,MX,AR").split(",") if g.strip()]

FEEDS = [u.strip() for u in (os.environ.get("NEWS_FEEDS") or "\n".join([
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://venturebeat.com/category/ai/feed/",
    "https://arstechnica.com/ai/feed/",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "https://the-decoder.com/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://openai.com/news/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://deepmind.google/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://www.engadget.com/rss.xml",
])).replace(",", "\n").split("\n") if u.strip()]

# Pre-filter only. Claude makes the real "is this AI news, and does it matter" call.
AI_RE = re.compile(r"""(\bA\.?I\b|\bAGI\b|artificial intelligence|machine learning|\bLLMs?\b|chatbot|generative|
    \bGPT[- ]?\d|ChatGPT|OpenAI|Sam Altman|Anthropic|\bClaude\b|Gemini|DeepMind|Demis Hassabis|Copilot|\bGrok\b|\bxAI\b|
    Llama|Meta AI|Mistral|DeepSeek|Qwen|Kimi|Moonshot|Perplexity|Sora|\bVeo\b|Midjourney|Stable Diffusion|Runway|
    ElevenLabs|Hugging ?Face|Nvidia|Jensen Huang|\bTPU\b|data ?cent(?:er|re)|humanoid|robotaxi|Waymo|Tesla Optimus|
    deepfake|neural|Apple Intelligence|Siri|Alexa\+|Cursor|agentic|AI agents?)""", re.I | re.X)


def _get(url, timeout=25):
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.content


def _when(s):
    try:
        return email.utils.parsedate_to_datetime(s).astimezone(dt.timezone.utc)
    except Exception:
        try:
            return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
        except Exception:
            return None


def _traffic(s):
    """'200+' -> 200, '20K+' -> 20000, '2M+' -> 2000000."""
    m = re.match(r"([\d.]+)\s*([KM]?)", (s or "").replace(",", ""), re.I)
    if not m: return 0
    return int(float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6}[m.group(2).upper()])


def _clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def sid(url, title=""):
    base = (url or "").split("?")[0].rstrip("/").lower() or title.lower()
    return hashlib.sha1(base.encode()).hexdigest()[:10]


# ----------------------------------------------------------------------------- Google Trends
def trends_geo(geo):
    root = ET.fromstring(_get(f"https://trends.google.com/trending/rss?geo={geo}"))
    out = []
    for it in root.iter("item"):
        news = [{"title": _clean(n.findtext(f"{HT}news_item_title")), "url": (n.findtext(f"{HT}news_item_url") or "").strip(),
                 "source": _clean(n.findtext(f"{HT}news_item_source"))} for n in it.findall(f"{HT}news_item")]
        out.append({"query": _clean(it.findtext("title")), "traffic": _traffic(it.findtext(f"{HT}approx_traffic")),
                    "time": _when(it.findtext("pubDate") or ""), "news": news, "geo": geo})
    return out


def trends():
    """AI-related trending searches across countries, merged by search term."""
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda g: _safe(trends_geo, g), GEOS))
    merged = {}
    for geo, items in zip(GEOS, res):
        for it in items or []:
            blob = it["query"] + " " + " ".join(n["title"] for n in it["news"])
            if not AI_RE.search(blob): continue
            k = it["query"].lower()
            m = merged.setdefault(k, {"query": it["query"], "geos": [], "traffic": 0, "news": {}, "time": it["time"]})
            m["geos"].append(geo); m["traffic"] += it["traffic"]
            for n in it["news"]:
                if n["url"]: m["news"].setdefault(n["url"], n)
            if it["time"] and (not m["time"] or it["time"] > m["time"]): m["time"] = it["time"]
    ok = sum(1 for r in res if r is not None)
    print(f"      trends: {ok}/{len(GEOS)} countries read, {len(merged)} AI-related trending searches", flush=True)
    return sorted(merged.values(), key=lambda m: (len(m["geos"]), m["traffic"]), reverse=True)


# ----------------------------------------------------------------------------- news feeds
def feed(url):
    root = ET.fromstring(_get(url))
    out = []
    atom = "{http://www.w3.org/2005/Atom}"
    items = root.findall(".//item") or root.findall(f".//{atom}entry")
    src = _clean(root.findtext("channel/title") or root.findtext(f"{atom}title") or url.split("/")[2])
    for it in items[:40]:
        link = it.findtext("link") or ""
        if not link.strip():
            le = it.find(f"{atom}link"); link = le.get("href") if le is not None else ""
        desc = it.findtext("description") or it.findtext(f"{atom}summary") or it.findtext(f"{atom}content") or ""
        out.append({"title": _clean(it.findtext("title") or it.findtext(f"{atom}title")), "url": link.strip(),
                    "summary": _clean(desc)[:600], "source": src,
                    "time": _when(it.findtext("pubDate") or it.findtext(f"{atom}published") or it.findtext(f"{atom}updated") or "")})
    return out


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print(f"      ({fn.__name__} {a[0] if a else ''} failed: {str(e)[:100]})", flush=True)
        return None


def feeds(since):
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda u: _safe(feed, u), FEEDS))
    items = []
    for r in res:
        for it in r or []:
            if it["time"] and it["time"] < since: continue
            if not it["time"]: continue
            blob = it["title"] + " " + it["summary"]
            # lab blogs are always AI; general tech feeds are filtered
            if AI_RE.search(blob) or any(k in it["url"] for k in ("openai.com", "deepmind", "blog.google/technology/ai", "huggingface.co")):
                items.append(it)
    print(f"      feeds: {sum(1 for r in res if r is not None)}/{len(FEEDS)} read, {len(items)} AI stories in window", flush=True)
    return items


# ----------------------------------------------------------------------------- candidates
def candidates(lookback_hours=8, covered=()):
    """Everything the editor gets to choose from, newest/most-trending first.
    Each candidate: id, headline, source, url, time, summary, trend {geos, traffic, query} (or None), links[]."""
    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(hours=lookback_hours)
    covered = set(covered)
    out = {}
    for t in trends():
        if t["time"] and t["time"] < now - dt.timedelta(hours=lookback_hours + 16):  # trending items linger; allow a day
            continue
        news = list(t["news"].values())
        if not news: continue
        first = news[0]
        c = {"id": sid(first["url"], first["title"]), "headline": first["title"], "source": first["source"], "url": first["url"],
             "time": t["time"].isoformat() if t["time"] else "", "summary": " | ".join(n["title"] + f" ({n['source']})" for n in news[1:4]),
             "trend": {"query": t["query"], "countries": t["geos"], "approx_searches": t["traffic"]},
             "links": [n["url"] for n in news[:4]]}
        if c["id"] not in covered: out[c["id"]] = c
    for f in feeds(since):
        c = {"id": sid(f["url"], f["title"]), "headline": f["title"], "source": f["source"], "url": f["url"],
             "time": f["time"].isoformat(), "summary": f["summary"][:400], "trend": None, "links": [f["url"]]}
        if c["id"] not in covered and c["id"] not in out: out[c["id"]] = c
    lst = sorted(out.values(), key=lambda c: (len((c["trend"] or {}).get("countries", [])), c["time"]), reverse=True)
    return lst[:int(os.environ.get("MAX_CANDIDATES") or 60)]


# ----------------------------------------------------------------------------- article text
def article_text(url):
    try:
        import trafilatura
        raw = _get(url, timeout=30).decode("utf-8", "ignore")
        txt = trafilatura.extract(raw, include_comments=False, include_tables=False, favor_precision=True) or ""
    except Exception as e:
        print(f"      (article {url[:80]} unreadable: {str(e)[:80]})", flush=True)
        return ""
    return re.sub(r"\n{3,}", "\n\n", txt).strip()[:7000]


def fetch_articles(stories, by_id):
    """For each picked story, read up to 3 articles. Returns the source pack: list of {headline, source, url, text}."""
    jobs = []
    for st in stories:
        urls = []
        for cid in st.get("candidate_ids", []):
            c = by_id.get(cid)
            if c: urls += [u for u in c["links"] if u not in urls]
        jobs.append((st, urls[:3]))
    pack = []
    with ThreadPoolExecutor(6) as ex:
        for st, urls in jobs:
            texts = list(ex.map(article_text, urls))
            heads = [by_id[c] for c in st.get("candidate_ids", []) if c in by_id]
            base = "\n".join(f"HEADLINE: {h['headline']} ({h['source']})\nSUMMARY: {h['summary']}" for h in heads)
            body = "\n\n".join(f"ARTICLE ({u}):\n{t}" for u, t in zip(urls, texts) if len(t) > 300)
            pack.append({"story": st.get("headline", ""), "urls": urls, "text": (base + "\n\n" + body).strip(),
                         "articles_read": sum(1 for t in texts if len(t) > 300)})
    return pack


if __name__ == "__main__":  # quick look: python -m pipeline.news
    cs = candidates()
    print(json.dumps(cs[:15], indent=1, ensure_ascii=False))
