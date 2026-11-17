import json, os, tempfile
from pipeline import parse, candidates, validate
from pipeline.entities import Entities
from pipeline.store import Store


def ents():
    d = tempfile.mkdtemp()
    g = {"nodes": [{"id": "mck", "name": "McKesson Corporation"}, {"id": "cvs", "name": "CVS Health Corporation"},
                   {"id": "nvda", "name": "NVIDIA Corporation"}, {"id": "tsm", "name": "Taiwan Semiconductor Manufacturing Company"}]}
    json.dump(g, open(os.path.join(d, "g.json"), "w"))
    open(os.path.join(d, "sp.csv"), "w").write("Symbol,Security,CIK\nMCK,McKesson,927653\n")
    return Entities(os.path.join(d, "g.json"), os.path.join(d, "sp.csv"))


TEXT = ("Item 1. Business\nWe distribute pharmaceuticals across North America. Sales to our largest customer, CVS Health "
        "Corporation, accounted for approximately 24% of our total consolidated revenues in fiscal 2026. "
        "Our offices are located in Irving, Texas and we employ many people there.")
LINK = {"passage_id": 0, "from_company": "FILER", "to_company": "CVS Health Corporation", "type": "sells_to",
        "revenue_share": 0.24, "amount_usd": None, "tags": [], "anonymised": False, "inferred": False,
        "evidence_quote": "Sales to our largest customer, CVS Health Corporation, accounted for approximately 24% of our total consolidated revenues in fiscal 2026."}
OK_DIR = lambda *a: "A_SELLS_TO_B"


def test_sentence_split_keeps_abbreviations():
    s = [x for _, x in parse.sentences("We sold goods to Acme Inc. and Beta Corp. during the year. Revenue grew strongly in every region.")]
    assert len(s) == 2 and "Acme Inc. and Beta Corp." in s[0]


def test_candidates_keep_trigger_and_drop_noise():
    c = candidates.find(TEXT, ents(), "mck")
    assert len(c) == 1 and "CVS Health" in c[0]["sentence"] and c[0]["section"] == "Item 1"


def test_entity_resolution():
    e = ents()
    assert e.resolve("CVS Health") == "cvs" and e.resolve("NVIDIA") == "nvda" and e.resolve("Nobody LLC") is None
    assert e.mentions("We buy from NVIDIA and McKesson.", exclude="mck") == {"nvda"}


def test_valid_link_passes():
    rec, why = validate.validate(LINK, parse.norm(TEXT), "mck", "McKesson Corporation", ents(), "body", OK_DIR)
    assert why == [] and (rec["from_id"], rec["to_id"], rec["tier"]) == ("mck", "cvs", "DISCLOSED")


def test_invented_quote_is_rejected():
    bad = dict(LINK, evidence_quote="CVS Health Corporation accounted for 24% of McKesson revenue in fiscal 2026.")
    _, why = validate.validate(bad, parse.norm(TEXT), "mck", "McKesson Corporation", ents(), "body", OK_DIR)
    assert "quote_not_in_source" in why


def test_share_range_unknown_entity_and_direction():
    e, t = ents(), parse.norm(TEXT)
    assert "share_out_of_range" in validate.validate(dict(LINK, revenue_share=24), t, "mck", "McKesson", e, "body", OK_DIR)[1]
    assert "unknown_entity" in validate.validate(dict(LINK, to_company="Nobody LLC"), t, "mck", "McKesson", e, "body", OK_DIR)[1]
    assert validate.validate(LINK, t, "mck", "McKesson", e, "body", lambda *a: "B_SELLS_TO_A")[1] == ["direction_disagrees:B_SELLS_TO_A"]


def test_anonymous_customer_kept_and_share_sum():
    e = ents()
    txt = "Customer A accounted for 60% of total revenue and Customer B accounted for 55% of total revenue this year."
    recs = []
    for nm, sh in (("Customer A", 0.6), ("Customer B", 0.55)):
        l = dict(LINK, to_company=nm, revenue_share=sh, anonymised=True, evidence_quote=txt)
        rec, why = validate.validate(l, parse.norm(txt), "mck", "McKesson", e, "body", OK_DIR)
        assert why == [] and rec["to_id"].startswith("anon:mck:") and "anonymised" in rec["tags"]
        recs.append(rec)
    assert validate.share_sum_check(recs) == {"mck"}


def test_point_in_time_and_corroboration():
    s = Store(":memory:")
    rec, _ = validate.validate(LINK, parse.norm(TEXT), "mck", "McKesson", ents(), "body", OK_DIR)
    f1 = {"accession_no": "a1", "accepted_at": "2020-05-08T16:00:00.000Z", "cik": 1, "form": "10-K", "filed": "2020-05-08", "url": "u"}
    f2 = dict(f1, accession_no="a2", accepted_at="2021-05-07T16:00:00.000Z")
    stated = dict(rec, revenue_share=None, tier="STATED")
    s.add_observation(stated, f1, "u1", "body", "mck"); s.add_observation(stated, f2, "u2", "body", "mck")
    assert s.graph_as_of("2020-05-08") == []                              # filed that day, not yet known the day before
    g = s.graph_as_of("2020-06-01"); assert len(g) == 1 and g[0]["confidence"] == "STATED"
    g = s.graph_as_of("2021-06-01"); assert g[0]["confidence"] == "DISCLOSED" and g[0]["corroborated"]
    assert s.graph_as_of("2023-06-01") == []                              # not repeated for 550 days, dropped
    assert s.diff("2020-01-01", "2020-06-01")["added"] == [("mck", "cvs", "sells_to")]
