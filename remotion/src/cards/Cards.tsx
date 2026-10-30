import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Video} from '@remotion/media';
import {C, FONTS, clamp, ease, formatNumber, parseNumber, pop, prog, sec} from '../theme';
import {Card, ReelProps, Scene} from '../types';

// Card positions are relative to the stage box (936 x 820). Frames inside a card are absolute (useCurrentFrame()).
const SW = 936, SH = 820;
const COL: Record<string, string> = {gold: C.red, red: C.red, white: C.ink, green: C.green, blue: C.blue, muted: C.muted, ice: C.blue};
const col = (c: any, d = C.ink) => COL[c] ?? d;

const shadow = '0 18px 0 rgba(20,20,20,0.10), 0 30px 60px rgba(20,20,20,0.12)';

// ---------------------------------------------------------------- building blocks
const Tag: React.FC<{text: string; at: number | null; color?: string; rotate?: number; size?: number; style?: React.CSSProperties}> =
  ({text, at, color = C.red, rotate = -3, size = 44, style}) => {
    const frame = useCurrentFrame(); const {fps} = useVideoConfig();
    const s = pop(frame, at, fps, 11, 220);
    if (at == null || frame < at) return null;
    return (
      <div style={{display: 'inline-block', background: color, color: '#fff', fontFamily: FONTS.display, fontSize: size,
        letterSpacing: 1, padding: `${size * 0.12}px ${size * 0.38}px`, textTransform: 'uppercase', rotate: `${rotate}deg`,
        scale: String(interpolate(s, [0, 1], [1.6, 1])), opacity: Math.min(1, s * 3), boxShadow: '0 6px 0 rgba(0,0,0,0.15)', ...style}}>
        {text}
      </div>
    );
  };

const Rise: React.FC<{at: number | null; children: React.ReactNode; dist?: number; style?: React.CSSProperties}> = ({at, children, dist = 40, style}) => {
  const frame = useCurrentFrame();
  const a = prog(frame, at, 10);
  if (at == null || frame < at - 1) return null;
  return <div style={{opacity: a, translate: `0px ${(1 - a) * dist}px`, ...style}}>{children}</div>;
};

/** Card frame entrance: spring up + slight tilt settle. */
const Enter: React.FC<{at: number; children: React.ReactNode; tilt?: number; style?: React.CSSProperties}> = ({at, children, tilt = -2.5, style}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const s = pop(frame, at, fps, 15, 150);
  return (
    <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
      translate: `0px ${interpolate(s, [0, 1], [140, 0])}px`, scale: String(interpolate(s, [0, 1], [0.86, 1])),
      rotate: `${interpolate(s, [0, 1], [tilt * 3, tilt * 0.3])}deg`, opacity: Math.min(1, s * 2.5), ...style}}>
      {children}
    </div>
  );
};

/** Big red condensed slogan with a drawn underline ("HOOKED IN 1 SECOND"). */
const Slogan: React.FC<{text: string; at: number | null; size?: number; color?: string}> = ({text, at, size = 120, color = C.red}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  if (at == null || frame < at) return null;
  const s = pop(frame, at, fps, 9, 260);
  const u = prog(frame, at + 4, 10);
  return (
    <div style={{textAlign: 'center', scale: String(interpolate(s, [0, 1], [1.5, 1])), opacity: Math.min(1, s * 3)}}>
      <span style={{fontFamily: FONTS.display, fontSize: size, color, textTransform: 'uppercase', lineHeight: 1.05,
        backgroundImage: `linear-gradient(${color}, ${color})`, backgroundRepeat: 'no-repeat', backgroundPosition: '0 100%',
        backgroundSize: `${u * 100}% ${Math.max(6, size * 0.06)}px`, paddingBottom: size * 0.06}}>{text}</span>
    </div>
  );
};

const Media: React.FC<{p: ReelProps; id?: string; at: number; style?: React.CSSProperties; zoom?: boolean}> = ({p, id, at, style, zoom = true}) => {
  const frame = useCurrentFrame();
  const m = id ? p.media[id] : undefined;
  if (!m) return null;
  const k = interpolate(frame - at, [0, 150], [1.0, 1.12], clamp);
  const common: React.CSSProperties = {width: '100%', height: '100%', objectFit: 'cover', scale: zoom ? String(k) : '1', ...style};
  return m.kind === 'video'
    ? <Video src={staticFile(m.src)} muted loop style={common} />
    : <Img src={staticFile(m.src)} style={common} />;
};

const Credit: React.FC<{text?: string}> = ({text}) => text ? (
  <div style={{position: 'absolute', top: 18, right: 18, background: 'rgba(20,20,20,0.75)', color: '#fff', fontFamily: FONTS.mono,
    fontSize: 18, padding: '6px 12px', borderRadius: 8, letterSpacing: 1}}>{text.toUpperCase()}</div>
) : null;

const Sparkline: React.FC<{at: number; w: number; h: number; down?: boolean; color?: string}> = ({at, w, h, down, color = C.red}) => {
  const frame = useCurrentFrame();
  const pts = Array.from({length: 24}, (_, i) => {
    const x = (i / 23) * w;
    const base = down ? 0.15 + 0.75 * (i / 23) ** 1.6 : 0.9 - 0.8 * (i / 23) ** 2.2;
    const y = (base + Math.sin(i * 1.7) * 0.03) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const p = prog(frame, at, 26);
  const len = w * 1.6;
  return (
    <svg width={w} height={h} style={{overflow: 'visible'}}>
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth={6} strokeLinejoin="round" strokeLinecap="round"
        strokeDasharray={len} strokeDashoffset={len * (1 - p)} />
      {p > 0.98 && <circle cx={w} cy={pts[23].split(',')[1]} r={11} fill="#fff" stroke={color} strokeWidth={5} />}
    </svg>
  );
};

// Small flat icon set (no outlines) for headline cards
const Icon: React.FC<{name?: string; at: number}> = ({name, at}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  if (!name) return null;
  const s = pop(frame, at, fps, 12, 180);
  const g: Record<string, React.ReactNode> = {
    chip: (<g><rect x="30" y="30" width="140" height="140" rx="22" fill={C.ink} /><rect x="58" y="58" width="84" height="84" rx="12" fill="none" stroke={C.red} strokeWidth="6" />
      <text x="100" y="114" textAnchor="middle" fontFamily="Anton" fontSize="44" fill="#fff">AI</text>
      {[50, 83, 116, 149].map((v) => <g key={v}><rect x={v - 5} y="8" width="10" height="22" fill={C.ink} /><rect x={v - 5} y="170" width="10" height="22" fill={C.ink} /></g>)}</g>),
    phone: (<g><rect x="55" y="10" width="90" height="180" rx="18" fill={C.ink} /><rect x="64" y="28" width="72" height="144" rx="8" fill="#fff" />
      <rect x="72" y="44" width="56" height="16" rx="5" fill={C.red} /><rect x="72" y="68" width="40" height="12" rx="5" fill={C.muted} /></g>),
    globe: (<g><circle cx="100" cy="100" r="80" fill={C.blue} /><ellipse cx="100" cy="100" rx="34" ry="80" fill="none" stroke="#fff" strokeWidth="5" />
      <line x1="20" y1="100" x2="180" y2="100" stroke="#fff" strokeWidth="5" /></g>),
    robot: (<g><rect x="35" y="50" width="130" height="110" rx="28" fill={C.ink} /><circle cx="75" cy="100" r="14" fill={C.red} /><circle cx="125" cy="100" r="14" fill={C.red} />
      <line x1="100" y1="50" x2="100" y2="22" stroke={C.ink} strokeWidth="7" /><circle cx="100" cy="18" r="10" fill={C.red} /></g>),
    coin: (<g><circle cx="100" cy="100" r="80" fill="#F2B630" /><text x="100" y="128" textAnchor="middle" fontFamily="Anton" fontSize="90" fill="#7A5300">$</text></g>),
    plane: (<g><polygon points="20,100 180,30 130,170 95,120" fill={C.red} /><line x1="95" y1="120" x2="180" y2="30" stroke="#fff" strokeWidth="6" /></g>),
  };
  return <svg width={170} height={170} viewBox="0 0 200 200" style={{scale: String(s), rotate: `${(1 - s) * -30}deg`}}>{g[name] ?? g.chip}</svg>;
};

// ---------------------------------------------------------------- cards
const NewsCard: React.FC<{c: Card; p: ReelProps; t0: number}> = ({c, p, t0}) => {
  const {fps} = useVideoConfig(); const f = (k: string) => sec(c[k], fps);
  const bg = p.media[c.bg_media]; const logo = p.media[c.logo];
  const src = String(c.source || '').replace(/^via\s+/i, '');
  return (
    <Enter at={t0} tilt={-2}>
      <div style={{width: 860, background: C.card, borderRadius: 26, border: `4px solid ${C.ink}`, boxShadow: shadow, overflow: 'hidden', position: 'relative'}}>
        <div style={{height: 64, background: C.ink, display: 'flex', alignItems: 'center', gap: 12, padding: '0 22px'}}>
          {['#FF5F57', '#FEBC2E', '#28C840'].map((x) => <div key={x} style={{width: 18, height: 18, borderRadius: 9, background: x}} />)}
          <div style={{marginLeft: 16, flex: 1, height: 36, borderRadius: 18, background: '#2B2B31', color: '#BDBAB2', fontFamily: FONTS.mono,
            fontSize: 20, display: 'flex', alignItems: 'center', padding: '0 18px'}}>{(src || 'news').toLowerCase().replace(/\s+/g, '')}.com</div>
        </div>
        <div style={{height: 330, position: 'relative', overflow: 'hidden', background: `repeating-linear-gradient(135deg, #EEE9DF 0 18px, #E6E0D4 18px 36px)`}}>
          {bg && <Media p={p} id={c.bg_media} at={t0} />}
          {bg?.credit && <Credit text={bg.credit} />}
        </div>
        <div style={{padding: '30px 36px 34px'}}>
          <Rise at={f('at') ?? t0}><div style={{fontFamily: FONTS.sans, fontWeight: 800, fontSize: 50, lineHeight: 1.12, color: C.ink, letterSpacing: -1}}>{c.title}</div></Rise>
          <Rise at={f('source_at')} dist={20}>
            <div style={{display: 'flex', alignItems: 'center', gap: 14, marginTop: 22}}>
              {logo ? <Img src={staticFile(logo.src)} style={{width: 44, height: 44, borderRadius: 10, background: '#fff', border: `2px solid ${C.ink}`}} />
                : <div style={{width: 44, height: 44, borderRadius: 22, background: C.red, color: '#fff', fontFamily: FONTS.display, fontSize: 26,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'}}>{(src[0] || '•').toUpperCase()}</div>}
              <div style={{fontFamily: FONTS.mono, fontSize: 24, color: C.soft}}>{src || 'source'} · <span style={{color: C.muted}}>reported</span></div>
            </div>
          </Rise>
        </div>
      </div>
      <div style={{position: 'absolute', top: 70, left: -6}}><Tag text={c.tag || 'BREAKING'} at={f('tag_at') ?? t0} rotate={-5} size={48} /></div>
    </Enter>
  );
};

const FootageCard: React.FC<{c: Card; p: ReelProps; t0: number}> = ({c, p, t0}) => {
  const {fps} = useVideoConfig();
  const m = p.media[c.media];
  return (
    <Enter at={t0} tilt={2}>
      <div style={{width: 860, height: 700, borderRadius: 34, border: `14px solid ${C.ink}`, overflow: 'hidden', position: 'relative', boxShadow: shadow, background: C.ink}}>
        <Media p={p} id={c.media} at={t0} />
        <Credit text={m?.credit} />
      </div>
      {c.caption && <div style={{position: 'absolute', bottom: 18, left: 30}}><Tag text={c.caption} at={sec(c.caption_at, fps) ?? t0 + 6} rotate={-3} size={50} /></div>}
    </Enter>
  );
};

const NumberCard: React.FC<{c: Card; t0: number; counter?: boolean}> = ({c, t0, counter}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const at = sec(counter ? c.at : c.value_at, fps) ?? t0;
  const value = counter ? `${c.prefix || ''}${c.to}${c.suffix || ''}` : String(c.value || '');
  const pn = parseNumber(value);
  const p = prog(frame, at, 24);
  const shown = pn ? `${pn.pre}${formatNumber(pn.num * p, pn.dec, pn.commas || (counter && Math.abs(pn.num) >= 1000))}${pn.suf}` : value;
  const down = /drop|fall|loss|lost|down|crash|cut|−|-/i.test(`${c.label} ${c.note} ${c.done_text}`);
  return (
    <Enter at={t0} tilt={-1.5}>
      <div style={{width: 860, background: C.dark, borderRadius: 30, padding: '36px 44px 30px', boxShadow: shadow, border: `2px solid ${C.darkLine}`}}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <div style={{fontFamily: FONTS.mono, fontSize: 24, color: '#A8A49B', letterSpacing: 1, textTransform: 'uppercase'}}>{c.label || ''}</div>
          <div style={{fontFamily: FONTS.mono, fontSize: 20, color: '#6E6B64'}}>insights</div>
        </div>
        <div style={{fontFamily: FONTS.display, fontSize: pn && shown.length > 7 ? 170 : 210, color: C.red, lineHeight: 1.1, marginTop: 14,
          scale: String(interpolate(pop(frame, at, fps, 10, 200), [0, 1], [0.7, 1])), transformOrigin: 'left center'}}>{frame >= at - 1 ? shown : ''}</div>
        <div style={{fontFamily: FONTS.sans, fontWeight: 700, fontSize: 40, color: '#F2EEE6', minHeight: 50}}>
          <Rise at={sec(counter ? c.done_at : c.note_at, fps)} dist={16}>{counter ? c.done_text : c.note}</Rise>
        </div>
        <div style={{marginTop: 26, borderTop: '2px dashed #34343B', paddingTop: 22}}><Sparkline at={at} w={770} h={150} down={down} /></div>
      </div>
    </Enter>
  );
};

const PercentCard: React.FC<{c: Card; t0: number}> = ({c, t0}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const at = sec(c.at, fps) ?? t0; const v = Number(c.value || 0);
  const p = prog(frame, at, 30); const r = 230, L = 2 * Math.PI * r;
  return (
    <Enter at={t0} tilt={0}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
        <svg width={560} height={560} viewBox="-280 -280 560 560">
          <circle r={r + 30} fill={C.card} stroke={C.ink} strokeWidth={8} />
          {Array.from({length: 60}, (_, i) => {
            const a = (i / 60) * 2 * Math.PI; const l = i % 5 ? 14 : 30;
            return <line key={i} x1={Math.sin(a) * (r + 18)} y1={-Math.cos(a) * (r + 18)} x2={Math.sin(a) * (r + 18 - l)} y2={-Math.cos(a) * (r + 18 - l)} stroke={C.ink} strokeWidth={i % 5 ? 3 : 6} />;
          })}
          <circle r={r - 40} fill="none" stroke="#EDE8DE" strokeWidth={46} />
          <circle r={r - 40} fill="none" stroke={C.red} strokeWidth={46} strokeDasharray={2 * Math.PI * (r - 40)}
            strokeDashoffset={2 * Math.PI * (r - 40) * (1 - (v / 100) * p)} transform="rotate(-90)" />
          <rect x={-150} y={-52} width={300} height={104} rx={18} fill={C.ink} />
          <text x={0} y={30} textAnchor="middle" fontFamily="JetBrains Mono" fontWeight={700} fontSize={78} fill="#fff">{Math.round(v * p)}%</text>
        </svg>
        <Rise at={sec(c.label_at, fps) ?? at + 10}><div style={{fontFamily: FONTS.display, fontSize: 78, color: C.ink, textTransform: 'uppercase', marginTop: 10, textAlign: 'center'}}>{c.label}</div></Rise>
      </div>
    </Enter>
  );
};

const HeadlineCard: React.FC<{c: Card; t0: number}> = ({c, t0}) => {
  const {fps} = useVideoConfig();
  return (
    <Enter at={t0} tilt={-2}>
      <div style={{width: 820, background: C.card, border: `5px solid ${C.ink}`, borderRadius: 18, padding: '46px 48px 54px', boxShadow: shadow,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
        <Icon name={c.icon} at={t0 + 2} />
        <Rise at={sec(c.at, fps) ?? t0}><div style={{fontFamily: FONTS.display, fontSize: 104, lineHeight: 1.0, color: C.ink, textTransform: 'uppercase', textAlign: 'center'}}>{c.title}</div></Rise>
        {c.sub && <Rise at={sec(c.sub_at, fps) ?? t0 + 10}><div style={{fontFamily: FONTS.serif, fontStyle: 'italic', fontSize: 76, color: C.red, textAlign: 'center', lineHeight: 1.05}}>{c.sub}</div></Rise>}
      </div>
    </Enter>
  );
};

const SlamCard: React.FC<{c: Card; t0: number}> = ({c, t0}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const at = sec(c.at, fps) ?? t0;
  const shake = frame >= at ? Math.sin((frame - at) * 2.2) * Math.max(0, 1 - (frame - at) / 9) * 14 : 0;
  const len = String(c.title || '').length;
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', translate: `${shake}px 0px`, rotate: '-3deg'}}>
      <Slogan text={c.title} at={at} size={len > 12 ? 150 : len > 7 ? 200 : 260} color={c.color === 'white' ? C.ink : C.red} />
    </AbsoluteFill>
  );
};

const SplitCard: React.FC<{c: Card; t0: number}> = ({c, t0}) => {
  const {fps} = useVideoConfig(); const L = c.left || {}, R = c.right || {};
  const side = (s: any, k: number) => (
    <Rise at={sec(s.at, fps) ?? t0 + k * 8} dist={60}>
      <div style={{width: 380, height: 380, background: k ? C.ink : C.card, color: k ? '#fff' : C.ink, border: `5px solid ${C.ink}`, borderRadius: 22,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 26, textAlign: 'center', rotate: `${k ? 3 : -3}deg`, boxShadow: shadow,
        fontFamily: FONTS.display, fontSize: String(s.text || '').length > 10 ? 60 : 84, textTransform: 'uppercase', lineHeight: 1.05}}>{s.text}</div>
    </Rise>
  );
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 30}}>
      <Rise at={sec(c.title_at, fps) ?? t0}><div style={{fontFamily: FONTS.mono, fontSize: 30, color: C.muted, letterSpacing: 2, textTransform: 'uppercase'}}>{c.title}</div></Rise>
      <div style={{display: 'flex', alignItems: 'center', gap: 20}}>
        {side(L, 0)}
        <div style={{width: 96, height: 96, borderRadius: 48, background: C.red, color: '#fff', fontFamily: FONTS.display, fontSize: 44,
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2, margin: '0 -40px'}}>VS</div>
        {side(R, 1)}
      </div>
      {c.result && <Slogan text={c.result} at={sec(c.result_at, fps)} size={84} />}
    </AbsoluteFill>
  );
};

const CompareCard: React.FC<{c: Card; t0: number}> = ({c, t0}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const ta = sec(c.to_at, fps); const a = prog(frame, ta == null ? null : ta - 8, 10);
  const box = (txt: string, red: boolean) => (
    <div style={{padding: '26px 46px', borderRadius: 20, border: `5px solid ${C.ink}`, background: red ? C.red : C.card, color: red ? '#fff' : C.ink,
      fontFamily: FONTS.display, fontSize: 92, textTransform: 'uppercase', boxShadow: shadow, textAlign: 'center'}}>{txt}</div>
  );
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 10}}>
      <Rise at={sec(c.title_at, fps) ?? t0}><div style={{fontFamily: FONTS.mono, fontSize: 30, color: C.muted, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 14}}>{c.title}</div></Rise>
      <Rise at={sec(c.from_at, fps) ?? t0 + 4}>{box(c.from_text, false)}</Rise>
      <svg width={60} height={130}><line x1={30} y1={8} x2={30} y2={8 + 92 * a} stroke={C.ink} strokeWidth={10} strokeLinecap="round" />
        {a > 0.95 && <polygon points="6,98 54,98 30,126" fill={C.ink} />}</svg>
      <Rise at={ta}>{box(c.to_text, true)}</Rise>
      {c.result && <div style={{marginTop: 26}}><Slogan text={c.result} at={sec(c.result_at, fps)} size={70} color={C.ink} /></div>}
    </AbsoluteFill>
  );
};

const ListCard: React.FC<{c: Card; t0: number; check?: boolean}> = ({c, t0, check}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const items = (c.items || []).slice(0, 4);
  const shownN = items.filter((it: any) => (sec(it.at, fps) ?? 1e9) <= frame).length;
  return (
    <Enter at={t0} tilt={-1.5}>
      <div style={{width: 860, background: C.card, border: `5px solid ${C.ink}`, borderRadius: 22, padding: '40px 44px', boxShadow: shadow}}>
        <div style={{fontFamily: FONTS.display, fontSize: 72, color: check ? C.ink : col(c.color), textTransform: 'uppercase', marginBottom: 18}}>{c.title}</div>
        {check && <div style={{display: 'flex', gap: 16, marginBottom: 26}}>{items.map((_: any, k: number) => (
          <div key={k} style={{flex: 1, height: 84, borderRadius: 14, border: `4px ${k < shownN ? 'solid' : 'dashed'} ${k < shownN ? C.red : '#CFC8BA'}`,
            background: k < shownN ? '#FBE3DF' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: FONTS.display, fontSize: 52, color: k < shownN ? C.red : '#CFC8BA'}}>{k + 1}</div>))}</div>}
        {items.map((it: any, k: number) => {
          const at = sec(it.at, fps);
          const strikeP = prog(frame, at == null ? null : at + 6, 10);
          return (
            <Rise key={k} at={at} dist={24}>
              <div style={{display: 'flex', alignItems: 'center', gap: 22, padding: '16px 0', borderTop: k ? '2px dashed #DDD6C8' : 'none', position: 'relative'}}>
                <div style={{width: 54, height: 54, borderRadius: 12, background: check ? C.ink : C.red, color: '#fff', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontFamily: FONTS.display, fontSize: 32, flexShrink: 0}}>{check ? '✓' : '✕'}</div>
                <div style={{fontFamily: FONTS.sans, fontWeight: 700, fontSize: 46, color: C.ink, position: 'relative'}}>
                  {it.text}
                  {!check && it.strike !== false && <div style={{position: 'absolute', left: -6, top: '52%', height: 8, background: C.red, width: `${strikeP * 104}%`, borderRadius: 4}} />}
                </div>
              </div>
            </Rise>
          );
        })}
        {c.final && <div style={{marginTop: 20}}><Tag text={c.final} at={sec(c.final_at, fps)} size={46} rotate={-2} /></div>}
      </div>
    </Enter>
  );
};

const WarningCard: React.FC<{c: Card; t0: number}> = ({c, t0}) => {
  const {fps} = useVideoConfig();
  return (
    <Enter at={t0} tilt={1.5}>
      <div style={{width: 860, background: C.card, border: `5px solid ${C.ink}`, borderRadius: 22, padding: '50px 44px 44px', boxShadow: shadow, position: 'relative'}}>
        <div style={{position: 'absolute', top: -38, right: 40}}><Tag text="⚠ HEADS UP" at={t0} color={C.ink} rotate={4} size={40} /></div>
        <Rise at={sec(c.title_at, fps) ?? t0}><div style={{fontFamily: FONTS.display, fontSize: 92, color: C.red, textTransform: 'uppercase', lineHeight: 1.02}}>{c.title}</div></Rise>
        {c.sub && <Rise at={sec(c.sub_at, fps) ?? t0 + 6}><div style={{fontFamily: FONTS.serif, fontStyle: 'italic', fontSize: 64, color: C.ink, marginTop: 10}}>{c.sub}</div></Rise>}
        <div style={{display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 26}}>
          {(c.chips || []).slice(0, 3).map((ch: any, k: number) => <Tag key={k} text={ch.text} at={sec(ch.at, fps)} color={k % 2 ? C.ink : C.red} rotate={k % 2 ? 2 : -2} size={36} />)}
        </div>
        {c.big && <div style={{marginTop: 26}}><Slogan text={c.big} at={sec(c.big_at, fps)} size={130} /></div>}
      </div>
    </Enter>
  );
};

const MoneyCard: React.FC<{c: Card; t0: number}> = ({c, t0}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const sym = String(c.symbol || '$').slice(0, 2);
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      {Array.from({length: 12}, (_, k) => {
        const ph = ((frame - t0) / 70 + k * 0.29) % 1;
        if (frame < t0) return null;
        return <div key={k} style={{position: 'absolute', left: ((k * 157) % 760) + 40, top: -120 + ph * (SH + 160), width: 150, height: 74, borderRadius: 10,
          background: '#7FC79A', border: `4px solid ${C.ink}`, rotate: `${(k * 37 + frame * 1.6) % 360}deg`, display: 'flex', alignItems: 'center',
          justifyContent: 'center', fontFamily: FONTS.display, fontSize: 42, color: '#1E5A36', opacity: Math.min(1, ph * 6, (1 - ph) * 6)}}>{sym}</div>;
      })}
      <div style={{background: C.paper, padding: '20px 40px', borderRadius: 24}}>
        <Slogan text={c.line1} at={sec(c.line1_at, fps) ?? t0} size={170} color={C.green} />
        <Rise at={sec(c.line2_at, fps)}><div style={{fontFamily: FONTS.serif, fontStyle: 'italic', fontSize: 80, color: C.ink, textAlign: 'center'}}>{c.line2}</div></Rise>
      </div>
    </AbsoluteFill>
  );
};

const CtaCard: React.FC<{c: Card; p: ReelProps; t0: number}> = ({c, p, t0}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const a = prog(frame, t0, 22);
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 24}}>
      <svg width={220} height={220} viewBox="0 0 200 200" style={{translate: `${interpolate(a, [0, 1], [-600, 0])}px ${Math.sin(frame / 8) * 8}px`, rotate: `${(1 - a) * 25}deg`}}>
        <polygon points="20,100 180,30 130,170 95,120" fill={C.red} stroke={C.ink} strokeWidth="6" strokeLinejoin="round" />
        <line x1="95" y1="120" x2="180" y2="30" stroke={C.ink} strokeWidth="6" />
      </svg>
      <Rise at={sec(c.line1_at, fps) ?? t0 + 4}><div style={{fontFamily: FONTS.sans, fontWeight: 900, fontSize: 96, color: C.ink, letterSpacing: -2}}>{c.line1}</div></Rise>
      <Rise at={sec(c.line2_at, fps) ?? t0 + 12}><div style={{fontFamily: FONTS.serif, fontStyle: 'italic', fontSize: 84, color: C.red, textAlign: 'center', lineHeight: 1.0}}>{c.line2}</div></Rise>
      <Rise at={t0 + 24}><div style={{marginTop: 22, background: C.ink, color: '#fff', fontFamily: FONTS.sans, fontWeight: 800, fontSize: 44, padding: '22px 46px', borderRadius: 999}}>Follow {p.meta.handle}</div></Rise>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- the hook (before the first scene): key words slam in the stage
export const HookStage: React.FC<{p: ReelProps}> = ({p}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const items = p.hook.items;
  const shown = items.filter((it) => sec(it.t, fps)! <= frame + 1);
  const list = shown.length ? shown : items.slice(0, 1);
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 6}}>
      {list.map((it, k) => {
        const at = k === 0 && sec(it.t, fps)! <= 1 ? -30 : sec(it.t, fps)!;   // first key word is on screen from frame 1 (cover)
        const last = k === list.length - 1;
        const s = pop(frame, at, fps, 9, 260);
        const len = it.text.length;
        return (
          <div key={k} style={{fontFamily: FONTS.display, fontSize: len > 14 ? 130 : len > 9 ? 170 : 220, lineHeight: 1.0, textTransform: 'uppercase',
            color: last ? C.red : C.ink, scale: String(interpolate(s, [0, 1], [1.7, 1])), opacity: Math.min(1, s * 3),
            rotate: `${k % 2 ? 2 : -2}deg`, textAlign: 'center'}}>{it.text}</div>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- dispatcher
export const CardView: React.FC<{scene: Scene; p: ReelProps}> = ({scene, p}) => {
  const {fps} = useVideoConfig();
  const c = scene.card; const t0 = sec(scene.start, fps)!;
  switch (c.type) {
    case 'news': return <NewsCard c={c} p={p} t0={t0} />;
    case 'footage': return p.media[c.media] ? <FootageCard c={c} p={p} t0={t0} /> : <HeadlineCard c={{...c, title: c.caption}} t0={t0} />;
    case 'big_number': return <NumberCard c={c} t0={t0} />;
    case 'counter': return <NumberCard c={c} t0={t0} counter />;
    case 'percent': return <PercentCard c={c} t0={t0} />;
    case 'title_slam': return <SlamCard c={c} t0={t0} />;
    case 'split': return <SplitCard c={c} t0={t0} />;
    case 'compare_arrow': return <CompareCard c={c} t0={t0} />;
    case 'strike_list': return <ListCard c={c} t0={t0} />;
    case 'checklist': return <ListCard c={c} t0={t0} check />;
    case 'warning': return <WarningCard c={c} t0={t0} />;
    case 'money_rain': return <MoneyCard c={c} t0={t0} />;
    case 'cta': return <CtaCard c={c} p={p} t0={t0} />;
    default: return <HeadlineCard c={c} t0={t0} />;
  }
};
