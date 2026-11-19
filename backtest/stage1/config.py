"""Paths, environment and fixed settings for the Stage 1 backtest."""
import os
from pathlib import Path

BT = Path(__file__).resolve().parents[1]          # backtest/
REPO = BT.parent                                   # repo root
CACHE = Path(os.environ.get("BACKTEST_CACHE", BT / "cache"))
RESULTS = BT / "results"
FIGURES = RESULTS / "figures"
TRIAL_LOG = RESULTS / "trial_log.csv"
GRAPH_JSON = REPO / "data" / "graph.json"

SEED = 4801                                        # global RNG seed

# Licensed WRDS export (CRSP / Compustat). Never committed; read in place.
_wrds_default = CACHE / "wrds"
if not _wrds_default.exists():
    _wrds_default = Path.home() / "upstream-v3" / "backtest" / "cache" / "wrds"
WRDS = Path(os.environ.get("BACKTEST_WRDS", _wrds_default))
WRDS2 = Path(os.environ.get("BACKTEST_WRDS2", WRDS.parent / "wrds2"))

for p in (CACHE, RESULTS, FIGURES):
    p.mkdir(parents=True, exist_ok=True)


def _dotenv_values():
    """Read KEY=VALUE pairs from the nearest .env at or above the repo root."""
    out = {}
    d = REPO
    for _ in range(6):
        f = d / ".env"
        if f.exists():
            for line in f.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break
        d = d.parent
    return out


def env(key, default=None):
    if os.environ.get(key):
        return os.environ[key]
    return _dotenv_values().get(key, default)
