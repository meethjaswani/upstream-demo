"""Writes results/stage1_summary.md from the result files."""
import json

import numpy as np
import pandas as pd

from . import seed_graph
from .config import RESULTS

COLS = [("n_pairs", "pairs", "{:,.0f}"), ("spearman_pooled", "Spearman (pooled)", "{:.3f}"),
        ("spearman_event_mean", "Spearman (per event)", "{:.3f}"), ("n_events_5plus", "events >=5", "{:.0f}"),
        ("hit_rate", "hit rate", "{:.2f}"), ("reg_t", "slope t", "{:.2f}"), ("r2_gain", "R2 gain vs B0", "{:.3f}"),
        ("mae_skill", "MAE skill vs B0", "{:.4f}")]


def fmt(v, f):
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else f.format(v)


def table(df, window, label_col="label"):
    out = ["| method | outcome | period | " + " | ".join(c[1] for c in COLS) + " |",
           "|---|---|---|" + "---:|" * len(COLS)]
    d = df[df["window"] == window]
    for _, r in d.iterrows():
        out.append(f"| {r[label_col]} | {r['outcome']} | {r['period']} | " +
                   " | ".join(fmt(r.get(c), f) for c, _, f in COLS) + " |")
    return "\n".join(out)


def main():
    sel = json.loads((RESULTS / "selected_crsp.json").read_text())
    ck = {a: json.loads((RESULTS / f"checkpoint_step4_{a}.json").read_text()) for a in ("crsp", "yahoo")}
    S = pd.read_csv(RESULTS / "search_crsp.csv")
    B = pd.read_csv(RESULTS / "baselines_crsp.csv")
    K = pd.read_csv(RESULTS / "kept_config.csv")
    H = pd.read_csv(RESULTS / "head_to_head_crsp.csv")
    HY = pd.read_csv(RESULTS / "head_to_head_yahoo.csv")
    kc = json.loads((RESULTS / "kept_counts_crsp.json").read_text())
    e3 = {a: json.loads((RESULTS / f"e3_{a}.json").read_text()) for a in ("crsp", "yahoo")}
    e4 = json.loads((RESULTS / "e4_apple_crsp.json").read_text())
    seg = json.loads((RESULTS / "seg_customer_crosscheck.json").read_text())
    links, ti = seed_graph.load()
    py = seed_graph.per_year(links)
    py.to_csv(RESULTS / "seed_links_per_year.csv")
    trials = sum(1 for _ in open(RESULTS / "trial_log.csv")) - 1

    # best configuration per variant (same selection rule)
    key = S[(S["window"] == "car_0_5") & (S["outcome"] == "plain") & (S["period"] == "choose")]
    rows = []
    for v in ("M1", "M2", "M3"):
        b = key[key["variant"] == v].sort_values(["mae_skill", "r2"], ascending=False).iloc[0]
        sub = S[(S["variant"] == v) & (S["delta"] == b["delta"]) & (S["H"] == b["H"])].copy()
        sub["label"] = f"{v} (delta {b['delta']}, H {int(b['H'])}, 1k runs)" if v == "M3" else \
            f"{v} (delta {b['delta']}, H {int(b['H'])})"
        rows.append(sub)
    kept = K[(K["arm"] == "crsp") & (K["contamination"] == "any")].copy()
    kept["label"] = f"**kept {sel['variant']}** (delta {sel['delta']}, H {sel['H']}, 10k runs)"
    base = B.copy()
    base["label"] = base["method"].map({"B1_industry": "B1 same sub-industry", "B2_neighbours": "B2 direct neighbours",
                                        "B3_correlated": "B3 20 most correlated"})
    T = pd.concat(rows + [kept, base], ignore_index=True)
    h = H.copy()
    h["label"] = h["method"].map(lambda m: "kept model" if m.startswith("kept") else
                                 {"B1_industry": "B1", "B2_neighbours": "B2", "B3_correlated": "B3"}[m])
    hy = HY.copy()
    hy["label"] = hy["method"].map(lambda m: "kept model" if m.startswith("kept") else
                                   {"B1_industry": "B1", "B2_neighbours": "B2", "B3_correlated": "B3"}[m])
    rob = K[(K["contamination"] != "any") | (K["arm"] != "crsp")].copy()
    rob["label"] = rob["arm"] + ", contamination " + rob["contamination"]

    def g(arm, w, o, p, m, df=K, cont="any"):
        x = df[(df["arm"] == arm) & (df["contamination"] == cont) & (df["window"] == w) & (df["outcome"] == o)
               & (df["period"] == p)]
        return float(x[m].iloc[0]) if len(x) else float("nan")

    c, y = ck["crsp"], ck["yahoo"]
    md = f"""# Upstream, Stage 1 backtest: summary

All numbers use data dated before 2024-01-01 only. Fitting period 2016-01 to 2021-12, choosing period 2022-01 to
2023-12; the 2024+ test period was never loaded. Headline arm: CRSP/Compustat. Yahoo arm reported alongside.
{trials} rows in the trial log (`trial_log.csv`), every configuration and every baseline included.

## Power (amendment 11)

| | CRSP | Yahoo |
|---|---:|---:|
| Events (fitting / choosing) | {c['events_total']:,} ({c['events_by_period']['fit']:,} / {c['events_by_period']['choose']:,}) | {y['events_total']:,} ({y['events_by_period']['fit']:,} / {y['events_by_period']['choose']:,}) |
| Events with a linked firm (1 hop) | {c['events_with_linked_h1']:,} | {y['events_with_linked_h1']:,} |
| Event-firm pairs, 1 hop, before cleaning | {c['event_firm_pairs_h1']:,} | {y['event_firm_pairs_h1']:,} |
| Pairs used by the kept model, [0,+5] (after amendments 3 and 4) | {kc['car_0_5']['pairs_used']:,} | {int(g('yahoo','car_0_5','plain','fit','n_pairs') + g('yahoo','car_0_5','plain','choose','n_pairs')):,} |
| Pairs used by the kept model, [+1,+20] | {kc['car_1_20']['pairs_used']:,} | {int(g('yahoo','car_1_20','plain','fit','n_pairs') + g('yahoo','car_1_20','plain','choose','n_pairs')):,} |
| Median linked firms per event (events with any) | {c['median_linked_h1_given_any']:.0f} | {y['median_linked_h1_given_any']:.0f} |
| Events with >= 5 linked firms | {c['events_with_5plus_linked_h1']} | {y['events_with_5plus_linked_h1']} |
| Seed links, both ends in the universe | {c['seed_links_both_ends_in_universe']:,} | {y['seed_links_both_ends_in_universe']:,} |
| Share of index member-days without a return, 2016-2023 | {c['survivorship']['share_member_days_without_returns']:.1%} | {y['survivorship']['share_member_days_without_prices']:.1%} |
| Share of index tickers with no prices at all | 0% (CRSP) | {y['survivorship']['share_tickers_without_prices']:.1%} |

Kept model, [0,+5]: of {kc['car_0_5']['pairs_with_car']:,} pairs with a CAR, {kc['car_0_5']['dropped_contaminated']:,} were
dropped because the linked firm had its own 8-K, 10-Q, 10-K or earnings day in the window (amendment 3) and
{kc['car_0_5']['dropped_overlap']:,} by the overlap rule (amendment 4). For [+1,+20]: {kc['car_1_20']['dropped_contaminated']:,}
and {kc['car_1_20']['dropped_overlap']:,}. The choosing period has only
{int(g('crsp','car_0_5','plain','choose','n_pairs'))} usable pairs for [0,+5] and {int(g('crsp','car_1_20','plain','choose','n_pairs'))} for [+1,+20]: the test is weak (amendment 12), see "Not done".

Seed links per year (10-K acceptance year; 3,544 links in all, from 10-Ks of the CRSP index members):

| year | links | sellers | named | with share | from XBRL |
|---|---:|---:|---:|---:|---:|
""" + "\n".join(f"| {i} | {r.links} | {r.sellers} | {r.named} | {r.with_share} | {r.xbrl} |" for i, r in py.iterrows()) + f"""

## Results, CRSP arm, every variant and baseline

Each variant at its best configuration under the selection rule (full grid of 120 in `search_crsp.csv`), the kept
configuration, and the baselines on their own pairs. B0 (zero for everyone) is the null inside "R2 gain vs B0" and
"MAE skill vs B0" (amendment 6). "outcome adj" = industry-adjusted CAR (amendment 8). Per-event Spearman only for
events with >= 5 linked firms (amendment 5); B1 and B2 give every firm in an event the same prediction, so they have
no within-event ranking. At H = 1 delta only rescales the prediction, which lambda undoes, so every delta gives the
same M1/M2 result; the table shows the first.

### CAR [0,+5]

{table(T, 'car_0_5')}

### CAR [+1,+20]

{table(T, 'car_1_20')}

### Head to head on the model's own pairs (choosing and fitting periods)

Every method scored on exactly the kept model's cleaned event-firm pairs; a baseline with no prediction for a
pair predicts 0 there (hit rate then counts that pair as a miss, so read Spearman, R2 and MAE).

CRSP:

{table(h, 'car_0_5')}

Yahoo:

{table(hy, 'car_0_5')}

### Robustness of the kept configuration (Yahoo arm; earnings-only contamination rule)

{table(rob, 'car_0_5')}

## E3, customer momentum portfolio

Quintiles of firms by their customers' last-month return through the graph (delta {sel['delta']}, H {sel['H']}),
long top minus bottom next month, alpha on FF3 + momentum, Newey-West t.

| arm | period | weights | months | median firms | mean / month | alpha / month | alpha t |
|---|---|---|---:|---:|---:|---:|---:|
""" + "\n".join(f"| {a} | {k.split('_')[0]} | {k.split('_')[1]} | {v['months']} | {v['median_firms']:.0f} | {v['mean_monthly']:.2%} | {v['alpha_monthly']:.2%} | {v['alpha_t']:.2f} |"
                for a in ("crsp", "yahoo") for k, v in e3[a].items() if isinstance(v, dict)) + f"""

## E4, Apple guidance cut (illustration only)

Letter released after the close on 2 Jan 2019 (8-K accepted 16:30 ET), event day 3 Jan 2019. Not in the E2 panel
because the S&P 500 fell 2.5% that day. Apple AR {e4['apple_ar']:.1%} (z {e4['apple_z']:.1f}). The graph of 2 Jan 2019
links Apple to {e4['linked_firms']} priced suppliers; their mean CAR[0,+5] was {e4['linked_mean_car_0_5']:.1%}, against
{e4['b1_mean_car_0_5']:.1%} for Apple's sub-industry peers (B1) and {e4['b3_mean_car_0_5']:.1%} for its 20 most correlated
stocks (B3). Qorvo and Jabil fell as predicted; Activision and Akamai (app-store and network-service suppliers) rose.
Skyworks is missing: its FY2018 10-K tags Apple only as an anonymous customer (47%). Figure: `figures/e4_apple_replay.png`.

## What worked

- Point-in-time pipeline: graph from 10-Ks accepted before the event day, membership by date, acceptance times
  checked (SEC times are UTC), events dated from the New York clock; a guard raises on anything from 2024.
- The seed graph is accurate where it can be checked: 91% of our links to universe customers are also in
  Compustat's customer segments ({seg['universe_customers_in_both']} of {seg['universe_customers_ours']}).
- Over [0,+5] the kept model's predictions line up with linked firms' CARs in both periods and both arms (pooled
  Spearman {g('crsp','car_0_5','plain','fit','spearman_pooled'):.2f} fitting, {g('crsp','car_0_5','plain','choose','spearman_pooled'):.2f} choosing),
  and in the choosing period the relation survives the industry adjustment (Spearman {g('crsp','car_0_5','adj','choose','spearman_pooled'):.2f},
  slope t {g('crsp','car_0_5','adj','choose','reg_t'):.1f}, {int(g('crsp','car_0_5','adj','choose','n_pairs'))} pairs).
- CRSP removes the survivorship gap (0.4% of member-days missing against 11.5% on Yahoo); the Yahoo results are close.

## What did not work

- The effect is small and not robust across periods. Fitting period [0,+5]: slope t {g('crsp','car_0_5','plain','fit','reg_t'):.2f} plain,
  {g('crsp','car_0_5','adj','fit','reg_t'):.2f} industry-adjusted; MAE improves on B0 by only {g('crsp','car_0_5','plain','fit','mae_skill'):.2%}.
  The strong choosing-period industry-adjusted number rests on {int(g('crsp','car_0_5','adj','choose','n_pairs'))} pairs and is not matched in the fitting period.
- No drift: over [+1,+20] the slope is negative or indistinguishable from zero in every cut (CRSP fitting t
  {g('crsp','car_1_20','plain','fit','reg_t'):.2f}); lambda hits its floor of 0 in the main runs.
- The revenue-share weights add nothing clear. On the model's own pairs the unweighted neighbour baseline B2 is about
  as good: Spearman B2 {float(H[(H.method=='B2_neighbours')&(H.window=='car_0_5')&(H.outcome=='plain')&(H.period=='fit')]['spearman_pooled'].iloc[0]):.2f} vs model
  {float(H[(H.method.str.startswith('kept'))&(H.window=='car_0_5')&(H.outcome=='plain')&(H.period=='fit')]['spearman_pooled'].iloc[0]):.2f} in the fitting period and
  {float(H[(H.method=='B2_neighbours')&(H.window=='car_0_5')&(H.outcome=='plain')&(H.period=='choose')]['spearman_pooled'].iloc[0]):.2f} vs
  {float(H[(H.method.str.startswith('kept'))&(H.window=='car_0_5')&(H.outcome=='plain')&(H.period=='choose')]['spearman_pooled'].iloc[0]):.2f} in the choosing period,
  and B2 has the lower error (MAE) in both periods. The links carry the signal; the share weighting does not
  calibrate how much each linked firm moves.
- On plain CAR the industry and correlation baselines (B1, B3) are stronger on their own, much larger samples
  (B1 choosing slope t {float(B[(B.method=='B1_industry')&(B.window=='car_0_5')&(B.outcome=='plain')&(B.period=='choose')]['reg_t'].iloc[0]):.1f}); that signal is industry co-movement and disappears for B1 after the
  industry adjustment.
- Variant, delta and H do not matter. At one hop M1, M2 and M3 are the same model in expectation and delta is
  absorbed by lambda; H = 3, 4 and 6 give identical results because the graph has almost no multi-hop paths between
  priced firms. The rule picked {sel['variant']} over M1 at H = 1 on Monte Carlo noise of 1,000 runs, not on substance.
- E3 is null in both periods and arms (largest alpha t {max(v['alpha_t'] for a in e3 for v in e3[a].values() if isinstance(v, dict)):.2f}).

## Design decisions (amendments)

1. Event day from acceptance time: SEC `acceptanceDateTime` is true UTC (Apple 8-K 21:30:03Z = 16:30:03 ET on the
   EDGAR index page); converted to New York time; after 16:00 counts for the next trading day. Unit test on the
   Apple 8-K of 2 Jan 2019 -> 3 Jan 2019.
2. Signed shocks: the magnitude of the seed AR (capped at 1) is propagated and the seed's sign applied.
3. Contaminated firms: a linked firm with its own 8-K, 10-Q, 10-K or earnings day (Compustat rdq or the day after,
   CRSP arm) inside the CAR window is dropped; counts above. Earnings-only version reported as robustness.
4. Overlap: a firm inside two events' windows keeps the pair with the larger predicted exposure.
5. Per-event Spearman only for events with >= 5 linked firms; pooled Spearman and the regression are the headline.
6. B0 is not ranked; it is the null in the regression (controls only) and in the error metric (mean |CAR|).
7. Weights judged by rank correlation; delta, H and lambda by out-of-sample MAE and R2. lambda is fitted on the
   fitting period by least absolute deviation through the origin and floored at 0 (a negative lambda would reward a
   reversed sign). Selection: best choosing-period MAE skill on [0,+5] plain CAR, then R2.
8. Industry-adjusted CAR: minus the mean CAR of same GICS sub-industry firms not linked to the seed (not within 6
   hops downstream and not a direct customer), the firm itself and the seed excluded.
9. Search over variant, delta {{0.2..0.9}}, H {{1,2,3,4,6}} only; beta = 0, tier factors at their starting values.
10. M3 with 1,000 runs in the search and 10,000 for the kept configuration.
11. Power table at the top.
12. Widening: not done in this pass (see below). The raw 1-hop pair count is above 1,000, the cleaned count is not.

## Expectations

- E3: in the original customer-momentum study the effect was strongest in small, low-attention stocks. This test
  uses S&P 500 firms only, so a weak or null result is a plausible outcome; that is what we find.
- Yahoo prices miss delisted firms ({y['survivorship']['share_tickers_without_prices']:.0%} of index tickers here). Survivors are the firms
  that did not fail or get taken over, so the Yahoo sample over-represents firms whose later news was better. For this
  test that means fewer pairs, and spillovers from bad shocks measured mostly on firms that came through them, which
  biases the measured negative spillover towards zero. The CRSP arm, with delisting returns, has no such gap.

## Assumptions and things not done

- Not done: widening the seller side (amendment 12). Compustat customer segments name about 1,250 links a year from
  848 sellers outside the index, but only for fiscal years 2020-2023 in this export, and their CRSP prices are not
  in it. Needs a second WRDS pull (seg_customer from 2014, CCM links and crsp.dsf for those sellers).
- Not done: beta and the tier factors (Stage 2), the DeepSeek replay (closed period).
- Seed graph from 10-K text and XBRL only; Compustat lists more customers than we find (we find
  {seg['recall_of_compustat_universe_customers']:.0%} of the universe customers it lists, many of them below 10% of sales). Short
  names ("Caesars") and table layouts are the known misses. Exhibit 13 annual reports are not read.
- Tiers: share stated in the 10-K = DISCLOSED, named without a share = STATED; anonymous customers count only
  toward R_i. Customers later acquired by a universe firm are mapped to the parent after the deal date.
- GICS sub-industry is Compustat's current code (not historical) for both arms.
- The 2% market filter uses the S&P 500 index level (^GSPC); the export has no CRSP index file.
- Yahoo-arm market caps use SEC share counts and a public-float check for post-2023 splits (approximate for firms
  with large insider holdings); the CRSP arm uses CRSP price x shares.
- Holding-company changes (Exxon, BlackRock, Alphabet, Disney, Cigna and others) are merged into one company;
  tickers reused by another company are rejected.
- Only the CRSP arm was searched; the Yahoo arm uses the configuration chosen on CRSP.
"""
    (RESULTS / "stage1_summary.md").write_text(md)
    print(md[:3000])


if __name__ == "__main__":
    main()
