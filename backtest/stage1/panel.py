"""Shared evaluation panel for one data arm.

Arms: 'crsp' (index firms, 10-K graph), 'wide' (CRSP common stocks incl. firms outside the index,
10-K + Compustat customer-segment graph), 'yahoo' (index firms, Yahoo prices, 10-K graph).
Seeds are always E2 events at index firms. Linked firms: index members on the event day
('crsp', 'yahoo') or any firm with a CRSP return that day ('wide').

Per event (computed on demand): CARs of all firms over [0,+5] and [+1,+20] (FF3 with the
event-day fit), industry-adjusted CARs, own 8-K/earnings flags, controls (same GICS sub-industry
as the seed on that day, market beta, log size) and the graph known before the event day.

Industry-adjusted CAR (amendment 8): firm CAR minus the mean CAR of eligible firms in its GICS
sub-industry (historical GICS on the event day, CRSP arms) that are not linked to the shocked
company (not within 6 hops downstream of the seed, not a direct customer), the seed and the firm
itself excluded.
"""
import numpy as np
import pandas as pd

from . import crsp, engine, events, fetch_sec_index, seed_graph
from .config import CACHE
from .run_step4 import own_day_flags

WINDOWS = events.CAR_WINDOWS                     # {"car_0_5": (0, 5), "car_1_20": (1, 20)}
MAX_H = 6


class Panel:
    def __init__(self, arm, graph=None):
        self.arm = arm
        if arm in ("crsp", "wide"):
            from .universe_crsp import CrspUniverse
            U = CrspUniverse(widen=(arm == "wide"))
        else:
            from .universe import Universe
            U = Universe()
        self.U = U
        self.y, self.X = U.excess_returns()
        self.Y = self.y.values
        self.B, self.sig, _ = events.rolling_ff3(self.y, self.X)
        self.ev = pd.read_parquet(CACHE / f"events_{arm}.parquet")
        filings = fetch_sec_index.load_filings()
        self.own_any, self.own_earn = own_day_flags(U, filings, U.earnings_days() if arm != "yahoo" else None)
        self.mcap = U.market_caps()
        self.logsize = np.log(self.mcap.shift(1).values)                 # day t-1
        self.eligible = U.member if arm != "wide" else ~np.isnan(self.Y)
        self._industry()
        self.graph = graph or ("wide" if arm == "wide" else "universe")
        if self.graph == "wide":
            from . import compseg
            links, ti = compseg.load()
        else:
            links = pd.read_parquet(CACHE / "seed_links_universe.parquet")
            ti = pd.read_parquet(CACHE / "tenk_index_universe.parquet")
        self.links, self.ti = links, ti
        self.G = seed_graph.SeedGraph(links, ti)
        self._snap = {}
        self.T, self.S = self.Y.shape

    def _industry(self):
        if hasattr(self.U, "gics_matrix"):
            self.gics = self.U.gics_matrix()                             # T x S codes, -1 unknown
        else:
            pm = crsp.permno_map().dropna(subset=["cik"])
            g = {}
            for c, s in zip(pm["cik"], pm["gsubind"]):
                if isinstance(s, str) and s:
                    g.setdefault(int(c), s)
            codes, row = {}, []
            for s in self.U.symbols:
                v = g.get(self.U.cik_of_sym[s])
                row.append(codes.setdefault(v, len(codes)) if v else -1)
            self.gics = np.tile(np.array(row, dtype=np.int32), (len(self.U.calendar), 1))

    def gsub_at(self, t):
        return self.gics[t]

    # ------------------------------------------------------------------ graph snapshot
    def snapshot(self, date):
        """Weights (beta = 0, tier factors fixed) of the graph known before `date`."""
        s = self._snap.get(date)
        if s is not None:
            return s
        g = self.G.at(date)
        if g.empty:
            s = {"nodes": [], "idx": {}, "W": None, "links": g}
        else:
            recs = [{"seller": r.seller, "buyer": r.buyer if isinstance(r.buyer, str) else None,
                     "share": float(r.revenue_share) if pd.notna(r.revenue_share) else None, "tier": r.tier}
                    for r in g.itertuples()]
            w = engine.weights(recs, {}, beta=0.0)
            nodes = sorted({n for k in w for n in k})
            s = {"nodes": nodes, "idx": {n: i for i, n in enumerate(nodes)}, "W": engine.matrix(w, nodes), "links": g}
        self._snap[date] = s
        return s

    def node_cols(self, snap):
        """Universe column of each snapshot node (-1 if not a priced company)."""
        cols = np.full(len(snap["nodes"]), -1)
        for i, n in enumerate(snap["nodes"]):
            if n.startswith("cik:"):
                sym = self.U.sym_of_cik.get(int(n[4:]))
                if sym is not None:
                    cols[i] = self.U.col[sym]
        return cols

    def linked_mask(self, k):
        """Firms linked to event k's seed: within MAX_H hops downstream or a direct customer."""
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

    # ------------------------------------------------------------------ CARs on demand
    def car_vec(self, k):
        t = int(self.ev.iloc[k]["t"])
        return {w: events.car(self.Y, self.X, self.B, t, k0, k1) for w, (k0, k1) in WINDOWS.items()}

    def adj_vec(self, k, car=None):
        """Industry-adjusted CARs (all firms) for event k."""
        r = self.ev.iloc[k]
        t = int(r["t"])
        car = car or self.car_vec(k)
        codes = self.gsub_at(t)
        G = int(codes.max()) + 1 if codes.max() >= 0 else 1
        has_g = codes >= 0
        excl = self.linked_mask(k)
        excl[self.U.col[r["symbol"]]] = True
        out = {}
        for w in WINDOWS:
            c = car[w]
            ok = self.eligible[t] & ~excl & ~np.isnan(c) & has_g
            sums = np.bincount(codes[ok], weights=c[ok], minlength=G)
            cnt = np.bincount(codes[ok], minlength=G).astype(float)
            s = np.where(has_g, sums[np.maximum(codes, 0)], np.nan) - np.where(ok, c, 0.0)
            n = np.where(has_g, cnt[np.maximum(codes, 0)], 0.0) - ok
            with np.errstate(invalid="ignore", divide="ignore"):
                a = c - s / n
            a[(n <= 0) | ~has_g | np.isnan(c)] = np.nan
            out[w] = a
        return out

    def controls(self, k, cols):
        r = self.ev.iloc[k]
        t = int(r["t"])
        sc = self.U.col[r["symbol"]]
        g = self.gsub_at(t)
        same = (g[cols] == g[sc]) & (g[cols] >= 0)
        return same.astype(float), self.B[t, cols, 1], self.logsize[t, cols]

    def own_in_window(self, k, cols, w, which="any"):
        t = int(self.ev.iloc[k]["t"])
        k0, k1 = WINDOWS[w]
        a, b = t + k0, min(t + k1, self.T - 1)
        F = self.own_any if which == "any" else self.own_earn
        return F[a:b + 1][:, cols].any(axis=0)
