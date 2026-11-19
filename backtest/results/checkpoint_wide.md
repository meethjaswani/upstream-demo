# Checkpoint before the widened search: universe-only vs widened

No model has been scored on the widened arm. Both CRSP arms now use crsp.dsi sprtrn for the 2% market
filter and historical GICS (comp.co_hgic) for industry; events are re-detected with that filter
(7,631, of which 5,819 fitting and 1,812 choosing; 7,636 with ^GSPC before). Seeds are E2 events at index
firms in both arms. Numbers from `checkpoint_wide.json`; Compustat row-level data stays in cache/.

## How the widened graph is built

- Compustat customer segments 2012-2023, ctype COMPANY: 98,617 seller-customer-year rows after summing
  salecs over segments; 40,251 resolved to a firm, 33,440 anonymous ("Not Reported", "3 Customers",
  "Customer A"; count only toward the seller's disclosed total), 24,926 unresolved names (mostly foreign or
  private: Daimler, BMW, Shell, Food Lion, Hobby Lobby). 70,796 rows have a share (salecs / sale).
- Point in time: 74,586 rows dated by the seller's 10-K acceptance on EDGAR, 24,031 by datadate + 90 days.
- Merged with the 10-K graph, one link per seller, buyer and filing: 100,042 links in all.

## Links per year (10-K acceptance year)

| year | universe-only (10-K) | widened | both sources | Compustat only | 10-K only |
|---|---:|---:|---:|---:|---:|
| 2015 | 344 | 9,567 | 122 | 9,221 | 224 |
| 2016 | 336 | 9,449 | 116 | 9,111 | 222 |
| 2017 | 357 | 9,138 | 125 | 8,779 | 234 |
| 2018 | 363 | 8,902 | 118 | 8,537 | 247 |
| 2019 | 363 | 8,589 | 133 | 8,224 | 232 |
| 2020 | 447 | 8,403 | 160 | 7,954 | 289 |
| 2021 | 449 | 8,369 | 168 | 7,917 | 284 |
| 2022 | 448 | 8,302 | 152 | 7,852 | 298 |
| 2023 | 437 | 8,320 | 157 | 7,882 | 281 |

(10-K only counts include the 10-K graph's anonymous edges.)

## What Compustat adds to the 10-K text

On the 10-Ks the text parser read: 5,037 named links only in Compustat (2,988 of them to a customer with a
CIK), 1,251 in both, 1,148 only in the 10-K text. Skyworks -> Apple FY2018: present from Compustat, 47%,
usable from 2018-11-14 18:44 ET (the FY2018 10-K); FY2019-2023 in both sources (51% to 66%).

## Event-firm pairs (linked firms reached from the seed; cleaning = amendments 3 and 4)

| | universe-only H1 | widened H1 | widened H2 | widened H3 |
|---|---:|---:|---:|---:|
| companies that can be linked firms | 704 (index) | 3,779 (CRSP common stock) | | |
| events whose seed is a customer in the graph | 2,365 | 5,308 | | |
| events with >= 1 linked firm | 743 | 3,328 | 3,401 | 3,401 |
| pairs, raw | 1,645 | 16,727 | 24,624 | 29,042 |
| [0,+5]: dropped own filing / overlap | 721 / 122 | 6,670 / 1,698 | 10,319 / 2,847 | 12,108 / 3,635 |
| [0,+5]: pairs used, fitting / choosing | 578 / 203 | 6,079 / 1,841 | 8,284 / 2,445 | 9,489 / 2,888 |
| [+1,+20]: pairs used, fitting / choosing | 251 / 89 | 2,378 / 723 | 3,185 / 951 | 3,578 / 1,100 |
| events with >= 5 linked firms, raw | 70 | 910 | 1,049 | 1,049 |
| events with >= 5 linked firms after cleaning, [0,+5] | 20 | 466 | 575 | 582 |
| median linked firms per event | 1 | 2 | 2 | 2 |

## Multi-hop paths between priced firms (graph at each year end)

| year end | universe direct | universe 2-hop | universe 3-hop | widened direct | widened 2-hop | widened 3-hop |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | 127 | 13 | 9 | 1,356 | 640 | 471 |
| 2016 | 120 | 19 | 7 | 1,420 | 660 | 521 |
| 2017 | 129 | 23 | 6 | 1,399 | 689 | 578 |
| 2018 | 123 | 24 | 5 | 1,369 | 783 | 742 |
| 2019 | 133 | 36 | 6 | 1,297 | 680 | 577 |
| 2020 | 161 | 54 | 11 | 1,293 | 707 | 646 |
| 2021 | 172 | 70 | 18 | 1,295 | 722 | 626 |
| 2022 | 160 | 63 | 10 | 1,215 | 697 | 589 |
| 2023 | 150 | 48 | 10 | 1,123 | 613 | 503 |

## Pre-registered weight tests

Written into the trial log before any widened-arm scoring (row `preregistered_weight_tests`): weights
binary / share / share x (buyer cap / seller cap)^beta for beta in {0, 0.5, 1}; H in {1, 2, 3}; shocks all /
negative / positive; 45 runs on the widened arm, M1 with the widened search's delta, fitting and choosing only.
