// Upstream local server. No dependencies (Node 18+).
// Serves index.html and exposes POST /api/parse-scenario, which asks Claude to turn a
// free-text scenario into { origin, target, kind, severity }. The API key stays on this
// machine: it is read from the environment (or a local .env file) and never sent to the browser.
//
//   ANTHROPIC_API_KEY=sk-ant-... node server.js     ->  http://localhost:3000
'use strict';
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = __dirname;
// minimal .env loader (KEY=value lines); real environment variables win
try {
  for (const line of fs.readFileSync(path.join(ROOT, '.env'), 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
} catch { /* no .env file */ }

const PORT = +process.env.PORT || 3000;
const KEY = process.env.ANTHROPIC_API_KEY || '';
const MODEL = process.env.UPSTREAM_MODEL || 'claude-sonnet-5';
const companies = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/companies.json'), 'utf8'));
const links = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/links.json'), 'utf8'));
const IDS = companies.map(c => c.id);

const SYSTEM = `You turn an investor's "what could go wrong" scenario into parameters for a shock model.
Companies (id: name, ticker): ${companies.map(c => `${c.id}: ${c.name} (${c.ticker})`).join('; ')}.
Supply links (seller -> buyer): ${links.filter(l => l.type === 'supply').map(l => `${l.from}->${l.to}`).join(', ')}.
Rules:
- origin = the company where the problem starts.
- kind = "demand" if origin buys less / pays less / misses payments (hits its sellers upstream);
  "supply" if origin cannot deliver what it sells (hits its buyers downstream).
- target = one counterparty id if the scenario names a single deal, else "".
  For demand, target must be a seller to origin; for supply, a buyer from origin.
- severity = fraction 0..1. Use the stated %; "misses payments", "defaults" or "cancels" = 1.0; "halves" = 0.5; unstated = 0.4.
- Only business scenarios. If the text is political or not about these companies, pick the closest business reading and say so in reason.
Always answer by calling set_scenario.`;

const TOOL = {
  name: 'set_scenario',
  description: 'Structured scenario for the shock model.',
  input_schema: {
    type: 'object',
    properties: {
      origin: { type: 'string', enum: IDS },
      target: { type: 'string', enum: ['', ...IDS] },
      kind: { type: 'string', enum: ['demand', 'supply'] },
      severity: { type: 'number', minimum: 0, maximum: 1 },
      reason: { type: 'string', description: 'One short sentence on how you read the scenario.' }
    },
    required: ['origin', 'target', 'kind', 'severity', 'reason']
  }
};

async function parseWithClaude(text) {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'x-api-key': KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
    body: JSON.stringify({
      model: MODEL, max_tokens: 400, system: SYSTEM,
      tools: [TOOL], tool_choice: { type: 'tool', name: 'set_scenario' },
      messages: [{ role: 'user', content: String(text).slice(0, 500) }]
    })
  });
  if (!r.ok) throw new Error(`Anthropic API ${r.status}: ${(await r.text()).slice(0, 300)}`);
  const j = await r.json();
  const call = (j.content || []).find(b => b.type === 'tool_use');
  if (!call) throw new Error('no tool call in response');
  return call.input;
}

const TYPES = { '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.md': 'text/markdown; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png' };
const send = (res, code, body, type = 'application/json') => { res.writeHead(code, { 'content-type': type, 'cache-control': 'no-store' }); res.end(typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body)); };

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname === '/api/health') return send(res, 200, { live: !!KEY, model: KEY ? MODEL : null });
  if (url.pathname === '/api/parse-scenario') {
    if (req.method !== 'POST') return send(res, 405, { error: 'POST only' });
    if (!KEY) return send(res, 503, { error: 'ANTHROPIC_API_KEY not set' });
    let body = '';
    for await (const chunk of req) { body += chunk; if (body.length > 10000) return send(res, 413, { error: 'too large' }); }
    try {
      const { text } = JSON.parse(body || '{}');
      if (!text || typeof text !== 'string') return send(res, 400, { error: 'text required' });
      const out = await parseWithClaude(text);
      console.log(`[parse] "${text}" -> ${JSON.stringify(out)}`);
      return send(res, 200, out);
    } catch (e) {
      console.error('[parse] failed:', e.message);
      return send(res, 502, { error: 'parse failed' });
    }
  }
  // static files, restricted to the project folder
  let file = path.normalize(path.join(ROOT, url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname)));
  if (!file.startsWith(ROOT) || /[\\/]\.(env|git)/.test(file.slice(ROOT.length))) return send(res, 404, 'not found', 'text/plain');
  fs.readFile(file, (err, data) => err ? send(res, 404, 'not found', 'text/plain') : send(res, 200, data, TYPES[path.extname(file)] || 'application/octet-stream'));
}).listen(PORT, () => {
  console.log(`Upstream running at http://localhost:${PORT}`);
  console.log(KEY ? `Live mode: scenarios parsed by ${MODEL}` : 'No ANTHROPIC_API_KEY found: running offline (keyword parser). Add it to .env for live mode.');
});
