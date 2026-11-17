"""Seed graph: major-customer links from annual 10-Ks accepted 2015-2023.

Route 1 (structured): XBRL ConcentrationRiskPercentage facts whose context has a customer
member (srt/us-gaap MajorCustomersAxis or a custom *Customer* axis), revenue benchmark,
current fiscal year, no segment or product dimension.
Route 2 (text): sentences in the 10-K with a percentage, a revenue word and a concentration
cue ('accounted for', 'represented', ...); named customers found with the name index.
Anonymous customers ('Customer A', 'one customer') are kept as edges without a buyer.

Tiers: share stated in the filing (XBRL or text) -> DISCLOSED; customer named in the text
without a share -> STATED.

A seller's link set comes from its latest 10-K accepted before day t; a 10-K with no
customer disclosure clears the seller's links; sets older than STALE_DAYS are dropped.
"""
import gzip
import json
import re

import numpy as np
import pandas as pd

from . import fetch_10k, pit
from .config import CACHE, GRAPH_JSON
from .names import NameIndex, camel_words, norm

STALE_DAYS = 456
OUT = CACHE / "seed_links.parquet"
TENK_INDEX = CACHE / "tenk_index.parquet"

PCT = re.compile(r"(?<![\d.$])(\d{1,3}(?:\.\d+)?)\s?(?:%|percent\b|per cent\b)", re.I)
REV = re.compile(r"\b(revenues?|net sales|sales|net revenues?|operating revenues?|rental revenues?|rental income|"
                 r"product sales|billings)\b", re.I)
CUE = re.compile(r"accounted for|account for|represent(?:ed|s|ing)?\b|comprised|constitut(?:ed|es)|amounted to|"
                 r"contributed|attributable to|derived from|made up|generated|sales to|revenues? from|customer|tenant",
                 re.I)
SUPPLY = re.compile(r"\b(purchases? from|purchased from|suppliers?|vendors?|sourced from|raw materials?)\b", re.I)
BEFORE_SKIP = re.compile(r"(increase[ds]?|decrease[ds]?|grew|grow|growth|declined?|declines|rose|fell|up|down|"
                         r"higher|lower|margins?|rates?|interest|tax|discount|ownership|owns?|owned|stake|equity|"
                         r"shares|voting|approximately half|change|changed|by)\W+(?:[\w$.,]+\W+){0,2}$", re.I)
ANON = re.compile(r"\b(customer [A-Z]\b|customer (?:one|two|three|four|1|2|3|4)\b|one customer|a single customer|"
                  r"(?:our )?(?:largest|second[- ]largest|third[- ]largest) (?:customer|client|tenant)|"
                  r"another customer|one of our customers|one client|a single client|one tenant|"
                  r"two customers|three customers)", re.I)
NONE_CUE = re.compile(r"\bno (?:single |one |individual |other )?(?:customer|client|tenant)s?\b|"
                      r"\bnone of (?:our|the) customers\b|\bdid not have any (?:single )?customer", re.I)
SENT = re.compile(r"(?<=[.;])\s+(?=[A-Z(\"“])")
YEAR = re.compile(r"\b(?:fiscal\s+)?((?:19|20)\d\d)\b")

ANON_MEMBER = re.compile(r"^(customer|client|tenant|lessee)\s?([a-z]|\d+|one|two|three|four|five)$|"
                         r"^(one|two|three|single|largest|major|significant|another|second|third|first)\b", re.I)
AGG_MEMBER = re.compile(r"\b(customers|clients|tenants|distributors|wholesalers|others?|all|top|ten|five|"
                        r"commercial|international|domestic|retail|group)\b", re.I)
GOV_MEMBER = re.compile(r"\b(government|federal|defense|navy|army|air force|dod)\b", re.I)
REV_BENCH = re.compile(r"revenue|sales", re.I)
NOT_REV = re.compile(r"receivable|purchase|cost|supplier|vendor|inventory|expense|payable|backlog|asset", re.I)
CONC_AXES = re.compile(r"ConcentrationRiskByBenchmarkAxis|ConcentrationRiskByTypeAxis", re.I)


def build_index():
    ent = pd.read_csv(CACHE / "entities.csv")
    meta = json.loads((CACHE / "sec" / "entity_meta.json").read_text())
    t2c = {}
    for r in ent.dropna(subset=["cik"]).itertuples():
        for t in (r.member_ticker, r.yahoo):
            if isinstance(t, str):
                t2c.setdefault(t.upper(), int(r.cik))
    g = json.load(open(GRAPH_JSON))
    idx = NameIndex().build(meta, t2c, g["nodes"])
    return idx, t2c


# ------------------------------------------------------------------ XBRL route
def xbrl_links(facts, seller, idx):
    rows = []
    good = []
    for f in facts:
        if f.get("value") is None or not f.get("end") or not f.get("start"):
            continue
        dims = f.get("dims", {})
        cust = [d for d in dims if re.search(r"customer", d.split(":")[-1], re.I)]
        if len(cust) != 1:
            continue
        other = [d for d in dims if d != cust[0] and not CONC_AXES.search(d)]
        if other:
            continue      # segment, product or geography share: not a share of total revenue
        bench = [m for d, m in dims.items() if re.search(r"BenchmarkAxis", d)]
        typ = [m for d, m in dims.items() if re.search(r"ByTypeAxis", d)]
        if bench and (not REV_BENCH.search(bench[0]) or NOT_REV.search(bench[0])):
            continue
        if typ and re.search(r"credit|supplier|vendor", typ[0], re.I):
            continue
        days = (pd.Timestamp(f["end"]) - pd.Timestamp(f["start"])).days
        if not 300 <= days <= 380:
            continue
        good.append((f, dims[cust[0]]))
    if not good:
        return rows
    last = max(f["end"] for f, _ in good)
    for f, member in good:
        if f["end"] != last:
            continue
        words = camel_words(member)
        nm = norm(words)
        hits = idx.find(words)
        whole = [h for h in hits if norm(words[h[0]:h[1]]) == nm]
        if whole:
            buyer, kind = whole[0][2], "named"
        elif ANON_MEMBER.search(nm):
            buyer, kind = None, "anonymous"
        elif GOV_MEMBER.search(words):
            buyer, kind = "gov:us", "named"
        elif AGG_MEMBER.search(words):
            continue
        else:
            buyer, kind = "name:" + re.sub(r"[^a-z0-9]+", "_", nm).strip("_"), "named_unresolved"
        if buyer == seller:
            continue
        v = float(f["value"])
        if not 0.005 <= v <= 1.0:
            continue
        rows.append({"buyer": buyer, "buyer_label": words, "kind": kind, "revenue_share": v, "source": "xbrl",
                     "period_end": f["end"],
                     "quote": f"XBRL fact: {f['concept']} = {v * 100:.1f}% of revenue, customer member {member}, "
                              f"period {f['start']} to {f['end']}"})
    return rows


# ------------------------------------------------------------------ text route
def _percents(s):
    out = []
    for m in PCT.finditer(s):
        v = float(m.group(1))
        if v <= 0 or v > 100:
            continue
        if BEFORE_SKIP.search(s[max(0, m.start() - 40):m.start()]):
            continue
        out.append((m.start(), v / 100.0))
    return out


def _ascending_years(s):
    ys = [int(y) for y in YEAR.findall(s)]
    return len(ys) >= 2 and ys == sorted(ys) and ys[0] != ys[-1]


def text_links(text, seller, idx, seller_names=()):
    rows = []
    for para in text.split("\n"):
        if len(para) < 30 or not PCT.search(para) or not REV.search(para):
            continue
        for s in SENT.split(para):
            if len(s) > 1500 or not PCT.search(s) or not REV.search(s) or not CUE.search(s):
                continue
            if SUPPLY.search(s) or NONE_CUE.search(s):
                continue
            cut = re.search(r"receivable", s, re.I)
            if cut and REV.search(s[:cut.start()]):
                s = s[:cut.start()]
            elif cut:
                continue
            pcts = _percents(s)
            if not pcts:
                continue
            asc = _ascending_years(s)
            pick = (lambda g: g[-1]) if asc else (lambda g: g[0])
            names = [h for h in idx.find(s) if h[2] != seller and norm(s[h[0]:h[1]]) not in seller_names]
            # de-duplicate repeated mentions of the same node
            seen, uniq = set(), []
            for h in names:
                if h[2] not in seen:
                    seen.add(h[2]); uniq.append(h)
            names = uniq
            assigned = {}
            if names:
                if re.search(r"respectively", s, re.I) and all(h[1] <= pcts[0][0] for h in names):
                    if len(names) == 1:
                        assigned = {names[0][2]: pick(pcts)[1]}
                    elif len(pcts) == len(names):
                        assigned = {h[2]: p[1] for h, p in zip(names, pcts)}
                else:
                    for k, h in enumerate(names):
                        nxt = names[k + 1][0] if k + 1 < len(names) else len(s)
                        grp = [p for p in pcts if h[1] <= p[0] < nxt]
                        if grp:
                            assigned[h[2]] = pick(grp)[1]
                    if not assigned and len(names) == 1:
                        before = [p for p in pcts if p[0] < names[0][0]]
                        if before:
                            assigned[names[0][2]] = before[-1][1]
                for h in names:
                    share = assigned.get(h[2])
                    rows.append({"buyer": h[2], "buyer_label": s[h[0]:h[1]], "kind": "named",
                                 "revenue_share": share, "source": "text", "period_end": None,
                                 "quote": s.strip()[:600]})
            else:
                for m in ANON.finditer(s):
                    grp = [p for p in pcts if p[0] > m.end()]
                    if grp:
                        lab = m.group(0).lower()
                        rows.append({"buyer": None, "buyer_label": lab, "kind": "anonymous",
                                     "revenue_share": pick(grp)[1], "source": "text", "period_end": None,
                                     "quote": s.strip()[:600]})
                        break
    return rows


def merge_filing(xb, tx):
    """One link per buyer per 10-K. XBRL wins; text adds buyers XBRL did not tag.
    Anonymous edges come from XBRL if it has any, else from text (largest share per label)."""
    out, have = [], set()
    for r in xb:
        if r["buyer"] is not None and r["buyer"] not in have:
            out.append(r); have.add(r["buyer"])
    named_text = {}
    for r in tx:
        if r["buyer"] is None or r["buyer"] in have:
            continue
        cur = named_text.get(r["buyer"])
        if cur is None or (cur["revenue_share"] is None and r["revenue_share"] is not None) or \
                (r["revenue_share"] is not None and cur["revenue_share"] is not None
                 and r["revenue_share"] > cur["revenue_share"]):
            named_text[r["buyer"]] = r
    out += list(named_text.values())
    anon_x = [r for r in xb if r["buyer"] is None]
    if anon_x:
        best = {}
        for r in anon_x:
            k = r["buyer_label"].lower()
            if k not in best or r["revenue_share"] > best[k]["revenue_share"]:
                best[k] = r
        out += list(best.values())
    else:
        best = {}
        for r in tx:
            if r["buyer"] is None:
                k = (r["buyer_label"], round(r["revenue_share"], 4))
                best.setdefault(k, r)
        out += list(best.values())
    for r in out:
        r["tier"] = "DISCLOSED" if r["revenue_share"] is not None else "STATED"
    return out


def build(ciks=None):
    idx, t2c = build_index()
    tenk = fetch_10k.todo(ciks)
    meta = {m["cik"]: m for m in json.loads((CACHE / "sec" / "entity_meta.json").read_text())}
    rows, index_rows = [], []
    for r in tenk.itertuples():
        d = fetch_10k.OUT / str(int(r.cik))
        xf, tf = d / f"{r.accession}.xbrl.json", d / f"{r.accession}.txt.gz"
        if not xf.exists() or not tf.exists():
            index_rows.append({"cik": int(r.cik), "accession": r.accession, "accepted": r.accepted, "fetched": False,
                               "n_links": 0})
            continue
        seller = f"cik:{int(r.cik)}"
        m = meta.get(int(r.cik), {})
        snames = {norm(n) for n in [m.get("name")] + list(m.get("former_names") or []) if n}
        xb = xbrl_links(json.loads(xf.read_text()).get("facts", []), seller, idx)
        tx = text_links(gzip.decompress(tf.read_bytes()).decode("utf-8", "replace"), seller, idx, snames)
        links = merge_filing(xb, tx)
        for l in links:
            l.update({"seller": seller, "seller_cik": int(r.cik), "accession": r.accession, "accepted_at": r.accepted,
                      "report_date": r.report_date})
        rows += links
        index_rows.append({"cik": int(r.cik), "accession": r.accession, "accepted": r.accepted, "fetched": True,
                           "n_links": len(links)})
    df = pd.DataFrame(rows)
    pit.check_frame(df, ["accepted_at"], what="seed links")
    df.to_parquet(OUT, index=False)
    ti = pd.DataFrame(index_rows)
    ti.to_parquet(TENK_INDEX, index=False)
    return df, ti


def load():
    df = pd.read_parquet(OUT)
    ti = pd.read_parquet(TENK_INDEX)
    pit.check_frame(df, ["accepted_at"], what="seed links")
    pit.check_frame(ti, ["accepted"], what="10-K index")
    return df, ti


class SeedGraph:
    """Point-in-time view: links(t) uses only 10-Ks accepted before day t."""

    def __init__(self, links, tenk_index):
        self.links = links
        ti = tenk_index[tenk_index["fetched"]].sort_values("accepted")
        self.ti = ti
        self.by_acc = {a: g for a, g in links.groupby("accession")}

    def latest_10k(self, t):
        t = pit.check_date(t)
        ti = self.ti[(self.ti["accepted"] < t) & (self.ti["accepted"] >= t - pd.Timedelta(days=STALE_DAYS))]
        return ti.groupby("cik").tail(1)

    def at(self, t):
        cur = self.latest_10k(t)
        parts = [self.by_acc[a] for a in cur["accession"] if a in self.by_acc]
        if not parts:
            return self.links.iloc[0:0]
        return pd.concat(parts, ignore_index=True)


def per_year(links):
    l = links.copy()
    l["year"] = pd.to_datetime(l["accepted_at"]).dt.year
    l["named"] = l["buyer"].notna()
    g = l.groupby("year").agg(links=("seller", "size"), sellers=("seller", "nunique"),
                              named=("named", "sum"), with_share=("revenue_share", lambda s: s.notna().sum()),
                              xbrl=("source", lambda s: (s == "xbrl").sum()))
    return g


if __name__ == "__main__":
    df, ti = build()
    print("10-Ks", len(ti), "fetched", int(ti["fetched"].sum()), "with links", int((ti["n_links"] > 0).sum()))
    print("links", len(df))
    print(per_year(df))
