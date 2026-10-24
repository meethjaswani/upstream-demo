'use strict';
// ============================================================
//  Data
// ============================================================
const G = window.GRAPH;
const N = Object.fromEntries(G.nodes.map(n => [n.id, n]));
const LK = Object.fromEntries(G.links.map(l => [l.id, l]));
const SUPL = G.links.filter(l => l.role === 'propagates');          // from = seller, to = buyer
const EQL = G.links.filter(l => l.type === 'equity' && l.stake);    // from = investor, to = investee
const group = (arr, key) => { const o = {}; for (const x of arr) (o[x[key]] ||= []).push(x); return o; };
const bySeller = group(SUPL, 'from'), byBuyer = group(SUPL, 'to'), eqByInvestee = group(EQL, 'to'), eqByInvestor = group(EQL, 'from');
const linksOf = {}; for (const l of G.links) { (linksOf[l.from] ||= []).push(l); (linksOf[l.to] ||= []).push(l); }

const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const fB = v => v == null ? 'n/a' : Math.abs(v) >= 1000 ? '$' + (v / 1000).toFixed(2) + 'T' : '$' + (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2)) + 'B';
const fP = (p, d = 1) => (p * 100).toFixed(d) + '%';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const cleanName = s => s.replace(/,? (Inc\.?|Incorporated|Corporation|Corp\.?|Company|Co\.|plc|PLC|Ltd\.?|Limited|Holdings?|Group|N\.V\.|S\.A\.|L\.P\.|LLC|\(The\))(?=$|,| )/g, '').replace(/^The /, '').replace(/[,.]+$/, '').trim();
const SHORT = { tsmc: 'TSMC', zeiss: 'Zeiss', sibelco: 'Sibelco', quartz_corp: 'Quartz Corp', tok: 'Tokyo Ohka', shin_etsu: 'Shin-Etsu', 'brk-b': 'Berkshire', us_gov: 'U.S. government' };
const short = id => { const n = N[id]; if (!n) return id; if (SHORT[id]) return SHORT[id]; const c = cleanName(n.name); return c.length > 18 ? (n.sp && n.ticker ? n.ticker : c.slice(0, 17) + '…') : c; };
const tick = id => N[id].sp && N[id].ticker ? N[id].ticker.split(/[;,]/)[0] : short(id);
const tagHTML = c => c ? `<span class="tag ${c}">${c}</span>` : '';

// ============================================================
//  Link strength:  p = base x size x confidence
//  base: disclosed revenue share, else 1 / number of buyers (weighted cascade, Kempe, Kleinberg, Tardos 2003)
//  size: sqrt(buyer market cap / seller market cap), capped at 1
//  confidence: disclosed 1.0, reported 0.7, estimated 0.4
// ============================================================
const CONF_W = { DISCLOSED: 1.0, REPORTED: 0.7, ESTIMATED: 0.4 };
const CONF_TXT = { DISCLOSED: 'Read from a filing and checked by hand.', REPORTED: 'From credible media, or from a filing we have not yet checked by hand.', ESTIMATED: 'Found by a text rule or inferred, not yet checked by hand.' };
const confOf = l => l.conf ? l.conf : l.exist === 'REPORTED' ? 'REPORTED' : l.review === 'reviewed' ? 'DISCLOSED' : 'ESTIMATED';
const nBuyers = id => new Set((bySeller[id] || []).map(l => l.to)).size, nSellers = id => new Set((byBuyer[id] || []).map(l => l.from)).size;
function weigh(l, kind) {
  const seller = N[l.from], buyer = N[l.to], tag = confOf(l), conf = CONF_W[tag];
  const demand = kind === 'demand', disclosed = demand ? l.share : l.reliance, n = demand ? nBuyers(l.from) : nSellers(l.to);
  const base = disclosed != null ? Math.min(1, disclosed) : 1 / n;
  const baseFrom = disclosed != null ? (demand ? 'disclosed revenue share' : 'disclosed reliance') : `1 / ${n} ${demand ? 'buyer' : 'supplier'}${n === 1 ? '' : 's'}`;
  const big = demand ? buyer.cap : seller.cap, small = demand ? seller.cap : buyer.cap;
  const size = big && small ? Math.min(1, Math.sqrt(big / small)) : 1;
  return { p: Math.min(1, base * size * conf), base, baseFrom, size, sized: !!(big && small), conf, tag, disclosed: disclosed != null };
}
const W = { demand: {}, supply: {} };
for (const l of SUPL) { W.demand[l.id] = weigh(l, 'demand'); W.supply[l.id] = weigh(l, 'supply'); }

// ============================================================
//  Independent cascade, Monte Carlo
// ============================================================
const RUNS = 20000, DAMP = 0.6, SEED = 42;
function mulberry32(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
// One cascade per group of starting companies. A scenario can have several groups with different directions.
function cascade(g, rand, runs) {
  const demand = g.kind === 'demand', w = W[g.kind], adj = demand ? byBuyer : bySeller, nextOf = l => demand ? l.from : l.to, base = g.direct ? 1 : 0;
  const hits = {}, dropSum = {}, hopSum = {}, pass = {};
  for (let r = 0; r < runs; r++) {
    const hop = new Map(g.origins.map(o => [o, 0])); let fr = g.origins.slice();
    for (let k = 1; fr.length && k <= 8; k++) {
      const nx = [];
      for (const j of fr) for (const l of adj[j] || []) {
        const t = nextOf(l); if (hop.has(t)) continue;
        if (rand() < w[l.id].p) { hop.set(t, k); nx.push(t); pass[l.id] = (pass[l.id] || 0) + 1; }
      }
      fr = nx;
    }
    for (const [id, k] of hop) if (k > 0) { hits[id] = (hits[id] || 0) + 1; dropSum[id] = (dropSum[id] || 0) + g.severity * Math.pow(DAMP, k - 1 + base); hopSum[id] = (hopSum[id] || 0) + k; }
  }
  // "direct" groups: the event changes the starting companies' own value, before anything spreads
  if (g.direct) for (const o of g.origins) { hits[o] = runs; dropSum[o] = g.severity * runs; hopSum[o] = 0; }
  return { hits, dropSum, hopSum, pass };
}
function simulate(sc, runs = RUNS) {
  const t0 = performance.now(), rand = mulberry32(SEED);
  const groups = sc.groups || [{ label: '', origins: sc.origins, kind: sc.kind, dir: sc.dir > 0 ? 1 : -1, severity: sc.severity, direct: false }];
  const parts = groups.map(g => cascade(g, rand, runs));
  const pass = {}, passBest = {}, passDir = {};
  parts.forEach((p, i) => { for (const id in p.pass) { pass[id] = (pass[id] || 0) + p.pass[id]; if (!(passBest[id] >= p.pass[id])) { passBest[id] = p.pass[id]; passDir[id] = groups[i].dir; } } });
  const rows = [...new Set(parts.flatMap(p => Object.keys(p.hits)))].map(id => {
    let net = 0, miss = 1, hop = 99, best = -1, via = null, viaLink = null;
    parts.forEach((p, i) => {
      if (!p.hits[id]) return;
      const g = groups[i], d = p.dropSum[id] / runs; net += g.dir * d; miss *= 1 - p.hits[id] / runs; hop = Math.min(hop, Math.round(p.hopSum[id] / p.hits[id]));
      if (d > best) { best = d; const ins = ((g.kind === 'demand' ? bySeller[id] : byBuyer[id]) || []).filter(l => p.pass[l.id]).sort((a, b) => p.pass[b.id] - p.pass[a.id])[0]; via = ins ? (g.kind === 'demand' ? ins.to : ins.from) : null; viaLink = ins?.id; }
    });
    const drop = Math.abs(net);
    return { id, p: 1 - miss, net, sgn: net >= 0 ? 1 : -1, drop, hop, mcar: N[id].cap ? drop * N[id].cap : null, via, viaLink };
  }).sort((a, b) => (b.mcar ?? -1) - (a.mcar ?? -1) || b.drop - a.drop);
  const byId = Object.fromEntries(rows.map(r => [r.id, r]));
  const stakes = {};
  for (const l of EQL) {
    const g = groups.find(x => !x.direct && x.origins.includes(l.to)), d = g ? g.dir * g.severity : byId[l.to]?.net; if (!d) continue;
    (stakes[l.from] ||= { id: l.from, net: 0, in: [] }).net += l.stake * d; stakes[l.from].in.push(l.to);
  }
  const pathOf = id => { const p = [id]; let c = byId[id]; for (let i = 0; i < 8 && c?.via && !p.includes(c.via); i++) { p.unshift(c.via); c = byId[c.via]; } return p; };
  const gain = rows.filter(r => r.sgn > 0).reduce((s, r) => s + (r.mcar || 0), 0), loss = rows.filter(r => r.sgn < 0).reduce((s, r) => s + (r.mcar || 0), 0);
  const dirs = new Set(groups.map(g => g.dir)), origins = [...new Set(groups.flatMap(g => g.origins))];
  const full = { ...sc, origins, kind: groups[0].kind, dir: dirs.size > 1 ? 0 : groups[0].dir, severity: Math.max(...groups.map(g => g.severity)) };
  return { sc: full, groups, runs, ms: performance.now() - t0, rows, byId, pass, passDir, pathOf, gain, loss, total: gain + loss,
    stakes: Object.values(stakes).map(s => ({ ...s, usd: Math.abs(s.net), sgn: s.net >= 0 ? 1 : -1 })).sort((a, b) => b.usd - a.usd), tried: SUPL.length };
}

// ============================================================
//  Scenario parsing (keyword parser; replaced by the LLM when the local server has a key)
// ============================================================
const GROUPS = [[/(ai compute buyers|ai buyers|hyperscalers?|cloud giants|big tech)/, ['msft', 'amzn', 'googl', 'meta', 'orcl', 'openai']]];
const EXTRA = { google: 'googl', alphabet: 'googl', aws: 'amzn', azure: 'msft', chatgpt: 'openai', facebook: 'meta', tsmc: 'tsmc', 'taiwan semiconductor': 'tsmc', zeiss: 'zeiss', 'spruce pine': 'sibelco', 'federal government': 'us_gov', 'u.s. government': 'us_gov', 'us government': 'us_gov' };
const MODEL_IDS = [...new Set(SUPL.flatMap(l => [l.from, l.to]))];
const ALIASES = [...Object.entries(EXTRA), ...MODEL_IDS.map(id => [cleanName(N[id].name).toLowerCase(), id])].filter(([a, id]) => N[id] && a.length >= 4).sort((a, b) => b[0].length - a[0].length);
const TICKERS = Object.fromEntries(MODEL_IDS.filter(id => N[id].sp && N[id].ticker).map(id => [N[id].ticker, id]));
let LIVE = false, SERVER = false, SERVER_KEY = false;
const KEY_STORE = 'upstream.apiKey';
let USER_KEY = (() => { try { return localStorage.getItem(KEY_STORE) || ''; } catch (e) { return ''; } })();
function parseLocal(text) {
  const t = ' ' + text.toLowerCase() + ' ', notes = [], found = new Map();
  for (const [re, ids] of GROUPS) { const m = t.match(re); if (m) ids.filter(id => N[id]).forEach(id => found.set(id, m.index)); }
  for (const [a, id] of ALIASES) { if (found.size >= 8) break; const i = t.search(new RegExp('(^|[^a-z0-9])' + a.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '([^a-z0-9]|$)')); if (i >= 0 && !found.has(id)) found.set(id, i); }
  for (const m of text.matchAll(/\b[A-Z]{2,5}\b/g)) if (TICKERS[m[0]] && !found.has(TICKERS[m[0]])) found.set(TICKERS[m[0]], m.index);
  let origins = [...found.entries()].sort((a, b) => a[1] - b[1]).map(e => e[0]);
  if (!origins.length) return { text, error: 'No company found in that text. This model starts a shock at named companies, for example "Apple cuts orders 25%" or "banks cut lending 10%" is not enough on its own.' };
  let kind = /(shortage|outage|can'?t deliver|cannot deliver|halts?|output (falls|drops|cut)|production (cut|halt|falls)|supply (shock|cut|disruption)|fire|earthquake|export ban)/.test(t) ? 'supply' : 'demand';
  const has = (id, k) => !!(k === 'demand' ? byBuyer[id] : bySeller[id]);
  if (!origins.some(o => has(o, kind)) && origins.some(o => has(o, kind === 'demand' ? 'supply' : 'demand'))) { kind = kind === 'demand' ? 'supply' : 'demand'; notes.push(`read as a ${kind} shock, because that is the side with links`); }
  const dir = /(raises?|increases?|boosts?|ramps? up|doubles?|triples?|expands?|spends? more|buys? more|orders? more|delivers? more|hikes?|adds?|steps? up|surges?|accelerates?)/.test(t) && !/(cuts?|reduces?|slashes|halts?|falls?|drops?|less|miss|default|cancel|fail)/.test(t) ? 1 : -1;
  let sev; const pm = t.match(/(\d+(?:\.\d+)?)\s*(%|percent)/);
  if (pm) sev = Math.min(100, parseFloat(pm[1])); else if (/\b(halves?|half)\b/.test(t)) sev = 50; else if (dir > 0 && /doubles?|triples?/.test(t)) sev = 100;
  else if (/\b(miss(es|ed)?|defaults?|stops? paying|cancels?|collapses?|fails?|bankrupt)/.test(t)) sev = 100; else { sev = 40; notes.push('no size given, assumed 40%'); }
  return { text, origins, kind, dir, severity: sev / 100, notes };
}
async function checkLive() {
  if (location.protocol !== 'file:') {
    try { const r = await fetch('api/health', { cache: 'no-store' }); if (r.ok) { SERVER = true; SERVER_KEY = !!(await r.json()).live; } } catch (e) { SERVER = false; }
  }
  renderParser();
}
function renderParser() {
  LIVE = SERVER && (SERVER_KEY || !!USER_KEY);
  $('#parserBadge').textContent = LIVE ? (USER_KEY ? 'Read by the LLM (your key)' : 'Read by the LLM (live)') : 'Keyword parser (offline)';
  const btn = $('#keyBtn');
  if (!SERVER) { btn.textContent = 'Run npm start to use your own API key'; btn.disabled = true; return; }
  btn.disabled = false;
  btn.textContent = USER_KEY ? 'Using your API key \u00b7 change' : 'Use your own API key';
}
function initKey() {
  const form = $('#keyForm'), note = $('#keyNote'), input = $('#keyIn');
  const toggle = show => { form.classList.toggle('hide', !show); note.classList.toggle('hide', !show); if (show) input.focus(); };
  const save = key => { USER_KEY = key; try { key ? localStorage.setItem(KEY_STORE, key) : localStorage.removeItem(KEY_STORE); } catch (e) { /* storage blocked: keep it for this visit */ } renderParser(); };
  $('#keyBtn').addEventListener('click', () => toggle(form.classList.contains('hide')));
  form.addEventListener('submit', e => { e.preventDefault(); const key = input.value.trim(); if (key) { save(key); input.value = ''; toggle(false); } });
  $('#keyDel').addEventListener('click', () => { save(''); input.value = ''; toggle(false); });
}
async function parseSmart(text) {
  if (!LIVE) return parseLocal(text);
  try {
    const ctl = new AbortController(), to = setTimeout(() => ctl.abort(), 15000);
    const r = await fetch('api/parse-scenario', { method: 'POST', headers: { 'content-type': 'application/json', ...(USER_KEY ? { 'x-user-api-key': USER_KEY } : {}) }, body: JSON.stringify({ text }), signal: ctl.signal });
    clearTimeout(to); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'status ' + r.status);
    const j = await r.json();
    const groups = (j.groups || []).map(g => ({ label: g.label || '', origins: (g.origins || []).filter(id => N[id]).slice(0, 8), kind: g.kind, dir: g.direction === 'positive' ? 1 : -1, severity: +g.severity, direct: !!g.hits_them_directly }))
      .filter(g => g.origins.length && ['demand', 'supply'].includes(g.kind) && g.severity > 0 && g.severity <= 1).slice(0, 4);
    if (!groups.length) { if (j.reason) return { text, error: 'The LLM could not turn this into company-level effects: ' + j.reason }; throw new Error('bad parse'); }
    const notes = ['read by the LLM' + (j.reason ? ': ' + j.reason : '')];
    if (groups.length === 1 && !groups[0].direct) return { text, origins: groups[0].origins, kind: groups[0].kind, dir: groups[0].dir, severity: groups[0].severity, notes };
    return { text, title: j.title || text, groups, origins: [...new Set(groups.flatMap(g => g.origins))], kind: groups[0].kind, dir: 0, severity: Math.max(...groups.map(g => g.severity)), notes };
  } catch (e) { const sc = parseLocal(text), why = 'The LLM could not be reached (' + e.message + '), so the keyword parser was used.'; if (sc.error) sc.error += ' ' + why; else sc.notes.push(why); return sc; }
}

// ============================================================
//  State
// ============================================================
const S = {
  pf: new Set(['nvda', 'msft', 'orcl', 'coreweave', 'amd'].filter(id => N[id])), focus: N.openai ? 'openai' : MODEL_IDS[0],
  view: 'all', sizeBy: 'value', fam: null, sel: null, loops: false, loopIdx: 0, loopList: [],
  sc: null, res: null, shown: null, hot: new Set(), hop: 0, nHop: 0, animating: false, animToken: 0, revealed: new Set(), cap: '',
  q: '', fType: 'All', srcOpen: false
};
const PRESETS = [
  { tag: 'AI', t: 'OpenAI cuts compute spending 40%', sc: { origins: ['openai'], kind: 'demand', severity: 0.4 } },
  { tag: 'health care', t: 'Big three drug distributors cut orders 25%', sc: { title: 'Big three drug distributors cut orders 25%', origins: ['mck', 'cor', 'cah'], kind: 'demand', severity: 0.25 } },
  { tag: 'AI', t: 'AI compute buyers cut spending 30%', sc: { origins: ['msft', 'amzn', 'googl', 'meta', 'orcl', 'openai'], kind: 'demand', severity: 0.3 } },
  { tag: 'chips', t: 'TSMC output falls 50%', sc: { origins: ['tsmc'], kind: 'supply', severity: 0.5 } },
  { tag: 'retail', t: 'Walmart cuts purchases 20%', sc: { origins: ['wmt'], kind: 'demand', severity: 0.2 } },
  { tag: 'AI, upside', t: 'Microsoft raises AI spending 30%', sc: { origins: ['msft'], kind: 'demand', dir: 1, severity: 0.3 } },
  { tag: 'energy, mixed', t: 'Oil price falls 20%', sc: { title: 'Oil price falls 20%', dir: 0, origins: ['xom', 'cvx', 'cop', 'dal', 'ual', 'luv'], kind: 'demand', severity: 0.1, groups: [
    { label: 'Oil producers', origins: ['xom', 'cvx', 'cop'], kind: 'demand', dir: -1, severity: 0.1, direct: true },
    { label: 'Airlines', origins: ['dal', 'ual', 'luv'], kind: 'demand', dir: 1, severity: 0.06, direct: true }] } },
  { tag: 'chips', t: 'Zeiss optics output falls 50%', sc: { origins: ['zeiss'], kind: 'supply', severity: 0.5 } }
].filter(p => p.sc.origins.every(id => N[id]));
PRESETS.forEach(p => { if (p.sc.groups) p.note = 'illustrative assumption'; });
const INK = '#16171B', NEG = '#D92D4A', POS = '#0B7A2E', ORANGE = '#F7931E';
let RED = NEG;   // the shock colour: red for a cut, green for a boost
const isUp = () => (S.res ? S.res.sc.dir : S.sc?.dir) > 0;
const isMixed = () => (S.res ? S.res.sc.dir : S.sc?.dir) === 0;
const V = () => isMixed()
  ? { sign: '', risk: 'changed', Risk: 'Market cap change', hit: 'affected', move: 'change', lose: 'change', stakes: 'Stakes revalued' }
  : isUp()
    ? { sign: '+', risk: 'gained', Risk: 'Market cap gained', hit: 'lifted', move: 'rise', lose: 'gain', stakes: 'Stakes marked up' }
    : { sign: '-', risk: 'at risk', Risk: 'Market cap at risk', hit: 'hit', move: 'drop', lose: 'lose', stakes: 'Stakes written down' };
const colOf = x => x > 0 ? POS : NEG;
const nodeCol = id => colOf(S.res?.byId[id]?.sgn ?? S.res?.sc.dir ?? -1);
const linkCol = id => colOf(S.res?.passDir[id] ?? -1);
const gOf = id => S.res.groups.find(g => g.origins.includes(id));
const rs = r => r.sgn > 0 ? '+' : '-';
function setTone() { RED = isUp() ? POS : NEG; document.body.classList.toggle('pos', isUp()); document.body.classList.toggle('mixed', isMixed()); }
const NS = 'http://www.w3.org/2000/svg', MW = 1100, MH = 740;
const el = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
const R = id => N[id].cap ? Math.max(7, Math.min(22, 6 + 0.26 * Math.sqrt(N[id].cap))) : 8;
const describe = sc => {
  if (sc.title) return sc.title;
  const who = sc.origins.length > 2 ? `${short(sc.origins[0])} and ${sc.origins.length - 1} others` : sc.origins.map(short).join(' and '), one = sc.origins.length === 1, pct = fP(sc.severity, 0);
  if (sc.kind === 'demand') return `${who} ${sc.dir > 0 ? 'raise' : 'cut'}${one ? 's' : ''} spending ${pct}`;
  return `${who} deliver${one ? 's' : ''} ${pct} ${sc.dir > 0 ? 'more' : 'less'}`;
};

// ============================================================
//  Layout: suppliers | company | customers (ego view), or by hop (scenario view)
// ============================================================
const CAPN = 9;
function egoSets(f) {
  const rank = (ls, other, kind) => { const best = {}; for (const l of ls) { const o = l[other], p = W[kind][l.id].p; if (best[o] == null || p > best[o]) best[o] = p; } return Object.keys(best).sort((a, b) => best[b] - best[a]); };
  const sup1 = rank(byBuyer[f] || [], 'from', 'demand'), cust1 = rank(bySeller[f] || [], 'to', 'demand').filter(id => !sup1.includes(id));
  const sup2 = rank(sup1.flatMap(s => byBuyer[s] || []), 'from', 'demand').filter(id => id !== f && !sup1.includes(id) && !cust1.includes(id));
  const cust2 = rank(cust1.flatMap(c => bySeller[c] || []), 'to', 'demand').filter(id => id !== f && ![...sup1, ...cust1, ...sup2].includes(id));
  const inv = (eqByInvestee[f] || []).sort((a, b) => b.stake - a.stake).map(l => l.from).filter((id, i, a) => a.indexOf(id) === i && ![...sup1, ...cust1, ...sup2, ...cust2].includes(id));
  return { sup2, sup1, cust1, cust2, inv };
}
function egoCols(f, must = []) {
  const s = egoSets(f), take = (ids, n) => { const first = ids.filter(id => must.includes(id)); return [...first, ...ids.filter(id => !must.includes(id))].slice(0, Math.max(n, first.length)); };
  const cols = [
    { name: "Suppliers' suppliers", all: s.sup2, ids: take(s.sup2, 7) }, { name: 'Suppliers', all: s.sup1, ids: take(s.sup1, CAPN) },
    { name: 'Company', all: [f], ids: [f] },
    { name: 'Customers', all: s.cust1, ids: take(s.cust1, CAPN) }, { name: "Customers' customers", all: s.cust2, ids: take(s.cust2, 7) },
    { name: 'Investors', all: s.inv, ids: take(s.inv, 6) }
  ];
  const placed = new Set(cols.flatMap(c => c.ids)), extra = must.filter(id => !placed.has(id));
  if (extra.length) cols.push({ name: 'Also in the loop', all: extra, ids: extra });
  return cols.filter(c => c.ids.length);
}
function scenCols(res) {
  const demand = res.sc.kind === 'demand', vis = res.rows.filter(r => r.p >= 0.005);
  const names = demand ? ['Suppliers', "Suppliers' suppliers", 'Further upstream'] : ['Customers', "Customers' customers", 'Further downstream'];
  const cols = [0, 1, 2].map(i => { const all = vis.filter(r => i < 2 ? r.hop === i + 1 : r.hop >= 3).map(r => r.id); return { name: names[i], all, ids: all.slice(0, 10) }; }).filter(c => c.ids.length);
  const origin = { name: res.groups.length > 1 || res.groups[0].direct ? 'Starts here' : 'Shock starts', all: res.sc.origins, ids: res.sc.origins.slice(0, 8) };
  return demand ? [...cols.reverse(), origin] : [origin, ...cols];
}
let P = {}, NODE = {}, EDGE = {}, COLS = [], gParticles, gPulse, gShock, gFloat;
function edgeD(l) {
  const a = P[l.from], b = P[l.to]; if (!a || !b) return null;
  const ra = R(l.from) + 3, rb = R(l.to) + 7, eq = l.type === 'equity', o = eq ? -8 : 0;
  if (b.x - a.x > 40) { const dx = (b.x - a.x) * (eq ? 0.3 : 0.45); return `M${a.x + ra},${a.y + o} C${a.x + ra + dx},${a.y + o} ${b.x - rb - dx},${b.y + o} ${b.x - rb},${b.y + o}`; }
  if (Math.abs(b.x - a.x) <= 40) { const s = eq ? -1 : 1, k = 40 + Math.abs(b.y - a.y) * 0.2; return `M${a.x + s * ra},${a.y} C${a.x + s * (ra + k)},${a.y} ${b.x + s * (rb + k)},${b.y} ${b.x + s * rb},${b.y}`; }
  const up = eq ? -1 : 1, cy = up < 0 ? Math.min(a.y, b.y) - 110 : Math.max(a.y, b.y) + 110;
  return `M${a.x},${a.y + up * ra} C${a.x},${cy} ${b.x},${cy} ${b.x},${b.y + up * rb}`;
}
const edgeW = l => l.type === 'equity' ? 1.6 : 1.2 + 6.5 * W.demand[l.id].p;
const EDGE_BASE = l => l.type === 'equity' ? ORANGE : '#A9A398';

// ============================================================
//  All companies: network map (fixed layout from tools/layout.mjs)
//  position = sector neighbourhood, colour = sector family, size = value or links, line = who sells to whom
// ============================================================
const LAY = window.LAYOUT;
const FAMILY = [
  { key: 'tech', name: 'Tech & communications', color: '#2a78d6', sectors: ['Information Technology', 'Communication Services'] },
  { key: 'industry', name: 'Industry, energy & utilities', color: '#eda100', sectors: ['Industrials', 'Materials', 'Energy', 'Utilities'] },
  { key: 'consumer', name: 'Consumer', color: '#e87ba4', sectors: ['Consumer Discretionary', 'Consumer Staples'] },
  { key: 'health', name: 'Health care', color: '#008300', sectors: ['Health Care'] },
  { key: 'fin', name: 'Financials & real estate', color: '#4a3aa7', sectors: ['Financials', 'Real Estate'] },
  { key: 'other', name: 'Private, overseas & government', color: '#A39E94', sectors: [] }
];
const FAM_OF = {}; FAMILY.forEach(f => f.sectors.forEach(s => { FAM_OF[s] = f; }));
const famOf = id => FAM_OF[N[id].sector] || FAMILY[5];
const OV_IDS = Object.keys(LAY.pos).filter(id => N[id]);
const OVDEG = Object.fromEntries(OV_IDS.map(id => [id, new Set([...(bySeller[id] || []).map(l => l.to), ...(byBuyer[id] || []).map(l => l.from)]).size]));
const OV_LINKS = SUPL.filter(l => LAY.pos[l.from] && LAY.pos[l.to]);
const HUBS = [...OV_IDS].sort((a, b) => OVDEG[b] - OVDEG[a]).slice(0, 3);
const maxCap = Math.max(...OV_IDS.map(id => N[id].cap || 0)), maxDeg = Math.max(...Object.values(OVDEG));
const OV_RANK = [...OV_IDS].sort((a, b) => (Math.sqrt((N[b].cap || 0) / maxCap) + OVDEG[b] / maxDeg) - (Math.sqrt((N[a].cap || 0) / maxCap) + OVDEG[a] / maxDeg));
const ovR = id => S.sizeBy === 'links' ? 4 + 2.1 * Math.sqrt(OVDEG[id]) : (N[id].cap ? Math.max(4, Math.min(13, 3.4 + 0.125 * Math.sqrt(N[id].cap))) : 4);
let OV = null, labelRaf = 0;
const Z = { k: 1, x: 0, y: 0 };
function buildOverview(svg) {
  const vp = el('g', { class: 'vp' }, svg), gL = el('g', {}, vp), gN = el('g', {}, vp), gT = el('g', {}, vp);
  OV = { vp, c: {}, t: {}, lines: [], sec: [], hover: null, k: 0, size: null, r: {} };
  for (const l of OV_LINKS) {
    const a = LAY.pos[l.from], b = LAY.pos[l.to], dx = b[0] - a[0], dy = b[1] - a[1];
    const e = el('path', { d: `M${a[0]},${a[1]} Q${((a[0] + b[0]) / 2 - dy * 0.13).toFixed(1)},${((a[1] + b[1]) / 2 + dx * 0.13).toFixed(1)} ${b[0]},${b[1]}`, class: 'ov-l', 'stroke-width': (0.6 + 1.7 * W.demand[l.id].p).toFixed(2) }, gL);
    OV.lines.push({ l, e });
  }
  for (const id of [...OV_IDS].sort((a, b) => (N[b].cap || 0) - (N[a].cap || 0))) {
    const [x, y] = LAY.pos[id];
    const c = el('circle', { cx: x, cy: y, r: 4, class: 'ov-n' + (OVDEG[id] ? '' : ' nolink') }, gN);
    c.addEventListener('mousemove', e => { showTip(e, ovTip(id)); if (OV.hover !== id) { OV.hover = id; ovFocus(); } });
    c.addEventListener('mouseleave', () => { hideTip(); OV.hover = null; ovFocus(); });
    c.addEventListener('click', e => { e.stopPropagation(); if (S.res) select('node', id); else openChain(id); });
    OV.c[id] = c;
    const t = el('text', { class: 'ov-t', 'text-anchor': 'middle' }, gT); t.textContent = tick(id); t.style.display = 'none'; OV.t[id] = t;
  }
  for (const s of LAY.sectors) { const t = el('text', { x: s.x, y: s.y, 'text-anchor': 'middle', class: 'ov-sec' }, gT); t.textContent = s.name; OV.sec.push({ s, t }); }
  Z.k = 1; Z.x = 0; Z.y = 0;
  if (S.res) fitTo([...S.res.sc.origins, ...S.res.rows.filter(r => r.p >= 0.02).map(r => r.id)]);
  applyZoom(); paintOverview();
}
function ovTip(id) {
  const n = N[id], ns = new Set((byBuyer[id] || []).map(l => l.from)).size, nc = new Set((bySeller[id] || []).map(l => l.to)).size, r = S.res?.byId[id];
  return `<b>${esc(n.name)}</b><div class="s">${esc(n.sector || 'Private / overseas')}${n.cap ? ' · ' + fB(n.cap) : ''}</div>
    <div class="s">${OVDEG[id] ? `${ns} supplier${ns === 1 ? '' : 's'} · ${nc} customer${nc === 1 ? '' : 's'} in the data` : 'No modelled links yet. That does not mean it is safe.'}</div>
    ${r ? `<div class="s">${r.sgn > 0 ? 'Lifted' : 'Hit'} in ${fP(r.p, 0)} of runs${r.mcar != null ? ', ' + rs(r) + fB(r.mcar) : ''}</div>` : ''}<div class="s">${S.res ? 'Click for details' : 'Click to open its supply chain'}</div>`;
}
function ovFocus() {
  if (!OV) return;
  const id = OV.hover || (S.sel?.kind === 'node' && OV.c[S.sel.id] ? S.sel.id : null), near = new Set(id ? [id] : []);
  for (const { l, e } of OV.lines) { const on = id && (l.from === id || l.to === id); e.classList.toggle('on', !!on); if (on) { near.add(l.from); near.add(l.to); } }
  for (const k in OV.c) OV.c[k].classList.toggle('on', near.has(k));
  OV.vp.classList.toggle('focus', !!id); OV.near = id ? near : null;
  queueLabels();
}
function paintOverview() {
  const heat = !!S.res, shown = S.shown || {}, org = heat ? S.res.sc.origins : [], seen = id => S.revealed.has(id) || org.includes(id);
  for (const id of OV_IDS) {
    const c = OV.c[id], f = famOf(id), p = heat ? shown[id] || 0 : 0, o = org.includes(id);
    c.style.fill = heat ? (o && !p ? INK : p > 0 ? nodeCol(id) : '#D9D5CD') : f.color;
    c.style.fillOpacity = heat ? (!p ? 1 : (0.22 + 0.78 * Math.sqrt(p)).toFixed(2)) : (OVDEG[id] ? 1 : 0.32);
    c.classList.toggle('held', S.pf.has(id));
    c.classList.toggle('off', !heat && !!S.fam && f.key !== S.fam);
  }
  for (const { l, e } of OV.lines) {
    const fr = heat ? (S.res.pass[l.id] || 0) / S.res.runs : 0, hot = fr > 0 && seen(l.from) && seen(l.to);
    e.style.stroke = heat ? (hot ? linkCol(l.id) : '#CFCAC0') : famOf(l.from).color;
    e.style.opacity = heat ? (hot ? (0.3 + 0.7 * Math.sqrt(fr)).toFixed(2) : 0.14) : '';
    e.classList.toggle('off', !heat && !!S.fam && famOf(l.from).key !== S.fam && famOf(l.to).key !== S.fam);
  }
  ovFocus(); renderLegend();
}
function applyZoom() {
  if (!OV) return;
  Z.k = Math.max(1, Math.min(9, Z.k)); Z.x = Math.max(MW * (1 - Z.k), Math.min(0, Z.x)); Z.y = Math.max(MH * (1 - Z.k), Math.min(0, Z.y));
  OV.vp.setAttribute('transform', `translate(${Z.x.toFixed(1)},${Z.y.toFixed(1)}) scale(${Z.k.toFixed(3)})`);
  $('#map').style.setProperty('--k', Z.k.toFixed(3));
  if (OV.k !== Z.k || OV.size !== S.sizeBy) {
    const s = Math.pow(Z.k, 0.55);
    for (const id of OV_IDS) { OV.r[id] = ovR(id) / s; OV.c[id].setAttribute('r', OV.r[id].toFixed(2)); }
    OV.k = Z.k; OV.size = S.sizeBy;
  }
  queueLabels();
}
function queueLabels() { if (!labelRaf) labelRaf = requestAnimationFrame(() => { labelRaf = 0; layoutLabels(); }); }
// label the companies that matter most, as many as fit without overlapping; more appear as you zoom in
function layoutLabels() {
  if (!OV) return;
  const k = Z.k, placed = [], show = new Set(), fs = 10.5;
  const hits = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
  for (const { s } of OV.sec) { const x = s.x * k + Z.x, y = s.y * k + Z.y, w = s.name.length * 8.4; placed.push([x - w / 2, y - 11, x + w / 2, y + 3]); }
  const forced = [...new Set([...(OV.near || []), ...(S.res ? [...S.res.sc.origins, ...S.res.rows.filter(r => S.revealed.has(r.id)).slice(0, 14).map(r => r.id)] : []), ...S.pf])].filter(id => OV.c[id]);
  const cap = OV.near ? 0 : S.res ? 0 : k < 1.35 ? 44 : k < 2.2 ? 110 : 9999;
  let free = 0;
  for (const [i, id] of [...new Set([...forced, ...OV_RANK])].entries()) {
    const must = i < forced.length; if (!must && (free >= cap || OV.c[id].classList.contains('off'))) continue;
    const [px, py] = LAY.pos[id], x = px * k + Z.x, y = py * k + Z.y; if (x < 0 || x > MW || y < 0 || y > MH) continue;
    const w = OV.t[id].textContent.length * 6.4 + 6, top = y - OV.r[id] * k - 3 - fs, box = [x - w / 2, top, x + w / 2, top + fs + 2];
    if (placed.some(b => hits(box, b)) && !(must && id === (OV.hover || S.sel?.id))) continue;
    placed.push(box); show.add(id); if (!must) free++;
    OV.t[id].setAttribute('x', px); OV.t[id].setAttribute('y', (py - OV.r[id] - 3.5 / k).toFixed(2));
  }
  for (const id of OV_IDS) OV.t[id].style.display = show.has(id) ? '' : 'none';
}
function fitTo(ids) {
  const ps = ids.filter(id => LAY.pos[id]).map(id => LAY.pos[id]); if (ps.length < 2) return;
  const x0 = Math.min(...ps.map(p => p[0])) - 70, x1 = Math.max(...ps.map(p => p[0])) + 70, y0 = Math.min(...ps.map(p => p[1])) - 60, y1 = Math.max(...ps.map(p => p[1])) + 50;
  Z.k = Math.max(1, Math.min(3.5, Math.min(MW / (x1 - x0), MH / (y1 - y0)))); Z.x = MW / 2 - Z.k * (x0 + x1) / 2; Z.y = MH / 2 - Z.k * (y0 + y1) / 2;
}
function zoomBy(f, cx = MW / 2, cy = MH / 2) { const k = Math.max(1, Math.min(9, Z.k * f)); Z.x = cx - (cx - Z.x) * (k / Z.k); Z.y = cy - (cy - Z.y) * (k / Z.k); Z.k = k; applyZoom(); }
function bindZoom() {
  const svg = $('#map'); let drag = null, dragged = false;
  const pt = e => { const m = svg.getScreenCTM(); return { x: (e.clientX - m.e) / m.a, y: (e.clientY - m.f) / m.d, s: m.a }; };
  svg.addEventListener('wheel', e => { if (!OV) return; e.preventDefault(); const p = pt(e); zoomBy(Math.exp(-e.deltaY * (e.ctrlKey ? 0.012 : 0.0024)), p.x, p.y); }, { passive: false });
  svg.addEventListener('pointerdown', e => { if (!OV || e.pointerType === 'touch' || e.button) return; drag = { x: e.clientX, y: e.clientY, zx: Z.x, zy: Z.y, s: pt(e).s }; dragged = false; });
  window.addEventListener('pointermove', e => {
    if (!drag || !OV) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (!dragged && Math.hypot(dx, dy) < 4) return;
    dragged = true; hideTip(); svg.classList.add('panning'); Z.x = drag.zx + dx / drag.s; Z.y = drag.zy + dy / drag.s; applyZoom();
  });
  window.addEventListener('pointerup', () => { drag = null; svg.classList.remove('panning'); setTimeout(() => { dragged = false; }, 0); });
  svg.addEventListener('click', e => { if (dragged) { e.stopPropagation(); e.preventDefault(); } }, true);
  $('#zIn').onclick = () => zoomBy(1.5); $('#zOut').onclick = () => zoomBy(1 / 1.5); $('#zFit').onclick = () => { Z.k = 1; Z.x = 0; Z.y = 0; applyZoom(); };
}
const CHAIN_LEGEND = `<span><svg width="26" height="8"><path d="M1 4H25" stroke="#8F8A80" stroke-width="2.5"/></svg>sells to, revenue share disclosed</span>
  <span><svg width="26" height="8"><path d="M2 4H25" stroke="#8F8A80" stroke-width="2" stroke-dasharray="0.1 4" stroke-linecap="round"/></svg>sells to, strength estimated</span>
  <span><svg width="26" height="8"><path d="M1 4H25" stroke="#F7931E" stroke-width="1.8" stroke-dasharray="5 3"/></svg>invests in</span>
  <span><svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="#FFE2B8" stroke="#8F8A80" stroke-width="1.6"/></svg>you hold it</span>
  <span>thicker arrow = shock more likely to pass · bigger circle = bigger company</span>`;
function renderLegend() {
  const lg = $('#legend'); $('#zoom').classList.toggle('hide', !OV);
  if (G3.active) {
    lg.innerHTML = FAMILY.map(f => `<span><i style="width:11px;height:11px;border-radius:50%;display:inline-block;background:${f.color}"></i>${esc(f.name)}</span>`).join('') +
      `<span><i style="width:11px;height:11px;border-radius:50%;display:inline-block;background:${NEG}"></i>hit</span><span><i style="width:11px;height:11px;border-radius:50%;display:inline-block;background:${POS}"></i>lifted</span><span>tower height = market value · brighter = hit in more runs</span>`;
    return;
  }
  if (!OV) { lg.innerHTML = CHAIN_LEGEND; return; }
  const ring = '<span><svg width="16" height="16"><circle cx="8" cy="8" r="5" fill="#C9C4B9" stroke="#16171B" stroke-width="2.4"/></svg>you hold it</span>';
  if (S.res) {
    lg.innerHTML = `<span>Share of runs in which it was ${V().hit}<svg width="92" height="12" style="margin-left:4px">${[0.05, 0.25, 0.5, 0.75, 1].map((p, i) => `<rect x="${i * 18}" y="1" width="16" height="10" fill="${RED}" fill-opacity="${(0.22 + 0.78 * Math.sqrt(p)).toFixed(2)}"/>`).join('')}</svg>5% to 100%</span>
      <span><svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="${INK}"/></svg>where it starts</span><span><svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="#D9D5CD"/></svg>not ${V().hit}</span>${ring}`;
    return;
  }
  lg.innerHTML = FAMILY.map(f => `<button class="fam" data-f="${f.key}" aria-pressed="${S.fam === f.key}"><i style="background:${f.color}"></i>${esc(f.name)}</button>`).join('') +
    `<span><svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="#A39E94" fill-opacity=".32" stroke="#C9C4B9"/></svg>paler = no links found yet</span>${ring}
    <span class="seg">Circle size<button data-s="value" aria-pressed="${S.sizeBy === 'value'}">Market value</button><button data-s="links" aria-pressed="${S.sizeBy === 'links'}">Number of links</button></span>`;
  lg.querySelectorAll('.fam').forEach(b => b.onclick = () => { S.fam = S.fam === b.dataset.f ? null : b.dataset.f; paintOverview(); });
  lg.querySelectorAll('.seg button').forEach(b => b.onclick = () => { S.sizeBy = b.dataset.s; applyZoom(); renderLegend(); });
}
function openChain(id) { hideTip(); if (S.res) clearScenario(true); S.view = 'chain'; S.loops = false; S.sel = null; renderDetail(); setFocus(id); }
function buildMap() {
  const svg = $('#map'); svg.innerHTML = ''; NODE = {}; EDGE = {}; P = {}; OV = null;
  svg.setAttribute('viewBox', `0 0 ${MW} ${MH}`);
  const is3d = !S.loops && S.view === '3d';
  $('#gl').classList.toggle('hide', !is3d); svg.style.display = is3d ? 'none' : '';
  if (is3d) { if (G3.show($('#gl'))) G3.setScenario(S.res); renderLegend(); return; }
  G3.hide();
  if (!S.loops && S.view === 'all') return buildOverview(svg);
  COLS = S.res ? scenCols(S.res) : egoCols(S.focus, S.loops && S.loopList[S.loopIdx] ? S.loopList[S.loopIdx].nodes : []);
  const defs = el('defs', {}, svg), gl = el('g', {}, svg);
  COLS.forEach((c, i) => {
    const x = COLS.length === 1 ? MW / 2 : 130 + i * (MW - 250) / (COLS.length - 1), n = c.ids.length, top = 56, span = MH - 110;
    el('line', { x1: x, x2: x, y1: 40, y2: MH - 34, stroke: '#ECE8E0', 'stroke-width': 1 }, gl);
    el('text', { x, y: 26, 'text-anchor': 'middle', class: 'lane-t', style: /Company|Shock|Starts/.test(c.name) ? 'fill:#16171B' : '' }, gl).textContent = c.name;
    if (c.all.length > n) {
      const t = el('text', { x, y: MH - 14, 'text-anchor': 'middle', class: 'more-t', tabindex: 0, role: 'button' }, gl); t.textContent = `and ${c.all.length - n} others`;
      const open = e => { e.stopPropagation(); select('list', { title: c.name, ids: c.all }); };
      t.addEventListener('click', open); t.addEventListener('keydown', e => { if (e.key === 'Enter') open(e); });
    }
    c.ids.forEach((id, k) => { P[id] = { x, y: top + span * (k + 0.5) / n }; });
  });
  const gE = el('g', {}, svg); gShock = el('g', {}, svg); const gH = el('g', {}, svg); gParticles = el('g', {}, svg);
  const gN = el('g', {}, svg); gPulse = el('g', {}, svg); gFloat = el('g', {}, svg);
  const shown = [...SUPL, ...EQL].filter(l => P[l.from] && P[l.to]);
  shown.sort((a, b) => edgeW(b) - edgeW(a)).forEach(l => {
    const d = edgeD(l), w = edgeW(l), ms = Math.max(8, Math.min(13, w * 1.9));
    const mk = el('marker', { id: 'm-' + l.id.replace(/[^a-z0-9]/gi, '_'), viewBox: '0 0 10 10', refX: 8.5, refY: 5, markerUnits: 'userSpaceOnUse', markerWidth: ms, markerHeight: ms, orient: 'auto-start-reverse' }, defs);
    const mp = el('path', { d: 'M0,1 L10,5 L0,9 Z', fill: EDGE_BASE(l) }, mk);
    const p = el('path', { d, class: 'edge', stroke: EDGE_BASE(l), 'stroke-width': w.toFixed(2), 'marker-end': `url(#${mk.id})` }, gE);
    const dash = l.type === 'equity' ? '6 4' : !W.demand[l.id].disclosed ? '0.1 ' + Math.max(4, w * 1.7).toFixed(1) : null;
    if (dash) { p.setAttribute('stroke-dasharray', dash); if (l.type !== 'equity') p.setAttribute('stroke-linecap', 'round'); }
    const h = el('path', { d, class: 'ehit' }, gH);
    h.addEventListener('click', e => { e.stopPropagation(); select('link', l.id); });
    h.addEventListener('mousemove', e => showTip(e, linkTip(l))); h.addEventListener('mouseleave', hideTip);
    EDGE[l.id] = { p, mp, w, dash };
  });
  for (const id in P) {
    const { x, y } = P[id], r = R(id);
    const g = el('g', { class: 'node' + (N[id].inModel ? '' : ' muted'), transform: `translate(${x},${y})`, tabindex: 0, role: 'button', 'aria-label': N[id].name }, gN);
    el('circle', { r: r + 5, class: 'selring' }, g);
    const core = el('circle', { r, class: 'core', fill: '#fff', 'stroke-width': id === S.focus && !S.res ? 4 : 2.4 }, g);
    el('text', { class: 'tick', 'text-anchor': 'middle', y: r + 16 }, g).textContent = short(id);
    const bg = el('g', { transform: `translate(${-r - 8},0)`, opacity: 0 }, g);
    const br = el('rect', { class: 'badge-r', x: -56, y: -10, width: 56, height: 19 }, bg), bt = el('text', { class: 'badge-t', 'text-anchor': 'end', x: -6, y: 4 }, bg);
    g.addEventListener('click', e => { e.stopPropagation(); select('node', id); });
    g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select('node', id); } });
    g.addEventListener('mousemove', e => showTip(e, nodeTip(id))); g.addEventListener('mouseleave', hideTip);
    NODE[id] = { g, core, bg, br, bt };
  }
  paintMap(); renderLegend();
}
const nodeTip = id => `<b>${esc(N[id].name)}</b><div class="s">${N[id].cap ? 'Value ' + fB(N[id].cap) : 'No market value'}${N[id].sector ? ' · ' + esc(N[id].sector) : ''}</div><div class="s">Click for details</div>`;
const verb = l => ({ supply: 'sells to', licensing: 'licenses to', equity: 'invests in', partnership: 'partners with', acquisition: 'acquires', financing: 'finances' }[l.type] || 'is linked to');
const linkTip = l => `<b>${esc(short(l.from))} ${verb(l)} ${esc(short(l.to))}</b><div class="s">${esc(l.label || '')}</div><div class="s">Click for the evidence</div>`;
function showTip(e, html) {
  const t = $('#tip'); t.innerHTML = html; t.classList.remove('hide');
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + t.offsetWidth > innerWidth - 8) x = e.clientX - t.offsetWidth - 14;
  if (y + t.offsetHeight > innerHeight - 8) y = e.clientY - t.offsetHeight - 14;
  t.style.left = x + 'px'; t.style.top = y + 'px';
}
function hideTip() { $('#tip').classList.add('hide'); }

function paintMap() {
  if (OV) return paintOverview();
  if (G3.active) return G3.refresh();
  const loop = S.loops ? S.loopList[S.loopIdx] : null, scen = !!S.shown, selL = new Set(), selN = new Set();
  const addL = l => { selL.add(l.id); selN.add(l.from); selN.add(l.to); };
  const focusing = S.sel && S.sel.kind !== 'list';
  if (S.sel?.kind === 'node') { selN.add(S.sel.id); (linksOf[S.sel.id] || []).forEach(addL); }
  if (S.sel?.kind === 'link') addL(LK[S.sel.id]);
  for (const id in NODE) {
    const n = NODE[id];
    n.g.classList.toggle('dim', loop ? !loop.nodes.includes(id) : focusing ? !selN.has(id) : false);
    n.g.classList.toggle('sel', S.sel?.kind === 'node' && S.sel.id === id);
    const p = scen ? (S.shown[id] || 0) : 0, origin = scen && S.res.sc.origins.includes(id);
    const badge = txt => { n.bg.setAttribute('opacity', 1); n.bt.textContent = txt; const w = txt.length * 7.4 + 12; n.br.setAttribute('x', -w); n.br.setAttribute('width', w); };
    const g = origin ? gOf(id) : null;
    n.core.setAttribute('fill-opacity', g ? (g.direct ? 0.75 : 1) : p > 0 ? (0.12 + 0.7 * Math.sqrt(p)).toFixed(2) : 1);
    if (g) {
      n.core.setAttribute('fill', g.direct ? colOf(g.dir) : S.pf.has(id) ? '#FFE2B8' : '#fff'); n.core.setAttribute('stroke', colOf(g.dir));
      n.br.style.stroke = colOf(g.dir); n.bt.style.fill = colOf(g.dir);
      badge((g.dir > 0 ? '+' : '-') + fP(g.severity, 0) + (g.direct ? '' : g.kind === 'demand' ? ' spend' : ' output'));
    } else if (p > 0) {
      const c = nodeCol(id); n.core.setAttribute('fill', c); n.core.setAttribute('stroke', c); n.br.style.stroke = c; n.bt.style.fill = c;
      badge(fP(p, 0) + (S.res.byId[id].sgn > 0 ? ' lifted' : ' hit'));
    } else {
      n.core.setAttribute('fill', S.pf.has(id) ? '#FFE2B8' : '#fff');
      n.core.setAttribute('stroke', id === S.focus && !scen ? INK : '#A8A298');
      n.bg.setAttribute('opacity', 0);
    }
  }
  for (const id in EDGE) {
    const l = LK[id], e = EDGE[id];
    let color = EDGE_BASE(l), op = l.type === 'equity' ? 0.75 : 1, w = e.w, flow = false, dash = e.dash;
    if (loop) { if (loop.links.includes(id)) { color = ORANGE; w = Math.max(2.6, e.w); flow = true; dash = l.type === 'equity' ? '6 4' : '10 6'; op = 1; } else op = 0.07; }
    else if (scen && S.hot.has(id)) { color = linkCol(id); op = 1; }
    else if (focusing) { if (selL.has(id)) { color = l.type === 'equity' ? ORANGE : INK; op = 1; } else op = 0.08; }
    else if (scen) op = 0.25;
    e.p.setAttribute('stroke', color); e.mp.setAttribute('fill', color); e.p.setAttribute('stroke-width', w.toFixed(2)); e.p.style.opacity = op;
    if (dash) e.p.setAttribute('stroke-dasharray', dash); else e.p.removeAttribute('stroke-dasharray');
    e.p.classList.toggle('flow', flow);
  }
}
function setFocus(id) { if (!N[id]) return; S.focus = id; S.loopList = findLoops(id); S.loopIdx = 0; buildMap(); renderCap(); renderPortfolio(); }

// ============================================================
//  Money loops through the chosen company (buyer pays seller, investor funds investee)
// ============================================================
function findLoops(f) {
  const out = [], seen = new Set();
  const next = v => [...(byBuyer[v] || []).map(l => [l.from, l.id]), ...(eqByInvestor[v] || []).map(l => [l.to, l.id])];
  const go = (v, nodes, links) => {
    if (out.length >= 40) return;
    for (const [w, lid] of next(v)) {
      if (w === f && nodes.length > 1) { const key = [...nodes].sort().join('|'); if (!seen.has(key) && links.concat(lid).some(x => LK[x].type === 'equity')) { seen.add(key); out.push({ nodes: [...nodes], links: [...links, lid] }); } }
      else if (!nodes.includes(w) && nodes.length < 4) go(w, [...nodes, w], [...links, lid]);
    }
  };
  go(f, [f], []);
  return out.sort((a, b) => a.nodes.length - b.nodes.length).slice(0, 12);
}
const loopText = lp => lp.links.map((lid, i) => { const a = lp.nodes[i], b = lp.nodes[(i + 1) % lp.nodes.length]; return `${short(a)} ${LK[lid].type === 'equity' ? 'invests in' : 'pays'} ${short(b)}`; }).join(', then ') + '.';
function setView(v) { S.loops = false; S.view = v; S.sel = null; renderDetail(); buildMap(); renderCap(); renderPortfolio(); }
function setLoops(on) {
  S.loops = on;
  if (on) { clearScenario(true); S.sel = null; renderDetail(); }
  buildMap(); renderCap();
}

// ============================================================
//  Caption above the map
// ============================================================
function renderCap() {
  const c = $('#cap');
  const mode = S.loops ? 'loops' : S.view;
  $$('.views button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.mode === mode)));
  $('#nLoops').textContent = S.loopList.length;
  if (S.loops) {
    const lp = S.loopList[S.loopIdx];
    c.innerHTML = lp ? `<div class="tx"><span class="lbl" style="color:var(--accent-ink)">Money loop ${S.loopIdx + 1} of ${S.loopList.length} through ${esc(short(S.focus))}</span><h1>${lp.nodes.map(short).map(esc).join(' &rarr; ')} &rarr; ${esc(short(S.focus))}</h1><p>${esc(loopText(lp))}</p></div>
      <div class="acts"><button class="btn" id="lpPrev">Prev</button><button class="btn" id="lpNext">Next</button></div>`
      : `<div class="tx"><span class="lbl">Money loops</span><h1>No money loop runs through ${esc(short(S.focus))}</h1><p>A loop needs an investment and a purchase that lead back to the same company. Try OpenAI or Nvidia.</p></div>`;
    if (lp) { const step = d => { S.loopIdx = (S.loopIdx + S.loopList.length + d) % S.loopList.length; buildMap(); renderCap(); }; $('#lpPrev').onclick = () => step(-1); $('#lpNext').onclick = () => step(1); }
    return;
  }
  if (S.res) {
    const net = S.res.rows.filter(r => S.revealed.has(r.id)).reduce((s, r) => s + r.sgn * (r.mcar || 0), 0), risk = Math.abs(net);
    c.innerHTML = `<div class="tx"><span class="lbl" style="color:var(--danger)">${S.animating ? (S.hop ? `Hop ${S.hop} of ${S.nHop}` : 'Shock starts') : `${S.res.runs.toLocaleString()} simulated runs`}</span><h1>${esc(describe(S.res.sc))}</h1><p>${esc(S.cap)}</p><div class="pips">${Array.from({ length: S.nHop }, (_, i) => `<i class="${i < S.hop ? 'on' : ''}"></i>`).join('')}</div></div>
      ${S.animating ? '' : `<div class="acts"><button class="btn" id="swapView">${S.view === 'all' ? 'See it hop by hop' : 'See it on the whole market'}</button></div>`}
      <div class="kp"><span class="lbl">${isMixed() ? 'Net market cap change' : V().Risk}</span><b style="color:${colOf(net)}">${net >= 0 && risk ? '+' : '-'}${fB(risk)}</b></div>`;
    if ($('#swapView')) $('#swapView').onclick = () => setView(S.view === 'all' ? 'chain' : 'all');
    return;
  }
  if (S.view === '3d') {
    c.innerHTML = `<div class="tx"><span class="lbl">3D view, for presenting</span><h1>The market as a planet</h1>
      <p>Each continent is a sector, each tower is a company and its height is its market value. Lines show who sells to whom. Run a scenario to watch it spread, or press F for full screen.</p></div>`;
    return;
  }
  if (S.view === 'all') {
    c.innerHTML = `<div class="tx"><span class="lbl">All companies</span><h1>${OV_IDS.length.toLocaleString()} companies, ${OV_LINKS.length} supply links</h1>
      <p>Each dot is a company, each line is one company selling to another. Hover to trace its links, click to open its supply chain. Most connected: ${HUBS.map(id => `<button class="hub" data-id="${esc(id)}">${esc(short(id))}</button>`).join(' ')}</p></div>
      <div class="find"><input id="focusIn" placeholder="Search any company" aria-label="Search a company" spellcheck="false" autocomplete="off"></div>`;
    $$('#cap .hub').forEach(b => b.onclick = () => openChain(b.dataset.id));
  } else {
    c.innerHTML = `<div class="tx"><span class="lbl">Supply chain of</span><h1>${esc(N[S.focus].name)}</h1>
      <p>Suppliers on the left, customers on the right. Click a company or an arrow for the evidence.</p></div>
      <div class="find"><input id="focusIn" placeholder="Search another company" aria-label="Search a company" spellcheck="false" autocomplete="off"></div>`;
  }
  attachSearch($('#focusIn'), id => openChain(id));
}
// ---------- company search with suggestions ----------
function searchCompanies(q) {
  q = q.trim().toLowerCase(); if (!q) return [];
  const pool = G.nodes.filter(n => n.sp || linksOf[n.id]), tk = n => (n.sp && n.ticker || '').toLowerCase().split(/[;,]/);
  const score = n => { const nm = n.name.toLowerCase(), t = tk(n); return t.includes(q) ? 0 : nm.startsWith(q) ? 1 : t.some(x => x.startsWith(q)) ? 2 : nm.split(/[\s&.-]+/).some(w => w.startsWith(q)) ? 3 : nm.includes(q) ? 4 : 9; };
  return pool.map(n => [score(n), n]).filter(x => x[0] < 9).sort((a, b) => a[0] - b[0] || (b[1].cap || 0) - (a[1].cap || 0)).slice(0, 8).map(x => x[1]);
}
function attachSearch(inp, onPick) {
  const box = document.createElement('div'); box.className = 'ac hide'; inp.parentNode.appendChild(box);
  let list = [], at = 0;
  const pick = n => { inp.value = ''; box.classList.add('hide'); inp.blur(); onPick(n.id); };
  const draw = () => {
    list = searchCompanies(inp.value); at = Math.min(at, Math.max(0, list.length - 1));
    box.classList.toggle('hide', !inp.value.trim());
    box.innerHTML = list.map((n, i) => `<button type="button" class="${i === at ? 'on' : ''}" data-i="${i}"><b>${esc(n.sp && n.ticker ? n.ticker.split(/[;,]/)[0] : '·')}</b><span>${esc(n.name)}</span><em>${n.cap ? fB(n.cap) : ''}${linksOf[n.id] ? '' : ' no links yet'}</em></button>`).join('') || '<p>No company matches.</p>';
    box.querySelectorAll('button').forEach(b => b.onmousedown = e => { e.preventDefault(); pick(list[+b.dataset.i]); });
  };
  inp.oninput = () => { at = 0; draw(); };
  inp.onfocus = draw;
  inp.onblur = () => setTimeout(() => box.classList.add('hide'), 120);
  inp.onkeydown = e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); at = Math.min(list.length - 1, at + 1); draw(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); at = Math.max(0, at - 1); draw(); }
    else if (e.key === 'Enter') { e.preventDefault(); if (list[at]) pick(list[at]); }
    else if (e.key === 'Escape') { inp.value = ''; box.classList.add('hide'); inp.blur(); e.stopPropagation(); }
  };
}
const NAME_ID = {}; for (const n of G.nodes) { NAME_ID[n.name.toLowerCase()] = n.id; if (n.sp && n.ticker) NAME_ID[n.ticker.toLowerCase()] = n.id; }
function resolve(v) {
  v = v.trim().toLowerCase(); if (!v) return null;
  return NAME_ID[v] || (N[v] ? v : null) || G.nodes.find(n => linksOf[n.id] && n.name.toLowerCase().startsWith(v))?.id || G.nodes.find(n => linksOf[n.id] && n.name.toLowerCase().includes(v))?.id || null;
}

// ============================================================
//  Selection + detail
// ============================================================
function select(kind, id) { S.sel = kind ? { kind, id } : null; renderDetail(); if (OV) ovFocus(); else paintMap(); }
const lkRow = l => `<button class="lk" data-link="${esc(l.id)}">${esc(short(l.from))} ${verb(l)} ${esc(short(l.to))}<span>${l.role === 'propagates' ? 'p ' + W.demand[l.id].p.toFixed(2) : l.stake ? fB(l.stake) : esc(l.type)}</span></button>`;
const pLine = (w, label) => `<dt>${label}</dt><dd><span class="mono">${w.p.toFixed(3)}</span> <span class="note">= ${w.base.toFixed(2)} (${esc(w.baseFrom)}) &times; ${w.size.toFixed(2)} size${w.sized ? '' : ' (no value, so 1)'} &times; ${w.conf.toFixed(1)} confidence</span></dd>`;
let evLoading = null;
function loadEvidence() { return evLoading ||= new Promise(res => { if (window.EVIDENCE) return res(); const s = document.createElement('script'); s.src = 'data/evidence.js'; s.onload = res; s.onerror = res; document.head.appendChild(s); }); }
function renderDetail() {
  const d = $('#detail');
  if (!S.sel) { d.classList.add('hide'); d.innerHTML = ''; return; }
  let h = '';
  if (S.sel.kind === 'list') {
    const { title, ids } = S.sel.id;
    h = `<div class="dh"><div><span class="lbl">${esc(short(S.focus))}</span><h2>${esc(title)} (${ids.length})</h2></div><button class="x" id="dX" aria-label="Close">&times;</button></div>
      <p class="note">Strongest link first. Click a company to open its supply chain.</p>
      ${ids.map(id => `<button class="lk" data-open="${esc(id)}">${esc(N[id].name)}<span>${N[id].cap ? fB(N[id].cap) : ''}</span></button>`).join('')}`;
  } else if (S.sel.kind === 'node') {
    const id = S.sel.id, n = N[id], row = S.res && !S.animating ? S.res.byId[id] : null, ls = (linksOf[id] || []).slice().sort((a, b) => (b.role === 'propagates') - (a.role === 'propagates') || (b.stake || 0) - (a.stake || 0));
    h = `<div class="dh"><div><span class="lbl">${n.sp ? esc(n.ticker) + ' · S&amp;P 500' : esc(n.type === 'sp500_company' ? '' : (n.region || 'Counterparty'))}</span><h2>${esc(n.name)}</h2></div><button class="x" id="dX" aria-label="Close">&times;</button></div>
      <dl class="kv"><dt>Value</dt><dd>${n.cap ? fB(n.cap) + ` <span class="note">${n.capBasis === 'market_cap' ? 'market cap, ' + esc(n.capAsOf) : 'private valuation'}</span>` : 'n/a <span class="note">no market value in the data</span>'}</dd>
      ${n.rev ? `<dt>Revenue</dt><dd>${fB(n.rev)} <span class="note">${esc(n.revEnd || '')}</span></dd>` : ''}
      ${n.sector ? `<dt>Sector</dt><dd>${esc(n.sector)}</dd>` : ''}
      ${row ? `<dt>In this scenario</dt><dd style="color:${colOf(row.sgn)}">${row.sgn > 0 ? 'lifted' : 'hit'} in ${fP(row.p)} of runs, predicted change ${rs(row)}${fP(row.drop)}${row.mcar != null ? ', ' + rs(row) + fB(row.mcar) : ''}</dd>` : ''}
      ${n.inModel ? '' : '<dt>Model</dt><dd>No modelled relationships yet. This does not mean it is safe.</dd>'}</dl>
      ${id !== S.focus || S.res || S.view === 'all' ? `<button class="btn" id="dFocus">Open the supply chain of ${esc(short(id))}</button>` : ''}
      <div class="sub"><span class="lbl">Links (${ls.length})</span><span class="note">p = chance a shock passes</span></div>${ls.slice(0, 40).map(lkRow).join('')}${ls.length > 40 ? `<p class="note">${ls.length - 40} more in Sources.</p>` : ''}`;
  } else {
    const l = LK[S.sel.id], prop = l.role === 'propagates', tag = confOf(l), ev = window.EVIDENCE?.[l.id];
    h = `<div class="dh"><div><span class="lbl">${esc(verb(l))}</span><h2>${esc(short(l.from))} &rarr; ${esc(short(l.to))}</h2></div><button class="x" id="dX" aria-label="Close">&times;</button></div>
      <dl class="kv"><dt>Deal</dt><dd>${esc(l.label || l.type)}</dd>
      ${l.stake ? `<dt>Stake value</dt><dd>${fB(l.stake)}</dd>` : ''}
      ${prop ? pLine(W.demand[l.id], 'If the buyer cuts') + pLine(W.supply[l.id], 'If the seller fails') : '<dt>In the model</dt><dd>' + (l.stake ? 'Stake is written down with the investee. It does not pass shocks on.' : 'Shown for context only. It does not pass shocks on.') + '</dd>'}
      <dt>Confidence</dt><dd>${tagHTML(tag)} <span class="note">${esc(CONF_TXT[tag])}</span></dd></dl>
      ${l.note && prop ? `<p class="note"><b>Weight note:</b> ${esc(l.note)}</p>` : ''}
      <div class="sub"><span class="lbl">Evidence</span></div>
      ${ev ? ev.map(e => `<div class="quote">${esc(e.q || 'No quote recorded.')}<small>${e.kind === 'paraphrase' ? 'Paraphrase' : 'Quoted'}${e.doc ? ' · ' + esc(e.doc) : ''}${e.filed ? ' · ' + esc(e.filed) : ''}${e.by && N[e.by] ? ' · filed by ' + esc(short(e.by)) : ''}${e.url ? ` · <a href="${esc(e.url)}" target="_blank" rel="noopener">open document</a>` : ''}</small></div>`).join('') : '<p class="note">' + (window.EVIDENCE ? 'No evidence recorded for this link.' : 'Loading evidence…') + '</p>'}`;
    if (!window.EVIDENCE) loadEvidence().then(() => { if (S.sel?.kind === 'link' && S.sel.id === l.id) renderDetail(); });
  }
  d.innerHTML = h; d.classList.remove('hide');
  $('#dX').onclick = () => select(null);
  d.querySelectorAll('.lk[data-link]').forEach(b => b.onclick = () => select('link', b.dataset.link));
  d.querySelectorAll('.lk[data-open]').forEach(b => b.onclick = () => { clearScenario(true); openChain(b.dataset.open); });
  if ($('#dFocus')) $('#dFocus').onclick = () => { const id = S.sel.id; clearScenario(true); openChain(id); };
}

// ============================================================
//  Portfolio
// ============================================================
function renderPortfolio() {
  const hold = [...S.pf], f = S.focus, s = egoSets(f);
  const up = hold.filter(id => id === f || s.sup1.includes(id) || s.sup2.includes(id) || (eqByInvestee[f] || []).some(l => l.from === id)), dn = hold.filter(id => !up.includes(id) && (s.cust1.includes(id) || s.cust2.includes(id)));
  const k = up.length + dn.length, how = !dn.length ? `${short(f)} paying its bills` : !up.length ? `${short(f)} delivering` : `${short(f)}, as its suppliers or customers`;
  $('#pfBlk').innerHTML = `<div class="lbl"><span>Your portfolio · ${hold.length} held</span>${hold.length ? '<button class="linkbtn" id="pfClear">Clear all</button>' : ''}</div>
    <div class="chips" id="chips">${hold.map(id => `<button class="chip" data-id="${esc(id)}" aria-pressed="true" title="Remove ${esc(N[id].name)}">${esc(tick(id))} &times;</button>`).join('')}<span class="find"><input id="pfAdd" placeholder="+ search a stock" aria-label="Add a stock" spellcheck="false" autocomplete="off"></span></div>
    ${S.res ? '' : `<p class="headline">${hold.length ? `<em>${k === hold.length && k > 1 ? 'All ' + k : k + ' of your ' + hold.length}</em> ${k === hold.length && k > 1 ? 'of your holdings depend' : 'holding' + (hold.length === 1 ? '' : 's') + ' depend' + (k === 1 ? 's' : '')} on ${esc(how)}.` : 'Add the stocks you hold.'}</p>`}`;
  const again = () => { renderPortfolio(); paintMap(); renderReport(); };
  $$('#chips .chip').forEach(b => b.onclick = () => { S.pf.delete(b.dataset.id); again(); });
  attachSearch($('#pfAdd'), id => { S.pf.add(id); again(); setTimeout(() => $('#pfAdd')?.focus(), 0); });
  if ($('#pfClear')) $('#pfClear').onclick = () => { S.pf.clear(); again(); };
}

// ============================================================
//  Scenario
// ============================================================
function renderInterp() {
  $('#presets').classList.toggle('hide', !!S.sc);
  const b = $('#interp'); if (!S.sc) { b.classList.add('hide'); return; }
  const sc = S.sc;
  b.classList.remove('hide');
  if (sc.groups) {
    const what = g => (g.direct ? (g.dir > 0 ? 'gain' : 'lose') + ' value, then ' : '') + (g.kind === 'demand' ? (g.dir > 0 ? 'buy more' : 'buy less') : (g.dir > 0 ? 'deliver more' : 'deliver less'));
    b.innerHTML = `<span class="lbl">The AI's assumption, not a finding</span>
      ${sc.groups.map(g => `<div class="grp"><b style="color:${colOf(g.dir)}">${g.dir > 0 ? '+' : '-'}${fP(g.severity, 0)}</b><div><strong>${esc(g.label || 'Group')}</strong> <span class="note">${esc(what(g))}</span><div class="row" style="margin-top:3px">${g.origins.map(id => `<span class="tag DISCLOSED">${esc(tick(id))}</span>`).join('')}</div></div></div>`).join('')}
      ${sc.notes?.length ? `<div class="why">${esc(sc.notes.join('; '))}</div>` : ''}
      <div class="why">Who is affected first, and by how much, is the AI's reading of the event. Everything after that comes from the links.</div>`;
    return;
  }
  b.innerHTML = `<span class="lbl">AI interpretation. Edit to rerun.</span>
    <div class="row">${sc.origins.map(id => `<span class="tag DISCLOSED" style="font-size:11px;padding:3px 6px">${esc(tick(id))}</span>`).join('')}</div>
    <div class="row"><select id="iKind" aria-label="Type">${[['demand', -1, 'buy less'], ['demand', 1, 'buy more'], ['supply', -1, 'deliver less'], ['supply', 1, 'deliver more']].map(([k, d, t]) => `<option value="${k}:${d}"${sc.kind === k && (sc.dir || -1) === d ? ' selected' : ''}>${t}</option>`).join('')}</select>
    <input type="range" id="iSev" min="5" max="100" step="5" value="${Math.round(sc.severity * 100)}" aria-label="Severity"><output>${fP(sc.severity, 0)}</output></div>
    ${sc.notes?.length ? `<div class="why">${esc(sc.notes.join('; '))}</div>` : ''}`;
  const edit = () => { const [k, d] = $('#iKind').value.split(':'); S.sc = { ...sc, kind: k, dir: +d, severity: +$('#iSev').value / 100, notes: ['edited by you'] }; S.sc.text = describe(S.sc); $('#sText').value = S.sc.text; showInstant(); };
  $('#iKind').onchange = edit; $('#iSev').onchange = edit;
  $('#iSev').oninput = e => { e.target.nextElementSibling.textContent = e.target.value + '%'; };
}
async function runFromText(text, preset) {
  text = (text || '').trim(); if (!text) { $('#sText').focus(); return; }
  $('#sText').value = text; $('#sText').blur();
  const t0 = performance.now();
  S.sc = preset ? { text, ...preset, notes: [preset.groups ? 'preset scenario: the starting companies and sizes are an illustrative assumption' : 'preset scenario'] } : await parseSmart(text);
  S.parseMs = performance.now() - t0; if (!S.sc.error && !S.sc.groups) S.sc.dir = S.sc.dir > 0 ? 1 : -1;
  if (S.sc.error) { const msg = S.sc.error; S.sc = null; renderInterp(); const b = $('#interp'); b.classList.remove('hide'); b.innerHTML = `<span class="lbl" style="color:var(--danger)">Could not read that scenario</span><div class="why" style="color:var(--ink);font-size:13px">${esc(msg)}</div>`; $('#presets').classList.remove('hide'); return; }
  renderInterp(); await play();
}
function prepare() {
  S.res = simulate(S.sc); setTone();
  S.loops = false; S.sel = null; renderDetail();
  S.shown = {}; S.hot = new Set(); S.revealed = new Set(); S.hop = 0;
  buildMap();
  S.nHop = Math.max(1, ...S.res.rows.filter(r => P[r.id]).map(r => r.hop));
}
async function play() {
  if (S.view !== '3d') S.view = 'chain';
  prepare();
  if (S.view === '3d') { S.animToken++; settle(); S.cap = 'Playing on the 3D view. The full report is on the right.'; renderCap(); $('#repBlk').scrollIntoView({ behavior: 'smooth', block: 'nearest' }); return; }
  const res = S.res, my = ++S.animToken, dead = () => my !== S.animToken, mixed = res.groups.length > 1 || res.groups[0].direct;
  const hopOf = id => res.sc.origins.includes(id) && !res.byId[id] ? 0 : res.byId[id]?.hop ?? 99;
  S.animating = true; S.cap = `${res.runs.toLocaleString()} runs simulated in ${Math.round(res.ms)} ms. Replaying the average run.`;
  renderCap(); renderPortfolio(); renderReport();
  $('#repBlk').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  res.sc.origins.forEach(blast);
  const reveal = (rows) => rows.forEach((r, i) => setTimeout(() => {
    if (dead()) return;
    S.shown[r.id] = r.p; S.revealed.add(r.id); paintMap();
    impact(r.id, colOf(r.sgn)); floater(r.id, rs(r) + (r.mcar != null ? fB(r.mcar) : fP(r.drop)), colOf(r.sgn)); strike(r.id);
    renderReport(); renderCap();
  }, i * 80));
  const first = res.rows.filter(r => r.hop === 0);
  if (first.length) { S.cap = 'First, the event changes the value of the companies it touches directly.'; renderCap(); reveal(first); }
  await sleep(first.length ? 1300 : 900);
  for (let k = 1; k <= S.nHop; k++) {
    if (dead()) return;
    S.hop = k;
    const g0 = res.groups[0], who = g0.kind === 'demand' ? 'supplier' : 'customer', pos = g0.dir > 0;
    S.cap = mixed ? (k === 1 ? 'Then it spreads: each trading partner is reached with probability p, its link strength.' : 'It moves one more step along the chain and fades 0.6x per hop.')
      : k === 1 ? `Each ${who} is ${pos ? 'lifted' : 'hit'} with probability p, its link strength.` : `${pos ? 'Lifted' : 'Hit'} ${who}s ${g0.kind === 'demand' ? (pos ? 'raise' : 'cut') + ' their own orders' : 'deliver ' + (pos ? 'more' : 'less')}. The effect fades 0.6x per hop.`;
    renderCap();
    const hit = res.rows.filter(r => P[r.id] && r.hop === k), ids = new Set(hit.map(r => r.id));
    const fire = Object.keys(EDGE).filter(id => { const l = LK[id]; return l.role === 'propagates' && res.pass[id] && ((ids.has(l.from) && hopOf(l.to) < k) || (ids.has(l.to) && hopOf(l.from) < k)); });
    for (const id of fire) { const back = ids.has(LK[id].from); burn(id, back, 700, linkCol(id)); particle(id, back, Math.min(1, 0.25 + res.pass[id] / res.runs), linkCol(id), 700); }
    await sleep(720);
    if (dead()) return;
    fire.forEach(id => S.hot.add(id));
    reveal(hit);
    await sleep(Math.max(600, hit.length * 80 + 420));
  }
  if (dead()) return;
  settle();
}
function settle() {
  const res = S.res;
  S.animating = false; S.hop = S.nHop; S.shown = Object.fromEntries(res.rows.map(r => [r.id, r.p])); S.revealed = new Set(res.rows.map(r => r.id));
  S.hot = new Set(Object.keys(EDGE).filter(id => res.pass[id]));
  const far = res.rows.filter(r => r.p >= 0.05).length;
  S.cap = res.rows.length ? `${far} compan${far === 1 ? 'y is' : 'ies are'} ${V().hit} in at least 5% of runs. The full report is on the right.` : 'No company in the data is linked to this shock.';
  renderCap(); paintMap(); renderPortfolio(); renderReport(); renderDetail();
}
function showInstant() { S.animToken++; prepare(); settle(); renderInterp(); }
function clearScenario(quiet) {
  S.animToken++; S.animating = false; S.res = null; S.sc = null; setTone(); S.shown = null; S.hot = new Set(); S.hop = 0; S.revealed = new Set();
  $('#sText').value = ''; renderInterp(); renderReport();
  if (!quiet) { buildMap(); renderCap(); renderPortfolio(); renderDetail(); }
}

// ============================================================
//  Report
// ============================================================
function renderReport() {
  const b = $('#repBlk'); if (!S.res) { b.classList.add('hide'); b.innerHTML = ''; return; }
  const res = S.res, run = S.animating, mixed = res.sc.dir === 0, v = V(), rows = res.rows.filter(r => S.revealed.has(r.id));
  const sum = (rs_, f = () => true) => rs_.filter(f).reduce((s, r) => s + r.sgn * (r.mcar || 0), 0), money = x => Math.abs(x) < 0.005 ? '$0' : (x >= 0 ? '+' : '-') + fB(Math.abs(x));
  const held = rows.filter(r => S.pf.has(r.id)), pfNet = sum(held), allNet = sum(rows), gain = sum(rows, r => r.sgn > 0), loss = sum(rows, r => r.sgn < 0);
  const likely = held.filter(r => r.p >= 0.5).length, n = S.pf.size, top = rows.slice(0, 25);
  const pfStake = res.stakes.filter(s => S.pf.has(s.id)).reduce((a, s) => a + s.sgn * s.usd, 0);
  b.classList.remove('hide');
  b.innerHTML = `<div class="rep-h"><span class="lbl" style="color:${mixed ? 'var(--ink)' : 'var(--danger)'}">Report${run ? ' · running' : ''}</span><div style="display:flex;gap:6px"><button class="btn" id="rReplay">Replay</button><button class="btn ghost" id="rClear">Clear</button></div></div>
    <div class="rep-t">${esc(describe(res.sc))}</div>
    <div class="kpis${mixed ? ' mixed' : ''}">${mixed
      ? `<div><span class="lbl">Your holdings, net</span><b style="color:${colOf(pfNet)}">${money(pfNet)}</b></div><div><span class="lbl">Gains</span><b style="color:${POS}">${money(gain)}</b></div><div><span class="lbl">Losses</span><b style="color:${NEG}">${loss ? money(loss) : '-$0.00B'}</b></div>`
      : `<div><span class="lbl">Your holdings</span><b>${money(pfNet)}</b></div><div><span class="lbl">All companies</span><b>${money(allNet)}</b></div><div><span class="lbl">Companies ${v.hit}</span><b>${rows.length}</b></div>`}</div>
    ${run ? '' : `<p class="lead">Across <b>${res.runs.toLocaleString()}</b> simulated runs, your ${n} holding${n === 1 ? '' : 's'} ${mixed ? 'change by a net' : v.lose + ' an expected'} <b>${mixed ? money(pfNet) : fB(Math.abs(pfNet))}</b> of market value. ${likely} of them ${likely === 1 ? 'is' : 'are'} ${v.hit} in more than half the runs.${mixed || isUp() ? ' Upside estimates are weaker than downside ones: extra spending does not lift a supplier as reliably as a cut hurts it.' : ''}</p>`}
    <div class="sub"><span class="lbl">${v.Risk}, by company</span><span class="note">P(${v.hit}) · ${v.move} · value</span></div>
    <table class="rt"><tbody>${top.map(r => { const path = res.pathOf(r.id), c = colOf(r.sgn); return `<tr data-node="${esc(r.id)}"><td class="nm"><b class="${S.pf.has(r.id) ? 'own' : ''}">${esc(tick(r.id))}</b><div>${r.hop === 0 ? 'affected directly (AI assumption)' : path.length > 1 ? 'via ' + path.slice(0, -1).reverse().map(short).map(esc).join(' &lsaquo; ') : ''} ${r.viaLink && r.hop ? tagHTML(confOf(LK[r.viaLink])) : ''}</div><div class="pb"><i style="width:${Math.max(1, r.p * 100)}%;background:${c}"></i></div></td>
      <td class="num">${fP(r.p, 0)}</td><td class="num p" style="color:${c}">${rs(r)}${fP(r.drop, r.drop < 0.01 ? 2 : 1)}</td><td class="num">${r.mcar != null ? fB(r.mcar) : 'n/a'}</td></tr>`; }).join('') || `<tr><td class="note">${run ? 'Waiting for the first company.' : 'No company was affected.'}</td></tr>`}</tbody></table>
    ${!run && rows.length > top.length ? `<p class="note">${rows.length - top.length} more companies with smaller exposure.</p>` : ''}
    ${!run && res.stakes.length ? `<div class="sub"><span class="lbl">${v.stakes}</span><span class="note">stake &times; investee's ${v.move}</span></div><table class="rt"><tbody>${res.stakes.slice(0, 6).map(s => `<tr data-node="${esc(s.id)}"><td class="nm"><b class="${S.pf.has(s.id) ? 'own' : ''}">${esc(tick(s.id))}</b><div>stake in ${esc([...new Set(s.in)].slice(0, 3).map(short).join(', '))}</div></td><td class="num p" style="color:${colOf(s.sgn)}">${s.sgn > 0 ? '+' : '-'}${fB(s.usd)}</td></tr>`).join('')}</tbody></table>${pfStake ? `<p class="note">Your holdings' share of this: ${money(pfStake)}.</p>` : ''}` : ''}
    ${run ? '' : `<div class="sub"><span class="lbl">Summary</span></div><p class="summary">${explain(res)}</p>
    <details class="trace"><summary>How the AI got this<span class="tag DISCLOSED">RUN IN YOUR BROWSER</span></summary>${trace(res).map(s => `<div class="call"><div class="f">${esc(s.fn)}<span>${esc(s.ms)}</span></div><pre>${esc(s.out)}</pre></div>`).join('')}</details>
    <p class="note" style="margin:12px 0 0">The AI only picks where the effect starts and how big it is. It never picks who is affected after that. Links without a disclosed revenue share count equally, shocks are treated as independent, and only signed deals are seen. Not investment advice.</p>`}`;
  $('#rReplay').onclick = () => play(); $('#rClear').onclick = () => clearScenario();
  b.querySelectorAll('tr[data-node]').forEach(tr => tr.onclick = () => select('node', tr.dataset.node));
}
function explain(res) {
  const r = res.rows; if (!r.length) return 'No company in the data is linked to this scenario, so nothing was affected.';
  const mixed = res.sc.dir === 0, v = V(), likely = [...r].filter(x => x.hop > 0).sort((a, b) => b.p - a.p)[0] || r[0], big = r[0], far = r.filter(x => x.hop >= 2).sort((a, b) => (b.mcar || 0) - (a.mcar || 0))[0];
  let s = mixed ? `If ${esc(describe(res.sc))}, the model expects <b>+${fB(res.gain)}</b> of gains and <b>-${fB(res.loss)}</b> of losses in market value across ${r.length} companies. `
    : `If ${esc(describe(res.sc))}, the expected ${isUp() ? 'gain' : 'loss'} is <b>${fB(res.total)}</b> of market value across ${r.length} companies. `;
  s += `${esc(N[likely.id].name)} is the most likely to be ${likely.sgn > 0 ? 'lifted' : 'hit'} through its links (<b>${fP(likely.p, 0)}</b> of runs). `;
  if (big.id !== likely.id && big.mcar) s += `${esc(N[big.id].name)} has the largest change in value (<b>${rs(big)}${fB(big.mcar)}</b>). `;
  if (far) s += `The effect reaches ${esc(N[far.id].name)} ${far.hop} hops away, through ${esc(res.pathOf(far.id).slice(1, -1).map(short).join(' and ') || 'its trading partners')}. `;
  if (res.stakes[0]) s += `Separately, ${esc(N[res.stakes[0].id].name)} would mark its stake ${res.stakes[0].sgn > 0 ? 'up' : 'down'} by about <b>${fB(res.stakes[0].usd)}</b>. `;
  if (res.groups.some(g => g.direct)) s += 'Which companies the event touches first is the AI\'s assumption.';
  return s;
}
function trace(res) {
  const sc = res.sc, g0 = res.groups[0], c = { DISCLOSED: 0, REPORTED: 0, ESTIMATED: 0 }; SUPL.forEach(l => c[confOf(l)]++);
  const first = (g0.kind === 'demand' ? byBuyer : bySeller)[g0.origins[0]]?.slice().sort((a, b) => W[g0.kind][b.id].p - W[g0.kind][a.id].p)[0], w = first && W[g0.kind][first.id];
  return [
    { fn: '1. build_graph()', ms: 'from filings', out: `${G.nodes.length} companies, ${G.links.length} links\n${SUPL.length} supply links can pass a shock, ${EQL.length} stakes are valued` },
    { fn: '2. weight_links()', ms: 'p = base x size x confidence', out: `confidence: ${c.DISCLOSED} disclosed (1.0), ${c.REPORTED} reported (0.7), ${c.ESTIMATED} estimated (0.4)\n${SUPL.filter(l => l.share != null).length} links use a disclosed revenue share, the rest use 1 / number of buyers` + (w ? `\ne.g. ${short(first.from)} -> ${short(first.to)}: ${w.base.toFixed(2)} x ${w.size.toFixed(2)} x ${w.conf.toFixed(1)} = ${w.p.toFixed(3)}` : '') },
    { fn: '3. read_scenario()', ms: Math.round(S.parseMs || 0) + ' ms', out: `"${sc.text}"\n` + res.groups.map(g => `{ start: [${g.origins.map(tick).join(', ')}], type: "${g.kind}", direction: "${g.dir > 0 ? 'positive' : 'negative'}", size: ${g.severity.toFixed(2)}${g.direct ? ', hits_them_directly: true' : ''} }`).join('\n') + `\n${LIVE ? 'read by the LLM' : 'read by the keyword parser (no API key)'}` },
    { fn: `4. monte_carlo(runs=${res.runs}, seed=${SEED})`, ms: Math.round(res.ms) + ' ms', out: `independent cascade${res.groups.length > 1 ? ', one per group' : ''}: each affected company gets one chance per link\n${res.rows.length} companies affected at least once` },
    { fn: '5. summarise()', ms: '', out: res.rows.slice(0, 4).map(r => `${tick(r.id)}: P ${fP(r.p, 0)}, change ${rs(r)}${fP(r.drop)}, value ${r.mcar != null ? rs(r) + fB(r.mcar) : 'n/a'}`).join('\n') + `\ngains +${fB(res.gain)}, losses -${fB(res.loss)}` },
    { fn: '6. explain()', ms: '', out: 'see the summary above' }
  ];
}

// ============================================================
//  Animation helpers
// ============================================================
function anim(dur, fn, done) { const t0 = performance.now(); const step = now => { const t = Math.min(1, (now - t0) / dur); fn(t); if (t < 1) requestAnimationFrame(step); else done && done(); }; requestAnimationFrame(step); }
function strike(id) { const c = $$('#chips .chip').find(x => x.dataset.id === id); if (c) { c.classList.remove('struck'); void c.offsetWidth; c.classList.add('struck'); } }
function blast(id) {
  if (!P[id]) return; const { x, y } = P[id];
  for (let k = 0; k < 3; k++) { const c = el('circle', { cx: x, cy: y, r: R(id), fill: 'none', stroke: colOf(gOf(id)?.dir ?? -1), 'stroke-width': 2, 'pointer-events': 'none', opacity: 0 }, gPulse); setTimeout(() => anim(1000, t => { c.setAttribute('r', R(id) + t * 80); c.setAttribute('opacity', (1 - t).toFixed(2)); }, () => c.remove()), k * 220); }
}
function burn(linkId, reverse, dur, color) {
  const e = EDGE[linkId]; if (!e) return; const len = e.p.getTotalLength();
  const b = el('path', { d: e.p.getAttribute('d'), class: 'burn', stroke: color, 'stroke-width': (e.w + 1.5).toFixed(2), 'stroke-dasharray': `${len} ${len}`, 'stroke-dashoffset': reverse ? -len : len }, gShock);
  anim(dur, t => { const k = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; b.setAttribute('stroke-dashoffset', ((reverse ? -len : len) * (1 - k)).toFixed(1)); }, () => anim(500, t => b.setAttribute('opacity', (1 - t).toFixed(2)), () => b.remove()));
}
function particle(linkId, reverse, size, color, dur) {
  const e = EDGE[linkId]; if (!e) return; const len = e.p.getTotalLength();
  const c = el('circle', { r: 3 + 4 * size, fill: color, stroke: '#fff', 'stroke-width': 1.5, 'pointer-events': 'none' }, gParticles);
  anim(dur, t => { const k = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; const pt = e.p.getPointAtLength(len * (reverse ? 1 - k : k)); c.setAttribute('cx', pt.x); c.setAttribute('cy', pt.y); }, () => c.remove());
}
function impact(id, color) {
  if (!P[id]) return; const { x, y } = P[id], r0 = R(id), n = NODE[id];
  const c = el('circle', { cx: x, cy: y, r: r0, fill: 'none', stroke: color, 'stroke-width': 3, 'pointer-events': 'none' }, gPulse);
  anim(750, t => { c.setAttribute('r', r0 + t * 36); c.setAttribute('opacity', (1 - t).toFixed(2)); }, () => c.remove());
  anim(420, t => n.core.setAttribute('r', (r0 * (1 + 0.25 * Math.sin(Math.PI * t))).toFixed(2)), () => n.core.setAttribute('r', r0));
}
function floater(id, text, color) {
  if (!P[id]) return; const { x, y } = P[id], off = Math.max(R(id) + 10, 20), right = x < MW - 190;
  const t = el('text', { x: x + (right ? off : -off), y: y + 5, class: 'floater', fill: color, 'text-anchor': right ? 'start' : 'end' }, gFloat); t.textContent = text;
  anim(2000, k => { t.setAttribute('transform', `translate(0,${(-12 * (1 - Math.pow(1 - k, 3))).toFixed(1)})`); t.setAttribute('opacity', k < .75 ? 1 : ((1 - k) / .25).toFixed(2)); }, () => t.remove());
}

// ============================================================
//  Sources: every link and its evidence
// ============================================================
function filteredLinks() {
  const q = S.q.trim().toLowerCase();
  return G.links.filter(l => (S.fType === 'All' || l.type === S.fType) && (!q || [N[l.from].name, N[l.to].name, N[l.from].ticker, N[l.to].ticker, l.label, l.type].join(' ').toLowerCase().includes(q)));
}
function renderSources() {
  const list = filteredLinks();
  $('#srcT').textContent = `${list.length.toLocaleString()} of ${G.links.length.toLocaleString()} links`;
  $('#types').innerHTML = ['All', ...new Set(G.links.map(l => l.type))].map(t => `<button class="chip" data-t="${esc(t)}" aria-pressed="${S.fType === t}">${esc(t)}</button>`).join('');
  $$('#types .chip').forEach(b => b.onclick = () => { S.fType = b.dataset.t; renderSources(); });
  $('#srcList').innerHTML = list.slice(0, 120).map(l => `<button class="srow" data-link="${esc(l.id)}"><div class="m"><span class="tag DISCLOSED">${esc(l.type.toUpperCase())}</span>${tagHTML(confOf(l))}${l.role === 'propagates' ? '<span>passes shocks</span>' : ''}</div><div class="t">${esc(N[l.from].name)} ${verb(l)} ${esc(N[l.to].name)}</div><div class="u">${esc(l.label || '')}</div></button>`).join('') + (list.length > 120 ? `<p class="note" style="padding:12px 20px">Showing the first 120. Search to narrow it down.</p>` : '') || '<p class="note" style="padding:16px 20px">No link matches.</p>';
  $$('#srcList .srow').forEach(b => b.onclick = () => { const id = b.dataset.link; closeSources(); select('link', id); });
}
function openSources() { S.srcOpen = true; $('#src').classList.remove('hide'); $('#scrim').classList.remove('hide'); renderSources(); $('#fq').focus(); loadEvidence(); }
function closeSources() { S.srcOpen = false; $('#src').classList.add('hide'); $('#scrim').classList.add('hide'); }

// ============================================================
//  Init
// ============================================================
function init() {
  const cov = G.meta.coverage || {}, rev = G.links.filter(l => l.review === 'reviewed').length;
  $('#snapT').textContent = `${G.nodes.length.toLocaleString()} companies · ${G.links.length.toLocaleString()} links from filings · prices ${G.meta.priced}`;
  $('#nSrc').textContent = G.links.length.toLocaleString();
  $('#covNote').textContent = `Coverage: all ${cov.sp500_nodes} S&P 500 companies are in the data, ${cov.sp500_in_model} have links that can pass a shock. ${rev} of ${G.links.length} links were checked by hand; the rest were found by text rules and count at 0.4 confidence. Results are a lower bound.`;
  $('#presets').innerHTML = PRESETS.map((p, i) => `<button class="preset" data-i="${i}">${esc(p.t)}<span>${esc(p.tag || 'run')}</span></button>`).join('');
  $$('.preset').forEach(b => b.onclick = () => { const p = PRESETS[+b.dataset.i]; runFromText(p.t, p.sc); });
  $('#askForm').onsubmit = e => { e.preventDefault(); const v = $('#sText').value.trim(); v ? runFromText(v) : runFromText(PRESETS[0].t, PRESETS[0].sc); };
  $$('.views button').forEach(b => b.onclick = () => { const m = b.dataset.mode; if (m === 'loops') { S.view = 'chain'; setLoops(true); renderPortfolio(); } else setView(m); });
  bindZoom();
  $('#brand').onclick = () => { clearScenario(true); S.sel = null; S.loops = false; S.view = 'all'; renderDetail(); setFocus(N.openai ? 'openai' : S.focus); };
  $('#srcBtn').onclick = openSources; $('#srcX').onclick = closeSources; $('#scrim').onclick = closeSources;
  $('#fq').oninput = e => { S.q = e.target.value; renderSources(); };
  $('#howBtn').onclick = () => $('#how').classList.remove('hide');
  $('#howX').onclick = () => $('#how').classList.add('hide');
  $('#how').onclick = e => { if (e.target.id === 'how') $('#how').classList.add('hide'); };
  $('#map').addEventListener('click', () => { if (S.sel) select(null); });
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (!$('#how').classList.contains('hide')) $('#how').classList.add('hide'); else if (S.srcOpen) closeSources(); else if (S.sel) select(null);
  });
  S.loopList = findLoops(S.focus);
  buildMap(); renderCap(); renderPortfolio(); renderInterp(); renderReport(); renderParser(); initKey(); checkLive();
}
init();
