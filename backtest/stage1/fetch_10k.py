"""Annual 10-K documents 2015-2023 for the universe: XBRL concentration facts and plain text.

Per 10-K (form 10-K / 10-K405 / 10-KT accepted 2015-01-01 .. 2023-12-31):
  cache/10k/<cik>/<accession>.xbrl.json  ConcentrationRiskPercentage facts with their dimensions
  cache/10k/<cik>/<accession>.txt.gz     the primary document as plain text (tables as ' | ')
Inline XBRL filings carry the facts in the primary document; older ones get the instance
file listed in the filing index. The HTML itself is not kept.
"""
import gzip
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from . import fetch_sec_index, pit, sec
from .config import CACHE

OUT = CACHE / "10k"
FORMS_10K = {"10-K", "10-K405", "10-KT"}
FIRST, LAST = pd.Timestamp("2015-01-01"), pd.Timestamp("2023-12-31 23:59:59")

RE_CONTEXT = re.compile(r'<(?:[\w-]+:)?context\b[^>]*?\bid\s*=\s*"([^"]+)"[^>]*>(.*?)</(?:[\w-]+:)?context>', re.S | re.I)
RE_MEMBER = re.compile(r'<(?:[\w-]+:)?explicitMember\b[^>]*?dimension\s*=\s*"([^"]+)"[^>]*>\s*([^<\s]+)\s*<', re.S | re.I)
RE_START = re.compile(r'<(?:[\w-]+:)?startDate>\s*([\d-]+)', re.I)
RE_END = re.compile(r'<(?:[\w-]+:)?(?:endDate|instant)>\s*([\d-]+)', re.I)
RE_FACT_XML = re.compile(r'<([\w-]+:ConcentrationRiskPercentage\d*)\b([^>]*?)>([^<]*)</\1>', re.S)
RE_FACT_IX = re.compile(r'<ix:nonFraction\b([^>]*?\bname\s*=\s*"[\w-]+:ConcentrationRiskPercentage\d*"[^>]*)>(.*?)</ix:nonFraction>', re.S | re.I)
RE_ATTR = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                     "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}


def _contexts(raw):
    out = {}
    for cid, body in RE_CONTEXT.findall(raw):
        s, e = RE_START.search(body), RE_END.search(body)
        out[cid] = {"dims": {d: m for d, m in RE_MEMBER.findall(body)},
                    "start": s.group(1) if s else None, "end": e.group(1) if e else None}
    return out


def _num(text, attrs):
    t = re.sub(r"<[^>]+>", "", text).strip().lower()
    fmt = attrs.get("format", "").lower()
    if "zero" in fmt or t in ("-", "—", "–"):
        v = 0.0
    elif t in WORDS:
        v = float(WORDS[t])
    else:
        if "numcommadecimal" in fmt or "num-comma-decimal" in fmt:
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
        m = re.search(r"\d+(?:\.\d+)?", t)
        if not m:
            return None
        v = float(m.group(0))
    if attrs.get("scale"):
        v *= 10 ** int(attrs["scale"])
    elif v > 1:
        v /= 100.0
    if attrs.get("sign") == "-":
        v = -v
    return v


def concentration_facts(raw, inline):
    ctx = _contexts(raw)
    facts = []
    if inline:
        for a, inner in RE_FACT_IX.findall(raw):
            attrs = dict(RE_ATTR.findall(a))
            facts.append((attrs.get("name"), attrs.get("contextRef"), _num(inner, attrs)))
    else:
        for name, a, val in RE_FACT_XML.findall(raw):
            attrs = dict(RE_ATTR.findall(a))
            try:
                v = float(val.strip())
                v = v / 100.0 if v > 1 else v
            except ValueError:
                v = None
            facts.append((name, attrs.get("contextRef"), v))
    out = []
    for name, cref, v in facts:
        c = ctx.get(cref, {})
        out.append({"concept": name, "value": v, "context": cref, "dims": c.get("dims", {}),
                    "start": c.get("start"), "end": c.get("end")})
    return out


def to_text(raw):
    s = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", " ", raw)
    s = re.sub(r"(?is)<ix:header\b.*?</ix:header\s*>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h[1-6]|table|center|font)\s*>", "\n", s)
    s = re.sub(r"(?i)</t[dh]\s*>", " | ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0​  ]+", " ", s)
    s = re.sub(r" *\n[ \n|]*\n", "\n", s)
    return s.strip()


def _decode(r):
    try:
        return r.content.decode("utf-8")
    except UnicodeDecodeError:
        return r.content.decode("latin-1")


def _instance_url(cik, acc_nd):
    j = sec.get_json(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nd}/index.json")
    if not j:
        return None
    names = [x["name"] for x in j.get("directory", {}).get("item", [])]
    xml = [n for n in names if n.lower().endswith(".xml") and not re.search(r"_(cal|def|lab|pre)\.xml$|filingsummary", n, re.I)]
    pick = [n for n in xml if n.lower().endswith("_htm.xml")] or [n for n in xml if re.search(r"\d{8}\.xml$", n)] or xml
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nd}/{pick[0]}" if pick else None


def fetch_one(row):
    cik, acc = int(row.cik), row.accession
    d = OUT / str(cik)
    d.mkdir(parents=True, exist_ok=True)
    tx, xb = d / f"{acc}.txt.gz", d / f"{acc}.xbrl.json"
    if tx.exists() and xb.exists():
        return "cached"
    acc_nd = acc.replace("-", "")
    r = sec.get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nd}/{row.primary_doc}")
    if r is None:
        xb.write_text(json.dumps({"error": "primary 404", "facts": []}))
        tx.write_bytes(gzip.compress(b""))
        return "missing"
    raw = _decode(r)
    facts, src = [], None
    if row.is_ixbrl:
        facts, src = concentration_facts(raw, inline=True), "inline"
    elif row.is_xbrl:
        u = _instance_url(cik, acc_nd)
        if u:
            ri = sec.get(u)
            if ri is not None:
                facts, src = concentration_facts(_decode(ri), inline=False), u.rsplit("/", 1)[-1]
    xb.write_text(json.dumps({"source": src, "facts": facts}))
    tx.write_bytes(gzip.compress(to_text(raw).encode("utf-8")))
    return "ok"


def todo(ciks=None):
    f = fetch_sec_index.load_filings()
    f = f[f["form"].isin(FORMS_10K) & (f["accepted"] >= FIRST) & (f["accepted"] <= LAST)]
    if ciks is not None:
        f = f[f["cik"].isin(ciks)]
    pit.check_frame(f, ["accepted"], what="10-K list")
    return f.sort_values(["cik", "accepted"])


def run(workers=8, ciks=None):
    jobs = todo(ciks)
    print("10-K filings to fetch", len(jobs), "companies", jobs["cik"].nunique(), flush=True)
    n, stat = 0, {}
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(fetch_one, r) for r in jobs.itertuples()]
        for fu in as_completed(futs):
            try:
                s = fu.result()
            except Exception as e:  # keep going; report at the end
                s = "error:" + type(e).__name__
            stat[s] = stat.get(s, 0) + 1
            n += 1
            if n % 200 == 0:
                print(n, stat, flush=True)
    print("done", stat, flush=True)


if __name__ == "__main__":
    run()
