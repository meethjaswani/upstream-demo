// Upstream local server. No dependencies (Node 18+).
// Serves index.html and exposes POST /api/parse-scenario, which asks Claude to turn a
// free-text scenario into starting groups { origins, kind, direction, severity }. The API key stays on this
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
const graph = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/graph.json'), 'utf8'));
const inModel = new Set(graph.links.filter(l => l.model_role === 'propagates').flatMap(l => [l.from, l.to]));
const companies = graph.nodes.filter(n => inModel.has(n.id));

const SYSTEM = `You turn an investor's "what if" scenario into the starting point of a network model of companies.
The model then spreads the effect along supply links by itself. You only choose where it starts, in which direction and how big.
You never choose which other companies get affected after that.
Companies (id: name): ${companies.map(c => `${c.id}: ${c.name}`).join('; ')}.

Return 1 to 4 groups. Each group is a set of companies that the scenario touches first in the same way.
- origins: 1 to 8 ids from the list, spelled exactly. Only companies the scenario acts on directly.
- kind: "demand" if the effect then travels to their suppliers (they buy more or less);
  "supply" if it travels to their customers (they deliver more or less).
- direction: "negative" (they buy or deliver less, or lose value) or "positive" (they buy or deliver more, or gain value).
- severity: fraction 0..1.
- hits_them_directly: false for a company's own decision ("OpenAI cuts compute spending 40%": origins ["openai"], demand,
  negative, 0.4, false - never add its suppliers). true for an outside event that changes the companies' own business
  (a war ends, oil falls, a tariff, a rate change, a regulation): then severity is your estimate of the change in their
  own value, usually 0.03 to 0.25, and you may use several groups with different directions
  (e.g. oil falls: oil producers negative, airlines positive).
- label: 2 to 4 words naming the group (e.g. "Oil producers").
A named group such as "hyperscalers" or "AI compute buyers" means its members, e.g. msft, amzn, googl, meta, orcl, openai.
If a number in the text measures something else (interest-rate points, a price), do not use it as the severity.
title: a short neutral headline for the scenario, under 8 words.
reason: one or two sentences on how you read it and what you assumed.
If the text is political, model only its business consequences. If nothing company-level fits, return groups [] and say why.
Always answer by calling set_scenario.`;

const TOOL = {
  name: 'set_scenario',
  description: 'Starting groups for the network model.',
  input_schema: {
    type: 'object',
    properties: {
      title: { type: 'string' },
      groups: { type: 'array', maxItems: 4, items: { type: 'object', properties: {
        label: { type: 'string' },
        origins: { type: 'array', items: { type: 'string' }, maxItems: 8 },
        kind: { type: 'string', enum: ['demand', 'supply'] },
        direction: { type: 'string', enum: ['negative', 'positive'] },
        severity: { type: 'number', minimum: 0, maximum: 1 },
        hits_them_directly: { type: 'boolean' }
      }, required: ['label', 'origins', 'kind', 'direction', 'severity', 'hits_them_directly'] } },
      reason: { type: 'string' }
    },
    required: ['title', 'groups', 'reason']
  }
};

async function parseWithClaude(text) {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'x-api-key': KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
    body: JSON.stringify({
      model: MODEL, max_tokens: 900, system: SYSTEM,
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
      return send(res, 502, { error: /401/.test(e.message) ? 'API key rejected' : /40[34]|model/.test(e.message) ? 'model not available for this key' : 'request failed' });
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
