"""E4: case replay, illustration only. Apple's revenue guidance cut, letter released after the
close on 2 Jan 2019 (8-K accepted 16:30 ET), event day 3 Jan 2019. Not in the E2 panel: the
S&P 500 fell 2.5% that day, so the 2% market filter removes it.

Seed: Apple's FF3 abnormal return on 3 Jan 2019. Graph: 10-Ks accepted before 3 Jan 2019.
Predictions of the kept configuration, B1 (same sub-industry) and B3 (20 most correlated),
against realised CARs over [0,+5] and [+1,+20]."""
import json

import numpy as np
import pandas as pd

from . import engine, events
from .config import RESULTS
from .methods import B3_N, correlations

APPLE = 320193
DAY = pd.Timestamp("2019-01-03")


def run(arm, sel):
    from .panel import Panel
    P = Panel(arm)
    t = P.U.calendar.get_loc(DAY)
    sc = P.U.col[P.U.sym_of_cik[APPLE]]
    Y = P.y.values
    ar = float(Y[t, sc] - P.X[t] @ P.B[t, sc])
    z = ar / float(P.sig[t, sc])
    snap = P.snapshot(DAY)
    params = engine.Params(beta=0.0, delta=sel["delta"], H=sel["H"], n_runs=10_000)
    x = engine.signed_shock(sel["variant"], snap["W"], snap["idx"][f"cik:{APPLE}"], ar, params, seed=2019)
    cols = P.node_cols(snap)
    pred = {int(cols[i]): float(x[i]) for i in np.flatnonzero(x) if cols[i] >= 0 and cols[i] != sc}
    car = {w: events.car(Y, P.X, P.B, t, k0, k1) for w, (k0, k1) in events.CAR_WINDOWS.items()}
    names = {}
    meta = json.loads((RESULTS.parent / "cache" / "sec" / "entity_meta.json").read_text())
    nm = {m["cik"]: m["name"] for m in meta}
    rows = []
    g = P.gsub[sc]
    b1 = [c for c in np.flatnonzero((P.gsub == g) & P.U.member[t]) if c != sc]
    corr = correlations(P, t, sc)
    b3 = list(np.argsort(-np.nan_to_num(corr, nan=-np.inf))[:B3_N])
    for c in sorted(set(pred) | set(b1) | set(b3)):
        cik = P.U.cik_of_sym[P.U.symbols[c]]
        rows.append({"firm": nm.get(cik, str(cik)), "linked": c in pred, "pred_model": pred.get(c, 0.0),
                     "pred_B1": ar if c in b1 else 0.0, "pred_B3": float(corr[c] * ar) if c in b3 else 0.0,
                     "car_0_5": float(car["car_0_5"][c]), "car_1_20": float(car["car_1_20"][c])})
    D = pd.DataFrame(rows).sort_values("pred_model")
    D.to_csv(RESULTS / f"e4_apple_{arm}.csv", index=False)
    lk = D[D["linked"]]
    summ = {"arm": arm, "apple_ar": ar, "apple_z": z, "config": sel, "linked_firms": int(len(lk)),
            "linked_mean_car_0_5": float(lk["car_0_5"].mean()) if len(lk) else None,
            "linked_mean_car_1_20": float(lk["car_1_20"].mean()) if len(lk) else None,
            "b1_mean_car_0_5": float(D.loc[D["pred_B1"] != 0, "car_0_5"].mean()),
            "b3_mean_car_0_5": float(D.loc[D["pred_B3"] != 0, "car_0_5"].mean())}
    (RESULTS / f"e4_apple_{arm}.json").write_text(json.dumps(summ, indent=1, default=str))
    print(json.dumps(summ, indent=1, default=str))
    print(lk[["firm", "pred_model", "car_0_5", "car_1_20"]].round(4).to_string(index=False))
    return D, summ


if __name__ == "__main__":
    sel = json.loads((RESULTS / "selected_crsp.json").read_text())
    run("crsp", sel)
