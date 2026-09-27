import pytest
import pandas as pd
from nmtccalc.models import investor


def test_moic_positive(sample_deal):
    result = investor.analyze(sample_deal)
    assert result.moic > 0


def test_moic_literal_value(sample_deal):
    # Replaces test_moic_math, a tautology: it computed the expectation from
    # the same two properties the implementation divides, so it could not fail
    # for any input and would go red on any correction. The expectation here
    # is from literals: credits retained 3,900,000 / equity paid 3,237,000.
    result = investor.analyze(sample_deal)
    assert result.moic == pytest.approx(3_900_000 / 3_237_000, abs=1e-12)


def test_gross_benefit_equals_total_nmtcs(sample_deal):
    result = investor.analyze(sample_deal)
    assert result.gross_benefit == pytest.approx(sample_deal.total_nmtcs)


def test_net_benefit_math(sample_deal):
    result = investor.analyze(sample_deal)
    expected = sample_deal.total_nmtcs - sample_deal.investor_equity
    assert result.net_benefit == pytest.approx(expected)


def test_irr_is_float(sample_deal):
    import math
    result = investor.analyze(sample_deal)
    assert isinstance(result.irr, float) and not math.isnan(result.irr)


def test_irr_positive_and_reasonable(sample_deal):
    result = investor.analyze(sample_deal)
    assert 0.01 < result.irr < 0.25


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
