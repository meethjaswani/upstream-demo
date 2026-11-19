"""Hand audit of Compustat customer-name matches (precision check before the widened search).

Population: distinct (customer name -> firm) matches among resolved Compustat COMPANY rows.
Sample: 60, fixed seed, stratified: 20 short names (one word after normalisation or <= 10 characters),
40 others. The verdicts are entered by hand in results/match_audit_verdicts.csv (match id, verdict,
reason); this module draws the sample and computes precision from the verdicts.
"""
import json

import numpy as np
import pandas as pd

from . import compseg, wrds2
from .config import CACHE, RESULTS, SEED
from .names import norm


def population():
    W, _ = compseg.load()
    c = W[(W["source"].isin(["compseg", "both"])) & W["buyer"].str.startswith(("cik:", "gv:"), na=False)]
    m = c.groupby(["buyer_label", "buyer"]).agg(rows=("seller", "size"), sellers=("seller", "nunique"),
                                                 example_seller=("seller", "first"),
                                                 example_year=("report_date", "first")).reset_index()
    m["short"] = [len(norm(n).split()) <= 1 or len(n.strip()) <= 10 for n in m["buyer_label"]]
    return m


def names_lookup():
    meta = json.loads((CACHE / "sec" / "entity_meta.json").read_text())
    nm = {f"cik:{x['cik']}": (x.get("name"), ", ".join((x.get("former_names") or [])[:3])) for x in meta}
    co = wrds2.company_all()
    for r in co.itertuples():
        node = f"cik:{int(r.cik_c)}" if pd.notna(r.cik_c) else f"gv:{r.gvkey}"
        nm.setdefault(node, (r.conm, r.conml))
    return nm


def draw(seed=SEED):
    m = population()
    rng = np.random.default_rng(seed)
    short = m[m["short"]]
    rest = m[~m["short"]]
    s = pd.concat([short.iloc[rng.choice(len(short), 20, replace=False)],
                   rest.iloc[rng.choice(len(rest), 40, replace=False)]], ignore_index=True)
    nm = names_lookup()
    s["matched_name"] = s["buyer"].map(lambda b: nm.get(b, ("?", ""))[0])
    s["matched_other_names"] = s["buyer"].map(lambda b: nm.get(b, ("?", ""))[1])
    s["seller_name"] = s["example_seller"].map(lambda b: nm.get(b, ("?", ""))[0])
    s.insert(0, "match_id", range(1, len(s) + 1))
    s.to_csv(CACHE / "match_audit_sample.csv", index=False)       # names from licensed data: cache only
    pop = {"population_matches": int(len(m)), "population_short": int(m["short"].sum()),
           "population_rows": int(m["rows"].sum()), "population_rows_short": int(m.loc[m["short"], "rows"].sum())}
    return s, pop


def score(verdicts_path=RESULTS / "match_audit_verdicts.csv", seed=SEED):
    s = pd.read_csv(CACHE / "match_audit_sample.csv")
    v = pd.read_csv(verdicts_path)
    d = s.merge(v, on="match_id")
    _, pop = draw(seed)
    ok = d["verdict"].eq("correct")
    res = {"sample": int(len(d)), "correct": int(ok.sum()), "precision_sample": round(float(ok.mean()), 3),
           "precision_short": round(float(ok[d["short"]].mean()), 3),
           "precision_other": round(float(ok[~d["short"]].mean()), 3), **pop}
    w = pop["population_short"] / pop["population_matches"]
    res["precision_weighted_by_matches"] = round(w * res["precision_short"] + (1 - w) * res["precision_other"], 3)
    (RESULTS / "match_audit.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    import sys
    s, pop = draw(int(sys.argv[1]) if len(sys.argv) > 1 else SEED)
    print(pop)
    pd.set_option("display.width", 250, "display.max_colwidth", 60)
    print(s[["match_id", "short", "buyer_label", "matched_name", "matched_other_names", "seller_name",
             "example_year", "rows"]].to_string(index=False))
