"""Item 2: a negative tranche is refused at construction (F4)."""
import dataclasses

import pytest

from nmtccalc import NMTCDeal, NegativeTrancheError, utils


BASE = dict(
    project_name="P", total_project_cost=10_000_000, nmtc_allocation=10_000_000,
    credit_price=0.83, leverage_loan_rate=0.045, qlici_a_loan_rate=0.045,
    qlici_b_loan_rate=0.010,
)


def test_fee_above_boundary_refused():
    # boundary: cde_fee_rate > 0.39 x 0.83 = 0.3237
    with pytest.raises(NegativeTrancheError, match=r"qlici_b_loan would be \$-763,000") as ei:
        NMTCDeal(**BASE, cde_fee_rate=0.40)
    msg = str(ei.value)
    assert "0.3237" in msg
    assert "$4,000,000" in msg and "$3,237,000" in msg


def test_negative_tranche_error_is_a_valueerror():
    assert issubclass(NegativeTrancheError, ValueError)
    with pytest.raises(ValueError):
        NMTCDeal(**BASE, cde_fee_rate=0.40)


def test_just_below_boundary_constructs():
    d = NMTCDeal(**BASE, cde_fee_rate=0.3236)
    assert d.qlici_b_loan == pytest.approx(1_000, abs=1e-6)


def test_just_above_boundary_refused():
    with pytest.raises(NegativeTrancheError):
        NMTCDeal(**BASE, cde_fee_rate=0.3238)


def test_zero_b_loan_is_not_negative():
    # 0.39 x 0.80 = 0.312 exactly representable enough: B = 3,120,000 - 3,120,000
    d = NMTCDeal(**{**BASE, "credit_price": 0.80}, cde_fee_rate=0.312)
    assert d.qlici_b_loan == pytest.approx(0, abs=1e-6)


def test_replace_into_negative_is_refused(sample_deal):
    with pytest.raises(NegativeTrancheError):
        dataclasses.replace(sample_deal, cde_fee_rate=0.5)


def test_sweep_degrades_the_row_not_the_table():
    d = NMTCDeal(**BASE, cde_fee_rate=0.30)
    # 0.30 > 0.39p for p < 0.7692: 0.70..0.76 refused, 0.78+ computed
    df = utils.credit_price_sensitivity(d)
    refused = list(df["IRR"] == "REFUSED")
    assert refused == [True] * 4 + [False] * 7
    assert df.iloc[0]["Subsidy % of Cost"] == "REFUSED (negative tranche)"
    assert df.iloc[0]["Equity ($MM)"] == "REFUSED"
    assert df.iloc[4]["Equity ($MM)"] == pytest.approx(3.04)


def test_every_tranche_name_is_checked(monkeypatch, sample_deal):
    # Guard against a check that only ever inspects the B loan.
    for name in ("investor_equity", "leverage_loan", "qlici_total", "qlici_a_loan", "qlici_b_loan"):
        monkeypatch.setattr(NMTCDeal, name, property(lambda self: -1.0))
        with pytest.raises(NegativeTrancheError, match=name):
            dataclasses.replace(sample_deal)
        monkeypatch.undo()
