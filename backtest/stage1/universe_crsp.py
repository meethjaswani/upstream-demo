"""CRSP arms of the universe: same interface as universe.Universe (the Yahoo arm).

- returns: CRSP daily `ret` with the delisting return folded in on the delisting date
- one primary PERMNO per company (CIK); second share classes count once
- member[t, s]: company in crsp.dsp500list on day t (spells capped at 2023-12-31); seeds come
  only from index members in both arms
- market cap: abs(prc) * shrout * 1000, summed over the company's share classes
- earnings days: Compustat rdq
- the +-2% market filter: crsp.dsi sprtrn (falls back to ^GSPC if the second export is absent)
- industry: historical GICS sub-industry on each day (comp.co_hgic)

widen=True (the widened arm) adds every common stock in the second export with a CIK, so linked
firms outside the index can be scored.
"""
import numpy as np
import pandas as pd

from . import crsp, fetch_factors, fetch_prices, pit
from .config import WRDS2


class CrspUniverse:
    def __init__(self, widen=False):
        self.widen = widen
        self.arm = "wide" if widen else "crsp"
        d = crsp.dsf()
        pm = crsp.permno_map()
        if widen:
            from . import wrds2
            d2 = wrds2.dsf()
            d2 = d2[~d2["permno"].isin(set(d["permno"]))]
            d2 = crsp.merge_delisting(d2, wrds2.delist())
            d = pd.concat([d, d2[[c for c in d.columns if c in d2.columns]]], ignore_index=True)
            pm = pd.concat([pm, self._seller_map(set(d2["permno"]) - set(pm["permno"]))], ignore_index=True)
        self.d = d
        self.pm = pm
        self.ff = fetch_factors.load("d")
        if (WRDS2 / "crsp_dsi.parquet").exists():
            from . import wrds2
            mkt = wrds2.dsi()
            self.market_source = "crsp.dsi sprtrn"
        else:
            px = fetch_prices.load()
            mkt = px[px["ticker"] == fetch_prices.INDEX].set_index("date")["adj_close"].sort_index().pct_change(fill_method=None)
            self.market_source = "^GSPC"
        cal = pd.DatetimeIndex(sorted(d["date"].unique())).intersection(self.ff.index).intersection(mkt.index)
        self.calendar = cal[(cal >= pit.DATA_START) & (cal < pit.CUTOFF)]
        self.spx_ret = mkt.reindex(self.calendar).fillna(0.0).values
        self.spells = crsp.sp500_spells().merge(self.pm[["permno", "cik"]], on="permno", how="left")
        self._primary()
        self._member()

    @staticmethod
    def _seller_map(permnos):
        """permno -> gvkey -> CIK for the second export (link with most overlap, CIK required)."""
        from . import wrds2
        c = wrds2.ccm()
        c = c[c["permno"].isin(permnos)]
        co = wrds2.company_all()[["gvkey", "cik_c", "conm", "gsector", "gsubind", "sic"]]
        c = c.merge(co, on="gvkey", how="left")
        a = c["linkdt"].clip(lower=pit.DATA_START)
        b = c["linkenddt"].clip(upper=crsp.LAST)
        c["overlap"] = (b - a).dt.days.clip(lower=0)
        c["has_cik"] = c["cik_c"].notna()
        c = c.sort_values(["permno", "has_cik", "prim", "overlap"], ascending=[True, False, False, False])
        m = c.drop_duplicates("permno").rename(columns={"cik_c": "cik"})
        return m[["permno", "gvkey", "cik", "conm", "gsector", "gsubind", "sic"]]

    def _primary(self):
        mc = self.d.groupby("permno")["mcap"].mean()
        sp = self.spells.dropna(subset=["cik"]).copy()
        sp["days"] = (sp["ending"] - sp["start"].clip(lower=pit.DATA_START)).dt.days.clip(lower=0)
        idx_days = sp.groupby("permno")["days"].sum()
        if self.widen:
            cand = self.pm.dropna(subset=["cik"])
            cand = cand[cand["permno"].isin(set(self.d["permno"]))][["permno", "cik"]].copy()
        else:
            cand = sp[["permno", "cik"]].drop_duplicates()
        cand["cik"] = cand["cik"].astype(int)
        cand["days"] = cand["permno"].map(idx_days).fillna(0)
        cand["mcap"] = cand["permno"].map(mc)
        cand = cand.sort_values(["cik", "days", "mcap"], ascending=[True, False, False])
        prim = cand.drop_duplicates("cik")
        self.sym_of_cik = {int(c): f"p{int(p)}" for c, p in zip(prim["cik"], prim["permno"])}
        self.cik_of_sym = {s: c for c, s in self.sym_of_cik.items()}
        self.symbols = sorted(self.sym_of_cik.values())
        self.col = {s: k for k, s in enumerate(self.symbols)}
        self.permnos_of_cik = cand.groupby("cik")["permno"].apply(lambda s: sorted(set(s))).to_dict()
        g = self.pm.dropna(subset=["cik"]).copy()
        g["cik"] = g["cik"].astype(int)
        self.gvkey_of_cik = {}
        self.gsubind = {}
        for c, grp in g.groupby("cik"):
            v = grp["gvkey"].dropna()
            if len(v):
                self.gvkey_of_cik[int(c)] = str(v.iloc[0])
            s = grp["gsubind"].dropna()
            if len(s):
                self.gsubind[int(c)] = str(s.iloc[0])

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
        r = crsp.rdq()[["gvkey", "rdq"]]
        g2p = crsp.ccm()[["gvkey", "permno"]]
        if self.widen:
            from . import wrds2
            r = pd.concat([r, wrds2.rdq()[["gvkey", "rdq"]]], ignore_index=True)
            g2p = pd.concat([g2p, wrds2.ccm()[["gvkey", "permno"]]], ignore_index=True)
        r = r.merge(g2p.drop_duplicates(), on="gvkey").merge(self.pm[["permno", "cik"]], on="permno").dropna(subset=["cik"])
        r = r.drop_duplicates(["cik", "rdq"])
        T, S = len(self.calendar), len(self.symbols)
        E = np.zeros((T, S), dtype=bool)
        i = self.calendar.searchsorted(r["rdq"].values)
        s = r["cik"].map(lambda x: self.col.get(self.sym_of_cik.get(int(x)), -1)).values
        ok = (i < T) & (s >= 0)
        E[i[ok], s[ok]] = True
        return E

    # -------------------------------------------------------------- historical GICS
    def gics_matrix(self):
        """T x S int codes of the GICS sub-industry each company had on each day (-1 unknown), from
        comp.co_hgic; the current Compustat code where no history is available."""
        T, S = len(self.calendar), len(self.symbols)
        G = np.full((T, S), -1, dtype=np.int32)
        codes = {}
        hist = None
        if (WRDS2 / "comp_hist_gics.parquet").exists():
            from . import wrds2
            hist = {g: grp for g, grp in wrds2.hist_gics().groupby("gvkey")}
        for s in self.symbols:
            c = self.cik_of_sym[s]
            j = self.col[s]
            gv = self.gvkey_of_cik.get(c)
            rows = hist.get(gv) if (hist is not None and gv) else None
            if rows is not None and len(rows):
                for r in rows.itertuples():
                    a = self.calendar.searchsorted(r.indfrom)
                    b = self.calendar.searchsorted(r.indthru, side="right")
                    G[a:b, j] = codes.setdefault(str(r.gsubind), len(codes))
            if (G[:, j] < 0).any() and c in self.gsubind:
                G[G[:, j] < 0, j] = codes.setdefault(self.gsubind[c], len(codes))
        self.gics_codes = codes
        return G

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
