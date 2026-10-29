# AI & Tech News — automated Instagram Reels

Every 2 hours this repo checks what's new worldwide and posts one reel — alternating AI and Tech & Business, 12 a day, no one touching anything.
Built from the [paisadecode-reels](https://github.com/candidmarketingltd-art/paisadecode-reels) pipeline (same Rohan mascot,
ElevenLabs voice, sound design, Claude Sonnet + Opus, Buffer free plan), with a new news source and a new look.

```
Google Trends (30 countries) ─┐
AI news feeds + lab blogs ────┴─▶ Claude picks: single story or roundup ─▶ read the articles ─▶ Sonnet writes the script
      ─▶ Opus edits (scene plan) ─▶ fact-check every number against the articles ─▶ ElevenLabs "Rohan" voiceover (+ word timings)
      ─▶ render (modern glass UI, Rohan host cam, word-by-word captions) ─▶ theme music + mix ─▶ Buffer ─▶ Instagram
```

## 12 reels a day — one every 2 hours, alternating AI ↔ Tech & Business
| IST | Topic | | IST | Topic |
|---|---|---|---|---|
| 01:11 | AI | | 13:11 | AI |
| 03:11 | Tech & Business | | 15:11 | Tech & Business |
| 05:11 | AI | | 17:11 | AI |
| 07:11 | Tech & Business | | 19:11 | Tech & Business |
| 09:11 | AI | | 21:11 | AI |
| 11:11 | Tech & Business | | 23:11 | Tech & Business |

**AI reels:** models, AI products, AI companies & funding, AI rules. **Tech & Business reels:** big-tech launches (phones,
gadgets, apps, EVs, space), startups & funding, IPOs, acquisitions, earnings, layoffs, outages/hacks, Indian startup news
with global interest — stories that are *not* mainly about AI. Each topic has its own Google Trends filter and news feeds
(Tech & Business: TechCrunch, The Verge, CNBC Tech/Business, BBC, Guardian, Fortune, Inc42, YourStory, 9to5Mac, Electrek…).

Every 2-hour window gets exactly **one** reel, posted the moment it's made. `logs/slots.json` records which windows are done;
a backup run 1 hour later only works if the main run failed (otherwise it exits in seconds).
Change the pace with variable `SLOT_HOURS` (3 = 8 a day, 6 = 4 a day) and the mix with `TOPIC_ROTATION` (e.g. `ai,ai,tech`).

## How each run picks the story
| Situation | What gets posted |
|---|---|
| One story with importance ≥ 8 (big launch, $B deal, landmark law, trending in many countries) | **single** — one-story reel, ~40–60 s |
| No blockbuster | **roundup** of the 2–4 best stories, ~45–70 s |
| A quiet news cycle | the best story not yet covered, as an explainer; if the last 8 h are empty it looks back 24 h, then 48 h |

If the script for a story fails the fact-check, it's dropped and the next best story is used (up to 3 tries).
Stories never repeat (7-day memory in `logs/covered.json`). Anything below importance 3 is never posted.
Want posts only when there's real news instead? Set variable `MUST_POST` = `0`.

Google has no worldwide "trending now" feed, so the bot builds one: it reads Trending Now in 30 countries and an AI story
trending in many of them ranks higher. AI outlets (TechCrunch, The Verge, Ars, MIT Tech Review, Wired, VentureBeat, The Decoder)
and lab blogs (OpenAI, Google, DeepMind, Hugging Face) catch stories before they become mass searches.

---

## One-time setup (~15 minutes)

Secrets go in **GitHub → this repo → Settings → Secrets and variables → Actions → Secrets**; plain settings in the **Variables** tab.

### 0. Make this repo public
Settings → General → Danger zone → *Change visibility* → Public. Buffer downloads each reel from a public GitHub Release link,
and public repos get unlimited free Actions minutes. Secrets stay private.

### 1. Keys (same ones as Paisa Decode work)
- **`ANTHROPIC_API_KEY`** (secret) — Sonnet picks the news + writes, Opus 5.5 edits.
- **`ELEVENLABS_API_KEY`** (secret) — every reel is voiced by your cloned **Rohan** voice (`dVIifp6W0jifqeThgNN0`, Eleven v4 with emotion tags), speaking English;
  create the key in the same ElevenLabs workspace as the voice. Falls back to Microsoft's free `en-IN-PrabhatNeural` when credits run out.

### 1b. Footage — Apify (same token as Paisa Decode)
Secret **`APIFY_TOKEN`** = your Apify token (console.apify.com → Settings → API & Integrations). Stock clips come from Pexels
through the Apify actor `memo23/pexels-scraper` — about $0.003 per clip (~$1/month at 4 reels a day), covered by Apify's
free monthly credit. Official company images and logos need no key. (Alternatively a free Pexels key as `PEXELS_API_KEY`.)

**What footage is used:** the company's own announcement/share image and logo (found via links in the news articles, never
news-agency photos), plus generic Pexels clips matching what Rohan says. Company YouTube videos and Reuters/Getty/AP photos are
never used — those trigger Instagram copyright matching (muted or removed reels, strikes on the account).

### 2. The new Instagram account in Buffer (free plan)
1. Switch the new Instagram account to **Professional (Creator or Business)**.
2. Use a **separate Buffer account** for @ihackgrowth (not the Paisa Decode one): sign up free → *Connect channel* → Instagram → @ihackgrowth.
3. Open that channel in Buffer — the URL shows `.../channels/<ID>/...` → variable **`BUFFER_CHANNEL_ID`**.
4. In that Buffer account: publish.buffer.com/settings/api → create an API key → secret **`BUFFER_API_KEY`** in this repo.
   Keys are per Buffer account, so this repo can only post to @ihackgrowth and Paisa Decode is untouched.
5. The reels post to **@ihackgrowth** (set variable **`IG_HANDLE`** only if that changes).

Reels go out **3 minutes after they're made** (news shouldn't wait in a queue), so the free plan's queue limit never comes into play.
Prefer Buffer's posting schedule instead? Variable `BUFFER_MODE` = `queue`.

### 3. Test, then go live
- **Actions → AI news reel → Run workflow** (dry run ticked) → download the reel from *Artifacts*, check `logs/runs.csv` for the decision.
- Happy? Run it with dry run unticked. From then on it runs every 6 hours by itself.

## Everyday controls
- **Pause:** Actions → *AI news reel* → ⋯ → *Disable workflow*.
- **Run right now:** edit `triggers/run-now.txt` on GitHub (any change) and commit, or *Actions → Run workflow* (pick a topic).
- **Single vs roundup:** variables `SINGLE_MIN_IMPORTANCE` (default 8) and `ROUNDUP_MIN_IMPORTANCE` (default 5); `MIN_IMPORTANCE` (default 3) is the floor.
- **Change countries:** variable `TREND_GEOS`, e.g. `US,IN,GB,CA,AU`.
- **Change the news judgement / script / edit:** plain-English prompts in `prompts/news_editor.md`, `prompts/script_writer.md`, `prompts/video_editor.md`.
- **Look:** `RENDER_STYLE` = `modern` (default: glass panel, gradient accents, Rohan host cam), `panel` (flat samjho-style) or `classic` (Paisa Decode cinematic look). `MASCOT_BADGE` = text on Rohan's t-shirt (default `AI`).
- **Fact-check:** if the script uses a number that isn't in the articles, Claude is asked to fix it; if it still fails the run is
  logged as `skipped_factcheck` and nothing is posted.

## Costs (at 12 reels a day ≈ 360 a month)
- **Free:** GitHub (public repo), Google Trends, news feeds, Buffer free plan, official images/logos, the Microsoft fallback voice.
- **ElevenLabs:** a ~45 s reel uses ~750 credits → ~9,000 a day, **~270,000 a month**. That needs a plan with that many credits
  (shared with Paisa Decode). When credits run out, reels keep posting with the free Microsoft voice until they refill.
- **Claude API:** 3 calls per reel (pick the news, Sonnet script, Opus edit), billed per use.
- **Apify:** ~2–6 Pexels clips per reel at ~$0.003 each → roughly $3–6 a month.

## Layout
```
prompts/   news_editor.md (what counts as news), script_writer.md, video_editor.md, example_plan.json (format reference)
pipeline/  run.py (one 6-hour check), news.py (Trends + feeds + article reader), script_writer.py (pick, write, edit, fact-check),
           voice.py, buffer.py, publish.py, render/ (engine, Rohan mascot, sound design, theme music, fonts)
logs/      runs.csv (every decision), covered.json (stories already posted), plans/ (every script), episode.json
```
