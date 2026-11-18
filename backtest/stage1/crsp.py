"""CRSP / Compustat loaders (WRDS export, licensed, read in place from config.WRDS).

Everything dated 2024-01-01 or later is dropped or capped as it is read:
- dsp500list spell ends after 2023 are capped at 2023-12-31 (the export's vintage marks
  current members with 2024-12-31; that tells us nothing we may use)
- dsenames rows starting in 2024 are dropped, later end dates capped
- CCM link end dates (and open links) are capped at 2023-12-31
"""
import numpy as np
import pandas as pd

from . import pit
from .config import WRDS
from .predecessors import canonical

LAST = pit.CUTOFF - pd.Timedelta(days=1)
WIN0 = pit.DATA_START


def _read(name, dates=()):
    df = pd.read_parquet(WRDS / f"{name}.parquet")
    for c in dates:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def dsf():
    """Daily stock file with delisting returns merged in (ret_d). Market cap in USD."""
    d = _read("crsp_dsf", ["date"])
    d = pit.clip(d, "date")
    pit.check_frame(d, ["date"], what="crsp_dsf")
    d["permno"] = d["permno"].astype(int)
    for c in ["ret", "retx", "prc", "shrout", "vol", "cfacpr", "cfacshr"]:
        d[c] = d[c].astype(float)
    d["mcap"] = d["prc"].abs() * d["shrout"] * 1000.0
    d = merge_delisting(d, delist())
    return d.sort_values(["permno", "date"]).reset_index(drop=True)


def delist():
    x = _read("crsp_delist", ["dlstdt"])
    x = pit.clip(x, "dlstdt")
    x["permno"] = x["permno"].astype(int)
    x["dlret"] = x["dlret"].astype(float)
    return x


def merge_delisting(d, dl):
    """Total return on the delisting day: (1+ret)(1+dlret)-1 when CRSP has a price row that day;
    otherwise the delisting return is added as its own row on the delisting date."""
    d = d.copy()
    d["dlret"] = np.nan
    key = d.set_index(["permno", "date"]).index
    dl = dl.dropna(subset=["dlret"])
    on_row = dl.set_index(["permno", "dlstdt"]).index.isin(key)
    a = dl[on_row]
    if len(a):
        m = d.merge(a[["permno", "dlstdt", "dlret"]], left_on=["permno", "date"], right_on=["permno", "dlstdt"],
                    how="left", suffixes=("", "_x"))
        d["dlret"] = m["dlret_x"].values
    extra = dl[~on_row]
    if len(extra):
        add = pd.DataFrame({"permno": extra["permno"].values, "date": extra["dlstdt"].values, "ret": np.nan,
                            "dlret": extra["dlret"].values})
        d = pd.concat([d, add], ignore_index=True)
    r, dr = d["ret"], d["dlret"]
    d["ret_d"] = np.where(dr.notna() & r.notna(), (1 + r) * (1 + dr) - 1, np.where(dr.notna(), dr, r))
    return d


def sp500_spells():
    s = _read("crsp_sp500list", ["start", "ending"])
    s["permno"] = s["permno"].astype(int)
    s = s[s["start"] < pit.CUTOFF]
    s["censored"] = s["ending"] > LAST
    s["ending"] = s["ending"].clip(upper=LAST)
    return s[s["ending"] >= WIN0].reset_index(drop=True)


def names():
    n = _read("crsp_names", ["namedt", "nameendt"])
    n = n[n["namedt"] < pit.CUTOFF].copy()
    n["nameendt"] = n["nameendt"].clip(upper=LAST)
    n["permno"] = n["permno"].astype(int)
    return n


def ccm():
    c = _read("ccm_links", ["linkdt", "linkenddt"])
    c = c[(c["linkdt"] < pit.CUTOFF) & c["linktype"].isin(["LU", "LC"])].copy()
    c["prim"] = c["linkprim"].isin(["P", "C"])
    c["linkenddt"] = c["linkenddt"].fillna(LAST).clip(upper=LAST)
    c = c.dropna(subset=["permno"])
    c["permno"] = c["permno"].astype(int)
    return c


def company():
    co = _read("comp_company")
    co["cik"] = pd.to_numeric(co["cik"], errors="coerce").astype("Int64")
    return co


def permno_map():
    """One row per permno: gvkey whose link covers most of 2014-10..2023-12 among gvkeys that
    Compustat gives a CIK for; CIK folded to the successor company (predecessors.py)."""
    c = ccm().merge(company()[["gvkey", "cik", "conm", "gsector", "gsubind", "sic"]], on="gvkey", how="left")
    a = c["linkdt"].clip(lower=WIN0)
    b = c["linkenddt"].clip(upper=LAST)
    c["overlap"] = (b - a).dt.days.clip(lower=0)
    c["has_cik"] = c["cik"].notna()
    c = c.sort_values(["permno", "has_cik", "prim", "overlap"], ascending=[True, False, False, False])
    m = c.drop_duplicates("permno")[["permno", "gvkey", "cik", "conm", "gsector", "gsubind", "sic"]].copy()
    # Compustat has no CIK for these two; SEC's ticker file does (EQR; DPS is now KDP, same registrant)
    fill = {"028733": 906107, "179700": 1418135}
    m["cik"] = [fill.get(g, c) if pd.isna(c) else c for g, c in zip(m["gvkey"], m["cik"])]
    # index members with no CCM link in the export (mostly second share classes): CRSP ticker -> SEC CIK
    sp = sp500_spells()
    nolink = sorted(set(sp["permno"]) - set(m["permno"]))
    if nolink:
        sec_t = _sec_tickers()
        manual = {17700: 1725057}          # Ceridian (CDAY), no longer in SEC's ticker file
        last = names().sort_values("nameendt").groupby("permno").tail(1).set_index("permno")
        add = []
        for p in nolink:
            tk = str(last["ticker"].get(p, "")).upper()
            cik = manual.get(p) or sec_t.get(tk) or sec_t.get(tk.replace(".", "-"))
            add.append({"permno": p, "gvkey": None, "cik": cik, "conm": last["comnam"].get(p),
                        "gsector": None, "gsubind": None, "sic": None})
        m = pd.concat([m, pd.DataFrame(add)], ignore_index=True)
        # second share classes take the sector codes of the primary class of the same company
        for col in ("gvkey", "gsector", "gsubind", "sic"):
            m[col] = m.groupby("cik")[col].transform(lambda s: s.ffill().bfill())
    m["cik"] = m["cik"].map(lambda x: canonical(int(x)) if pd.notna(x) else None)
    return m.reset_index(drop=True)


def _sec_tickers():
    import json
    from .config import CACHE
    f = CACHE / "sec" / "company_tickers.json"
    if not f.exists():
        return {}
    return {v["ticker"].upper(): int(v["cik_str"]) for v in json.loads(f.read_text()).values()}


def rdq():
    """Compustat earnings announcement dates by gvkey (rdq), within the open window."""
    r = _read("comp_rdq", ["datadate", "rdq"])
    r = r.dropna(subset=["rdq"])
    r = pit.clip(r, "rdq")
    pit.check_frame(r, ["rdq", "datadate"], what="comp_rdq")
    return r


def ticker_cik():
    """Historical ticker -> CIK from CRSP names (latest name spell wins for reused tickers)."""
    n = names().merge(permno_map()[["permno", "cik"]], on="permno").dropna(subset=["cik"])
    n = n.sort_values("nameendt").drop_duplicates("ticker", keep="last")
    return {t.upper(): int(c) for t, c in zip(n["ticker"], n["cik"]) if isinstance(t, str)}
