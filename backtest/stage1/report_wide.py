"""Checkpoint before the widened search: universe-only vs widened arm.
Writes results/checkpoint_wide.json and results/checkpoint_wide.md (aggregates only)."""
import json

import numpy as np
import pandas as pd
import scipy.sparse as sp

from . import compseg, trial_log
from .config import CACHE, RESULTS
from .evaluate import clean, pairs
from .panel import WINDOWS, Panel
from .search import model_preds, seeded_events

SKYWORKS, APPLE = 4127, 320193
YEAR_ENDS = [pd.Timestamp(f"{y}-12-31") for y in range(2015, 2024)]


def links_per_year():
    U = pd.read_parquet(CACHE / "seed_links_universe.parquet")
    W, _ = compseg.load()
    u = U.assign(year=pd.to_datetime(U["accepted_at"]).dt.year).groupby("year").size().rename("universe_only")
    w = W.assign(year=pd.to_datetime(W["accepted_at"]).dt.year)
    by = w.pivot_table(index="year", columns="source", values="seller", aggfunc="size", fill_value=0)
    out = pd.concat([u, w.groupby("year").size().rename("widened"), by], axis=1).fillna(0).astype(int)
    return out[(out.index >= 2015) & (out.index <= 2023)]


def compseg_additions():
    W, _ = compseg.load()
    tti = pd.read_parquet(CACHE / "tenk_index_universe.parquet")
    read = set(tti.loc[tti["fetched"], "accession"])
    named = W[W["buyer"].notna()]
    on_read = named[named["accession"].isin(read)]
    sk = W[(W["seller"] == f"cik:{SKYWORKS}") & (W["buyer"] == f"cik:{APPLE}")].copy()
    sk["fy"] = pd.to_datetime(sk["report_date"]).dt.year
    sk = sk.sort_values("accepted_at")
    return {
        "on_10ks_the_text_parser_read": {k: int(v) for k, v in on_read["source"].value_counts().items()},
        "all_named_links": {k: int(v) for k, v in named["source"].value_counts().items()},
        "compseg_links_naming_a_cik_customer_missed_by_text": int(
            ((on_read["source"] == "compseg") & on_read["buyer"].str.startswith("cik:")).sum()),
        "skyworks_to_apple": [{"fiscal_year_end": str(pd.Timestamp(r.report_date).date()), "source": r.source,
                               "usable_from": str(r.accepted_at), "revenue_share": None if pd.isna(r.revenue_share)
                               else round(float(r.revenue_share), 3)} for r in sk.itertuples()],
    }


def paths_in_graph(P):
    """Year-end snapshots: 2- and 3-hop demand paths between priced companies (buyer -> ... -> seller)."""
    rows = []
    for d in YEAR_ENDS:
        snap = P.snapshot(d)                       # 10-Ks accepted before 31 December (never 2024)
        if snap["W"] is None:
            continue
        A = (snap["W"] > 0).astype(np.int64).tocsr()
        priced = P.node_cols(snap) >= 0
        D = sp.diags(priced.astype(np.int64))
        A1 = D @ A @ D
        A2 = A @ A
        A3 = A2 @ A
        P2 = (D @ A2 @ D).tocoo()
        P3 = (D @ A3 @ D).tocoo()
        rows.append({"year_end": str(d.date()), "direct_links_priced": int(A1.nnz),
                     "two_hop_paths": int(P2.data[P2.row != P2.col].sum()),
                     "two_hop_pairs": int((P2.row != P2.col).sum()),
                     "three_hop_paths": int(P3.data[P3.row != P3.col].sum())})
    return rows


def arm_counts(arm):
    P = Panel(arm)
    ks = seeded_events(P)
    res = {"events": int(len(P.ev)), "events_by_period": {k: int(v) for k, v in P.ev["period"].value_counts().items()},
           "events_with_seed_in_graph": len(ks), "companies": len(P.U.symbols), "market_filter": P.U.market_source}
    prev = None
    for H in (1, 2, 3):
        preds = model_preds(P, ks, "M1", 0.7, H, 1000)
        df = pairs(P, preds)
        r = {"pairs_raw": int(len(df)), "events_with_linked": int(df["k"].nunique()) if len(df) else 0}
        per_ev = df.groupby("k").size() if len(df) else pd.Series(dtype=int)
        r["events_with_5plus_raw"] = int((per_ev >= 5).sum())
        r["median_linked_per_event"] = float(per_ev.median()) if len(per_ev) else 0.0
        if prev is not None:
            new = df.merge(prev[["k", "col"]], on=["k", "col"], how="left", indicator=True)
            r["pairs_added_by_this_hop"] = int((new["_merge"] == "left_only").sum())
        for w in WINDOWS:
            d, cnt = clean(df, w)
            r[w] = {**cnt, "used_fit": int((d["period"] == "fit").sum()), "used_choose": int((d["period"] == "choose").sum()),
                    "events_with_5plus_after_cleaning": int((d.groupby("k").size() >= 5).sum())}
        res[f"H{H}"] = r
        prev = df
    res["graph_paths"] = paths_in_graph(P)
    return res


def main():
    out = {"links_per_year": links_per_year().reset_index().rename(columns={"index": "year"}).to_dict(orient="records"),
           "compseg_vs_10k_text": compseg_additions(),
           "build": json.loads((RESULTS / "wide_graph_build.json").read_text())}
    for arm in ("crsp", "wide"):
        out[arm] = arm_counts(arm)
    (RESULTS / "checkpoint_wide.json").write_text(json.dumps(out, indent=1, default=str))
    trial_log.log("checkpoint_wide", {"overlap_exposure": "M1 delta 0.7", "contamination": "any"}, "fit+choose",
                  {a: {k: out[a][k] for k in ("events", "events_with_seed_in_graph", "H1", "H2", "H3")}
                   for a in ("crsp", "wide")}, "data checkpoint before the widened search")
    print(json.dumps(out, indent=1, default=str)[:12000])
    return out


if __name__ == "__main__":
    main()
