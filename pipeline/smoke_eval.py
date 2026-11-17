"""Quick recall check with no SEC access needed: feed passages from the hand reviewed links of the old bundle
through extraction and validation, and see whether the same pair and direction comes back.

  python3 -m pipeline.smoke_eval "<path to links_detail.jsonl>" 40

This is NOT the gold set of the project plan (it has only positives, from the latest filings). It is a sanity check.
"""
import json, random, sys
from . import extract, validate, parse
from .entities import Entities


def main(path, n=40, seed=7):
    ents = Entities()
    rows = []
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        if d.get("type") != "supply" or d.get("review_status") != "reviewed":
            continue
        ev = [e for e in d.get("evidence") or [] if e.get("quote_kind") == "verbatim" and e.get("reported_by")]
        ctx = [c for c in d.get("context_passages") or [] if c.get("text")]
        if ev and d["from"] in ents.nodes and d["to"] in ents.nodes and ev[0]["reported_by"] in (d["from"], d["to"]):
            rows.append((d, ev[0], (ctx[0]["text"] if ctx else ev[0]["quote"])))
    random.Random(seed).shuffle(rows)
    rows = rows[:n]
    hit = wrong_dir = miss = review = 0
    for d, ev, passage in rows:
        filer = ev["reported_by"]; name = ents.nodes[filer]["name"]
        raw = extract.extract(name, ev.get("form") or "10-K", [{"pid": 0, "passage": passage}])
        got = [validate.validate(l, parse.norm(passage), filer, name, ents, "body", extract.check_direction) for l in raw]
        pairs = {(r["from_id"], r["to_id"]): why for r, why in got}
        if (d["from"], d["to"]) in pairs:
            if pairs[(d["from"], d["to"])]: review += 1
            else: hit += 1
        elif (d["to"], d["from"]) in pairs:
            wrong_dir += 1
        else:
            miss += 1
            print("MISS", d["link_id"], "| got:", [(r["from_name"], r["to_name"], why) for r, why in got], "|", passage[:160])
    print(f"\n{len(rows)} reviewed links: found and passed {hit}, found but sent to review {review}, "
          f"direction reversed {wrong_dir}, missed {miss}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40)
