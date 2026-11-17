"""Checks on the seed graph: overlap with the Oct 2026 snapshot's disclosed-share links
(cross-check only, not used to build anything) and a random sample of links with quotes."""
import json

import pandas as pd

from . import seed_graph
from .config import CACHE, GRAPH_JSON, RESULTS, SEED

DISCLOSED = {"disclosed_share", "disclosed_share_xbrl", "disclosed_share_auto_extracted", "disclosed_lower_bound"}


def main():
    links, ti = seed_graph.load()
    ent = pd.read_csv(CACHE / "entities.csv").dropna(subset=["cik"])
    t2c = {t.upper(): int(c) for t, c in zip(ent["member_ticker"], ent["cik"])}
    t2c.update({t.upper(): int(c) for t, c in zip(ent["yahoo"].fillna(""), ent["cik"]) if t})
    g = json.load(open(GRAPH_JSON))
    tick = {n["id"]: (n.get("ticker") or "").upper() for n in g["nodes"]}
    ref = []
    for e in g["exposures"]:
        if e["channel"] == "demand" and e.get("basis") in DISCLOSED:
            s, b = tick.get(e["exposed"]), tick.get(e["source"])
            if s in t2c and b in t2c:
                ref.append((f"cik:{t2c[s]}", f"cik:{t2c[b]}", s, b, e["weight_current"]["mode"]))
    ref = pd.DataFrame(ref, columns=["seller", "buyer", "seller_t", "buyer_t", "share_2026"]).drop_duplicates(["seller", "buyer"])
    late = links[pd.to_datetime(links["accepted_at"]) >= "2022-01-01"]
    have = late.groupby(["seller", "buyer"])["revenue_share"].max()
    ever = set(zip(links["seller"], links["buyer"]))
    ref["found_2022_23"] = [(s, b) in have.index for s, b in zip(ref["seller"], ref["buyer"])]
    ref["found_any_year"] = [(s, b) in ever for s, b in zip(ref["seller"], ref["buyer"])]
    ref["share_2022_23"] = [have.get((s, b)) for s, b in zip(ref["seller"], ref["buyer"])]
    ref.to_csv(RESULTS / "seed_crosscheck_2026.csv", index=False)
    named = links[links["buyer"].notna()]
    sample = named.sample(min(40, len(named)), random_state=SEED)[
        ["seller", "buyer", "buyer_label", "revenue_share", "tier", "source", "accepted_at", "quote"]]
    sample.to_csv(RESULTS / "seed_sample_for_review.csv", index=False)
    print("2026 disclosed-share pairs between universe firms:", len(ref),
          "found in 2022-23 10-Ks:", int(ref["found_2022_23"].sum()), "found in any year:", int(ref["found_any_year"].sum()))
    return ref, sample


if __name__ == "__main__":
    main()
