# Stage 1 checkpoint after step 4 (before any model scoring)

Nothing dated 2024-01-01 or later was loaded. No model, baseline or parameter search has been run.

## Seed graph (10-Ks accepted 2015-2023)

| | |
|---|---|
| 10-K filings read | 4,747 (536 universe companies plus 13 predecessor registrants) |
| 10-Ks with a customer disclosure | 1,500 |
| Links | 2,881 (named 1,900, anonymous 981) |
| Links with a stated share (DISCLOSED) | 2,613; named without a share (STATED) 268 |
| Links with both ends priced universe firms | 1,047 (247 distinct seller-buyer pairs) |
| Sellers with any link | 263 |

Links per year (by 10-K acceptance year): see `seed_links_per_year.csv`.

| year | links | sellers | named | with share | from XBRL |
|---|---|---|---|---|---|
| 2015 | 270 | 134 | 172 | 247 | 132 |
| 2016 | 261 | 142 | 167 | 240 | 126 |
| 2017 | 285 | 146 | 185 | 249 | 147 |
| 2018 | 291 | 150 | 192 | 258 | 159 |
| 2019 | 297 | 155 | 201 | 265 | 150 |
| 2020 | 360 | 185 | 241 | 333 | 149 |
| 2021 | 374 | 196 | 255 | 337 | 169 |
| 2022 | 378 | 199 | 248 | 346 | 199 |
| 2023 | 365 | 190 | 239 | 338 | 198 |

Cross-check against the Oct 2026 snapshot (not used to build anything): of 94 disclosed-share
pairs between universe firms in `data/graph.json`, 62 are found in our 2022-23 10-Ks, usually with
almost the same share. Most misses are small REIT tenant shares (1-3%) that are not 10% customer
disclosures. See `seed_crosscheck_2026.csv` and `seed_sample_for_review.csv`.

## Event panel (E2)

| | |
|---|---|
| Stock-days in the index with a valid FF3 fit | 869,732 |
| abs(z) >= 3 | 16,583 |
| and an 8-K / 10-Q / 10-K within one trading day | 7,998 |
| and abs(S&P 500 return) <= 2% | **6,710 events** |
| fitting period (2016-01 to 2021-12) | 5,012 |
| choosing period (2022-01 to 2023-12) | 1,698 |
| negative / positive | 3,414 / 3,296 |
| with an earnings filing in the window | 5,471 |

## Power (amendment 11 and 12)

| | fitting | choosing | total |
|---|---|---|---|
| events with at least one linked universe firm (1 hop) | | | 675 |
| event-firm pairs, 1 hop | 1,046 | 358 | 1,404 |
| event-firm pairs, up to 4 hops | | | 1,685 |
| pairs left after dropping firms with any own 8-K/earnings in [0,+5] | 590 | 211 | 801 |
| pairs left after dropping firms with any own 8-K/earnings in [+1,+20] | 261 | 97 | 358 |
| same, earnings filings only, [0,+5] | 755 | 247 | 1,002 |
| same, earnings filings only, [+1,+20] | 553 | 174 | 727 |

Median linked firms per event (events with any): 1. Very few events have the 5 linked firms
amendment 5 needs for a per-event Spearman, so the pooled numbers carry the result.

After the contamination rule the universe-only test is below about 1,000 pairs, so amendment 12
applies: widen the seller side. Not started; waiting for a go-ahead because it is a much larger
data pull.

## Survivorship

126 of 688 index tickers (18.3%) in 2016-2023 have no usable Yahoo prices; 11.4% of index
member-days are lost. They are firms acquired or delisted, including ~20 acquired between 2024
and 2026 (PXD, HES, JNPR, ANSS, DFS, ...), whose history Yahoo has also removed.

## Decisions made so far

- SEC `acceptanceDateTime` is true UTC (Apple 8-K of 2 Jan 2019: 21:30:03Z in the API, 16:30:03 on
  the EDGAR index page). Converted to New York time; after-16:00 filings go to the next trading day.
  Apple's letter maps to 3 Jan 2019 (unit test).
- Holding-company reorganisations (Exxon, BlackRock, Bunge, Apache, Avago/Broadcom, Cigna, Disney,
  Google, HollyFrontier, Medtronic, Xerox, Navient) are merged into one company across the CIK change.
  Tickers reused by a different company (ADT, SE, STI, TE, NE, old DOW/DD) are rejected.
- Membership ticker IR before 2020-03-02 is Ingersoll-Rand plc (now TT), not Gardner Denver.
- Tiers: share stated in the 10-K (XBRL or text) = DISCLOSED; customer named without a share = STATED.
- Customers later bought by a universe firm are mapped to the parent after the deal (Express Scripts ->
  Cigna from Dec 2018, Aetna -> CVS, Sprint -> T-Mobile, Celgene -> BMY, Allergan -> AbbVie).
