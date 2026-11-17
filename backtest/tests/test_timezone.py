"""Amendment 1: event day from the SEC acceptance time.

Apple's revenue guidance letter (8-K, 2 Jan 2019) went out after the close, so its event
day must be 3 Jan 2019. The first test uses the acceptance time as EDGAR's filing index
shows it (Eastern time); the second uses the value stored in the cache, if present.
"""
import pandas as pd
import pytest

from stage1 import events
from stage1.config import CACHE

CAL = pd.bdate_range("2018-12-24", "2019-01-15").drop(pd.to_datetime(["2018-12-25", "2019-01-01"]))


def test_after_close_filing_moves_to_next_trading_day():
    e = events.effective_day_index([pd.Timestamp("2019-01-02 16:31:00")], CAL)[0]
    assert CAL[e] == pd.Timestamp("2019-01-03")


def test_apple_8k_2019_01_02_event_day_from_cache():
    f = CACHE / "sec" / "filings.parquet"
    if not f.exists():
        pytest.skip("SEC filings not cached")
    df = pd.read_parquet(f)
    a = df[(df["cik"] == 320193) & (df["form"] == "8-K") & (df["filing_date"] == "2019-01-02")]
    assert len(a) >= 1
    e = events.effective_day_index(a["accepted"], CAL)
    assert all(CAL[i] == pd.Timestamp("2019-01-03") for i in e)
