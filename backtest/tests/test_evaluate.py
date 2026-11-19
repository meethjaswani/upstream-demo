import numpy as np
import pandas as pd
import pytest

from stage1 import evaluate


def frame(rows):
    df = pd.DataFrame(rows, columns=["k", "t", "col", "pred", "car_car_0_5", "own_car_0_5"])
    df = df.rename(columns={"car_car_0_5": "car_car_0_5"})
    df["period"] = "fit"
    df["date"] = pd.Timestamp("2019-01-02") + pd.to_timedelta(df["t"], unit="D")
    return df


def test_contaminated_pairs_dropped_and_counted():
    df = frame([(0, 100, 1, -0.02, -0.05, True), (0, 100, 2, -0.01, -0.01, False)])
    d, cnt = evaluate.clean(df, "car_0_5")
    assert list(d["col"]) == [2]
    assert cnt["dropped_contaminated"] == 1 and cnt["pairs_used"] == 1


def test_overlap_keeps_larger_exposure():
    # firm 7 sits in the windows of events at t=100 and t=103 ([0,+5] windows overlap)
    df = frame([(0, 100, 7, -0.01, -0.02, False), (1, 103, 7, -0.03, -0.04, False),
                (2, 110, 7, -0.005, 0.01, False)])
    d, cnt = evaluate.clean(df, "car_0_5")
    assert sorted(d["k"]) == [1, 2]          # t=110 starts after 103+5, so it survives
    assert cnt["dropped_overlap"] == 1


def test_lad_slope_is_weighted_median_through_origin():
    p = np.array([1.0, 1.0, 1.0, 1.0])
    c = np.array([0.5, 2.0, 2.0, 10.0])
    assert evaluate.lad_slope(p, c) == pytest.approx(2.0)
    assert evaluate.lad_slope(np.array([0.0]), np.array([1.0])) == 0.0


def test_metrics_on_a_clean_linear_relation():
    rng = np.random.default_rng(0)
    n = 400
    p = rng.normal(0, 0.01, n)
    c = 2 * p + rng.normal(0, 0.002, n)
    d = pd.DataFrame({"k": np.repeat(np.arange(80), 5), "pred": p, "car_car_0_5": c,
                      "same_ind": rng.integers(0, 2, n), "beta": rng.normal(1, 0.2, n), "size": rng.normal(24, 1, n),
                      "date": pd.Timestamp("2019-01-02") + pd.to_timedelta(np.repeat(np.arange(80), 5), unit="D")})
    m = evaluate.metrics(d, "car_0_5", "plain", lam=evaluate.lad_slope(p, c))
    assert m["spearman_pooled"] > 0.9 and m["r2"] > 0.9 and m["reg_b"] == pytest.approx(2, rel=0.05)
    assert m["mae_skill"] > 0.7 and m["n_events_5plus"] == 80 and m["hit_rate"] > 0.9
    assert m["r2_gain"] > 0.8
