"""Paths, environment and model settings for the Upstream extraction pipeline."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPE = os.path.join(ROOT, "pipeline")
CACHE = os.path.join(PIPE, "cache")
DB_PATH = os.path.join(PIPE, "db", "upstream.sqlite")
GRAPH_JSON = os.path.join(ROOT, "data", "graph.json")
SP500_CSV = os.path.join(PIPE, "data", "sp500.csv")

EXTRACTOR_VERSION = "v1"          # bump when the prompt or schema changes
FORMS = ("10-K", "10-Q", "8-K", "20-F")
EIGHT_K_ITEMS = {"1.01", "1.02", "2.01", "7.01", "8.01"}   # deals and announcements
SEC_RATE = 7.0                    # requests per second, under the SEC limit of 10
LINK_LIFETIME_DAYS = 550          # a link not seen again in a filing for this long drops out


def load_env():
    """Read KEY=VALUE lines from .env into os.environ (no dotenv dependency)."""
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()
EXTRACT_MODEL = os.environ.get("UPSTREAM_EXTRACT_MODEL", "claude-haiku-5-5")
CHECK_MODEL = os.environ.get("UPSTREAM_CHECK_MODEL", "claude-haiku-5-5")
