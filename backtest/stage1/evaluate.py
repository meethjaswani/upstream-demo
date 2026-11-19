"""Pairs, cleaning and metrics (amendments 3-8).

pairs(): one row per (event, linked firm) with the prediction, CARs, industry-adjusted CARs,
  own-filing flags per window and controls.
clean(): amendment 3 (drop firms with their own 8-K or earnings day inside the CAR window) and
  amendment 4 (a firm inside two events' windows at once: keep the pair with the larger
  predicted exposure). Counts of both drops are returned.
metrics():
  - per-event Spearman only for events with >= 5 linked firms (amendment 5)
  - pooled Spearman over all pairs (headline)
  - hit rate: share of pairs where the CAR has the predicted sign (all, and above the method's
    fitting-period median |prediction|)
  - pooled OLS of CAR on prediction + same sub-industry + beta + log size, errors clustered by
    event date; B0 = the same regression without the prediction (amendment 6)
  - lambda fitted on the fitting period by least absolute deviation through the origin; MAE of
    lambda x prediction vs CAR, against B0's MAE (mean |CAR|) (amendment 7)
Every metric is computed for the plain and the industry-adjusted CAR (amendment 8).
"""
import bisect

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr

from .panel import WINDOWS

OUTCOMES = {"plain": "car", "adj": "adj"}


def pairs(P, preds):
    """preds: {event k: {col: pred}} -> DataFrame."""
    rows = []
    for k, d in preds.items():
        if not d:
            continue
        cols = np.fromiter(d.keys(), dtype=int)
        pr = np.fromiter(d.values(), dtype=float)
        same, beta, size = P.controls(k, cols)
        r = P.ev.iloc[k]
        base = {"k": k, "t": int(r["t"]), "date": r["date"], "period": r["period"]}
        df = pd.DataFrame({"col": cols, "pred": pr, "same_ind": same, "beta": beta, "size": size})
        car = P.car_vec(k)
        adj = P.adj_vec(k, car)
        for w in WINDOWS:
            df[f"car_{w}"] = car[w][cols]
            df[f"adj_{w}"] = adj[w][cols]
            df[f"own_{w}"] = P.own_in_window(k, cols, w)
            df[f"ownearn_{w}"] = P.own_in_window(k, cols, w, which="earn")
        for c, v in base.items():
            df[c] = v
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def clean(df, w, contamination="any"):
    """Returns (cleaned pairs for window w, counts). contamination: 'any' (own 8-K, 10-Q, 10-K or
    earnings day, amendment 3 as written) or 'earn' (earnings days only, robustness)."""
    k0, k1 = WINDOWS[w]
    n0 = len(df)
    d = df[df[f"car_{w}"].notna() & (df["pred"] != 0)]
    n_valid = len(d)
    d = d[~d[f"own_{w}" if contamination == "any" else f"ownearn_{w}"]]
    n_contam = n_valid - len(d)
    d = d.assign(a=d["t"] + k0, b=d["t"] + k1, mag=d["pred"].abs()).sort_values("mag", ascending=False, kind="mergesort")
    keep = np.zeros(len(d), dtype=bool)
    taken = {}
    L = k1 - k0                      # all windows have the same length: overlap iff starts differ by <= L
    for i, (c, a) in enumerate(zip(d["col"].values, d["a"].values)):
        starts = taken.setdefault(c, [])
        j = bisect.bisect_left(starts, a - L)
        if j < len(starts) and starts[j] <= a + L:
            continue
        bisect.insort(starts, a)
        keep[i] = True
    out = d[keep].drop(columns=["a", "b", "mag"])
    return out, {"pairs_raw": n0, "pairs_with_car": n_valid, "dropped_contaminated": n_contam,
                 "dropped_overlap": int((~keep).sum()), "pairs_used": int(len(out))}


def lad_slope(p, c):
    """argmin_{l >= 0} sum |c - l p| = weighted median of c/p with weights |p|, floored at 0.
    The model says linked firms move with the seed; a negative scale would reward a reversed
    sign, so lambda stops at 0 (the B0 prediction). The regression slope is reported unconstrained."""
    m = (p != 0) & ~np.isnan(c)
    if m.sum() == 0:
        return 0.0
    ratio, wt = c[m] / p[m], np.abs(p[m])
    o = np.argsort(ratio)
    cw = np.cumsum(wt[o])
    return max(0.0, float(ratio[o][np.searchsorted(cw, 0.5 * cw[-1])]))


def _ols(y, Xc, groups):
    X = sm.add_constant(Xc, has_constant="add")
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    if ok.sum() < X.shape[1] + 5:
        return None
    try:
        m = sm.OLS(y[ok], X[ok]).fit(cov_type="cluster", cov_kwds={"groups": groups[ok]})
    except Exception:
        return None
    return m


def metrics(d, w, outcome, lam=None):
    """Metrics on cleaned pairs d (one period). lam: lambda from the fitting period."""
    c = d[f"{OUTCOMES[outcome]}_{w}"].values.astype(float)
    p = d["pred"].values.astype(float)
    ok = ~np.isnan(c)
    d, c, p = d[ok], c[ok], p[ok]
    out = {"n_pairs": int(len(d)), "n_events": int(d["k"].nunique()) if len(d) else 0}
    if len(d) < 10:
        return out
    out["spearman_pooled"] = float(spearmanr(p, c).statistic)
    per = []
    for _, g in d.assign(_c=c, _p=p).groupby("k"):
        if len(g) >= 5 and g["_p"].nunique() > 1:
            per.append(spearmanr(g["_p"], g["_c"]).statistic)
    out["n_events_5plus"] = len(per)
    out["spearman_event_mean"] = float(np.nanmean(per)) if per else None
    out["hit_rate"] = float(np.mean(np.sign(c) == np.sign(p)))
    groups = pd.factorize(d["date"])[0]
    ctrl = np.column_stack([d["same_ind"], d["beta"], d["size"]]).astype(float)
    full = _ols(c, np.column_stack([p, ctrl]), groups)
    null = _ols(c, ctrl, groups)
    if full is not None:
        out.update({"reg_b": float(full.params[1]), "reg_t": float(full.tvalues[1]), "r2": float(full.rsquared)})
    if null is not None:
        out["r2_b0"] = float(null.rsquared)
    if full is not None and null is not None:
        out["r2_gain"] = out["r2"] - out["r2_b0"]
    out["mae_b0"] = float(np.mean(np.abs(c)))
    if lam is not None:
        out["lambda"] = lam
        out["mae"] = float(np.mean(np.abs(c - lam * p)))
        out["mae_skill"] = 1 - out["mae"] / out["mae_b0"]
    return out


def evaluate(P, preds, label, contamination="any", df=None):
    """All windows x outcomes x periods for one method. Returns (rows, counts, pairs frame)."""
    df = pairs(P, preds) if df is None else df
    rows, counts = [], {}
    for w in WINDOWS:
        if df.empty:
            continue
        d, cnt = clean(df, w, contamination)
        counts[w] = cnt
        fit = d[d["period"] == "fit"]
        thr = float(fit["pred"].abs().median()) if len(fit) else 0.0
        for o in OUTCOMES:
            lam = lad_slope(fit["pred"].values, fit[f"{OUTCOMES[o]}_{w}"].values.astype(float)) if len(fit) else 0.0
            for per in ("fit", "choose"):
                dd = d[d["period"] == per]
                m = metrics(dd, w, o, lam)
                top = dd[dd["pred"].abs() > thr]
                cc = top[f"{OUTCOMES[o]}_{w}"].values.astype(float)
                okk = ~np.isnan(cc)
                m["hit_rate_top"] = float(np.mean(np.sign(cc[okk]) == np.sign(top["pred"].values[okk]))) if okk.sum() else None
                rows.append({"method": label, "window": w, "outcome": o, "period": per, **m,
                             **{f"cnt_{k}": v for k, v in cnt.items()}})
    return rows, counts, df


def common_sample(P, model_df, other_preds, label, contamination="any"):
    """Score another predictor on the model's cleaned pairs (its prediction, 0 where it has none),
    so methods are compared on identical event-firm pairs."""
    rows = []
    for w in WINDOWS:
        d, _ = clean(model_df, w, contamination)
        alt = np.array([other_preds.get(k, {}).get(c, 0.0) for k, c in zip(d["k"], d["col"])])
        d = d.assign(pred=alt)
        fit = d[d["period"] == "fit"]
        for o in OUTCOMES:
            lam = lad_slope(fit["pred"].values, fit[f"{OUTCOMES[o]}_{w}"].values.astype(float))
            for per in ("fit", "choose"):
                m = metrics(d[d["period"] == per], w, o, lam)
                m["share_pairs_predicted"] = float((d.loc[d["period"] == per, "pred"] != 0).mean()) if len(d) else None
                rows.append({"method": label, "sample": "model_pairs", "window": w, "outcome": o, "period": per, **m})
    return rows
