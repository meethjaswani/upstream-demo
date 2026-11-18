"""SEC filings for CRSP index members that the Yahoo arm never covered (mostly firms delisted
before 2024): submissions (8-K/10-Q/10-K with acceptance times) and their 2015-2023 10-Ks."""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from . import crsp, fetch_10k, fetch_sec_index


def missing_ciks():
    m = crsp.permno_map()
    want = {int(c) for c in m["cik"].dropna()}
    have = set()
    p = fetch_sec_index.SEC_DIR / "filings.parquet"
    if p.exists():
        f = pd.read_parquet(p, columns=["cik", "orig_cik"])
        have = set(f["cik"]) | set(f["orig_cik"])
    have |= {int(x.stem) for x in fetch_sec_index.SUB_DIR.glob("*.parquet")}
    return sorted(want - have)


def run():
    new = missing_ciks()
    print("CIKs without SEC submissions:", len(new), flush=True)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(fetch_sec_index.fetch_submissions, new))
    fetch_sec_index.consolidate()
    fetch_10k.run(workers=24, ciks=sorted({int(c) for c in crsp.permno_map()["cik"].dropna()}))


if __name__ == "__main__":
    run()
