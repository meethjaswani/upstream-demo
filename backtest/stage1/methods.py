"""Predicted moves of universe firms for one event: the network model and baselines B1-B3.
B0 predicts zero for everyone and is used only as the null in the regression and error metric.
Every predictor returns {universe column: signed predicted move}, the seed excluded."""
import numpy as np

from . import engine

CORR_WINDOW = 250
CORR_MIN_OBS = 200
B3_N = 20


def model(P, k, variant, delta, H, n_runs=1000):
    r = P.ev.iloc[k]
    snap = P.snapshot(r["date"])
    seed = f"cik:{int(r['cik'])}"
    if snap["W"] is None or seed not in snap["idx"]:
        return {}
    p = engine.Params(beta=0.0, delta=delta, H=H, n_runs=n_runs)
    x = engine.signed_shock(variant, snap["W"], snap["idx"][seed], float(r["ar"]), p, seed=int(k))
    cols = P.node_cols(snap)
    t = int(r["t"])
    sc = P.U.col[r["symbol"]]
    out = {}
    for i in np.flatnonzero(x):
        c = cols[i]
        if c >= 0 and c != sc and P.U.member[t, c]:
            out[int(c)] = float(x[i])
    return out


def b1_industry(P, k):
    r = P.ev.iloc[k]
    t, sc = int(r["t"]), P.U.col[r["symbol"]]
    g = P.gsub[sc]
    if not g:
        return {}
    cols = np.flatnonzero((P.gsub == g) & P.U.member[t])
    return {int(c): float(r["ar"]) for c in cols if c != sc}


def b2_neighbours(P, k):
    """Firms directly linked to the seed in the graph (its suppliers and its customers), unweighted."""
    r = P.ev.iloc[k]
    snap = P.snapshot(r["date"])
    seed = f"cik:{int(r['cik'])}"
    if snap["W"] is None or seed not in snap["idx"]:
        return {}
    W = snap["W"].tocsr()
    WT = W.T.tocsr()
    s0 = snap["idx"][seed]
    nb = set(W.indices[W.indptr[s0]:W.indptr[s0 + 1]]) | set(WT.indices[WT.indptr[s0]:WT.indptr[s0 + 1]])
    cols = P.node_cols(snap)
    t, sc = int(r["t"]), P.U.col[r["symbol"]]
    return {int(cols[i]): float(r["ar"]) for i in nb if cols[i] >= 0 and cols[i] != sc and P.U.member[t, cols[i]]}


def correlations(P, t, sc):
    """Correlation of every universe firm with column sc over t-250 .. t-1 (excess returns);
    NaN for the seed, non-members and firms with fewer than 200 shared observations."""
    a = max(0, t - CORR_WINDOW)
    Y = P.y.values[a:t]
    s = Y[:, sc]
    ok_s = ~np.isnan(s)
    corr = np.full(Y.shape[1], np.nan)
    if ok_s.sum() < CORR_MIN_OBS:
        return corr
    M = Y[ok_s]
    s = s[ok_s]
    valid = (~np.isnan(M)).sum(axis=0) >= CORR_MIN_OBS
    mu = np.nanmean(M, axis=0)
    sd = np.nanstd(M, axis=0)
    sz = (s - s.mean()) / s.std()
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.nanmean(((M - mu) / sd) * sz[:, None], axis=0)
    corr[~valid | ~P.U.member[t]] = np.nan
    corr[sc] = np.nan
    return corr


def b3_correlated(P, k):
    """The 20 universe firms most correlated with the seed over the past 250 trading days
    (t-250 .. t-1, excess returns), predicted move = correlation x seed AR."""
    r = P.ev.iloc[k]
    t, sc = int(r["t"]), P.U.col[r["symbol"]]
    corr = correlations(P, t, sc)
    if np.isnan(corr).all():
        return {}
    order = np.argsort(-np.nan_to_num(corr, nan=-np.inf))[:B3_N]
    return {int(c): float(corr[c] * r["ar"]) for c in order if not np.isnan(corr[c])}


BASELINES = {"B1_industry": b1_industry, "B2_neighbours": b2_neighbours, "B3_correlated": b3_correlated}
