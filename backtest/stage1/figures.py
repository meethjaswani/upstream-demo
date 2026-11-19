"""Three static figures for slides (results/figures/*.png), light surface.
Colours: categorical slots 1-2 of the reference palette (validated: blue #2a78d6, orange #eb6834);
baselines in muted grey so the model stands out; thin marks, hairline grid, direct labels."""
import json
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates  # noqa: E402
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import FIGURES, RESULTS

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#b9b8b0"
plt.rcParams.update({"font.family": ["Helvetica", "Arial", "DejaVu Sans"], "font.size": 11,
                     "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE})


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def methods_on_model_pairs(arm="crsp"):
    h = pd.read_csv(RESULTS / f"head_to_head_{arm}.csv")
    h = h[(h["window"] == "car_0_5") & (h["period"] == "choose")]
    order = [m for m in h["method"].unique() if m.startswith("kept")] + ["B1_industry", "B2_neighbours", "B3_correlated"]
    label = {"B1_industry": "B1 same sub-industry", "B2_neighbours": "B2 direct neighbours",
             "B3_correlated": "B3 20 most correlated"}
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, (o, title) in zip(axes, [("plain", "Plain CAR [0,+5]"), ("adj", "Industry-adjusted CAR [0,+5]")]):
        d = h[h["outcome"] == o].set_index("method").reindex(order)
        vals = d["spearman_pooled"].values
        names = [label.get(m, "Network model (kept)") for m in order]
        y = np.arange(len(order))[::-1]
        colors = [BLUE if m.startswith("kept") else GREY for m in order]
        ax.barh(y, vals, color=colors, height=0.55)
        for yi, v in zip(y, vals):
            if np.isfinite(v):
                ax.text(v + (0.004 if v >= 0 else -0.004), yi, f"{v:.2f}", va="center",
                        ha="left" if v >= 0 else "right", color=INK, fontsize=10)
        ax.axvline(0, color=AXIS, linewidth=1)
        ax.set_yticks(y, names)
        ax.set_title(title, color=INK, fontsize=11, loc="left")
        ax.set_xlabel("Pooled Spearman, prediction vs CAR")
        _style(ax)
        lo, hi = np.nanmin(np.r_[vals, 0]), np.nanmax(np.r_[vals, 0])
        ax.set_xlim(lo - 0.05, hi + 0.06)
    n = int(h["n_pairs"].max())
    fig.suptitle(f"Choosing period 2022-23, the model's {n} event-firm pairs (CRSP)", x=0.01, ha="left", color=INK,
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGURES / "methods_on_model_pairs.png", dpi=200)
    plt.close(fig)


def apple_replay(arm="crsp"):
    d = pd.read_csv(RESULTS / f"e4_apple_{arm}.csv")
    s = json.loads((RESULTS / f"e4_apple_{arm}.json").read_text())
    d = d[d["linked"]].sort_values("pred_model")
    if d.empty:
        return
    lam = None
    k = pd.read_csv(RESULTS / "kept_config.csv")
    k = k[(k["arm"] == arm) & (k["contamination"] == "any") & (k["window"] == "car_0_5") & (k["outcome"] == "plain")
          & (k["period"] == "fit")]
    if len(k):
        lam = float(k["lambda"].iloc[0])
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(d) + 2.0))
    y = np.arange(len(d))
    ax.barh(y, d["car_0_5"] * 100, color=BLUE, height=0.55, label="Realised CAR [0,+5]")
    ax.scatter(d["pred_model"] * 100, y, color=ORANGE, s=48, zorder=3, edgecolor=SURFACE, linewidth=1.5,
               label="Model prediction (before scaling)")
    for yi, v in zip(y, d["car_0_5"] * 100):
        ax.text(v + (0.3 if v >= 0 else -0.3), yi, f"{v:.1f}%", va="center", ha="left" if v >= 0 else "right",
                color=INK, fontsize=9)
    lo = min(0.0, float(d["car_0_5"].min() * 100), float(d["pred_model"].min() * 100))
    hi = max(0.0, float(d["car_0_5"].max() * 100))
    ax.set_xlim(lo - 2.2, hi + 1.6)
    names = [re.sub(r"[,.]?\s+(Inc|Corp|Co|Ltd|Plc)\.?$", "", f.title() if f.isupper() else f)[:28]
             for f in d["firm"]]
    ax.set_yticks(y, names)
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.set_xlabel("% move")
    _style(ax)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2, fontsize=9, labelcolor=INK2)
    ttl = f"Apple guidance cut, event day 3 Jan 2019: Apple AR {s['apple_ar'] * 100:.1f}%, linked suppliers"
    ax.set_title(ttl, color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(FIGURES / "e4_apple_replay.png", dpi=200)
    plt.close(fig)


def e3_cumulative(arm="crsp"):
    L = pd.read_csv(RESULTS / f"e3_longshort_{arm}.csv")
    L["date"] = pd.PeriodIndex(L["month"], freq="M").to_timestamp(how="end")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for col, c, lab in (("ls_ew", BLUE, "Equal weighted"), ("ls_vw", ORANGE, "Value weighted")):
        cum = (1 + L[col].fillna(0)).cumprod() - 1
        ax.plot(L["date"], cum * 100, color=c, linewidth=2, label=lab)
        ax.text(L["date"].iloc[-1], cum.iloc[-1] * 100, f"  {lab} {cum.iloc[-1] * 100:.0f}%", color=INK2,
                fontsize=9, va="center")
    ax.axvline(pd.Timestamp("2022-01-01"), color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
    ax.text(pd.Timestamp("2022-01-15"), ax.get_ylim()[1] * 0.9, "choosing period", color=MUTED, fontsize=9)
    ax.axhline(0, color=AXIS, linewidth=1)
    ax.set_xlim(pd.Timestamp("2015-01-01"), pd.Timestamp("2023-12-31"))
    ax.set_xticks(pd.date_range("2015-01-01", "2023-01-01", freq="YS"))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    ax.set_ylabel("Cumulative top-minus-bottom return, %")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=INK2)
    ax.set_title("E3 customer momentum, quintile long-short (CRSP)", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(FIGURES / "e3_cumulative_longshort.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    methods_on_model_pairs()
    apple_replay()
    e3_cumulative()
