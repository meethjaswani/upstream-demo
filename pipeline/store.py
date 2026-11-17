"""Step 6, store: every observation of a link with its provenance. The graph for any past date is rebuilt from here."""
import datetime as dt, json, os, sqlite3
from . import config
from .validate import TIERS

SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (accession_no TEXT PRIMARY KEY, cik INTEGER, node_id TEXT, form TEXT, filed TEXT,
  accepted_at TEXT, url TEXT, processed_at TEXT, n_candidates INTEGER, n_links INTEGER, n_review INTEGER, extractor_version TEXT);
CREATE TABLE IF NOT EXISTS observations (id INTEGER PRIMARY KEY, from_id TEXT, to_id TEXT, type TEXT, revenue_share REAL,
  amount_usd REAL, tags TEXT, tier TEXT, evidence_quote TEXT, source_url TEXT, accession_no TEXT, accepted_at TEXT,
  reported_by TEXT, doc_kind TEXT, extractor_version TEXT,
  UNIQUE(accession_no, from_id, to_id, type, evidence_quote));
CREATE TABLE IF NOT EXISTS review_queue (id INTEGER PRIMARY KEY, accession_no TEXT, source_url TEXT, accepted_at TEXT,
  reported_by TEXT, reasons TEXT, record TEXT, status TEXT DEFAULT 'open', created_at TEXT);
CREATE INDEX IF NOT EXISTS obs_pair ON observations(from_id, to_id, type, accepted_at);
"""


class Store:
    def __init__(self, path=config.DB_PATH):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def done(self, accession_no):
        r = self.db.execute("SELECT extractor_version FROM filings WHERE accession_no=?", (accession_no,)).fetchone()
        return bool(r) and r[0] == config.EXTRACTOR_VERSION

    def add_observation(self, rec, filing, source_url, doc_kind, reported_by):
        self.db.execute(
            "INSERT OR IGNORE INTO observations (from_id,to_id,type,revenue_share,amount_usd,tags,tier,evidence_quote,"
            "source_url,accession_no,accepted_at,reported_by,doc_kind,extractor_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rec["from_id"], rec["to_id"], rec["type"], rec["revenue_share"], rec["amount_usd"], json.dumps(rec["tags"]),
             rec["tier"], rec["evidence_quote"], source_url, filing["accession_no"], filing["accepted_at"], reported_by,
             doc_kind, config.EXTRACTOR_VERSION))

    def add_review(self, rec, reasons, filing, source_url, reported_by):
        self.db.execute("INSERT INTO review_queue (accession_no,source_url,accepted_at,reported_by,reasons,record,created_at)"
                        " VALUES (?,?,?,?,?,?,?)",
                        (filing["accession_no"], source_url, filing["accepted_at"], reported_by, ";".join(reasons),
                         json.dumps(rec), dt.datetime.utcnow().isoformat()))

    def mark_filing(self, filing, node_id, n_cand, n_links, n_review):
        self.db.execute("INSERT OR REPLACE INTO filings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (filing["accession_no"], filing["cik"], node_id, filing["form"], filing["filed"],
                         filing["accepted_at"], filing["url"], dt.datetime.utcnow().isoformat(), n_cand, n_links,
                         n_review, config.EXTRACTOR_VERSION))
        self.db.commit()

    def last_accepted(self, node_id):
        r = self.db.execute("SELECT MAX(accepted_at) FROM filings WHERE node_id=?", (node_id,)).fetchone()
        return r[0]

    def graph_as_of(self, date, lifetime_days=config.LINK_LIFETIME_DAYS):
        """Links known strictly before `date` (ISO), using only filings accepted before it.
        A link drops out if no filing has repeated it within the lifetime window.
        A link reported in two filings or by both companies moves up one confidence tier."""
        start = (dt.date.fromisoformat(date[:10]) - dt.timedelta(days=lifetime_days)).isoformat()
        rows = self.db.execute("SELECT * FROM observations WHERE accepted_at < ? AND accepted_at >= ? ORDER BY accepted_at",
                               (date, start)).fetchall()
        links = {}
        for r in rows:
            key = (r["from_id"], r["to_id"], r["type"])
            l = links.setdefault(key, {"from": r["from_id"], "to": r["to_id"], "type": r["type"], "filings": set(),
                                       "reporters": set(), "valid_from": r["accepted_at"]})
            l["filings"].add(r["accession_no"]); l["reporters"].add(r["reported_by"])
            best = max(TIERS.index(r["tier"]), TIERS.index(l.get("base_tier", "INFERRED")))
            l["base_tier"] = TIERS[best]
            if r["revenue_share"] is not None or "revenue_share" not in l:      # latest stated share wins
                l["revenue_share"] = r["revenue_share"] if r["revenue_share"] is not None else l.get("revenue_share")
            l.update(amount_usd=r["amount_usd"] or l.get("amount_usd"), tags=json.loads(r["tags"]),
                     evidence_quote=r["evidence_quote"], source_url=r["source_url"], accession_no=r["accession_no"],
                     accepted_at=r["accepted_at"], extractor_version=r["extractor_version"])
        out = []
        for l in links.values():
            corroborated = len(l["filings"]) >= 2 or len(l["reporters"]) >= 2
            i = TIERS.index(l.pop("base_tier"))
            l["confidence"] = TIERS[min(i + 1, len(TIERS) - 1)] if corroborated and i > 0 else TIERS[i]
            l["corroborated"] = corroborated
            l["n_filings"] = len(l.pop("filings")); l.pop("reporters")
            out.append(l)
        return out

    def diff(self, date_a, date_b):
        """What changed in the graph between two dates: added, removed, changed (share or confidence)."""
        key = lambda l: (l["from"], l["to"], l["type"])
        a = {key(l): l for l in self.graph_as_of(date_a)}
        b = {key(l): l for l in self.graph_as_of(date_b)}
        changed = [k for k in a.keys() & b.keys()
                   if (a[k]["revenue_share"], a[k]["confidence"]) != (b[k]["revenue_share"], b[k]["confidence"])]
        return {"added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()), "changed": sorted(changed)}
