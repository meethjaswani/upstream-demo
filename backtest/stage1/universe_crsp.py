"""CRSP arm of the universe: same interface as universe.Universe (the Yahoo arm).

- returns: CRSP daily `ret` with the delisting return folded in on the delisting date
- one primary PERMNO per company (CIK); second share classes count once
- member[t, s]: company in crsp.dsp500list on day t (spells capped at 2023-12-31)
- market cap: abs(prc) * shrout * 1000, summed over the company's share classes
- earnings days: Compustat rdq
- the +-2% market filter uses the S&P 500 index level (^GSPC); the export has no CRSP index file
"""
import numpy as np
import pandas as pd

from . import crsp, fetch_factors, fetch_prices, pit


class CrspUniverse:
    arm = "crsp"

    def __init__(self):
        self.d = crsp.dsf()
        self.ff = fetch_factors.load("d")
        px = fetch_prices.load()
        spx = px[px["ticker"] == fetch_prices.INDEX].set_index("date")["adj_close"].sort_index()
        cal = pd.DatetimeIndex(sorted(self.d["date"].unique())).intersection(self.ff.index).intersection(spx.index)
        self.calendar = cal[(cal >= pit.DATA_START) & (cal < pit.CUTOFF)]
        self.spx_ret = spx.pct_change(fill_method=None).reindex(self.calendar).fillna(0.0).values
        self.pm = crsp.permno_map()
        self.spells = crsp.sp500_spells().merge(self.pm[["permno", "cik"]], on="permno", how="left")
        self._primary()
        self._member()

    def _primary(self):
        sp = self.spells.dropna(subset=["cik"]).copy()
        sp["cik"] = sp["cik"].astype(int)
        a = sp["start"].clip(lower=pit.DATA_START)
        sp["days"] = (sp["ending"] - a).dt.days.clip(lower=0)
        mc = self.d.groupby("permno")["mcap"].mean()
        sp["mcap"] = sp["permno"].map(mc)
        score = sp.groupby(["cik", "permno"]).agg(days=("days", "sum"), mcap=("mcap", "first")).reset_index()
        score = score.sort_values(["cik", "days", "mcap"], ascending=[True, False, False])
        prim = score.drop_duplicates("cik")
        self.sym_of_cik = {int(c): f"p{int(p)}" for c, p in zip(prim["cik"], prim["permno"])}
        self.cik_of_sym = {s: c for c, s in self.sym_of_cik.items()}
        self.symbols = sorted(self.sym_of_cik.values())
        self.col = {s: k for k, s in enumerate(self.symbols)}
        self.permnos_of_cik = sp.groupby("cik")["permno"].apply(lambda s: sorted(set(s))).to_dict()
        self.gsubind = {}
        for c, g in self.pm.dropna(subset=["cik"]).groupby("cik"):
            v = g["gsubind"].dropna()
            if len(v):
                self.gsubind[int(c)] = str(v.iloc[0])

    def _member(self):
        T, S = len(self.calendar), len(self.symbols)
        M = np.zeros((T, S), dtype=bool)
        cal = self.calendar
        self.span_rows = []
        for r in self.spells.itertuples():
            a, b = cal.searchsorted(r.start), cal.searchsorted(r.ending, side="right")
            col = self.col.get(self.sym_of_cik.get(int(r.cik))) if pd.notna(r.cik) else None
            if col is not None:
                M[a:b, col] = True
            self.span_rows.append((r.permno, a, b, col))
        self.member = M
        self.rejected_spans = []

    # -------------------------------------------------------------- returns
    def excess_returns(self):
        prim = {int(s[1:]) for s in self.symbols}
        d = self.d[self.d["permno"].isin(prim)]
        r = d.pivot_table(index="date", columns="permno", values="ret_d", aggfunc="last")
        r.columns = [f"p{c}" for c in r.columns]
        r = r.reindex(index=self.calendar, columns=self.symbols)
        f = self.ff.loc[self.calendar]
        y = r.sub(f["rf"], axis=0)
        X = np.column_stack([np.ones(len(f)), f["mkt_rf"].values, f["smb"].values, f["hml"].values])
        pit.check_frame(y, index=True, what="crsp returns")
        return y, X

    def market_caps(self):
        cap = self.d.pivot_table(index="date", columns="permno", values="mcap", aggfunc="last").reindex(self.calendar)
        out = pd.DataFrame(np.nan, index=self.calendar, columns=self.symbols)
        for c, s in self.sym_of_cik.items():
            cols = [p for p in self.permnos_of_cik.get(c, []) if p in cap.columns]
            if cols:
                out[s] = cap[cols].sum(axis=1, min_count=1).values
        return out

    # -------------------------------------------------------------- earnings (Compustat rdq)
    def earnings_days(self):
        """T x S bool: Compustat rdq falls on day t (rdq mapped to the trading day on/after it)."""
        r = crsp.rdq()
        c = crsp.ccm()
        g2p = c[["gvkey", "permno"]].drop_duplicates()
        r = r.merge(g2p, on="gvkey").merge(self.pm[["permno", "cik"]], on="permno").dropna(subset=["cik"])
        r = r.drop_duplicates(["cik", "rdq"])
        T, S = len(self.calendar), len(self.symbols)
        E = np.zeros((T, S), dtype=bool)
        i = self.calendar.searchsorted(r["rdq"].values)
        s = r["cik"].map(lambda x: self.col.get(self.sym_of_cik.get(int(x)), -1)).values
        ok = (i < T) & (s >= 0)
        E[i[ok], s[ok]] = True
        return E

    # -------------------------------------------------------------- survivorship
    def survivorship(self, start="2016-01-01"):
        y, _ = self.excess_returns()
        has = ~np.isnan(y.values)
        t0 = self.calendar.searchsorted(pd.Timestamp(start))
        days = priced = 0
        no_cik = 0
        for p, a, b, col in self.span_rows:
            a = max(a, t0)
            if b <= a:
                continue
            days += b - a
            if col is None:
                no_cik += b - a
            else:
                priced += int(has[a:b, col].sum())
        return {"member_permnos": int(self.spells["permno"].nunique()),
                "companies": len(self.symbols),
                "share_member_days_without_returns": round(1 - priced / days, 4),
                "member_days_without_cik": int(no_cik)}
