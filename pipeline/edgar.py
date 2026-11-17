"""Step 1, ingest: list and download filings from SEC EDGAR, keeping the acceptance time."""
import json, os, threading, time
import requests
from . import config

_lock, _next = threading.Lock(), [0.0]
_session = None


def _sess():
    global _session
    if _session is None:
        ua = os.environ.get("SEC_USER_AGENT")
        if not ua:
            raise RuntimeError("Set SEC_USER_AGENT in .env (name and contact email). The SEC requires it.")
        _session = requests.Session()
        _session.headers.update({"User-Agent": ua, "Accept-Encoding": "gzip, deflate"})
    return _session


def get(url, as_json=False):
    """Rate limited GET with retries."""
    for attempt in range(6):
        with _lock:
            now = time.time()
            wait = _next[0] - now
            _next[0] = max(now, _next[0]) + 1.0 / config.SEC_RATE
        if wait > 0:
            time.sleep(wait)
        try:
            r = _sess().get(url, timeout=60)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 200:
            return r.json() if as_json else r.text
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"GET {url} -> {r.status_code}")
    raise RuntimeError(f"GET {url} failed after retries")


def _rows(block):
    keys = ("accessionNumber", "form", "filingDate", "acceptanceDateTime", "primaryDocument", "items")
    n = len(block.get("accessionNumber", []))
    return [{k: (block.get(k) or [""] * n)[i] for k in keys} for i in range(n)]


def list_filings(cik, since="2015-01-01", forms=config.FORMS):
    """Every filing of the wanted forms since a date, oldest first."""
    cik10 = str(int(cik)).zfill(10)
    sub = get(f"https://data.sec.gov/submissions/CIK{cik10}.json", as_json=True)
    rows = _rows(sub["filings"]["recent"])
    for extra in sub["filings"].get("files", []):
        if extra.get("filingTo", "9999") >= since:
            rows += _rows(get("https://data.sec.gov/submissions/" + extra["name"], as_json=True))
    out = []
    for r in rows:
        if r["form"] not in forms or r["filingDate"] < since:
            continue
        if r["form"] == "8-K" and not (set(r["items"].split(",")) & config.EIGHT_K_ITEMS):
            continue
        acc = r["accessionNumber"].replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}"
        out.append({"cik": int(cik), "accession_no": r["accessionNumber"], "form": r["form"],
                    "filed": r["filingDate"], "accepted_at": r["acceptanceDateTime"],
                    "items": r["items"], "base": base, "url": f"{base}/{r['primaryDocument']}"})
    return sorted(out, key=lambda f: f["accepted_at"])


def download(filing):
    """Return [(doc_kind, url, html)] for a filing. 8-Ks also bring their EX-99 exhibits. Cached on disk."""
    d = os.path.join(config.CACHE, "filings", str(filing["cik"]), filing["accession_no"])
    os.makedirs(d, exist_ok=True)
    docs = [("body", filing["url"])]
    if filing["form"] == "8-K":
        idx_path = os.path.join(d, "index.json")
        if os.path.exists(idx_path):
            idx = json.load(open(idx_path))
        else:
            idx = get(filing["base"] + "/index.json", as_json=True)
            json.dump(idx, open(idx_path, "w"))
        for it in idx.get("directory", {}).get("item", []):
            name = it.get("name", "")
            low = name.lower().replace("-", "").replace("_", "")
            if "ex99" in low and low.endswith((".htm", ".html")):
                docs.append(("press_release", f"{filing['base']}/{name}"))
    out = []
    for kind, url in docs:
        path = os.path.join(d, url.rsplit("/", 1)[1])
        if os.path.exists(path):
            html = open(path, encoding="utf-8", errors="replace").read()
        else:
            html = get(url)
            open(path, "w", encoding="utf-8").write(html)
        out.append((kind, url, html))
    return out
