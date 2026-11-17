"""Demand-shock propagation engine.

Weight from buyer j to seller i (row j, column i of W):
    r_ij                                              if the seller disclosed the share
    (1 - R_i) * u_ji / (1 + sum_k u_ki)               otherwise, k over i's undisclosed buyers
    u_ji = (M_j / M_i) ** beta,  M = market cap,  R_i = sum of i's disclosed shares
times a confidence factor for the link's tier.

Propagation (x = loss as a fraction, seed x0):
    M1 linear cascade   x(h+1) = min(1, x0 + delta * W^T x(h)), up to H hops or change < tol
    M2 DebtRank         as M1, but each node passes its loss on once (the step after it is hit)
    M3 independent cascade: a newly hit node j hits seller i with probability W[j, i];
                        a hit passes delta times the parent's loss; mean over n_runs runs.
"""
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp

TIERS = {"DISCLOSED": 1.0, "STATED": 0.9, "ANNOUNCED": 0.8, "INFERRED": 0.5}
TOL = 1e-3


@dataclass
class Params:
    beta: float = 1.0
    delta: float = 0.6
    H: int = 4
    tiers: dict = field(default_factory=lambda: dict(TIERS))
    n_runs: int = 10_000


def weights(links, mcap, beta, tiers=TIERS):
    """links: iterable of dicts with seller, buyer, share (None if undisclosed), tier.
    Buyers that are None (anonymous customers) only count toward R_i.
    mcap: dict node -> market cap (missing or <= 0 means unknown; then u = 1).
    Returns {(buyer, seller): weight}."""
    by_seller = {}
    for l in links:
        by_seller.setdefault(l["seller"], []).append(l)
    out = {}
    for i, ls in by_seller.items():
        R = sum(l["share"] for l in ls if l["share"] is not None)
        R = min(R, 1.0)
        und = [l for l in ls if l["share"] is None and l["buyer"] is not None]
        Mi = mcap.get(i)
        u = {}
        for l in und:
            Mj = mcap.get(l["buyer"])
            if Mi and Mj and Mi > 0 and Mj > 0:
                u[l["buyer"]] = (Mj / Mi) ** beta
            else:
                u[l["buyer"]] = 1.0
        denom = 1.0 + sum(u.values())
        for l in ls:
            j = l["buyer"]
            if j is None or j == i:
                continue
            c = tiers.get(l["tier"], 0.0)
            w = l["share"] if l["share"] is not None else (1.0 - R) * u[j] / denom
            w = max(0.0, min(1.0, w)) * c
            key = (j, i)
            out[key] = max(out.get(key, 0.0), w)   # duplicate links: keep the strongest
    return out


def matrix(wdict, nodes):
    """Sparse W with W[j, i] = weight buyer j -> seller i over the node order given."""
    idx = {n: k for k, n in enumerate(nodes)}
    rows, cols, vals = [], [], []
    for (j, i), w in wdict.items():
        if j in idx and i in idx and w > 0:
            rows.append(idx[j]); cols.append(idx[i]); vals.append(w)
    n = len(nodes)
    return sp.csr_matrix((vals, (rows, cols)), shape=(n, n))


def linear(W, x0, delta, H, tol=TOL):
    WT = W.T.tocsr()
    x = x0.copy()
    for _ in range(H):
        nx = np.minimum(1.0, x0 + delta * (WT @ x))
        done = np.max(np.abs(nx - x)) < tol
        x = nx
        if done:
            break
    return x


def debtrank(W, x0, delta, H, tol=TOL):
    WT = W.T.tocsr()
    h = x0.copy()
    active = x0 > 0
    passed = np.zeros_like(active)
    for _ in range(H):
        if not active.any():
            break
        nh = np.minimum(1.0, h + delta * (WT @ (h * active)))
        passed |= active
        active = (nh > h + 1e-15) & ~passed
        change = np.max(np.abs(nh - h))
        h = nh
        if change < tol:
            break
    return h


def independent_cascade(W, x0, delta, H, n_runs=10_000, seed=0):
    """Monte Carlo independent cascade. Each run: seeds start hit with their x0; a node hit
    at hop d tries once, at hop d+1, to hit each seller i with probability W[j, i]; a hit
    carries delta * parent's loss (the largest if several parents hit it the same hop).
    Returns the mean loss per node over runs (seeds keep x0)."""
    rng = np.random.default_rng(seed)
    n = W.shape[0]
    seeds = np.flatnonzero(x0 > 0)
    # reachable sub-graph within H hops
    Wc = W.tocsr()
    reach, frontier = set(seeds.tolist()), set(seeds.tolist())
    for _ in range(H):
        nxt = set()
        for j in frontier:
            nxt.update(Wc.indices[Wc.indptr[j]:Wc.indptr[j + 1]].tolist())
        nxt -= reach
        reach |= nxt
        frontier = nxt
        if not frontier:
            break
    sub = np.array(sorted(reach))
    pos = {g: k for k, g in enumerate(sub)}
    Ws = Wc[sub][:, sub].tocoo()
    ej, ei, ep = Ws.row, Ws.col, np.minimum(1.0, Ws.data)
    m = len(sub)
    loss = np.zeros((n_runs, m))
    hit = np.zeros((n_runs, m), dtype=bool)
    for s in seeds:
        loss[:, pos[s]] = x0[s]
        hit[:, pos[s]] = True
    new = hit.copy()
    for _ in range(H):
        if not new.any() or len(ej) == 0:
            break
        nl = np.zeros((n_runs, m))
        fire_any = np.zeros((n_runs, m), dtype=bool)
        draws = rng.random((n_runs, len(ej)))
        for e in range(len(ej)):
            j, i = ej[e], ei[e]
            f = new[:, j] & ~hit[:, i] & (draws[:, e] < ep[e])
            if f.any():
                nl[f, i] = np.maximum(nl[f, i], delta * loss[f, j])
                fire_any[f, i] = True
        hit |= fire_any
        loss = np.where(fire_any, np.minimum(1.0, nl), loss)
        new = fire_any
    out = np.zeros(n)
    out[sub] = loss.mean(axis=0)
    return out


def signed_shock(model, W, seed_index, seed_ar, p: Params, seed=0):
    """Amendment 2: propagate the magnitude of the seed's abnormal return (capped at 1),
    then give every node the sign of the seed. Returns signed predicted moves."""
    x0 = np.zeros(W.shape[0])
    x0[seed_index] = min(1.0, abs(seed_ar))
    return np.sign(seed_ar) * propagate(model, W, x0, p, seed)


def propagate(model, W, x0, p: Params, seed=0):
    if model == "M1":
        return linear(W, x0, p.delta, p.H)
    if model == "M2":
        return debtrank(W, x0, p.delta, p.H)
    if model == "M3":
        return independent_cascade(W, x0, p.delta, p.H, p.n_runs, seed)
    raise ValueError(model)
