"""Writes results/widening/widening_summary.md: universe-only vs widened vs widened without the
datadate + 90 rows, the name-match audit, the search, baselines, head-to-head and the pre-registered
weight tests. Tables come from the result files; the reading of them is written below each table."""
import json

import pandas as pd

from .config import RESULTS
from .search import OUT
from .widening_report import ARMS, all_tables


def jl(p):
    return json.loads(p.read_text()) if p.exists() else {}


def main():
    T = all_tables()
    a1, a2 = jl(RESULTS / "match_audit_round1.json"), jl(RESULTS / "match_audit_round2.json")
    b, bnf = jl(RESULTS / "wide_graph_build.json"), jl(RESULTS / "wide_graph_build_nofallback.json")
    ck = jl(RESULTS / "checkpoint_wide_strict.json")
    sel = {a: jl(OUT / f"selected_{a}.json") for a in ARMS}
    kc = {a: jl(OUT / f"kept_counts_{a}.json") for a in ARMS}
    trials = sum(1 for _ in open(RESULTS / "trial_log.csv")) - 1

    lpy = ""
    if ck:
        L = pd.DataFrame(ck["links_per_year"])
        lpy = "| year | universe-only | widened | both sources | Compustat only | 10-K only |\n|---|---:|---:|---:|---:|---:|\n" + \
              "\n".join(f"| {int(r.year)} | {int(r.universe_only):,} | {int(r.widened):,} | {int(r.both):,} | "
                        f"{int(r.compseg):,} | {int(r.tenk):,} |" for r in L.itertuples())
    paths = ""
    if ck:
        rows = []
        for arm in ARMS:
            for p in ck.get(arm, {}).get("graph_paths", []):
                rows.append({"arm": ARMS[arm], **p})
        P = pd.DataFrame(rows)
        if len(P):
            g = P.groupby("arm")[["direct_links_priced", "two_hop_paths", "three_hop_paths"]].agg(["min", "max"])
            paths = "| arm | direct links | 2-hop paths | 3-hop paths |\n|---|---:|---:|---:|\n" + "\n".join(
                f"| {a} | {r[('direct_links_priced', 'min')]:,}-{r[('direct_links_priced', 'max')]:,} | "
                f"{r[('two_hop_paths', 'min')]:,}-{r[('two_hop_paths', 'max')]:,} | "
                f"{r[('three_hop_paths', 'min')]:,}-{r[('three_hop_paths', 'max')]:,} |" for a, r in g.iterrows())
    sky = ck.get("compseg_vs_10k_text", {}).get("skyworks_to_apple", []) if ck else []
    sky18 = [s for s in sky if s["fiscal_year_end"].startswith("2018")]

    md = f"""# Widening (amendment 12): universe-only vs widened

Fitting 2016-2021 and choosing 2022-2023 only; nothing from 2024 was loaded. Both CRSP arms use crsp.dsi
sprtrn for the 2% market filter and historical GICS (comp.co_hgic) for industry, so the universe-only numbers
here differ slightly from the first Stage 1 report. Seeds are the same 7,631 E2 events at index firms in every
arm. {trials} rows in the trial log; the weight tests were written into it before any widened-arm scoring.

Arms: **universe-only** = 10-K graph, linked firms are index members (704 companies). **widened** = 10-K graph
plus Compustat customer segments 2012-2023, linked firms are any CRSP common stock with a CIK (3,779
companies). **widened, no +90d rows** = the same without Compustat rows dated by datadate + 90 days.

## 1. Name-match audit (before scoring)

60 resolved Compustat customer-name matches, fixed seed, stratified (20 short or one-word names, 40 others),
each checked against the customer's identity, and against the seller's 10-K where unclear.

| round | matching | correct | precision | short names | other names | weighted by population |
|---|---|---:|---:|---:|---:|---:|
| 1 | first version (index aliases, prefix matches) | {a1.get('correct')}/60 | {a1.get('precision_sample', 0):.1%} | {a1.get('precision_short', 0):.0%} | {a1.get('precision_other', 0):.1%} | {a1.get('precision_weighted_by_matches', 0):.1%} |
| 2 | strict: exact legal names only (new sample, seed + 1) | {a2.get('correct')}/60 | {a2.get('precision_sample', 0):.1%} | {a2.get('precision_short', 0):.0%} | {a2.get('precision_other', 0):.1%} | {a2.get('precision_weighted_by_matches', 0):.1%} |

Round 1 was below 90%. All nine errors were long names matched by prefix to a firm whose name reduces to one
generic word ("Super", "New", "TD", "Bank", "Classic", "Shenandoah"), or Compustat strings that name a defunct
namesake (Lionbridge's client "Philips" coded as Philips Industries). The graph was rebuilt with exact legal-name
matching: names compared after removing only the legal form (Inc, Corp, Co, Ltd, plc, ...), punctuation and
"the"; no prefix matches, no brand aliases, names pointing to more than one company dropped; a one-word name
only matches when written as a legal name ("Paccar Inc", not "Unum"). Sources: SEC current and former names,
Compustat names, CRSP historical names. The two round-2 errors are Compustat strings that point to the wrong
legal entity (a DuPont affiliate; a defunct firm sharing a retailer's name), which no name rule can catch.

Effect: Compustat rows resolved to a firm fell from 40,251 to {b.get('compseg_rows_by_kind', {}).get('named', 0):,}; correct subsidiary
matches were lost too (Janssen, OptumRx, Alcoa Power Generating). Skyworks -> Apple FY2018 is still in:
{sky18[0]['source'] if sky18 else 'n/a'}, share {sky18[0]['revenue_share'] if sky18 else 'n/a'}, usable from {sky18[0]['usable_from'] if sky18 else 'n/a'}.

## 2. The graphs

| | widened | widened, no +90d rows |
|---|---:|---:|
| Compustat company rows used | {b.get('compseg_company_rows', 0):,} | {bnf.get('compseg_company_rows', 0):,} |
| ... resolved to a firm / anonymous / unresolved | {b.get('compseg_rows_by_kind', {}).get('named', 0):,} / {b.get('compseg_rows_by_kind', {}).get('anonymous', 0):,} / {b.get('compseg_rows_by_kind', {}).get('unresolved', 0):,} | {bnf.get('compseg_rows_by_kind', {}).get('named', 0):,} / {bnf.get('compseg_rows_by_kind', {}).get('anonymous', 0):,} / {bnf.get('compseg_rows_by_kind', {}).get('unresolved', 0):,} |
| dated by the 10-K on EDGAR / by datadate + 90 | {b.get('compseg_pit_source', {}).get('edgar_10k', 0):,} / {b.get('compseg_pit_source', {}).get('datadate+90', 0):,} | {bnf.get('compseg_pit_source', {}).get('edgar_10k', 0):,} / 0 |
| named links in both sources / 10-K only / Compustat only | {b.get('named_links_both', 0):,} / {b.get('named_links_tenk_only', 0):,} / {b.get('named_links_compseg_only', 0):,} | {bnf.get('named_links_both', 0):,} / {bnf.get('named_links_tenk_only', 0):,} / {bnf.get('named_links_compseg_only', 0):,} |
| links in all | {b.get('links_total_wide', 0):,} | {bnf.get('links_total_wide', 0):,} |

("Compustat only" counts include unresolved customer names, which are dead ends in the graph.)

Links per year, strict widened graph:

{lpy}

Paths between priced firms in the year-end graphs 2015-2023:

{paths}

## 3. Power after cleaning (kept configuration of each arm, CAR [0,+5])

| | universe-only | widened | widened, no +90d rows |
|---|---:|---:|---:|
| kept configuration | {sel['crsp'].get('variant')} delta {sel['crsp'].get('delta')} H {sel['crsp'].get('H')} | {sel['wide'].get('variant')} delta {sel['wide'].get('delta')} H {sel['wide'].get('H')} | {sel['wide_nf'].get('variant')} delta {sel['wide_nf'].get('delta')} H {sel['wide_nf'].get('H')} |
| pairs with a CAR | {kc['crsp'].get('car_0_5', {}).get('pairs_with_car', 0):,} | {kc['wide'].get('car_0_5', {}).get('pairs_with_car', 0):,} | {kc['wide_nf'].get('car_0_5', {}).get('pairs_with_car', 0):,} |
| dropped, own 8-K/10-Q/10-K/earnings in window | {kc['crsp'].get('car_0_5', {}).get('dropped_contaminated', 0):,} | {kc['wide'].get('car_0_5', {}).get('dropped_contaminated', 0):,} | {kc['wide_nf'].get('car_0_5', {}).get('dropped_contaminated', 0):,} |
| dropped, overlap | {kc['crsp'].get('car_0_5', {}).get('dropped_overlap', 0):,} | {kc['wide'].get('car_0_5', {}).get('dropped_overlap', 0):,} | {kc['wide_nf'].get('car_0_5', {}).get('dropped_overlap', 0):,} |
| pairs used | {kc['crsp'].get('car_0_5', {}).get('pairs_used', 0):,} | {kc['wide'].get('car_0_5', {}).get('pairs_used', 0):,} | {kc['wide_nf'].get('car_0_5', {}).get('pairs_used', 0):,} |

## 4. Results side by side

Selection rule as before: best choosing-period MAE skill on [0,+5] plain CAR, then R2. "R2 gain" and "MAE skill"
are against B0 (predict zero). Per-event Spearman only for events with >= 5 linked firms.

### Kept configuration, CAR [0,+5]

{T['kept_car_0_5']}

### Kept configuration, CAR [+1,+20]

{T['kept_car_1_20']}

### Baselines on their own pairs, CAR [0,+5], plain

{T['base_car_0_5_plain']}

### Baselines on their own pairs, CAR [0,+5], industry-adjusted

{T['base_car_0_5_adj']}

### Every method on the kept model's own pairs, CAR [0,+5], plain

(A baseline predicts 0 where it has no prediction for a pair. B1 and B3 predict only a small share of the model's
pairs in the universe-only arm, so their numbers there rest on few pairs; the B1 slope t of 29 in the adjusted
table below is such an artefact.)

{T['h2h_car_0_5_plain']}

### Every method on the kept model's own pairs, CAR [0,+5], industry-adjusted

{T['h2h_car_0_5_adj']}

### Search: best of each variant and H, widened arm, CAR [0,+5] plain (all 120 runs in `search_wide.csv`)

{T.get('search_wide', '')}

Widened without +90d rows:

{T.get('search_wide_nf', '')}

## 5. Pre-registered weight tests (widened arm, M1, delta {sel['wide'].get('delta')}, CAR [0,+5])

Plain CAR:

{T['wt_wide_car_0_5_plain']}

Industry-adjusted CAR:

{T['wt_wide_car_0_5_adj']}

The same 45 runs without the +90d rows are in `weight_tests_wide_nf.csv` (and below, plain CAR):

{T['wt_wide_nf_car_0_5_plain']}

## 6. What the widening shows

- Power: about nine times the usable pairs ({kc['wide'].get('car_0_5', {}).get('pairs_used', 0):,} against {kc['crsp'].get('car_0_5', {}).get('pairs_used', 0):,} for [0,+5]), 300 fitting-period
  events with five or more linked firms, and hundreds of two- and three-hop paths.
- With that power the [0,+5] effect on plain CAR is statistically there in both periods (slope t 2.45 fitting,
  2.08 choosing; pooled Spearman 0.087 and 0.111) but economically small: R2 rises by 0.2 to 0.4 points and the
  error against predicting zero falls by 0.2 to 0.4%.
- It does not hold up as a supply-chain effect beyond industry: on the industry-adjusted CAR the fitting-period
  slope t is 1.15 (choosing 1.84), and under the earnings-only contamination rule it falls to about 0. On plain
  CAR the earnings-only rule leaves fitting t 1.0.
- The signal is the seed's sign, not the weights. Scored within negative shocks only or within positive shocks
  only, the share-weighted model has no slope t above 1.4 in either period (H = 1: pooled Spearman 0.035 fitting
  and 0.036 choosing for negative shocks, -0.009 and 0.079 for positive ones). Knowing a firm is linked tells you
  it tends to move with the customer; the revenue share does not tell you by how much.
- Weights: revenue share is slightly better than a binary link (choosing Spearman 0.111 vs 0.094); multiplying by
  (buyer cap / seller cap)^beta makes it worse for beta 0.5 and 1. The unweighted neighbour baseline B2 is level
  with the model on the model's own pairs.
- Hops: with real paths now, H = 2 and 3 still do not beat H = 1 (Spearman falls from 0.087 to 0.075 fitting).
  M1, M2 and M3 are the same at H = 1; at H >= 3 M3 is a little worse.
- No drift: over [+1,+20] the widened model has slope t 0.48 fitting and 0.53 choosing.
- Baselines on their own samples: B3 (20 most correlated stocks) is the strongest on plain CAR in the widened arm
  (t 6.1 and 5.3) and B1 (industry) in the universe-only arm. After the industry adjustment B1 goes to zero (as it
  must) and B3 shrinks to Spearman 0.03-0.06 (t about 2.7-3.0 on its 28,000 and 9,000 pairs). On the model's own
  pairs neither beats the model.
- The datadate + 90 rows do not drive anything: dropping them changes every number by a few hundredths.

## 7. Notes and limits

- Prices exist for index firms and for the Compustat sellers; customers outside both are unpriced nodes. Linked
  firms are suppliers, so this covers what is scored.
- Compustat customer names are free text; after tightening, precision is about 97% but recall is lower (subsidiary
  and brand names no longer match). 33,909 rows stay unresolved, mostly foreign or private customers.
- Revenue share = salecs / sale; 28% of Compustat rows have no share (missing salecs or sale) and use the
  engine's undisclosed-share formula (beta 0).
- The 10-K text graph (universe sellers) keeps its own matching (91% confirmed by Compustat in Stage 1).
- Universe-only results here use crsp.dsi and historical GICS; they differ from the first Stage 1 report in the
  third decimal (events 7,631 instead of 7,636).
"""
    (OUT / "widening_summary.md").write_text(md)
    print(md[:2500])


if __name__ == "__main__":
    main()
