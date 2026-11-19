"""Loaders for the second WRDS export (widening, amendment 12). Licensed, read in place from
config.WRDS2, never committed. Anything dated 2024-01-01 or later is dropped or capped on read:
comp_company_all IPO/deletion dates are not used at all; historical GICS, CCM links and CRSP
name spells that start in 2024+ are dropped and later end dates capped at 2023-12-31."""
import numpy as np
import pandas as pd

from . import pit
from .config import WRDS2
from .predecessors import canonical

LAST = pit.CUTOFF - pd.Timedelta(days=1)


def _read(name, dates=()):
    df = pd.read_parquet(WRDS2 / f"{name}.parquet")
    for c in dates:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def seg_customer(ctype="COMPANY"):
    """COMPANY customer rows; salecs summed over a seller's segments per (seller, customer, fiscal
    year end). Rows repeated across segment types with the same segment id are counted once."""
    s = _read("compseg_seg_customer_2012_2023", ["datadate"])
    s = s[(s["ctype"] == ctype) & s["cnms"].notna()].copy()
    s = pit.clip(s, "datadate")
    s["salecs"] = s["salecs"].astype(float)
    s["cnms"] = s["cnms"].str.strip()
    s = s.drop_duplicates(["gvkey", "datadate", "cnms", "sid", "salecs"])
    agg = s.groupby(["gvkey", "datadate", "cnms"], as_index=False).agg(
        salecs=("salecs", lambda x: x.sum(min_count=1)), n_segments=("sid", "nunique"))
    return agg


def company_all():
    co = _read("comp_company_all")
    co = co.drop(columns=[c for c in ("ipodate", "dldte", "dlrsn") if c in co.columns])
    co["cik"] = pd.to_numeric(co["cik"], errors="coerce").astype("Int64")
    co["cik_c"] = co["cik"].map(lambda x: canonical(int(x)) if pd.notna(x) else None)
    return co


def funda():
    f = _read("comp_funda_sellers", ["datadate"])
    f = pit.clip(f, "datadate")
    f["sale"] = f["sale"].astype(float)
    return f.sort_values(["gvkey", "datadate"]).drop_duplicates(["gvkey", "datadate"], keep="last")


def rdq():
    r = _read("comp_rdq_sellers", ["datadate", "rdq"]).dropna(subset=["rdq"])
    r = pit.clip(r, "rdq")
    pit.check_frame(r, ["rdq"], what="comp_rdq_sellers")
    return r


def hist_gics():
    g = _read("comp_hist_gics", ["indfrom", "indthru"])
    g = g[g["indfrom"] < pit.CUTOFF].copy()
    g["indthru"] = g["indthru"].fillna(LAST).clip(upper=LAST)
    return g.dropna(subset=["gsubind"])


def ccm():
    c = _read("ccm_links_sellers", ["linkdt", "linkenddt"])
    c = c[(c["linkdt"] < pit.CUTOFF) & c["linktype"].isin(["LU", "LC"])].dropna(subset=["permno"]).copy()
    c["linkenddt"] = c["linkenddt"].fillna(LAST).clip(upper=LAST)
    c["permno"] = c["permno"].astype(int)
    c["prim"] = c["linkprim"].isin(["P", "C"])
    return c


def names():
    n = _read("crsp_names_sellers", ["namedt", "nameendt"])
    n = n[n["namedt"] < pit.CUTOFF].copy()
    n["nameendt"] = n["nameendt"].clip(upper=LAST)
    n["permno"] = n["permno"].astype(int)
    return n


def dsf():
    d = _read("crsp_dsf_sellers", ["date"])
    d = pit.clip(d, "date")
    pit.check_frame(d, ["date"], what="crsp_dsf_sellers")
    d["permno"] = d["permno"].astype(int)
    for c in ["ret", "prc", "shrout"]:
        d[c] = d[c].astype(float)
    d["mcap"] = d["prc"].abs() * d["shrout"] * 1000.0
    return d[["permno", "date", "ret", "prc", "shrout", "mcap"]]


def delist():
    x = _read("crsp_delist_sellers", ["dlstdt"])
    x = pit.clip(x, "dlstdt")
    x["permno"] = x["permno"].astype(int)
    x["dlret"] = x["dlret"].astype(float)
    return x


def dsi():
    d = _read("crsp_dsi", ["date"])
    d = pit.clip(d, "date")
    pit.check_frame(d, ["date"], what="crsp_dsi")
    return d.set_index("date")["sprtrn"].astype(float)
