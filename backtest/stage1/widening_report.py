"""Tables for results/widening/widening_summary.md (universe-only vs widened vs widened without the
datadate + 90 rows). The narrative sections are written by hand below the tables."""
import json

import numpy as np
import pandas as pd

from .config import RESULTS
from .search import OUT

ARMS = {"crsp": "universe-only", "wide": "widened", "wide_nf": "widened, no +90d rows"}
M = [("n_pairs", "pairs", "{:,.0f}"), ("spearman_pooled", "Spearman", "{:.3f}"),
     ("spearman_event_mean", "per-event Spearman", "{:.3f}"), ("n_events_5plus", "events>=5", "{:,.0f}"),
     ("hit_rate", "hit", "{:.2f}"), ("reg_t", "slope t", "{:.2f}"), ("r2_gain", "R2 gain", "{:.3f}"),
     ("mae_skill", "MAE skill", "{:.4f}")]


def f(v, fmt):
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else fmt.format(v)


def tab(df, keys, cols=M):
    head = "| " + " | ".join(k for k, _ in keys) + " | " + " | ".join(c[1] for c in cols) + " |"
    sep = "|" + "---|" * len(keys) + "---:|" * len(cols)
    lines = [head, sep]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(fn(r)) for _, fn in keys) + " | " +
                     " | ".join(f(r.get(c), fm) for c, _, fm in cols) + " |")
    return "\n".join(lines)


def load(name, arm):
    p = OUT / f"{name}_{arm}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def kept_table(window):
    rows = []
    for arm in ARMS:
        k = load("kept", arm)
        if k.empty:
            continue
        k = k[(k["contamination"] == "any") & (k["window"] == window)]
        rows.append(k.assign(arm_label=ARMS[arm]))
    d = pd.concat(rows, ignore_index=True)
    return tab(d, [("arm", lambda r: r["arm_label"]), ("config", lambda r: f"{r['variant']} d{r['delta']} H{r['H']}"),
                   ("outcome", lambda r: r["outcome"]), ("period", lambda r: r["period"])])


def baselines_table(window, outcome):
    rows = []
    for arm in ARMS:
        b = load("baselines", arm)
        if b.empty:
            continue
        rows.append(b[(b["window"] == window) & (b["outcome"] == outcome)].assign(arm_label=ARMS[arm]))
    d = pd.concat(rows, ignore_index=True)
    return tab(d, [("arm", lambda r: r["arm_label"]), ("method", lambda r: r["method"]), ("period", lambda r: r["period"])])


def h2h_table(window, outcome):
    rows = []
    for arm in ARMS:
        h = load("head_to_head", arm)
        if h.empty:
            continue
        rows.append(h[(h["window"] == window) & (h["outcome"] == outcome)].assign(arm_label=ARMS[arm]))
    d = pd.concat(rows, ignore_index=True)
    cols = [c for c in M if c[0] not in ("hit_rate",)]
    return tab(d, [("arm", lambda r: r["arm_label"]), ("method", lambda r: r["method"]), ("period", lambda r: r["period"])], cols)


def search_by_h(arm):
    s = load("search", arm)
    k = s[(s["window"] == "car_0_5") & (s["outcome"] == "plain")]
    g = k.pivot_table(index=["variant", "H"], columns="period", values=["mae_skill", "r2_gain", "spearman_pooled", "reg_t"],
                      aggfunc="max")
    g.columns = [f"{a}_{b}" for a, b in g.columns]
    g = g.reset_index()
    cols = [("spearman_pooled_fit", "Spearman fit", "{:.3f}"), ("spearman_pooled_choose", "Spearman choose", "{:.3f}"),
            ("reg_t_fit", "slope t fit", "{:.2f}"), ("reg_t_choose", "slope t choose", "{:.2f}"),
            ("r2_gain_choose", "R2 gain choose", "{:.3f}"), ("mae_skill_choose", "MAE skill choose", "{:.4f}")]
    return tab(g, [("variant", lambda r: r["variant"]), ("H", lambda r: int(r["H"]))], cols)


def weight_table(arm, window, outcome):
    w = load("weight_tests", arm)
    if w.empty:
        return "(not run)"
    w = w[(w["window"] == window) & (w["outcome"] == outcome)]
    piv = w.pivot_table(index=["weights", "H", "shocks"], columns="period",
                        values=["n_pairs", "spearman_pooled", "reg_t", "r2_gain", "mae_skill"], aggfunc="first")
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    piv = piv.reset_index()
    order = {"binary": 0, "share": 1, "share_cap_b0.0": 2, "share_cap_b0.5": 3, "share_cap_b1.0": 4}
    so = {"all": 0, "negative": 1, "positive": 2}
    piv = piv.sort_values(["weights", "H", "shocks"], key=lambda s: s.map(order) if s.name == "weights" else
                          (s.map(so) if s.name == "shocks" else s))
    cols = [("n_pairs_fit", "pairs fit", "{:,.0f}"), ("spearman_pooled_fit", "Spearman fit", "{:.3f}"),
            ("reg_t_fit", "t fit", "{:.2f}"), ("n_pairs_choose", "pairs choose", "{:,.0f}"),
            ("spearman_pooled_choose", "Spearman choose", "{:.3f}"), ("reg_t_choose", "t choose", "{:.2f}"),
            ("r2_gain_choose", "R2 gain choose", "{:.3f}"), ("mae_skill_choose", "MAE skill choose", "{:.4f}")]
    return tab(piv, [("weights", lambda r: r["weights"]), ("H", lambda r: int(r["H"])), ("shocks", lambda r: r["shocks"])], cols)


def all_tables():
    parts = {}
    for w in ("car_0_5", "car_1_20"):
        parts[f"kept_{w}"] = kept_table(w)
        for o in ("plain", "adj"):
            parts[f"base_{w}_{o}"] = baselines_table(w, o)
            parts[f"h2h_{w}_{o}"] = h2h_table(w, o)
    for arm in ARMS:
        if not load("search", arm).empty:
            parts[f"search_{arm}"] = search_by_h(arm)
    for arm in ("wide", "wide_nf"):
        for w in ("car_0_5", "car_1_20"):
            for o in ("plain", "adj"):
                parts[f"wt_{arm}_{w}_{o}"] = weight_table(arm, w, o)
    return parts


if __name__ == "__main__":
    for k, v in all_tables().items():
        print("##", k)
        print(v[:3000])
