"""Footage for the reels — only sources that are safe to post:

1. OFFICIAL company visuals: the og:image of the company's own announcement page (found as a link inside the news article,
   or the article itself when it's on the company's site), falling back to the company homepage's share image, plus the
   company logo. Companies publish these for press coverage.
2. STOCK B-ROLL from Pexels (free for commercial use, no attribution required, no Content-ID claims): short portrait clips
   for the visual ideas the script writer suggests ("data center servers", "robot arm", "phone screen").

Deliberately NOT used: clips from company YouTube videos, news-agency photos (Reuters/Getty/AP) or photos of people —
those get reels muted/removed or the account copyright strikes.

Every item is pre-processed for the renderer: images -> PNG, videos -> raw RGB frames at the panel size (memory-mapped by the
renderer), with a short credit line ("Image: openai.com", "Video: Pexels").
"""
import json, os, re, subprocess
from urllib.parse import urljoin, urlparse
import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}
PANEL_W, PANEL_H, FPS = 952, 740, 30   # = render.modern.PANEL size
MAX_CLIP_S = 8.0
# Big photo agencies: their pictures are licensed to the outlet, not to us.
AGENCY = re.compile(r"(gettyimages|reuters|apnews|ap\.org|afp|shutterstock|alamy|epa\.eu|bloomberg|zumapress|sipa)", re.I)


def _get(url, **kw):
    r = requests.get(url, headers=UA, timeout=kw.pop("timeout", 30), **kw)
    r.raise_for_status()
    return r


def _host(u):
    return (urlparse(u).hostname or "").lower().removeprefix("www.")


def _og_image(page_url):
    html = _get(page_url).text
    for pat in (r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
                r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)'):
        m = re.search(pat, html, re.I)
        if m: return urljoin(page_url, m.group(1).replace("&amp;", "&"))
    return None


def _official_pages(domain, article_urls):
    """Pages on the company's own site: the article itself if it's there, else links to it inside the articles."""
    pages = [u for u in article_urls if _host(u).endswith(domain)]
    for u in article_urls:
        if len(pages) >= 3: break
        try:
            html = _get(u).text
        except Exception:
            continue
        for href in re.findall(r'href=["\'](https?://[^"\'#]+)', html):
            h = _host(href)
            if h.endswith(domain) and len(urlparse(href).path) > 3 and not re.search(r"\.(pdf|png|jpe?g|svg|css|js)$", href, re.I):
                if href not in pages: pages.append(href)
            if len(pages) >= 3: break
    return pages + [f"https://{domain}/"]


def _save_image(url, path, min_w=600):
    from PIL import Image
    import io
    if AGENCY.search(url): return False
    r = _get(url, timeout=40)
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    if im.width < min_w: return False
    im.save(path)
    return True


def official_image(domain, article_urls, path):
    for page in _official_pages(domain, article_urls):
        try:
            img = _og_image(page)
            if img and _save_image(img, path):
                return page
        except Exception as e:
            print(f"      (media: {page[:70]} -> {str(e)[:80]})", flush=True)
    return None


def logo(domain, path):
    from PIL import Image
    import io
    for url in (f"https://www.google.com/s2/favicons?domain={domain}&sz=256", f"https://icons.duckduckgo.com/ip3/{domain}.ico"):
        try:
            im = Image.open(io.BytesIO(_get(url).content)).convert("RGBA")
            if im.width >= 64:
                im.save(path); return True
        except Exception:
            pass
    return False


def pexels_video(query, path, used):
    key = os.environ.get("PEXELS_API_KEY")
    if not key: return None
    r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key},
                     params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 8}, timeout=30)
    r.raise_for_status()
    for v in r.json().get("videos", []):
        if v["id"] in used or v.get("duration", 0) < 4: continue
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")]
        files = [f for f in files if f["height"] >= f["width"]] or files
        if not files: continue
        f = min(files, key=lambda f: abs(f["height"] - 1280))          # ~720p portrait is plenty for the panel
        with requests.get(f["link"], headers=UA, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(path, "wb") as out:
                for chunk in resp.iter_content(1 << 20): out.write(chunk)
        used.add(v["id"])
        return {"pexels_id": v["id"], "by": (v.get("user") or {}).get("name", ""), "page": v.get("url", "")}
    return None


def to_raw(mp4, raw):
    """Decode up to MAX_CLIP_S of a clip, cover-cropped to the panel, as raw RGB frames. Returns the frame count."""
    vf = (f"fps={FPS},scale={PANEL_W}:{PANEL_H}:force_original_aspect_ratio=increase,"
          f"crop={PANEL_W}:{PANEL_H},eq=saturation=0.9:contrast=1.05")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-t", str(MAX_CLIP_S), "-an", "-vf", vf,
                    "-f", "rawvideo", "-pix_fmt", "rgb24", raw], check=True)
    return os.path.getsize(raw) // (PANEL_W * PANEL_H * 3)


def collect(hints, pack, workdir):
    """hints: script writer's `media_hints` [{story, company, domain, broll: [...]}]; pack: news.fetch_articles() output.
    Returns the media list the video editor can use: [{id, kind, path, frames?, credit, desc}]."""
    os.makedirs(workdir, exist_ok=True)
    out, used = [], set()
    for h in hints or []:
        n = int(h.get("story") or 1)
        urls = (pack[n - 1]["urls"] if 0 < n <= len(pack) else [])
        dom = _host("https://" + str(h.get("domain") or "").strip().removeprefix("https://").removeprefix("http://").split("/")[0])
        company = h.get("company") or dom
        if dom and "." in dom:
            p = os.path.join(workdir, f"s{n}_image.png")
            try:
                page = official_image(dom, urls, p)
                if page:
                    out.append({"id": f"s{n}_image", "kind": "image", "path": p, "credit": f"Image: {dom}",
                                "desc": f"official image from {company} ({'announcement page' if page.rstrip('/') != 'https://' + dom else 'homepage'})"})
            except Exception as e:
                print(f"      (media: no official image for {dom}: {str(e)[:80]})", flush=True)
            p = os.path.join(workdir, f"s{n}_logo.png")
            if logo(dom, p):
                out.append({"id": f"s{n}_logo", "kind": "logo", "path": p, "credit": "", "desc": f"{company} logo"})
        for k, q in enumerate((h.get("broll") or [])[:2]):
            mp4 = os.path.join(workdir, f"s{n}_broll{k + 1}.mp4")
            try:
                info = pexels_video(q, mp4, used)
                if not info: continue
                raw = mp4[:-4] + ".rgb"
                frames = to_raw(mp4, raw)
                if frames < FPS * 2: continue
                out.append({"id": f"s{n}_broll{k + 1}", "kind": "video", "path": raw, "frames": frames, "credit": "Video: Pexels",
                            "desc": f"stock video: {q} ({frames / FPS:.0f}s) — generic, NOT the company's own footage"})
            except Exception as e:
                print(f"      (media: pexels '{q}' failed: {str(e)[:80]})", flush=True)
    print(f"      media: {', '.join(m['id'] for m in out) or 'none'}", flush=True)
    return out


if __name__ == "__main__":   # python -m pipeline.media openai.com "data center"
    import sys
    print(json.dumps(collect([{"story": 1, "company": sys.argv[1], "domain": sys.argv[1], "broll": sys.argv[2:]}],
                             [{"urls": []}], "out/media_test"), indent=1))
