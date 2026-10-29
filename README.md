# AI News — automated Instagram Reels

Every 6 hours this repo checks what's new in AI worldwide and, if something is worth it, posts a reel — no one touching anything.
Built from the [paisadecode-reels](https://github.com/candidmarketingltd-art/paisadecode-reels) pipeline (same Rohan mascot,
ElevenLabs voice, sound design, Claude Sonnet + Opus, Buffer free plan), with a new news source and a new look.

```
Google Trends (30 countries) ─┐
AI news feeds + lab blogs ────┴─▶ Claude picks: single / roundup / skip ─▶ read the articles ─▶ Sonnet writes the script
      ─▶ Opus edits (scene plan) ─▶ fact-check every number against the articles ─▶ ElevenLabs "Rohan" voiceover (+ word timings)
      ─▶ render (modern glass UI, Rohan host cam, word-by-word captions) ─▶ theme music + mix ─▶ Buffer ─▶ Instagram
```

## How each run decides
| Situation | What gets posted |
|---|---|
| One story with importance ≥ 8 (big launch, $B deal, landmark law, trending in many countries) | **single** — one-story reel, ~45–60 s |
| No blockbuster, but 2–4 notable stories (importance ≥ 5) | **roundup** — "3 AI stories in 24 hours", ~55–70 s |
| Nothing new or notable | **skip** — nothing is posted (no filler) |

Google has no worldwide "trending now" feed, so the bot builds one: it reads Trending Now in 30 countries and an AI story
trending in many of them ranks higher. AI outlets (TechCrunch, The Verge, Ars, MIT Tech Review, Wired, VentureBeat, The Decoder)
and lab blogs (OpenAI, Google, DeepMind, Hugging Face) catch stories before they become mass searches.
Stories already covered are remembered for 7 days (`logs/covered.json`), so the same news is never posted twice.

Runs at **07:11, 13:11, 19:11 and 01:11 IST** (covers India's day and the US evening). At most 4 reels a day.

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
- **Post more / less often:** variables `SINGLE_MIN_IMPORTANCE` (default 8) and `ROUNDUP_MIN_IMPORTANCE` (default 5). Lower = more reels.
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
