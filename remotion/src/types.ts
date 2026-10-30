// Props produced by pipeline/render/remotion_render.py. All times are in SECONDS (convert with fps).
export type Word = {t: string; s: number; e: number; hl: boolean};
export type Phrase = {s: number; e: number; from: number; to: number};
export type Card = {type: string; [k: string]: any};
export type Scene = {start: number; end: number; mood: string; tint?: string; card: Card};
export type MediaItem = {kind: 'image' | 'logo' | 'video'; src: string; credit?: string; frames?: number};

export type ReelProps = {
  durationFrames: number;
  fps: number;
  words: Word[];
  phrases: Phrase[];
  scenes: Scene[];
  hook: {end: number; items: {t: number; text: string}[]};
  meta: {tag: string; ep: number; kicker: string; handle: string; topic: string};
  mascot: {sprites: string[]; track: number[]};
  media: Record<string, MediaItem>;
};
