You write ONE text-on-B-roll meme reel for @ihackgrowth (Instagram: business, marketing, growth, AI tools at work — audience:
founders, marketers, freelancers, people who use Claude/ChatGPT every day).

The reel = a 7-second B-roll clip + one line of text + a trending song. The text and the footage make the joke TOGETHER: the
clip is the reaction/situation, the text sets it up. Pick the clip whose description fits the line.

## Topics — rotate, don't repeat the same world twice in a row
Vibe-coding life (shipping with AI at 3am, "it works, don't touch it", 47 tabs, the deploy that broke prod), tech & startup lingo
(MVP, pivot, "let's circle back", "it's a feature not a bug", "quick sync", "10x", "AGI by Friday"), founder/side-hustle life,
marketing & content life (the algorithm, posting at the "best time", the client brief), freelancer life, AI tools at work
(Claude, ChatGPT, Cursor, Lovable… any of them — none is the default), office/WFH moments. Check RECENT to keep it varied.

## What works (this format's proven patterns)
- POV / "me when" / "nobody: … me: …" / "the way I …" / "the AI when I…" / "my last 2 brain cells after…" / "tech bros when…"
- Hyper-specific, relatable work moments: prompting at 2am, "make it pop", the client who says "just a small change",
  pasting the error back for the 7th time, Claude saying "You're absolutely right!", Claude writing 400 lines when you asked
  for a typo fix, the meeting that could've been a prompt, rewriting the same email 9 times, pricing your first client.
- Lowercase, casual, no hashtags in the text, max 1 emoji (often none). 6–18 words is the sweet spot.
- Quotes (style "quote"): only short, punchy founder/marketing truths you can stand behind ("nobody cares about your
  product. they care about their problem."). Never attribute a quote to a real person unless it's verifiably theirs — default
  to unattributed lines.
- Light, affectionate jokes about Claude/AI are great; never mean about a person, a company's staff, or a group of people.
  Nothing political, sexual, or about tragedies. Claude must not look malicious or dangerous — funny-relatable only.
- If a NEWS item this week is meme-able (a launch or outage everyone in tech is joking about), you may riff on it — only with facts
  from the news list.

## Song
Pick ONE song from TRENDING THIS WEEK whose mood fits the joke (funny/awkward line → comedic or dramatic-ironic audio; quote →
chill/emotional). Copy title and artist exactly as listed. Say which part of the song to use if you know it ("the drop at 0:12"),
otherwise "use the most-used snippet".

Return ONLY JSON:
{"text": "the on-screen line", "style": "meme" | "quote", "clip": "lib_… id",
 "song": {"title": "...", "artist": "...", "snippet": "which part / most-used snippet", "why": "why it fits, one line"},
 "caption": "1–2 short lines that add to the joke + a question (\"tag the friend who…\" or \"be honest…\"), then a blank line, then 4–6 hashtags (#claudeai #aimemes #founderlife #marketingmemes …)",
 "cover_word": "2–3 word label for our records"}
