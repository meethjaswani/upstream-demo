"""Steps 2 and 4 outputs for the checkpoint: seed graph size, event panel and power counts.

Writes cache/events.parquet, cache/ff3_fit.npz and results/checkpoint_step4.json.
"""
import json

import numpy as np
import pandas as pd

from . import engine, events, fetch_sec_index, pit, seed_graph
from .config import CACHE, RESULTS
from .universe import Universe


def linked_firms(G, seed_cik, member_ciks, H):
    """Universe firms reachable from the seed's suppliers within H hops (demand direction:
    buyer -> seller), excluding the seed."""
    if G.empty:
        return set()
    out_edges = {}
    for b, s in zip(G["buyer"], G["seller"]):
        if isinstance(b, str):
            out_edges.setdefault(b, set()).add(s)
    seen, frontier = set(), {f"cik:{seed_cik}"}
    for _ in range(H):
        nxt = set()
        for n in frontier:
            nxt |= out_edges.get(n, set())
        nxt -= seen
        seen |= nxt
        frontier = nxt
    return {int(n[4:]) for n in seen if n.startswith("cik:") and int(n[4:]) in member_ciks} - {seed_cik}


def main():
    U = Universe()
    y, X = U.excess_returns()
    B, sig, nobs = events.rolling_ff3(y, X)
    np.savez_compressed(CACHE / "ff3_fit.npz", B=B, sig=sig, nobs=nobs)
    filings = fetch_sec_index.load_filings()
    any_f, earn = events.filing_flags(filings, U.calendar, U.sym_of_cik, U.symbols)
    ev, funnel = events.detect(y, X, B, sig, U.member, U.spx_ret, any_f, earn, U.calendar, U.symbols)
    ev["cik"] = ev["symbol"].map(U.cik_of_sym)
    pit.check_frame(ev, ["date"], what="events")

    links, ti = seed_graph.load()
    G = seed_graph.SeedGraph(links, ti)
    n1, n4 = [], []
    cache = {}
    for r in ev.itertuples():
        g = cache.get(r.date)
        if g is None:
            g = cache[r.date] = G.at(r.date)
        mem = {U.cik_of_sym[U.symbols[k]] for k in np.flatnonzero(U.member[r.t])}
        n1.append(len(linked_firms(g, r.cik, mem, 1)))
        n4.append(len(linked_firms(g, r.cik, mem, 4)))
    ev["linked_h1"], ev["linked_h4"] = n1, n4
    ev.to_parquet(CACHE / "events.parquet", index=False)

    py = seed_graph.per_year(links)
    py.to_csv(RESULTS / "seed_links_per_year.csv")
    priced = {f"cik:{c}" for c in U.sym_of_cik}
    usable = links[links["buyer"].isin(priced) & links["seller"].isin(priced)]
    rep = {
        "seed_links_total": int(len(links)),
        "seed_links_named": int(links["buyer"].notna().sum()),
        "seed_links_both_ends_priced": int(len(usable)),
        "seed_links_per_year": py.reset_index().to_dict(orient="records"),
        "sellers_with_any_link": int(links["seller"].nunique()),
        "tenk_filings": int(len(ti)), "tenk_fetched": int(ti["fetched"].sum()),
        "events_total": int(len(ev)),
        "events_by_period": ev["period"].value_counts().to_dict(),
        "events_negative": int((ev["sign"] < 0).sum()), "events_positive": int((ev["sign"] > 0).sum()),
        "events_earnings": int(ev["earnings"].sum()),
        "event_funnel": funnel,
        "events_with_linked_h1": int((ev["linked_h1"] > 0).sum()),
        "events_with_linked_h4": int((ev["linked_h4"] > 0).sum()),
        "event_firm_pairs_h1": int(ev["linked_h1"].sum()),
        "event_firm_pairs_h4": int(ev["linked_h4"].sum()),
        "event_firm_pairs_h1_by_period": ev.groupby("period")["linked_h1"].sum().to_dict(),
        "median_linked_h1_given_any": float(ev.loc[ev["linked_h1"] > 0, "linked_h1"].median()) if (ev["linked_h1"] > 0).any() else 0,
        "survivorship": U.survivorship(),
        "universe_symbols": len(U.symbols),
    }
    (RESULTS / "checkpoint_step4.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({k: v for k, v in rep.items() if k not in ("seed_links_per_year",)}, indent=1, default=str)[:4000])
    print(py)


if __name__ == "__main__":
    main()
