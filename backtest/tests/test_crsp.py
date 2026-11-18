import numpy as np
import pandas as pd
import pytest

from stage1 import crsp, pit
from stage1.config import WRDS
from stage1.run_step4 import shift_rows


def test_delisting_return_compounds_on_same_day_row():
    d = pd.DataFrame({"permno": [1, 1], "date": pd.to_datetime(["2019-05-01", "2019-05-02"]),
                      "ret": [0.01, 0.02]})
    dl = pd.DataFrame({"permno": [1], "dlstdt": pd.to_datetime(["2019-05-02"]), "dlret": [-0.5]})
    out = crsp.merge_delisting(d, dl).set_index("date")
    assert out.loc["2019-05-01", "ret_d"] == pytest.approx(0.01)
    assert out.loc["2019-05-02", "ret_d"] == pytest.approx(1.02 * 0.5 - 1)


def test_delisting_return_added_as_own_row_when_no_price_that_day():
    d = pd.DataFrame({"permno": [1], "date": pd.to_datetime(["2019-05-01"]), "ret": [0.01]})
    dl = pd.DataFrame({"permno": [1], "dlstdt": pd.to_datetime(["2019-05-03"]), "dlret": [0.2]})
    out = crsp.merge_delisting(d, dl).sort_values("date")
    assert len(out) == 2 and out.iloc[-1]["ret_d"] == pytest.approx(0.2)


def test_shift_rows_has_no_wraparound():
    A = np.array([[1], [0], [0], [1]], dtype=bool)
    assert shift_rows(A, 1)[:, 0].tolist() == [False, True, False, False]
    assert shift_rows(A, -1)[:, 0].tolist() == [False, False, True, False]


@pytest.mark.skipif(not (WRDS / "crsp_sp500list.parquet").exists(), reason="WRDS export not present")
def test_wrds_loaders_respect_cutoff():
    sp = crsp.sp500_spells()
    assert sp["ending"].max() <= pd.Timestamp("2023-12-31")
    assert sp["start"].max() < pit.CUTOFF
    n = crsp.names()
    assert n["namedt"].max() < pit.CUTOFF and n["nameendt"].max() <= pd.Timestamp("2023-12-31")
    c = crsp.ccm()
    assert c["linkenddt"].max() <= pd.Timestamp("2023-12-31")
    r = crsp.rdq()
    assert r["rdq"].max() < pit.CUTOFF
