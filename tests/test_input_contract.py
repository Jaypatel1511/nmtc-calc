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


# ── fix round 2, R1-1 ────────────────────────────────────────────────────────

def test_noi_dict_refused(sample_deal):
    with pytest.raises(ValueError, match=r"noi must not be a mapping \(a dict gives its keys"):
        dataclasses.replace(sample_deal, noi={i: 600_000 for i in range(7)})


def test_noi_mapping_types_refused(sample_deal):
    import collections
    with pytest.raises(ValueError, match="noi must not be a mapping"):
        dataclasses.replace(sample_deal, noi=collections.OrderedDict((i, 1.0) for i in range(7)))


@pytest.mark.parametrize("s", [{1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0}, frozenset({1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0})])
def test_noi_set_refused(sample_deal, s):
    with pytest.raises(ValueError, match=r"noi must not be a set \(a set has no order\)"):
        dataclasses.replace(sample_deal, noi=s)


@pytest.mark.parametrize("arr", [np.full((7, 1), 6e5), np.full((1, 7), 6e5), pd.DataFrame({"noi": [6e5] * 7})])
def test_noi_not_one_dimensional_refused(sample_deal, arr):
    with pytest.raises(ValueError, match=r"noi must be one-dimensional \(got an array with ndim=2\)"):
        dataclasses.replace(sample_deal, noi=arr)


def test_noi_zero_dim_array_is_a_scalar(sample_deal):
    # np.float64 is a Real and takes the scalar path
    assert dataclasses.replace(sample_deal, noi=np.float64(6e5)).noi == 6e5


def test_noi_series_with_nondefault_index_uses_values_in_order(sample_deal):
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], index=[70, 60, 50, 40, 30, 20, 10])
    assert dataclasses.replace(sample_deal, noi=s).noi == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0)


def test_moic_renders_at_implausible_price(sample_deal):
    # X10 residual, decided: credit-only MOIC = 1 / price for any legal price. At 1e-9 it is
    # 1e9x -- correct arithmetic on an implausible input; the package does not police price
    # plausibility beyond (0, 1). The IRR is refused (no sign change).
    # (fee 1e-10 < 39% x 1e-9, so the B loan stays non-negative)
    r = investor.analyze(dataclasses.replace(sample_deal, credit_price=1e-9, cde_fee_rate=1e-10))
    assert r.credit_only_moic == pytest.approx(1e9, rel=1e-9)
    assert r.refused_code == "no_sign_change"
