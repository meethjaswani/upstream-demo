"""SEC submissions (10-K acceptance times and 8-Ks) for every Compustat seller that names a
company customer, so compseg links can be dated point in time and the new firms' own filings
used for contamination. No 10-K documents are downloaded for these firms."""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from . import fetch_sec_index, wrds2


def seller_ciks():
    s = wrds2.seg_customer()
    co = wrds2.company_all().set_index("gvkey")
    ciks = s["gvkey"].drop_duplicates().map(co["cik"]).dropna().astype(int)
    return sorted(set(ciks))


def run():
    want = seller_ciks()
    have = {int(p.stem) for p in fetch_sec_index.SUB_DIR.glob("*.parquet")}
    todo = [c for c in want if c not in have]
    print("seller CIKs", len(want), "to fetch", len(todo), flush=True)
    done = 0

    def one(c):
        try:
            fetch_sec_index.fetch_submissions(c)
        except Exception as e:      # keep going; the fallback is datadate + 90 days
            print("failed", c, type(e).__name__, flush=True)

    with ThreadPoolExecutor(16) as ex:
        for _ in ex.map(one, todo):
            done += 1
            if done % 500 == 0:
                print(done, flush=True)
    fetch_sec_index.consolidate()


if __name__ == "__main__":
    run()
