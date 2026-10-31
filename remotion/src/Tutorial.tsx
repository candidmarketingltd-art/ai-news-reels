import React from "react";
import { interpolate, spring, useCurrentFrame, Easing } from "remotion";
import { COL, SANS, FPS, clamp, easeOut, fx, col, fit, Card, Mono, Ill, Reveal } from "./lib";

/* Tutorial elements (AI / tech how-to reels). Same glass cards, springs and timing rules as the rest of the library. */
const W = 940;
type El = { type: string; at: number; [k: string]: any };
type Spec = { h: (e: El) => number; R: React.FC<{ e: El }> };

/** wrap text into lines of about `n` characters */
const wrap = (t: string, n: number) => {
  const out: string[] = []; let cur = "";
  for (const w of t.split(/\s+/)) {
    if (cur && (cur + " " + w).length > n) { out.push(cur); cur = w; } else cur = cur ? cur + " " + w : w;
  }
  if (cur) out.push(cur);
  return out;
};

/** chat / prompt box: the prompt types itself in, then the send button pulses */
const Prompt: React.FC<{ e: El }> = ({ e }) => {
  const f = useCurrentFrame();
  const text: string = e.text || "";
  const lines = wrap(text, 30).slice(0, 4);
  const shown = text.length ? Math.floor(interpolate(f, [fx(e.at + 0.15), fx(e.at + 0.15 + Math.min(2.2, 0.035 * text.length))], [0, text.length], clamp)) : 0;
  let left = shown;
  const h = 150 + lines.length * 62;
  const sent = e.send_at !== undefined && f >= fx(e.send_at);
  const k = sent ? spring({ frame: f - fx(e.send_at), fps: FPS, config: { damping: 9, stiffness: 220 } }) : 0;
  const accent = col(e.color, COL.green);
  return (
    <Card w={W} h={h} label={(e.app || "PROMPT").toUpperCase()} accent={accent} glow={sent ? accent : undefined} glowAt={e.send_at} shineAt={e.at + 0.1}>
      <div style={{ position: "absolute", left: 30, right: 140, top: 78 }}>
        {lines.map((ln, i) => {
          const n = Math.max(0, Math.min(ln.length, left)); left -= ln.length + 1;
          const typing = n < ln.length && n > 0;
          return (
            <div key={i} style={{ font: `600 46px ${SANS}`, color: COL.txt, letterSpacing: -0.5, height: 62, whiteSpace: "nowrap" }}>
              {ln.slice(0, n)}{(typing || (n === ln.length && i === lines.length - 1 && !sent)) && <span style={{ color: accent, opacity: f % 16 < 9 ? 1 : 0 }}>▍</span>}
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", right: 30, bottom: 28, width: 84, height: 84, borderRadius: 42, background: sent ? accent : "#2A2D31",
        display: "flex", alignItems: "center", justifyContent: "center", scale: `${1 + 0.18 * k * (1 - k) * 4}`, boxShadow: sent ? `0 0 34px ${accent}aa` : "none" }}>
        <svg width={40} height={40} viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7" stroke={sent ? COL.ink : COL.mute} strokeWidth={3} fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </div>
    </Card>
  );
};

/** keyboard shortcut: keycaps press down one after another */
const Keys: React.FC<{ e: El }> = ({ e }) => {
  const f = useCurrentFrame();
  const keys: string[] = (e.keys || []).slice(0, 4);
  return (
    <div style={{ width: W, display: "flex", flexDirection: "column", alignItems: "center", gap: 22 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        {keys.map((k, i) => {
          const t = e.at + i * 0.22;
          const s = spring({ frame: f - fx(t), fps: FPS, config: { damping: 12, stiffness: 180 } });
          const press = interpolate(f, [fx(t + 0.25), fx(t + 0.3), fx(t + 0.5)], [0, 1, 0.6], clamp);
          const w = Math.max(150, k.length * 40 + 60);
          return (
            <React.Fragment key={i}>
              {i > 0 && <div style={{ font: `800 60px ${SANS}`, color: COL.mute, opacity: s }}>+</div>}
              <div style={{ width: w, height: 150, borderRadius: 26, opacity: s, scale: `${0.7 + 0.3 * s}`, translate: `0 ${press * 10}px`,
                background: "linear-gradient(180deg,#3A3D44,#26282D)", border: `2px solid ${press > 0.3 ? COL.gold : COL.edge}`,
                boxShadow: `inset 0 2px 0 rgba(255,255,255,.12), 0 ${16 - press * 12}px 0 #141517, 0 30px 50px rgba(0,0,0,.6)${press > 0.3 ? `, 0 0 40px ${COL.gold}55` : ""}`,
                display: "flex", alignItems: "center", justifyContent: "center", font: `800 ${fit(k, w - 30, 64, 0.62)}px ${SANS}`, color: COL.txt }}>{k}</div>
            </React.Fragment>
          );
        })}
      </div>
      {e.label && <Mono s={fit(e.label, 900, 30, 0.66)} c={COL.gold} w={800}>{e.label}</Mono>}
    </div>
  );
};

/** settings row with a switch that flips at `flip_at` */
const Toggle: React.FC<{ e: El }> = ({ e }) => {
  const f = useCurrentFrame();
  const fa = e.flip_at ?? e.at + 0.6;
  const k = interpolate(f, [fx(fa), fx(fa) + 7], [0, 1], { ...clamp, easing: easeOut });
  const on = e.to === "off" ? 1 - k : k;
  const c = e.to === "off" ? COL.red : COL.green;
  return (
    <Card w={W} h={190} label={(e.path || "SETTINGS").toUpperCase()} accent={c} glow={k > 0.5 ? c : undefined} glowAt={fa} shineAt={e.at + 0.1}>
      <div style={{ position: "absolute", left: 30, top: 84, font: `800 ${fit(e.text || "", 640, 54, 0.56)}px ${SANS}`, color: COL.txt, whiteSpace: "nowrap", letterSpacing: -1 }}>{e.text}</div>
      <div style={{ position: "absolute", right: 34, top: 76, width: 150, height: 80, borderRadius: 40, background: on > 0.5 ? COL.green : "#3A3D44",
        boxShadow: on > 0.5 ? `0 0 30px ${COL.green}88` : "inset 0 2px 8px rgba(0,0,0,.6)" }}>
        <div style={{ position: "absolute", top: 8, left: 8 + on * 70, width: 64, height: 64, borderRadius: 32, background: "#F4F4F2", boxShadow: "0 4px 10px rgba(0,0,0,.4)" }} />
      </div>
    </Card>
  );
};

/** the tool being taught: illustration tile + name + one-line description */
const App: React.FC<{ e: El }> = ({ e }) => {
  const c = col(e.color, COL.blue);
  return (
    <Card w={W} h={220} label={(e.label || "THE TOOL").toUpperCase()} accent={c} glow={c} glowAt={e.at} shineAt={e.at + 0.1}>
      <div style={{ position: "absolute", left: 28, top: 70, width: 128, height: 128, borderRadius: 32, background: `linear-gradient(160deg, ${c}55, ${c}15)`,
        border: `2px solid ${c}66`, display: "flex", alignItems: "center", justifyContent: "center" }}>
        {e.ill ? <Ill name={e.ill} size={100} at={e.at + 0.1} /> : <div style={{ font: `900 64px ${SANS}`, color: c }}>{(e.name || "?").slice(0, 1)}</div>}
      </div>
      <div style={{ position: "absolute", left: 186, top: 76, font: `900 ${fit(e.name || "", 700, 76, 0.58)}px ${SANS}`, color: COL.txt, letterSpacing: -2.5, whiteSpace: "nowrap" }}>{e.name}</div>
      {e.sub && <Reveal at={e.sub_at ?? e.at + 0.35} dy={14} style={{ position: "absolute", left: 188, top: 160 }}><Mono s={fit(e.sub, 700, 28, 0.66)} c={c} w={700}>{e.sub}</Mono></Reveal>}
    </Card>
  );
};

/** before -> after of a piece of text (bad prompt vs good prompt, weak line vs strong line) */
const BeforeAfter: React.FC<{ e: El }> = ({ e }) => {
  const f = useCurrentFrame();
  const L = e.left || {}, R = e.right || {};
  const la = wrap(L.text || "", 26).slice(0, 3), ra = wrap(R.text || "", 26).slice(0, 4);
  const hl = 110 + la.length * 52, hr = 110 + ra.length * 52;
  const lose = R.at !== undefined && f >= fx(R.at);
  return (
    <div style={{ position: "relative", width: W, height: hl + hr + 24 }}>
      <Reveal at={e.at} style={{ position: "absolute", left: 0, top: 0, opacity: lose ? 0.5 : 1 }}>
        <Card w={W} h={hl} label={(L.label || "BEFORE").toUpperCase()} accent={COL.red} shineAt={e.at + 0.1}>
          <div style={{ position: "absolute", left: 30, top: 72 }}>
            {la.map((ln, i) => <div key={i} style={{ font: `600 40px ${SANS}`, color: COL.mute, height: 52, whiteSpace: "nowrap", textDecoration: lose ? `line-through ${COL.red}` : "none" }}>{ln}</div>)}
          </div>
        </Card>
      </Reveal>
      {R.at !== undefined && (
        <Reveal at={R.at} style={{ position: "absolute", left: 0, top: hl + 24 }}>
          <Card w={W} h={hr} label={(R.label || "AFTER").toUpperCase()} accent={COL.green} glow={COL.green} glowAt={R.at} shineAt={R.at + 0.1}>
            <div style={{ position: "absolute", left: 30, top: 72 }}>
              {ra.map((ln, i) => <div key={i} style={{ font: `700 40px ${SANS}`, color: COL.txt, height: 52, whiteSpace: "nowrap" }}>{ln}</div>)}
            </div>
          </Card>
        </Reveal>
      )}
    </div>
  );
};

export const TUTORIAL_SPECS: Record<string, Spec> = {
  prompt: { h: (e) => 150 + Math.min(4, wrap(e.text || "", 30).length) * 62, R: Prompt },
  keys: { h: (e) => 170 + (e.label ? 60 : 0), R: Keys },
  toggle: { h: () => 190, R: Toggle },
  app: { h: () => 220, R: App },
  before_after: {
    h: (e) => 110 + Math.min(3, wrap(e.left?.text || "", 26).length) * 52 + 24 + 110 + Math.min(4, wrap(e.right?.text || "", 26).length) * 52,
    R: BeforeAfter,
  },
};
export const _unused = Easing;
