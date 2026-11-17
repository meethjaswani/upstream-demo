"""Point-in-time rules and the closed-period guard.

Nothing dated 2024-01-01 or later may be loaded, plotted or scored. Fetchers drop
such rows before anything is written to the cache, and every loader calls
`check_*` on what it reads, so a stray row raises ClosedPeriodError.
"""
import pandas as pd

CUTOFF = pd.Timestamp("2024-01-01")
DATA_START = pd.Timestamp("2014-10-01")
PERIODS = {
    "fit": (pd.Timestamp("2016-01-01"), pd.Timestamp("2021-12-31")),
    "choose": (pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31")),
}


class ClosedPeriodError(RuntimeError):
    """Raised when anything from 2024-01 onwards is touched."""


def _naive(ts):
    ts = pd.to_datetime(ts)
    if isinstance(ts, pd.Timestamp):
        return ts.tz_convert(None) if ts.tzinfo is not None else ts
    if getattr(ts, "tz", None) is not None:
        return ts.tz_convert(None)
    return ts


def check_date(d, what="date"):
    ts = _naive(d)
    if pd.notna(ts) and ts >= CUTOFF:
        raise ClosedPeriodError(f"{what} {ts.date()} is in the closed period (>= {CUTOFF.date()})")
    return ts


def check_dates(dates, what="data"):
    s = pd.Series(pd.to_datetime(dates))
    if s.dt.tz is not None:
        s = s.dt.tz_convert(None)
    bad = s[s >= CUTOFF]
    if len(bad):
        raise ClosedPeriodError(f"{what}: {len(bad)} rows on/after {CUTOFF.date()} (first {bad.iloc[0].date()})")
    return dates


def check_frame(df, cols=(), index=False, what="frame"):
    if index:
        check_dates(df.index.get_level_values(0) if isinstance(df.index, pd.MultiIndex) else df.index, what)
    for c in cols:
        check_dates(df[c].dropna(), f"{what}.{c}")
    return df


def clip(df, col=None):
    """Ingestion only: drop rows on/after the cutoff before they reach the cache."""
    if col is None:
        idx = pd.to_datetime(df.index)
        return df[idx < CUTOFF]
    return df[pd.to_datetime(df[col]) < CUTOFF]


def period(name):
    if name not in PERIODS:
        raise ClosedPeriodError(f"period '{name}' is not open; only {list(PERIODS)} may be used")
    return PERIODS[name]
