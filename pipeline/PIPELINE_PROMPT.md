# Extraction without API credits: instructions for Claude Code

You are the LLM step of the Upstream pipeline. Read `pipeline/README.md` first. Do NOT use the Anthropic API key and do NOT call `pipeline.run extract`. Work one file at a time, no parallel subagents.

## Loop
1. Run: `python3 -m pipeline.batch export --tickers <TICKERS> --since <DATE> --forms 10-K`
2. For each `pipeline/work/*.in.json` that has no `.out.json` yet:
   a. Read the file. Follow the rules in the SYSTEM text inside `pipeline/extract.py` exactly (FILER naming, direction, verbatim quote, what to reject).
   b. Write `<same name>.out.json` as `{"links": [ ... ]}`. Each link has exactly these fields:
      passage_id, from_company, to_company, type (sells_to | invests_in | partners_with), revenue_share (fraction or null),
      amount_usd (number or null), tags (list from sole_source, risk_factor_mention, purchase_commitment), anonymised (bool),
      inferred (bool), evidence_quote (copied word for word from the passage).
      An empty list is a normal answer.
3. Direction check, done separately so it is independent: start ONE fresh subagent that sees only the quotes, not your answers.
   Give it, for every sells_to link, the quote plus "Company A" (from_company) and "Company B" (to_company), and ask who sells to whom.
   Save its answers as `<same name>.check.json`: `{"<evidence_quote>": "A_SELLS_TO_B" | "B_SELLS_TO_A" | "UNCLEAR"}`.
4. Run: `python3 -m pipeline.batch import` then `python3 -m pipeline.run review`.
5. Report: files done, links stored, links in review and the reasons. Do not edit the validation code to make links pass.

## First run
Tickers MCK,NVDA,CRWV,AAPL,ORCL with `--since 2025-01-01 --limit 1`. Stop after it and show me the stored links and the review queue.
