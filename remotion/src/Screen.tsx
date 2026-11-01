import React from "react";
import { interpolate, spring, useCurrentFrame, Easing, Img, OffthreadVideo, staticFile, Sequence, Loop } from "remotion";
import { COL, SANS, MONO, FPS, clamp, easeOut, fx, Card, Mono } from "./lib";
import { KINDS } from "./AppKinds";

/* ------------------------------------------------------------------------------------------------
   "screen": an app walkthrough. A browser window (web) or a phone (phone) shows a simplified, generic
   recreation of the app's UI; a cursor (or finger tap) moves to each control the voice names, clicks it,
   the camera pushes in on it, and the next screen appears. Views are described as data:
     view = { sidebar?: [label], profile?: label, chat?: [{from: "user"|"ai", text}], input?: text,
              menu?: {items: [label], anchor?: "profile"|"top"},
              panel?: {title, nav?: [label], active?: label, back?: bool,
                       rows: [{label, kind: "toggle"|"arrow"|"value"|"field"|"button"|"text", value?, on?}]} }
     step  = { at, view, action?: {kind: "click"|"type"|"toggle"|"point", target: label, text?, at?} }
   ------------------------------------------------------------------------------------------------ */
type Row = { label: string; kind?: string; value?: string; on?: boolean };
type View = {
  kind?: string; [k: string]: any;
  input_buttons?: string[]; top_buttons?: string[];
  sidebar?: string[]; profile?: string; chat?: { from: string; text: string }[]; input?: string; title?: string;
  menu?: { items: string[]; anchor?: string };
  panel?: { title?: string; nav?: string[]; active?: string; back?: boolean; rows?: Row[] };
};
type Action = { kind?: string; target?: string; text?: string; at?: number };
type Step = { at: number; view: View; action?: Action };
type Box = { x: number; y: number; w: number; h: number };

const THEMES: Record<string, Record<string, string>> = {
  dark: { bg: "#212121", side: "#171717", panel: "#2B2B2B", text: "#ECECEC", mute: "#9B9B9B", line: "#3A3A3A", bubble: "#303030", hover: "#2F2F2F", field: "#1E1E1E", accent: "#10A37F", shade: "rgba(0,0,0,0.55)" },
  claude: { bg: "#FAF9F5", side: "#F0EEE6", panel: "#FFFFFF", text: "#1F1E1D", mute: "#73726C", line: "#E5E2D9", bubble: "#F0EEE6", hover: "#ECE9DF", field: "#FFFFFF", accent: "#C96442", shade: "rgba(0,0,0,0.3)" },
  gemini: { bg: "#FFFFFF", side: "#F0F4F9", panel: "#FFFFFF", text: "#1F1F1F", mute: "#5F6368", line: "#E3E3E3", bubble: "#E9EEF6", hover: "#E1E7F0", field: "#F0F4F9", accent: "#4285F4", shade: "rgba(0,0,0,0.3)" },
  perplexity: { bg: "#191A1A", side: "#202222", panel: "#202222", text: "#E8E8E6", mute: "#8D9191", line: "#2F3131", bubble: "#2A2C2C", hover: "#2A2C2C", field: "#202222", accent: "#20B8CD", shade: "rgba(0,0,0,0.55)" },
  light: { bg: "#FFFFFF", side: "#F7F7F8", panel: "#FFFFFF", text: "#0D0D0D", mute: "#6B6B6B", line: "#E3E3E3", bubble: "#F1F1F1", hover: "#ECECEC", field: "#F7F7F8", accent: "#10A37F", shade: "rgba(0,0,0,0.35)" },
};

const norm = (s?: string) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "") || (s || "").trim();
const wrap = (t: string, n: number) => {
  const out: string[] = []; let cur = "";
  for (const w of (t || "").split(/\s+/)) { if (cur && (cur + " " + w).length > n) { out.push(cur); cur = w; } else cur = cur ? cur + " " + w : w; }
  if (cur) out.push(cur);
  return out;
};

/* ------------------------------------------------------------- geometry (shared by drawing and the cursor) */
export const SCREEN_GEOM = {
  web: { W: 940, H: 800, bar: 50, cw: 814, ch: 649, s: 1.15 },   // UI is laid out at 814x649 and drawn 15% bigger (readable on a phone)
  phone: { W: 470, H: 900, bar: 0, cw: 430, ch: 860, s: 1 },
};

type Item = { id: string; label: string; box: Box; kind: string; row?: Row; extra?: any };

function layout(v: View, dev: "web" | "phone") {
  const g = SCREEN_GEOM[dev];
  if (v.kind && KINDS[v.kind]) return KINDS[v.kind].layout(v, dev, g) as Item[];
  const items: Item[] = [];
  const add = (label: string, box: Box, kind: string, row?: Row, extra?: any) => items.push({ id: norm(label), label, box, kind, row, extra });
  const web = dev === "web";
  const sideW = web ? 232 : 300;
  const drawer = !!v.sidebar && (web || !v.panel);
  if (web || drawer) {
    (v.sidebar || []).forEach((s, i) => add(s, { x: 12, y: (web ? 84 : 110) + i * (web ? 48 : 58), w: sideW - 24, h: web ? 42 : 50 }, "side"));
  }
  if (v.profile) add(v.profile, web || drawer ? { x: 12, y: g.ch - (web ? 64 : 80), w: sideW - 24, h: web ? 50 : 60 } : { x: 14, y: 46, w: 52, h: 52 }, "profile");
  const mainX = web ? sideW : 0, mainW = g.cw - mainX;
  if (v.input !== undefined) {
    const ib = v.input_buttons || [], bw = (lab: string) => (lab.length <= 2 ? (web ? 44 : 48) : 18 + lab.length * (web ? 12 : 13));
    const iy = g.ch - (web ? 86 : 96), ih = web ? 58 : 64;
    let bx = mainX + 30 + 8;
    ib.forEach((lab) => { const w = bw(lab); add(lab, { x: bx, y: iy + (ih - (web ? 44 : 48)) / 2, w, h: web ? 44 : 48 }, "ibtn"); bx += w + 6; });
    add("input", { x: mainX + 30, y: iy, w: mainW - 60, h: ih }, "input", undefined, { pad: bx - (mainX + 30) });
  }
  {
    let bx = g.cw - 16;
    (v.top_buttons || []).slice().reverse().forEach((lab) => {
      const w = lab.length <= 2 ? 48 : 22 + lab.length * 13; bx -= w;
      add(lab, { x: bx, y: web ? 14 : 52, w, h: 46 }, "tbtn"); bx -= 8;
    });
  }
  if (v.menu) {
    const n = v.menu.items.length, ih = web ? 46 : 58;
    if (web) {
      const top = v.menu.anchor === "top" ? 60 : g.ch - 76 - n * ih - 16;
      const x = v.menu.anchor === "top" ? g.cw - 290 : 12;
      v.menu.items.forEach((s, i) => add(s, { x: x + 8, y: top + 8 + i * ih, w: 260, h: ih - 4 }, "menu"));
    } else {
      const top = g.ch - n * ih - 40;
      v.menu.items.forEach((s, i) => add(s, { x: 18, y: top + i * ih, w: g.cw - 36, h: ih - 4 }, "menu"));
    }
  }
  if (v.panel) {
    const p = v.panel, rows = p.rows || [];
    const nav = web ? p.nav || [] : [];
    const pw = web ? 760 : g.cw, px = web ? (g.cw - pw) / 2 : 0;
    const rx = px + (nav.length ? 210 : 0), rw = pw - (nav.length ? 210 : 0);
    let y = web ? 60 + 76 : 46 + 86;
    nav.forEach((s, i) => add(s, { x: px + 14, y: web ? 60 + 76 + i * 46 : 0, w: 182, h: 40 }, "nav"));
    rows.forEach((r) => {
      const field = r.kind === "field";
      const lines = field ? Math.min(4, Math.max(2, wrap(r.value || "", web ? 44 : 30).length)) : 0;
      const h = field ? 56 + lines * 30 + 20 : web ? 62 : 70;
      add(r.label, { x: rx + 18, y, w: rw - 36, h }, "row", r);
      y += h + 6;
    });
    if (!web && p.back) add("back", { x: 8, y: 50, w: 50, h: 50 }, "back");
  }
  return items;
}

function find(items: Item[], target?: string) {
  if (!target) return undefined;
  const t = norm(target);
  return items.find((i) => i.id === t) || items.find((i) => i.id.startsWith(t) || t.startsWith(i.id)) || items.find((i) => i.id.includes(t));
}

/* ------------------------------------------------------------- drawing one view */
const Toggle: React.FC<{ on: number; th: Record<string, string> }> = ({ on, th }) => (
  <div style={{ width: 62, height: 36, borderRadius: 18, background: on > 0.5 ? th.accent : th.line, position: "relative", flex: "none" }}>
    <div style={{ position: "absolute", top: 4, left: 4 + on * 26, width: 28, height: 28, borderRadius: 14, background: "#fff", boxShadow: "0 2px 4px rgba(0,0,0,.3)" }} />
  </div>
);

const ViewLayer: React.FC<{ v: View; dev: "web" | "phone"; th: Record<string, string>; app: string; hot?: string; hotK: number;
  typed?: { id: string; text: string }; flips: Record<string, number> }> = ({ v, dev, th, app, hot, hotK, typed, flips }) => {
  const g = SCREEN_GEOM[dev];
  if (v.kind && KINDS[v.kind]) {
    const K = KINDS[v.kind];
    return <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>{K.draw(v, dev, g, K.layout(v, dev, g), { hot, hotK, typed, flips })}</div>;
  }
  const items = layout(v, dev);
  const web = dev === "web";
  const sideW = web ? 232 : 300;
  const drawer = !!v.sidebar && (web || !v.panel);
  const fs = web ? 22 : 24;
  const ring = (id: string): React.CSSProperties => (hot === id ? { boxShadow: `0 0 0 ${3 * hotK}px ${COL.gold}, 0 0 ${30 * hotK}px ${COL.gold}88`, background: th.hover } : {});
  const txt = (it: Item) => (typed && typed.id === it.id ? typed.text : undefined);
  const mainX = web ? sideW : 0;
  return (
    <div style={{ position: "absolute", inset: 0, background: th.bg, fontFamily: SANS, color: th.text, overflow: "hidden" }}>
      {/* chrome */}
      {web && <div style={{ position: "absolute", left: 0, top: 0, width: sideW, bottom: 0, background: th.side, borderRight: `1px solid ${th.line}` }} />}
      {web && <div style={{ position: "absolute", left: 16, top: 22, display: "flex", alignItems: "center", gap: 12, font: `700 ${fs + 2}px ${SANS}` }}>
        <div style={{ width: 34, height: 34, borderRadius: 17, background: th.text, color: th.bg, display: "flex", alignItems: "center", justifyContent: "center", font: `800 18px ${SANS}` }}>{app.slice(0, 1)}</div>{app}</div>}
      {!web && <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 40, display: "flex", justifyContent: "space-between", padding: "10px 28px", font: `600 18px ${SANS}`, color: th.text }}><span>9:41</span><span>●●● ▮</span></div>}
      {!web && !v.panel && <div style={{ position: "absolute", left: 0, right: 0, top: 50, height: 52, display: "flex", alignItems: "center", justifyContent: "center", font: `700 ${fs + 2}px ${SANS}` }}>{v.title || app}</div>}
      {/* chat */}
      {(v.chat || []).length > 0 && (
        <div style={{ position: "absolute", left: mainX + 30, right: 30, top: web ? 40 : 120, display: "flex", flexDirection: "column", gap: 18 }}>
          {(v.chat || []).slice(-3).map((m, i) => (
            <div key={i} style={{ alignSelf: m.from === "user" ? "flex-end" : "flex-start", maxWidth: m.from === "user" ? "78%" : "100%",
              background: m.from === "user" ? th.bubble : "transparent", borderRadius: 22, padding: m.from === "user" ? "12px 20px" : "0",
              font: `500 ${fs}px/1.35 ${SANS}` }}>{m.text}</div>
          ))}
        </div>
      )}
      {!v.chat?.length && v.input !== undefined && !v.panel && (
        <div style={{ position: "absolute", left: mainX, right: 0, top: web ? 220 : 330, textAlign: "center", font: `600 ${web ? 32 : 30}px ${SANS}` }}>{v.title || "What can I help with?"}</div>
      )}
      {items.filter((i) => i.kind === "input").map((it) => (
        <div key="in" style={{ position: "absolute", left: it.box.x, top: it.box.y, width: it.box.w, height: it.box.h, borderRadius: 30, border: `1px solid ${th.line}`,
          background: th.panel, display: "flex", alignItems: "center", padding: `0 22px 0 ${(it.extra?.pad || 0) + 14}px`, font: `500 ${fs}px ${SANS}`, color: txt(it) || (v.input && v.input !== "") ? th.text : th.mute, ...ring(it.id) }}>
          <span style={{ whiteSpace: "nowrap", overflow: "hidden" }}>{txt(it) ?? (v.input || "Ask anything")}</span>
        </div>
      ))}
      {items.filter((i) => i.kind === "ibtn" || i.kind === "tbtn").map((it) => (
        <div key={it.kind + it.id} style={{ position: "absolute", left: it.box.x, top: it.box.y, width: it.box.w, height: it.box.h, borderRadius: 26,
          border: `1px solid ${th.line}`, background: it.kind === "tbtn" ? th.bg : th.hover, display: "flex", alignItems: "center", justifyContent: "center",
          font: `${it.label.length <= 2 ? 500 : 600} ${it.label.length <= 2 ? 30 : fs - 2}px ${SANS}`, color: th.text, ...ring(it.id) }}>{it.label}</div>
      ))}
      {/* sidebar / drawer */}
      {!web && drawer && <div style={{ position: "absolute", inset: 0, background: th.shade }} />}
      {!web && drawer && <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: sideW, background: th.side }} />}
      {items.filter((i) => i.kind === "side").map((it) => (
        <div key={it.id} style={{ position: "absolute", left: it.box.x, top: it.box.y, width: it.box.w, height: it.box.h, borderRadius: 10, display: "flex", alignItems: "center",
          padding: "0 12px", font: `500 ${fs}px ${SANS}`, whiteSpace: "nowrap", overflow: "hidden", ...ring(it.id) }}>{it.label}</div>
      ))}
      {items.filter((i) => i.kind === "profile").map((it) => (
        <div key="pr" style={{ position: "absolute", left: it.box.x, top: it.box.y, width: it.box.w, height: it.box.h, borderRadius: web || drawer ? 12 : 26, display: "flex", alignItems: "center", gap: 12,
          padding: web || drawer ? "0 8px" : 0, font: `600 ${fs}px ${SANS}`, ...ring(it.id) }}>
          <div style={{ width: web ? 36 : 44, height: web ? 36 : 44, borderRadius: 22, background: "linear-gradient(135deg,#7C5CFF,#E2483D)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", font: `800 18px ${SANS}`, flex: "none", margin: web || drawer ? 0 : 4 }}>{it.label.slice(0, 1).toUpperCase()}</div>
          {(web || drawer) && it.label}
        </div>
      ))}
      {/* popup menu / bottom sheet */}
      {v.menu && (() => {
        const ms = items.filter((i) => i.kind === "menu");
        if (!ms.length) return null;
        const b0 = ms[0].box, b1 = ms[ms.length - 1].box;
        return (
          <>
            {!web && <div style={{ position: "absolute", inset: 0, background: th.shade }} />}
            <div style={{ position: "absolute", left: b0.x - 8, top: b0.y - (web ? 8 : 24), width: b0.w + 16, height: b1.y + b1.h - b0.y + (web ? 16 : 60), borderRadius: web ? 16 : 26,
              background: th.panel, border: `1px solid ${th.line}`, boxShadow: "0 18px 50px rgba(0,0,0,.45)" }} />
            {ms.map((it) => (
              <div key={it.id} style={{ position: "absolute", left: it.box.x, top: it.box.y, width: it.box.w, height: it.box.h, borderRadius: 10, display: "flex", alignItems: "center",
                padding: "0 14px", font: `500 ${fs}px ${SANS}`, ...ring(it.id) }}>{it.label}</div>
            ))}
          </>
        );
      })()}
      {/* settings panel (modal on web, full page on phone) */}
      {v.panel && (() => {
        const p = v.panel; const pw = web ? 760 : g.cw, px = web ? (g.cw - pw) / 2 : 0;
        const rows = items.filter((i) => i.kind === "row"), nav = items.filter((i) => i.kind === "nav");
        const last = rows[rows.length - 1]?.box;
        const ph = web ? Math.max(260, (last ? last.y + last.h : 200) - 60 + 24, nav.length ? 76 + nav.length * 46 + 20 : 0) : g.ch;
        return (
          <>
            {web && <div style={{ position: "absolute", inset: 0, background: th.shade }} />}
            <div style={{ position: "absolute", left: px, top: web ? 60 : 0, width: pw, height: ph, background: th.panel, borderRadius: web ? 18 : 0, border: web ? `1px solid ${th.line}` : "none",
              boxShadow: web ? "0 30px 80px rgba(0,0,0,.5)" : "none" }} />
            <div style={{ position: "absolute", left: px + (web ? 26 : 70), top: web ? 80 : 60, font: `700 ${web ? 28 : 28}px ${SANS}` }}>{p.title}</div>
            {!web && p.back && <div style={{ position: "absolute", left: 18, top: 52, font: `400 44px ${SANS}`, color: th.text }}>‹</div>}
            {web && <div style={{ position: "absolute", left: px, top: 60 + 64, width: pw, height: 1, background: th.line }} />}
            {nav.map((it) => (
              <div key={it.id} style={{ position: "absolute", left: it.box.x, top: it.box.y, width: it.box.w, height: it.box.h, borderRadius: 10, display: "flex", alignItems: "center", padding: "0 12px",
                font: `${norm(p.active) === it.id ? 700 : 500} 20px ${SANS}`, background: norm(p.active) === it.id ? th.hover : "transparent", ...ring(it.id) }}>{it.label}</div>
            ))}
            {rows.map((it) => {
              const r = it.row!;
              const field = r.kind === "field";
              const val = txt(it) ?? r.value ?? "";
              const flip = flips[it.id];
              const on = flip !== undefined ? (r.on ? 1 - flip : flip) : r.on ? 1 : 0;
              return (
                <div key={it.id} style={{ position: "absolute", left: it.box.x, top: it.box.y, width: it.box.w, height: it.box.h, borderRadius: 12, borderBottom: field ? "none" : `1px solid ${th.line}`,
                  padding: field ? "10px 10px" : "0 10px", display: "flex", flexDirection: field ? "column" : "row", alignItems: field ? "stretch" : "center", justifyContent: "space-between", gap: 10, ...ring(it.id) }}>
                  <div style={{ font: `${field ? 600 : 500} ${fs}px ${SANS}`, whiteSpace: "nowrap", overflow: "hidden" }}>{r.label}</div>
                  {field && (
                    <div style={{ flex: 1, borderRadius: 12, border: `1px solid ${th.line}`, background: th.field, padding: "10px 14px", font: `500 ${fs - 2}px/30px ${SANS}`, color: val ? th.text : th.mute, overflow: "hidden" }}>
                      {wrap(val || "…", web ? 44 : 30).slice(0, 4).map((ln, k) => <div key={k}>{ln}</div>)}
                    </div>
                  )}
                  {r.kind === "toggle" && <Toggle on={on} th={th} />}
                  {r.kind === "arrow" && <div style={{ font: `400 34px ${SANS}`, color: th.mute }}>›</div>}
                  {r.kind === "value" && <div style={{ font: `500 ${fs}px ${SANS}`, color: th.mute, whiteSpace: "nowrap" }}>{r.value} ⌄</div>}
                  {r.kind === "button" && <div style={{ padding: "8px 20px", borderRadius: 20, border: `1px solid ${th.line}`, font: `600 ${fs - 2}px ${SANS}` }}>{r.value || "Open"}</div>}
                </div>
              );
            })}
          </>
        );
      })()}
    </div>
  );
};

/* ------------------------------------------------------------- the element */
const Cursor: React.FC<{ x: number; y: number; dev: string; press: number }> = ({ x, y, dev, press }) =>
  dev === "web" ? (
    <svg width={44} height={54} viewBox="0 0 22 27" style={{ position: "absolute", left: x - 4, top: y - 2, scale: `${1 - press * 0.15}`, filter: "drop-shadow(0 4px 6px rgba(0,0,0,.5))" }}>
      <path d="M2 1 L2 21 L7.5 16 L11 24 L14.5 22.5 L11 15 L18 15 Z" fill="#fff" stroke="#111" strokeWidth={1.6} strokeLinejoin="round" />
    </svg>
  ) : (
    <div style={{ position: "absolute", left: x - 34, top: y - 34, width: 68, height: 68, borderRadius: 34, background: "rgba(255,255,255,.35)", border: "3px solid rgba(255,255,255,.9)",
      scale: `${1 - press * 0.25}`, boxShadow: "0 6px 20px rgba(0,0,0,.4)" }} />
  );

/** persistent chapter header above a walkthrough ("STEP 2 · INSTALL THE TOOLS") */
const StepHead: React.FC<{ text: string }> = ({ text }) => {
  const [a, b] = text.split(/\s*[·|:]\s*/, 2);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, height: 54 }}>
      {b !== undefined && <div style={{ padding: "8px 18px", borderRadius: 999, background: COL.gold, color: COL.ink, font: `800 24px ${MONO}`, letterSpacing: 1.5 }}>{a.toUpperCase()}</div>}
      <div style={{ font: `800 38px ${SANS}`, color: COL.txt, letterSpacing: -1, whiteSpace: "nowrap" }}>{b ?? a}</div>
    </div>
  );
};

export const ScreenWalk: React.FC<{ e: any }> = ({ e }) => {
  const f = useCurrentFrame();
  const t = f / FPS;
  const dev: "web" | "phone" = e.device === "phone" ? "phone" : "web";
  const desktop = e.device === "desktop";
  const g = SCREEN_GEOM[dev];
  const th = THEMES[THEMES[e.brand] ? e.brand : e.theme === "light" ? "light" : "dark"];
  const steps: Step[] = (e.steps || []).filter((s: Step) => s && s.view);
  if (!steps.length) return null;
  let i = 0;
  for (let k = 0; k < steps.length; k++) if (t >= steps[k].at - 0.05) i = k;
  const st = steps[i];
  const actAt = (s: Step) => s.action?.at ?? s.at + 0.8;
  // cursor path: rest -> target of each action
  const center = (s: Step) => {
    const it = find(layout(s.view, dev), s.action?.target);
    if (!it) return null;
    if (it.kind === "citem") return { x: it.box.x + it.box.w - 40, y: it.box.y + it.box.h / 2, box: it.box, id: it.id };
    if (it.kind === "mrow") return { x: it.box.x + 30, y: it.box.y + it.box.h / 2, box: it.box, id: it.id };
    if (["search", "pinput", "page", "term"].includes(it.kind)) return { x: it.box.x + Math.min(it.box.w * 0.35, 260), y: it.box.y + Math.min(it.box.h / 2, 60), box: it.box, id: it.id };
    const right = it.kind === "row" && (it.row?.kind === "toggle" || it.row?.kind === "value" || it.row?.kind === "button" || it.row?.kind === "arrow");
    const x = right ? it.box.x + it.box.w - 50 : it.kind === "input" || (it.kind === "row" && it.row?.kind === "field") ? it.box.x + it.box.w * 0.4 : it.box.x + Math.min(it.box.w / 2, 120);
    const y = it.kind === "row" && it.row?.kind === "field" ? it.box.y + it.box.h * 0.65 : it.box.y + it.box.h / 2;
    return { x, y, box: it.box, id: it.id };
  };
  let pos = { x: g.cw * 0.62, y: g.ch * 0.7 };
  for (let k = 0; k <= i; k++) {
    const c = center(steps[k]);
    if (!c) continue;
    const a = actAt(steps[k]);
    const m = interpolate(t, [a - 0.6, a - 0.08], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
    if (k < i) pos = { x: c.x, y: c.y };
    else pos = { x: pos.x + (c.x - pos.x) * m, y: pos.y + (c.y - pos.y) * m };
  }
  const c = center(st);
  const a = actAt(st);
  const press = interpolate(t, [a - 0.05, a, a + 0.12], [0, 1, 0], clamp);
  const hotK = c ? interpolate(t, [a - 0.05, a + 0.1], [0, 1], clamp) : 0;
  const ripple = c && t >= a ? interpolate(t, [a, a + 0.45], [0, 1], clamp) : 0;
  // typing / toggles
  let typed: { id: string; text: string } | undefined;
  const flips: Record<string, number> = {};
  if (st.action && c && (st.action.kind === "type") && st.action.text) {
    const n = Math.floor(interpolate(t, [a + 0.1, a + 0.1 + Math.min(2.4, 0.04 * st.action.text.length)], [0, st.action.text.length], clamp));
    typed = { id: c.id, text: st.action.text.slice(0, n) + (n < st.action.text.length && f % 12 < 7 ? "▍" : "") };
  }
  if (st.action && c && st.action.kind === "toggle") flips[c.id] = interpolate(t, [a + 0.05, a + 0.25], [0, 1], clamp);
  // camera: push in on the target around the click, ease back as the next screen arrives
  const next = steps[i + 1]?.at ?? 1e9;
  const z = c && st.action?.kind !== "point" ? Math.min(interpolate(t, [a - 0.7, a - 0.05], [0, 1], { ...clamp, easing: easeOut }), interpolate(t, [next - 0.35, next], [1, 0], clamp)) : 0;
  const base = (dev === "web" ? 0.5 : 0.42) * z;
  const bw = c ? c.box.w + 120 : g.cw, bh = c ? c.box.h + 120 : g.ch;
  const Z = Math.max(0, Math.min(base, (g.cw / bw - 1) * z, (g.ch / bh - 1) * z, base));
  const ox = c ? c.box.x + c.box.w / 2 : g.cw / 2, oy = c ? c.box.y + c.box.h / 2 : g.ch / 2;
  // keep the scaled screen covering the whole viewport (no dark gaps at the edges)
  const clampT = (want: number, o: number, size: number) => Math.max(-(size - o) * Z, Math.min(o * Z, want));
  const tx = clampT((g.cw / 2 - ox) * Z * 0.9, ox, g.cw), ty = clampT((g.ch / 2 - oy) * Z * 0.9, oy, g.ch);
  const fade = interpolate(t, [st.at - 0.02, st.at + 0.1], [0, 1], clamp);
  const prev = steps[i - 1];
  const showCursor = steps.some((s) => s.action?.target) && t >= steps[0].at;
  const inner = (
    <div style={{ position: "absolute", left: 0, top: g.bar, width: g.cw * g.s, height: g.ch * g.s, overflow: "hidden", borderRadius: dev === "web" ? "0 0 22px 22px" : 46 }}>
     <div style={{ position: "absolute", left: 0, top: 0, width: g.cw, height: g.ch, scale: `${g.s}`, transformOrigin: "0 0" }}>
      <div style={{ position: "absolute", inset: 0, transformOrigin: `${ox}px ${oy}px`, scale: `${1 + Z}`, translate: `${tx}px ${ty}px` }}>
        {prev && fade < 1 && <ViewLayer v={prev.view} dev={dev} th={th} app={e.app || "App"} flips={{}} hotK={0} />}
        <div style={{ position: "absolute", inset: 0, opacity: fade }}>
          <ViewLayer v={st.view} dev={dev} th={th} app={e.app || "App"} hot={c?.id} hotK={hotK} typed={typed} flips={flips} />
        </div>
        {ripple > 0 && ripple < 1 && c && <div style={{ position: "absolute", left: c.x - 60 * ripple, top: c.y - 60 * ripple, width: 120 * ripple, height: 120 * ripple, borderRadius: "50%",
          border: `4px solid ${COL.gold}`, opacity: 1 - ripple }} />}
        {showCursor && <Cursor x={pos.x} y={pos.y} dev={dev} press={press} />}
      </div>
     </div>
    </div>
  );
  if (dev === "web") {
    return (
      <div style={{ width: 940, display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>{e.step && <StepHead text={e.step} />}
        <div style={{ position: "relative", width: g.W, height: g.H, borderRadius: 24, background: "#0F1012", border: `2px solid ${COL.edge}`, boxShadow: "0 40px 90px rgba(0,0,0,.7)", overflow: "hidden" }}>
          <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: g.bar, display: "flex", alignItems: "center", gap: 10, padding: "0 20px", background: "#1A1B1E" }}>
            {["#FF5F57", "#FEBC2E", "#28C840"].map((c2) => <div key={c2} style={{ width: 14, height: 14, borderRadius: 7, background: c2 }} />)}
            {desktop ? <div style={{ flex: 1, textAlign: "center", font: `600 20px ${SANS}`, color: "#C9C9CC", marginRight: 70 }}>{(st.view as any).window || e.app || ""}</div>
              : <div style={{ marginLeft: 18, flex: 1, height: 32, borderRadius: 16, background: "#0F1012", display: "flex", alignItems: "center", padding: "0 18px", font: `500 19px ${MONO}`, color: COL.mute }}>🔒 {(st.view as any).url || e.url || ""}</div>}
          </div>
          {inner}
        </div>
      </div>
    );
  }
  return (
    <div style={{ width: 940, display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>{e.step && <StepHead text={e.step} />}
      <div style={{ position: "relative", width: g.W, height: g.H, borderRadius: 64, background: "#0B0B0C", border: "3px solid #2A2B2F", boxShadow: "0 40px 90px rgba(0,0,0,.7), inset 0 0 0 10px #151518" }}>
        <div style={{ position: "absolute", left: 20, top: 20, width: g.cw, height: g.ch }}>{inner}</div>
        <div style={{ position: "absolute", left: g.W / 2 - 60, top: 30, width: 120, height: 32, borderRadius: 16, background: "#000" }} />
      </div>
    </div>
  );
};

/* ------------------------------------------------------------- footage: a real clip or image from the internet / your own recording */
export const Footage: React.FC<{ e: any }> = ({ e }) => {
  const f = useCurrentFrame();
  const m = e._media;
  if (!m) return null;
  const h = e.tall ? 1000 : 700;
  const zoom = interpolate(f, [fx(e.at), fx(e.at) + 150], [1.0, 1.08], clamp);
  return (
    <Card w={940} h={h} shineAt={e.at + 0.1} accent={COL.gold}>
      <div style={{ position: "absolute", inset: 0, overflow: "hidden", borderRadius: 26 }}>
        {m.kind === "video" ? (
          <Sequence from={Math.round(fx(e.at))} layout="none">
            {m.frames ? (
              <Loop durationInFrames={Math.max(30, m.frames - 2)} layout="none">
                <OffthreadVideo src={staticFile(m.src)} muted style={{ width: "100%", height: "100%", objectFit: m.fit || "cover" }} />
              </Loop>
            ) : (
              <OffthreadVideo src={staticFile(m.src)} muted style={{ width: "100%", height: "100%", objectFit: m.fit || "cover" }} />
            )}
          </Sequence>
        ) : (
          <Img src={staticFile(m.src)} style={{ width: "100%", height: "100%", objectFit: m.fit || "cover", scale: `${zoom}` }} />
        )}
      </div>
      {e.caption && (
        <div style={{ position: "absolute", left: 24, bottom: 24, padding: "10px 20px", borderRadius: 14, background: "rgba(10,10,11,.78)", border: `2px solid ${COL.gold}`, font: `800 32px ${SANS}`, color: COL.txt }}>{e.caption}</div>
      )}
      {m.credit && <Mono s={18} c="rgba(255,255,255,.7)" style={{ position: "absolute", right: 22, top: 18, textShadow: "0 2px 6px #000" }}>{m.credit}</Mono>}
    </Card>
  );
};

/** a vertical clip filling the whole reel behind the scene's other elements (darkened so captions stay readable) */
export const FullFootage: React.FC<{ e: any; start: number; end: number }> = ({ e, start, end }) => {
  const f = useCurrentFrame();
  const m = e._media;
  if (!m || f < fx(e.at) - 1 || f > fx(end) + 10) return null;
  const op = Math.min(interpolate(f, [fx(e.at), fx(e.at) + 8], [0, 1], clamp), interpolate(f, [fx(end) - 2, fx(end) + 8], [1, 0], clamp));
  const zoom = interpolate(f, [fx(e.at), fx(end)], [1.04, 1.12], clamp);
  return (
    <div style={{ position: "absolute", inset: 0, opacity: op, overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, scale: `${zoom}` }}>
        {m.kind === "video" ? (
          <Sequence from={Math.round(fx(e.at))} layout="none">
            <Loop durationInFrames={Math.max(30, (m.frames || 240) - 2)} layout="none">
              <OffthreadVideo src={staticFile(m.src)} muted style={{ width: 1080, height: 1920, objectFit: "cover" }} />
            </Loop>
          </Sequence>
        ) : (
          <Img src={staticFile(m.src)} style={{ width: 1080, height: 1920, objectFit: "cover" }} />
        )}
      </div>
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(10,10,11,.55) 0%, rgba(10,10,11,.15) 30%, rgba(10,10,11,.25) 52%, rgba(10,10,11,.88) 66%, rgba(10,10,11,.95) 100%)" }} />
      {e.caption && (
        <div style={{ position: "absolute", left: 70, top: 1000, padding: "10px 22px", borderRadius: 14, background: "rgba(10,10,11,.78)", border: `2px solid ${COL.gold}`,
          font: `800 34px ${SANS}`, color: COL.txt, opacity: interpolate(f, [fx(e.caption_at ?? e.at + 0.3), fx(e.caption_at ?? e.at + 0.3) + 8], [0, 1], clamp) }}>{e.caption}</div>
      )}
    </div>
  );
};

export const SCREEN_SPECS = {
  screen: { h: (e: any) => (e.device === "phone" ? SCREEN_GEOM.phone.H : SCREEN_GEOM.web.H) + (e.step ? 70 : 0), R: ScreenWalk },
  footage: { h: (e: any) => (e.full ? 0 : e.tall ? 1000 : 700), R: Footage },
};
export const _s = spring;
