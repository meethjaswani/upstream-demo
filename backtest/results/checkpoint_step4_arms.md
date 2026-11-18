# Step 4 counts by data arm (same seed graph, before any model scoring)

| | CRSP | Yahoo |
|---|---:|---:|
| Universe companies | 704 | 548 |
| Seed links (all) | 3,544 | 3,544 |
| Seed links, both ends in universe | 1,279 | 1,053 |
| Seed seller-buyer pairs in universe | 337 | 249 |
| Stock-days with a valid FF3 fit | 979,203 | 868,824 |
| abs(z) >= 3 | 18,658 | 16,568 |
| ... and filing/earnings within 1 day | 9,031 | 7,989 |
| ... and abs(S&P 500) <= 2%: events | 7,636 | 6,701 |
| Events, fitting | 5,823 | 5,009 |
| Events, choosing | 1,813 | 1,692 |
| Events negative | 3,904 | 3,408 |
| Events on an earnings day | 5,570 | 5,463 |
| Events with >= 1 linked firm (1 hop) | 743 | 678 |
| Events with >= 5 linked firms (1 hop) | 70 | 42 |
| Event-firm pairs, 1 hop | 1,652 | 1,408 |
|   fitting | 1,255 | 1,047 |
|   choosing | 397 | 361 |
| Event-firm pairs, up to 4 hops | 2,050 | 1,707 |
| Pairs left, drop own 8-K/earnings in [0,+5]: fitting | 683 | 590 |
|   choosing | 229 | 212 |
| Pairs left, drop own 8-K/earnings in [+1,+20]: fitting | 307 | 261 |
|   choosing | 103 | 97 |
| Pairs left, drop own earnings only, [0,+5]: fitting | 952 | 756 |
|   choosing | 290 | 250 |
| Pairs left, drop own earnings only, [+1,+20]: fitting | 779 | 553 |
|   choosing | 222 | 176 |
| Member-days without a return (2016-2023) | 0.4% | 11.5% |

Notes
- Same seed graph in both arms: 3,544 links from 5,565 10-Ks read (1,825 with a customer disclosure),
  2015-2023, covering the CRSP index members including firms delisted before 2024 that the Yahoo arm
  cannot price.
- CRSP arm: returns include delisting returns; membership from crsp.dsp500list (spell ends capped at
  2023-12-31); market cap = abs(prc) x shrout x 1000 summed over share classes; earnings days from
  Compustat rdq. Event filter = SEC 8-K/10-Q/10-K or rdq within one trading day.
- Yahoo arm: earnings = 8-K item 2.02 or 10-Q/10-K; 11.5% of member-days have no price (delisted firms).
- Both arms use the S&P 500 index level (^GSPC) for the 2% market filter (no CRSP index file in the export).

Cross-check with Compustat customer segments (fiscal periods ending 2020-06 to 2023-12 only, 757 seller-years
present in both sources): 91% of our links to universe customers are also in Compustat (407 of 446); we find
43% of the universe customers Compustat lists (407 of 939). Compustat also lists customers below 10% of sales,
so 43% is a lower bound on our recall of 10% customers. Known miss pattern: tenants or customers written by
a short name (VICI 10-K: "Caesars"). Details in cache/ (licensed data, not committed).

Widening source for amendment 12: 848 sellers outside the index name an index company as a customer in
Compustat segments (about 1,250 links a year, 2020-2023). Using them needs their CRSP prices, which are not
in this export.
