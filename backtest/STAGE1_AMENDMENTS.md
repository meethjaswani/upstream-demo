# Amendments to STAGE1_PROMPT.md

Apply these before the parameter search. Where they conflict with STAGE1_PROMPT.md, these win. Log each one in the summary as a design decision.

## Correctness
1. Event day from the acceptance time. A filing accepted after 16:00 New York time belongs to the next trading day. First check which timezone the SEC `acceptanceDateTime` field is really in. Test case: Apple's revenue letter 8-K of 2 Jan 2019 was filed after the close, so its event day must come out as 3 Jan 2019. Add this as a unit test.
2. Signed shocks. Events can be positive or negative. Propagate the magnitude, cap the magnitude at 1, then apply the sign of the seed.
3. Contaminated firms. Drop a linked firm from an event if it has its own 8-K or earnings date inside the CAR window. Report how many pairs were dropped.
4. Overlap. If one linked firm sits in the window of two events at once, keep the event with the larger predicted exposure and drop the other pair.

## Metrics
5. Per event Spearman only for events with at least 5 linked firms. Headline numbers are pooled across all event and firm pairs: pooled Spearman and the regression.
6. B0 predicts zero for everyone, so it has no ranking. Do not score it with Spearman. Use it as the null in the regression and in the error metric.
7. Rank correlation cannot see delta or lambda (at one hop the ranking depends only on the weights). So: judge the weights with rank correlation, and choose delta, H and lambda by out of sample error (mean absolute error between lambda times x and CAR) and regression R squared.
8. Add an industry adjusted CAR: the firm's CAR minus the mean CAR of firms in its GICS sub-industry that are not linked to the shocked company. Run every metric on both the plain and the adjusted CAR. The adjusted one is the stricter test of whether links add anything beyond industry.

## Search
9. Stage 1 searches only the variant (M1, M2, M3), delta and H. Fix beta at 0 and the tier factors at their starting values. Nearly every seed link is DISCLOSED with a stated share, so beta and the tier factors cannot be identified here. They are fitted in Stage 2. This also keeps the trial count low.
10. M3 uses 1,000 Monte Carlo runs during the search and 10,000 only for the configuration that is kept.

## Power
11. At the top of the summary report: number of events, number of event and firm pairs, median linked firms per event, links per year, share of tickers with missing prices.
12. If there are fewer than about 1,000 event and firm pairs, the test is too weak. Then widen the seller side of the seed graph: add any SEC filer, inside the universe or not, that names a universe company as a customer of 10% or more of revenue (2015 to 2023), as long as price data exists for it. Report "universe only" and "widened" side by side. Do not widen silently.

## Expectations to state in the summary
- E3 (customer momentum portfolio) was strongest in small, low attention stocks in the original paper. A weak or null result on large caps is a plausible outcome and should be reported as such.
- Yahoo prices miss delisted firms. State the direction of that bias.
