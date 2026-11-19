"""Pre-registered weight tests (written into the trial log before any widened-arm scoring).

5 weightings x H in {1, 2, 3} x shocks {all, negative, positive} = 45 runs per arm, M1 (linear
cascade) with delta = the widened search's selected delta, lambda fitted on the fitting period.

Weightings (buyer j -> seller i):
  binary        w = 1 for every named link (times the tier factor)
  share         w = disclosed revenue share; links without a share (1 - R_i) / (1 + n_undisclosed)
  share_cap_b   w = share x (M_j / M_i)^b, b in {0, 0.5, 1}; M = CRSP market cap on the day before
                the event; factor 1 when either cap is unknown; w itself is not capped (the
                propagation caps each firm's move at 1)
"""
import json
import sys
import time

import numpy as np
import pandas as pd

from . import engine
from .config import RESULTS
from .evaluate import evaluate
from .panel import Panel
from .search import OUT, _log, seeded_events

SCHEMES = [("binary", None), ("share", None), ("share_cap", 0.0), ("share_cap", 0.5), ("share_cap", 1.0)]
HS = [1, 2, 3]
SIGNS = ["all", "negative", "positive"]


def weight_matrix(P, k, scheme, beta, cache):
    r = P.ev.iloc[k]
    snap = P.snapshot(r["date"])
    if scheme == "share":
        return snap
    key = (r["date"], scheme, beta, int(r["t"]) if scheme == "share_cap" else None)
    if key in cache:
        return cache[key]
    if scheme == "binary":
        w = {}
        for rec in snap["recs"]:
            if rec["buyer"] is None or rec["buyer"] == rec["seller"]:
                continue
            kk = (rec["buyer"], rec["seller"])
            w[kk] = max(w.get(kk, 0.0), engine.TIERS.get(rec["tier"], 0.0))
    else:
        t = int(r["t"])
        cols = P.node_cols(snap)
        cap_row = P.mcap.values[max(t - 1, 0)]
        cap = {n: cap_row[c] for n, c in zip(snap["nodes"], cols) if c >= 0 and np.isfinite(cap_row[c]) and cap_row[c] > 0}
        w = {}
        for (j, i), base in snap["wdict"].items():
            f = (cap[j] / cap[i]) ** beta if (j in cap and i in cap) else 1.0
            w[(j, i)] = base * f
    out = {"nodes": snap["nodes"], "idx": snap["idx"], "W": engine.matrix(w, snap["nodes"])}
    cache[key] = out
    return out


def preds_for(P, ks, scheme, beta, H, sign, delta):
    cache, preds = {}, {}
    for k in ks:
        r = P.ev.iloc[k]
        if sign == "negative" and r["sign"] >= 0 or sign == "positive" and r["sign"] <= 0:
            continue
        snap = weight_matrix(P, k, scheme, beta, cache)
        seed = f"cik:{int(r['cik'])}"
        if seed not in snap["idx"]:
            continue
        p = engine.Params(beta=0.0, delta=delta, H=H)
        x = engine.signed_shock("M1", snap["W"], snap["idx"][seed], float(r["ar"]), p)
        cols = P.node_cols(P.snapshot(r["date"]))
        t, sc = int(r["t"]), P.U.col[r["symbol"]]
        preds[k] = {int(cols[i]): float(x[i]) for i in np.flatnonzero(x)
                    if cols[i] >= 0 and cols[i] != sc and P.eligible[t, cols[i]]}
    return preds


def run(arm, delta):
    P = Panel(arm)
    ks = seeded_events(P)
    rows = []
    for scheme, beta in SCHEMES:
        for H in HS:
            for sign in SIGNS:
                t0 = time.time()
                label = scheme if beta is None else f"{scheme}_b{beta}"
                preds = preds_for(P, ks, scheme, beta, H, sign, delta)
                r, cnt, _ = evaluate(P, preds, label)
                for x in r:
                    x.update({"arm": arm, "weights": label, "H": H, "shocks": sign, "delta": delta})
                rows += r
                _log("weight_test", {"weights": label, "H": H, "shocks": sign, "delta": delta, "model": "M1"}, r, arm,
                     "pre-registered weight test")
                print(f"{arm} {label} H={H} {sign}: pairs={cnt.get('car_0_5', {}).get('pairs_used')} "
                      f"({time.time() - t0:.0f}s)", flush=True)
    pd.DataFrame(rows).to_csv(OUT / f"weight_tests_{arm}.csv", index=False)


if __name__ == "__main__":
    delta = json.loads((OUT / "selected_wide.json").read_text())["delta"]
    for arm in (sys.argv[1:] or ["wide", "wide_nf"]):
        run(arm, delta)
