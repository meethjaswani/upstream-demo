"""Entity dictionary: company names and aliases to node ids, built from data/graph.json and the S&P list."""
import csv, json, os, re
from . import config

_SUFFIX = re.compile(r",?\s+(incorporated|inc\.?|corporation|corp\.?|company|co\.?|ltd\.?|limited|plc|p\.l\.c\.|"
                     r"llc|l\.p\.|lp|n\.v\.|s\.a\.|ag|se|holdings?|group|\(the\)|& co\.?)$", re.I)
# names that are also ordinary words: only match the full legal name, never the short form
_AMBIGUOUS = {"target", "gap", "block", "match", "visa", "apple", "ball", "ross", "coach", "first", "general", "united",
              "national", "american", "international", "global", "western", "southern", "public", "progressive",
              "corning", "dover", "intuit", "keys", "best", "dominion", "amazon", "meta", "alphabet", "oracle", "arm"}


def _aliases(name):
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", name)          # "Taiwan Semiconductor Manufacturing (TSMC)"
    if m:
        return _aliases(m.group(1)) | {name} | ({m.group(2)} if len(m.group(2)) >= 3 else set())
    out, cur = {name}, name
    for _ in range(3):
        nxt = _SUFFIX.sub("", cur).strip(" ,")
        if nxt == cur:
            break
        out.add(nxt)
        cur = nxt
    return {a for a in out if len(a) >= 4 and (a.lower() not in _AMBIGUOUS or a == name)}


class Entities:
    def __init__(self, graph_path=config.GRAPH_JSON, sp500_path=config.SP500_CSV, extra_aliases=None):
        g = json.load(open(graph_path, encoding="utf-8"))
        self.nodes = {n["id"]: n for n in g["nodes"]}
        self.alias = {}                                   # lowercased alias -> node id
        for n in g["nodes"]:
            for a in _aliases(n["name"]):
                self.alias.setdefault(a.lower(), n["id"])
        extra = dict(extra_aliases or {})
        alias_csv = os.path.join(os.path.dirname(sp500_path), "aliases.csv")
        if os.path.exists(alias_csv):                     # hand kept: alias,node_id
            extra.update({r["alias"]: r["node_id"] for r in csv.DictReader(open(alias_csv, encoding="utf-8"))})
        for a, nid in extra.items():
            if nid in self.nodes:
                self.alias[a.lower()] = nid
        self.cik = {}                                     # node id -> CIK (S&P members)
        for r in csv.DictReader(open(sp500_path, encoding="utf-8")):
            nid = r["Symbol"].lower().replace(".", "-")
            if nid in self.nodes:
                self.cik[nid] = int(r["CIK"])
        names = sorted(self.alias, key=len, reverse=True)
        self._rx = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(a) for a in names) + r")(?![A-Za-z0-9])", re.I)

    def resolve(self, name):
        """Name as written in a filing -> node id, or None."""
        if not name:
            return None
        key = name.strip().lower()
        if key in self.alias:
            return self.alias[key]
        for a in _aliases(name.strip()):
            if a.lower() in self.alias:
                return self.alias[a.lower()]
        return None

    def mentions(self, text, exclude=None):
        """Node ids of known companies named in the text, leaving out the filer itself."""
        found = {self.alias[m.group(1).lower()] for m in self._rx.finditer(text)}
        found.discard(exclude)
        return found
