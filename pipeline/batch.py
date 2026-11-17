"""No API key mode. The LLM step is done by a Claude Code session reading and writing files.

  python3 -m pipeline.batch export --tickers MCK,NVDA --since 2025-01-01 --forms 10-K   # writes pipeline/work/*.in.json
  (Claude Code reads each .in.json and writes .out.json, then a checker pass writes .check.json)
  python3 -m pipeline.batch import                                                      # validates and stores

Every deterministic check still runs on import, so a careless answer cannot enter the graph.
"""
import argparse, glob, json, os
from . import config, edgar, parse, candidates, validate
from .entities import Entities
from .store import Store

WORK = os.path.join(config.PIPE, "work")


def export(ids, since, forms, limit):
    ents, store = Entities(), Store()
    os.makedirs(WORK, exist_ok=True)
    n = 0
    for nid in ids:
        cik = ents.cik.get(nid)
        if not cik:
            print(f"{nid}: no CIK, skipped"); continue
        todo = [f for f in edgar.list_filings(cik, since=since, forms=forms) if not store.done(f["accession_no"])]
        for f in (todo[-limit:] if limit else todo):
            for k, (doc_kind, url, html) in enumerate(edgar.download(f)):
                cands = candidates.find(parse.html_to_text(html), ents, nid)
                path = os.path.join(WORK, f"{nid}_{f['accession_no']}_{k}.in.json")
                json.dump({"filing": f, "node_id": nid, "filer_name": ents.nodes[nid]["name"], "doc_kind": doc_kind,
                           "url": url, "doc_index": k,
                           "passages": [{"pid": c["pid"], "passage": c["passage"]} for c in cands]},
                          open(path, "w"), indent=1)
                n += 1
                print(f"{os.path.basename(path)}: {len(cands)} passages")
    print(f"{n} batch files written to {WORK}")


def import_():
    ents, store = Entities(), Store()
    per_filing = {}
    for path in sorted(glob.glob(os.path.join(WORK, "*.in.json"))):
        out_path, chk_path = path.replace(".in.json", ".out.json"), path.replace(".in.json", ".check.json")
        if not os.path.exists(out_path):
            print("waiting for", os.path.basename(out_path)); continue
        b = json.load(open(path)); f, nid = b["filing"], b["node_id"]
        html = edgar.download(f)[b["doc_index"]][2]
        text_norm = parse.norm(parse.html_to_text(html))
        checks = json.load(open(chk_path)) if os.path.exists(chk_path) else {}
        direction = lambda quote, *_: checks.get(quote, "UNCHECKED")
        raw = json.load(open(out_path)).get("links", [])
        checked = [validate.validate(l, text_norm, nid, b["filer_name"], ents, b["doc_kind"], direction) for l in raw]
        over = validate.share_sum_check([r for r, why in checked if not why])
        ok = rev = 0
        for rec, why in checked:
            if not why and rec["from_id"] in over and rec["revenue_share"] is not None:
                why = ["shares_sum_above_1"]
            if why:
                store.add_review(rec, why, f, b["url"], nid); rev += 1
            else:
                store.add_observation(rec, f, b["url"], b["doc_kind"], nid); ok += 1
        t = per_filing.setdefault(f["accession_no"], [f, nid, 0, 0, 0])
        t[2] += len(b["passages"]); t[3] += ok; t[4] += rev
        os.rename(path, path + ".done")
        print(f"{os.path.basename(path)}: stored {ok}, review {rev}")
    for f, nid, c, ok, rev in per_filing.values():
        store.mark_filing(f, nid, c, ok, rev)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("--tickers", required=True); e.add_argument("--since", default="2015-01-01")
    e.add_argument("--forms", default="10-K"); e.add_argument("--limit", type=int)
    sub.add_parser("import")
    a = ap.parse_args()
    if a.cmd == "export":
        export([t.strip().lower().replace(".", "-") for t in a.tickers.split(",")], a.since, tuple(a.forms.split(",")), a.limit)
    else:
        import_()
