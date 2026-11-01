import React from "react";
import { COL, SANS, MONO } from "./lib";

/* ------------------------------------------------------------------------------------------------
   App-specific screens for walkthroughs, so the screen always matches what the voice is talking about:
   search (a search engine results page), mail (an inbox), files (a Finder/Explorer window), page (a website / dashboard),
   doc (a document editor), terminal, checklist (installer / to-do with ticks), home (phone home screen).
   Each kind returns clickable items (for the cursor) and draws itself. Light, clean, generic — no logos.
   ------------------------------------------------------------------------------------------------ */
export type Box = { x: number; y: number; w: number; h: number };
export type KItem = { id: string; label: string; box: Box; kind: string; extra?: any };
export type Ctx = { hot?: string; hotK: number; typed?: { id: string; text: string }; flips: Record<string, number> };
type G = { cw: number; ch: number };

export const knorm = (s?: string) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "") || (s || "").trim();
const wrap = (t: string, n: number) => {
  const out: string[] = []; let cur = "";
  for (const w of (t || "").split(/\s+/)) { if (cur && (cur + " " + w).length > n) { out.push(cur); cur = w; } else cur = cur ? cur + " " + w : w; }
  if (cur) out.push(cur);
  return out;
};
const L = { bg: "#FFFFFF", soft: "#F6F8FC", panel: "#FFFFFF", text: "#1F1F1F", mute: "#5F6368", line: "#E3E3E3", link: "#1A0DAB", blue: "#0B57D0", hover: "#EEF2F8", green: "#1E8E3E" };

const ring = (c: Ctx, id: string): React.CSSProperties =>
  c.hot === id ? { boxShadow: `0 0 0 ${3 * c.hotK}px ${COL.gold}, 0 0 ${28 * c.hotK}px ${COL.gold}88`, borderRadius: 10 } : {};
const typedOr = (c: Ctx, id: string, v?: string) => (c.typed && c.typed.id === id ? c.typed.text : v);
const flipOn = (c: Ctx, id: string, on?: boolean) => { const f = c.flips[id]; return f !== undefined ? (on ? 1 - f : f) : on ? 1 : 0; };

const Check: React.FC<{ on: number; round?: boolean }> = ({ on, round }) => (
  <div style={{ width: 30, height: 30, borderRadius: round ? 15 : 7, border: `2px solid ${on > 0.5 ? L.blue : "#9AA0A6"}`, background: on > 0.5 ? L.blue : "transparent",
    display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", font: `800 20px ${SANS}`, flex: "none" }}>{on > 0.5 ? "✓" : ""}</div>
);
const Folder: React.FC<{ s?: number }> = ({ s = 34 }) => (
  <svg width={s} height={s * 0.8} viewBox="0 0 40 32"><path d="M2 6a3 3 0 0 1 3-3h10l4 4h16a3 3 0 0 1 3 3v17a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3z" fill="#5AA9F2" /><path d="M2 11h36v16a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3z" fill="#75BDF7" /></svg>
);
const FileIcon: React.FC<{ s?: number }> = ({ s = 34 }) => (
  <svg width={s * 0.8} height={s} viewBox="0 0 30 38"><path d="M3 2h17l8 8v25a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#fff" stroke="#B0B6BE" strokeWidth={2} /><path d="M20 2v8h8" fill="none" stroke="#B0B6BE" strokeWidth={2} /></svg>
);
const Tile: React.FC<{ label: string; s: number; hue?: number }> = ({ label, s, hue }) => {
  const h = hue ?? [...label].reduce((a, ch) => a + ch.charCodeAt(0), 0) % 360;
  return <div style={{ width: s, height: s, borderRadius: s * 0.24, background: `linear-gradient(145deg, hsl(${h},70%,60%), hsl(${(h + 40) % 360},70%,45%))`,
    display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", font: `800 ${s * 0.42}px ${SANS}`, flex: "none" }}>{label.slice(0, 1).toUpperCase()}</div>;
};

type Kind = { layout: (v: any, dev: string, g: G) => KItem[]; draw: (v: any, dev: string, g: G, items: KItem[], c: Ctx) => React.ReactNode };
const it = (label: string, box: Box, kind: string, extra?: any): KItem => ({ id: knorm(label), label, box, kind, extra });
const byKind = (items: KItem[], k: string) => items.filter((i) => i.kind === k);
const Abs: React.FC<{ b: Box; style?: React.CSSProperties; children?: React.ReactNode }> = ({ b, style, children }) => (
  <div style={{ position: "absolute", left: b.x, top: b.y, width: b.w, height: b.h, ...style }}>{children}</div>
);

/* --------------------------------------------------------------- search results page */
const search: Kind = {
  layout: (v, dev, g) => {
    const web = dev !== "phone", out: KItem[] = [];
    const x0 = web ? 40 : 16, w = web ? 660 : g.cw - 32;
    out.push(it("search", { x: x0, y: web ? 24 : 56, w, h: 56 }, "search"));
    let tx = x0 + 6;
    (v.tabs || ["All", "Images", "Videos", "News"]).forEach((t: string) => { const tw = 26 + t.length * (web ? 12 : 11); out.push(it(t, { x: tx, y: web ? 96 : 128, w: tw, h: 38 }, "tab")); tx += tw + 8; });
    let y = web ? 156 : 186;
    if (v.ai_overview) {
      const lines = wrap(v.ai_overview, web ? 58 : 32).slice(0, 5);
      out.push(it("AI Overview", { x: x0, y, w, h: 64 + lines.length * 30 }, "ai", { lines })); y += 64 + lines.length * 30 + 18;
    }
    (v.results || []).slice(0, 4).forEach((r: any) => {
      const sn = wrap(r.snippet || "", web ? 70 : 36).slice(0, 2);
      const h = 30 + 36 + sn.length * 26 + 18;
      if (y + h > g.ch) return;
      out.push(it(r.title, { x: x0, y, w, h }, "result", { r, sn })); y += h;
    });
    return out;
  },
  draw: (v, dev, g, items, c) => {
    const web = dev !== "phone", fs = web ? 1 : 0.92;
    return (
      <div style={{ position: "absolute", inset: 0, background: L.bg, fontFamily: SANS, color: L.text }}>
        {byKind(items, "search").map((s) => (
          <Abs key="s" b={s.box} style={{ borderRadius: 28, border: `1px solid ${L.line}`, boxShadow: "0 1px 6px rgba(32,33,36,.18)", display: "flex", alignItems: "center", gap: 14, padding: "0 22px", ...ring(c, s.id) }}>
            <span style={{ font: `400 26px ${SANS}`, color: L.mute }}>⌕</span>
            <span style={{ font: `500 ${24 * fs}px ${SANS}`, whiteSpace: "nowrap", overflow: "hidden" }}>{typedOr(c, s.id, v.query) || ""}</span>
          </Abs>
        ))}
        {byKind(items, "tab").map((t, i) => (
          <Abs key={t.id} b={t.box} style={{ display: "flex", alignItems: "center", justifyContent: "center", font: `500 ${20 * fs}px ${SANS}`, color: knorm(v.active_tab || "All") === t.id ? L.blue : L.mute,
            borderBottom: knorm(v.active_tab || "All") === t.id ? `3px solid ${L.blue}` : "none", ...ring(c, t.id) }}>{t.label}</Abs>
        ))}
        <div style={{ position: "absolute", left: 0, right: 0, top: web ? 140 : 172, height: 1, background: L.line }} />
        {byKind(items, "ai").map((a) => (
          <Abs key="ai" b={a.box} style={{ borderRadius: 18, background: "#F0F4F9", padding: "16px 22px", ...ring(c, a.id) }}>
            <div style={{ font: `700 ${21 * fs}px ${SANS}`, marginBottom: 8 }}>✦ AI Overview</div>
            {a.extra.lines.map((ln: string, k: number) => <div key={k} style={{ font: `400 ${20 * fs}px/30px ${SANS}` }}>{ln}</div>)}
          </Abs>
        ))}
        {byKind(items, "result").map((r) => (
          <Abs key={r.id} b={r.box} style={{ padding: "2px 6px", ...ring(c, r.id) }}>
            <div style={{ font: `400 ${17 * fs}px ${SANS}`, color: L.mute, height: 28, whiteSpace: "nowrap", overflow: "hidden" }}>{r.extra.r.url || ""}</div>
            <div style={{ font: `500 ${25 * fs}px ${SANS}`, color: L.link, height: 36, whiteSpace: "nowrap", overflow: "hidden" }}>{r.label}</div>
            {r.extra.sn.map((ln: string, k: number) => <div key={k} style={{ font: `400 ${18 * fs}px/26px ${SANS}`, color: "#4D5156" }}>{ln}</div>)}
          </Abs>
        ))}
      </div>
    );
  },
};

/* --------------------------------------------------------------- email inbox */
const mail: Kind = {
  layout: (v, dev, g) => {
    const web = dev !== "phone", out: KItem[] = [];
    const nx = web ? 210 : 0;
    if (web) {
      out.push(it(v.compose || "Compose", { x: 16, y: 18, w: 160, h: 58 }, "compose"));
      (v.folders || ["Inbox", "Starred", "Sent", "Drafts", "Trash"]).forEach((f: string, i: number) => out.push(it(f, { x: 8, y: 96 + i * 46, w: 190, h: 40 }, "folder")));
    }
    out.push(it("search", { x: nx + 14, y: web ? 16 : 50, w: g.cw - nx - 28, h: 54 }, "search"));
    let y = web ? 84 : 118;
    out.push(it(v.select_label || "Select all", { x: nx + 18, y, w: 44, h: 40 }, "selall"));
    let bx = nx + 76;
    (v.toolbar || []).forEach((t: string) => { const w = 30 + t.length * 11; out.push(it(t, { x: bx, y, w, h: 40 }, "tool")); bx += w + 8; });
    y += 50;
    if (v.banner) {
      const bl = wrap(v.banner.text || "", web ? 64 : 32).slice(0, 2);
      out.push(it(v.banner.link || "banner", { x: nx + 10, y, w: g.cw - nx - 20, h: 30 + bl.length * 26 }, "banner", { lines: bl })); y += 40 + bl.length * 26;
    }
    (v.rows || []).forEach((r: any) => {
      const h = web ? 52 : 76;
      if (y + h > g.ch) return;
      out.push(it(r.subject || r.from, { x: nx + 6, y, w: g.cw - nx - 12, h }, "mrow", { r })); y += h;
    });
    return out;
  },
  draw: (v, dev, g, items, c) => {
    const web = dev !== "phone";
    return (
      <div style={{ position: "absolute", inset: 0, background: L.soft, fontFamily: SANS, color: L.text }}>
        {byKind(items, "compose").map((s) => <Abs key="c" b={s.box} style={{ borderRadius: 18, background: "#C2E7FF", display: "flex", alignItems: "center", justifyContent: "center", font: `600 21px ${SANS}`, ...ring(c, s.id) }}>✎ {s.label}</Abs>)}
        {byKind(items, "folder").map((s) => <Abs key={s.id} b={s.box} style={{ borderRadius: 20, padding: "0 20px", display: "flex", alignItems: "center", font: `${knorm(v.folder || "Inbox") === s.id ? 700 : 500} 20px ${SANS}`, background: knorm(v.folder || "Inbox") === s.id ? "#D3E3FD" : "transparent", ...ring(c, s.id) }}>{s.label}</Abs>)}
        {byKind(items, "search").map((s) => (
          <Abs key="s" b={s.box} style={{ borderRadius: 28, background: "#E9EEF6", display: "flex", alignItems: "center", gap: 14, padding: "0 22px", ...ring(c, s.id) }}>
            <span style={{ font: `400 26px ${SANS}`, color: L.mute }}>⌕</span>
            <span style={{ font: `500 ${web ? 22 : 21}px ${SANS}`, whiteSpace: "nowrap", overflow: "hidden", color: typedOr(c, s.id, v.search) ? L.text : L.mute }}>{typedOr(c, s.id, v.search) || "Search mail"}</span>
          </Abs>
        ))}
        <div style={{ position: "absolute", left: web ? 210 : 0, right: 0, top: web ? 76 : 110, bottom: 0, background: L.panel, borderRadius: web ? "18px 0 0 0" : 0 }} />
        {byKind(items, "selall").map((s) => <Abs key="sa" b={s.box} style={{ display: "flex", alignItems: "center", justifyContent: "center", ...ring(c, s.id) }}><Check on={flipOn(c, s.id, v.all_selected)} /></Abs>)}
        {byKind(items, "tool").map((s) => <Abs key={s.id} b={s.box} style={{ borderRadius: 18, border: `1px solid ${L.line}`, display: "flex", alignItems: "center", justifyContent: "center", font: `500 18px ${SANS}`, background: "#fff", ...ring(c, s.id) }}>{s.label}</Abs>)}
        {byKind(items, "banner").map((s) => (
          <Abs key="b" b={s.box} style={{ background: "#F2F6FC", borderRadius: 10, padding: "6px 14px", font: `400 18px/26px ${SANS}`, textAlign: "center", ...ring(c, s.id) }}>
            {s.extra.lines.map((ln: string, k: number) => <div key={k}>{ln}</div>)}
            {v.banner.link && <div style={{ color: L.blue, fontWeight: 600 }}>{v.banner.link}</div>}
          </Abs>
        ))}
        {byKind(items, "mrow").map((s) => {
          const r = s.extra.r, on = flipOn(c, s.id, r.checked ?? v.all_selected);
          return (
            <Abs key={s.id} b={s.box} style={{ borderBottom: `1px solid ${L.line}`, background: on > 0.5 ? "#C2DBFF55" : "transparent", display: "flex", alignItems: web ? "center" : "flex-start", gap: 16, padding: web ? "0 12px" : "10px 12px", ...ring(c, s.id) }}>
              <Check on={on} />
              {web ? (
                <>
                  <div style={{ width: 190, font: `${r.unread ? 700 : 500} 19px ${SANS}`, whiteSpace: "nowrap", overflow: "hidden", flex: "none" }}>{r.from}</div>
                  <div style={{ flex: 1, font: `${r.unread ? 700 : 400} 19px ${SANS}`, whiteSpace: "nowrap", overflow: "hidden" }}>{r.subject}</div>
                  {r.attachment && <div style={{ font: `500 15px ${SANS}`, border: `1px solid ${L.line}`, borderRadius: 12, padding: "2px 10px", color: L.mute }}>📎 {r.attachment}</div>}
                  <div style={{ width: 80, textAlign: "right", font: `500 17px ${SANS}`, color: L.mute }}>{r.meta || ""}</div>
                </>
              ) : (
                <div style={{ flex: 1, overflow: "hidden" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", font: `700 19px ${SANS}` }}><span>{r.from}</span><span style={{ color: L.mute, fontWeight: 500, fontSize: 15 }}>{r.meta || ""}</span></div>
                  <div style={{ font: `400 18px ${SANS}`, whiteSpace: "nowrap", overflow: "hidden" }}>{r.subject}</div>
                </div>
              )}
            </Abs>
          );
        })}
      </div>
    );
  },
};

/* --------------------------------------------------------------- Finder / file explorer */
const files: Kind = {
  layout: (v, dev, g) => {
    const web = dev !== "phone", out: KItem[] = [];
    const sx = web ? 200 : 0;
    if (web) (v.sidebar || ["AirDrop", "Recents", "Applications", "Desktop", "Documents", "Downloads"]).forEach((s: string, i: number) => out.push(it(s, { x: 10, y: 70 + i * 42, w: 180, h: 36 }, "fside")));
    (v.toolbar || []).forEach((t: string, i: number) => out.push(it(t, { x: g.cw - 20 - (i + 1) * 120, y: 10, w: 112, h: 40 }, "tool")));
    let y = web ? 104 : 120;
    const grid = v.view === "grid";
    (v.items || []).forEach((f: any, i: number) => {
      if (grid) { const cols = web ? 5 : 3, cw = (g.cw - sx - 30) / cols; out.push(it(f.name, { x: sx + 15 + (i % cols) * cw, y: (web ? 76 : 120) + Math.floor(i / cols) * 150, w: cw - 10, h: 140 }, "fitem", { f, grid })); }
      else { if (y + 56 > g.ch) return; out.push(it(f.name, { x: sx + 10, y, w: g.cw - sx - 20, h: 52 }, "fitem", { f })); y += 54; }
    });
    return out;
  },
  draw: (v, dev, g, items, c) => {
    const web = dev !== "phone";
    const grid = v.view === "grid";
    return (
      <div style={{ position: "absolute", inset: 0, background: "#FFFFFF", fontFamily: SANS, color: "#1D1D1F" }}>
        {web && <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 200, background: "#F2F2F4", borderRight: "1px solid #E2E2E5" }} />}
        {web && <div style={{ position: "absolute", left: 22, top: 40, font: `600 15px ${SANS}`, color: "#8E8E93" }}>Favorites</div>}
        {byKind(items, "fside").map((s) => <Abs key={s.id} b={s.box} style={{ borderRadius: 8, display: "flex", alignItems: "center", gap: 10, padding: "0 12px", font: `500 18px ${SANS}`, background: knorm(v.selected_side) === s.id ? "#DCDCE0" : "transparent", ...ring(c, s.id) }}><span style={{ color: "#3B82F6" }}>▣</span>{s.label}</Abs>)}
        <div style={{ position: "absolute", left: web ? 220 : 20, top: 16, font: `700 22px ${SANS}` }}>‹ › &nbsp;{v.path || "Documents"}</div>
        {byKind(items, "tool").map((s) => <Abs key={s.id} b={s.box} style={{ borderRadius: 10, border: "1px solid #DDD", display: "flex", alignItems: "center", justifyContent: "center", font: `600 17px ${SANS}`, ...ring(c, s.id) }}>{s.label}</Abs>)}
        {!grid && <div style={{ position: "absolute", left: web ? 210 : 10, right: 10, top: 66, height: 32, display: "flex", font: `600 15px ${SANS}`, color: "#8E8E93", borderBottom: "1px solid #EEE", padding: "0 14px" }}>
          <span style={{ flex: 1 }}>Name</span><span style={{ width: web ? 200 : 120 }}>Date Modified</span>{web && <span style={{ width: 90 }}>Kind</span>}</div>}
        {!(v.items || []).length && <div style={{ position: "absolute", left: web ? 200 : 0, right: 0, top: g.ch / 2 - 20, textAlign: "center", font: `500 20px ${SANS}`, color: "#A1A1A6" }}>This folder is empty</div>}
        {byKind(items, "fitem").map((s, i) => {
          const f = s.extra.f, folder = (f.type || "folder") === "folder";
          return grid ? (
            <Abs key={s.id} b={s.box} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, paddingTop: 10, ...ring(c, s.id) }}>
              {f.thumb ? <Tile label={f.name} s={76} /> : folder ? <Folder s={84} /> : <FileIcon s={70} />}
              <div style={{ font: `500 17px ${SANS}`, textAlign: "center", width: "100%", overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" }}>{f.name}</div>
            </Abs>
          ) : (
            <Abs key={s.id} b={s.box} style={{ display: "flex", alignItems: "center", gap: 14, padding: "0 14px", borderRadius: 8, background: knorm(v.selected) === s.id ? "#2F6FED" : i % 2 ? "#F7F7F9" : "transparent", color: knorm(v.selected) === s.id ? "#fff" : "#1D1D1F", ...ring(c, s.id) }}>
              {folder ? <Folder s={30} /> : <FileIcon s={26} />}
              <span style={{ flex: 1, font: `500 20px ${SANS}`, whiteSpace: "nowrap", overflow: "hidden" }}>{f.name}</span>
              <span style={{ width: web ? 200 : 120, font: `400 16px ${SANS}`, opacity: 0.7 }}>{f.date || "Today at 10:42"}</span>
              {web && <span style={{ width: 90, font: `400 16px ${SANS}`, opacity: 0.7 }}>{folder ? "Folder" : f.kind || "File"}</span>}
            </Abs>
          );
        })}
      </div>
    );
  },
};

/* --------------------------------------------------------------- website / web app / dashboard */
const page: Kind = {
  layout: (v, dev, g) => {
    const web = dev !== "phone", out: KItem[] = [];
    let nx = g.cw - 24;
    (web ? v.nav || [] : []).slice().reverse().forEach((n: string) => { const w = 24 + n.length * 11; nx -= w; out.push(it(n, { x: nx, y: 14, w, h: 40 }, "nav")); nx -= 6; });
    let y = web ? 96 : 110;
    const hl = wrap(v.heading || "", web ? 30 : 18).slice(0, 3); y += hl.length * (web ? 54 : 44) + 10;
    const sl = wrap(v.sub || "", web ? 58 : 32).slice(0, 3); y += sl.length * 30 + 20;
    let bx = web ? 60 : 20;
    (v.buttons || []).forEach((b: string, i: number) => { const w = 44 + b.length * 13; out.push(it(b, { x: bx, y, w, h: 56 }, "btn", { primary: i === 0 })); bx += w + 14; });
    if ((v.buttons || []).length) y += 80;
    if (v.input !== undefined) { out.push(it("input", { x: web ? 60 : 20, y, w: g.cw - (web ? 120 : 40), h: 64 }, "pinput")); y += 88; }
    const cols = web ? 2 : 1, cw = (g.cw - (web ? 120 : 40) - (cols - 1) * 20) / cols;
    (v.cards || []).forEach((cd: any, i: number) => {
      const tl = wrap(cd.text || "", web ? 34 : 34).slice(0, 2), h = 70 + tl.length * 26 + (cd.buttons ? 56 : 0);
      const row = Math.floor(i / cols), cy = y + row * (h + 18);
      if (cy + h > g.ch) return;
      out.push(it(cd.title, { x: (web ? 60 : 20) + (i % cols) * (cw + 20), y: cy, w: cw, h }, "card", { cd, tl }));
      (cd.buttons || []).forEach((b: string, k: number) => out.push(it(b, { x: (web ? 60 : 20) + (i % cols) * (cw + 20) + 20 + k * 130, y: cy + h - 50, w: 118, h: 40 }, "cbtn")));
    });
    return out.map((o) => ({ ...o, extra: { ...(o.extra || {}), hl, sl } }));
  },
  draw: (v, dev, g, items, c) => {
    const web = dev !== "phone", accent = v.accent || "#5B5BD6";
    const hl = items[0]?.extra?.hl || wrap(v.heading || "", web ? 30 : 18).slice(0, 3), sl = items[0]?.extra?.sl || wrap(v.sub || "", web ? 58 : 32).slice(0, 3);
    return (
      <div style={{ position: "absolute", inset: 0, background: v.dark ? "#0F1115" : "#FFFFFF", color: v.dark ? "#F2F2F2" : "#111", fontFamily: SANS }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 68, borderBottom: `1px solid ${v.dark ? "#22252B" : "#EEE"}` }} />
        <div style={{ position: "absolute", left: web ? 30 : 20, top: 20, font: `800 24px ${SANS}`, display: "flex", alignItems: "center", gap: 10 }}><Tile label={v.site || "S"} s={30} />{v.site || ""}</div>
        {byKind(items, "nav").map((s) => <Abs key={s.id} b={s.box} style={{ display: "flex", alignItems: "center", justifyContent: "center", font: `500 18px ${SANS}`, opacity: 0.8, ...ring(c, s.id) }}>{s.label}</Abs>)}
        <div style={{ position: "absolute", left: web ? 60 : 20, top: web ? 96 : 110, right: web ? 60 : 20 }}>
          {hl.map((ln: string, k: number) => <div key={k} style={{ font: `800 ${web ? 46 : 36}px/${web ? 54 : 44}px ${SANS}`, letterSpacing: -1 }}>{ln}</div>)}
          <div style={{ height: 10 }} />
          {sl.map((ln: string, k: number) => <div key={k} style={{ font: `400 21px/30px ${SANS}`, opacity: 0.7 }}>{ln}</div>)}
        </div>
        {byKind(items, "btn").map((s) => <Abs key={s.id} b={s.box} style={{ borderRadius: 12, background: s.extra.primary ? accent : "transparent", border: s.extra.primary ? "none" : `1px solid ${v.dark ? "#333" : "#CCC"}`, color: s.extra.primary ? "#fff" : "inherit", display: "flex", alignItems: "center", justifyContent: "center", font: `700 20px ${SANS}`, ...ring(c, s.id) }}>{s.label}</Abs>)}
        {byKind(items, "pinput").map((s) => <Abs key="pi" b={s.box} style={{ borderRadius: 16, border: `1px solid ${v.dark ? "#333" : "#D0D0D0"}`, display: "flex", alignItems: "center", padding: "0 20px", font: `500 21px ${SANS}`, opacity: typedOr(c, s.id, v.input) ? 1 : 0.5, ...ring(c, s.id) }}>{typedOr(c, s.id, v.input) || "Type here…"}</Abs>)}
        {byKind(items, "card").map((s) => (
          <Abs key={s.id} b={s.box} style={{ borderRadius: 18, border: `1px solid ${v.dark ? "#262A31" : "#E8E8EC"}`, background: v.dark ? "#161A20" : "#FAFAFC", padding: "18px 20px", ...ring(c, s.id) }}>
            <div style={{ font: `700 22px ${SANS}`, marginBottom: 6 }}>{s.label}</div>
            {s.extra.tl.map((ln: string, k: number) => <div key={k} style={{ font: `400 18px/26px ${SANS}`, opacity: 0.7 }}>{ln}</div>)}
            {s.extra.cd.status && <div style={{ position: "absolute", right: 16, top: 16, font: `700 14px ${SANS}`, padding: "4px 10px", borderRadius: 10, background: "#E6F4EA", color: L.green }}>{s.extra.cd.status}</div>}
          </Abs>
        ))}
        {byKind(items, "cbtn").map((s) => <Abs key={s.id} b={s.box} style={{ borderRadius: 10, border: `1px solid ${v.dark ? "#333" : "#CCC"}`, background: v.dark ? "#1E222A" : "#fff", display: "flex", alignItems: "center", justifyContent: "center", font: `600 17px ${SANS}`, ...ring(c, s.id) }}>{s.label}</Abs>)}
      </div>
    );
  },
};

/* --------------------------------------------------------------- document editor */
const doc: Kind = {
  layout: (v, dev, g) => {
    const web = dev !== "phone", out: KItem[] = [];
    let tx = 20;
    (v.toolbar || []).forEach((t: string) => { const w = 22 + t.length * 11; out.push(it(t, { x: tx, y: 12, w, h: 38 }, "tool")); tx += w + 6; });
    const px = web ? 110 : 14;
    out.push(it("doc", { x: px, y: 74, w: g.cw - 2 * px, h: g.ch - 74 }, "page"));
    return out;
  },
  draw: (v, dev, g, items, c) => {
    const pg = byKind(items, "page")[0];
    const lines: string[] = [...(v.lines || [])];
    const t = typedOr(c, "doc", undefined);
    if (t !== undefined) lines.push(t);
    return (
      <div style={{ position: "absolute", inset: 0, background: "#F0F2F5", fontFamily: SANS, color: "#202124" }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 62, background: "#fff", borderBottom: "1px solid #E0E0E0" }} />
        {byKind(items, "tool").map((s) => <Abs key={s.id} b={s.box} style={{ borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", font: `500 18px ${SANS}`, ...ring(c, s.id) }}>{s.label}</Abs>)}
        {pg && <Abs b={pg.box} style={{ background: "#fff", boxShadow: "0 1px 4px rgba(0,0,0,.15)", padding: "40px 46px", overflow: "hidden", ...ring(c, "doc") }}>
          {v.title && <div style={{ font: `700 32px ${SANS}`, marginBottom: 18 }}>{v.title}</div>}
          {lines.flatMap((ln, k) => wrap(ln, dev !== "phone" ? 52 : 30).map((w, j) => <div key={`${k}-${j}`} style={{ font: `400 21px/32px ${SANS}` }}>{w}</div>))}
        </Abs>}
      </div>
    );
  },
};

/* --------------------------------------------------------------- terminal */
const terminal: Kind = {
  layout: (v, dev, g) => [it("terminal", { x: 20, y: 20, w: g.cw - 40, h: g.ch - 40 }, "term")],
  draw: (v, dev, g, items, c) => {
    const lines: string[] = [...(v.lines || [])];
    const t = typedOr(c, "terminal", undefined);
    if (t !== undefined) lines.push("$ " + t);
    return (
      <div style={{ position: "absolute", inset: 0, background: "#0D1117", padding: 28, font: `500 21px/32px ${MONO}`, color: "#C9D1D9" }}>
        {lines.slice(-18).map((ln, k) => <div key={k} style={{ color: ln.startsWith("$") ? "#7EE787" : ln.startsWith("✓") ? "#56D364" : "#C9D1D9", whiteSpace: "pre-wrap" }}>{ln}</div>)}
      </div>
    );
  },
};

/* --------------------------------------------------------------- checklist / installer */
const checklist: Kind = {
  layout: (v, dev, g) => {
    const out: KItem[] = [];
    (v.items || []).forEach((r: any, i: number) => out.push(it(r.label, { x: 24, y: 96 + i * 92, w: g.cw - 48, h: 82 }, "citem", { r })));
    return out;
  },
  draw: (v, dev, g, items, c) => (
    <div style={{ position: "absolute", inset: 0, background: "#FAFAF7", fontFamily: SANS, color: "#1F1F1F" }}>
      <div style={{ position: "absolute", left: 30, top: 30, font: `800 28px ${SANS}` }}>{v.title || ""}</div>
      {byKind(items, "citem").map((s) => {
        const r = s.extra.r, on = flipOn(c, s.id, r.checked);
        return (
          <Abs key={s.id} b={s.box} style={{ borderRadius: 16, background: "#fff", border: "1px solid #ECEBE6", display: "flex", alignItems: "center", gap: 18, padding: "0 20px", ...ring(c, s.id) }}>
            <Tile label={r.label} s={46} />
            <div style={{ flex: 1, overflow: "hidden" }}>
              <div style={{ font: `700 22px ${SANS}`, whiteSpace: "nowrap" }}>{r.label}</div>
              {r.sub && <div style={{ font: `400 17px ${SANS}`, color: "#6B6B6B", whiteSpace: "nowrap" }}>{r.sub}</div>}
            </div>
            <Check on={on} />
          </Abs>
        );
      })}
    </div>
  ),
};

/* --------------------------------------------------------------- phone home screen / app grid */
const home: Kind = {
  layout: (v, dev, g) => {
    const cols = dev === "phone" ? 4 : 6, cw = (g.cw - 40) / cols;
    return (v.apps || []).map((a: string, i: number) => it(a, { x: 20 + (i % cols) * cw, y: 80 + Math.floor(i / cols) * 128, w: cw, h: 118 }, "app"));
  },
  draw: (v, dev, g, items, c) => (
    <div style={{ position: "absolute", inset: 0, background: "linear-gradient(160deg,#3A2E6E,#14243F 60%,#0E1626)", fontFamily: SANS }}>
      {byKind(items, "app").map((s) => (
        <Abs key={s.id} b={s.box} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, ...ring(c, s.id) }}>
          <Tile label={s.label} s={74} />
          <div style={{ font: `500 16px ${SANS}`, color: "#fff", whiteSpace: "nowrap", overflow: "hidden", maxWidth: "100%" }}>{s.label}</div>
        </Abs>
      ))}
    </div>
  ),
};

export const KINDS: Record<string, Kind> = { search, mail, files, page, doc, terminal, checklist, home };

/** labels the cursor can target in a view of this kind (for validation in Python, mirrored there) */
export const kindTargets = (v: any, dev: string, g: G) => KINDS[v.kind] ? KINDS[v.kind].layout(v, dev, g).map((i) => i.label) : [];
