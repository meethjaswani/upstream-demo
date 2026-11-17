"""Fama-French 3 factors and momentum, daily and monthly, from the Ken French data library.

Output cache/ff_daily.parquet and cache/ff_monthly.parquet, columns
mkt_rf, smb, hml, rf, mom as decimals. Rows from 2024-01 onwards are dropped on parse.
"""
import io
import zipfile

import pandas as pd
import requests

from . import pit
from .config import CACHE

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {
    "ff3_d": "F-F_Research_Data_Factors_daily_CSV.zip",
    "mom_d": "F-F_Momentum_Factor_daily_CSV.zip",
    "ff3_m": "F-F_Research_Data_Factors_CSV.zip",
    "mom_m": "F-F_Momentum_Factor_CSV.zip",
}


def _read(name, monthly):
    r = requests.get(BASE + name, timeout=120, headers={"User-Agent": "stage1-backtest"})
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    text = z.read(z.namelist()[0]).decode("latin-1")
    rows, header = [], None
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if header is None:
            if len(parts) > 1 and parts[0] == "" and any(p for p in parts[1:]):
                header = [p.lower().replace("-", "_") for p in parts[1:]]
            continue
        key = parts[0]
        if not key.isdigit():
            if rows:            # monthly files append an annual block after a blank/text line
                break
            continue
        if monthly and len(key) != 6:
            break
        rows.append([key] + parts[1:])
    df = pd.DataFrame(rows, columns=["key"] + header)
    df.index = pd.to_datetime(df.pop("key"), format="%Y%m" if monthly else "%Y%m%d")
    if monthly:
        df.index = df.index + pd.offsets.MonthEnd(0)
    df = df.astype(float) / 100.0
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def fetch():
    out = {}
    for freq, monthly in (("d", False), ("m", True)):
        ff = _read(FILES["ff3_" + freq], monthly)
        mom = _read(FILES["mom_" + freq], monthly)
        mom.columns = ["mom"]
        df = ff.join(mom, how="inner")
        df = df.rename(columns={"mkt_rf": "mkt_rf"})
        df = pit.clip(df)
        df = df[df.index >= pd.Timestamp("2010-01-01")]
        df.index.name = "date"
        pit.check_frame(df, index=True, what="ff_" + freq)
        df.to_parquet(CACHE / ("ff_daily.parquet" if freq == "d" else "ff_monthly.parquet"))
        out[freq] = df
    return out


def load(freq="d"):
    df = pd.read_parquet(CACHE / ("ff_daily.parquet" if freq == "d" else "ff_monthly.parquet"))
    return pit.check_frame(df, index=True, what="ff")


if __name__ == "__main__":
    o = fetch()
    for k, v in o.items():
        print(k, v.shape, v.index.min().date(), v.index.max().date(), list(v.columns))
        print(v.tail(2))
