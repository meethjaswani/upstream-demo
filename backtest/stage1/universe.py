"""Universe objects shared by events, graph and metrics.

- calendar: trading days with S&P 500 and FF factor data, 2014-10 .. 2023-12
- one primary Yahoo symbol per CIK (GOOGL/GOOG, FOXA/FOX, NWSA/NWS, ... count once)
- member[t, s]: CIK s was in the S&P 500 on day t (point in time)
- market cap on day t: split-adjusted close x shares outstanding from the latest filing
  accepted before t, converted to the same split basis (see `post_2023_factor`)
"""
import json

import numpy as np
import pandas as pd

from . import fetch_factors, fetch_membership, fetch_prices, pit
from .config import CACHE


class Universe:
    def __init__(self):
        self.prices = fetch_prices.load()
        self.ff = fetch_factors.load("d")
        self.mem = fetch_membership.load()
        ent = pd.read_csv(CACHE / "entities.csv")
        self.ent = ent
        spx = self.prices[self.prices["ticker"] == fetch_prices.INDEX].set_index("date")["adj_close"].sort_index()
        cal = spx.index.intersection(self.ff.index)
        cal = cal[(cal >= pit.DATA_START) & (cal < pit.CUTOFF)]
        self.calendar = cal
        self.spx_ret = spx.pct_change(fill_method=None).reindex(cal).fillna(0.0).values
        self._membership_days()
        self._primary_symbols()
        self._member_matrix()

    # -------------------------------------------------------------- symbols
    def _membership_days(self):
        m = self.mem.sort_values("date")
        dates = m["date"].drop_duplicates().sort_values().reset_index(drop=True)
        # each change row is in force until the next one
        nxt = dict(zip(dates, list(dates[1:]) + [pit.CUTOFF]))
        m = m.assign(until=m["date"].map(nxt))
        self.mem_spans = m[m["until"] > pit.DATA_START]

    def _primary_symbols(self):
        ent = self.ent.dropna(subset=["cik"]).copy()
        ent["cik"] = ent["cik"].astype(int)
        have = set(self.prices["ticker"])
        ent = ent[ent["yahoo"].isin(have)]
        spans = self.mem_spans.merge(ent[["member_ticker", "cik", "yahoo"]], left_on="ticker",
                                     right_on="member_ticker")
        spans["days"] = (spans["until"].clip(upper=pit.CUTOFF) - spans["date"].clip(lower=pit.DATA_START)).dt.days
        score = spans.groupby(["cik", "yahoo"])["days"].sum().reset_index()
        score = score.sort_values(["cik", "days", "yahoo"], ascending=[True, False, True])
        prim = score.drop_duplicates("cik")
        self.sym_of_cik = dict(zip(prim["cik"], prim["yahoo"]))
        self.cik_of_sym = {s: c for c, s in self.sym_of_cik.items()}
        self.symbols = sorted(self.sym_of_cik.values())
        self.col = {s: k for k, s in enumerate(self.symbols)}
        self.ticker_cik = dict(zip(ent["member_ticker"], ent["cik"]))

    def _member_matrix(self):
        T, S = len(self.calendar), len(self.symbols)
        M = np.zeros((T, S), dtype=bool)
        cal = self.calendar
        for r in self.mem_spans.itertuples():
            c = self.ticker_cik.get(r.ticker)
            if c is None or c not in self.sym_of_cik:
                continue
            a, b = cal.searchsorted(r.date), cal.searchsorted(r.until)
            M[a:b, self.col[self.sym_of_cik[c]]] = True
        self.member = M

    def survivorship(self):
        """Share of index member-days (2016-2023) whose company has no Yahoo prices."""
        sp = self.mem_spans
        rows = []
        for r in sp.itertuples():
            a = max(r.date, pd.Timestamp("2016-01-01"))
            b = min(r.until, pit.CUTOFF)
            if b <= a:
                continue
            ok = r.ticker in self.ticker_cik and self.ticker_cik[r.ticker] in self.sym_of_cik
            dup = r.ticker in ("DISCK", "CMCSK")
            rows.append({"ticker": r.ticker, "days": (b - a).days, "priced": ok, "dup_class": dup})
        d = pd.DataFrame(rows)
        d = d[~d["dup_class"]]
        tick = d.groupby("ticker").agg(days=("days", "sum"), priced=("priced", "max"))
        return {"member_tickers_2016_2023": int(len(tick)),
                "tickers_without_prices": int((~tick["priced"]).sum()),
                "share_tickers_without_prices": float((~tick["priced"]).mean()),
                "share_member_days_without_prices": float(d.loc[~d["priced"], "days"].sum() / d["days"].sum()),
                "missing": sorted(tick.index[~tick["priced"]])}

    # -------------------------------------------------------------- returns
    def excess_returns(self):
        """y: excess returns (calendar x symbols); X: [1, mkt_rf, smb, hml] on the calendar."""
        px = self.prices.pivot(index="date", columns="ticker", values="adj_close")
        px = px.reindex(index=self.calendar, columns=self.symbols)
        f = self.ff.loc[self.calendar]
        y = px.pct_change(fill_method=None).sub(f["rf"], axis=0)
        X = np.column_stack([np.ones(len(f)), f["mkt_rf"].values, f["smb"].values, f["hml"].values])
        pit.check_frame(y, index=True, what="returns")
        return y, X

    # -------------------------------------------------------------- market cap
    def market_caps(self):
        """DataFrame (calendar x symbols) of market cap in USD, point in time."""
        sh = pd.read_parquet(CACHE / "sec" / "shares.parquet")
        pit.check_frame(sh, ["filed"], what="shares")
        filings = pd.read_parquet(CACHE / "sec" / "filings.parquet")[["accession", "accepted"]]
        sh = sh.merge(filings, left_on="accn", right_on="accession", how="left")
        sh["known"] = sh["accepted"].fillna(sh["filed"] + pd.Timedelta(hours=17, minutes=30))
        close = self.prices.pivot(index="date", columns="ticker", values="close").reindex(self.calendar)
        splits = pd.read_parquet(CACHE / "splits.parquet")
        out = pd.DataFrame(np.nan, index=self.calendar, columns=self.symbols)
        pref = {"EntityCommonStockSharesOutstanding": 0, "CommonStockSharesOutstanding": 1,
                "WeightedAverageNumberOfSharesOutstandingBasic": 2,
                "WeightedAverageNumberOfDilutedSharesOutstanding": 3}
        self.post_factor = {}
        for s in self.symbols:
            c = self.cik_of_sym[s]
            x = sh[(sh["cik"] == c) & sh["concept"].isin(pref) & (sh["val"] > 0)].copy()
            if x.empty or s not in close:
                continue
            x["p"] = x["concept"].map(pref)
            x = x.sort_values(["known", "p"]).drop_duplicates("known", keep="first")
            spl = splits[splits["ticker"] == s]
            # in-window split factor after the share count's as-of date
            def f_after(d):
                return float(np.prod(spl.loc[spl["date"] > d, "ratio"])) if len(spl) else 1.0
            x["adj_shares"] = [v * f_after(e) for v, e in zip(x["val"], x["end"].fillna(x["known"]))]
            ser = pd.Series(x["adj_shares"].values, index=x["known"].values).sort_index()
            ser = ser[~ser.index.duplicated(keep="last")]
            idx = ser.index.searchsorted(self.calendar, side="left") - 1      # known strictly before day t
            vals = np.where(idx >= 0, ser.values[np.maximum(idx, 0)], np.nan)
            pf = self.post_2023_factor(s, sh[(sh["cik"] == c)], close[s], spl)
            self.post_factor[s] = pf
            out[s] = close[s].values * vals * pf
        return out

    @staticmethod
    def post_2023_factor(sym, facts, close, spl):
        """Yahoo's split-adjusted close also reflects splits after 2023, which we may not load.
        Infer that constant factor from data filed before 2024: the reported public float (USD,
        raw basis) divided by split-adjusted close x shares on the float date. Snap to a
        common split ratio; 1 if the evidence is weak."""
        pfl = facts[facts["concept"] == "EntityPublicFloat"].dropna(subset=["end"])
        shs = facts[facts["concept"] == "EntityCommonStockSharesOutstanding"].dropna(subset=["end"])
        if pfl.empty or shs.empty:
            return 1.0
        ratios = []
        for r in pfl.sort_values("end").tail(4).itertuples():
            px = close[:r.end].dropna()
            sh0 = shs[shs["end"] <= r.end + pd.Timedelta(days=400)].sort_values("end")
            sh0 = sh0[sh0["end"] >= r.end]
            if px.empty or sh0.empty:
                continue
            f_in_sh = float(np.prod(spl.loc[spl["date"] > sh0.iloc[0]["end"], "ratio"])) if len(spl) else 1.0
            raw_mcap_est = px.iloc[-1] * sh0.iloc[0]["val"] * f_in_sh
            if raw_mcap_est > 0:
                ratios.append(r.val / raw_mcap_est)
        if not ratios:
            return 1.0
        r = float(np.median(ratios))
        if r < 1.6:
            return 1.0
        cands = np.array([2, 3, 4, 5, 6, 8, 10, 15, 20, 25, 30, 40, 50])
        # float <= market cap, so the factor is at least r; take the nearest common ratio
        k = cands[np.argmin(np.abs(np.log(cands / (r / 0.92))))]
        return float(k)
