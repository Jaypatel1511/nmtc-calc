import pytest
from nmtccalc.data.schema import NMTCDeal
from nmtccalc.models import transaction


def test_total_nmtcs(sample_deal):
    assert sample_deal.total_nmtcs == pytest.approx(10_000_000 * 0.39)


def test_investor_equity(sample_deal):
    expected = 10_000_000 * 0.39 * 0.83
    assert sample_deal.investor_equity == pytest.approx(expected)


def test_leverage_loan(sample_deal):
    expected = 10_000_000 - (10_000_000 * 0.39 * 0.83)
    assert sample_deal.leverage_loan == pytest.approx(expected)


def test_qei_equals_equity_plus_loan(sample_deal):
    assert sample_deal.qei == pytest.approx(
        sample_deal.investor_equity + sample_deal.leverage_loan
    )


def test_qlici_total(sample_deal):
    expected = 10_000_000 - (10_000_000 * 0.02)
    assert sample_deal.qlici_total == pytest.approx(expected)


def test_qlici_a_plus_b_equals_total(sample_deal):
    assert pytest.approx(sample_deal.qlici_a_loan + sample_deal.qlici_b_loan,
                         rel=1e-4) == sample_deal.qlici_total


def test_structure_returns_result(sample_deal):
    result = transaction.structure(sample_deal)
    assert result.qei == sample_deal.qei
    assert result.leverage_ratio > 0


def test_summary_returns_dataframe(sample_deal):
    import pandas as pd
    result = transaction.structure(sample_deal)
    df = result.summary()
    assert isinstance(df, pd.DataFrame)


def test_allocation_exceeds_project_cost_raises():
    with pytest.raises(ValueError, match="cannot exceed"):
        NMTCDeal(
            project_name="Bad Deal",
            total_project_cost=5_000_000,
            nmtc_allocation=6_000_000,
            credit_price=0.83,
            leverage_loan_rate=0.045,
            qlici_a_loan_rate=0.045,
            qlici_b_loan_rate=0.01,
            cde_fee_rate=0.02,
        )


def test_to_dict_keys(sample_deal):
    result = transaction.structure(sample_deal)
    d = result.to_dict()
    assert "qei" in d
    assert "leverage_loan" in d
    assert "nmtc_coverage" in d
