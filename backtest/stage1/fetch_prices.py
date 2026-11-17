"""Daily prices 2014-10 to 2023-12 from Yahoo (yfinance) for every ticker that was in the
S&P 500 at any point in that window, plus the S&P 500 index (^GSPC).

Membership tickers are point in time (FB until 2022-06, then META). `ticker_map.csv`
maps an old symbol to the symbol Yahoo now keeps its history under. Companies that were
delisted or acquired are gone from Yahoo; they are counted, not filled.

Outputs
  cache/prices.parquet   date, ticker (Yahoo symbol), close (split adjusted), adj_close, volume
  cache/splits.parquet   date, ticker, ratio
  cache/price_status.csv membership ticker -> Yahoo symbol, rows, first/last date
"""
import time

import pandas as pd
import yfinance as yf

from . import fetch_membership, pit
from .config import BT, CACHE

START, END = "2014-10-01", "2024-01-01"   # yfinance end is exclusive
MAP_FILE = BT / "stage1" / "ticker_map.csv"
INDEX = "^GSPC"


def ticker_map():
    if not MAP_FILE.exists():
        return {}
    m = pd.read_csv(MAP_FILE, comment="#")
    return {r.old: (r.yahoo if isinstance(r.yahoo, str) else None) for r in m.itertuples()}


def yahoo_symbol(t, tmap):
    if t in tmap:
        return tmap[t]
    return t.replace(".", "-")


def universe_tickers():
    mem = fetch_membership.load()
    w = mem[mem["date"] >= pd.Timestamp(START)]
    # include the snapshot in force on START
    first = mem.loc[mem["date"] <= pd.Timestamp(START), "date"].max()
    w = pd.concat([mem[mem["date"] == first], w])
    return sorted(w["ticker"].unique())


def _download(symbols, tries=3):
    for k in range(tries):
        try:
            return yf.download(symbols, start=START, end=END, auto_adjust=False, actions=True,
                               group_by="ticker", progress=False, threads=True)
        except Exception as e:  # network hiccup
            print("retry", k, e)
            time.sleep(5 * (k + 1))
    raise RuntimeError("download failed")


def fetch(chunk=40, pause=15):
    """Incremental: symbols already in the cache are not downloaded again."""
    tmap = ticker_map()
    tickers = universe_tickers()
    sym_of = {t: yahoo_symbol(t, tmap) for t in tickers}
    symbols = sorted({s for s in sym_of.values() if s} | {INDEX})
    px, sp = [], []
    if (CACHE / "prices.parquet").exists():
        old = pd.read_parquet(CACHE / "prices.parquet")
        old = old[old["ticker"].isin(symbols)]
        px.append(old)
        if (CACHE / "splits.parquet").exists():
            sp.append(pd.read_parquet(CACHE / "splits.parquet"))
        have = set(old["ticker"])
        tried = CACHE / "price_tried.txt"
        done_before = set(tried.read_text().split()) if tried.exists() else set()
        symbols_todo = [s for s in symbols if s not in have and s not in done_before]
    else:
        symbols_todo = symbols
    print("to download", len(symbols_todo), flush=True)
    for i in range(0, len(symbols_todo), chunk):
        if i:
            time.sleep(pause)
        part = symbols_todo[i:i + chunk]
        d = _download(part)
        for s in part:
            if s not in d.columns.get_level_values(0):
                continue
            x = d[s].dropna(subset=["Adj Close"])
            if x.empty:
                continue
            x = pit.clip(x)
            px.append(pd.DataFrame({"date": x.index, "ticker": s, "close": x["Close"].values,
                                    "adj_close": x["Adj Close"].values, "volume": x["Volume"].values}))
            spl = x["Stock Splits"][x["Stock Splits"] > 0]
            if len(spl):
                sp.append(pd.DataFrame({"date": spl.index, "ticker": s, "ratio": spl.values}))
        print(f"{min(i + chunk, len(symbols_todo))}/{len(symbols_todo)} symbols", flush=True)
    prices = pd.concat(px, ignore_index=True).drop_duplicates(["date", "ticker"])
    prices["date"] = pd.to_datetime(prices["date"]).dt.tz_localize(None)
    pit.check_frame(prices, ["date"], what="prices")
    prices.to_parquet(CACHE / "prices.parquet", index=False)
    splits = pd.concat(sp, ignore_index=True) if sp else pd.DataFrame(columns=["date", "ticker", "ratio"])
    splits["date"] = pd.to_datetime(splits["date"])
    if splits["date"].dt.tz is not None:
        splits["date"] = splits["date"].dt.tz_localize(None)
    splits = splits.drop_duplicates(["date", "ticker"])
    splits.to_parquet(CACHE / "splits.parquet", index=False)
    g = prices.groupby("ticker")["date"].agg(["size", "min", "max"])
    st = pd.DataFrame({"member_ticker": tickers, "yahoo": [sym_of[t] for t in tickers]})
    st = st.join(g, on="yahoo")
    st.to_csv(CACHE / "price_status.csv", index=False)
    return prices, st


def load():
    df = pd.read_parquet(CACHE / "prices.parquet")
    return pit.check_frame(df, ["date"], what="prices")


if __name__ == "__main__":
    prices, st = fetch()
    print("rows", len(prices), "symbols", prices["ticker"].nunique())
    miss = st[st["size"].isna()]
    print("membership tickers", len(st), "with prices", st["size"].notna().sum(), "missing", len(miss))
    print(" ".join(miss["member_ticker"]))
