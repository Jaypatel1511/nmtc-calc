import pytest
import pandas as pd
from nmtccalc import utils


def test_credit_price_sensitivity_returns_dataframe(sample_deal):
    df = utils.credit_price_sensitivity(sample_deal)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_credit_price_sensitivity_custom_prices(sample_deal):
    df = utils.credit_price_sensitivity(sample_deal, prices=[0.75, 0.80, 0.85])
    assert len(df) == 3


def test_higher_credit_price_means_more_equity(sample_deal):
    df = utils.credit_price_sensitivity(sample_deal, prices=[0.75, 0.85])
    assert df.iloc[0]["Equity ($MM)"] < df.iloc[1]["Equity ($MM)"]


def test_higher_credit_price_means_lower_leverage(sample_deal):
    df = utils.credit_price_sensitivity(sample_deal, prices=[0.75, 0.85])
    assert df.iloc[0]["Leverage Loan ($MM)"] > df.iloc[1]["Leverage Loan ($MM)"]


def test_discount_rate_sensitivity_returns_dataframe(sample_deal):
    df = utils.discount_rate_sensitivity(sample_deal)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_discount_rate_sensitivity_custom_rates(sample_deal):
    df = utils.discount_rate_sensitivity(sample_deal, rates=[0.06, 0.08, 0.10])
    assert len(df) == 3


def test_higher_discount_rate_means_lower_pv(sample_deal):
    df = utils.discount_rate_sensitivity(sample_deal, rates=[0.05, 0.10])
    assert df.iloc[0]["PV of Credits ($MM)"] > df.iloc[1]["PV of Credits ($MM)"]
