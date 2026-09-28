"""Fix round 1: X2 rate ranges, X3 frozen deal, X9 input types, X10 schema nits."""
import dataclasses
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from nmtccalc import NMTCDeal, NegativeTrancheError, credits, investor, subsidy, transaction, waterfall
from nmtccalc.data.schema import MAX_UNWIND_YEAR

RATES = ["leverage_loan_rate", "qlici_a_loan_rate", "qlici_b_loan_rate",
         "guarantee_fee_rate", "exit_fee_rate"]


# ── X2 ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("field", RATES)
@pytest.mark.parametrize("bad", [-0.0001, -0.05, 1.0, 3.0])
def test_rates_must_lie_in_zero_one(sample_deal, field, bad):
    with pytest.raises(ValueError, match=f"{field} must be at least 0 and below 1"):
        dataclasses.replace(sample_deal, **{field: bad})


@pytest.mark.parametrize("field", RATES)
@pytest.mark.parametrize("ok", [0.0, 0.9999])
def test_rate_boundaries_allowed(sample_deal, field, ok):
    assert getattr(dataclasses.replace(sample_deal, **{field: ok}), field) == ok


# ── X3 ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("field, value", [("cde_fee_rate", 0.40), ("credit_price", 5.0),
                                          ("noi", -1.0), ("qlici_a_loan_amount", -1.0),
                                          ("unwind_year", 3)])
def test_attribute_assignment_raises(sample_deal, field, value):
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(sample_deal, field, value)


def test_replace_and_with_still_revalidate(sample_deal):
    with pytest.raises(NegativeTrancheError):
        dataclasses.replace(sample_deal, cde_fee_rate=0.40)
    with pytest.raises(ValueError, match="credit_price"):
        sample_deal.with_credit_price(1.2)
    assert sample_deal.with_credit_price(0.90).credit_price == 0.90


def test_deal_is_hashable(sample_deal):
    assert hash(sample_deal) == hash(dataclasses.replace(sample_deal))


# ── X9 ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("series", [
    np.array([500_000, 550_000, 600_000, 650_000, 700_000, 750_000, 800_000]),
    pd.Series([500_000, 550_000, 600_000, 650_000, 700_000, 750_000, 800_000]),
    range(500_000, 850_000, 50_000),
])
def test_noi_accepts_array_series_range(sample_deal, series):
    d = dataclasses.replace(sample_deal, noi=series)
    assert d.noi == (500_000.0, 550_000.0, 600_000.0, 650_000.0, 700_000.0, 750_000.0, 800_000.0)
    assert all(type(v) is float for v in d.noi)
    assert waterfall.analyze(d).dscr_varies is True


def test_noi_rejects_string_and_dict_keys_are_values(sample_deal):
    with pytest.raises(ValueError, match="noi must be a finite non-negative number, a sequence"):
        dataclasses.replace(sample_deal, noi="600000")
    with pytest.raises(ValueError, match="noi must be a finite non-negative number, a sequence"):
        dataclasses.replace(sample_deal, noi=object())


def test_numpy_integer_unwind_year(sample_deal):
    d = dataclasses.replace(sample_deal, unwind_year=np.int64(4))
    assert d.unwind_year == 4 and type(d.unwind_year) is int
    assert credits.schedule(d).in_recapture_period is True


# ── X10 ──────────────────────────────────────────────────────────────────────

def test_unwind_year_upper_bound(sample_deal):
    assert MAX_UNWIND_YEAR == 30
    assert dataclasses.replace(sample_deal, unwind_year=30).unwind_year == 30
    with pytest.raises(ValueError, match="unwind_year must be at most 30 .*not a calendar year"):
        dataclasses.replace(sample_deal, unwind_year=31)
    with pytest.raises(ValueError, match="at most 30"):
        dataclasses.replace(sample_deal, unwind_year=2033)


def test_fraction_inputs_coerced_and_summaries_render(sample_deal, capsys):
    d = dataclasses.replace(sample_deal, credit_price=Fraction(83, 100), cde_fee_rate=Fraction(1, 50),
                            b_loan_forgiveness_rate=Fraction(1, 1), noi=Fraction(600_000))
    assert type(d.credit_price) is float and d.credit_price == 0.83
    assert type(d.b_loan_forgiveness_rate) is float and type(d.noi) is float
    for fn in (transaction.structure, credits.schedule, investor.analyze, subsidy.analyze, waterfall.analyze):
        fn(d).summary()
    assert "Credit-only IRR" in capsys.readouterr().out


def test_numeric_fields_are_floats(sample_deal):
    d = dataclasses.replace(sample_deal, nmtc_allocation=np.int64(10_000_000), total_project_cost=10_000_000)
    assert type(d.nmtc_allocation) is float and type(d.total_project_cost) is float
