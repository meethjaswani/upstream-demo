"""Companies that moved to a new holding company (new CIK) while the listed shares and the
Yahoo price history stayed continuous. Filings of the old CIK are merged into the successor,
so the company is one entity across the change. Ticker reuse by a different company is NOT
listed here (those spans are rejected by the universe check).
"""
PREDECESSOR = {      # old CIK -> successor CIK (checked against SEC names in verify())
    34088: 2115436,      # Exxon Mobil Corp -> ExxonMobil Holdings Corp
    1364742: 2012383,    # BlackRock (old) -> BlackRock, Inc. (2024 holding company)
    1144519: 1996862,    # Bunge Ltd -> Bunge Global SA (2023)
    6769: 1841666,       # Apache Corp -> APA Corp (2021)
    1441634: 1730168,    # Avago Technologies -> Broadcom Inc
    1649338: 1730168,    # Broadcom Ltd (2016-2018) -> Broadcom Inc
    701221: 1739940,     # Cigna Corp (old) -> Cigna Group (2018)
    1001039: 1744489,    # Walt Disney (old, TWDC Enterprises 18) -> Walt Disney Co (2019)
    1288776: 1652044,    # Google Inc -> Alphabet (2015)
    48039: 1915657,      # HollyFrontier -> HF Sinclair (2022)
    64670: 1613103,      # Medtronic Inc -> Medtronic plc (2015)
    108772: 1770450,     # Xerox Corp -> Xerox Holdings (2019)
    1593538: 2152623,    # Navient Corp -> Navient Holdings
}

# membership ticker that meant another company before a date: (ticker, until, meant)
DATED_TICKERS = [("IR", "2020-03-02", "TT")]   # Ingersoll-Rand plc became Trane (TT); IR then = Gardner Denver


def canonical(cik):
    if cik is None:
        return None
    c = int(cik)
    return PREDECESSOR.get(c, c)


def verify():
    import json
    from . import fetch_sec_index
    from .config import CACHE
    out = []
    for old, new in PREDECESSOR.items():
        fetch_sec_index.fetch_submissions(old)
        fetch_sec_index.fetch_shares(old)
        m_old = json.loads((fetch_sec_index.SUB_DIR / f"{old}.meta.json").read_text())
        p = fetch_sec_index.SUB_DIR / f"{new}.meta.json"
        m_new = json.loads(p.read_text()) if p.exists() else {}
        import pandas as pd
        f = pd.read_parquet(fetch_sec_index.SUB_DIR / f"{old}.parquet")
        k = f[f["form"] == "10-K"]
        out.append({"old": old, "old_name": m_old.get("name"), "new": new, "new_name": m_new.get("name"),
                    "old_10k_first": str(k["filing_date"].min().date()) if len(k) else None,
                    "old_10k_last": str(k["filing_date"].max().date()) if len(k) else None})
    (CACHE / "predecessors_check.json").write_text(json.dumps(out, indent=1))
    for o in out:
        print(o)


if __name__ == "__main__":
    verify()
