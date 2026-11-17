"""One trial log for every run (rule 3): timestamp, variant, parameters, period, metrics.
Bad runs are logged too. Rows are only ever appended."""
import csv
import json
from datetime import datetime, timezone

from .config import TRIAL_LOG

FIELDS = ["timestamp", "variant", "parameters", "period", "metrics", "note"]


def log(variant, parameters, period, metrics, note=""):
    new = not TRIAL_LOG.exists()
    with open(TRIAL_LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variant": variant,
                    "parameters": json.dumps(parameters, sort_keys=True), "period": period,
                    "metrics": json.dumps(metrics, sort_keys=True, default=str), "note": note})
