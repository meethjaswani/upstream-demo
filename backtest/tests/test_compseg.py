import pandas as pd

from stage1 import compseg
from stage1.names import NameIndex


def idx():
    meta = [{"cik": 320193, "name": "Apple Inc.", "former_names": []},
            {"cik": 104169, "name": "Walmart Inc.", "former_names": ["WAL MART STORES INC"]}]
    return NameIndex().build(meta, {"AAPL": 320193, "WMT": 104169}, [])


def test_resolve_named_anonymous_and_aggregate():
    ix = idx()
    assert compseg.resolve(ix, "Apple Inc") == ("cik:320193", "named")
    assert compseg.resolve(ix, "WALMART STORES") == ("cik:104169", "named")
    assert compseg.resolve(ix, "3 Customers")[1] == "anonymous"
    assert compseg.resolve(ix, "Customer A")[1] == "anonymous"
    assert compseg.resolve(ix, "Various distributors")[1] == "aggregate"
    assert compseg.resolve(ix, "Obscure Widgets Corp")[1] == "unresolved"


def test_availability_uses_matching_10k_else_datadate_plus_90():
    f = pd.DataFrame({"accession": ["a1", "a2"], "report_date": pd.to_datetime(["2018-09-28", "2019-09-27"]),
                      "filing_date": pd.to_datetime(["2018-11-16", "2019-11-15"]),
                      "accepted": pd.to_datetime(["2018-11-15 16:30", "2019-11-14 16:10"])})
    by = {4127: f}
    acc, t = compseg.availability(by, 4127, pd.Timestamp("2018-09-30"))
    assert acc == "a1" and t == pd.Timestamp("2018-11-15 16:30")
    acc, t = compseg.availability(by, 4127, pd.Timestamp("2016-09-30"))
    assert acc is None and t == pd.Timestamp("2016-12-29")
    acc, t = compseg.availability(by, None, pd.Timestamp("2016-09-30"))
    assert acc is None and t == pd.Timestamp("2016-12-29")
