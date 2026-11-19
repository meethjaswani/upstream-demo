"""Shared evaluation panel for one data arm.

For every E2 event: CARs of all universe firms over [0,+5] and [+1,+20] (FF3 with the event-day
fit), industry-adjusted CARs, own 8-K/earnings flags in each window, controls (same GICS
sub-industry as the seed, market beta, log size) and the point-in-time seed graph of the day
before (10-Ks accepted before the event day).

Industry-adjusted CAR (amendment 8): firm CAR minus the mean CAR of firms in its GICS
sub-industry that are not linked to the shocked company (not within 6 hops downstream of the
seed, not a direct customer of the seed), excluding the seed and the firm itself.
"""
import numpy as np
import pandas as pd

from . import crsp, engine, events, fetch_sec_index, seed_graph
from .config import CACHE
from .run_step4 import own_day_flags

WINDOWS = events.CAR_WINDOWS                     # {"car_0_5": (0, 5), "car_1_20": (1, 20)}
MAX_H = 6


class Panel:
    def __init__(self, arm):
        self.arm = arm
        if arm == "crsp":
            from .universe_crsp import CrspUniverse
            U = CrspUniverse()
        else:
            from .universe import Universe
            U = Universe()
        self.U = U
        self.y, self.X = U.excess_returns()
        f = np.load(CACHE / f"ff3_fit_{arm}.npz")
        self.B, self.sig = f["B"], f["sig"]
        self.ev = pd.read_parquet(CACHE / f"events_{arm}.parquet")
        filings = fetch_sec_index.load_filings()
        self.own_any, self.own_earn = own_day_flags(U, filings, U.earnings_days() if arm == "crsp" else None)
        self.mcap = U.market_caps()
        self.logsize = np.log(self.mcap.shift(1).values)                 # day t-1
        self._industry()
        links, ti = seed_graph.load()
        self.G = seed_graph.SeedGraph(links, ti)
        self._snap = {}
        self.T, self.S = self.y.shape
        Y = self.y.values
        self.car = {w: np.full((len(self.ev), self.S), np.nan) for w in WINDOWS}
        for k, t in enumerate(self.ev["t"].values):
            for w, (k0, k1) in WINDOWS.items():
                self.car[w][k] = events.car(Y, self.X, self.B, t, k0, k1)

    def _industry(self):
        pm = crsp.permno_map().dropna(subset=["cik"])
        g = {}
        for c, s in zip(pm["cik"], pm["gsubind"]):
            if isinstance(s, str) and s:
                g.setdefault(int(c), s)
        self.gsub = np.array([g.get(self.U.cik_of_sym[s], "") for s in self.U.symbols], dtype=object)

    # ------------------------------------------------------------------ graph snapshot
    def snapshot(self, date):
        """Weights (beta = 0, tier factors fixed) of the graph known before `date`."""
        s = self._snap.get(date)
        if s is not None:
            return s
        g = self.G.at(date)
        if g.empty:
            s = {"nodes": [], "idx": {}, "W": None}
        else:
            recs = [{"seller": r.seller, "buyer": r.buyer if isinstance(r.buyer, str) else None,
                     "share": float(r.revenue_share) if pd.notna(r.revenue_share) else None, "tier": r.tier}
                    for r in g.itertuples()]
            w = engine.weights(recs, {}, beta=0.0)
            nodes = sorted({n for k in w for n in k})
            s = {"nodes": nodes, "idx": {n: i for i, n in enumerate(nodes)}, "W": engine.matrix(w, nodes)}
        self._snap[date] = s
        return s

    def node_cols(self, snap):
        """Universe column of each snapshot node (-1 if not a priced universe company)."""
        cols = np.full(len(snap["nodes"]), -1)
        for i, n in enumerate(snap["nodes"]):
            if n.startswith("cik:"):
                sym = self.U.sym_of_cik.get(int(n[4:]))
                if sym is not None:
                    cols[i] = self.U.col[sym]
        return cols

    def linked_mask(self, k):
        """Universe firms linked to event k's seed: within MAX_H hops downstream or a direct customer."""
        r = self.ev.iloc[k]
        snap = self.snapshot(r["date"])
        mask = np.zeros(self.S, dtype=bool)
        seed = f"cik:{int(r['cik'])}"
        if snap["W"] is None or seed not in snap["idx"]:
            return mask
        W = snap["W"].tocsr()
        WT = W.T.tocsr()
        cols = self.node_cols(snap)
        s0 = snap["idx"][seed]
        seen, frontier = set(), {s0}
        for _ in range(MAX_H):
            nxt = set()
            for j in frontier:
                nxt.update(W.indices[W.indptr[j]:W.indptr[j + 1]].tolist())
            nxt -= seen
            seen |= nxt
            frontier = nxt
        seen |= set(WT.indices[WT.indptr[s0]:WT.indptr[s0 + 1]].tolist())   # direct customers of the seed
        c = cols[list(seen)] if seen else np.array([], dtype=int)
        mask[c[c >= 0]] = True
        return mask

    # ------------------------------------------------------------------ industry-adjusted CAR
    def adjusted_all(self):
        """Industry-adjusted CARs for every event and window (cached on disk)."""
        f = CACHE / f"panel_adj_{self.arm}.npz"
        if f.exists():
            z = np.load(f)
            if z[list(WINDOWS)[0]].shape == (len(self.ev), self.S):
                self.adj = {w: z[w] for w in WINDOWS}
                return self.adj
        codes, uniq = pd.factorize(pd.Series(self.gsub).replace("", np.nan))
        G = len(uniq)
        has_g = codes >= 0
        self.adj = {w: np.full((len(self.ev), self.S), np.nan) for w in WINDOWS}
        for k in range(len(self.ev)):
            r = self.ev.iloc[k]
            t = int(r["t"])
            excl = self.linked_mask(k)
            excl[self.U.col[r["symbol"]]] = True
            for w in WINDOWS:
                car = self.car[w][k]
                ok = self.U.member[t] & ~excl & ~np.isnan(car) & has_g
                sums = np.bincount(codes[ok], weights=car[ok], minlength=G)
                cnt = np.bincount(codes[ok], minlength=G).astype(float)
                s = np.where(has_g, sums[np.maximum(codes, 0)], np.nan) - np.where(ok, car, 0.0)
                n = np.where(has_g, cnt[np.maximum(codes, 0)], 0.0) - ok
                with np.errstate(invalid="ignore", divide="ignore"):
                    a = car - s / n
                a[(n <= 0) | ~has_g | np.isnan(car)] = np.nan
                self.adj[w][k] = a
        np.savez_compressed(f, **self.adj)
        return self.adj

    def controls(self, k, cols):
        r = self.ev.iloc[k]
        t = int(r["t"])
        sc = self.U.col[r["symbol"]]
        same = (self.gsub[cols] == self.gsub[sc]) & (self.gsub[cols] != "")
        return same.astype(float), self.B[t, cols, 1], self.logsize[t, cols]

    def own_in_window(self, k, cols, w, which="any"):
        t = int(self.ev.iloc[k]["t"])
        k0, k1 = WINDOWS[w]
        a, b = t + k0, min(t + k1, self.T - 1)
        F = self.own_any if which == "any" else self.own_earn
        return F[a:b + 1][:, cols].any(axis=0)
