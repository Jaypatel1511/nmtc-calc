import pytest
import pandas as pd
from nmtccalc.models import investor


def test_moic_positive(sample_deal):
    result = investor.analyze(sample_deal)
    assert result.moic > 0


def test_moic_math(sample_deal):
    result = investor.analyze(sample_deal)
    expected_moic = sample_deal.total_nmtcs / sample_deal.investor_equity
    assert result.moic == pytest.approx(expected_moic)


def test_gross_benefit_equals_total_nmtcs(sample_deal):
    result = investor.analyze(sample_deal)
    assert result.gross_benefit == pytest.approx(sample_deal.total_nmtcs)


def test_net_benefit_math(sample_deal):
    result = investor.analyze(sample_deal)
    expected = sample_deal.total_nmtcs - sample_deal.investor_equity
    assert result.net_benefit == pytest.approx(expected)


def test_irr_is_float(sample_deal):
    result = investor.analyze(sample_deal)
    assert isinstance(result.irr, float)


def test_summary_returns_dataframe(sample_deal):
    result = investor.analyze(sample_deal)
    df = result.summary()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 7


def test_to_dict_keys(sample_deal):
    result = investor.analyze(sample_deal)
    d = result.to_dict()
    assert "irr" in d
    assert "moic" in d
    assert "net_benefit" in d
