import {loadFont} from '@remotion/fonts';
import {Easing, interpolate, spring, staticFile} from 'remotion';

// Editorial "paper" look: warm cream canvas, ink black, one red accent.
export const C = {
  paper: '#F2EEE6',
  grid: 'rgba(20,20,20,0.055)',
  ink: '#141414',
  soft: '#3A3833',
  muted: '#8C877C',
  red: '#E2483D',
  redDeep: '#C23A30',
  card: '#FFFFFF',
  dark: '#17171B',
  darkLine: '#2A2A31',
  green: '#2FA36B',
  blue: '#3A6FE0',
};

export const FONTS = {
  sans: 'Inter, sans-serif',
  serif: '"Instrument Serif", serif',
  display: 'Anton, Impact, sans-serif',
  mono: '"JetBrains Mono", monospace',
  num: '"Space Grotesk", Inter, sans-serif',
};

const f = (family: string, file: string, weight = '400', style = 'normal') =>
  loadFont({family, url: staticFile(`fonts/${file}`), weight, style});

export const fontsReady = Promise.all([
  f('Inter', 'Inter-Medium.ttf', '500'),
  f('Inter', 'Inter-Bold.ttf', '700'),
  f('Inter', 'Inter-ExtraBold.ttf', '800'),
  f('Inter', 'Inter-Black.ttf', '900'),
  f('Instrument Serif', 'InstrumentSerif.woff2', '400'),
  f('Instrument Serif', 'InstrumentSerif-Italic.woff2', '400', 'italic'),
  f('Anton', 'Anton.woff2', '400'),
  f('JetBrains Mono', 'JetBrainsMono-Medium.ttf', '500'),
  f('JetBrains Mono', 'JetBrainsMono-Bold.ttf', '700'),
  f('Space Grotesk', 'SpaceGrotesk-Bold.ttf', '700'),
]);

// ---- animation helpers (frame-based; every time below is in frames)
export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const ease = Easing.bezier(0.16, 1, 0.3, 1);

/** 0→1 spring that starts at `at` (frames). */
export const pop = (frame: number, at: number, fps: number, damping = 14, stiffness = 170) =>
  at == null ? 0 : spring({frame: frame - at, fps, config: {damping, stiffness, mass: 0.8}});

/** 0→1 eased progress over `dur` frames from `at`. */
export const prog = (frame: number, at: number, dur = 12) =>
  at == null ? 0 : interpolate(frame, [at, at + dur], [0, 1], {...clamp, easing: ease});

export const sec = (s: number | undefined | null, fps: number) => (s == null ? null : Math.round(s * fps));

/** Parse "$16.3B", "40%", "2,899", "5M" → {pre, num, dec, suf} for count-ups. */
export function parseNumber(v: string) {
  const m = String(v).match(/^([^\d\-]*)(-?[\d,]*\.?\d+)(.*)$/);
  if (!m) return null;
  const raw = m[2].replace(/,/g, '');
  const dec = raw.includes('.') ? raw.split('.')[1].length : 0;
  return {pre: m[1], num: parseFloat(raw), dec, suf: m[3], commas: m[2].includes(',')};
}

export function formatNumber(n: number, dec: number, commas: boolean) {
  const s = n.toFixed(dec);
  if (!commas) return s;
  const [i, d] = s.split('.');
  return i.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (d ? '.' + d : '');
}
