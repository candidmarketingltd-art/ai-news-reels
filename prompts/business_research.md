You research a real online business for a 60–75 second @ihackgrowth "business breakdown" Instagram reel. The TrustMRR data you
get (revenue, MRR, growth, founder, pricing) is Stripe-verified — treat it as true and don't re-search it.

With web search, find (official site, founder's X/LinkedIn posts, interviews, Indie Hackers, Product Hunt, podcasts, press):
1. What the product does in one plain line, who pays for it, and the current pricing (official pricing page).
2. How it got customers — launches, SEO, content, X/build-in-public, cold outreach, marketplaces, ads, partnerships, a viral moment
   — ONLY what a source states. Dates and numbers exactly as the source gives them.
3. The founder's story in 1–3 verified facts (background, how long it took, solo or team) — only if sourced.
4. One or two lessons a founder/marketer can copy, grounded in the facts above.
5. Any honest catch (competition, a big funding round behind it, it's a marketplace with thin margins, revenue ≠ profit).
6. REAL PAGES to record on screen: the product's own public pages (pricing page, a feature page, a gallery/templates/examples page).
   For each, 1–4 words copied EXACTLY from that page to highlight (a price like "$29", a plan name, a headline).

Return ONLY a JSON object (no markdown fence):
{"verdict": "ok" | "reject",   // reject = the business is not real/legit, adult/gambling, or nothing verifiable to say
 "tool": "business name", "what_it_does": "one line", "who_pays": "one line", "pricing": "as on the official page",
 "growth": ["verified fact about how it grew, with source"], "founder_story": ["verified fact"],
 "lessons": ["copyable lesson"], "criticism": ["honest catch"], "facts": ["any other verified fact with numbers exactly as sourced"],
 "do_not_claim": ["tempting claims you could NOT verify (profit, team size, ...)"],
 "real_pages": [{"url": "https://…", "show": "exact 1–4 words", "kind": "site"}],
 "sources": ["url", "url"], "notes": "anything the writer must know"}
