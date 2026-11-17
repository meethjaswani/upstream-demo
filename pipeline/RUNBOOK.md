# Pipeline runbook (for Claude Code)

Read `pipeline/README.md` first. Do the phases in order. Stop where it says STOP and report. Work lean: no parallel subagents except the one direction checker.

BILLING RULE: phases 0 to 5 use no API. Never set or read ANTHROPIC_API_KEY, never run `pipeline.run extract`, never call `claude -p`. You do the reading yourself through `pipeline.batch` (see `PIPELINE_PROMPT.md`). Only phase 6 uses the API, and only after Meeth says so.

The pipeline has passed unit tests only. It has never read a real filing. Expect to find bugs in phase 3.

## Phase 0: setup
- `SEC_USER_AGENT` must be set (in `.env` or the environment). If missing, stop and ask.
- Fetch one page from data.sec.gov and www.sec.gov. If blocked, stop.
- `python3 -m pytest pipeline/tests -q` must pass.

## Phase 1: fixes before any real run (add a unit test for each)
1. Quote check: before comparing, normalise curly quotes, apostrophes, dashes and non breaking spaces on both the quote and the filing text. Models often straighten these and a correct quote gets rejected.
2. Tables: when a candidate comes from a flattened table row, add the table's header row and the caption line above it to the passage. A bare row like "Customer A | 22% | 14%" has no year or metric.
3. Prompt: when shares for several years are given, record the latest fiscal year only.
4. Link ending: when a newer 10-K from the same reporter no longer states a link that its previous 10-K stated, close that link at the newer filing's acceptance time. Keep the 550 day rule only as the fallback.
5. Corroboration: count it only when both companies report the link (two different reporters). One company repeating itself in a 10-K and a 10-Q is not independent.
6. Store the model name on every observation, next to `extractor_version`.
7. External companies: an unknown name that matches an SEC registrant (company_tickers.json) or appears in two or more filings gets an `ext:` leaf node automatically. Everything else stays in the review queue.
8. Subsidiaries: parse Exhibit 21 of each 10-K into a subsidiary to parent map, and resolve subsidiary names to the listed parent with a note on the link.
9. Add CIKs for the roughly 100 companies outside the S&P 500 that are in `data/graph.json` and file with the SEC.

STOP. Show the test results.

## Phase 2: free links first, no LLM
Read named customer concentration facts from each filing's XBRL (ConcentrationRiskPercentage with a customer member, revenue benchmark only). Store them as DISCLOSED with the fact as evidence and the filing's acceptance time. Report how many links per year this gives for 2015 to 2023.

## Phase 3: first real run
Tickers MCK, NVDA, CRWV, AAPL, ORCL, latest 10-K only, through `pipeline.batch` as described in `PIPELINE_PROMPT.md`.
Report: candidates per filing, links stored, review queue with reasons, and every bug found. Compare the stored links with the hand reviewed links for the same companies in `data/graph.json`.

STOP. Wait for Meeth.

## Phase 4: gold set (needs Meeth for labelling)
Sample 50 10-K filings, stratified by sector. Label on the full Item 1, 1A, 7 and the concentration note, not only on the candidate sentences, so the recall of the candidate filter is measured too. At least 300 sentences. Hold out half and use it once, after the prompt is final.
Report precision, recall, F1 for link existence and direction, exact match for shares, and filter recall separately. Targets: precision 0.85, recall 0.60.

## Phase 5: backfill
Order: 10-K 2015 to 2023 for the S&P 500 first (the backtest needs these), then the extra companies, then 10-Q, then 8-K. Resumable.
After the first 100 filings, STOP and report the usage, so Meeth can decide how far to go.

## Phase 6: daily updates (the only step that uses the API)
Add a GitHub Actions workflow on a daily schedule that runs `python3 -m pipeline.run daily` with `ANTHROPIC_API_KEY` and `SEC_USER_AGENT` as repository secrets and the cheapest model that passed the gold set. It saves the database and a dated diff of links added, changed and removed. Daily volume is small, so the cost is small.
Do not turn this on without Meeth's go.

## Phase 7: hand over to the backtest
`python3 -m pipeline.run export --as-of <date>` gives the graph for any past date. Stage 2 of the backtest reads these exports.
