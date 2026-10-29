# AI News — automated Instagram Reels

Every 6 hours this repo checks what's new in AI worldwide and posts one reel about it — 4 reels a day, no one touching anything.
Built from the [paisadecode-reels](https://github.com/candidmarketingltd-art/paisadecode-reels) pipeline (same Rohan mascot,
ElevenLabs voice, sound design, Claude Sonnet + Opus, Buffer free plan), with a new news source and a new look.

```
Google Trends (30 countries) ─┐
AI news feeds + lab blogs ────┴─▶ Claude picks: single story or roundup ─▶ read the articles ─▶ Sonnet writes the script
      ─▶ Opus edits (scene plan) ─▶ fact-check every number against the articles ─▶ ElevenLabs "Rohan" voiceover (+ word timings)
      ─▶ render (modern glass UI, Rohan host cam, word-by-word captions) ─▶ theme music + mix ─▶ Buffer ─▶ Instagram
```

## 4 reels a day — one every 6 hours
| Window (IST) | Main run | Backup run |
|---|---|---|
| 07:00 – 13:00 | 07:11 | 08:26 |
| 13:00 – 19:00 | 13:11 | 14:26 |
| 19:00 – 01:00 | 19:11 | 20:26 |
| 01:00 – 07:00 | 01:11 (US evening) | 02:26 |

Every window gets exactly **one** reel, posted the moment it's made. `logs/slots.json` records which windows are done, so the
backup run only does something if the main run failed (GitHub hiccup, ElevenLabs/Buffer error, a story that couldn't be fact-checked).

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

### 1b. Footage — Pexels (free)
pexels.com/api → sign up → copy your API key → secret **`PEXELS_API_KEY`**. Used for stock B-roll clips (free for commercial use,
no copyright claims). Official company images and logos need no key. Without the key, reels use official images + cards only.

**What footage is used:** the company's own announcement/share image and logo (found via links in the news articles, never
news-agency photos), plus generic Pexels clips matching what Rohan says. Company YouTube videos and Reuters/Getty/AP photos are
never used — those trigger Instagram copyright matching (muted or removed reels, strikes on the account).

### 2. The new Instagram account in Buffer (free plan)
1. Switch the new Instagram account to **Professional (Creator or Business)**.
2. In Buffer → *Connect channel* → Instagram → the new account. (Buffer's free plan allows 3 channels.)
3. Open that channel in Buffer — the URL shows `.../channels/<ID>/...` → variable **`BUFFER_CHANNEL_ID`**.
4. Secret **`BUFFER_API_KEY`** (you can reuse the Paisa Decode key — it's per Buffer account).
5. Variable **`IG_HANDLE`** = the new account's handle (shown in the reels and captions).

Reels go out **3 minutes after they're made** (news shouldn't wait in a queue), so the free plan's queue limit never comes into play.
Prefer Buffer's posting schedule instead? Variable `BUFFER_MODE` = `queue`.

### 3. Test, then go live
- **Actions → AI news reel → Run workflow** (dry run ticked) → download the reel from *Artifacts*, check `logs/runs.csv` for the decision.
- Happy? Run it with dry run unticked. From then on it runs every 6 hours by itself.

## Everyday controls
- **Pause:** Actions → *AI news reel* → ⋯ → *Disable workflow*.
- **Run right now:** edit `triggers/run-now.txt` on GitHub (any change) and commit.
- **Single vs roundup:** variables `SINGLE_MIN_IMPORTANCE` (default 8) and `ROUNDUP_MIN_IMPORTANCE` (default 5); `MIN_IMPORTANCE` (default 3) is the floor.
- **Change countries:** variable `TREND_GEOS`, e.g. `US,IN,GB,CA,AU`.
- **Change the news judgement / script / edit:** plain-English prompts in `prompts/news_editor.md`, `prompts/script_writer.md`, `prompts/video_editor.md`.
- **Look:** `RENDER_STYLE` = `modern` (default: glass panel, gradient accents, Rohan host cam), `panel` (flat samjho-style) or `classic` (Paisa Decode cinematic look). `MASCOT_BADGE` = text on Rohan's t-shirt (default `AI`).
- **Fact-check:** if the script uses a number that isn't in the articles, Claude is asked to fix it; if it still fails the run is
  logged as `skipped_factcheck` and nothing is posted.

## Costs
GitHub (public), Google Trends, RSS feeds, Buffer free plan, the Microsoft fallback voice: free.
Paid per use: Claude API — 1 small call per run to pick the news, plus 2 calls (Sonnet + Opus) only when a reel is made.
ElevenLabs stays within your plan's credits.

## Layout
```
prompts/   news_editor.md (what counts as news), script_writer.md, video_editor.md, example_plan.json (format reference)
pipeline/  run.py (one 6-hour check), news.py (Trends + feeds + article reader), script_writer.py (pick, write, edit, fact-check),
           voice.py, buffer.py, publish.py, render/ (engine, Rohan mascot, sound design, theme music, fonts)
logs/      runs.csv (every decision), covered.json (stories already posted), plans/ (every script), episode.json
```
