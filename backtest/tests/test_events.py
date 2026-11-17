import numpy as np
import pandas as pd
import pytest

from stage1 import events, pit


def synth(T=700, S=3, seed=0, shock=None):
    rng = np.random.default_rng(seed)
    f = rng.normal(0, 0.01, (T, 3))
    X = np.column_stack([np.ones(T), f])
    beta = np.array([[0.0002, 1.0, 0.3, -0.2], [0.0, 0.8, -0.1, 0.5], [0.0001, 1.2, 0.0, 0.0]])[:S]
    Y = X @ beta.T + rng.normal(0, 0.01, (T, S))
    if shock:
        for (t, s), v in shock.items():
            Y[t, s] += v
    return Y, X, beta


def test_rolling_ff3_recovers_loadings_and_uses_only_past():
    Y, X, beta = synth()
    B, sig, n = events.rolling_ff3(Y, X)
    t = 500
    assert n[t, 0] == 250
    assert np.allclose(B[t, :, 1:], beta[:, 1:], atol=0.15)
    assert np.allclose(sig[t], 0.01, rtol=0.15)
    # changing data on day t-10 .. t+5 must not change the day-t fit
    Y2 = Y.copy()
    Y2[t - 10:t + 6] += 0.5
    B2, sig2, _ = events.rolling_ff3(Y2, X)
    assert np.allclose(B[t], B2[t]) and np.allclose(sig[t], sig2[t])


def test_no_fit_before_enough_history():
    Y, X, _ = synth(T=300)
    B, sig, n = events.rolling_ff3(Y, X)
    assert np.isnan(sig[:260]).all()
    assert not np.isnan(sig[270]).any()


def test_missing_returns_reduce_obs_and_min_obs_enforced():
    Y, X, _ = synth()
    Y[300:340, 1] = np.nan
    B, sig, n = events.rolling_ff3(Y, X)
    assert n[400, 1] == 250 - 40 and not np.isnan(sig[400, 1])
    Y[300:380, 1] = np.nan
    B, sig, n = events.rolling_ff3(Y, X)
    assert np.isnan(sig[400, 1])          # 170 < 200 obs


def test_abnormal_return_flags_injected_shock():
    Y, X, _ = synth(shock={(500, 2): -0.08})
    B, sig, _ = events.rolling_ff3(Y, X)
    AR = events.abnormal(Y, X, B)
    z = AR / sig
    assert z[500, 2] < -3
    assert np.nanmean(np.abs(z[400:600]) >= 3) < 0.02


def test_car_sums_abnormal_returns_with_event_day_coefficients():
    Y, X, _ = synth()
    B, sig, _ = events.rolling_ff3(Y, X)
    t = 450
    c = events.car(Y, X, B, t, 1, 20)
    manual = sum(Y[t + k] - X[t + k] @ B[t].T for k in range(1, 21))
    assert np.allclose(c, manual)
    assert np.isnan(events.car(Y, X, B, len(Y) - 5, 1, 20)).all()


def test_effective_day_uses_16h_cutoff_and_weekends():
    cal = pd.bdate_range("2019-01-07", "2019-01-18")
    acc = pd.to_datetime(["2019-01-08 09:00", "2019-01-08 16:30", "2019-01-12 10:00", "2019-01-11 17:00"])
    i = events.effective_day_index(acc, cal)
    assert list(cal[i]) == list(pd.to_datetime(["2019-01-08", "2019-01-09", "2019-01-14", "2019-01-14"]))


def test_filing_flags_window_and_earnings():
    cal = pd.bdate_range("2019-01-07", "2019-01-25")
    fil = pd.DataFrame({"cik": [1, 1, 2], "form": ["8-K", "8-K", "10-Q"],
                        "items": ["2.02,9.01", "8.01", None],
                        "accepted": pd.to_datetime(["2019-01-10 07:00", "2019-01-22 18:00", "2019-01-15 12:00"])})
    any_f, earn = events.filing_flags(fil, cal, {1: "A", 2: "B"}, ["A", "B"])
    d = {x: k for k, x in enumerate(cal)}
    a = pd.Timestamp
    assert any_f[d[a("2019-01-09")], 0] and any_f[d[a("2019-01-10")], 0] and any_f[d[a("2019-01-11")], 0]
    assert not any_f[d[a("2019-01-14")], 0]
    assert earn[d[a("2019-01-10")], 0] and not earn[d[a("2019-01-23")], 0]
    assert any_f[d[a("2019-01-23")], 0] and any_f[d[a("2019-01-24")], 0]   # after-hours -> next day
    assert earn[d[a("2019-01-15")], 1]


def make_panel(T=900, shock_t=700, filing=True, spx=0.0, start="2018-06-01"):
    Y, X, _ = synth(T=T, shock={(shock_t, 0): -0.1})
    cal = pd.bdate_range(start, periods=T)
    B, sig, _ = events.rolling_ff3(Y, X)
    member = np.ones_like(Y, dtype=bool)
    spx_ret = np.zeros(T)
    spx_ret[shock_t] = spx
    any_f = np.zeros_like(member)
    if filing:
        any_f[shock_t, 0] = True
    earn = any_f.copy()
    return events.detect(Y, X, B, sig, member, spx_ret, any_f, earn, cal, ["A", "B", "C"]), cal


def test_detect_requires_filing_and_calm_market():
    (ev, funnel), cal = make_panel()
    assert len(ev) == 1 and ev.iloc[0]["symbol"] == "A" and ev.iloc[0]["sign"] == -1
    assert ev.iloc[0]["period"] in ("fit", "choose")
    (ev2, _), _ = make_panel(filing=False)
    assert len(ev2) == 0
    (ev3, _), _ = make_panel(spx=-0.025)
    assert len(ev3) == 0
    assert funnel["abs_z_ge_3"] >= funnel["and_filing_within_1d"] >= funnel["and_spx_within_2pct"] == 1


def test_period_embargo_keeps_forward_window_inside_period():
    cal = pd.bdate_range("2021-11-01", "2022-02-28")
    lab = events.period_of(cal)
    s = pd.Series(lab, index=cal)
    last_fit = s[s == "fit"].index.max()
    assert last_fit < pd.Timestamp("2021-12-31")
    assert cal.get_loc(pd.Timestamp("2021-12-31")) - cal.get_loc(last_fit) == events.POST
    assert s[pd.Timestamp("2022-01-03")] == "choose"


def test_period_labels_never_include_closed_period():
    cal = pd.bdate_range("2023-10-01", "2023-12-29")
    lab = events.period_of(cal)
    assert set(lab) <= {"choose", ""}


def test_guard_raises_on_2024():
    with pytest.raises(pit.ClosedPeriodError):
        pit.check_date("2024-01-02")
    with pytest.raises(pit.ClosedPeriodError):
        pit.check_dates(pd.to_datetime(["2023-12-29", "2024-01-03"]))
    with pytest.raises(pit.ClosedPeriodError):
        pit.period("test")
    df = pd.DataFrame({"date": pd.to_datetime(["2023-12-29", "2024-01-03"])})
    assert len(pit.clip(df, "date")) == 1
    pit.check_dates(pd.to_datetime(["2023-12-29"]))
