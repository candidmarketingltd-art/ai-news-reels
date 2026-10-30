import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig, delayRender, continueRender} from 'remotion';
import {C, FONTS, clamp, ease, fontsReady, pop, prog, sec} from './theme';
import {ReelProps, Scene} from './types';
import {CardView, HookStage} from './cards/Cards';

const W = 1080;
export const STAGE = {x: 72, y: 590, w: 936, h: 820};   // ends at y=1410 (Instagram's caption area starts ~1590)   // the visual area (cards / footage)

// ---------------------------------------------------------------- background: cream paper + fine grid
const Paper: React.FC = () => (
  <AbsoluteFill style={{background: C.paper}}>
    <AbsoluteFill
      style={{
        backgroundImage: `linear-gradient(${C.grid} 1.5px, transparent 1.5px), linear-gradient(90deg, ${C.grid} 1.5px, transparent 1.5px)`,
        backgroundSize: '44px 44px',
        backgroundPosition: '-1px -1px',
      }}
    />
    <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(255,255,255,0.55), rgba(242,238,230,0) 60%)'}} />
  </AbsoluteFill>
);

// ---------------------------------------------------------------- top labels
const Kicker: React.FC<{p: ReelProps; section: string}> = ({p, section}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{position: 'absolute', top: 132, left: 72, right: 72, display: 'flex', justifyContent: 'space-between',
      fontFamily: FONTS.mono, fontSize: 26, color: C.muted, letterSpacing: 1, opacity: prog(frame, 0, 8)}}>
      <span>{section}</span>
      <span>EP {String(p.meta.ep).padStart(2, '0')} · {p.meta.tag}</span>
    </div>
  );
};

// ---------------------------------------------------------------- the spoken sentence as the headline (reference style)
const Headline: React.FC<{p: ReelProps}> = ({p}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const ph = p.phrases.find((x) => t >= x.s - 0.05 && t < x.e) ?? null;
  if (!ph) return null;
  const words = p.words.slice(ph.from, ph.to + 1);
  const n = words.reduce((a, w) => a + w.t.length + 1, 0);
  const size = n > 85 ? 62 : n > 60 ? 70 : 80;
  return (
    <div style={{position: 'absolute', top: 210, left: 72, right: 72, height: 340, display: 'flex', alignItems: 'flex-start'}}>
      <div style={{fontFamily: FONTS.sans, fontWeight: 700, fontSize: size, lineHeight: 1.13, color: C.ink, letterSpacing: -1.5,
        opacity: prog(frame, sec(ph.s, fps)! - 3, 5), translate: `0px ${interpolate(prog(frame, sec(ph.s, fps)! - 3, 6), [0, 1], [24, 0])}px`}}>
        {words.map((w, i) => {
          const at = sec(w.s, fps)! - 2;
          const a = prog(frame, at, 5);                     // spoken -> full ink; not yet spoken -> faint
          const hl = w.hl;
          return (
            <span key={i} style={{
              display: 'inline-block', marginRight: size * 0.24, opacity: interpolate(a, [0, 1], [0.16, 1]),
              translate: `0px ${interpolate(a, [0, 1], [6, 0])}px`,
              fontFamily: hl ? FONTS.serif : FONTS.sans, fontStyle: hl ? 'italic' : 'normal', fontWeight: hl ? 400 : 700,
              fontSize: hl ? size * 1.14 : size, color: hl && a > 0.5 ? C.red : C.ink, letterSpacing: hl ? 0 : -1.5,
            }}>{w.t}</span>
          );
        })}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- Rohan sticker (lip-synced sprite track)
const Host: React.FC<{p: ReelProps}> = ({p}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const idx = p.mascot.track[Math.min(frame, p.mascot.track.length - 1)] ?? 0;
  const name = p.mascot.sprites[idx];
  const speaking = /_(A|O|E|MBP)_/.test(name);
  const s = pop(frame, 4, fps, 12);
  return (
    <div style={{position: 'absolute', left: 60, top: 1424, width: 168, height: 168, borderRadius: 999, overflow: 'hidden',
      background: C.card, border: `5px solid ${C.ink}`, boxShadow: '0 10px 0 rgba(20,20,20,0.12)', scale: String(s),
      rotate: `${interpolate(Math.sin(frame / 9), [-1, 1], [-2, 2])}deg`}}>
      <Img src={staticFile(`mascot/${name}`)} style={{width: 168, height: 168, translate: `0px ${speaking ? 6 : 8}px`}} />
    </div>
  );
};

const HostLabel: React.FC = () => (
  <div style={{position: 'absolute', left: 244, top: 1470, fontFamily: FONTS.mono, fontSize: 22, color: C.muted, lineHeight: 1.4}}>
    <div style={{color: C.ink, fontWeight: 700}}>ROHAN</div>
    <div>explains the news</div>
  </div>
);

// ---------------------------------------------------------------- halftone wipe between stories
const Halftone: React.FC<{at: number}> = ({at}) => {
  const frame = useCurrentFrame();
  const d = frame - at;
  if (d < -6 || d > 8) return null;
  const k = d < 0 ? interpolate(d, [-6, 0], [0, 1], clamp) : interpolate(d, [0, 8], [1, 0], {...clamp, easing: ease});
  const cell = 54;
  const cols = Math.ceil(W / cell) + 1, rows = Math.ceil(1920 / cell) + 1;
  const dots = [];
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++) {
      const delay = (r / rows) * 0.35;
      const kk = Math.max(0, Math.min(1, (k - delay) / 0.65));
      const rad = kk * cell * 0.78;
      if (rad > 0.5) dots.push(<circle key={`${r}-${c}`} cx={c * cell} cy={r * cell} r={rad} fill={C.ink} />);
    }
  return (
    <svg width={W} height={1920} style={{position: 'absolute', inset: 0}}>{dots}</svg>
  );
};

// ---------------------------------------------------------------- composition
export const Reel: React.FC<ReelProps> = (p) => {
  const [handle] = React.useState(() => delayRender('fonts'));
  React.useEffect(() => { fontsReady.then(() => continueRender(handle)); }, [handle]);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const scenes = p.scenes;
  const cur: Scene | undefined = [...scenes].reverse().find((s) => t >= s.start);
  const storyStarts = scenes.filter((s) => s.card.type === 'news' || s.card.type === 'cta').map((s) => sec(s.start, fps)!);
  const storyNo = scenes.filter((s) => s.card.type === 'news' && s.start <= t).length;
  const section = `// ${String(Math.max(1, storyNo)).padStart(2, '0')} · ${p.meta.kicker}`;
  return (
    <AbsoluteFill style={{background: C.paper, overflow: 'hidden'}}>
      <Paper />
      <Kicker p={p} section={section} />
      <Headline p={p} />
      <div style={{position: 'absolute', left: STAGE.x, top: STAGE.y, width: STAGE.w, height: STAGE.h}}>
        {cur ? <CardView key={scenes.indexOf(cur)} scene={cur} p={p} /> : <HookStage p={p} />}
      </div>
      <Host p={p} />
      <HostLabel />
      {storyStarts.map((f) => <Halftone key={f} at={f} />)}
      <div style={{position: 'absolute', bottom: 0, left: 0, height: 10, background: C.red,
        width: `${interpolate(frame, [0, p.durationFrames], [0, 100], clamp)}%`}} />
    </AbsoluteFill>
  );
};
