"""SEC index data for the universe.

1. Map every membership ticker to a Yahoo symbol and an SEC CIK (cache/entities.csv).
2. Submissions per CIK: every 10-K, 10-Q and 8-K accepted before 2024-01-01, with the
   acceptance datetime and the 8-K item codes (cache/sec/filings.parquet).
3. Shares outstanding per filing from companyfacts (cache/sec/shares.parquet).

Raw JSON is not kept: rows dated 2024-01 onwards are dropped before anything is written.
"""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from . import fetch_prices, pit, sec
from .config import CACHE

SEC_DIR = CACHE / "sec"
SUB_DIR = SEC_DIR / "submissions"
SH_DIR = SEC_DIR / "shares"
for d in (SEC_DIR, SUB_DIR, SH_DIR):
    d.mkdir(parents=True, exist_ok=True)

FORMS = {"10-K", "10-K405", "10-KT", "10-Q", "8-K"}
SHARE_CONCEPTS = [("dei", "EntityCommonStockSharesOutstanding"),
                  ("us-gaap", "CommonStockSharesOutstanding"),
                  ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic"),
                  ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding")]
FIRST = pd.Timestamp("2013-01-01")


def sec_tickers():
    f = SEC_DIR / "company_tickers.json"
    if not f.exists():
        data = sec.get_json("https://www.sec.gov/files/company_tickers.json")
        f.write_text(json.dumps(data))
    data = json.loads(f.read_text())
    return {v["ticker"].upper(): (int(v["cik_str"]), v["title"]) for v in data.values()}


def build_entities():
    st = pd.read_csv(CACHE / "price_status.csv")
    tick = sec_tickers()
    rows = []
    for r in st.itertuples():
        cik = name = None
        for cand in (r.yahoo, r.member_ticker):
            if isinstance(cand, str):
                for c in (cand.upper(), cand.upper().replace(".", "-"), cand.upper().replace("-", ".")):
                    if c in tick:
                        cik, name = tick[c]
                        break
            if cik:
                break
        rows.append({"member_ticker": r.member_ticker, "yahoo": r.yahoo if isinstance(r.yahoo, str) else None,
                     "has_prices": pd.notna(r.size), "cik": cik, "sec_name": name})
    ent = pd.DataFrame(rows)
    ent["cik"] = ent["cik"].astype("Int64")
    ent.to_csv(CACHE / "entities.csv", index=False)
    return ent


def _acc_time(s):
    """acceptanceDateTime is true UTC (checked in timezone_check.py: Apple's 8-K of 2 Jan 2019
    is 21:30:03Z in the API and 16:30:03 on the EDGAR index page). Stored as naive New York time."""
    t = pd.to_datetime(s, utc=True, errors="coerce")
    return t.dt.tz_convert("America/New_York").dt.tz_localize(None)


def fix_cached_tz():
    """One-off: per-CIK files written before the UTC fix hold the UTC clock time; convert them."""
    n = 0
    for p in sorted(SUB_DIR.glob("*.parquet")):
        df = pd.read_parquet(p)
        if df.empty or "accepted_tz" in df.columns:
            continue
        df["accepted"] = (df["accepted"].dt.tz_localize("UTC").dt.tz_convert("America/New_York")
                          .dt.tz_localize(None))
        df["accepted_tz"] = "America/New_York"
        df.to_parquet(p, index=False)
        n += 1
    return n


def _frame(block):
    df = pd.DataFrame(block)
    if df.empty:
        return df
    keep = ["accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "items",
            "primaryDocument", "isXBRL", "isInlineXBRL"]
    return df[[c for c in keep if c in df.columns]]


def fetch_submissions(cik):
    out = SUB_DIR / f"{cik}.parquet"
    if out.exists():
        return
    j = sec.get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    if j is None:
        pd.DataFrame().to_parquet(out)
        return
    parts = [_frame(j["filings"]["recent"])]
    for f in j["filings"].get("files", []):
        if pd.Timestamp(f["filingTo"]) >= FIRST and pd.Timestamp(f["filingFrom"]) < pit.CUTOFF:
            parts.append(_frame(sec.get_json("https://data.sec.gov/submissions/" + f["name"])))
    df = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    df["accepted"] = _acc_time(df["acceptanceDateTime"])
    df["filingDate"] = pd.to_datetime(df["filingDate"])
    df = df[df["form"].isin(FORMS) & (df["filingDate"] >= FIRST)]
    df = pit.clip(pit.clip(df, "filingDate"), "accepted")
    df = df.drop(columns=["acceptanceDateTime"]).rename(columns={
        "accessionNumber": "accession", "filingDate": "filing_date", "reportDate": "report_date",
        "primaryDocument": "primary_doc", "isXBRL": "is_xbrl", "isInlineXBRL": "is_ixbrl"})
    df["cik"] = cik
    df["accepted_tz"] = "America/New_York"
    pit.check_frame(df, ["filing_date", "accepted"], what=f"submissions {cik}")
    df.to_parquet(out, index=False)
    former = [x for x in j.get("formerNames", []) if pd.Timestamp(x["from"][:10]) < pit.CUTOFF]
    meta = {"cik": cik, "name": j.get("name"), "sic": j.get("sic"), "sic_desc": j.get("sicDescription"),
            "fiscal_year_end": j.get("fiscalYearEnd"), "former_names": [x["name"] for x in former]}
    (SUB_DIR / f"{cik}.meta.json").write_text(json.dumps(meta))


def fetch_shares(cik):
    out = SH_DIR / f"{cik}.parquet"
    if out.exists():
        return
    j = sec.get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
    rows = []
    for tax, concept in SHARE_CONCEPTS + [("dei", "EntityPublicFloat")]:
        units = ((j or {}).get("facts", {}).get(tax, {}).get(concept, {}) or {}).get("units", {})
        for v in units.get("shares", []) + units.get("USD", []):
            val = v.get("val")
            rows.append({"concept": concept, "end": v.get("end"), "val": float(val) if val is not None else None,
                         "accn": v.get("accn"),
                         "form": v.get("form"), "filed": v.get("filed")})
    df = pd.DataFrame(rows, columns=["concept", "end", "val", "accn", "form", "filed"])
    df["filed"] = pd.to_datetime(df["filed"])
    df["end"] = pd.to_datetime(df["end"], errors="coerce")
    df = pit.clip(df, "filed")
    df = df[df["filed"] >= FIRST]
    df["cik"] = cik
    pit.check_frame(df, ["filed"], what=f"shares {cik}")
    df.to_parquet(out, index=False)


def run(workers=8):
    ent = build_entities()
    ciks = sorted(set(int(c) for c in ent["cik"].dropna()))
    print("entities", len(ent), "with CIK", ent["cik"].notna().sum(), "unique CIKs", len(ciks), flush=True)
    jobs = [(fetch_submissions, c) for c in ciks] + [(fetch_shares, c) for c in ciks]
    done = 0
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(f, c): (f.__name__, c) for f, c in jobs}
        for fu in as_completed(futs):
            fu.result()
            done += 1
            if done % 100 == 0:
                print(f"{done}/{len(jobs)}", flush=True)
    consolidate()


def consolidate():
    """Merge per-CIK files. Predecessor CIKs (predecessors.py) are folded into the successor:
    `cik` is the company, `orig_cik` the registrant that filed (used for archive URLs)."""
    from .predecessors import canonical
    subs = [pd.read_parquet(p) for p in sorted(SUB_DIR.glob("*.parquet"))]
    subs = pd.concat([s for s in subs if not s.empty], ignore_index=True)
    subs["orig_cik"] = subs["cik"].astype(int)
    subs["cik"] = subs["orig_cik"].map(canonical)
    subs = subs.sort_values(["accession", "orig_cik"]).drop_duplicates("accession", keep="first")
    pit.check_frame(subs, ["filing_date", "accepted"], what="filings")
    subs.to_parquet(SEC_DIR / "filings.parquet", index=False)
    sh = pd.concat([pd.read_parquet(p) for p in sorted(SH_DIR.glob("*.parquet"))], ignore_index=True)
    sh["orig_cik"] = sh["cik"].astype(int)
    sh["cik"] = sh["orig_cik"].map(canonical)
    pit.check_frame(sh, ["filed"], what="shares")
    sh.to_parquet(SEC_DIR / "shares.parquet", index=False)
    metas = {}
    for p in sorted(SUB_DIR.glob("*.meta.json")):
        m = json.loads(p.read_text())
        c = canonical(m["cik"])
        names = [m.get("name")] + list(m.get("former_names") or [])
        if c in metas:
            metas[c]["former_names"] = list(dict.fromkeys(metas[c]["former_names"] + [n for n in names if n]))
        else:
            if c != m["cik"]:
                m = {**m, "cik": c, "name": None, "former_names": [n for n in names if n]}
            metas[c] = m
    for c, m in metas.items():
        if m.get("name") is None and m["former_names"]:
            m["name"] = m["former_names"][0]
    pd.DataFrame(list(metas.values())).to_json(SEC_DIR / "entity_meta.json", orient="records")
    print("filings", len(subs), subs["form"].value_counts().to_dict())
    print("share facts", len(sh), "ciks", sh["cik"].nunique())


def load_filings():
    df = pd.read_parquet(SEC_DIR / "filings.parquet")
    return pit.check_frame(df, ["filing_date", "accepted"], what="filings")


if __name__ == "__main__":
    run()
