"""Step 4 checkpoint for one data arm ('yahoo' or 'crsp'): event panel, seed graph coverage and
power counts. Writes cache/events_<arm>.parquet, cache/pairs_<arm>.parquet and
results/checkpoint_step4_<arm>.json.

Event filter by arm:
  yahoo: an 8-K, 10-Q or 10-K (SEC) within one trading day; earnings = 8-K item 2.02 or 10-Q/10-K
  crsp:  an 8-K, 10-Q or 10-K (SEC) or a Compustat rdq within one trading day; earnings = rdq
Contamination preview (amendment 3): a linked firm with its own 8-K or earnings day inside the CAR
window would be dropped; counts are given for both windows.
"""
import json
import sys

import numpy as np
import pandas as pd

from . import events, fetch_sec_index, pit, seed_graph, trial_log
from .config import CACHE, RESULTS


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


def shift_rows(A, d):
    """Rows moved down by d (up if d < 0), no wrap-around."""
    out = np.zeros_like(A)
    if d > 0:
        out[d:] = A[:-d]
    elif d < 0:
        out[:d] = A[-d:]
    else:
        out[:] = A
    return out


def own_day_flags(U, filings, earn_days=None):
    """T x S: the firm's own 8-K/10-Q/10-K first moves the price that day (any), and its earnings
    day (rdq and the day after for the CRSP arm; 8-K 2.02 or 10-Q/10-K for the Yahoo arm)."""
    T, S = len(U.calendar), len(U.symbols)
    f = filings[filings["cik"].isin(U.sym_of_cik)].copy()
    f["e"] = events.effective_day_index(f["accepted"], U.calendar)
    f["s"] = f["cik"].map(lambda c: U.col[U.sym_of_cik[c]])
    f = f[f["e"] < T]
    A = np.zeros((T, S), bool)
    A[f["e"], f["s"]] = True
    if earn_days is None:
        ise = (f["form"].isin(["10-Q", "10-K", "10-KT"]) | f["items"].fillna("").str.contains(r"\b2\.02\b")).values
        E = np.zeros((T, S), bool)
        E[f["e"].values[ise], f["s"].values[ise]] = True
    else:
        E = earn_days | shift_rows(earn_days, 1)    # rdq or the next day (after-close releases)
    return A | E, E


def main(arm):
    if arm in ("crsp", "wide"):
        from .universe_crsp import CrspUniverse
        U = CrspUniverse(widen=(arm == "wide"))
    elif arm == "yahoo":
        from .universe import Universe
        U = Universe()
    else:
        raise ValueError(arm)
    y, X = U.excess_returns()
    B, sig, nobs = events.rolling_ff3(y, X)
    np.savez_compressed(CACHE / f"ff3_fit_{arm}.npz", B=B, sig=sig, nobs=nobs)
    filings = fetch_sec_index.load_filings()
    any_f, earn = events.filing_flags(filings, U.calendar, U.sym_of_cik, U.symbols)
    rdq_days = None
    if arm in ("crsp", "wide"):
        rdq_days = U.earnings_days()
        win = np.zeros_like(rdq_days)
        for d in range(-events.FILING_WINDOW, events.FILING_WINDOW + 1):
            win |= shift_rows(rdq_days, d)
        any_f = any_f | win
        earn = win
    ev, funnel = events.detect(y, X, B, sig, U.member, U.spx_ret, any_f, earn, U.calendar, U.symbols)
    ev["cik"] = ev["symbol"].map(U.cik_of_sym)
    pit.check_frame(ev, ["date"], what="events")

    if arm == "wide":
        from . import compseg
        links, ti = compseg.load()
        eligible = ~np.isnan(y.values)              # any CRSP common stock with a return that day
    else:
        links = pd.read_parquet(CACHE / "seed_links_universe.parquet")
        ti = pd.read_parquet(CACHE / "tenk_index_universe.parquet")
        eligible = U.member
    G = seed_graph.SeedGraph(links, ti)
    own_any, own_earn = own_day_flags(U, filings, rdq_days)
    T = len(U.calendar)
    n1, n4, pairs, cache = [], [], [], {}
    for r in ev.itertuples():
        g = cache.get(r.date)
        if g is None:
            g = cache[r.date] = G.at(r.date)
        mem = {U.cik_of_sym[U.symbols[k]] for k in np.flatnonzero(eligible[r.t])}
        l1 = linked_firms(g, r.cik, mem, 1)
        n1.append(len(l1))
        n4.append(len(linked_firms(g, r.cik, mem, 4)))
        for c in l1:
            s = U.col[U.sym_of_cik[c]]
            row = {"event": r.Index, "date": r.date, "period": r.period, "seed_cik": r.cik, "firm_cik": c}
            for name, (k0, k1) in events.CAR_WINDOWS.items():
                a, b = r.t + k0, min(r.t + k1, T - 1)
                row[f"own_any_{name}"] = bool(own_any[a:b + 1, s].any())
                row[f"own_earn_{name}"] = bool(own_earn[a:b + 1, s].any())
            pairs.append(row)
    ev["linked_h1"], ev["linked_h4"] = n1, n4
    ev.to_parquet(CACHE / f"events_{arm}.parquet", index=False)
    P = pd.DataFrame(pairs)
    P.to_parquet(CACHE / f"pairs_{arm}.parquet", index=False)

    priced = {f"cik:{c}" for c in U.sym_of_cik}
    usable = links[links["buyer"].isin(priced) & links["seller"].isin(priced)]
    by = lambda s: {k: int(v) for k, v in s.items()}
    rep = {
        "arm": arm,
        "seed_links_total": int(len(links)),
        "seed_links_named": int(links["buyer"].notna().sum()),
        "seed_links_both_ends_in_universe": int(len(usable)),
        "seed_pairs_both_ends_in_universe": int(usable[["seller", "buyer"]].drop_duplicates().shape[0]),
        "universe_companies": len(U.symbols),
        "events_total": int(len(ev)),
        "events_by_period": by(ev["period"].value_counts()),
        "events_negative": int((ev["sign"] < 0).sum()), "events_positive": int((ev["sign"] > 0).sum()),
        "events_earnings": int(ev["earnings"].sum()),
        "event_funnel": funnel,
        "events_with_linked_h1": int((ev["linked_h1"] > 0).sum()),
        "event_firm_pairs_h1": int(ev["linked_h1"].sum()),
        "event_firm_pairs_h1_by_period": by(ev.groupby("period")["linked_h1"].sum()),
        "event_firm_pairs_h4": int(ev["linked_h4"].sum()),
        "median_linked_h1_given_any": float(ev.loc[ev["linked_h1"] > 0, "linked_h1"].median()) if len(P) else 0.0,
        "events_with_5plus_linked_h1": int((ev["linked_h1"] >= 5).sum()),
        "survivorship": U.survivorship(),
    }
    for name in events.CAR_WINDOWS:
        for kind in ("any", "earn"):
            col = f"own_{kind}_{name}"
            rep[f"clean_pairs_drop_{kind}_{name}"] = by(P.loc[~P[col]].groupby("period").size()) if len(P) else {}
    (RESULTS / f"checkpoint_step4_{arm}.json").write_text(json.dumps(rep, indent=1, default=str))
    trial_log.log(f"checkpoint_step4_{arm}", {"z_min": events.Z_MIN, "filing_window_days": events.FILING_WINDOW,
                                              "spx_max": events.SPX_MAX, "est_window": [-events.EST_START, -events.EST_END]},
                  "fit+choose", {k: v for k, v in rep.items() if k not in ("survivorship",)},
                  f"data checkpoint, {arm} arm, before any model scoring")
    print(json.dumps(rep, indent=1, default=str)[:5000])
    return rep


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "crsp")
