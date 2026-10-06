# Upstream

Type what could go wrong. See which of your stocks it hits.

Investors think they own several different AI stocks, but many depend on the same customer (OpenAI) and on each other through circular deals. Upstream maps 12 companies and 26 sourced deals, then runs a shock through the network so you can see which holdings get hit and by how much.

## How it works

- **Data:** `data/graph.json` holds all 500 S&P companies plus their counterparties, with links taken from filings, 13F forms, press releases and credible reports. `data/evidence.js` holds the quote and document behind every link. Rebuild everything with `npm run data` (or `python3 tools/build_data.py "<path to model bundle>"` then `node tools/layout.mjs`).
- **All companies:** a network map of every S&P 500 company and its counterparties. Position is the sector, colour is the sector family, lines are who sells to whom. Hover to trace a company's links, zoom for more names, click to open its supply chain. The layout is fixed and comes from `node tools/layout.mjs`.
- **3D view:** the same network on a rotating globe, for presenting. A scenario run from this tab plays on the globe in a loop. It uses `vendor/three.min.js`, saved locally so it works offline.
- **Supply chain:** suppliers on the left, the company in the middle, customers on the right, for any company you search.
- **Link strength:** `p = base x size x confidence`. Base is the disclosed revenue share, or 1 / number of buyers (weighted cascade, Kempe, Kleinberg and Tardos 2003). Size is sqrt(buyer market cap / seller market cap), capped at 1. Confidence is 1.0 disclosed, 0.7 reported, 0.4 estimated.
- **Scenario:** the AI picks only the starting companies and a severity. An independent cascade then runs 20,000 times in the browser (Monte Carlo).
- **Report:** P(hit), predicted drop (severity x 0.6 per extra hop) and market cap at risk for each company, with your holdings marked.
- **Known limits:** links without a disclosed share count equally, only signed deals are seen, shocks are treated as independent, and the damping and confidence weights are assumptions.

## Run it locally

Needs Node 18+. No npm install.

```bash
git clone <this repo> && cd upstream-demo
cp .env.example .env        # then put your key in .env: ANTHROPIC_API_KEY=sk-ant-...
npm start                   # open http://localhost:3000
```

With a key, free-text scenarios are interpreted by an LLM (`claude-sonnet-5`) through `POST /api/parse-scenario`. The key stays on your machine and is never sent to the browser.

No key, or just want the static version? Open `index.html` directly. The keyword parser and recorded trace still work.

## Roadmap

An AI extraction pipeline on AWS Bedrock reading SEC EDGAR, HKEX filings and press releases, producing the same JSON schema, so the map updates itself and covers any sector.
