"""Steps 5 and 6: baselines, metrics and the Stage 1 parameter search (amendments 9 and 10).

Search: variant in {M1, M2, M3} x delta in {0.2..0.9} x H in {1,2,3,4,6}; beta = 0 and tier
factors fixed; M3 with 1,000 Monte Carlo runs. lambda is fitted on the fitting period for each
configuration. Selection: highest choosing-period MAE skill (1 - MAE / MAE of B0) on the [0,+5]
plain CAR, ties broken by choosing-period R^2. Every configuration is logged in the trial log.
"""
import json
import sys
import time

import numpy as np
import pandas as pd

from . import methods, trial_log
from .config import RESULTS
from .evaluate import common_sample, evaluate
from .panel import Panel

VARIANTS = ["M1", "M2", "M3"]
DELTAS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
HS = [1, 2, 3, 4, 6]
KEY = ("car_0_5", "plain")
LOG_KEYS = ["n_pairs", "n_events", "spearman_pooled", "spearman_event_mean", "n_events_5plus", "hit_rate",
            "reg_b", "reg_t", "r2", "r2_b0", "r2_gain", "lambda", "mae", "mae_b0", "mae_skill"]


def _log(label, params, rows, arm, note=""):
    df = pd.DataFrame(rows)
    for per in ("fit", "choose"):
        sub = df[df["period"] == per]
        m = {f"{r.window}|{r.outcome}|{k}": (None if pd.isna(getattr(r, k, None)) else getattr(r, k))
             for r in sub.itertuples() for k in LOG_KEYS if hasattr(r, k)}
        trial_log.log(label, {**params, "arm": arm}, per, m, note)


def model_preds(P, ks, variant, delta, H, n_runs):
    return {k: methods.model(P, k, variant, delta, H, n_runs) for k in ks}


def run_baselines(P, arm, contamination="any"):
    rows, preds_all = [], {}
    for name, fn in methods.BASELINES.items():
        t0 = time.time()
        preds = {k: fn(P, k) for k in range(len(P.ev))}
        preds_all[name] = preds
        r, cnt, _ = evaluate(P, preds, name, contamination)
        rows += r
        _log(name, {"contamination": contamination}, r, arm, "baseline")
        print(f"{name}: {cnt} ({time.time() - t0:.0f}s)", flush=True)
    return rows, preds_all


def seeded_events(P):
    ks = []
    for k, r in enumerate(P.ev.itertuples()):
        snap = P.snapshot(r.date)
        if snap["W"] is not None and f"cik:{int(r.cik)}" in snap["idx"]:
            ks.append(k)
    return ks


def search(arm="crsp"):
    P = Panel(arm)
    ks = seeded_events(P)
    print("events whose seed is a customer in the graph:", len(ks), flush=True)
    base_rows, base_preds = run_baselines(P, arm)
    pd.DataFrame(base_rows).to_csv(RESULTS / f"baselines_{arm}.csv", index=False)
    rows = []
    for variant in VARIANTS:
        for H in HS:
            for delta in DELTAS:
                t0 = time.time()
                preds = model_preds(P, ks, variant, delta, H, 1000)
                r, cnt, _ = evaluate(P, preds, f"{variant}")
                for x in r:
                    x.update({"variant": variant, "delta": delta, "H": H})
                rows += r
                _log(f"search_{variant}", {"variant": variant, "delta": delta, "H": H, "beta": 0.0,
                                            "tiers": "start", "n_runs": 1000 if variant == "M3" else None}, r, arm)
                key = [x for x in r if (x["window"], x["outcome"], x["period"]) == (*KEY, "choose")]
                print(f"{variant} H={H} delta={delta}: choose skill={key[0].get('mae_skill') if key else None} "
                      f"pairs={cnt.get('car_0_5', {}).get('pairs_used')} ({time.time() - t0:.0f}s)", flush=True)
    S = pd.DataFrame(rows)
    S.to_csv(RESULTS / f"search_{arm}.csv", index=False)
    sel = S[(S["window"] == KEY[0]) & (S["outcome"] == KEY[1]) & (S["period"] == "choose")]
    sel = sel.sort_values(["mae_skill", "r2"], ascending=[False, False])
    best = sel.iloc[0]
    choice = {"variant": best["variant"], "delta": float(best["delta"]), "H": int(best["H"]),
              "choose_mae_skill": float(best["mae_skill"]), "choose_r2": float(best["r2"]),
              "rule": "max choosing-period MAE skill on [0,+5] plain CAR, then R^2"}
    (RESULTS / f"selected_{arm}.json").write_text(json.dumps(choice, indent=1))
    print("selected:", choice, flush=True)
    return choice


def final(choice, arms=("crsp", "yahoo")):
    """Kept configuration (M3 with 10,000 runs) on each arm, baselines on the Yahoo arm, the
    head-to-head on the model's pairs, and the earnings-only contamination robustness check."""
    out = []
    for arm in arms:
        P = Panel(arm)
        ks = seeded_events(P)
        n_runs = 10_000 if choice["variant"] == "M3" else 1000
        preds = model_preds(P, ks, choice["variant"], choice["delta"], choice["H"], n_runs)
        params = {"variant": choice["variant"], "delta": choice["delta"], "H": choice["H"], "beta": 0.0,
                  "tiers": "start", "n_runs": n_runs}
        for cont in ("any", "earn"):
            r, cnt, df = evaluate(P, preds, f"kept_{choice['variant']}", cont)
            for x in r:
                x.update({"arm": arm, "contamination": cont, **params})
            out += r
            _log("kept", {**params, "contamination": cont}, r, arm, "kept configuration")
            if cont == "any":
                model_df = df
                (RESULTS / f"kept_counts_{arm}.json").write_text(json.dumps(cnt, indent=1))
        if arm != "crsp":
            base_rows, base_preds = run_baselines(P, arm)
            pd.DataFrame(base_rows).to_csv(RESULTS / f"baselines_{arm}.csv", index=False)
        else:
            base_preds = {name: {k: fn(P, k) for k in range(len(P.ev))} for name, fn in methods.BASELINES.items()}
        h2h = common_sample(P, model_df, preds, f"kept_{choice['variant']}")
        for name, bp in base_preds.items():
            h2h += common_sample(P, model_df, bp, name)
        for x in h2h:
            x["arm"] = arm
        pd.DataFrame(h2h).to_csv(RESULTS / f"head_to_head_{arm}.csv", index=False)
        _log("head_to_head", {"arm": arm, **params}, [x for x in h2h if x["method"].startswith("kept")], arm,
             "model scored on its own pairs (same as kept); baselines in head_to_head csv")
    pd.DataFrame(out).to_csv(RESULTS / "kept_config.csv", index=False)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "search"
    if what == "search":
        search("crsp")
    else:
        final(json.loads((RESULTS / "selected_crsp.json").read_text()))
