"""Run the pipeline.

  python3 -m pipeline.run extract --tickers MCK,NVDA --since 2025-01-01 --forms 10-K
  python3 -m pipeline.run extract --all --since 2015-01-01            # full backfill (slow, costs API credits)
  python3 -m pipeline.run extract --tickers MCK --dry-run             # count candidates only, no LLM calls
  python3 -m pipeline.run daily                                       # new filings since the last run, for every company
  python3 -m pipeline.run export --as-of 2024-01-01 > graph_2023.json # point in time graph
  python3 -m pipeline.run review                                      # show the open review queue
"""
import argparse, datetime as dt, json, sys
from . import config, edgar, parse, candidates, extract, validate
from .entities import Entities
from .store import Store


def process_filing(filing, node_id, ents, store, dry_run=False, log=print):
    name = ents.nodes[node_id]["name"]
    n_cand = n_ok = n_rev = 0
    for doc_kind, url, html in edgar.download(filing):
        text = parse.html_to_text(html)
        cands = candidates.find(text, ents, node_id)
        n_cand += len(cands)
        if dry_run or not cands:
            continue
        text_norm = parse.norm(text)
        raw = extract.extract(name, filing["form"], cands)
        checked = [validate.validate(l, text_norm, node_id, name, ents, doc_kind, extract.check_direction) for l in raw]
        over = validate.share_sum_check([r for r, why in checked if not why])
        for rec, why in checked:
            if not why and rec["from_id"] in over and rec["revenue_share"] is not None:
                why = ["shares_sum_above_1"]
            if why:
                store.add_review(rec, why, filing, url, node_id); n_rev += 1
            else:
                store.add_observation(rec, filing, url, doc_kind, node_id); n_ok += 1
    if not dry_run:
        store.mark_filing(filing, node_id, n_cand, n_ok, n_rev)
    log(f"  {filing['form']:5} {filing['filed']} {filing['accession_no']}  candidates {n_cand}  stored {n_ok}  review {n_rev}")
    return n_cand, n_ok, n_rev


def run_extract(node_ids, ents, store, since, forms, limit=None, dry_run=False):
    tot = [0, 0, 0]
    for nid in node_ids:
        cik = ents.cik.get(nid)
        if not cik:
            print(f"{nid}: no CIK, skipped"); continue
        try:
            filings = edgar.list_filings(cik, since=since, forms=forms)
        except Exception as e:
            print(f"{nid}: listing failed: {e}"); continue
        todo = [f for f in filings if dry_run or not store.done(f["accession_no"])]
        if limit:
            todo = todo[-limit:]
        print(f"{nid}: {len(filings)} filings, {len(todo)} to process")
        for f in todo:
            try:
                for i, v in enumerate(process_filing(f, nid, ents, store, dry_run)):
                    tot[i] += v
            except Exception as e:                      # one bad filing must not stop the run
                print(f"  FAILED {f['accession_no']}: {e}")
    print(f"TOTAL candidates {tot[0]}  stored {tot[1]}  review {tot[2]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--tickers"); e.add_argument("--all", action="store_true")
    e.add_argument("--since", default="2015-01-01"); e.add_argument("--forms", default=",".join(config.FORMS))
    e.add_argument("--limit", type=int, help="latest N filings per company"); e.add_argument("--dry-run", action="store_true")
    sub.add_parser("daily")
    x = sub.add_parser("export"); x.add_argument("--as-of", default=dt.date.today().isoformat())
    d = sub.add_parser("diff"); d.add_argument("date_a"); d.add_argument("date_b")
    sub.add_parser("review")
    a = ap.parse_args(argv)
    store = Store()
    if a.cmd == "export":
        json.dump(store.graph_as_of(a.as_of), sys.stdout, indent=1); return
    if a.cmd == "diff":
        json.dump(store.diff(a.date_a, a.date_b), sys.stdout, indent=1); return
    if a.cmd == "review":
        for r in store.db.execute("SELECT * FROM review_queue WHERE status='open' ORDER BY id"):
            rec = json.loads(r["record"])
            print(f"#{r['id']} [{r['reasons']}] {rec['from_name']} -> {rec['to_name']} ({rec['type']})\n   \"{rec['evidence_quote'][:200]}\"\n   {r['source_url']}")
        return
    ents = Entities()
    if a.cmd == "daily":
        today = dt.date.today()
        before = (today - dt.timedelta(days=1)).isoformat()
        for nid in sorted(ents.cik):
            last = store.last_accepted(nid)
            since = last[:10] if last else (today - dt.timedelta(days=3)).isoformat()
            run_extract([nid], ents, store, since, config.FORMS)
        print(json.dumps(store.diff(before, (today + dt.timedelta(days=1)).isoformat()), indent=1))
        return
    ids = sorted(ents.cik) if a.all else [t.strip().lower().replace(".", "-") for t in (a.tickers or "").split(",") if t.strip()]
    run_extract(ids, ents, store, a.since, tuple(a.forms.split(",")), a.limit, a.dry_run)


if __name__ == "__main__":
    main()
