"""Business breakdown reels: real businesses making real money, from TrustMRR (Stripe-verified revenue).

trustmrr.com lists startups with verified revenue (Stripe / payment-provider API), MRR, growth, founder, pricing, category.
For each reel:
  1. candidates from TrustMRR leaderboards (top 100, categories, "$1M+ with few followers", recently added)
  2. Claude picks the one with the best story for founders/marketers (simple product, surprising money, stealable lesson)
  3. its TrustMRR page is read (numbers taken from there), the web is searched for how it grew (founder posts, interviews)
  4. real screens: its TrustMRR page (revenue highlighted) + its own homepage/pricing
  5. script + edit with the same writer/editor as the tutorial reels (format "business")
"""
import datetime as dt, json, math, os, re

from pipeline import tutorial
from pipeline.script_writer import _ask_json, SELECT_MODEL

BASE = "https://trustmrr.com"
LISTS = [p.strip() for p in (os.environ.get("TRUSTMRR_LISTS") or
         "/,/stats,/category/marketing,/category/ai,/category/saas,/category/productivity,/category/content-creation,"
         "/category/ecommerce,/category/no-code,/category/social-media,/micro-saas-examples").split(",") if p.strip()]


def _browser_text(pw, url, links=False):
    b = pw.chromium.launch()
    try:
        page = b.new_page(viewport={"width": 1440, "height": 1000}, locale="en-US")
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        try: page.wait_for_load_state("networkidle", timeout=15000)
        except Exception: pass
        if links:
            return page.evaluate("""() => {
              const out = {};
              for (const a of document.querySelectorAll('a[href*="/startup/"]')) {
                const m = a.getAttribute('href').match(/\\/startup\\/([^/?#]+)/); if (!m) continue;
                let el = a; for (let i = 0; i < 4 && el.parentElement && (el.innerText || '').length < 60; i++) el = el.parentElement;
                const row = el.closest('tr') || el;
                const t = (row.innerText || a.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 260);
                if (!out[m[1]] || t.length > out[m[1]].length) out[m[1]] = t;
              }
              return out; }""")
        return page.evaluate("document.body.innerText")
    finally:
        b.close()


def candidates(skip_slugs=()):
    from playwright.sync_api import sync_playwright
    rows = {}
    with sync_playwright() as pw:
        for path in LISTS:
            try:
                got = _browser_text(pw, BASE + path, links=True)
                for slug, t in got.items():
                    if slug in skip_slugs: continue
                    rows.setdefault(slug, {"slug": slug, "row": t, "lists": []})["lists"].append(path)
            except Exception as e:
                print(f"      (trustmrr {path}: {str(e)[:120]})", flush=True)
    print(f"      trustmrr: {len(rows)} startups from {len(LISTS)} lists", flush=True)
    return list(rows.values())


def pick(cands, recent):
    sysp = """You pick businesses for @ihackgrowth "business breakdown" Instagram reels: real online businesses with VERIFIED revenue
(TrustMRR shows Stripe-verified numbers). Audience: founders, freelancers, marketers, side-hustlers in India and worldwide.
Great picks: a simple or "boring" product making surprising money; a solo founder / tiny team; a clear niche; a growth tactic the
viewer can copy; a product people can look at (a public website). Prefer recognisable categories (marketing, AI tools, SaaS,
e-commerce, content, productivity, education). Skip: "Stealth Company"/anonymous listings, adult/dating/gambling/crypto-casino,
anything we covered recently, revenue under $5k/month unless the story is extraordinary.
Return ONLY JSON: {"picks": [{"slug": "...", "angle": "the hook idea in one line, e.g. 'A solo dev makes $40K/month from a boring
invoice tool'", "why": "one line"}]} — 4 picks, best first."""
    rows = "\n".join(f"- {c['slug']} · lists: {', '.join(c['lists'][:3])} · {c['row']}" for c in cands[:400])
    user = f"RECENTLY COVERED (don't repeat):\n" + ("\n".join(f"- {t}" for t in recent) or "- none") + f"\n\nSTARTUPS:\n{rows}\n\nReturn only the JSON."
    ok = {c["slug"] for c in cands}

    def check(d):
        p = d.get("picks") or []
        if not p: raise ValueError("no picks")
        for x in p:
            if x.get("slug") not in ok: raise ValueError(f"unknown slug {x.get('slug')} — use slugs from the list")
    return _ask_json(SELECT_MODEL, sysp, user, check)["picks"]


def _money_forms(text):
    """'$368,905' -> also '$368K', '$369K', '$370K', '$0.37M' so a spoken round number passes the fact check."""
    out = []
    for m in re.findall(r"\$\s?(\d[\d,]{3,}(?:\.\d+)?)", text):
        v = float(m.replace(",", ""))
        forms = {f"${math.floor(v / 1000)}K", f"${round(v / 1000)}K", f"${round(v / 10000) * 10}K"}
        if v >= 1e6: forms |= {f"${v / 1e6:.1f}M", f"${math.floor(v / 1e5) / 10:.1f}M", f"${round(v / 1e6)}M"}
        out.append(f"${m} (can be said as: {', '.join(sorted(forms))})")
    return out


def details(slug):
    from playwright.sync_api import sync_playwright
    url = f"{BASE}/startup/{slug}"
    with sync_playwright() as pw:
        txt = _browser_text(pw, url)
    sysp = ("Extract the facts shown on this TrustMRR startup page. Copy every number EXACTLY as written. Return ONLY JSON: "
            '{"name","one_liner","website": "https://…","founder","founder_x": "@handle or empty","founded","location","category",'
            '"audience","pricing","revenue_last_30_days","revenue_all_time","mrr","growth_mom","active_subscriptions","rank",'
            '"for_sale": "asking price or empty","verified_by": "e.g. Stripe API key","last_updated","other": ["any other fact shown"]}. '
            "Use empty strings for anything not on the page; never guess.")
    def need_name(d):
        if not d.get("name"): raise ValueError("name missing")
    d = _ask_json(SELECT_MODEL, sysp, f"PAGE ({url}):\n{txt[:20000]}", need_name)
    d["trustmrr_url"] = url
    return d


def research(biz):
    """Web research on how the business grew, layered on top of the TrustMRR numbers."""
    import anthropic
    sysp = (tutorial.ROOT / "prompts" / "business_research.md").read_text(encoding="utf-8")
    user = f"TODAY: {dt.date.today()}\nTRUSTMRR DATA (Stripe-verified, treat as true):\n{json.dumps(biz, ensure_ascii=False, indent=1)}\n\nResearch, then return only the JSON."
    client = anthropic.Anthropic()
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": int(os.environ.get("RESEARCH_SEARCHES") or 6)}]
    msgs, searched, raw = [{"role": "user", "content": user}], 0, ""
    for _ in range(4):
        resp = client.messages.create(model=tutorial.RESEARCH_MODEL, max_tokens=16000, system=sysp, messages=msgs, tools=tools)
        searched += sum(1 for b in resp.content if getattr(b, "type", "") == "server_tool_use")
        if resp.stop_reason != "pause_turn": break
        msgs = [{"role": "user", "content": user}, {"role": "assistant", "content": resp.content}]
    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    try:
        notes = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    except Exception:
        notes = _ask_json(tutorial.RESEARCH_MODEL, "Convert these research notes into one valid JSON object; keep every fact and url; add nothing.",
                          raw[-30000:], lambda d: None, attempts=2)
    notes["_searched"] = searched
    return notes


def make_plan(recent_topics, skip_urls=(), workdir="out/media", on_manual=None):
    print("[1/6] businesses making money (TrustMRR)", flush=True)
    skip = {u.rsplit("/", 1)[-1] for u in skip_urls if u and "trustmrr.com/startup/" in u}
    cands = candidates(skip)
    if not cands: raise RuntimeError("TrustMRR returned no startups")
    print("[2/6] picking the business", flush=True)
    for p in pick(cands, recent_topics)[:3]:
        print(f"      → {p['slug']}: {p.get('angle', '')} — {p.get('why', '')[:140]}", flush=True)
        try:
            biz = details(p["slug"])
        except Exception as e:
            print(f"      couldn't read its page ({str(e)[:150]}); next", flush=True); continue
        if not (biz.get("mrr") or biz.get("revenue_last_30_days")):
            print("      no revenue on its page; next", flush=True); continue
        print(f"[3/6] research: {biz['name']} · MRR {biz.get('mrr')} · 30d {biz.get('revenue_last_30_days')}", flush=True)
        notes = research(biz)
        if notes.get("verdict") == "reject":
            print(f"      rejected: {notes.get('notes', '')[:200]}", flush=True); continue
        notes["trustmrr"] = biz
        notes["say_numbers_as"] = _money_forms(json.dumps(biz))
        notes["tool"] = biz["name"]
        pages = [{"url": biz["trustmrr_url"], "show": biz.get("mrr") or biz.get("revenue_last_30_days"), "kind": "site"}]
        site = biz.get("website") or ""
        if site and not site.startswith("http"): site = "https://" + site
        if site: pages.append({"url": site, "show": "", "kind": "site"})
        notes["real_pages"] = pages + [x for x in (notes.get("real_pages") or []) if isinstance(x, dict) and x.get("url") not in (biz["trustmrr_url"], site)][:2]
        pk = {"topic": f"Business breakdown: {biz['name']} — {biz.get('one_liner', '')[:90]}", "tool": biz["name"], "format": "business",
              "angle": p.get("angle", "")}
        item = {"owner": "trustmrr", "plays": 0, "likes": 0, "comments": 0, "url": biz["trustmrr_url"],
                "caption": f"{biz['name']}: {biz.get('one_liner', '')}"}
        try:
            print("[4/6] script + edit", flush=True)
            script, sources = tutorial.write(pk, item, notes, "")
            media = tutorial.footage(script, notes, workdir)
            plan = tutorial.edit(script, pk, sources, notes, media)
        except tutorial.FactCheckError as e:
            print(f"      couldn't write it cleanly ({str(e)[:200]}); next", flush=True); continue
        plan.pop("manual_request", None)
        return {**script, **plan, "media": media, "sources_text": sources, "style": "hisaab", "topic": pk["topic"], "pick": pk,
                "inspired_by": {"url": biz["trustmrr_url"], "owner": "trustmrr", "plays": 0, "likes": 0, "comments": 0},
                "research": notes, "kind": "business"}
    raise RuntimeError("none of the business picks could be made")
