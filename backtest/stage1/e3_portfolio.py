"""E3: customer-momentum portfolio test.

At each month end m, a seller's signal is its customers' month-m returns passed through the
seed graph known at m: signal = sum_{h=1..H} delta^h (W^T)^h r (signed linear propagation, the
expectation of the kept configuration without the cap). Firms in the index with a non-zero
signal are sorted into quintiles; the top-minus-bottom portfolio is held over month m+1
(equal and value weighted). Monthly long-short returns are regressed on FF3 + momentum with
Newey-West (3 lags) errors, separately for the fitting and choosing periods (by return month).
"""
import json
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

from . import fetch_factors, pit, trial_log
from .config import RESULTS
from .panel import Panel

MIN_FIRMS = 20


def monthly_returns(P):
    rf = P.U.ff.loc[P.U.calendar, "rf"].values[:, None] if hasattr(P.U, "ff") else 0.0
    R = P.y.values + rf
    df = pd.DataFrame(np.log1p(R), index=P.U.calendar, columns=P.U.symbols)
    cnt = df.notna().groupby(df.index.to_period("M")).sum()
    m = np.expm1(df.groupby(df.index.to_period("M")).sum(min_count=1))
    return m.where(cnt >= 15)


def signal(snap, cols, r_month, delta, H):
    W = snap["W"]
    if W is None:
        return {}
    x = np.zeros(len(snap["nodes"]))
    ok = cols >= 0
    vals = r_month[np.maximum(cols, 0)]
    x[ok] = np.nan_to_num(vals[ok], nan=0.0)
    WT = W.T.tocsr()
    v, tot = x, np.zeros_like(x)
    for _ in range(H):
        v = delta * (WT @ v)
        tot += v
    return {int(cols[i]): float(tot[i]) for i in np.flatnonzero(tot) if cols[i] >= 0}


def run(arm, delta, H, label):
    P = Panel(arm)
    mret = monthly_returns(P)
    mcap = P.mcap
    months = mret.index
    rows = []
    for i in range(len(months) - 1):
        m, nxt = months[i], months[i + 1]
        end = m.to_timestamp(how="end").normalize()
        if end < pd.Timestamp("2015-01-31") or nxt.to_timestamp() >= pit.CUTOFF:
            continue
        cal_end = P.U.calendar[P.U.calendar <= end]
        if len(cal_end) == 0:
            continue
        t = P.U.calendar.get_loc(cal_end[-1])
        snap = P.snapshot(end + pd.Timedelta(days=1))
        if snap["W"] is None:
            continue
        cols = P.node_cols(snap)
        sig = signal(snap, cols, mret.loc[m].values, delta, H)
        sig = {c: s for c, s in sig.items() if P.eligible[t, c] and not np.isnan(mret.loc[nxt].values[c])}
        if len(sig) < MIN_FIRMS:
            continue
        s = pd.Series(sig)
        q = pd.qcut(s.rank(method="first"), 5, labels=False)
        nr = mret.loc[nxt].values
        cap = mcap.iloc[t].values
        out = {"month": str(nxt), "n_firms": len(s)}
        for wname in ("ew", "vw"):
            port = {}
            for b in (0, 4):
                c = s.index[q == b].values
                w = np.ones(len(c)) if wname == "ew" else np.nan_to_num(cap[c], nan=0.0)
                port[b] = float(np.sum(w * nr[c]) / w.sum()) if w.sum() > 0 else np.nan
            out[f"ls_{wname}"] = port[4] - port[0]
        rows.append(out)
    L = pd.DataFrame(rows)
    L["date"] = pd.PeriodIndex(L["month"], freq="M").to_timestamp(how="end").normalize()
    ffm = fetch_factors.load("m")
    ffm.index = ffm.index.normalize()
    L = L.merge(ffm, left_on="date", right_index=True, how="left")
    pit.check_frame(L, ["date"], what="E3 months")
    res = {}
    for per, (a, b) in pit.PERIODS.items():
        d = L[(L["date"] >= a) & (L["date"] <= b + pd.offsets.MonthEnd(0))].dropna(subset=["mkt_rf"])
        for wname in ("ew", "vw"):
            y = d[f"ls_{wname}"].values
            X = sm.add_constant(d[["mkt_rf", "smb", "hml", "mom"]].values)
            if len(d) < 12:
                continue
            fit = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
            res[f"{per}_{wname}"] = {"months": int(len(d)), "mean_monthly": float(np.mean(y)),
                                     "alpha_monthly": float(fit.params[0]), "alpha_t": float(fit.tvalues[0]),
                                     "median_firms": float(d["n_firms"].median())}
    L.drop(columns=["date"]).to_csv(RESULTS / f"e3_longshort_{arm}.csv", index=False)
    (RESULTS / f"e3_{arm}.json").write_text(json.dumps({"delta": delta, "H": H, **res}, indent=1))
    for per in pit.PERIODS:
        trial_log.log(f"E3_{label}", {"arm": arm, "delta": delta, "H": H, "quintiles": 5}, per,
                      {k: v for k, v in res.items() if k.startswith(per)}, "customer momentum portfolio")
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    sel = json.loads((RESULTS / "selected_crsp.json").read_text())
    for arm in (sys.argv[1:] or ["crsp", "yahoo"]):
        run(arm, sel["delta"], sel["H"], sel["variant"])
