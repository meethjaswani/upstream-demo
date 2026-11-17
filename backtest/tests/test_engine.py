import numpy as np
import pytest

from stage1 import engine
from stage1.engine import Params


def L(seller, buyer, share=None, tier="DISCLOSED"):
    return {"seller": seller, "buyer": buyer, "share": share, "tier": tier}


# ------------------------------------------------------------------ weights
def test_disclosed_share_used_directly_times_tier():
    w = engine.weights([L("s", "b", 0.25, "DISCLOSED"), L("s2", "b", 0.4, "INFERRED")], {}, beta=1.0)
    assert w[("b", "s")] == pytest.approx(0.25)
    assert w[("b", "s2")] == pytest.approx(0.4 * 0.5)


def test_undisclosed_beta_zero_splits_residual_equally():
    links = [L("s", "a", 0.3), L("s", "b", None, "STATED"), L("s", "c", None, "STATED")]
    w = engine.weights(links, {"s": 10, "b": 10, "c": 40}, beta=0.0)
    # (1 - 0.3) * 1 / (1 + 2), times STATED 0.9
    assert w[("b", "s")] == pytest.approx(0.7 / 3 * 0.9)
    assert w[("c", "s")] == pytest.approx(0.7 / 3 * 0.9)


def test_undisclosed_size_ratio_beta_one():
    links = [L("s", "b", None), L("s", "c", None)]
    w = engine.weights(links, {"s": 10, "b": 10, "c": 40}, beta=1.0)
    ub, uc = 1.0, 4.0
    assert w[("b", "s")] == pytest.approx(ub / (1 + ub + uc))
    assert w[("c", "s")] == pytest.approx(uc / (1 + ub + uc))


def test_anonymous_customer_counts_toward_R_only():
    links = [L("s", None, 0.5), L("s", "b", None)]
    w = engine.weights(links, {"s": 1, "b": 1}, beta=1.0)
    assert set(w) == {("b", "s")}
    assert w[("b", "s")] == pytest.approx(0.5 * 1 / 2)


def test_R_above_one_leaves_nothing_for_undisclosed():
    links = [L("s", "a", 0.7), L("s", "x", 0.5), L("s", "b", None)]
    w = engine.weights(links, {}, beta=1.0)
    assert w[("b", "s")] == 0.0


def test_missing_market_cap_falls_back_to_u_equal_one():
    links = [L("s", "b", None)]
    w = engine.weights(links, {"s": 5}, beta=2.0)
    assert w[("b", "s")] == pytest.approx(0.5)


# ------------------------------------------------------------------ propagation
def chain(wab=0.5, wbc=0.4):
    # a buys from b, b buys from c: a shock to a hits b, then c
    nodes = ["a", "b", "c"]
    W = engine.matrix({("a", "b"): wab, ("b", "c"): wbc}, nodes)
    return nodes, W


def test_direction_buyer_shock_reaches_seller_not_reverse():
    nodes, W = chain()
    x = engine.linear(W, np.array([0.0, 0.1, 0.0]), 0.6, 4)
    assert x[0] == 0.0 and x[2] > 0      # b hit: its seller c moves, its buyer a does not


def test_linear_chain_values_and_hop_limit():
    nodes, W = chain(0.5, 0.4)
    x0 = np.array([0.2, 0.0, 0.0])
    x = engine.linear(W, x0, 0.6, 4)
    assert x[1] == pytest.approx(0.6 * 0.5 * 0.2)
    assert x[2] == pytest.approx(0.6 * 0.4 * 0.6 * 0.5 * 0.2)
    x1 = engine.linear(W, x0, 0.6, 1)
    assert x1[2] == 0.0


def test_linear_caps_at_one():
    W = engine.matrix({("a", "b"): 1.0}, ["a", "b"])
    x = engine.linear(W, np.array([1.0, 0.9]), 0.9, 3)
    assert x[1] == 1.0


def test_debtrank_passes_once_on_cycle():
    nodes = ["a", "b"]
    W = engine.matrix({("a", "b"): 0.5, ("b", "a"): 0.5}, nodes)
    x0 = np.array([0.4, 0.0])
    lin = engine.linear(W, x0, 1.0, 6, tol=0)
    dr = engine.debtrank(W, x0, 1.0, 6)
    # DebtRank: a passes 0.2 to b; b passes 0.1 back to a; a has already passed, stops
    assert dr[1] == pytest.approx(0.2)
    assert dr[0] == pytest.approx(0.5)
    assert lin[0] > dr[0] and lin[1] > dr[1]


def test_debtrank_equals_linear_on_a_tree():
    nodes, W = chain(0.5, 0.4)
    x0 = np.array([0.2, 0.0, 0.0])
    assert np.allclose(engine.debtrank(W, x0, 0.6, 4), engine.linear(W, x0, 0.6, 4))


def test_ic_deterministic_with_probability_one():
    nodes, W = chain(1.0, 1.0)
    x = engine.independent_cascade(W, np.array([0.2, 0, 0]), 0.6, 4, n_runs=100, seed=1)
    assert x[1] == pytest.approx(0.12)
    assert x[2] == pytest.approx(0.072)


def test_ic_mean_matches_probability_and_is_seeded():
    W = engine.matrix({("a", "b"): 0.3}, ["a", "b"])
    x0 = np.array([0.1, 0.0])
    x = engine.independent_cascade(W, x0, 0.6, 2, n_runs=10_000, seed=7)
    assert x[1] == pytest.approx(0.3 * 0.6 * 0.1, rel=0.05)
    y = engine.independent_cascade(W, x0, 0.6, 2, n_runs=10_000, seed=7)
    assert np.array_equal(x, y)


def test_ic_respects_hop_limit():
    nodes, W = chain(1.0, 1.0)
    x = engine.independent_cascade(W, np.array([0.2, 0, 0]), 0.6, 1, n_runs=50, seed=1)
    assert x[2] == 0.0


def test_propagate_dispatch():
    nodes, W = chain()
    p = Params(delta=0.6, H=4, n_runs=200)
    x0 = np.array([0.2, 0, 0])
    for m in ("M1", "M2", "M3"):
        assert engine.propagate(m, W, x0, p, seed=3)[1] > 0
    with pytest.raises(ValueError):
        engine.propagate("M9", W, x0, p)


def test_signed_shock_propagates_magnitude_and_applies_sign():
    nodes, W = chain(0.5, 0.4)
    p = Params(delta=0.6, H=4, n_runs=200)
    up = engine.signed_shock("M1", W, 0, 0.2, p)
    down = engine.signed_shock("M1", W, 0, -0.2, p)
    assert up[1] == pytest.approx(0.06) and down[1] == pytest.approx(-0.06)
    assert np.allclose(up, -down)
    big = engine.signed_shock("M1", W, 0, -1.7, p)          # magnitude capped at 1
    assert big[0] == -1.0 and big[1] == pytest.approx(-0.3)
