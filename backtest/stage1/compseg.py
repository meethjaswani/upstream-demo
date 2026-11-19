"""Widened seed graph (amendment 12): Compustat customer segments merged with the 10-K graph.

Compseg links: compseg.seg_customer 2012-2023, ctype COMPANY, salecs summed over segments per
seller, customer and fiscal year end; revenue share = salecs / sale (comp.funda, same fiscal year
end); tier DISCLOSED. Customer names resolved with the existing name index first, then Compustat
company names (an alias is used only if it points to a single company). Anonymous names
('3 Customers', 'Customer A') become anonymous edges.

Point in time: a row is usable from the acceptance of the seller's 10-K for that fiscal year
(EDGAR, report date within 10 days of datadate; else the first 10-K filed within 200 days after
datadate); without one, from datadate + 90 days.

Merge: a compseg year that matches a 10-K already read joins that filing's link set, one link per
buyer (source tenk / compseg / both; the 10-K share wins when both have one). Other compseg
years become their own dated link sets. All 10-Ks of compseg sellers are listed so that a newer
filing replaces an older link set, as for the 10-K graph.
"""
import json
import re

import numpy as np
import pandas as pd

from . import crsp, pit, seed_graph, wrds2
from .config import CACHE, GRAPH_JSON, RESULTS
from .names import NameIndex, norm
from .predecessors import canonical
from .seed_graph import ANON_MEMBER

OUT_LINKS = CACHE / "seed_links_wide.parquet"
OUT_TI = CACHE / "tenk_index_wide.parquet"
FORMS_10K = ["10-K", "10-K405", "10-KT"]
NOT_NAMED = re.compile(r"^(not\s+(reported|disclosed|identified|available)|undisclosed|unnamed|unidentified|n/?a|"
                       r"none|confidential)\b", re.I)
# short brand or division names that point to a listed parent (ticker resolved through CRSP)
EXTRA_ALIASES = {"gap": "GPS", "old navy": "GPS", "banana republic": "GPS", "marshalls": "TJX", "tj maxx": "TJX",
                 "tjmaxx": "TJX", "homegoods": "TJX", "janssen": "JNJ", "janssen biotech": "JNJ",
                 "jp morgan chase": "JPM", "jp morgan": "JPM", "jpmorgan": "JPM", "hewlettpackard": "HPQ",
                 "sams club": "WMT", "kohls": "KSS", "macys": "M", "dicks sporting goods": "DKS",
                 "lowes home improvement": "LOW", "dollar general": "DG", "family dollar": "DLTR"}
AGG_NAME = re.compile(r"^\d+\s+(customers?|clients?|distributors?)\b|\b(customers|distributors|wholesalers|"
                      r"retailers|others|other|various|multiple)\b", re.I)


def name_index():
    """The 10-K graph's index (universe snapshot) plus Compustat company names with a unique alias."""
    meta = json.loads((CACHE / "sec" / "entity_meta_universe.json").read_text())
    t2c = crsp.ticker_cik()
    ent = pd.read_csv(CACHE / "entities.csv")
    for r in ent.dropna(subset=["cik"]).itertuples():
        for t in (r.member_ticker, r.yahoo):
            if isinstance(t, str):
                t2c.setdefault(t.upper(), canonical(int(r.cik)))
    g = json.load(open(GRAPH_JSON))
    idx = NameIndex().build(meta, t2c, g["nodes"])
    for a, tk in EXTRA_ALIASES.items():
        if tk in t2c:
            idx.alias.setdefault(a, f"cik:{t2c[tk]}")
    co = wrds2.company_all()
    seen = {}

    def add(nm, node):
        if isinstance(nm, str):
            for v in {nm, nm.replace("-", " ")}:
                a = norm(v)
                if a:
                    seen.setdefault(a, set()).add(node)

    for r in co.itertuples():
        node = f"cik:{int(r.cik_c)}" if pd.notna(r.cik_c) else f"gv:{r.gvkey}"
        add(r.conm, node)
        add(r.conml, node)
    # historical CRSP company names (both exports), via permno -> CIK
    pm = pd.concat([crsp.permno_map()[["permno", "cik"]], _seller_ciks()], ignore_index=True).dropna()
    p2c = dict(zip(pm["permno"].astype(int), pm["cik"].astype(int)))
    for n in (crsp.names(), wrds2.names()):
        for p, nm in zip(n["permno"], n["comnam"]):
            if int(p) in p2c:
                add(nm, f"cik:{p2c[int(p)]}")
    added = 0
    for a, nodes in seen.items():
        if len(nodes) == 1 and a not in idx.alias and not (len(a.split()) == 1 and len(a) < 4):
            idx.alias[a] = next(iter(nodes))
            added += 1
    idx.maxlen = max(len(a.split()) for a in idx.alias)
    return idx, t2c, added


def resolve(idx, name):
    if not isinstance(name, str) or not name.strip():
        return None, "empty"
    s = name.strip()
    if ANON_MEMBER.search(s.lower()) or re.match(r"^(customer|client)\b", s, re.I) \
            or re.match(r"^\d+\s+customers?$", s, re.I) or NOT_NAMED.match(s):
        return None, "anonymous"
    n = norm(s)
    if not n:
        return None, "anonymous"
    for v in (s, s.replace("-", " ")):
        nv = norm(v)
        hits = idx.find(v.title() if v.isupper() else v)
        for h in hits:
            if nv == h[3] or nv.startswith(h[3] + " "):
                return h[2], "named"
        if nv in idx.alias:
            return idx.alias[nv], "named"
    if AGG_NAME.search(s):
        return None, "aggregate"
    return "cs:" + re.sub(r"[^a-z0-9]+", "_", n).strip("_"), "unresolved"


def _seller_ciks():
    from .universe_crsp import CrspUniverse
    m = CrspUniverse._seller_map(set(wrds2.ccm()["permno"]))
    return m[["permno", "cik"]]


def availability(filings, cik, datadate):
    """(accession, accepted) of the seller's 10-K for fiscal year end `datadate`, or (None, datadate+90d)."""
    if cik is None:
        return None, datadate + pd.Timedelta(days=90)
    f = filings.get(cik)
    if f is not None and len(f):
        rd = f[(f["report_date"] - datadate).abs() <= pd.Timedelta(days=10)]
        if rd.empty:
            rd = f[(f["filing_date"] > datadate) & (f["filing_date"] <= datadate + pd.Timedelta(days=200))]
        if len(rd):
            r = rd.sort_values("accepted").iloc[0]
            return r["accession"], r["accepted"]
    return None, datadate + pd.Timedelta(days=90)


def build():
    idx, t2c, added = name_index()
    seg = wrds2.seg_customer()
    co = wrds2.company_all().set_index("gvkey")
    fa = wrds2.funda()
    # revenue share: same gvkey, fiscal year end within 10 days
    seg = seg.sort_values("datadate")
    fa2 = fa[["gvkey", "datadate", "sale"]].rename(columns={"datadate": "fdate"}).sort_values("fdate")
    seg = pd.merge_asof(seg, fa2, left_on="datadate", right_on="fdate", by="gvkey",
                        tolerance=pd.Timedelta(days=10), direction="nearest")
    share = seg["salecs"] / seg["sale"]
    seg["revenue_share"] = np.where((seg["sale"] > 0) & share.notna() & (share > 0) & (share <= 1.05),
                                    np.minimum(share, 1.0), np.nan)
    seg["seller_cik"] = seg["gvkey"].map(co["cik_c"])
    seg["seller"] = [f"cik:{int(c)}" if pd.notna(c) else f"gv:{g}" for c, g in zip(seg["seller_cik"], seg["gvkey"])]
    rmap = {n: resolve(idx, n) for n in seg["cnms"].drop_duplicates()}
    seg["buyer"] = seg["cnms"].map(lambda n: rmap[n][0])
    seg["kind"] = seg["cnms"].map(lambda n: rmap[n][1])
    seg = seg[seg["kind"] != "aggregate"]
    seg = seg[seg["buyer"] != seg["seller"]]

    # point in time
    fil = pd.read_parquet(CACHE / "sec" / "filings.parquet",
                          columns=["cik", "accession", "form", "filing_date", "report_date", "accepted"])
    fil = fil[fil["form"].isin(FORMS_10K)].copy()
    fil["report_date"] = pd.to_datetime(fil["report_date"], errors="coerce")
    by_cik = {c: g for c, g in fil.groupby("cik")}
    av = {}
    ck = seg["seller_cik"].fillna(-1).astype(int).values
    for c, dd in set(zip(ck, seg["datadate"])):
        av[(c, dd)] = availability(by_cik, int(c) if c >= 0 else None, dd)
    seg["accession"] = [av[(c, d)][0] for c, d in zip(ck, seg["datadate"])]
    seg["available_at"] = [av[(c, d)][1] for c, d in zip(ck, seg["datadate"])]
    seg["accession"] = [a if isinstance(a, str) else f"cs:{g}:{d.date()}"
                        for a, g, d in zip(seg["accession"], seg["gvkey"], seg["datadate"])]
    seg = seg[seg["available_at"] < pit.CUTOFF]
    seg["pit_source"] = np.where(seg["accession"].str.startswith("cs:"), "datadate+90", "edgar_10k")
    seg = remap(seg, t2c)

    # merge with the 10-K graph
    tl = pd.read_parquet(CACHE / "seed_links_universe.parquet")
    tti = pd.read_parquet(CACHE / "tenk_index_universe.parquet")
    tl = tl.assign(source="tenk")
    cs = pd.DataFrame({"seller": seg["seller"], "seller_cik": seg["seller_cik"], "buyer": seg["buyer"],
                       "buyer_label": seg["cnms"], "kind": seg["kind"], "revenue_share": seg["revenue_share"],
                       "tier": "DISCLOSED", "source": "compseg", "accession": seg["accession"],
                       "accepted_at": seg["available_at"], "report_date": seg["datadate"],
                       "quote": "Compustat customer segment: " + seg["cnms"] + ", salecs "
                                + seg["salecs"].round(2).astype(str) + "m, fiscal year end "
                                + seg["datadate"].dt.date.astype(str)})
    # a 10-K that was read keeps its own acceptance time; compseg rows on it use the same time
    acc_time = dict(zip(tti["accession"], tti["accepted"]))
    cs["accepted_at"] = [acc_time.get(a, t) for a, t in zip(cs["accession"], cs["accepted_at"])]
    named_t = tl[tl["buyer"].notna()]
    named_c = cs[cs["buyer"].notna()]
    key = ["accession", "seller", "buyer"]
    both = named_t.merge(named_c[key + ["revenue_share"]], on=key, how="inner", suffixes=("", "_cs"))
    both_keys = set(map(tuple, both[key].values))
    t_only = named_t[[tuple(x) not in both_keys for x in named_t[key].values]]
    c_only = named_c[[tuple(x) not in both_keys for x in named_c[key].values]]
    both = both.assign(source="both", revenue_share=both["revenue_share"].fillna(both["revenue_share_cs"])) \
               .drop(columns=["revenue_share_cs"])
    # anonymous edges: keep the 10-K's for filings it read, compseg's otherwise
    anon_t = tl[tl["buyer"].isna()]
    anon_c = cs[cs["buyer"].isna() & ~cs["accession"].isin(set(anon_t["accession"]))]
    W = pd.concat([t_only, c_only, both, anon_t, anon_c], ignore_index=True)
    W["seller_cik"] = W["seller_cik"].astype("Int64")
    W["report_date"] = pd.to_datetime(W["report_date"], errors="coerce")
    W["accepted_at"] = pd.to_datetime(W["accepted_at"])
    if "period_end" in W.columns:
        W["period_end"] = W["period_end"].astype("string")
    for c in ("buyer", "buyer_label", "kind", "quote", "tier", "source", "accession", "seller"):
        if c in W.columns:
            W[c] = W[c].astype("string")
    pit.check_frame(W, ["accepted_at"], what="wide links")

    # filing index: the 10-Ks that were read, every 10-K of compseg sellers, compseg-only records
    seller_ciks = set(seg["seller_cik"].dropna().astype(int))
    extra = fil[fil["cik"].isin(seller_ciks) & ~fil["accession"].isin(set(tti["accession"]))]
    extra = pit.clip(extra, "accepted")
    ti_extra = pd.DataFrame({"cik": extra["cik"].astype(int), "accession": extra["accession"],
                             "accepted": extra["accepted"], "fetched": True, "n_links": 0})
    pseudo = cs[cs["accession"].str.startswith("cs:")].groupby("accession").agg(
        accepted=("accepted_at", "first"), seller=("seller", "first"))
    ti_pseudo = pd.DataFrame({"cik": [int(s[4:]) if s.startswith("cik:") else -abs(hash(s)) % 10**9
                                      for s in pseudo["seller"]],
                              "accession": pseudo.index, "accepted": pseudo["accepted"].values,
                              "fetched": True, "n_links": 0})
    TI = pd.concat([tti, ti_extra, ti_pseudo], ignore_index=True).drop_duplicates("accession")
    cnt = W.groupby("accession").size()
    TI["n_links"] = TI["accession"].map(cnt).fillna(0).astype(int)
    pit.check_frame(TI, ["accepted"], what="wide 10-K index")
    W.to_parquet(OUT_LINKS, index=False)
    TI.to_parquet(OUT_TI, index=False)

    stats = {"compustat_aliases_added": added,
             "compseg_company_rows": int(len(seg)),
             "compseg_rows_by_kind": {k: int(v) for k, v in seg["kind"].value_counts().items()},
             "compseg_rows_with_share": int(seg["revenue_share"].notna().sum()),
             "compseg_pit_source": {k: int(v) for k, v in seg["pit_source"].value_counts().items()},
             "named_links_tenk_only": int(len(t_only)), "named_links_compseg_only": int(len(c_only)),
             "named_links_both": int(len(both)),
             "anonymous_links_tenk": int(len(anon_t)), "anonymous_links_compseg": int(len(anon_c)),
             "links_total_wide": int(len(W))}
    (RESULTS / "wide_graph_build.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))
    return W, TI


def remap(seg, t2c):
    """Customers bought by another universe firm map to the parent after the deal (same rule as the
    10-K graph), using the fiscal year end as the date."""
    tmp = seg.assign(seller_=seg["seller"], accession_=np.arange(len(seg)))
    named = tmp["buyer"].notna()
    df = tmp.loc[named, ["seller_", "buyer", "revenue_share", "accession_", "datadate"]].rename(
        columns={"seller_": "seller", "accession_": "accession", "datadate": "accepted_at"})
    out = seed_graph.remap_parents(df, t2c).set_index("accession")["buyer"]
    pos = np.arange(len(seg))
    seg = seg.copy()
    seg.loc[named.values, "buyer"] = pd.Series(pos[named.values]).map(out).values
    return seg[~(named.values & seg["buyer"].isna().values)]


def load():
    W = pd.read_parquet(OUT_LINKS)
    TI = pd.read_parquet(OUT_TI)
    pit.check_frame(W, ["accepted_at"], what="wide links")
    pit.check_frame(TI, ["accepted"], what="wide 10-K index")
    return W, TI


if __name__ == "__main__":
    build()
