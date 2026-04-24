import pytest
import pandas as pd
from nmtccalc.models import subsidy


def test_net_subsidy_positive(sample_deal):
    result = subsidy.analyze(sample_deal)
    assert result.net_subsidy > 0


def test_net_subsidy_equals_b_loan(sample_deal):
    result = subsidy.analyze(sample_deal)
    assert result.net_subsidy == pytest.approx(sample_deal.qlici_b_loan)


def test_net_subsidy_pct_range(sample_deal):
    result = subsidy.analyze(sample_deal)
    assert 0.10 <= result.net_subsidy_pct <= 0.35


def test_effective_cost_below_market(sample_deal):
    result = subsidy.analyze(sample_deal)
    assert result.effective_cost_of_capital < sample_deal.leverage_loan_rate


def test_interest_savings_positive(sample_deal):
    result = subsidy.analyze(sample_deal)
    assert result.interest_savings_7yr > 0


def test_summary_returns_dataframe(sample_deal):
    result = subsidy.analyze(sample_deal)
    df = result.summary()
    assert isinstance(df, pd.DataFrame)


def test_to_dict_keys(sample_deal):
    result = subsidy.analyze(sample_deal)
    d = result.to_dict()
    assert "net_subsidy" in d
    assert "net_subsidy_pct" in d
    assert "effective_cost_of_capital" in d
