# Widening (amendment 12): universe-only vs widened

Fitting 2016-2021 and choosing 2022-2023 only; nothing from 2024 was loaded. Both CRSP arms use crsp.dsi
sprtrn for the 2% market filter and historical GICS (comp.co_hgic) for industry, so the universe-only numbers
here differ slightly from the first Stage 1 report. Seeds are the same 7,631 E2 events at index firms in every
arm. 1212 rows in the trial log; the weight tests were written into it before any widened-arm scoring.

Arms: **universe-only** = 10-K graph, linked firms are index members (704 companies). **widened** = 10-K graph
plus Compustat customer segments 2012-2023, linked firms are any CRSP common stock with a CIK (3,779
companies). **widened, no +90d rows** = the same without Compustat rows dated by datadate + 90 days.

## 1. Name-match audit (before scoring)

60 resolved Compustat customer-name matches, fixed seed, stratified (20 short or one-word names, 40 others),
each checked against the customer's identity, and against the seller's 10-K where unclear.

| round | matching | correct | precision | short names | other names | weighted by population |
|---|---|---:|---:|---:|---:|---:|
| 1 | first version (index aliases, prefix matches) | 51/60 | 85.0% | 100% | 77.5% | 83.6% |
| 2 | strict: exact legal names only (new sample, seed + 1) | 58/60 | 96.7% | 100% | 95.0% | 96.9% |

Round 1 was below 90%. All nine errors were long names matched by prefix to a firm whose name reduces to one
generic word ("Super", "New", "TD", "Bank", "Classic", "Shenandoah"), or Compustat strings that name a defunct
namesake (Lionbridge's client "Philips" coded as Philips Industries). The graph was rebuilt with exact legal-name
matching: names compared after removing only the legal form (Inc, Corp, Co, Ltd, plc, ...), punctuation and
"the"; no prefix matches, no brand aliases, names pointing to more than one company dropped; a one-word name
only matches when written as a legal name ("Paccar Inc", not "Unum"). Sources: SEC current and former names,
Compustat names, CRSP historical names. The two round-2 errors are Compustat strings that point to the wrong
legal entity (a DuPont affiliate; a defunct firm sharing a retailer's name), which no name rule can catch.

Effect: Compustat rows resolved to a firm fell from 40,251 to 31,320; correct subsidiary
matches were lost too (Janssen, OptumRx, Alcoa Power Generating). Skyworks -> Apple FY2018 is still in:
compseg, share 0.47, usable from 2018-11-14 18:44:35.

## 2. The graphs

| | widened | widened, no +90d rows |
|---|---:|---:|
| Compustat company rows used | 98,669 | 74,629 |
| ... resolved to a firm / anonymous / unresolved | 31,320 / 33,440 / 33,909 | 26,331 / 23,596 / 24,702 |
| dated by the 10-K on EDGAR / by datadate + 90 | 74,629 / 24,040 | 74,629 / 0 |
| named links in both sources / 10-K only / Compustat only | 910 / 1,487 / 64,319 | 910 / 1,487 / 50,123 |
| links in all | 100,433 | 76,393 |

("Compustat only" counts include unresolved customer names, which are dead ends in the graph.)

Links per year, strict widened graph:

| year | universe-only | widened | both sources | Compustat only | 10-K only |
|---|---:|---:|---:|---:|---:|
| 2015 | 344 | 9,616 | 82 | 9,270 | 264 |
| 2016 | 336 | 9,488 | 83 | 9,150 | 255 |
| 2017 | 357 | 9,182 | 89 | 8,823 | 270 |
| 2018 | 363 | 8,941 | 87 | 8,576 | 278 |
| 2019 | 363 | 8,630 | 98 | 8,265 | 267 |
| 2020 | 447 | 8,451 | 116 | 8,002 | 333 |
| 2021 | 449 | 8,411 | 126 | 7,960 | 325 |
| 2022 | 448 | 8,340 | 113 | 7,891 | 336 |
| 2023 | 437 | 8,363 | 116 | 7,925 | 322 |

Paths between priced firms in the year-end graphs 2015-2023:

| arm | direct links | 2-hop paths | 3-hop paths |
|---|---:|---:|---:|
| universe-only | 120-172 | 13-70 | 5-18 |
| widened | 1,016-1,249 | 580-727 | 446-783 |
| widened, no +90d rows | 1,002-1,175 | 500-624 | 370-587 |

## 3. Power after cleaning (kept configuration of each arm, CAR [0,+5])

| | universe-only | widened | widened, no +90d rows |
|---|---:|---:|---:|
| kept configuration | M3 delta 0.7 H 1 | M1 delta 0.3 H 1 | M1 delta 0.2 H 1 |
| pairs with a CAR | 1,624 | 14,106 | 13,884 |
| dropped, own 8-K/10-Q/10-K/earnings in window | 721 | 5,799 | 5,724 |
| dropped, overlap | 122 | 1,399 | 1,378 |
| pairs used | 781 | 6,908 | 6,782 |

## 4. Results side by side

Selection rule as before: best choosing-period MAE skill on [0,+5] plain CAR, then R2. "R2 gain" and "MAE skill"
are against B0 (predict zero). Per-event Spearman only for events with >= 5 linked firms.

### Kept configuration, CAR [0,+5]

| arm | config | outcome | period | pairs | Spearman | per-event Spearman | events>=5 | hit | slope t | R2 gain | MAE skill |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| universe-only | M3 d0.7 H1 | plain | fit | 578 | 0.157 | 0.128 | 14 | 0.57 | 1.28 | 0.006 | 0.0035 |
| universe-only | M3 d0.7 H1 | plain | choose | 203 | 0.121 | -0.014 | 6 | 0.52 | 1.94 | 0.021 | 0.0016 |
| universe-only | M3 d0.7 H1 | adj | fit | 525 | 0.079 | 0.141 | 13 | 0.51 | 1.25 | 0.003 | 0.0028 |
| universe-only | M3 d0.7 H1 | adj | choose | 137 | 0.336 | 0.152 | 5 | 0.64 | 2.64 | 0.054 | 0.0124 |
| widened | M1 d0.3 H1 | plain | fit | 5,326 | 0.087 | 0.054 | 305 | 0.55 | 2.45 | 0.002 | 0.0022 |
| widened | M1 d0.3 H1 | plain | choose | 1,582 | 0.111 | 0.088 | 82 | 0.54 | 2.08 | 0.004 | 0.0037 |
| widened | M1 d0.3 H1 | adj | fit | 5,291 | 0.035 | 0.039 | 305 | 0.52 | 1.15 | 0.001 | 0.0003 |
| widened | M1 d0.3 H1 | adj | choose | 1,557 | 0.094 | 0.043 | 81 | 0.53 | 1.84 | 0.003 | 0.0015 |
| widened, no +90d rows | M1 d0.2 H1 | plain | fit | 5,217 | 0.089 | 0.042 | 299 | 0.55 | 2.41 | 0.002 | 0.0023 |
| widened, no +90d rows | M1 d0.2 H1 | plain | choose | 1,565 | 0.106 | 0.089 | 82 | 0.53 | 2.00 | 0.004 | 0.0033 |
| widened, no +90d rows | M1 d0.2 H1 | adj | fit | 5,182 | 0.037 | 0.030 | 299 | 0.52 | 1.15 | 0.001 | 0.0003 |
| widened, no +90d rows | M1 d0.2 H1 | adj | choose | 1,540 | 0.090 | 0.045 | 81 | 0.53 | 1.79 | 0.003 | 0.0015 |

### Kept configuration, CAR [+1,+20]

| arm | config | outcome | period | pairs | Spearman | per-event Spearman | events>=5 | hit | slope t | R2 gain | MAE skill |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| universe-only | M3 d0.7 H1 | plain | fit | 251 | -0.118 | 0.109 | 7 | 0.45 | -1.57 | 0.016 | 0.0000 |
| universe-only | M3 d0.7 H1 | plain | choose | 89 | -0.091 | 0.057 | 4 | 0.46 | -0.22 | 0.001 | 0.0000 |
| universe-only | M3 d0.7 H1 | adj | fit | 225 | -0.108 | -0.029 | 7 | 0.47 | -1.43 | 0.015 | 0.0000 |
| universe-only | M3 d0.7 H1 | adj | choose | 61 | -0.103 | 0.600 | 1 | 0.39 | -0.64 | 0.006 | 0.0000 |
| widened | M1 d0.3 H1 | plain | fit | 2,146 | -0.008 | -0.020 | 96 | 0.51 | 0.48 | 0.000 | 0.0000 |
| widened | M1 d0.3 H1 | plain | choose | 651 | 0.072 | 0.043 | 30 | 0.53 | 0.53 | 0.000 | 0.0009 |
| widened | M1 d0.3 H1 | adj | fit | 2,132 | -0.012 | -0.052 | 96 | 0.50 | -0.02 | 0.000 | 0.0000 |
| widened | M1 d0.3 H1 | adj | choose | 642 | 0.105 | 0.112 | 30 | 0.54 | 1.05 | 0.001 | 0.0000 |
| widened, no +90d rows | M1 d0.2 H1 | plain | fit | 2,076 | 0.001 | -0.026 | 91 | 0.52 | 0.68 | 0.000 | 0.0002 |
| widened, no +90d rows | M1 d0.2 H1 | plain | choose | 638 | 0.073 | 0.058 | 30 | 0.53 | 0.63 | 0.001 | 0.0016 |
| widened, no +90d rows | M1 d0.2 H1 | adj | fit | 2,062 | -0.004 | -0.057 | 91 | 0.50 | 0.23 | 0.000 | 0.0000 |
| widened, no +90d rows | M1 d0.2 H1 | adj | choose | 629 | 0.103 | 0.119 | 30 | 0.53 | 1.08 | 0.002 | 0.0000 |

### Baselines on their own pairs, CAR [0,+5], plain

| arm | method | period | pairs | Spearman | per-event Spearman | events>=5 | hit | slope t | R2 gain | MAE skill |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| universe-only | B1_industry | fit | 10,482 | 0.181 |  | 0 | 0.59 | 7.80 | 0.030 | 0.0128 |
| universe-only | B1_industry | choose | 3,611 | 0.214 |  | 0 | 0.62 | 4.14 | 0.072 | 0.0210 |
| universe-only | B2_neighbours | fit | 1,099 | 0.135 |  | 0 | 0.57 | 3.16 | 0.012 | 0.0081 |
| universe-only | B2_neighbours | choose | 344 | 0.088 |  | 0 | 0.53 | 2.04 | 0.014 | 0.0044 |
| universe-only | B3_correlated | fit | 22,648 | 0.110 | 0.071 | 1,888 | 0.55 | 5.00 | 0.020 | 0.0041 |
| universe-only | B3_correlated | choose | 7,800 | 0.148 | 0.074 | 645 | 0.56 | 4.23 | 0.034 | 0.0080 |
| widened | B1_industry | fit | 57,420 | 0.091 |  | 0 | 0.55 | 6.24 | 0.004 | 0.0037 |
| widened | B1_industry | choose | 20,889 | 0.050 |  | 0 | 0.54 | 0.66 | 0.000 | 0.0013 |
| widened | B2_neighbours | fit | 6,415 | 0.083 |  | 0 | 0.55 | 2.67 | 0.003 | 0.0034 |
| widened | B2_neighbours | choose | 1,982 | 0.081 |  | 0 | 0.53 | 1.90 | 0.002 | 0.0012 |
| widened | B3_correlated | fit | 28,415 | 0.135 | 0.061 | 2,450 | 0.55 | 6.14 | 0.025 | 0.0063 |
| widened | B3_correlated | choose | 9,431 | 0.162 | 0.072 | 761 | 0.57 | 5.30 | 0.030 | 0.0095 |
| widened, no +90d rows | B1_industry | fit | 57,420 | 0.091 |  | 0 | 0.55 | 6.24 | 0.004 | 0.0037 |
| widened, no +90d rows | B1_industry | choose | 20,889 | 0.050 |  | 0 | 0.54 | 0.66 | 0.000 | 0.0013 |
| widened, no +90d rows | B2_neighbours | fit | 6,297 | 0.085 |  | 0 | 0.55 | 2.63 | 0.003 | 0.0034 |
| widened, no +90d rows | B2_neighbours | choose | 1,964 | 0.076 |  | 0 | 0.53 | 1.79 | 0.002 | 0.0008 |
| widened, no +90d rows | B3_correlated | fit | 28,415 | 0.135 | 0.061 | 2,450 | 0.55 | 6.14 | 0.025 | 0.0063 |
| widened, no +90d rows | B3_correlated | choose | 9,431 | 0.162 | 0.072 | 761 | 0.57 | 5.30 | 0.030 | 0.0095 |

### Baselines on their own pairs, CAR [0,+5], industry-adjusted

| arm | method | period | pairs | Spearman | per-event Spearman | events>=5 | hit | slope t | R2 gain | MAE skill |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| universe-only | B1_industry | fit | 10,246 | -0.013 |  | 0 | 0.50 | 0.19 | 0.000 | 0.0000 |
| universe-only | B1_industry | choose | 3,534 | -0.011 |  | 0 | 0.49 | -0.28 | 0.000 | 0.0000 |
| universe-only | B2_neighbours | fit | 993 | 0.060 |  | 0 | 0.51 | 1.37 | 0.002 | 0.0016 |
| universe-only | B2_neighbours | choose | 258 | 0.061 |  | 0 | 0.57 | 1.32 | 0.009 | 0.0044 |
| universe-only | B3_correlated | fit | 21,283 | 0.019 | 0.020 | 1,767 | 0.51 | 2.07 | 0.001 | 0.0001 |
| universe-only | B3_correlated | choose | 7,271 | 0.031 | 0.026 | 603 | 0.52 | 2.16 | 0.002 | 0.0004 |
| widened | B1_industry | fit | 57,351 | -0.022 |  | 0 | 0.49 | -2.51 | 0.000 | 0.0000 |
| widened | B1_industry | choose | 20,866 | 0.017 |  | 0 | 0.51 | -1.08 | 0.000 | 0.0000 |
| widened | B2_neighbours | fit | 6,333 | 0.033 |  | 0 | 0.52 | 1.17 | 0.001 | 0.0005 |
| widened | B2_neighbours | choose | 1,949 | 0.078 |  | 0 | 0.52 | 1.32 | 0.001 | 0.0015 |
| widened | B3_correlated | fit | 28,187 | 0.028 | 0.025 | 2,434 | 0.51 | 2.70 | 0.002 | 0.0002 |
| widened | B3_correlated | choose | 9,269 | 0.056 | 0.034 | 754 | 0.52 | 2.98 | 0.004 | 0.0005 |
| widened, no +90d rows | B1_industry | fit | 57,351 | -0.022 |  | 0 | 0.49 | -2.53 | 0.000 | 0.0000 |
| widened, no +90d rows | B1_industry | choose | 20,866 | 0.017 |  | 0 | 0.51 | -1.09 | 0.000 | 0.0000 |
| widened, no +90d rows | B2_neighbours | fit | 6,215 | 0.033 |  | 0 | 0.52 | 1.05 | 0.001 | 0.0004 |
| widened, no +90d rows | B2_neighbours | choose | 1,931 | 0.075 |  | 0 | 0.52 | 1.22 | 0.001 | 0.0012 |
| widened, no +90d rows | B3_correlated | fit | 28,187 | 0.028 | 0.025 | 2,434 | 0.51 | 2.70 | 0.002 | 0.0002 |
| widened, no +90d rows | B3_correlated | choose | 9,269 | 0.056 | 0.034 | 754 | 0.52 | 2.98 | 0.004 | 0.0005 |

### Every method on the kept model's own pairs, CAR [0,+5], plain

(A baseline predicts 0 where it has no prediction for a pair. B1 and B3 predict only a small share of the model's
pairs in the universe-only arm, so their numbers there rest on few pairs; the B1 slope t of 29 in the adjusted
table below is such an artefact.)

| arm | method | period | pairs | Spearman | per-event Spearman | events>=5 | slope t | R2 gain | MAE skill |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| universe-only | kept_M3 | fit | 578 | 0.157 | 0.128 | 14 | 1.28 | 0.006 | 0.0035 |
| universe-only | kept_M3 | choose | 203 | 0.121 | -0.014 | 6 | 1.94 | 0.021 | 0.0016 |
| universe-only | B1_industry | fit | 578 | 0.057 |  | 0 | -0.08 | 0.000 | 0.0013 |
| universe-only | B1_industry | choose | 203 | 0.091 |  | 0 | 2.38 | 0.001 | 0.0010 |
| universe-only | B2_neighbours | fit | 578 | 0.164 |  | 0 | 1.95 | 0.011 | 0.0142 |
| universe-only | B2_neighbours | choose | 203 | 0.093 |  | 0 | 1.74 | 0.019 | 0.0031 |
| universe-only | B3_correlated | fit | 578 | 0.053 | 0.106 | 10 | 1.37 | 0.001 | 0.0025 |
| universe-only | B3_correlated | choose | 203 | 0.156 | -0.179 | 5 | 2.03 | 0.015 | 0.0049 |
| widened | kept_M1 | fit | 5,326 | 0.087 | 0.054 | 305 | 2.45 | 0.002 | 0.0022 |
| widened | kept_M1 | choose | 1,582 | 0.111 | 0.088 | 82 | 2.08 | 0.004 | 0.0037 |
| widened | B1_industry | fit | 5,326 | 0.077 | 0.094 | 99 | 2.83 | 0.003 | 0.0017 |
| widened | B1_industry | choose | 1,582 | 0.048 | -0.004 | 26 | 1.10 | 0.001 | 0.0016 |
| widened | B2_neighbours | fit | 5,326 | 0.084 |  | 0 | 2.10 | 0.002 | 0.0039 |
| widened | B2_neighbours | choose | 1,582 | 0.103 |  | 0 | 2.22 | 0.004 | 0.0023 |
| widened | B3_correlated | fit | 5,326 | 0.053 | 0.024 | 131 | 1.21 | 0.001 | 0.0013 |
| widened | B3_correlated | choose | 1,582 | 0.055 | -0.072 | 35 | 2.50 | 0.001 | 0.0010 |
| widened, no +90d rows | kept_M1 | fit | 5,217 | 0.089 | 0.042 | 299 | 2.41 | 0.002 | 0.0023 |
| widened, no +90d rows | kept_M1 | choose | 1,565 | 0.106 | 0.089 | 82 | 2.00 | 0.004 | 0.0033 |
| widened, no +90d rows | B1_industry | fit | 5,217 | 0.076 | 0.080 | 97 | 2.77 | 0.003 | 0.0016 |
| widened, no +90d rows | B1_industry | choose | 1,565 | 0.042 | -0.004 | 26 | 0.88 | 0.001 | 0.0013 |
| widened, no +90d rows | B2_neighbours | fit | 5,217 | 0.087 |  | 0 | 2.08 | 0.002 | 0.0040 |
| widened, no +90d rows | B2_neighbours | choose | 1,565 | 0.098 |  | 0 | 2.10 | 0.003 | 0.0018 |
| widened, no +90d rows | B3_correlated | fit | 5,217 | 0.053 | 0.027 | 129 | 1.28 | 0.001 | 0.0014 |
| widened, no +90d rows | B3_correlated | choose | 1,565 | 0.055 | -0.069 | 35 | 2.50 | 0.001 | 0.0010 |

### Every method on the kept model's own pairs, CAR [0,+5], industry-adjusted

| arm | method | period | pairs | Spearman | per-event Spearman | events>=5 | slope t | R2 gain | MAE skill |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| universe-only | kept_M3 | fit | 525 | 0.079 | 0.141 | 13 | 1.25 | 0.003 | 0.0028 |
| universe-only | kept_M3 | choose | 137 | 0.336 | 0.152 | 5 | 2.64 | 0.054 | 0.0124 |
| universe-only | B1_industry | fit | 525 | 0.014 |  | 0 | -0.89 | 0.005 | 0.0000 |
| universe-only | B1_industry | choose | 137 | 0.170 |  | 0 | 29.37 | 0.015 | 0.0000 |
| universe-only | B2_neighbours | fit | 525 | 0.074 |  | 0 | 0.60 | 0.001 | 0.0022 |
| universe-only | B2_neighbours | choose | 137 | 0.284 |  | 0 | 2.83 | 0.062 | 0.0167 |
| universe-only | B3_correlated | fit | 525 | 0.008 | 0.186 | 10 | 0.53 | 0.000 | 0.0000 |
| universe-only | B3_correlated | choose | 137 | 0.188 | -0.466 | 5 | 2.61 | 0.052 | 0.0000 |
| widened | kept_M1 | fit | 5,291 | 0.035 | 0.039 | 305 | 1.15 | 0.001 | 0.0003 |
| widened | kept_M1 | choose | 1,557 | 0.094 | 0.043 | 81 | 1.84 | 0.003 | 0.0015 |
| widened | B1_industry | fit | 5,291 | 0.023 | 0.048 | 99 | 0.18 | 0.000 | 0.0000 |
| widened | B1_industry | choose | 1,557 | 0.032 | -0.126 | 26 | 0.77 | 0.000 | 0.0003 |
| widened | B2_neighbours | fit | 5,291 | 0.038 |  | 0 | 0.88 | 0.001 | 0.0007 |
| widened | B2_neighbours | choose | 1,557 | 0.118 |  | 0 | 2.03 | 0.003 | 0.0025 |
| widened | B3_correlated | fit | 5,291 | 0.012 | 0.023 | 131 | -0.22 | 0.000 | 0.0002 |
| widened | B3_correlated | choose | 1,557 | 0.060 | -0.077 | 34 | 3.06 | 0.002 | 0.0009 |
| widened, no +90d rows | kept_M1 | fit | 5,182 | 0.037 | 0.030 | 299 | 1.15 | 0.001 | 0.0003 |
| widened, no +90d rows | kept_M1 | choose | 1,540 | 0.090 | 0.045 | 81 | 1.79 | 0.003 | 0.0015 |
| widened, no +90d rows | B1_industry | fit | 5,182 | 0.023 | 0.032 | 97 | 0.19 | 0.000 | 0.0000 |
| widened, no +90d rows | B1_industry | choose | 1,540 | 0.032 | -0.126 | 26 | 0.81 | 0.001 | 0.0003 |
| widened, no +90d rows | B2_neighbours | fit | 5,182 | 0.041 |  | 0 | 0.84 | 0.000 | 0.0007 |
| widened, no +90d rows | B2_neighbours | choose | 1,540 | 0.114 |  | 0 | 1.93 | 0.002 | 0.0024 |
| widened, no +90d rows | B3_correlated | fit | 5,182 | 0.014 | 0.026 | 129 | -0.15 | 0.000 | 0.0002 |
| widened, no +90d rows | B3_correlated | choose | 1,540 | 0.060 | -0.068 | 34 | 3.05 | 0.002 | 0.0009 |

### Search: best of each variant and H, widened arm, CAR [0,+5] plain (all 120 runs in `search_wide.csv`)

| variant | H | Spearman fit | Spearman choose | slope t fit | slope t choose | R2 gain choose | MAE skill choose |
|---|---|---:|---:|---:|---:|---:|---:|
| M1 | 1 | 0.087 | 0.111 | 2.45 | 2.08 | 0.004 | 0.0037 |
| M1 | 2 | 0.075 | 0.096 | 2.44 | 2.07 | 0.003 | 0.0027 |
| M1 | 3 | 0.075 | 0.095 | 2.45 | 2.08 | 0.003 | 0.0027 |
| M1 | 4 | 0.075 | 0.095 | 2.45 | 2.08 | 0.003 | 0.0027 |
| M1 | 6 | 0.075 | 0.095 | 2.45 | 2.08 | 0.003 | 0.0027 |
| M2 | 1 | 0.087 | 0.111 | 2.45 | 2.08 | 0.004 | 0.0037 |
| M2 | 2 | 0.075 | 0.096 | 2.44 | 2.07 | 0.003 | 0.0027 |
| M2 | 3 | 0.075 | 0.095 | 2.44 | 2.07 | 0.003 | 0.0027 |
| M2 | 4 | 0.075 | 0.095 | 2.44 | 2.07 | 0.003 | 0.0027 |
| M2 | 6 | 0.075 | 0.095 | 2.44 | 2.07 | 0.003 | 0.0027 |
| M3 | 1 | 0.088 | 0.109 | 2.48 | 2.04 | 0.004 | 0.0037 |
| M3 | 2 | 0.075 | 0.094 | 2.49 | 2.03 | 0.003 | 0.0026 |
| M3 | 3 | 0.071 | 0.072 | 2.51 | 2.02 | 0.002 | 0.0020 |
| M3 | 4 | 0.069 | 0.070 | 2.49 | 2.05 | 0.002 | 0.0020 |
| M3 | 6 | 0.068 | 0.070 | 2.50 | 2.04 | 0.002 | 0.0020 |

Widened without +90d rows:

| variant | H | Spearman fit | Spearman choose | slope t fit | slope t choose | R2 gain choose | MAE skill choose |
|---|---|---:|---:|---:|---:|---:|---:|
| M1 | 1 | 0.089 | 0.106 | 2.41 | 2.00 | 0.004 | 0.0033 |
| M1 | 2 | 0.079 | 0.091 | 2.41 | 2.00 | 0.003 | 0.0025 |
| M1 | 3 | 0.078 | 0.091 | 2.41 | 2.00 | 0.003 | 0.0025 |
| M1 | 4 | 0.078 | 0.091 | 2.41 | 2.00 | 0.003 | 0.0025 |
| M1 | 6 | 0.078 | 0.091 | 2.41 | 2.00 | 0.003 | 0.0025 |
| M2 | 1 | 0.089 | 0.106 | 2.41 | 2.00 | 0.004 | 0.0033 |
| M2 | 2 | 0.079 | 0.091 | 2.41 | 2.00 | 0.003 | 0.0025 |
| M2 | 3 | 0.078 | 0.091 | 2.41 | 2.00 | 0.003 | 0.0025 |
| M2 | 4 | 0.078 | 0.091 | 2.41 | 2.00 | 0.003 | 0.0025 |
| M2 | 6 | 0.078 | 0.091 | 2.41 | 2.00 | 0.003 | 0.0025 |
| M3 | 1 | 0.090 | 0.104 | 2.41 | 1.97 | 0.004 | 0.0032 |
| M3 | 2 | 0.077 | 0.091 | 2.37 | 2.00 | 0.003 | 0.0025 |
| M3 | 3 | 0.071 | 0.074 | 2.39 | 2.00 | 0.002 | 0.0021 |
| M3 | 4 | 0.070 | 0.073 | 2.37 | 1.99 | 0.002 | 0.0020 |
| M3 | 6 | 0.071 | 0.073 | 2.37 | 2.00 | 0.002 | 0.0020 |

## 5. Pre-registered weight tests (widened arm, M1, delta 0.3, CAR [0,+5])

Plain CAR:

| weights | H | shocks | pairs fit | Spearman fit | t fit | pairs choose | Spearman choose | t choose | R2 gain choose | MAE skill choose |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| binary | 1 | all | 5,391 | 0.087 | 2.16 | 1,604 | 0.094 | 2.08 | 0.003 | 0.0015 |
| binary | 1 | negative | 3,002 | 0.000 | -0.22 | 795 | 0.044 | 0.83 | 0.000 | 0.0071 |
| binary | 1 | positive | 2,848 | 0.021 | 0.93 | 895 | 0.040 | 0.47 | 0.000 | 0.0001 |
| binary | 2 | all | 7,514 | 0.075 | 2.15 | 2,198 | 0.078 | 2.07 | 0.003 | 0.0010 |
| binary | 2 | negative | 4,341 | 0.034 | 0.09 | 1,170 | -0.004 | -0.22 | 0.000 | 0.0059 |
| binary | 2 | positive | 3,919 | 0.022 | -0.15 | 1,151 | 0.082 | 0.97 | 0.002 | -0.0000 |
| binary | 3 | all | 8,744 | 0.066 | 2.08 | 2,726 | 0.063 | 1.90 | 0.002 | 0.0007 |
| binary | 3 | negative | 5,127 | 0.001 | -0.44 | 1,507 | 0.035 | 0.58 | 0.000 | 0.0043 |
| binary | 3 | positive | 4,591 | 0.023 | 0.22 | 1,355 | 0.165 | 1.99 | 0.010 | -0.0001 |
| share | 1 | all | 5,326 | 0.087 | 2.45 | 1,582 | 0.111 | 2.08 | 0.004 | 0.0037 |
| share | 1 | negative | 2,963 | 0.035 | 0.70 | 782 | 0.036 | 0.91 | 0.001 | 0.0081 |
| share | 1 | positive | 2,810 | -0.009 | 0.84 | 883 | 0.079 | 0.89 | 0.002 | 0.0002 |
| share | 2 | all | 7,332 | 0.074 | 2.44 | 2,156 | 0.096 | 2.07 | 0.003 | 0.0027 |
| share | 2 | negative | 4,212 | 0.050 | 1.02 | 1,138 | 0.021 | 0.31 | 0.000 | 0.0061 |
| share | 2 | positive | 3,824 | -0.004 | 0.11 | 1,135 | 0.100 | 1.23 | 0.003 | 0.0002 |
| share | 3 | all | 7,635 | 0.072 | 2.44 | 2,342 | 0.087 | 2.06 | 0.003 | 0.0024 |
| share | 3 | negative | 4,467 | 0.046 | 1.00 | 1,256 | 0.016 | 0.38 | 0.000 | 0.0054 |
| share | 3 | positive | 3,923 | -0.002 | 0.16 | 1,204 | 0.123 | 1.36 | 0.003 | 0.0001 |
| share_cap_b0.0 | 1 | all | 5,326 | 0.087 | 2.45 | 1,582 | 0.111 | 2.08 | 0.004 | 0.0037 |
| share_cap_b0.0 | 1 | negative | 2,963 | 0.035 | 0.70 | 782 | 0.036 | 0.91 | 0.001 | 0.0081 |
| share_cap_b0.0 | 1 | positive | 2,810 | -0.009 | 0.84 | 883 | 0.079 | 0.89 | 0.002 | 0.0002 |
| share_cap_b0.0 | 2 | all | 7,332 | 0.074 | 2.44 | 2,156 | 0.096 | 2.07 | 0.003 | 0.0027 |
| share_cap_b0.0 | 2 | negative | 4,212 | 0.050 | 1.02 | 1,138 | 0.021 | 0.31 | 0.000 | 0.0061 |
| share_cap_b0.0 | 2 | positive | 3,824 | -0.004 | 0.11 | 1,135 | 0.100 | 1.23 | 0.003 | 0.0002 |
| share_cap_b0.0 | 3 | all | 7,635 | 0.072 | 2.44 | 2,342 | 0.087 | 2.06 | 0.003 | 0.0024 |
| share_cap_b0.0 | 3 | negative | 4,467 | 0.046 | 1.00 | 1,256 | 0.016 | 0.38 | 0.000 | 0.0054 |
| share_cap_b0.0 | 3 | positive | 3,923 | -0.002 | 0.16 | 1,204 | 0.123 | 1.36 | 0.003 | 0.0001 |
| share_cap_b0.5 | 1 | all | 5,323 | 0.077 | 1.35 | 1,582 | 0.104 | -0.13 | 0.000 | 0.0009 |
| share_cap_b0.5 | 1 | negative | 2,962 | 0.045 | 0.79 | 782 | 0.021 | -1.35 | 0.005 | -0.0011 |
| share_cap_b0.5 | 1 | positive | 2,808 | -0.024 | 0.46 | 884 | 0.069 | 0.35 | 0.000 | 0.0002 |
| share_cap_b0.5 | 2 | all | 7,345 | 0.065 | 1.37 | 2,157 | 0.089 | -0.05 | 0.000 | 0.0007 |
| share_cap_b0.5 | 2 | negative | 4,222 | 0.055 | 1.12 | 1,139 | 0.004 | -1.58 | 0.006 | -0.0007 |
| share_cap_b0.5 | 2 | positive | 3,827 | -0.018 | 0.02 | 1,136 | 0.091 | 0.52 | 0.001 | 0.0002 |
| share_cap_b0.5 | 3 | all | 8,468 | 0.059 | 1.38 | 2,661 | 0.063 | 0.00 | 0.000 | 0.0005 |
| share_cap_b0.5 | 3 | negative | 4,938 | 0.024 | 0.99 | 1,456 | 0.027 | -1.01 | 0.002 | -0.0005 |
| share_cap_b0.5 | 3 | positive | 4,412 | -0.007 | 0.23 | 1,334 | 0.147 | 1.42 | 0.004 | 0.0001 |
| share_cap_b1.0 | 1 | all | 5,325 | 0.067 | 0.99 | 1,583 | 0.100 | 1.26 | 0.002 | 0.0035 |
| share_cap_b1.0 | 1 | negative | 2,963 | 0.035 | 0.46 | 782 | 0.020 | 1.51 | 0.002 | 0.0084 |
| share_cap_b1.0 | 1 | positive | 2,808 | -0.040 | -1.08 | 884 | 0.045 | 0.36 | 0.000 | 0.0000 |
| share_cap_b1.0 | 2 | all | 7,345 | 0.055 | 1.57 | 2,158 | 0.082 | 1.40 | 0.002 | 0.0026 |
| share_cap_b1.0 | 2 | negative | 4,225 | 0.042 | 1.47 | 1,140 | -0.002 | 0.42 | 0.000 | 0.0060 |
| share_cap_b1.0 | 2 | positive | 3,823 | -0.033 | -0.17 | 1,137 | 0.070 | 0.71 | 0.001 | 0.0000 |
| share_cap_b1.0 | 3 | all | 8,477 | 0.051 | 1.66 | 2,665 | 0.053 | 1.40 | 0.001 | 0.0018 |
| share_cap_b1.0 | 3 | negative | 4,948 | 0.019 | 1.10 | 1,459 | 0.022 | 1.02 | 0.001 | 0.0042 |
| share_cap_b1.0 | 3 | positive | 4,410 | -0.021 | 0.40 | 1,336 | 0.113 | 1.93 | 0.008 | 0.0000 |

Industry-adjusted CAR:

| weights | H | shocks | pairs fit | Spearman fit | t fit | pairs choose | Spearman choose | t choose | R2 gain choose | MAE skill choose |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| binary | 1 | all | 5,358 | 0.035 | 0.80 | 1,579 | 0.107 | 1.85 | 0.002 | 0.0023 |
| binary | 1 | negative | 2,988 | 0.011 | 0.20 | 781 | 0.077 | 1.13 | 0.001 | 0.0057 |
| binary | 1 | positive | 2,824 | -0.010 | -0.56 | 882 | 0.102 | 1.31 | 0.002 | 0.0003 |
| binary | 2 | all | 7,481 | 0.030 | 0.75 | 2,171 | 0.087 | 1.98 | 0.002 | 0.0019 |
| binary | 2 | negative | 4,327 | 0.029 | 0.37 | 1,155 | 0.038 | 0.48 | 0.000 | 0.0044 |
| binary | 2 | positive | 3,895 | 0.007 | -1.15 | 1,137 | 0.056 | 0.59 | 0.000 | 0.0002 |
| binary | 3 | all | 8,711 | 0.026 | 0.76 | 2,699 | 0.071 | 1.98 | 0.001 | 0.0014 |
| binary | 3 | negative | 5,113 | -0.006 | -0.17 | 1,492 | 0.032 | 0.40 | 0.000 | 0.0033 |
| binary | 3 | positive | 4,567 | 0.007 | -0.94 | 1,341 | 0.107 | 2.17 | 0.004 | 0.0002 |
| share | 1 | all | 5,291 | 0.035 | 1.15 | 1,557 | 0.094 | 1.84 | 0.003 | 0.0015 |
| share | 1 | negative | 2,948 | 0.017 | 0.62 | 768 | 0.050 | 1.01 | 0.001 | 0.0043 |
| share | 1 | positive | 2,786 | -0.028 | 0.59 | 870 | 0.046 | 0.96 | 0.002 | 0.0000 |
| share | 2 | all | 7,297 | 0.031 | 1.13 | 2,129 | 0.085 | 1.85 | 0.002 | 0.0011 |
| share | 2 | negative | 4,197 | 0.034 | 0.89 | 1,123 | 0.054 | 0.78 | 0.000 | 0.0028 |
| share | 2 | positive | 3,800 | -0.006 | -0.12 | 1,121 | 0.021 | 0.77 | 0.001 | 0.0000 |
| share | 3 | all | 7,600 | 0.031 | 1.13 | 2,315 | 0.078 | 1.85 | 0.002 | 0.0010 |
| share | 3 | negative | 4,452 | 0.023 | 0.74 | 1,241 | 0.052 | 0.90 | 0.001 | 0.0025 |
| share | 3 | positive | 3,899 | -0.005 | -0.10 | 1,190 | 0.055 | 1.06 | 0.002 | 0.0000 |
| share_cap_b0.0 | 1 | all | 5,291 | 0.035 | 1.15 | 1,557 | 0.094 | 1.84 | 0.003 | 0.0015 |
| share_cap_b0.0 | 1 | negative | 2,948 | 0.017 | 0.62 | 768 | 0.050 | 1.01 | 0.001 | 0.0043 |
| share_cap_b0.0 | 1 | positive | 2,786 | -0.028 | 0.59 | 870 | 0.046 | 0.96 | 0.002 | 0.0000 |
| share_cap_b0.0 | 2 | all | 7,297 | 0.031 | 1.13 | 2,129 | 0.085 | 1.85 | 0.002 | 0.0011 |
| share_cap_b0.0 | 2 | negative | 4,197 | 0.034 | 0.89 | 1,123 | 0.054 | 0.78 | 0.000 | 0.0028 |
| share_cap_b0.0 | 2 | positive | 3,800 | -0.006 | -0.12 | 1,121 | 0.021 | 0.77 | 0.001 | 0.0000 |
| share_cap_b0.0 | 3 | all | 7,600 | 0.031 | 1.13 | 2,315 | 0.078 | 1.85 | 0.002 | 0.0010 |
| share_cap_b0.0 | 3 | negative | 4,452 | 0.023 | 0.74 | 1,241 | 0.052 | 0.90 | 0.001 | 0.0025 |
| share_cap_b0.0 | 3 | positive | 3,899 | -0.005 | -0.10 | 1,190 | 0.055 | 1.06 | 0.002 | 0.0000 |
| share_cap_b0.5 | 1 | all | 5,286 | 0.033 | 0.85 | 1,555 | 0.082 | -0.21 | 0.000 | 0.0007 |
| share_cap_b0.5 | 1 | negative | 2,946 | 0.041 | 0.09 | 768 | 0.041 | -0.96 | 0.002 | 0.0009 |
| share_cap_b0.5 | 1 | positive | 2,784 | -0.045 | 0.96 | 871 | 0.017 | 0.53 | 0.001 | 0.0000 |
| share_cap_b0.5 | 2 | all | 7,308 | 0.027 | 0.88 | 2,128 | 0.075 | -0.20 | 0.000 | 0.0005 |
| share_cap_b0.5 | 2 | negative | 4,206 | 0.043 | 0.65 | 1,124 | 0.031 | -1.10 | 0.003 | 0.0006 |
| share_cap_b0.5 | 2 | positive | 3,803 | -0.021 | 0.29 | 1,122 | 0.003 | 0.31 | 0.000 | 0.0000 |
| share_cap_b0.5 | 3 | all | 8,431 | 0.024 | 0.89 | 2,632 | 0.061 | -0.13 | 0.000 | 0.0004 |
| share_cap_b0.5 | 3 | negative | 4,922 | 0.010 | 0.51 | 1,441 | 0.028 | -0.99 | 0.002 | 0.0004 |
| share_cap_b0.5 | 3 | positive | 4,388 | -0.010 | 0.48 | 1,320 | 0.051 | 1.09 | 0.002 | 0.0000 |
| share_cap_b1.0 | 1 | all | 5,287 | 0.022 | 0.26 | 1,556 | 0.074 | 0.83 | 0.001 | 0.0000 |
| share_cap_b1.0 | 1 | negative | 2,947 | 0.034 | -0.29 | 768 | 0.031 | 2.42 | 0.006 | 0.0055 |
| share_cap_b1.0 | 1 | positive | 2,784 | -0.056 | -0.03 | 871 | -0.006 | -0.29 | 0.000 | 0.0000 |
| share_cap_b1.0 | 2 | all | 7,307 | 0.016 | 0.94 | 2,129 | 0.067 | 0.99 | 0.001 | 0.0001 |
| share_cap_b1.0 | 2 | negative | 4,209 | 0.032 | 1.15 | 1,125 | 0.015 | 1.78 | 0.002 | 0.0039 |
| share_cap_b1.0 | 2 | positive | 3,799 | -0.035 | 0.41 | 1,123 | -0.008 | -0.22 | 0.000 | 0.0000 |
| share_cap_b1.0 | 3 | all | 8,439 | 0.015 | 1.06 | 2,636 | 0.054 | 1.06 | 0.001 | 0.0001 |
| share_cap_b1.0 | 3 | negative | 4,932 | 0.006 | 0.85 | 1,444 | 0.020 | 1.16 | 0.001 | 0.0028 |
| share_cap_b1.0 | 3 | positive | 4,386 | -0.026 | 0.85 | 1,322 | 0.032 | 1.34 | 0.002 | 0.0000 |

The same 45 runs without the +90d rows are in `weight_tests_wide_nf.csv` (and below, plain CAR):

| weights | H | shocks | pairs fit | Spearman fit | t fit | pairs choose | Spearman choose | t choose | R2 gain choose | MAE skill choose |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| binary | 1 | all | 5,282 | 0.089 | 2.14 | 1,587 | 0.088 | 1.95 | 0.003 | 0.0010 |
| binary | 1 | negative | 2,942 | -0.002 | -0.22 | 788 | 0.042 | 0.77 | 0.000 | 0.0068 |
| binary | 1 | positive | 2,789 | 0.021 | 0.83 | 885 | 0.039 | 0.45 | 0.000 | -0.0000 |
| binary | 2 | all | 7,226 | 0.078 | 2.16 | 2,131 | 0.074 | 1.87 | 0.002 | 0.0007 |
| binary | 2 | negative | 4,186 | 0.031 | 0.06 | 1,133 | 0.010 | 0.05 | 0.000 | 0.0057 |
| binary | 2 | positive | 3,762 | 0.021 | -0.32 | 1,120 | 0.088 | 1.49 | 0.003 | -0.0002 |
| binary | 3 | all | 8,286 | 0.069 | 2.10 | 2,540 | 0.062 | 1.82 | 0.002 | 0.0005 |
| binary | 3 | negative | 4,873 | 0.003 | -0.32 | 1,393 | 0.016 | 0.33 | 0.000 | 0.0046 |
| binary | 3 | positive | 4,335 | 0.025 | 0.05 | 1,282 | 0.165 | 2.39 | 0.012 | -0.0002 |
| share | 1 | all | 5,217 | 0.089 | 2.41 | 1,565 | 0.106 | 2.00 | 0.004 | 0.0033 |
| share | 1 | negative | 2,903 | 0.035 | 0.75 | 775 | 0.033 | 0.92 | 0.001 | 0.0077 |
| share | 1 | positive | 2,751 | -0.009 | 0.80 | 873 | 0.076 | 0.89 | 0.002 | 0.0003 |
| share | 2 | all | 7,046 | 0.078 | 2.41 | 2,088 | 0.091 | 2.00 | 0.003 | 0.0025 |
| share | 2 | negative | 4,057 | 0.047 | 1.00 | 1,101 | 0.029 | 0.66 | 0.000 | 0.0060 |
| share | 2 | positive | 3,668 | -0.004 | 0.01 | 1,103 | 0.108 | 1.62 | 0.005 | 0.0002 |
| share | 3 | all | 7,281 | 0.076 | 2.41 | 2,229 | 0.084 | 1.99 | 0.003 | 0.0023 |
| share | 3 | negative | 4,267 | 0.048 | 1.05 | 1,193 | 0.011 | 0.52 | 0.000 | 0.0053 |
| share | 3 | positive | 3,733 | -0.004 | 0.07 | 1,153 | 0.131 | 1.71 | 0.005 | 0.0002 |
| share_cap_b0.0 | 1 | all | 5,217 | 0.089 | 2.41 | 1,565 | 0.106 | 2.00 | 0.004 | 0.0033 |
| share_cap_b0.0 | 1 | negative | 2,903 | 0.035 | 0.75 | 775 | 0.033 | 0.92 | 0.001 | 0.0077 |
| share_cap_b0.0 | 1 | positive | 2,751 | -0.009 | 0.80 | 873 | 0.076 | 0.89 | 0.002 | 0.0003 |
| share_cap_b0.0 | 2 | all | 7,046 | 0.078 | 2.41 | 2,088 | 0.091 | 2.00 | 0.003 | 0.0025 |
| share_cap_b0.0 | 2 | negative | 4,057 | 0.047 | 1.00 | 1,101 | 0.029 | 0.66 | 0.000 | 0.0060 |
| share_cap_b0.0 | 2 | positive | 3,668 | -0.004 | 0.01 | 1,103 | 0.108 | 1.62 | 0.005 | 0.0002 |
| share_cap_b0.0 | 3 | all | 7,281 | 0.076 | 2.41 | 2,229 | 0.084 | 1.99 | 0.003 | 0.0023 |
| share_cap_b0.0 | 3 | negative | 4,267 | 0.048 | 1.05 | 1,193 | 0.011 | 0.52 | 0.000 | 0.0053 |
| share_cap_b0.0 | 3 | positive | 3,733 | -0.004 | 0.07 | 1,153 | 0.131 | 1.71 | 0.005 | 0.0002 |
| share_cap_b0.5 | 1 | all | 5,214 | 0.081 | 1.32 | 1,565 | 0.098 | -0.16 | 0.000 | 0.0006 |
| share_cap_b0.5 | 1 | negative | 2,902 | 0.049 | 0.80 | 775 | 0.016 | -1.34 | 0.005 | -0.0017 |
| share_cap_b0.5 | 1 | positive | 2,749 | -0.023 | 0.48 | 874 | 0.065 | 0.39 | 0.000 | 0.0002 |
| share_cap_b0.5 | 2 | all | 7,057 | 0.068 | 1.35 | 2,090 | 0.084 | -0.09 | 0.000 | 0.0004 |
| share_cap_b0.5 | 2 | negative | 4,067 | 0.054 | 1.10 | 1,102 | 0.014 | -1.39 | 0.005 | -0.0011 |
| share_cap_b0.5 | 2 | positive | 3,671 | -0.017 | -0.07 | 1,105 | 0.095 | 0.91 | 0.001 | 0.0002 |
| share_cap_b0.5 | 3 | all | 8,023 | 0.063 | 1.36 | 2,476 | 0.063 | -0.01 | 0.000 | 0.0003 |
| share_cap_b0.5 | 3 | negative | 4,693 | 0.030 | 1.05 | 1,343 | 0.007 | -1.17 | 0.003 | -0.0008 |
| share_cap_b0.5 | 3 | positive | 4,162 | -0.003 | 0.08 | 1,261 | 0.151 | 1.71 | 0.005 | 0.0001 |
| share_cap_b1.0 | 1 | all | 5,216 | 0.072 | 0.98 | 1,566 | 0.094 | 1.17 | 0.002 | 0.0033 |
| share_cap_b1.0 | 1 | negative | 2,903 | 0.040 | 0.72 | 775 | 0.015 | 1.47 | 0.002 | 0.0079 |
| share_cap_b1.0 | 1 | positive | 2,749 | -0.039 | -1.22 | 874 | 0.040 | 0.29 | 0.000 | 0.0000 |
| share_cap_b1.0 | 2 | all | 7,058 | 0.060 | 1.57 | 2,091 | 0.077 | 1.31 | 0.002 | 0.0024 |
| share_cap_b1.0 | 2 | negative | 4,070 | 0.042 | 1.51 | 1,103 | 0.009 | 1.06 | 0.001 | 0.0058 |
| share_cap_b1.0 | 2 | positive | 3,668 | -0.033 | -0.42 | 1,106 | 0.074 | 1.43 | 0.003 | 0.0000 |
| share_cap_b1.0 | 3 | all | 8,032 | 0.056 | 1.68 | 2,479 | 0.052 | 1.33 | 0.001 | 0.0018 |
| share_cap_b1.0 | 3 | negative | 4,704 | 0.026 | 1.31 | 1,345 | 0.002 | 0.80 | 0.001 | 0.0043 |
| share_cap_b1.0 | 3 | positive | 4,160 | -0.017 | 0.16 | 1,263 | 0.113 | 2.44 | 0.011 | 0.0000 |

## 6. What the widening shows

- Power: about nine times the usable pairs (6,908 against 781 for [0,+5]), 300 fitting-period
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
