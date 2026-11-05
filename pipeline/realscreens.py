"""REAL screens of the tool a reel talks about — captured live from the tool's own public pages, not recreated.

For every page the research found (homepage, pricing, features, templates, a help article…):
  real_<n>_phone  — the page as it looks on a phone (real mobile layout), smoothly scrolled from the top down to the
                    thing the voiceover talks about, which is outlined in gold with a tap marker. Vertical 720x1280 —
                    can fill the whole reel (`full`).
  real_<n>_web    — the desktop page, slow push-in from the whole window to that same thing. 1280x960.
For help-centre / app-store pages it also keeps the real product screenshots published on them (real_<n>_shot<k>),
checked with Claude vision so only genuine product UI is offered to the editor.

Everything is public, official material from the tool's own site (what reviewers normally show). Nothing logged-in:
screens behind a login still need a recreation or the owner's recording.
"""
import base64, json, os, re, subprocess
from urllib.parse import urljoin, urlparse

FPS = 30
PHONE = (720, 1280)
WEB = (1280, 960)
GOLD = "#FFC83D"
HIDE_CSS = """
[id*=cookie i],[class*=cookie i],[id*=consent i],[class*=consent i],[id*=onetrust i],[class*=onetrust i],[id*=gdpr i],
[class*=gdpr i],[aria-label*=cookie i],[id^=sp_message],[class*=intercom],[id*=intercom],[class*=drift],[id*=hubspot-messages],
[class*=crisp-client],[id*=chat-widget i],[class*=newsletter-popup i],[class*=modal-backdrop i] {display:none !important}
html,body{overflow:visible !important}
"""
MARK_JS = """([text, gold]) => {
  const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const want = norm(text);
  if (!want) return null;
  let best = null;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  while (walker.nextNode()) {
    const el = walker.currentNode;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || r.height > 700) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || +st.opacity === 0) continue;
    const t = norm(el.innerText);
    if (!t.includes(want)) continue;
    const area = r.width * r.height;
    if (!best || area < best.area) best = {el, area};
  }
  if (!best) return null;
  let el = best.el;
  // grow from a tiny text node to its card/row/button if that is still compact
  for (let i = 0; i < 3 && el.parentElement; i++) {
    const p = el.parentElement.getBoundingClientRect();
    if (p.height > 420 || p.width > window.innerWidth * 0.98) break;
    el = el.parentElement;
  }
  const r = el.getBoundingClientRect();
  const box = document.createElement('div');
  const pad = 8;
  Object.assign(box.style, {position: 'absolute', left: (r.left + scrollX - pad) + 'px', top: (r.top + scrollY - pad) + 'px',
    width: (r.width + pad * 2) + 'px', height: (r.height + pad * 2) + 'px', border: `5px solid ${gold}`, borderRadius: '16px',
    boxShadow: `0 0 0 9999px rgba(0,0,0,0.18), 0 0 28px ${gold}`, zIndex: 2147483646, pointerEvents: 'none'});
  document.body.appendChild(box);
  const tap = document.createElement('div');
  Object.assign(tap.style, {position: 'absolute', left: (r.left + scrollX + r.width * 0.72) + 'px', top: (r.top + scrollY + r.height * 0.6) + 'px',
    width: '34px', height: '34px', borderRadius: '50%', background: gold, border: '4px solid #fff',
    boxShadow: '0 0 0 10px rgba(255,255,255,0.35)', zIndex: 2147483647, pointerEvents: 'none'});
  document.body.appendChild(tap);
  return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height};
}"""


def _settle(page):
    try: page.wait_for_load_state("networkidle", timeout=12000)
    except Exception: pass
    page.add_style_tag(content=HIDE_CSS)
    # lazy-loaded sections: walk down the page once so images load, then back to the top
    try:
        page.evaluate("""async () => { for (let y = 0; y < Math.min(document.body.scrollHeight, 9000); y += 600) {
                           window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); } window.scrollTo(0, 0); }""")
        page.wait_for_timeout(700)
    except Exception: pass


def _ease(n, a, b, hold_a, hold_b):
    """Frame-by-frame positions: hold at a, ease-in-out to b, hold at b."""
    import math
    move = max(1, n - hold_a - hold_b)
    out = [a] * hold_a
    for i in range(move):
        k = i / (move - 1) if move > 1 else 1
        out.append(a + (b - a) * (0.5 - 0.5 * math.cos(math.pi * k)))
    return out + [b] * hold_b


def _pan_video(png, out_mp4, size, keys, seconds=6.0):
    """keys = (x, y, w) crop windows at start and end (in screenshot px); renders an eased move between them."""
    from PIL import Image
    im = Image.open(png).convert("RGB")
    W, H = size
    n = int(seconds * FPS)
    (x0, y0, w0), (x1, y1, w1) = keys
    xs, ys, ws = (_ease(n, a, b, int(FPS * 1.0), int(FPS * 1.6)) for a, b in ((x0, x1), (y0, y1), (w0, w1)))
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", out_mp4], stdin=subprocess.PIPE)
    for x, y, w in zip(xs, ys, ws):
        h = w * H / W
        x = max(0, min(x, im.width - w)); y = max(0, min(y, im.height - h))
        p.stdin.write(im.crop((int(x), int(y), int(x + w), int(y + h))).resize((W, H), Image.LANCZOS).tobytes())
    p.stdin.close(); p.wait()
    return n


def _candidates(show):
    show = str(show or "")
    q = re.findall(r"[\'\"‘“]([^\'\"’”]{2,40})[\'\"’”]", show)
    rest = [x.strip() for x in re.split(r"[,;/()]| and ", show) if 2 <= len(x.strip()) <= 30]
    out = []
    for x in q + rest:
        if x not in out: out.append(x)
    return out[:8]


def _mark(page, show):
    for c in _candidates(show):
        try:
            box = page.evaluate(MARK_JS, [c, GOLD])
        except Exception:
            box = None
        if box: return box
    return None


def _capture(browser, url, show, workdir, n):
    out = []
    # phone: real mobile layout, scroll to the highlighted thing
    ctx = browser.new_context(viewport={"width": 390, "height": 693}, device_scale_factor=2, is_mobile=True, has_touch=True,
                              user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
                              locale="en-US")
    try:
        page = ctx.new_page(); page.goto(url, timeout=45000, wait_until="domcontentloaded"); _settle(page)
        box = _mark(page, show) if show else None
        png = os.path.join(workdir, f"real_{n}_phone.png")
        page.screenshot(path=png, full_page=True, clip=None) if page.evaluate("document.body.scrollHeight") < 7000 else \
            page.screenshot(path=png, clip={"x": 0, "y": 0, "width": 390, "height": 7000})
        from PIL import Image
        iw, ih = Image.open(png).size
        s = iw / 390
        w = iw
        y1 = 0 if not box else max(0, (box["y"] + box["h"] / 2) * s - w * 16 / 9 / 2)
        if not box: y1 = min(ih - w * 16 / 9, w * 16 / 9 * 1.2)   # nothing to point at: a gentle scroll through the first screens
        mp4 = os.path.join(workdir, f"real_{n}_phone.mp4")
        _pan_video(png, mp4, PHONE, ((0, 0, w), (0, max(0, y1), w)), seconds=6.5 if y1 > 0 else 5)
        out.append({"id": f"real_{n}_phone", "kind": "video", "path": mp4, "mp4": mp4, "frames": int(6 * FPS), "fit": "cover",
                    "credit": f"Screen: {(urlparse(url).hostname or 'site').removeprefix('www.')}", "_box": bool(box)})
    except Exception as e:
        print(f"      (real screen phone {url}: {str(e)[:120]})", flush=True)
    finally:
        ctx.close()
    # desktop: whole window, then push in on the highlighted thing
    ctx = browser.new_context(viewport={"width": 1440, "height": 1080}, device_scale_factor=1.5, locale="en-US")
    try:
        page = ctx.new_page(); page.goto(url, timeout=45000, wait_until="domcontentloaded"); _settle(page)
        box = _mark(page, show) if show else None
        top = 0
        if box and box["y"] + box["h"] > 1000:   # bring it into the window, a little above centre
            top = max(0, box["y"] - 380); page.evaluate(f"window.scrollTo(0, {top})"); page.wait_for_timeout(500)
            top = page.evaluate("window.scrollY")
        png = os.path.join(workdir, f"real_{n}_web.png")
        page.screenshot(path=png)
        s = 1.5
        start = (0, 0, 1440 * s)
        if box:
            w = max(560, min(1440, box["w"] * 2.4)) * s
            cx, cy = (box["x"] + box["w"] / 2) * s, (box["y"] - top + box["h"] / 2) * s
            end = (cx - w / 2, cy - w * 0.75 / 2, w)
        else:
            end = (1440 * s * 0.08, 1080 * s * 0.06, 1440 * s * 0.84)
        mp4 = os.path.join(workdir, f"real_{n}_web.mp4")
        _pan_video(png, mp4, WEB, (start, end), seconds=6)
        out.append({"id": f"real_{n}_web", "kind": "video", "path": mp4, "mp4": mp4, "frames": int(6 * FPS), "fit": "cover",
                    "credit": f"Screen: {(urlparse(url).hostname or 'site').removeprefix('www.')}", "_box": bool(box)})
    except Exception as e:
        print(f"      (real screen desktop {url}: {str(e)[:120]})", flush=True)
    finally:
        ctx.close()
    return out


def _page_shots(url, workdir, n, limit=4):
    """Product screenshots published on an official help / app-store page."""
    import requests, io
    from PIL import Image
    ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}
    html = requests.get(url, headers=ua, timeout=30).text
    srcs = []
    for m in re.finditer(r"<img[^>]+?(?:data-src|src)=[\"']([^\"']+)[\"']", html, re.I):
        u = urljoin(url, m.group(1).replace("&amp;", "&"))
        if re.search(r"(logo|icon|avatar|sprite|badge|emoji|\.svg)", u, re.I) or u in srcs: continue
        srcs.append(u)
    out = []
    for u in srcs[:20]:
        if len(out) >= limit: break
        try:
            im = Image.open(io.BytesIO(requests.get(u, headers=ua, timeout=30).content)).convert("RGB")
        except Exception:
            continue
        if im.width < 600 or im.height < 300: continue
        p = os.path.join(workdir, f"real_{n}_shot{len(out) + 1}.png")
        im.save(p)
        out.append({"id": f"real_{n}_shot{len(out) + 1}", "kind": "image", "path": p, "fit": "contain",
                    "credit": f"Screenshot: {(urlparse(url).hostname or 'site').removeprefix('www.')}"})
    return out


def _vision(items, tool):
    """Describe each capture from its pixels; drop anything that isn't the real product (errors, captcha, blank, other brands)."""
    import anthropic
    from PIL import Image
    if not items: return []
    content = []
    for i, m in enumerate(items):
        src = m["path"] if m["kind"] == "image" else m["path"].replace(".mp4", ".png")
        im = Image.open(src).convert("RGB")
        if m["id"].endswith("_phone"): im = im.crop((0, 0, im.width, min(im.height, int(im.width * 16 / 9 * 2.2))))
        im.thumbnail((900, 1400))
        import io
        b = io.BytesIO(); im.save(b, "JPEG", quality=80)
        content += [{"type": "text", "text": f"#{i} ({m['id']})"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}]
    content.append({"type": "text", "text": (
        f"These are captures of the official pages of **{tool}** for an Instagram reel. For EACH #, return JSON "
        '{"items": [{"i": 0, "usable": true|false, "desc": "what is on screen, with the exact headline/plan names/prices/buttons you can READ"}]}. '
        "usable=false if it is an error page, captcha, cookie wall, login wall, blank/broken layout, or not this product. Read text exactly; "
        "never guess numbers you can't read. Return only the JSON.")})
    model = os.environ.get("VISION_MODEL") or os.environ.get("SCRIPT_MODEL") or "claude-sonnet-5-5"
    msg = anthropic.Anthropic().messages.create(model=model, max_tokens=2500, messages=[{"role": "user", "content": content}])
    txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    d = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
    keep = []
    for r in d.get("items", []):
        i = r.get("i")
        if not isinstance(i, int) or i >= len(items) or not r.get("usable"): continue
        m = dict(items[i]); m.pop("_box", None)
        where = {"phone": "REAL phone screen recording (vertical, fills the reel with full:true), scrolls down to",
                 "web": "REAL desktop screen recording, pushes in on"}.get(m["id"].rsplit("_", 1)[-1], "REAL product screenshot from the official site:")
        m["desc"] = f"{where} the gold-outlined part — {r.get('desc', '')[:300]} [{m['credit']}]"
        if "_box" in items[i] and not items[i]["_box"]: m["desc"] = m["desc"].replace("the gold-outlined part", "the page (no highlight)")
        keep.append(m)
    return keep


def collect(notes, workdir, max_pages=4):
    """notes.real_pages: [{"url", "show": exact visible text to point at, "kind": "site" | "help"}] from the research step."""
    pages = [p for p in (notes.get("real_pages") or []) if isinstance(p, dict) and str(p.get("url", "")).startswith("http")][:max_pages]
    if not pages: return []
    os.makedirs(workdir, exist_ok=True)
    raw = []
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"      (real screens unavailable: {e})", flush=True); return []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for n, p in enumerate(pages, 1):
            got = []
            if p.get("kind") == "help":
                try: got = _page_shots(p["url"], workdir, n)
                except Exception as e: print(f"      (screenshots from {p['url']}: {str(e)[:120]})", flush=True)
            raw += got
            if not got:   # a normal page, or a help page without usable screenshots: record the page itself
                raw += _capture(browser, p["url"], p.get("show"), workdir, n)
        browser.close()
    try:
        out = _vision(raw, notes.get("tool") or "")
    except Exception as e:
        print(f"      (real screen check failed: {str(e)[:150]})", flush=True); out = []
    print(f"      real screens: {len(out)} usable of {len(raw)} captured from {len(pages)} official pages", flush=True)
    return out
