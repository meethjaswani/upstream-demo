"""Cross-check of the seed graph against Compustat customer segments (comp.seg_customer).

Compustat rows: ctype COMPANY (named firms), one per seller gvkey, fiscal period end (datadate),
customer name (free text) and sales to that customer (salecs, USD m). The export covers fiscal
periods ending 2020-06 .. 2023-12 only.

Matched on seller CIK and fiscal year end (our 10-K report_date within 10 days of datadate),
over the seller-years both sources cover. Customer names are resolved with the same name index
the seed graph uses. Aggregates go to results/seg_customer_crosscheck.json; row-level output
(licensed data) stays in cache/.
"""
import json
import re

import numpy as np
import pandas as pd

from . import crsp, seed_graph
from .config import CACHE, RESULTS
from .names import norm
from .predecessors import canonical
from .seed_graph import ANON_MEMBER

TOL_DAYS = 10


def resolve(idx, name):
    if not isinstance(name, str) or not name.strip():
        return None
    n = norm(name)
    if not n or ANON_MEMBER.search(name.lower()) or re.match(r"^(customer|client)\b", name.strip(), re.I):
        return "anon"
    for h in idx.find(name.title() if name.isupper() else name):
        a = h[3]
        if n == a or n.startswith(a + " "):
            return h[2]
    return "raw:" + n


def main():
    idx, t2c = seed_graph.build_index()
    seg = crsp._read("comp_seg_customer", ["datadate"])
    seg = seg[seg["ctype"] == "COMPANY"].copy()
    seg["salecs"] = seg["salecs"].astype(float)
    seg = (seg.sort_values("salecs", ascending=False)
           .drop_duplicates(["gvkey", "datadate", "cnms"]))
    co = crsp.company()
    g2c = {g: canonical(int(c)) for g, c in zip(co["gvkey"], co["cik"]) if pd.notna(c)}
    pm = crsp.permno_map()
    for g, c in zip(pm["gvkey"], pm["cik"]):
        if isinstance(g, str) and pd.notna(c):
            g2c.setdefault(g, int(c))
    seg["seller_cik"] = seg["gvkey"].map(g2c)
    names = seg["cnms"].drop_duplicates()
    rmap = {n: resolve(idx, n) for n in names}
    seg["buyer"] = seg["cnms"].map(rmap)
    # same dated parent mapping as the seed graph (e.g. Express Scripts -> Cigna from Dec 2018)
    tmp = seg.assign(seller="x", revenue_share=seg["salecs"], accession=np.arange(len(seg)),
                     accepted_at=seg["datadate"])
    named = tmp["buyer"].notna() & ~tmp["buyer"].isin(["anon"])
    remapped = seed_graph.remap_parents(tmp[named][["seller", "buyer", "revenue_share", "accession", "accepted_at"]],
                                        t2c).set_index("accession")["buyer"]
    seg.loc[named.values, "buyer"] = pd.Series(np.arange(len(seg)))[named.values].map(remapped).values

    links, ti = seed_graph.load()
    filings = pd.read_parquet(CACHE / "sec" / "filings.parquet", columns=["accession", "report_date"])
    ti = ti.merge(filings, on="accession", how="left")
    ti["report_date"] = pd.to_datetime(ti["report_date"], errors="coerce")
    ti = ti[ti["fetched"]]
    links = links.copy()
    links["report_date"] = pd.to_datetime(links["report_date"], errors="coerce")

    uni = seg[seg["seller_cik"].notna()].copy()
    uni["seller_cik"] = uni["seller_cik"].astype(int)
    # attach our 10-K for the same fiscal year
    rows = []
    for (c, dd), g in uni.groupby(["seller_cik", "datadate"]):
        cand = ti[(ti["cik"] == c) & ((ti["report_date"] - dd).abs() <= pd.Timedelta(days=TOL_DAYS))]
        if cand.empty:
            continue
        acc = cand.sort_values("accepted").iloc[-1]["accession"]
        ours = links[links["accession"] == acc]
        ours_named = set(ours["buyer"].dropna())
        comp_named = set(g.loc[~g["buyer"].isin(["anon", None]), "buyer"])
        rows.append({"seller_cik": c, "datadate": dd, "accession": acc,
                     "comp_named": sorted(comp_named), "ours_named": sorted(ours_named),
                     "comp_resolved_cik": sorted(b for b in comp_named if b.startswith("cik:")),
                     "ours_cik": sorted(b for b in ours_named if b.startswith("cik:")),
                     "comp_anon": int((g["buyer"] == "anon").sum()),
                     "ours_anon": int(ours["buyer"].isna().sum())})
    R = pd.DataFrame(rows)
    R.to_parquet(CACHE / "seg_customer_crosscheck_rows.parquet", index=False)

    def cnt(col):
        return int(R[col].map(len).sum())
    both_cik = int(sum(len(set(a) & set(b)) for a, b in zip(R["comp_resolved_cik"], R["ours_cik"])))
    both_any = int(sum(len(set(a) & set(b)) for a, b in zip(R["comp_named"], R["ours_named"])))
    universe_ciks = {f"cik:{int(c)}" for c in pm["cik"].dropna()}
    comp_u = int(sum(len([b for b in a if b in universe_ciks]) for a in R["comp_resolved_cik"]))
    ours_u = int(sum(len([b for b in a if b in universe_ciks]) for a in R["ours_cik"]))
    both_u = int(sum(len({b for b in set(a) & set(bb) if b in universe_ciks})
                     for a, bb in zip(R["comp_resolved_cik"], R["ours_cik"])))

    # widening potential: sellers outside the universe export naming a universe customer
    outside = seg[seg["seller_cik"].isna() & seg["buyer"].isin(universe_ciks)]
    out = {
        "seg_customer_fiscal_period_range": [str(seg["datadate"].min().date()), str(seg["datadate"].max().date())],
        "company_rows_all_sellers": int(len(seg)),
        "distinct_customer_names": int(len(names)),
        "names_resolved_to_a_node": int(sum(1 for v in rmap.values() if v and v not in ("anon",) and not v.startswith("raw:"))),
        "universe_seller_years_in_both_sources": int(len(R)),
        "named_customers_compustat": cnt("comp_named"), "named_customers_ours": cnt("ours_named"),
        "named_in_both": both_any,
        "universe_customers_compustat": comp_u, "universe_customers_ours": ours_u, "universe_customers_in_both": both_u,
        "recall_of_compustat_universe_customers": round(both_u / comp_u, 3) if comp_u else None,
        "share_of_our_universe_customers_confirmed_by_compustat": round(both_u / ours_u, 3) if ours_u else None,
        "cik_customers_in_both": both_cik,
        "anonymous_rows_compustat": int(R["comp_anon"].sum()), "anonymous_links_ours": int(R["ours_anon"].sum()),
        "outside_sellers_naming_a_universe_customer": int(outside["gvkey"].nunique()),
        "outside_links_to_universe_customers": int(len(outside)),
        "outside_links_by_fiscal_year": {int(k): int(v) for k, v in outside.groupby(outside["datadate"].dt.year).size().items()},
    }
    (RESULTS / "seg_customer_crosscheck.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    # largest disagreements on universe customers, for review (kept in cache)
    miss = []
    for r in R.itertuples():
        for b in set(r.comp_resolved_cik) - set(r.ours_cik):
            if b in universe_ciks:
                miss.append({"seller_cik": r.seller_cik, "datadate": r.datadate, "customer": b, "side": "compustat_only"})
        for b in set(r.ours_cik) - set(r.comp_resolved_cik):
            if b in universe_ciks:
                miss.append({"seller_cik": r.seller_cik, "datadate": r.datadate, "customer": b, "side": "ours_only"})
    pd.DataFrame(miss).to_parquet(CACHE / "seg_customer_disagreements.parquet", index=False)
    return out


if __name__ == "__main__":
    main()
