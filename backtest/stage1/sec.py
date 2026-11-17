"""Small SEC EDGAR client: User-Agent from SEC_USER_AGENT, global rate limit below
10 requests per second shared across threads, retries with backoff on 429/5xx."""
import threading
import time

import requests

from .config import env

MAX_RPS = 8.0


class _Limiter:
    def __init__(self, rps):
        self.gap = 1.0 / rps
        self.lock = threading.Lock()
        self.next = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        if t > now:
            time.sleep(t - now)


_limiter = _Limiter(MAX_RPS)
_local = threading.local()


def user_agent():
    ua = env("SEC_USER_AGENT")
    if not ua:
        raise RuntimeError("SEC_USER_AGENT is not set (add it to .env)")
    return ua


def _session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"})
        _local.s = s
    return s


def get(url, tries=6, timeout=60):
    """GET with rate limit; returns the Response, or None on 404."""
    for k in range(tries):
        _limiter.wait()
        try:
            r = _session().get(url, timeout=timeout)
        except requests.RequestException:
            time.sleep(2 ** k)
            continue
        if r.status_code == 404:
            return None
        if r.status_code in (403, 429) or r.status_code >= 500:
            time.sleep(min(60, 2 ** (k + 1)))
            continue
        r.raise_for_status()
        return r
    raise RuntimeError(f"SEC fetch failed after {tries} tries: {url}")


def get_json(url):
    r = get(url)
    return None if r is None else r.json()
