"""Abnormal returns and the E2 shock panel.

FF3 market model per stock and day t, fitted on trading days t-260 .. t-11 (250 days,
at least MIN_OBS valid), with an intercept:
    r - rf = a + b1 mkt_rf + b2 smb + b3 hml + e
AR_t = (r_t - rf_t) - X_t b_t,   sigma_t = residual s.d. of that window.

Event on (stock, t):
    |AR_t| >= 3 sigma_t
    stock in the S&P 500 on t (point in time)
    an 8-K, 10-Q or 10-K whose effective day is within one trading day of t
      (effective day = acceptance day, or the next trading day if accepted after 16:00 ET)
    |S&P 500 return on t| <= 2%
    t in an open period, with t+20 trading days still inside that period
"""
import numpy as np
import pandas as pd

from . import pit

EST_START, EST_END = 260, 11      # estimation window: t-260 .. t-11
MIN_OBS = 200
Z_MIN = 3.0
SPX_MAX = 0.02
FILING_WINDOW = 1
CAR_WINDOWS = {"car_0_5": (0, 5), "car_1_20": (1, 20)}
POST = 20                          # longest forward window, used for the period embargo


# ---------------------------------------------------------------- returns and factors
def excess_returns(prices, ff, symbols=None):
    """Daily excess returns (dates x symbols) on the trading calendar shared by prices and FF."""
    pit.check_frame(prices, ["date"], what="prices")
    pit.check_frame(ff, index=True, what="ff")
    px = prices.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    if symbols is not None:
        px = px.reindex(columns=symbols)
    ret = px.pct_change(fill_method=None)
    cal = ret.index.intersection(ff.index)
    ret, f = ret.loc[cal], ff.loc[cal]
    y = ret.sub(f["rf"], axis=0)
    X = np.column_stack([np.ones(len(f)), f["mkt_rf"].values, f["smb"].values, f["hml"].values])
    return y, X


def rolling_ff3(y, X, est_start=EST_START, est_end=EST_END, min_obs=MIN_OBS):
    """Coefficients B (T x S x 4), residual s.d. sig (T x S) and n obs (T x S) for the
    window t-est_start .. t-est_end, using only data before t."""
    Y = y.values if hasattr(y, "values") else np.asarray(y)
    T, S = Y.shape
    k = X.shape[1]
    XX = np.einsum("ti,tj->tij", X, X)
    B = np.full((T, S, k), np.nan)
    sig = np.full((T, S), np.nan)
    nobs = np.zeros((T, S), dtype=int)
    hi = np.arange(T) - est_end            # last row in window
    lo = np.arange(T) - est_start - 1      # row before the first row in window
    ok_t = lo >= -1
    for s in range(S):
        m = ~np.isnan(Y[:, s])
        y0 = np.where(m, Y[:, s], 0.0)
        Cxx = np.cumsum(XX * m[:, None, None], axis=0)
        Cxy = np.cumsum(X * (y0 * m)[:, None], axis=0)
        Cyy = np.cumsum(y0 * y0)
        Cn = np.cumsum(m.astype(int))

        def win(C, t_hi, t_lo):
            out = C[t_hi]
            return out - np.where((t_lo >= 0).reshape((-1,) + (1,) * (C.ndim - 1)), C[np.maximum(t_lo, 0)], 0)

        idx = np.flatnonzero(ok_t & (hi >= 0))
        if len(idx) == 0:
            continue
        th, tl = hi[idx], lo[idx]
        Sxx, Sxy, Syy, Sn = win(Cxx, th, tl), win(Cxy, th, tl), win(Cyy, th, tl), win(Cn, th, tl)
        good = Sn >= min_obs
        if not good.any():
            continue
        g = idx[good]
        b = np.linalg.solve(Sxx[good], Sxy[good][..., None])[..., 0]
        ssr = Syy[good] - np.einsum("ij,ij->i", b, Sxy[good])
        B[g, s] = b
        sig[g, s] = np.sqrt(np.maximum(ssr, 0) / (Sn[good] - k))
        nobs[g, s] = Sn[good]
    return B, sig, nobs


def abnormal(y, X, B):
    Y = y.values if hasattr(y, "values") else np.asarray(y)
    return Y - np.einsum("tk,tsk->ts", X, B)


def car(y, X, B, t, k0, k1):
    """CAR over trading days t+k0 .. t+k1 for every stock, with the coefficients fitted for
    day t (window t-260 .. t-11). NaN if the window runs off the data or a return is missing."""
    Y = y.values if hasattr(y, "values") else np.asarray(y)
    T = Y.shape[0]
    if t + k1 >= T:
        return np.full(Y.shape[1], np.nan)
    rows = np.arange(t + k0, t + k1 + 1)
    pred = X[rows] @ B[t].T                     # (len, S)
    return np.sum(Y[rows] - pred, axis=0)       # NaN propagates if any day is missing


# ---------------------------------------------------------------- filings
def effective_day_index(accepted, calendar):
    """Trading-day index a filing can first move the price: same day if accepted by 16:00 ET
    on a trading day, otherwise the next trading day."""
    acc = pd.to_datetime(pd.Series(accepted)).reset_index(drop=True)
    day = acc.dt.normalize()
    after = (acc - day) > pd.Timedelta(hours=16)
    cal = pd.DatetimeIndex(calendar)
    i = cal.searchsorted(day.values, side="left")
    same = (i < len(cal)) & (cal[np.minimum(i, len(cal) - 1)] == day.values)
    i = np.where(same & after.values, i + 1, i)
    return i  # == len(cal) means after the calendar ends


def filing_flags(filings, calendar, sym_of_cik, symbols):
    """Boolean T x S arrays: any 8-K/10-Q/10-K within FILING_WINDOW trading days, and earnings
    (8-K item 2.02 or a 10-Q/10-K) within the same window."""
    T, S = len(calendar), len(symbols)
    col = {s: k for k, s in enumerate(symbols)}
    any_f = np.zeros((T, S), dtype=bool)
    earn = np.zeros((T, S), dtype=bool)
    f = filings[filings["cik"].isin(sym_of_cik.keys())].copy()
    f["e"] = effective_day_index(f["accepted"], calendar)
    f["s"] = f["cik"].map(lambda c: col.get(sym_of_cik[c], -1))
    f = f[(f["s"] >= 0) & (f["e"] < T)]
    is_earn = (f["form"].isin(["10-Q", "10-K", "10-K405", "10-KT"]) |
               f["items"].fillna("").str.contains(r"\b2\.02\b", regex=True)).values
    for d in range(-FILING_WINDOW, FILING_WINDOW + 1):
        t = f["e"].values - d          # filing at e counts for event days e-1 .. e+1
        ok = (t >= 0) & (t < T)
        any_f[t[ok], f["s"].values[ok]] = True
        earn[t[ok & is_earn], f["s"].values[ok & is_earn]] = True
    return any_f, earn


# ---------------------------------------------------------------- panel
def period_of(calendar):
    """Label each trading day 'fit', 'choose' or '' (embargo: t+POST must be in the same period)."""
    cal = pd.DatetimeIndex(calendar)
    lab = np.array([""] * len(cal), dtype=object)
    for name, (a, b) in pit.PERIODS.items():
        inside = (cal >= a) & (cal <= b)
        idx = np.flatnonzero(inside)
        if len(idx):
            last_ok = idx[-1] - POST
            lab[idx[idx <= last_ok]] = name
    return lab


def detect(y, X, B, sig, member, spx_ret, any_filing, earnings, calendar, symbols):
    """Returns the event table. member: T x S bool (in the index on t). spx_ret: length T."""
    AR = abnormal(y, X, B)
    z = AR / sig
    per = period_of(calendar)
    cond_z = np.abs(z) >= Z_MIN
    cond = cond_z & member & any_filing & (np.abs(np.asarray(spx_ret))[:, None] <= SPX_MAX)
    cond &= (per != "")[:, None]
    cond &= ~np.isnan(z)
    t, s = np.nonzero(cond)
    ev = pd.DataFrame({"t": t, "date": pd.DatetimeIndex(calendar)[t], "symbol": np.asarray(symbols)[s],
                       "s": s, "ar": AR[t, s], "sigma": sig[t, s], "z": z[t, s],
                       "earnings": earnings[t, s], "period": per[t]})
    ev["sign"] = np.sign(ev["ar"]).astype(int)
    # funnel counts for the report
    base = member & (per != "")[:, None] & ~np.isnan(z)
    funnel = {
        "stock_days_in_index_with_fit": int(base.sum()),
        "abs_z_ge_3": int((base & cond_z).sum()),
        "and_filing_within_1d": int((base & cond_z & any_filing).sum()),
        "and_spx_within_2pct": int(cond.sum()),
    }
    return ev.sort_values(["date", "symbol"]).reset_index(drop=True), funnel
