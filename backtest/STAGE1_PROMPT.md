# Stage 1 backtest: instructions for Claude Code

You are working on Upstream, my COMP4801 final year project. Goal: build and run the Stage 1 backtest on a seed graph and give me results I can put in a report. Nothing for the backtest exists yet. Build it in `backtest/` (Python). Do not touch the web app files. Work lean: no parallel subagents.

## What is already in this repo
- `data/graph.json`: 1,187 nodes (500 S&P companies plus counterparties), 1,291 links, with sector, sub_industry, market cap. `data/evidence.js` has the quote, document type, filing date and URL behind each link.
- IMPORTANT: this graph is a snapshot built in Oct 2026 from 2025 and 2026 filings. It is NOT point in time. Do not use it as the graph for 2016 to 2023 events. Use it only for the node list, tickers, CIKs, sectors, and as a cross-check.

## Data to fetch (run from this machine, cache everything under backtest/cache/, gitignore it)
1. Daily adjusted prices 2014-10 to 2023-12 for the universe (yfinance). Do not download 2024 onwards.
2. Fama French 3 daily factors plus momentum (Ken French data library).
3. Historical S&P 500 membership by date (for example the fja05680/sp500 dataset on GitHub).
4. SEC submissions index per company: every 10-K, 10-Q, 8-K with acceptance datetime and 8-K item codes (item 2.02 = earnings). Read the User-Agent from SEC_USER_AGENT in .env, stay under 10 requests per second.
5. Shares outstanding per filing from the SEC companyfacts API, times price, for point in time market cap.
6. Seed graph links: major customer disclosures from each annual 10-K 2015 to 2023. Try the structured route first: XBRL ConcentrationRiskPercentage facts with a named customer member (the repo already found 39 of these for 2026). Then pattern matching on the revenue concentration notes ("accounted for", "% of revenue", "10% or more"). Each link stored with seller, buyer, revenue_share, accession number, accepted_at, evidence quote. Unnamed customers ("Customer A") kept as anonymous edges.
Note for Yahoo prices: delisted companies will be missing. Count them and report the survivorship gap.

## Hard rules
1. Point in time only. The graph on date t uses filings accepted before t. Universe on date t is index membership on that date.
2. Split: 2016-01 to 2021-12 fitting, 2022-01 to 2023-12 choosing. NEVER load, plot or score anything from 2024-01 onwards. Add a guard that raises an error if it is touched.
3. Every configuration run goes into one trial log (CSV: timestamp, variant, parameters, period, metrics). Include bad runs.
4. Report results as found. If the model loses to a baseline, say so. Do not tune until it wins.
5. Deterministic and seeded. pytest unit tests for the engine and event detection.

## The model
Demand shock, weight from buyer j to seller i:
- disclosed revenue share r_ij if available
- otherwise (1 - R_i) * u_ji / (1 + sum of u_ki over undisclosed buyers), u_ji = (M_j / M_i)^beta, M = market cap
- times confidence factor by tier (DISCLOSED 1.0, STATED 0.9, ANNOUNCED 0.8, INFERRED 0.5 to start)
Propagation: x(h+1) = min(1, x0 + delta * W^T x(h)), up to H hops or until change < 0.001.
- M1 linear cascade (above)
- M2 DebtRank style, each node passes its loss on once
- M3 independent cascade, weight as transmission probability, 10,000 Monte Carlo runs
Search: beta 0 to 2, delta 0.2 to 0.9 (start 0.6), H in {1,2,3,4,6} (start 4).

## Shock panel (E2)
Event = trading day where a company's abnormal return is at least 3 standard deviations from zero versus its own trailing 250 day residuals, AND it filed an 8-K or reported earnings within one day. Drop days where the S&P 500 moves more than 2%.
Abnormal returns: Fama French 3 factor model estimated on days -260 to -11.
Per event: seed with the shocked company's abnormal return, run on the previous day's graph, compare with CAR of linked companies over [0,+5] and [+1,+20].
Metrics: Spearman rank correlation (per event, averaged); hit rate above an exposure threshold; pooled regression of CAR on predicted exposure with controls for same industry, beta, size, standard errors clustered by event date.
Baselines: B0 no network. B1 same GICS sub-industry gets the seed shock. B2 direct neighbours, unweighted. B3 the 20 most correlated stocks over the past year, scaled by correlation.

## Also run
- E3 portfolio test: monthly signal from linked companies' last month returns through the model, quintile sort, top minus bottom regressed on FF3 plus momentum.
- E4 case replay, illustration only: Apple guidance cut, 2 Jan 2019.
(The DeepSeek replay of 27 Jan 2025 is inside the closed test period. Skip it unless I say otherwise.)

## Output
- `backtest/results/stage1_summary.md`: one table of every variant and baseline on fitting and choosing periods, number of events, number of seed links per year, and a plain list of what worked and what did not
- `backtest/results/*.csv`, `backtest/results/figures/*.png` (2 or 3 charts for slides), the trial log
- a short list of anything assumed or not done

## Order
1. Data fetch and cache. 2. Seed graph. 3. Engine and tests. 4. Event detection and tests. 5. Baselines and metrics. 6. Parameter search with trial log. 7. E3 and E4. 8. Summary.
Stop and show me the seed graph size and event count after step 4 before running the search. Ask before any change to the equations.
