"""Steps 5 and 6: baselines, metrics and the Stage 1 parameter search (amendments 9 and 10), per arm.

Search: variant in {M1, M2, M3} x delta in {0.2..0.9} x H in {1,2,3,4,6}; beta = 0 and tier
factors fixed; M3 with 1,000 Monte Carlo runs. lambda is fitted on the fitting period for each
configuration. Selection: highest choosing-period MAE skill (1 - MAE / MAE of B0) on the [0,+5]
plain CAR, ties broken by choosing-period R^2. Kept configuration re-run (M3 with 10,000 runs),
with the earnings-only contamination rule as robustness and every baseline scored on the model's
own pairs. Every run is logged in the trial log.

Arms: 'crsp' (index firms, 10-K graph), 'wide' (widened graph and firms), 'wide_nf' (widened,
without Compustat rows dated by datadate + 90 days), 'yahoo'.
"""
import json
import sys
import time

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
OUT = RESULTS / "widening"
OUT.mkdir(exist_ok=True)


def _log(label, params, rows, arm, note=""):
    df = pd.DataFrame(rows)
    for per in ("fit", "choose"):
        sub = df[df["period"] == per]
        m = {f"{r.window}|{r.outcome}|{k}": (None if pd.isna(getattr(r, k, None)) else getattr(r, k))
             for r in sub.itertuples() for k in LOG_KEYS if hasattr(r, k)}
        trial_log.log(label, {**params, "arm": arm}, per, m, note)


def model_preds(P, ks, variant, delta, H, n_runs):
    return {k: methods.model(P, k, variant, delta, H, n_runs) for k in ks}


def seeded_events(P):
    ks = []
    for k, r in enumerate(P.ev.itertuples()):
        snap = P.snapshot(r.date)
        if snap["W"] is not None and f"cik:{int(r.cik)}" in snap["idx"]:
            ks.append(k)
    return ks


def run_baselines(P, arm, contamination="any"):
    rows, preds_all = [], {}
    for name, fn in methods.BASELINES.items():
        t0 = time.time()
        preds = {k: fn(P, k) for k in range(len(P.ev))}
        preds_all[name] = preds
        r, cnt, _ = evaluate(P, preds, name, contamination)
        for x in r:
            x["arm"] = arm
        rows += r
        _log(name, {"contamination": contamination}, r, arm, "baseline")
        print(f"{arm} {name}: {cnt} ({time.time() - t0:.0f}s)", flush=True)
    return rows, preds_all


def run_arm(arm, grid=True):
    t_start = time.time()
    P = Panel(arm)
    ks = seeded_events(P)
    print(f"{arm}: events {len(P.ev)}, seed is a customer in the graph {len(ks)}, firms {P.S}", flush=True)
    base_rows, base_preds = run_baselines(P, arm)
    pd.DataFrame(base_rows).to_csv(OUT / f"baselines_{arm}.csv", index=False)
    if grid:
        rows = []
        for variant in VARIANTS:
            for H in HS:
                for delta in DELTAS:
                    t0 = time.time()
                    preds = model_preds(P, ks, variant, delta, H, 1000)
                    r, cnt, _ = evaluate(P, preds, variant)
                    for x in r:
                        x.update({"variant": variant, "delta": delta, "H": H, "arm": arm})
                    rows += r
                    _log(f"search_{variant}", {"variant": variant, "delta": delta, "H": H, "beta": 0.0,
                                                "tiers": "start", "n_runs": 1000 if variant == "M3" else None}, r, arm)
                    key = [x for x in r if (x["window"], x["outcome"], x["period"]) == (*KEY, "choose")]
                    print(f"{arm} {variant} H={H} delta={delta}: choose skill={key[0].get('mae_skill') if key else None} "
                          f"pairs={cnt.get('car_0_5', {}).get('pairs_used')} ({time.time() - t0:.0f}s)", flush=True)
        S = pd.DataFrame(rows)
        S.to_csv(OUT / f"search_{arm}.csv", index=False)
        sel = S[(S["window"] == KEY[0]) & (S["outcome"] == KEY[1]) & (S["period"] == "choose")]
        best = sel.sort_values(["mae_skill", "r2"], ascending=[False, False]).iloc[0]
        choice = {"variant": best["variant"], "delta": float(best["delta"]), "H": int(best["H"]),
                  "choose_mae_skill": float(best["mae_skill"]), "choose_r2": float(best["r2"]),
                  "rule": "max choosing-period MAE skill on [0,+5] plain CAR, then R^2"}
        (OUT / f"selected_{arm}.json").write_text(json.dumps(choice, indent=1))
        print(f"{arm} selected: {choice}", flush=True)
    else:
        choice = json.loads((OUT / "selected_crsp.json").read_text())
    kept(P, ks, arm, choice, base_preds)
    print(f"{arm} done in {(time.time() - t_start) / 60:.0f} min", flush=True)
    return choice


def kept(P, ks, arm, choice, base_preds):
    n_runs = 10_000 if choice["variant"] == "M3" else 1000
    preds = model_preds(P, ks, choice["variant"], choice["delta"], choice["H"], n_runs)
    params = {"variant": choice["variant"], "delta": choice["delta"], "H": choice["H"], "beta": 0.0,
              "tiers": "start", "n_runs": n_runs}
    out, model_df = [], None
    for cont in ("any", "earn"):
        r, cnt, df = evaluate(P, preds, f"kept_{choice['variant']}", cont)
        for x in r:
            x.update({"arm": arm, "contamination": cont, **params})
        out += r
        _log("kept", {**params, "contamination": cont}, r, arm, "kept configuration")
        if cont == "any":
            model_df = df
            (OUT / f"kept_counts_{arm}.json").write_text(json.dumps(cnt, indent=1))
    pd.DataFrame(out).to_csv(OUT / f"kept_{arm}.csv", index=False)
    h2h = common_sample(P, model_df, preds, f"kept_{choice['variant']}")
    for name, bp in base_preds.items():
        h2h += common_sample(P, model_df, bp, name)
    for x in h2h:
        x["arm"] = arm
    pd.DataFrame(h2h).to_csv(OUT / f"head_to_head_{arm}.csv", index=False)
    _log("head_to_head", {**params}, [x for x in h2h if not x["method"].startswith("kept")], arm,
         "baselines scored on the kept model's own pairs")


if __name__ == "__main__":
    for arm in (sys.argv[1:] or ["crsp", "wide", "wide_nf"]):
        run_arm(arm)
