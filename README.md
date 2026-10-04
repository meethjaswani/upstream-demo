# Upstream

Type what could go wrong. See which of your stocks it hits.

Investors think they own several different AI stocks, but many depend on the same customer (OpenAI) and on each other through circular deals. Upstream maps 12 companies and 26 sourced deals, then runs a shock through the network so you can see which holdings get hit and by how much.

## How the demo works

- Frontend only. `index.html` is self-contained; all data is hardcoded in a `DATA` object and mirrors `data/*.json`.
- The network map is a fixed layout: suppliers, chips, clouds, OpenAI, investors. Solid arrows are "sells to", dashed are "invests in", dotted are undisclosed or estimated.
- Pick a portfolio, type a scenario (or use a preset). The shock math runs in the browser on the data: demand shocks flow upstream, damped 0.6 per hop, up to 4 hops. Equity hit = stake value x valuation drop (1.5 x shock, capped at 100%).
- Money loops are found with a cycle search over the combined supply and equity graph.
- Running a scenario plays it on the map: the shock burns along each deal hop by hop, each hit company shows its loss, and the last step shows investors writing down their stakes.
- Choke points are found by failing each company in full, as a buyer and as a supplier, and ranking by revenue at risk times companies hit. The top three are marked with a diamond.
- The agent trace tab is a recorded run, not a live agent.

## Real vs estimated

Every link carries a confidence tag and a source (`data/sources.md`):

- **DISCLOSED**: company filing or press release with an amount.
- **REPORTED**: credible media (WSJ, FT, Reuters, CNBC, Yonhap).
- **ESTIMATED**: our assumption, explained in the link's `estimate_note`. Annualised values (for example $250B over ~7 years = ~$36B/yr) are estimates.

Sources marked `unverified` in `data/sources.md` were not re-checked against the live document in our quick pass (many sites block automated fetches). Snapshot: hand-verified from filings and press releases, Oct 2026. Not investment advice.

## Run it locally

Needs Node 18+. No npm install.

```bash
git clone <this repo> && cd upstream-demo
cp .env.example .env        # then put your key in .env: ANTHROPIC_API_KEY=sk-ant-...
npm start                   # open http://localhost:3000
```

With a key, free-text scenarios are interpreted by Claude (`claude-sonnet-5`) through `POST /api/parse-scenario`. The key stays on your machine and is never sent to the browser.

No key, or just want the static version? Open `index.html` directly. The keyword parser and recorded trace still work.

## Data

- `data/companies.json`: id, name, ticker, type, revenue, fiscal year, revenue source
- `data/links.json`: from, to, type (supply or equity), amounts, date, confidence, source, quote
- `data/sources.json` and `data/sources.md`: every source document and what we took from it
- `npm run embed` re-embeds the JSON into `index.html` and regenerates `sources.md`

## Roadmap

An AI extraction pipeline on AWS Bedrock reading SEC EDGAR, HKEX filings and press releases, producing the same JSON schema, so the map updates itself and covers any sector.
