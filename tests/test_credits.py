import pytest
import pandas as pd
from nmtccalc.models import credits


def test_seven_years(sample_deal):
    result = credits.schedule(sample_deal)
    assert len(result.annual_credits) == 7


def test_years_1_to_3_rate(sample_deal):
    result = credits.schedule(sample_deal)
    for yr in range(3):
        assert result.annual_credits[yr] == pytest.approx(sample_deal.qei * 0.05)


def test_years_4_to_7_rate(sample_deal):
    result = credits.schedule(sample_deal)
    for yr in range(3, 7):
        assert result.annual_credits[yr] == pytest.approx(sample_deal.qei * 0.06)


def test_total_credits_equals_39pct(sample_deal):
    result = credits.schedule(sample_deal)
    assert sum(result.annual_credits) == pytest.approx(sample_deal.qei * 0.39)


def test_cumulative_final_equals_total(sample_deal):
    result = credits.schedule(sample_deal)
    assert result.cumulative_credits[-1] == pytest.approx(sample_deal.total_nmtcs)


def test_pv_less_than_total(sample_deal):
    result = credits.schedule(sample_deal)
    assert result.pv_credits < result.total_nmtcs


def test_summary_returns_dataframe(sample_deal):
    result = credits.schedule(sample_deal)
    df = result.summary()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 7


def test_to_dict_keys(sample_deal):
    result = credits.schedule(sample_deal)
    d = result.to_dict()
    assert "annual_credits" in d
    assert "pv_credits" in d
