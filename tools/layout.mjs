// Computes a fixed network layout for the "All companies" view and writes data/layout.js.
// Sector neighbourhoods on a ring, pulled together by supply links. Deterministic (seeded).
// Usage: node tools/layout.mjs   (run after tools/build_data.py)
import fs from 'node:fs';
const root = new URL('..', import.meta.url).pathname;
const src = fs.readFileSync(root + 'data/graph.js', 'utf8');
const G = JSON.parse(src.slice(src.indexOf('{'), src.lastIndexOf('}') + 1));
const W = 1100, H = 740, BOX = { x0: 26, x1: W - 26, y0: 46, y1: H - 30 };
const RING = ['Information Technology', 'Communication Services', 'Consumer Discretionary', 'Consumer Staples', 'Health Care', 'Financials', 'Real Estate', 'Utilities', 'Energy', 'Materials', 'Industrials'];

let seed = 7; const rnd = () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };

const sup = G.links.filter(l => l.role === 'propagates');
const linked = new Set(sup.flatMap(l => [l.from, l.to]));
const nodes = G.nodes.filter(n => n.sp || linked.has(n.id)).map(n => ({ id: n.id, sector: RING.includes(n.sector) ? n.sector : null, cap: n.cap || 0 }));
const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
const links = sup.filter(l => byId[l.from] && byId[l.to]).map(l => ({ s: byId[l.from], t: byId[l.to] }));
for (const n of nodes) n.deg = 0;
for (const l of links) { l.s.deg++; l.t.deg++; }
for (const n of nodes) n.r = Math.max(n.cap ? Math.max(4, Math.min(13, 3.4 + 0.125 * Math.sqrt(n.cap))) : 4, 0.8 * (4 + 2.1 * Math.sqrt(n.deg))) + 1.7;

// sector anchors on an ellipse, arc share ~ sqrt(size), Information Technology at the top
const count = Object.fromEntries(RING.map(s => [s, nodes.filter(n => n.sector === s).length]));
const wsum = RING.reduce((a, s) => a + Math.sqrt(count[s]), 0);
const anchor = {}; let acc = -Math.sqrt(count[RING[0]]) / 2;
for (const s of RING) {
  const w = Math.sqrt(count[s]), th = -Math.PI / 2 + 2 * Math.PI * (acc + w / 2) / wsum; acc += w;
  anchor[s] = { x: W / 2 + 408 * Math.cos(th), y: (BOX.y0 + BOX.y1) / 2 + 238 * Math.sin(th) };
}
// start positions
const nb = {}; for (const l of links) { (nb[l.s.id] ||= []).push(l.t); (nb[l.t.id] ||= []).push(l.s); }
for (const n of nodes) {
  let a = n.sector ? anchor[n.sector] : null;
  if (!a) { const ns = (nb[n.id] || []).filter(m => m.sector); a = ns.length ? { x: ns.reduce((s, m) => s + anchor[m.sector].x, 0) / ns.length, y: ns.reduce((s, m) => s + anchor[m.sector].y, 0) / ns.length } : { x: W / 2, y: H / 2 }; }
  n.x = a.x + (rnd() - 0.5) * 80; n.y = a.y + (rnd() - 0.5) * 80; n.vx = 0; n.vy = 0;
}
const TICKS = 520; let alpha = 1; const decay = 1 - Math.pow(0.001, 1 / TICKS);
for (let tick = 0; tick < TICKS; tick++) {
  alpha += (0 - alpha) * decay;
  // sector gravity (private counterparties only get a faint pull to the middle)
  for (const n of nodes) {
    if (n.sector) { const a = anchor[n.sector], g = n.deg ? 0.075 : 0.095; n.vx += (a.x - n.x) * g * alpha; n.vy += (a.y - n.y) * g * alpha; }
    else { n.vx += (W / 2 - n.x) * 0.006 * alpha; n.vy += (H / 2 - n.y) * 0.006 * alpha; }
  }
  // links: strong inside a sector or to a private counterparty, gentle across sectors
  for (const l of links) {
    const s = l.s, t = l.t; let dx = t.x + t.vx - s.x - s.vx || 1e-6, dy = t.y + t.vy - s.y - s.vy || 1e-6;
    const d = Math.sqrt(dx * dx + dy * dy), cross = s.sector && t.sector && s.sector !== t.sector;
    const k = (cross ? 0.05 : 0.55) / Math.min(s.deg, t.deg), want = 20 + s.r + t.r;
    const f = (d - want) / d * alpha * k, bias = s.deg / (s.deg + t.deg);
    // a private counterparty moves to its partner, not the other way round
    const bs = !s.sector && t.sector ? 0.97 : s.sector && !t.sector ? 0.03 : 1 - bias;
    t.vx -= dx * f * (1 - bs); t.vy -= dy * f * (1 - bs); s.vx += dx * f * bs; s.vy += dy * f * bs;
  }
  // repulsion
  for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
    const a = nodes[i], b = nodes[j]; let dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy;
    if (d2 > 110 * 110) continue; if (d2 < 1) { dx = rnd() - 0.5; dy = rnd() - 0.5; d2 = 1; }
    const w = 15 * alpha / d2; a.vx -= dx * w; a.vy -= dy * w; b.vx += dx * w; b.vy += dy * w;
  }
  for (const n of nodes) { n.vx *= 0.6; n.vy *= 0.6; n.x += n.vx; n.y += n.vy; }
  // collisions + stay inside the box
  for (let pass = 0; pass < 2; pass++) {
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j], dx = b.x - a.x, dy = b.y - a.y, min = a.r + b.r; if (Math.abs(dx) > min || Math.abs(dy) > min) continue;
      const d = Math.sqrt(dx * dx + dy * dy) || 1e-6; if (d >= min) continue;
      const push = (min - d) / d * 0.5, wa = b.r * b.r / (a.r * a.r + b.r * b.r);
      a.x -= dx * push * wa; a.y -= dy * push * wa; b.x += dx * push * (1 - wa); b.y += dy * push * (1 - wa);
    }
    for (const n of nodes) { n.x = Math.max(BOX.x0 + n.r, Math.min(BOX.x1 - n.r, n.x)); n.y = Math.max(BOX.y0 + n.r, Math.min(BOX.y1 - n.r, n.y)); }
  }
}
// sector labels: above or below the cluster, wherever the fewest dots are in the way
const placedLabels = [];
const sectors = RING.map(s => {
  const core = nodes.filter(n => n.sector === s), cx = core.reduce((a, n) => a + n.x, 0) / core.length, cy = core.reduce((a, n) => a + n.y, 0) / core.length;
  // the cluster also includes the private counterparties hanging off it, so the label clears them too
  const ns = [...core, ...nodes.filter(n => !n.sector && (nb[n.id] || []).some(m => m.sector === s && Math.hypot(m.x - n.x, m.y - n.y) < 60))];
  const w = s.length * 8.4 + 6, prefTop = cy < (BOX.y0 + BOX.y1) / 2; let best = null;
  for (const top of [prefTop, !prefTop]) for (const dx of [0, -45, 45, -90, 90, -135, 135]) {
    const x = Math.max(w / 2 + 8, Math.min(W - w / 2 - 8, cx + dx));
    const under = ns.filter(n => Math.abs(n.x - x) < w / 2 + 8), col = under.length ? under : ns;
    const y = Math.max(15, Math.min(H - 6, top ? Math.min(...col.map(n => n.y - n.r)) - 8 : Math.max(...col.map(n => n.y + n.r)) + 16));
    const box = [x - w / 2 - 3, y - 12, x + w / 2 + 3, y + 5];
    const hit = nodes.filter(n => n.x + n.r > box[0] && n.x - n.r < box[2] && n.y + n.r > box[1] && n.y - n.r < box[3]).length;
    const clash = placedLabels.filter(b => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1]).length;
    const score = hit + clash * 6 + (top === prefTop ? 0 : 0.6) + Math.abs(dx) / 90;
    if (!best || score < best.score) best = { score, x, y, box };
  }
  placedLabels.push(best.box);
  return { name: s, n: ns.length, x: +best.x.toFixed(1), y: +best.y.toFixed(1) };
});
const pos = Object.fromEntries(nodes.map(n => [n.id, [+n.x.toFixed(1), +n.y.toFixed(1)]]));
fs.writeFileSync(root + 'data/layout.js', 'window.LAYOUT = ' + JSON.stringify({ w: W, h: H, pos, sectors }) + ';\n');
let overlaps = 0; for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) { const a = nodes[i], b = nodes[j]; if (Math.hypot(a.x - b.x, a.y - b.y) < a.r + b.r - 1.5) overlaps++; }
console.log(`layout: ${nodes.length} nodes, ${links.length} links, ${overlaps} overlaps left`);
