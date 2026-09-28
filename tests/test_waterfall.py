import dataclasses
import pytest
import pandas as pd
from nmtccalc.models import waterfall


@pytest.fixture
def deal_with_noi(sample_deal):
    return dataclasses.replace(sample_deal, noi=600_000)


def test_seven_years(deal_with_noi):
    result = waterfall.analyze(deal_with_noi)
    assert len(result.years) == 7


def test_dscr_computed_when_noi_provided(deal_with_noi):
    result = waterfall.analyze(deal_with_noi)
    for yr in result.years:
        assert yr.dscr is not None and yr.dscr > 0


def test_dscr_none_without_noi(sample_deal):
    result = waterfall.analyze(sample_deal)
    for yr in result.years:
        assert yr.dscr is None


def test_b_loan_forgiven_only_in_year7(deal_with_noi):
    result = waterfall.analyze(dataclasses.replace(deal_with_noi, b_loan_forgiveness_rate=1.0))
    for yr in result.years[:-1]:
        assert yr.b_loan_forgiven == 0.0
    assert result.years[-1].b_loan_forgiven == pytest.approx(3_037_000)


def test_b_loan_forgiven_refused_without_rate(deal_with_noi, capsys):
    result = waterfall.analyze(deal_with_noi)
    assert result.years[-1].b_loan_forgiven is None
    assert result.b_loan_forgiven is None and result.net_subsidy_at_unwind is None
    result.summary()
    out = capsys.readouterr().out
    assert "B Loan Forgiven:  REFUSED: b_loan_forgiveness_rate not supplied" in out
    assert "Net Subsidy at Unwind (t=7): REFUSED" in out


def test_total_interest_math(deal_with_noi):
    result = waterfall.analyze(deal_with_noi)
    annual_ds = (
        deal_with_noi.qlici_a_loan * deal_with_noi.qlici_a_loan_rate
        + deal_with_noi.qlici_b_loan * deal_with_noi.qlici_b_loan_rate
    )
    assert result.total_interest_paid == pytest.approx(annual_ds * 7)


def test_net_subsidy_at_unwind_no_exit_fee(deal_with_noi):
    result = waterfall.analyze(dataclasses.replace(deal_with_noi, b_loan_forgiveness_rate=0.8))
    assert result.net_subsidy_at_unwind == pytest.approx(3_037_000 * 0.8)


def test_exit_fee_reduces_net_subsidy(sample_deal):
    deal = dataclasses.replace(sample_deal, exit_fee_rate=0.005, b_loan_forgiveness_rate=1.0)
    result = waterfall.analyze(deal)
    assert result.net_subsidy_at_unwind == pytest.approx(3_037_000 - 50_000)


def test_exit_fee_only_in_year7(sample_deal):
    deal = dataclasses.replace(sample_deal, exit_fee_rate=0.005)
    result = waterfall.analyze(deal)
    for yr in result.years[:-1]:
        assert yr.exit_fee == 0.0
    assert result.years[-1].exit_fee == pytest.approx(deal.exit_fee)


def test_guarantee_fee_every_year(sample_deal):
    deal = dataclasses.replace(sample_deal, guarantee_fee_rate=0.01)
    result = waterfall.analyze(deal)
    expected = deal.leverage_loan * 0.01
    for yr in result.years:
        assert yr.guarantee_fee == pytest.approx(expected)


def test_guarantee_fee_reduces_net_cf(sample_deal):
    base = dataclasses.replace(sample_deal, noi=600_000)
    with_fee = dataclasses.replace(sample_deal, noi=600_000, guarantee_fee_rate=0.01)
    r_base = waterfall.analyze(base)
    r_fee = waterfall.analyze(with_fee)
    expected_diff = with_fee.guarantee_fee_annual
    assert r_base.years[0].net_cash_flow - r_fee.years[0].net_cash_flow == pytest.approx(expected_diff)


def test_dscr_level_literal(deal_with_noi):
    # Replaces test_avg_dscr_equals_min_when_noi_constant, which pinned the
    # flat seven-row schedule (F2) as correct: it asserted avg == min, which
    # holds by construction for every legal deal, and would go red on any fix
    # that lets the rows differ. This pins the LEVEL instead, from literals:
    # 600,000 / (6,763,000 x 4.5% + 3,037,000 x 1.0%) = 600,000 / 334,705.
    result = waterfall.analyze(deal_with_noi)
    assert result.years[0].dscr == pytest.approx(600_000 / 334_705, abs=1e-12)


def test_summary_returns_dataframe(deal_with_noi):
    result = waterfall.analyze(deal_with_noi)
    df = result.summary()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 7


def test_to_dict_keys(deal_with_noi):
    result = waterfall.analyze(deal_with_noi)
    d = result.to_dict()
    assert "total_interest_paid" in d
    assert "b_loan_forgiven" in d
    assert "net_subsidy_at_unwind" in d
    assert "net_year7_subsidy" not in d
    assert "avg_dscr" in d
    assert "min_dscr" in d
