"""Amendment 1: which timezone is the SEC submissions `acceptanceDateTime` really in?

Two checks, written to results/timezone_check.json:
1. Apple's 8-K of 2 Jan 2019 (revenue guidance letter, released after the close): the raw
   submissions value against the 'Accepted' time printed on the EDGAR filing index page,
   which EDGAR shows in Eastern time.
2. EDGAR gives a filing the next business day as its filing date when it is accepted after
   17:30 Eastern. If the raw clock time is Eastern, the switch to next-day filing dates
   happens at 17:30 on the raw clock; if it were UTC it would happen at 21:30/22:30.
"""
import json
import re

import numpy as np
import pandas as pd

from . import events, fetch_sec_index, sec
from .config import RESULTS

APPLE = 320193


def index_page_accepted(cik, accession):
    acc_nd = accession.replace("-", "")
    r = sec.get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nd}/{accession}-index.htm")
    if r is None:
        return None
    m = re.search(r"Accepted</div>\s*<div class=\"info\">([^<]+)<", r.text)
    return m.group(1).strip() if m else None


def main():
    f = fetch_sec_index.load_filings()
    a = f[(f["cik"] == APPLE) & (f["form"] == "8-K") & (f["filing_date"] >= "2019-01-01") &
          (f["filing_date"] <= "2019-01-04")]
    out = {"apple_8k": []}
    cal = pd.bdate_range("2018-12-24", "2019-01-15").drop(pd.to_datetime(["2018-12-25", "2019-01-01"]))
    for r in a.itertuples():
        page = index_page_accepted(APPLE, r.accession)
        e = events.effective_day_index([r.accepted], cal)[0]
        raw_utc = pd.Timestamp(r.accepted).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        out["apple_8k"].append({"accession": r.accession, "items": r.items,
                                "raw_api_utc": str(raw_utc), "accepted_new_york": str(r.accepted),
                                "index_page_accepted": page, "event_day": str(cal[e].date())})
    # check 2: share of filings dated the next day, by raw clock hour
    g = f[f["form"].isin(["8-K", "10-Q", "10-K"])].copy()
    g["hour"] = g["accepted"].dt.hour + g["accepted"].dt.minute / 60   # New York clock after the fix
    g["next_day"] = g["filing_date"].dt.normalize() > g["accepted"].dt.normalize()
    bins = [0, 9, 12, 16, 17, 17.5, 18, 19, 21, 21.5, 22, 22.5, 24]
    g["bin"] = pd.cut(g["hour"], bins, right=False)
    tab = g.groupby("bin", observed=True)["next_day"].agg(["mean", "size"]).round(3)
    out["share_next_day_filing_date_by_raw_hour"] = {str(k): v for k, v in tab.to_dict(orient="index").items()}
    before, after = g[(g["hour"] >= 17) & (g["hour"] < 17.5)], g[(g["hour"] >= 17.5) & (g["hour"] < 18)]
    out["next_day_share_17_00_to_17_30"] = float(before["next_day"].mean())
    out["next_day_share_17_30_to_18_00"] = float(after["next_day"].mean())
    a0 = out["apple_8k"][0] if out["apple_8k"] else {}
    if a0.get("index_page_accepted"):
        diff = (pd.Timestamp(a0["raw_api_utc"]) - pd.Timestamp(a0["index_page_accepted"])).total_seconds() / 3600
        out["api_minus_index_page_hours"] = diff
        out["conclusion"] = ("acceptanceDateTime is true UTC; converted to New York time on load"
                             if diff in (4.0, 5.0) else "check by hand")
    (RESULTS / "timezone_check.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
