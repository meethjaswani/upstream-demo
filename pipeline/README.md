# Upstream extraction pipeline

Turns SEC filings into dated, cited links between companies. One LLM step, everything else is plain code.

| Step | File | What it does |
|---|---|---|
| 1 Ingest | `edgar.py` | Lists 10-K, 10-Q, 8-K, 20-F filings per company and downloads them, keeping the EDGAR acceptance time |
| 2 Parse | `parse.py` | HTML to text, tables flattened, sentences tagged with their Item section |
| 3 Candidates | `candidates.py` | Keeps only sentences with a trigger phrase or a known company plus a relation word |
| 4 Extract | `extract.py` | Claude with strict tool use returns each link in a fixed schema with its quote |
| 5 Validate | `validate.py` | Quote must appear word for word, entities must resolve, shares between 0 and 1, a second call confirms direction |
| 6 Store | `store.py` | SQLite. Passed links become observations, failed ones go to the review queue |

## Setup
    pip install anthropic requests lxml pytest
`.env` needs `ANTHROPIC_API_KEY` and `SEC_USER_AGENT` (your name and email, the SEC requires it).

## Use
    python3 -m pytest pipeline/tests -q
    python3 -m pipeline.run extract --tickers MCK,NVDA --since 2025-01-01 --forms 10-K --dry-run   # no LLM cost
    python3 -m pipeline.run extract --tickers MCK,NVDA --since 2025-01-01 --forms 10-K
    python3 -m pipeline.run review
    python3 -m pipeline.run export --as-of 2024-01-01 > graph.json
    python3 -m pipeline.run daily
    python3 -m pipeline.smoke_eval "<old bundle>/out/model_v2/links_detail.jsonl" 40

## Point in time
`export --as-of D` uses only filings accepted before D. A link drops out when no filing repeats it for 550 days.
A link seen in two filings, or reported by both companies, moves up one confidence tier.

## Confidence tiers
DISCLOSED (filing, with a share or amount), STATED (filing, no amount), ANNOUNCED (press release exhibit), INFERRED (indirect wording).

## Not done yet
- Only S&P 500 members have CIKs loaded. The extra 100 companies need CIKs added to `data/sp500.csv`.
- Unknown company names go to the review queue. Add them to `data/aliases.csv` or as new nodes, then rerun.
- Matching "Customer A" to a real name is not built.
- Storage is SQLite. The plan says PostgreSQL. The SQL is plain, so the move is small.
- No hand labelled gold set yet. `smoke_eval.py` is only a sanity check on old reviewed links.
- Daily run is a command. It still needs a scheduler (GitHub Actions or cron).
