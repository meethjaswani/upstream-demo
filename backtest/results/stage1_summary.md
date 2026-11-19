# Upstream, Stage 1 backtest: summary

All numbers use data dated before 2024-01-01 only. Fitting period 2016-01 to 2021-12, choosing period 2022-01 to
2023-12; the 2024+ test period was never loaded. Headline arm: CRSP/Compustat. Yahoo arm reported alongside.
271 rows in the trial log (`trial_log.csv`), every configuration and every baseline included.

## Power (amendment 11)

| | CRSP | Yahoo |
|---|---:|---:|
| Events (fitting / choosing) | 7,636 (5,823 / 1,813) | 6,701 (5,009 / 1,692) |
| Events with a linked firm (1 hop) | 743 | 678 |
| Event-firm pairs, 1 hop, before cleaning | 1,652 | 1,408 |
| Pairs used by the kept model, [0,+5] (after amendments 3 and 4) | 781 | 704 |
| Pairs used by the kept model, [+1,+20] | 339 | 302 |
| Median linked firms per event (events with any) | 1 | 1 |
| Events with >= 5 linked firms | 70 | 42 |
| Seed links, both ends in the universe | 1,279 | 1,053 |
| Share of index member-days without a return, 2016-2023 | 0.4% | 11.5% |
| Share of index tickers with no prices at all | 0% (CRSP) | 18.3% |

Kept model, [0,+5]: of 1,624 pairs with a CAR, 721 were
dropped because the linked firm had its own 8-K, 10-Q, 10-K or earnings day in the window (amendment 3) and
122 by the overlap rule (amendment 4). For [+1,+20]: 1,217
and 66. The choosing period has only
203 usable pairs for [0,+5] and 89 for [+1,+20]: the test is weak (amendment 12), see "Not done".

Seed links per year (10-K acceptance year; 3,544 links in all, from 10-Ks of the CRSP index members):

| year | links | sellers | named | with share | from XBRL |
|---|---:|---:|---:|---:|---:|
| 2015 | 344 | 174 | 233 | 317 | 169 |
| 2016 | 336 | 178 | 225 | 311 | 173 |
| 2017 | 357 | 185 | 239 | 316 | 193 |
| 2018 | 363 | 186 | 241 | 325 | 206 |
| 2019 | 363 | 189 | 250 | 330 | 191 |
| 2020 | 447 | 226 | 303 | 415 | 188 |
| 2021 | 449 | 232 | 306 | 405 | 206 |
| 2022 | 448 | 231 | 295 | 409 | 235 |
| 2023 | 437 | 219 | 289 | 404 | 236 |

## Results, CRSP arm, every variant and baseline

Each variant at its best configuration under the selection rule (full grid of 120 in `search_crsp.csv`), the kept
configuration, and the baselines on their own pairs. B0 (zero for everyone) is the null inside "R2 gain vs B0" and
"MAE skill vs B0" (amendment 6). "outcome adj" = industry-adjusted CAR (amendment 8). Per-event Spearman only for
events with >= 5 linked firms (amendment 5); B1 and B2 give every firm in an event the same prediction, so they have
no within-event ranking. At H = 1 delta only rescales the prediction, which lambda undoes, so every delta gives the
same M1/M2 result; the table shows the first.

### CAR [0,+5]

| method | outcome | period | pairs | Spearman (pooled) | Spearman (per event) | events >=5 | hit rate | slope t | R2 gain vs B0 | MAE skill vs B0 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 (delta 0.2, H 1) | plain | fit | 578 | 0.155 | 0.122 | 14 | 0.57 | 1.25 | 0.006 | 0.0034 |
| M1 (delta 0.2, H 1) | plain | choose | 203 | 0.122 | -0.005 | 6 | 0.52 | 1.95 | 0.021 | 0.0017 |
| M1 (delta 0.2, H 1) | adj | fit | 477 | 0.055 | 0.087 | 13 | 0.51 | 0.86 | 0.002 | 0.0022 |
| M1 (delta 0.2, H 1) | adj | choose | 124 | 0.385 | 0.169 | 5 | 0.64 | 2.80 | 0.060 | 0.0116 |
| M2 (delta 0.2, H 1) | plain | fit | 578 | 0.155 | 0.122 | 14 | 0.57 | 1.25 | 0.006 | 0.0034 |
| M2 (delta 0.2, H 1) | plain | choose | 203 | 0.122 | -0.005 | 6 | 0.52 | 1.95 | 0.021 | 0.0017 |
| M2 (delta 0.2, H 1) | adj | fit | 477 | 0.055 | 0.087 | 13 | 0.51 | 0.86 | 0.002 | 0.0022 |
| M2 (delta 0.2, H 1) | adj | choose | 124 | 0.385 | 0.169 | 5 | 0.64 | 2.80 | 0.060 | 0.0116 |
| M3 (delta 0.7, H 1, 1k runs) | plain | fit | 578 | 0.158 | 0.139 | 14 | 0.57 | 1.30 | 0.006 | 0.0036 |
| M3 (delta 0.7, H 1, 1k runs) | plain | choose | 203 | 0.123 | -0.012 | 6 | 0.52 | 1.98 | 0.022 | 0.0018 |
| M3 (delta 0.7, H 1, 1k runs) | adj | fit | 477 | 0.054 | 0.081 | 13 | 0.51 | 0.85 | 0.002 | 0.0022 |
| M3 (delta 0.7, H 1, 1k runs) | adj | choose | 124 | 0.387 | 0.145 | 5 | 0.64 | 2.74 | 0.061 | 0.0146 |
| **kept M3** (delta 0.7, H 1, 10k runs) | plain | fit | 578 | 0.154 | 0.134 | 14 | 0.57 | 1.25 | 0.006 | 0.0034 |
| **kept M3** (delta 0.7, H 1, 10k runs) | plain | choose | 203 | 0.123 | -0.015 | 6 | 0.52 | 1.95 | 0.021 | 0.0017 |
| **kept M3** (delta 0.7, H 1, 10k runs) | adj | fit | 477 | 0.057 | 0.092 | 13 | 0.51 | 0.86 | 0.002 | 0.0024 |
| **kept M3** (delta 0.7, H 1, 10k runs) | adj | choose | 124 | 0.385 | 0.152 | 5 | 0.64 | 2.81 | 0.061 | 0.0138 |
| B1 same sub-industry | plain | fit | 10,530 | 0.169 |  | 0 | 0.59 | 7.40 | 0.027 | 0.0113 |
| B1 same sub-industry | plain | choose | 3,622 | 0.193 |  | 0 | 0.61 | 5.66 | 0.043 | 0.0178 |
| B1 same sub-industry | adj | fit | 10,310 | -0.022 |  | 0 | 0.49 | -0.65 | 0.000 | 0.0000 |
| B1 same sub-industry | adj | choose | 3,542 | -0.009 |  | 0 | 0.49 | -0.20 | 0.000 | 0.0000 |
| B2 direct neighbours | plain | fit | 1,099 | 0.135 |  | 0 | 0.57 | 3.10 | 0.011 | 0.0081 |
| B2 direct neighbours | plain | choose | 344 | 0.088 |  | 0 | 0.53 | 2.04 | 0.014 | 0.0044 |
| B2 direct neighbours | adj | fit | 950 | 0.070 |  | 0 | 0.51 | 1.07 | 0.001 | 0.0022 |
| B2 direct neighbours | adj | choose | 249 | 0.092 |  | 0 | 0.58 | 1.47 | 0.011 | 0.0060 |
| B3 20 most correlated | plain | fit | 22,629 | 0.109 | 0.072 | 1887 | 0.54 | 4.96 | 0.020 | 0.0040 |
| B3 20 most correlated | plain | choose | 7,791 | 0.148 | 0.073 | 644 | 0.56 | 4.21 | 0.034 | 0.0079 |
| B3 20 most correlated | adj | fit | 21,027 | 0.021 | 0.029 | 1749 | 0.51 | 2.20 | 0.002 | 0.0001 |
| B3 20 most correlated | adj | choose | 7,234 | 0.032 | 0.026 | 599 | 0.52 | 2.04 | 0.002 | 0.0005 |

### CAR [+1,+20]

| method | outcome | period | pairs | Spearman (pooled) | Spearman (per event) | events >=5 | hit rate | slope t | R2 gain vs B0 | MAE skill vs B0 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 (delta 0.2, H 1) | plain | fit | 250 | -0.120 | 0.095 | 7 | 0.45 | -1.67 | 0.018 | 0.0000 |
| M1 (delta 0.2, H 1) | plain | choose | 89 | -0.091 | 0.057 | 4 | 0.46 | -0.30 | 0.002 | 0.0000 |
| M1 (delta 0.2, H 1) | adj | fit | 214 | -0.108 | 0.042 | 7 | 0.46 | -1.90 | 0.026 | 0.0000 |
| M1 (delta 0.2, H 1) | adj | choose | 59 | -0.117 | 0.600 | 1 | 0.37 | -0.86 | 0.012 | 0.0000 |
| M2 (delta 0.2, H 1) | plain | fit | 250 | -0.120 | 0.095 | 7 | 0.45 | -1.67 | 0.018 | 0.0000 |
| M2 (delta 0.2, H 1) | plain | choose | 89 | -0.091 | 0.057 | 4 | 0.46 | -0.30 | 0.002 | 0.0000 |
| M2 (delta 0.2, H 1) | adj | fit | 214 | -0.108 | 0.042 | 7 | 0.46 | -1.90 | 0.026 | 0.0000 |
| M2 (delta 0.2, H 1) | adj | choose | 59 | -0.117 | 0.600 | 1 | 0.37 | -0.86 | 0.012 | 0.0000 |
| M3 (delta 0.7, H 1, 1k runs) | plain | fit | 250 | -0.117 | 0.118 | 7 | 0.45 | -1.64 | 0.018 | 0.0000 |
| M3 (delta 0.7, H 1, 1k runs) | plain | choose | 89 | -0.092 | 0.057 | 4 | 0.46 | -0.33 | 0.002 | 0.0000 |
| M3 (delta 0.7, H 1, 1k runs) | adj | fit | 214 | -0.111 | 0.013 | 7 | 0.47 | -1.95 | 0.027 | 0.0000 |
| M3 (delta 0.7, H 1, 1k runs) | adj | choose | 59 | -0.120 | 0.600 | 1 | 0.37 | -0.86 | 0.012 | 0.0000 |
| **kept M3** (delta 0.7, H 1, 10k runs) | plain | fit | 250 | -0.114 | 0.104 | 7 | 0.45 | -1.62 | 0.017 | 0.0000 |
| **kept M3** (delta 0.7, H 1, 10k runs) | plain | choose | 89 | -0.091 | 0.057 | 4 | 0.46 | -0.29 | 0.002 | 0.0000 |
| **kept M3** (delta 0.7, H 1, 10k runs) | adj | fit | 214 | -0.110 | 0.051 | 7 | 0.46 | -1.90 | 0.027 | 0.0000 |
| **kept M3** (delta 0.7, H 1, 10k runs) | adj | choose | 59 | -0.115 | 0.600 | 1 | 0.37 | -0.85 | 0.011 | 0.0000 |
| B1 same sub-industry | plain | fit | 3,716 | -0.004 |  | 0 | 0.49 | -0.91 | 0.001 | 0.0000 |
| B1 same sub-industry | plain | choose | 1,418 | 0.104 |  | 0 | 0.53 | 2.54 | 0.011 | 0.0000 |
| B1 same sub-industry | adj | fit | 3,621 | -0.007 |  | 0 | 0.49 | -0.19 | 0.000 | 0.0000 |
| B1 same sub-industry | adj | choose | 1,375 | 0.064 |  | 0 | 0.52 | 2.17 | 0.002 | 0.0000 |
| B2 direct neighbours | plain | fit | 433 | -0.039 |  | 0 | 0.48 | -1.59 | 0.006 | 0.0000 |
| B2 direct neighbours | plain | choose | 137 | -0.047 |  | 0 | 0.47 | -0.87 | 0.008 | 0.0000 |
| B2 direct neighbours | adj | fit | 387 | -0.092 |  | 0 | 0.46 | -2.12 | 0.012 | 0.0000 |
| B2 direct neighbours | adj | choose | 101 | 0.080 |  | 0 | 0.49 | 0.39 | 0.002 | 0.0000 |
| B3 20 most correlated | plain | fit | 6,919 | -0.017 | -0.026 | 430 | 0.50 | -1.03 | 0.000 | 0.0000 |
| B3 20 most correlated | plain | choose | 2,512 | 0.086 | 0.028 | 171 | 0.53 | 2.49 | 0.020 | 0.0000 |
| B3 20 most correlated | adj | fit | 6,379 | -0.007 | -0.017 | 382 | 0.50 | -1.15 | 0.000 | 0.0000 |
| B3 20 most correlated | adj | choose | 2,333 | 0.032 | 0.016 | 144 | 0.51 | 1.43 | 0.004 | 0.0000 |

### Head to head on the model's own pairs (choosing and fitting periods)

Every method scored on exactly the kept model's cleaned event-firm pairs; a baseline with no prediction for a
pair predicts 0 there (hit rate then counts that pair as a miss, so read Spearman, R2 and MAE).

CRSP:

| method | outcome | period | pairs | Spearman (pooled) | Spearman (per event) | events >=5 | hit rate | slope t | R2 gain vs B0 | MAE skill vs B0 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kept model | plain | fit | 578 | 0.154 | 0.134 | 14 | 0.57 | 1.25 | 0.006 | 0.0034 |
| kept model | plain | choose | 203 | 0.123 | -0.015 | 6 | 0.52 | 1.95 | 0.021 | 0.0017 |
| kept model | adj | fit | 477 | 0.057 | 0.092 | 13 | 0.51 | 0.86 | 0.002 | 0.0024 |
| kept model | adj | choose | 124 | 0.385 | 0.152 | 5 | 0.64 | 2.81 | 0.061 | 0.0138 |
| B1 | plain | fit | 578 | 0.044 |  | 0 | 0.04 | -0.42 | 0.001 | 0.0012 |
| B1 | plain | choose | 203 | 0.090 |  | 0 | 0.04 | 1.29 | 0.003 | 0.0017 |
| B1 | adj | fit | 477 | -0.006 |  | 0 | 0.03 | -1.45 | 0.010 | 0.0004 |
| B1 | adj | choose | 124 | 0.210 |  | 0 | 0.06 | 5.17 | 0.033 | 0.0053 |
| B2 | plain | fit | 578 | 0.164 |  | 0 | 0.57 | 1.95 | 0.011 | 0.0142 |
| B2 | plain | choose | 203 | 0.093 |  | 0 | 0.52 | 1.74 | 0.019 | 0.0031 |
| B2 | adj | fit | 477 | 0.062 |  | 0 | 0.51 | 0.35 | 0.000 | 0.0023 |
| B2 | adj | choose | 124 | 0.333 |  | 0 | 0.64 | 3.12 | 0.069 | 0.0165 |
| B3 | plain | fit | 578 | 0.051 | 0.106 | 10 | 0.15 | 1.17 | 0.001 | 0.0025 |
| B3 | plain | choose | 203 | 0.156 | -0.179 | 5 | 0.18 | 1.94 | 0.014 | 0.0049 |
| B3 | adj | fit | 477 | -0.018 | 0.227 | 9 | 0.15 | -0.34 | 0.000 | 0.0000 |
| B3 | adj | choose | 124 | 0.186 | -0.466 | 5 | 0.20 | 2.74 | 0.061 | 0.0000 |

Yahoo:

| method | outcome | period | pairs | Spearman (pooled) | Spearman (per event) | events >=5 | hit rate | slope t | R2 gain vs B0 | MAE skill vs B0 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kept model | plain | fit | 513 | 0.137 | 0.110 | 12 | 0.56 | 1.03 | 0.006 | 0.0014 |
| kept model | plain | choose | 191 | 0.143 | 0.163 | 7 | 0.53 | 2.11 | 0.025 | 0.0020 |
| kept model | adj | fit | 418 | 0.023 | 0.023 | 10 | 0.50 | 0.64 | 0.001 | 0.0010 |
| kept model | adj | choose | 115 | 0.378 | 0.402 | 6 | 0.63 | 2.65 | 0.058 | 0.0067 |
| B1 | plain | fit | 513 | 0.065 |  | 0 | 0.04 | 0.09 | 0.000 | 0.0016 |
| B1 | plain | choose | 191 | 0.090 |  | 0 | 0.04 | 1.30 | 0.003 | 0.0022 |
| B1 | adj | fit | 418 | -0.017 |  | 0 | 0.03 | -0.84 | 0.013 | 0.0000 |
| B1 | adj | choose | 115 | 0.100 |  | 0 | 0.06 | 3.18 | 0.026 | 0.0000 |
| B2 | plain | fit | 513 | 0.155 |  | 0 | 0.56 | 2.22 | 0.017 | 0.0122 |
| B2 | plain | choose | 191 | 0.090 |  | 0 | 0.53 | 1.76 | 0.019 | 0.0028 |
| B2 | adj | fit | 418 | 0.039 |  | 0 | 0.50 | 0.09 | 0.000 | 0.0003 |
| B2 | adj | choose | 115 | 0.276 |  | 0 | 0.63 | 2.80 | 0.051 | 0.0094 |
| B3 | plain | fit | 513 | 0.050 | 0.097 | 9 | 0.17 | 0.99 | 0.001 | 0.0028 |
| B3 | plain | choose | 191 | 0.160 | -0.212 | 5 | 0.19 | 1.83 | 0.013 | 0.0051 |
| B3 | adj | fit | 418 | -0.026 | 0.208 | 8 | 0.17 | -0.53 | 0.000 | 0.0000 |
| B3 | adj | choose | 115 | 0.165 | -0.402 | 5 | 0.23 | 2.83 | 0.059 | 0.0000 |

### Robustness of the kept configuration (Yahoo arm; earnings-only contamination rule)

| method | outcome | period | pairs | Spearman (pooled) | Spearman (per event) | events >=5 | hit rate | slope t | R2 gain vs B0 | MAE skill vs B0 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| crsp, contamination earn | plain | fit | 794 | 0.155 | 0.042 | 25 | 0.58 | 1.45 | 0.006 | 0.0044 |
| crsp, contamination earn | plain | choose | 253 | 0.133 | -0.092 | 9 | 0.53 | 2.16 | 0.022 | 0.0021 |
| crsp, contamination earn | adj | fit | 644 | 0.030 | -0.038 | 23 | 0.49 | 0.32 | 0.000 | 0.0008 |
| crsp, contamination earn | adj | choose | 161 | 0.327 | 0.138 | 7 | 0.60 | 2.80 | 0.049 | 0.0092 |
| yahoo, contamination any | plain | fit | 513 | 0.137 | 0.110 | 12 | 0.56 | 1.03 | 0.006 | 0.0014 |
| yahoo, contamination any | plain | choose | 191 | 0.143 | 0.163 | 7 | 0.53 | 2.11 | 0.025 | 0.0020 |
| yahoo, contamination any | adj | fit | 418 | 0.023 | 0.023 | 10 | 0.50 | 0.64 | 0.001 | 0.0010 |
| yahoo, contamination any | adj | choose | 115 | 0.378 | 0.402 | 6 | 0.63 | 2.65 | 0.058 | 0.0067 |
| yahoo, contamination earn | plain | fit | 647 | 0.170 | 0.008 | 14 | 0.58 | 1.37 | 0.008 | 0.0036 |
| yahoo, contamination earn | plain | choose | 224 | 0.150 | 0.038 | 9 | 0.53 | 2.36 | 0.027 | 0.0026 |
| yahoo, contamination earn | adj | fit | 517 | 0.024 | 0.000 | 12 | 0.50 | 0.52 | 0.001 | 0.0005 |
| yahoo, contamination earn | adj | choose | 136 | 0.345 | 0.325 | 7 | 0.60 | 2.64 | 0.052 | 0.0061 |

## E3, customer momentum portfolio

Quintiles of firms by their customers' last-month return through the graph (delta 0.7, H 1),
long top minus bottom next month, alpha on FF3 + momentum, Newey-West t.

| arm | period | weights | months | median firms | mean / month | alpha / month | alpha t |
|---|---|---|---:|---:|---:|---:|---:|
| crsp | fit | ew | 72 | 72 | 0.26% | 0.43% | 0.90 |
| crsp | fit | vw | 72 | 72 | 0.10% | 0.16% | 0.46 |
| crsp | choose | ew | 24 | 80 | 0.18% | 0.22% | 0.28 |
| crsp | choose | vw | 24 | 80 | 0.08% | 0.31% | 0.53 |
| yahoo | fit | ew | 72 | 63 | 0.38% | 0.48% | 1.13 |
| yahoo | fit | vw | 72 | 63 | -0.19% | -0.07% | -0.13 |
| yahoo | choose | ew | 24 | 74 | 0.11% | 0.18% | 0.28 |
| yahoo | choose | vw | 24 | 74 | 0.31% | 0.48% | 0.72 |

## E4, Apple guidance cut (illustration only)

Letter released after the close on 2 Jan 2019 (8-K accepted 16:30 ET), event day 3 Jan 2019. Not in the E2 panel
because the S&P 500 fell 2.5% that day. Apple AR -6.3% (z -5.5). The graph of 2 Jan 2019
links Apple to 4 priced suppliers; their mean CAR[0,+5] was -1.9%, against
-0.2% for Apple's sub-industry peers (B1) and 0.1% for its 20 most correlated
stocks (B3). Qorvo and Jabil fell as predicted; Activision and Akamai (app-store and network-service suppliers) rose.
Skyworks is missing: its FY2018 10-K tags Apple only as an anonymous customer (47%). Figure: `figures/e4_apple_replay.png`.

## What worked

- Point-in-time pipeline: graph from 10-Ks accepted before the event day, membership by date, acceptance times
  checked (SEC times are UTC), events dated from the New York clock; a guard raises on anything from 2024.
- The seed graph is accurate where it can be checked: 91% of our links to universe customers are also in
  Compustat's customer segments (407 of 446).
- Over [0,+5] the kept model's predictions line up with linked firms' CARs in both periods and both arms (pooled
  Spearman 0.15 fitting, 0.12 choosing),
  and in the choosing period the relation survives the industry adjustment (Spearman 0.39,
  slope t 2.8, 124 pairs).
- CRSP removes the survivorship gap (0.4% of member-days missing against 11.5% on Yahoo); the Yahoo results are close.

## What did not work

- The effect is small and not robust across periods. Fitting period [0,+5]: slope t 1.25 plain,
  0.86 industry-adjusted; MAE improves on B0 by only 0.34%.
  The strong choosing-period industry-adjusted number rests on 124 pairs and is not matched in the fitting period.
- No drift: over [+1,+20] the slope is negative or indistinguishable from zero in every cut (CRSP fitting t
  -1.62); lambda hits its floor of 0 in the main runs.
- The revenue-share weights add nothing clear. On the model's own pairs the unweighted neighbour baseline B2 is about
  as good: Spearman B2 0.16 vs model
  0.15 in the fitting period and
  0.09 vs
  0.12 in the choosing period,
  and B2 has the lower error (MAE) in both periods. The links carry the signal; the share weighting does not
  calibrate how much each linked firm moves.
- On plain CAR the industry and correlation baselines (B1, B3) are stronger on their own, much larger samples
  (B1 choosing slope t 5.7); that signal is industry co-movement and disappears for B1 after the
  industry adjustment.
- Variant, delta and H do not matter. At one hop M1, M2 and M3 are the same model in expectation and delta is
  absorbed by lambda; H = 3, 4 and 6 give identical results because the graph has almost no multi-hop paths between
  priced firms. The rule picked M3 over M1 at H = 1 on Monte Carlo noise of 1,000 runs, not on substance.
- E3 is null in both periods and arms (largest alpha t 1.13).

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
9. Search over variant, delta {0.2..0.9}, H {1,2,3,4,6} only; beta = 0, tier factors at their starting values.
10. M3 with 1,000 runs in the search and 10,000 for the kept configuration.
11. Power table at the top.
12. Widening: not done in this pass (see below). The raw 1-hop pair count is above 1,000, the cleaned count is not.

## Expectations

- E3: in the original customer-momentum study the effect was strongest in small, low-attention stocks. This test
  uses S&P 500 firms only, so a weak or null result is a plausible outcome; that is what we find.
- Yahoo prices miss delisted firms (18% of index tickers here). Survivors are the firms
  that did not fail or get taken over, so the Yahoo sample over-represents firms whose later news was better. For this
  test that means fewer pairs, and spillovers from bad shocks measured mostly on firms that came through them, which
  biases the measured negative spillover towards zero. The CRSP arm, with delisting returns, has no such gap.

## Assumptions and things not done

- Not done: widening the seller side (amendment 12). Compustat customer segments name about 1,250 links a year from
  848 sellers outside the index, but only for fiscal years 2020-2023 in this export, and their CRSP prices are not
  in it. Needs a second WRDS pull (seg_customer from 2014, CCM links and crsp.dsf for those sellers).
- Not done: beta and the tier factors (Stage 2), the DeepSeek replay (closed period).
- Seed graph from 10-K text and XBRL only; Compustat lists more customers than we find (we find
  43% of the universe customers it lists, many of them below 10% of sales). Short
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
