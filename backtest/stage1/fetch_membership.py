"""Historical S&P 500 membership (fja05680/sp500, 'Updated' file).

Output cache/membership.parquet: one row per (change date, ticker), dates < 2024-01-01.
The file lists the full constituent set on every change date; membership on day t is
the last row dated <= t. Tickers of companies that later left carry a '-YYYYMM' suffix
in the source; `base` strips it.
"""
import io
import re

import pandas as pd
import requests

from . import pit
from .config import CACHE

URL = "https://raw.githubusercontent.com/fja05680/sp500/master/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
OUT = CACHE / "membership.parquet"


def base_ticker(t):
    return re.sub(r"-\d{6}$", "", t.strip())


def fetch():
    r = requests.get(URL, timeout=60, headers={"User-Agent": "stage1-backtest"})
    r.raise_for_status()
    raw = pd.read_csv(io.StringIO(r.text))
    raw["date"] = pd.to_datetime(raw["date"])
    raw = pit.clip(raw, "date")
    raw = raw[raw["date"] >= pd.Timestamp("2013-01-01")]
    rows = [(d, t.strip()) for d, ts in zip(raw["date"], raw["tickers"]) for t in ts.split(",") if t.strip()]
    df = pd.DataFrame(rows, columns=["date", "raw_ticker"])
    df["ticker"] = df["raw_ticker"].map(base_ticker)
    df = df.drop_duplicates(["date", "ticker"]).sort_values(["date", "ticker"]).reset_index(drop=True)
    pit.check_frame(df, ["date"], what="membership")
    df.to_parquet(OUT, index=False)
    return df


def load():
    df = pd.read_parquet(OUT)
    return pit.check_frame(df, ["date"], what="membership")


def members_on(df, day):
    """Set of base tickers in the index on `day` (last change row on or before it)."""
    day = pit.check_date(day)
    dates = df["date"].drop_duplicates().sort_values()
    d = dates[dates <= day]
    if d.empty:
        return set()
    return set(df.loc[df["date"] == d.iloc[-1], "ticker"])


if __name__ == "__main__":
    df = fetch()
    print("change dates", df["date"].nunique(), "from", df["date"].min().date(), "to", df["date"].max().date())
    w = df[(df["date"] >= "2014-10-01")]
    print("unique tickers 2014-10..2023-12", w["ticker"].nunique())
    print("members per date: min", w.groupby("date").size().min(), "max", w.groupby("date").size().max())
