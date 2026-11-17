import pandas as pd
import pytest

from stage1 import pit
from stage1.names import NameIndex, camel_words, norm
from stage1.seed_graph import SeedGraph, merge_filing, text_links, xbrl_links


@pytest.fixture(scope="module")
def idx():
    meta = [{"cik": 104169, "name": "Walmart Inc.", "former_names": ["WAL MART STORES INC"]},
            {"cik": 27419, "name": "TARGET CORP", "former_names": []},
            {"cik": 320193, "name": "Apple Inc.", "former_names": []},
            {"cik": 927653, "name": "MCKESSON CORP", "former_names": []},
            {"cik": 1140859, "name": "AmerisourceBergen Corp", "former_names": []},
            {"cik": 721371, "name": "CARDINAL HEALTH INC", "former_names": []},
            {"cik": 999, "name": "Seller Co", "former_names": []}]
    t2c = {"WMT": 104169, "TGT": 27419, "AAPL": 320193, "MCK": 927653, "COR": 1140859, "CAH": 721371}
    return NameIndex().build(meta, t2c, [])


def shares(rows):
    return {r["buyer"]: r["revenue_share"] for r in rows}


def test_norm_and_camel():
    assert norm("Wal-Mart Stores, Inc.") == "walmart"
    assert norm("The Home Depot, Inc.") == "home depot"
    assert norm("AT&T Inc.") == "at and t"
    assert camel_words("wmt:WalMartStoresIncMember") == "Wal Mart Stores Inc"


def test_single_customer_most_recent_year_first(idx):
    t = ("Sales to Wal-Mart Stores, Inc. and its affiliates accounted for approximately 26%, 25% and 24% "
         "of our net sales in fiscal 2017, 2016 and 2015, respectively.")
    assert shares(text_links(t, "cik:999", idx)) == {"cik:104169": 0.26}


def test_ascending_years_takes_last(idx):
    t = "Apple accounted for 30%, 33% and 36% of our revenue in 2015, 2016 and 2017."
    assert shares(text_links(t, "cik:999", idx)) == {"cik:320193": 0.36}


def test_respectively_list_is_zipped(idx):
    t = ("McKesson Corporation, AmerisourceBergen Corporation and Cardinal Health, Inc. accounted for 35%, "
         "28% and 20%, respectively, of our total revenues in 2018.")
    assert shares(text_links(t, "cik:999", idx)) == {"cik:927653": 0.35, "cik:1140859": 0.28, "cik:721371": 0.20}


def test_each_name_takes_following_percent(idx):
    t = "In 2019, Walmart accounted for 21% of net sales and Target accounted for 11% of net sales."
    assert shares(text_links(t, "cik:999", idx)) == {"cik:104169": 0.21, "cik:27419": 0.11}


def test_no_customer_and_receivable_and_supplier_sentences_ignored(idx):
    assert text_links("No single customer accounted for more than 10% of our net sales in 2018.", "cik:999", idx) == []
    assert text_links("Walmart accounted for 30% of accounts receivable at year end.", "cik:999", idx) == []
    assert text_links("Purchases from Apple accounted for 40% of our inventory costs and 5% of sales.",
                      "cik:999", idx) == []


def test_receivable_clause_cut(idx):
    t = "Walmart accounted for 18% of net sales in 2020 and 25% of accounts receivable."
    assert shares(text_links(t, "cik:999", idx)) == {"cik:104169": 0.18}


def test_growth_percent_skipped(idx):
    t = "Net sales to Target increased 12% and Target accounted for 15% of our net sales in 2021."
    assert shares(text_links(t, "cik:999", idx)) == {"cik:27419": 0.15}


def test_named_without_share_is_stated(idx):
    t = "Our customers include Walmart and Target, and sales to retail customers represented 60% of revenue."
    rows = text_links(t, "cik:999", idx)
    m = merge_filing([], rows)
    assert {r["buyer"]: r["tier"] for r in m}["cik:104169"] in ("STATED", "DISCLOSED")


def test_self_mentions_dropped(idx):
    t = "Walmart accounted for 20% of net sales of Walmart Inc."
    assert text_links(t, "cik:104169", idx) == []


def test_anonymous_customer(idx):
    t = "One customer accounted for 14% of our consolidated revenues in 2016."
    rows = text_links(t, "cik:999", idx)
    assert len(rows) == 1 and rows[0]["buyer"] is None and rows[0]["revenue_share"] == 0.14


def fact(member, v, bench="us-gaap:SalesRevenueNetMember", extra=None, start="2018-01-01", end="2018-12-31"):
    dims = {"srt:MajorCustomersAxis": member, "us-gaap:ConcentrationRiskByBenchmarkAxis": bench,
            "us-gaap:ConcentrationRiskByTypeAxis": "us-gaap:CustomerConcentrationRiskMember"}
    dims.update(extra or {})
    return {"concept": "us-gaap:ConcentrationRiskPercentage1", "value": v, "dims": dims, "start": start, "end": end}


def test_xbrl_route(idx):
    facts = [fact("abc:WalMartStoresIncMember", 0.22),
             fact("abc:WalMartStoresIncMember", 0.30, bench="us-gaap:AccountsReceivableMember"),
             fact("abc:TargetCorporationMember", 0.12, extra={"us-gaap:StatementBusinessSegmentsAxis": "abc:X"}),
             fact("abc:CustomerAMember", 0.11),
             fact("abc:WalMartStoresIncMember", 0.20, start="2017-01-01", end="2017-12-31"),
             fact("abc:TopTenCustomersMember", 0.55)]
    rows = xbrl_links(facts, "cik:999", idx)
    got = {(r["buyer"], r["revenue_share"]) for r in rows}
    assert got == {("cik:104169", 0.22), (None, 0.11)}


def test_merge_prefers_xbrl_and_tiers(idx):
    xb = [{"buyer": "cik:104169", "buyer_label": "Walmart", "kind": "named", "revenue_share": 0.22, "source": "xbrl",
           "period_end": "2018-12-31", "quote": "x"}]
    tx = [{"buyer": "cik:104169", "buyer_label": "Walmart", "kind": "named", "revenue_share": 0.2, "source": "text",
           "period_end": None, "quote": "t"},
          {"buyer": "cik:27419", "buyer_label": "Target", "kind": "named", "revenue_share": None, "source": "text",
           "period_end": None, "quote": "t"}]
    m = merge_filing(xb, tx)
    assert {r["buyer"]: (r["revenue_share"], r["tier"], r["source"]) for r in m} == {
        "cik:104169": (0.22, "DISCLOSED", "xbrl"), "cik:27419": (None, "STATED", "text")}


def test_seed_graph_point_in_time_and_supersede():
    links = pd.DataFrame([
        {"seller": "cik:1", "buyer": "cik:2", "accession": "a1", "accepted_at": pd.Timestamp("2016-02-10 16:30")},
        {"seller": "cik:1", "buyer": "cik:3", "accession": "a2", "accepted_at": pd.Timestamp("2017-02-10 08:00")},
    ])
    ti = pd.DataFrame([
        {"cik": 1, "accession": "a1", "accepted": pd.Timestamp("2016-02-10 16:30"), "fetched": True, "n_links": 1},
        {"cik": 1, "accession": "a2", "accepted": pd.Timestamp("2017-02-10 08:00"), "fetched": True, "n_links": 1},
        {"cik": 1, "accession": "a3", "accepted": pd.Timestamp("2018-02-10 08:00"), "fetched": True, "n_links": 0},
    ])
    g = SeedGraph(links, ti)
    assert len(g.at("2016-02-10")) == 0                      # accepted that day: not yet in the graph
    assert list(g.at("2016-02-11")["buyer"]) == ["cik:2"]
    assert list(g.at("2017-06-01")["buyer"]) == ["cik:3"]    # newer 10-K replaces the old set
    assert len(g.at("2018-03-01")) == 0                      # 10-K with no disclosure clears it
    ti2 = ti[ti["accession"] != "a3"]
    assert len(SeedGraph(links, ti2).at("2018-06-01")) == 0  # stale after 456 days
    with pytest.raises(pit.ClosedPeriodError):
        g.at("2024-01-05")
