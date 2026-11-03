import React, { useMemo } from "react";
import { ThreeCanvas } from "@remotion/three";
import * as THREE from "three";
import { useCurrentFrame, spring, interpolate, Easing, random } from "remotion";
import { FPS, clamp, fx } from "./lib";

/* Real-time 3D props that ACT OUT the story (learned from top explainer reels: a padlock snapping open = "hacked").
   kind: padlock | phone | laptop | envelope | shield | key | bulb | clock | coin | coins | jar | box
   act:  open (padlock shackle / laptop lid / envelope flap) | buzz (phone) | glow | spin | fill (coins pile into a glass box,
         jar fills) | burst (pieces fly apart) | tick (clock hands race) — starting at act_at. */

const lathe = (prof: [number, number][], seg = 96) => new THREE.LatheGeometry(prof.map(([x, y]) => new THREE.Vector2(x, y)), seg);
const GOLD = "#F5C242", INK = "#14151A", STEEL = "#B9C0CC";
const ease = (f: number, a: number, len: number) => interpolate(f, [a, a + len], [0, 1], { ...clamp, easing: Easing.bezier(0.2, 0.9, 0.25, 1) });

const metal = (c: string, r = 0.25, m = 0.9) => <meshStandardMaterial color={c} metalness={m} roughness={r} />;

const roundedBox = (w: number, h: number, d: number, r: number) => {
  const s = new THREE.Shape(); const x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + h - r);
  s.quadraticCurveTo(x + w, y + h, x + w - r, y + h); s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
  const g = new THREE.ExtrudeGeometry(s, { depth: d, bevelEnabled: true, bevelThickness: 0.06, bevelSize: 0.06, bevelSegments: 6, curveSegments: 16 });
  g.translate(0, 0, -d / 2); return g;
};

const Padlock: React.FC<{ open: number }> = ({ open }) => {
  const body = useMemo(() => roundedBox(2.0, 1.7, 0.8, 0.28), []);
  const arc = useMemo(() => new THREE.TorusGeometry(0.62, 0.15, 24, 64, Math.PI), []);
  return (
    <group position={[0, -0.4, 0]}>
      <mesh geometry={body}>{metal(GOLD, 0.28)}</mesh>
      <mesh position={[0, 0.1, 0.47]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.17, 0.17, 0.1, 32]} /><meshStandardMaterial color={INK} /></mesh>
      <mesh position={[0, -0.22, 0.47]}><boxGeometry args={[0.12, 0.42, 0.1]} /><meshStandardMaterial color={INK} /></mesh>
      {/* shackle: lifts and swings open */}
      <group position={[0.62, 0.85 + open * 0.55, 0]} rotation={[0, open * 1.1, 0]}>
        <group position={[-0.62, 0, 0]}>
          <mesh geometry={arc} position={[0, 0.5, 0]}>{metal(STEEL, 0.2, 1)}</mesh>
          <mesh position={[-0.62, 0.15, 0]}><cylinderGeometry args={[0.15, 0.15, 0.7, 24]} />{metal(STEEL, 0.2, 1)}</mesh>
          <mesh position={[0.62, 0.15 - open * 0.3, 0]}><cylinderGeometry args={[0.15, 0.15, 0.7, 24]} />{metal(STEEL, 0.2, 1)}</mesh>
        </group>
      </group>
    </group>
  );
};

const Phone: React.FC<{ glow: number }> = ({ glow }) => {
  const body = useMemo(() => roundedBox(1.5, 3.0, 0.16, 0.22), []);
  return (
    <group>
      <mesh geometry={body}><meshStandardMaterial color="#1B1D22" metalness={0.6} roughness={0.3} /></mesh>
      <mesh position={[0, 0, 0.15]}><planeGeometry args={[1.36, 2.82]} /><meshStandardMaterial color="#0E1730" emissive="#3E7BFF" emissiveIntensity={0.35 + glow * 1.4} /></mesh>
      <mesh position={[0, 1.22, 0.16]}><boxGeometry args={[0.42, 0.1, 0.01]} /><meshStandardMaterial color="#000" /></mesh>
      {[0, 1, 2].map((i) => <mesh key={i} position={[0, 0.55 - i * 0.42, 0.16]}><planeGeometry args={[1.05, 0.3]} /><meshStandardMaterial color="#ffffff" transparent opacity={0.12 + glow * 0.25 * (i === 0 ? 1 : 0.6)} /></mesh>)}
    </group>
  );
};

const Laptop: React.FC<{ open: number }> = ({ open }) => (
  <group position={[0, -0.6, 0]} rotation={[0.25, 0, 0]}>
    <mesh><boxGeometry args={[3.2, 0.12, 2.1]} /><meshStandardMaterial color="#C9CDD4" metalness={0.8} roughness={0.35} /></mesh>
    <mesh position={[0, 0.07, 0.15]}><boxGeometry args={[2.8, 0.02, 1.3]} /><meshStandardMaterial color="#2A2D33" /></mesh>
    <group position={[0, 0.06, -1.05]} rotation={[-(1 - open) * Math.PI / 2 + open * -0.25, 0, 0]}>
      <group position={[0, 1.0, 0]}>
        <mesh><boxGeometry args={[3.2, 2.0, 0.08]} /><meshStandardMaterial color="#C9CDD4" metalness={0.8} roughness={0.35} /></mesh>
        <mesh position={[0, 0, 0.045]}><planeGeometry args={[2.95, 1.78]} /><meshStandardMaterial color="#0E1730" emissive="#4C86FF" emissiveIntensity={0.2 + open * 1.0} /></mesh>
      </group>
    </group>
  </group>
);

const Envelope: React.FC<{ open: number }> = ({ open }) => {
  const flap = useMemo(() => { const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute([-1.6, 0, 0, 1.6, 0, 0, 0, -1.1, 0], 3)); g.computeVertexNormals(); return g; }, []);
  return (
    <group>
      <mesh><boxGeometry args={[3.2, 2.1, 0.1]} /><meshStandardMaterial color="#F4F1EA" roughness={0.6} /></mesh>
      <mesh position={[0, 0.35 + open * 0.9, 0.04]}><boxGeometry args={[2.6, 1.6, 0.02]} /><meshStandardMaterial color="#FFFFFF" emissive={GOLD} emissiveIntensity={open * 0.25} /></mesh>
      <group position={[0, 1.05, 0.07]} rotation={[open * Math.PI * 0.95, 0, 0]}><mesh geometry={flap}><meshStandardMaterial color="#E6E0D3" side={THREE.DoubleSide} /></mesh></group>
    </group>
  );
};

const Shield: React.FC<{ glow: number }> = ({ glow }) => {
  const g = useMemo(() => { const s = new THREE.Shape(); s.moveTo(0, 1.6); s.quadraticCurveTo(0.8, 1.35, 1.35, 1.35); s.quadraticCurveTo(1.45, -0.6, 0, -1.6); s.quadraticCurveTo(-1.45, -0.6, -1.35, 1.35); s.quadraticCurveTo(-0.8, 1.35, 0, 1.6);
    const e = new THREE.ExtrudeGeometry(s, { depth: 0.3, bevelEnabled: true, bevelThickness: 0.1, bevelSize: 0.08, bevelSegments: 6 }); e.translate(0, 0, -0.15); return e; }, []);
  return (
    <group>
      <mesh geometry={g}><meshStandardMaterial color="#2C7BE5" metalness={0.5} roughness={0.3} emissive="#2C7BE5" emissiveIntensity={0.15 + glow * 0.8} /></mesh>
      <mesh position={[0.17, 0.02, 0.3]} rotation={[0, 0, 0.9]}><boxGeometry args={[0.95, 0.2, 0.1]} /><meshStandardMaterial color="#fff" emissive="#fff" emissiveIntensity={glow} /></mesh>
      <mesh position={[-0.27, -0.18, 0.3]} rotation={[0, 0, -0.78]}><boxGeometry args={[0.48, 0.2, 0.1]} /><meshStandardMaterial color="#fff" emissive="#fff" emissiveIntensity={glow} /></mesh>
    </group>
  );
};

const Key: React.FC = () => (
  <group rotation={[0, 0, -0.5]}>
    <mesh position={[-1.1, 0, 0]}><torusGeometry args={[0.55, 0.18, 24, 64]} />{metal(GOLD)}</mesh>
    <mesh position={[0.45, 0, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.13, 0.13, 2.2, 24]} />{metal(GOLD)}</mesh>
    {[0.9, 1.25].map((x) => <mesh key={x} position={[x, -0.25, 0]}><boxGeometry args={[0.18, 0.4, 0.2]} />{metal(GOLD)}</mesh>)}
  </group>
);

const Bulb: React.FC<{ glow: number }> = ({ glow }) => (
  <group position={[0, 0.2, 0]}>
    <mesh><sphereGeometry args={[1.05, 48, 48]} /><meshPhysicalMaterial color="#FFF6D8" transparent opacity={0.55} roughness={0.05} emissive={GOLD} emissiveIntensity={glow * 2.2} /></mesh>
    <mesh position={[0, -1.25, 0]}><cylinderGeometry args={[0.45, 0.42, 0.6, 32]} />{metal(STEEL, 0.3)}</mesh>
    <pointLight position={[0, 0, 0]} intensity={glow * 12} color={GOLD} distance={6} />
  </group>
);

const Clock: React.FC<{ t: number }> = ({ t }) => (
  <group rotation={[0.1, 0, 0]}>
    <mesh rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[1.5, 1.5, 0.25, 64]} /><meshStandardMaterial color="#F4F1EA" /></mesh>
    <mesh position={[0, 0, 0.02]}><torusGeometry args={[1.5, 0.12, 16, 64]} />{metal(GOLD)}</mesh>
    {Array.from({ length: 12 }).map((_, i) => <mesh key={i} position={[Math.sin(i / 12 * Math.PI * 2) * 1.25, Math.cos(i / 12 * Math.PI * 2) * 1.25, 0.14]}><boxGeometry args={[0.06, 0.18, 0.02]} /><meshStandardMaterial color={INK} /></mesh>)}
    <group position={[0, 0, 0.16]} rotation={[0, 0, -t * Math.PI * 2 / 12]}><mesh position={[0, 0.4, 0]}><boxGeometry args={[0.1, 0.8, 0.03]} /><meshStandardMaterial color={INK} /></mesh></group>
    <group position={[0, 0, 0.18]} rotation={[0, 0, -t * Math.PI * 2]}><mesh position={[0, 0.55, 0]}><boxGeometry args={[0.06, 1.1, 0.03]} /><meshStandardMaterial color="#E2483D" /></mesh></group>
  </group>
);

const Coin: React.FC<{ r?: number }> = ({ r = 1.4 }) => (
  <group rotation={[Math.PI / 2, 0, 0]}>
    <mesh><cylinderGeometry args={[r, r, r * 0.17, 64]} /><meshStandardMaterial color={GOLD} metalness={0.85} roughness={0.25} emissive="#5a3c00" emissiveIntensity={0.25} /></mesh>
    <mesh position={[0, r * 0.09, 0]}><torusGeometry args={[r * 0.84, r * 0.045, 12, 64]} /><meshStandardMaterial color="#FFE08A" metalness={0.9} roughness={0.2} /></mesh>
  </group>
);

/* a glass box that fills with coins (or bursts) — big numbers made physical */
const Coins: React.FC<{ f: number; t0: number; count: number; burst: number }> = ({ f, t0, count, burst }) => {
  const n = Math.min(60, Math.max(6, count));
  const spots = useMemo(() => Array.from({ length: n }).map((_, i) => {
    const layer = Math.floor(i / 12), k = i % 12; const ang = k / 12 * Math.PI * 2 + layer * 0.4;
    const rr = 0.35 + random(`c${i}`) * 0.75;
    return { x: Math.cos(ang) * rr, z: Math.sin(ang) * rr * 0.7, y: -1.0 + layer * 0.22 + random(`h${i}`) * 0.08, rx: random(`a${i}`) * 0.6, delay: i * 1.1 };
  }), [n]);
  return (
    <group>
      <mesh position={[0, -0.2, 0]}><boxGeometry args={[2.8, 2.0, 2.0]} /><meshPhysicalMaterial color="#9FD3FF" transparent opacity={0.16} roughness={0.05} metalness={0} clearcoat={1} side={THREE.DoubleSide} /></mesh>
      <lineSegments position={[0, -0.2, 0]}><edgesGeometry args={[new THREE.BoxGeometry(2.8, 2.0, 2.0)]} /><lineBasicMaterial color="#CFE8FF" transparent opacity={0.6} /></lineSegments>
      {spots.map((s, i) => {
        const p = interpolate(f, [t0 + s.delay, t0 + s.delay + 9], [0, 1], { ...clamp, easing: Easing.in(Easing.quad) });
        if (p <= 0) return null;
        const y = 2.6 + (s.y - 2.6) * p;
        const bx = burst ? s.x * (1 + burst * 3) : s.x, by = burst ? y + burst * (1.5 + random(`u${i}`) * 2) : y, bz = burst ? s.z * (1 + burst * 3) : s.z;
        return <group key={i} position={[bx, by, bz]} rotation={[s.rx + burst * 6 * random(`v${i}`), i, burst * 4]}><group scale={0.3}><Coin /></group></group>;
      })}
    </group>
  );
};

const Jar: React.FC<{ fill: number }> = ({ fill }) => {
  const body = useMemo(() => lathe([[0, -1.5], [0.82, -1.5], [0.95, -1.42], [1.0, -1.25], [1.0, -0.6], [0.94, -0.45], [1.0, -0.3], [1.0, 0.35], [0.94, 0.5], [1.0, 0.65], [1.0, 0.95], [0.9, 1.2], [0.6, 1.42], [0.34, 1.52], [0.3, 1.7]]), []);
  const top = -1.45 + 2.6 * fill;
  const water = useMemo(() => lathe([[0, -1.45], [0.9, -1.45], [0.94, -1.25], [0.94, top], [0, top]], 64), [top]);
  return (
    <group>
      <mesh geometry={body}><meshPhysicalMaterial color="#5FB4FF" transparent opacity={0.42} roughness={0.08} clearcoat={1} side={THREE.DoubleSide} emissive="#0b3a66" emissiveIntensity={0.35} /></mesh>
      <mesh geometry={water}><meshStandardMaterial color="#2E8CF0" transparent opacity={0.55} roughness={0.2} emissive="#103a70" emissiveIntensity={0.5} /></mesh>
      <mesh position={[0, 1.82, 0]}><cylinderGeometry args={[0.36, 0.36, 0.26, 48]} /><meshStandardMaterial color="#1F6FD1" roughness={0.35} /></mesh>
    </group>
  );
};

const Box: React.FC = () => (
  <group>
    <mesh><boxGeometry args={[2.2, 1.6, 1.6]} /><meshStandardMaterial color="#C8955A" roughness={0.75} /></mesh>
    <mesh position={[0, 0.81, 0]}><boxGeometry args={[0.45, 0.02, 1.62]} /><meshStandardMaterial color="#E9D3A6" roughness={0.5} /></mesh>
  </group>
);

/* sparks + flying shards for "burst" */
const Shards: React.FC<{ k: number }> = ({ k }) => (
  <group>
    {Array.from({ length: 22 }).map((_, i) => {
      const a = random(`sa${i}`) * Math.PI * 2, e = (random(`se${i}`) - 0.5) * 2, r = k * (2 + random(`sr${i}`) * 2.5);
      return <mesh key={i} position={[Math.cos(a) * r, e * r * 0.8, Math.sin(a) * r * 0.6]} rotation={[k * 8 * random(`x${i}`), k * 6, 0]} scale={(1 - k) * 0.25 + 0.05}>
        <boxGeometry args={[0.6, 0.6, 0.12]} /><meshStandardMaterial color={i % 3 ? GOLD : "#ffffff"} emissive={GOLD} emissiveIntensity={1 - k} metalness={0.6} roughness={0.3} /></mesh>;
    })}
  </group>
);

export const OBJECT_KINDS = ["padlock", "phone", "laptop", "envelope", "shield", "key", "bulb", "clock", "coin", "coins", "jar", "box"];

export const Object3D: React.FC<{ kind: string; at: number; size: number; act?: string; act_at?: number; count?: number }> = ({ kind, at, size, act, act_at, count = 30 }) => {
  const f = useCurrentFrame();
  const s = spring({ frame: f - fx(at), fps: FPS, config: { damping: 12, stiffness: 120 } });
  const a0 = fx(act_at ?? at + 0.6);
  const k = act ? ease(f, a0, 14) : 0;
  const open = act === "open" ? k : 0;
  const glow = act === "glow" ? k * (0.7 + 0.3 * Math.sin((f - a0) / 3)) : act === "buzz" ? Math.max(0, Math.sin((f - a0) / 2)) * (f >= a0 ? 1 : 0) : 0.2;
  const burst = act === "burst" ? k : 0;
  const buzz = act === "buzz" && f >= a0 ? Math.sin((f - a0) * 3.1) * 0.08 * Math.max(0, 1 - (f - a0) / 30) : 0;
  const spinAct = act === "spin" ? k * Math.PI * 2 : 0;
  const idle = kind === "coin" ? f * 0.05 : Math.sin(f / 40) * 0.25;
  const fill = act === "fill" ? k : interpolate(f, [fx(at + 0.2), fx(at + 0.2) + 24], [0.02, 0.8], clamp);
  const clockT = act === "tick" ? interpolate(f, [a0, a0 + 45], [0, 3], { ...clamp, easing: Easing.inOut(Easing.cubic) }) : 0.1;
  const body = (() => {
    switch (kind) {
      case "padlock": return <Padlock open={open} />;
      case "phone": return <Phone glow={glow} />;
      case "laptop": return <Laptop open={act === "open" ? k : 1} />;
      case "envelope": return <Envelope open={open} />;
      case "shield": return <Shield glow={glow} />;
      case "key": return <Key />;
      case "bulb": return <Bulb glow={act === "glow" ? k : 0.15} />;
      case "clock": return <Clock t={clockT} />;
      case "coin": return <Coin />;
      case "coins": return <group scale={1.3}><Coins f={f} t0={act === "fill" || !act ? a0 : fx(at)} count={count} burst={burst} /></group>;
      case "box": return <Box />;
      default: return <Jar fill={fill} />;
    }
  })();
  return (
    <ThreeCanvas width={size} height={size} camera={{ position: [0, 0.4, 7.2], fov: 38 }} gl={{ antialias: true, alpha: true, preserveDrawingBuffer: true }}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[3, 4, 5]} intensity={2.4} />
      <directionalLight position={[-4, 1, -2]} intensity={1.5} color="#6EBEFF" />
      <pointLight position={[0, -2, 3]} intensity={6} color={GOLD} distance={9} />
      <group scale={(0.2 + 0.8 * s) * (1 + (act === "burst" && kind !== "coins" ? 0.3 * burst : 0))} position={[buzz, (1 - s) * -1.2, 0]}
        rotation={[0.18, -0.9 + s * 0.9 + idle + spinAct, -0.06 + buzz]}>
        {act === "burst" && kind !== "coins" ? (burst < 0.35 ? body : null) : body}
      </group>
      {act === "burst" && kind !== "coins" && burst > 0 && burst < 1 && <Shards k={burst} />}
    </ThreeCanvas>
  );
};
