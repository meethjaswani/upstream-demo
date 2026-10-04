// Embeds data/*.json into index.html (between DATA markers) and regenerates data/sources.md.
// Usage: node tools/embed.mjs   (run from repo root). Keeps index.html identical to the JSON files.
import fs from 'node:fs';
const root = new URL('..', import.meta.url).pathname;
const read = f => JSON.parse(fs.readFileSync(root + 'data/' + f, 'utf8'));
const companies = read('companies.json'), links = read('links.json'), sources = read('sources.json');
const html = fs.readFileSync(root + 'index.html', 'utf8');
const block = `/*DATA:BEGIN*/\nconst DATA = ${JSON.stringify({ companies, links, sources })};\n/*DATA:END*/`;
const out = html.replace(/\/\*DATA:BEGIN\*\/[\s\S]*?\/\*DATA:END\*\//, block);
if (out === html && !html.includes(block)) throw new Error('DATA markers not found');
fs.writeFileSync(root + 'index.html', out);

const byId = Object.fromEntries(companies.map(c => [c.id, c]));
let md = '# Sources\n\nEvery document behind the Upstream demo snapshot (hand-verified, Oct 2026). Check column: **verified** = number confirmed against the document text in a quick automated pass on Oct 4 2026; **unverified** = not confirmed in that pass (often the site blocked automated fetches), value kept from the hand-verified brief. Links marked *search link* point to a publisher search page because we did not pin the article URL.\n\n';
md += '| Date | Type | Company | Document | What we took from it | Check | Used by links |\n|---|---|---|---|---|---|---|\n';
for (const s of [...sources].sort((a, b) => a.date.localeCompare(b.date))) {
  const used = links.filter(l => l.source_id === s.id).map(l => l.id).join(', ') || '(company revenue)';
  const search = /search|site-search|\?q=|query=/.test(s.url) ? ' *search link*' : '';
  md += `| ${s.date} | ${s.type} | ${byId[s.company]?.name ?? s.company} | [${s.title}](${s.url})${search} | ${s.used_for} | **${s.verification}**: ${s.verified_note} | ${used} |\n`;
}
md += '\n## Confidence tags\n\n- **DISCLOSED**: company filing or company press release with an amount.\n- **REPORTED**: credible media (WSJ, FT, Reuters, CNBC, Yonhap).\n- **ESTIMATED**: our assumption; each link carries an `estimate_note` explaining how.\n';
fs.writeFileSync(root + 'data/sources.md', md);
console.log(`embedded ${companies.length} companies, ${links.length} links, ${sources.length} sources`);
