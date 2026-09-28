"""Item 8: subsidy repaired, not withdrawn. Expectations from literals.

Sample deal: QEI 10,000,000; A 6,763,000 @ 4.5%; B 3,037,000 @ 1.0%;
QLICI total 9,800,000; project cost 10,000,000.
"""
import dataclasses

import pandas as pd
import pytest

from nmtccalc import statute
from nmtccalc.models import subsidy
from nmtccalc.models.subsidy import (
    INTEREST_SAVINGS_NOTE, NET_SUBSIDY_NOTE, REFUSED_ALT_RATE, REFUSED_FORGIVENESS,
)


@pytest.fixture
def full(sample_deal):
    return dataclasses.replace(sample_deal, b_loan_forgiveness_rate=1.0,
                               qalicb_alternative_borrowing_rate=0.07)


# ── forgiveness ──────────────────────────────────────────────────────────────

def test_forgiveness_full(full):
    r = subsidy.analyze(full)
    assert r.b_loan_forgiven == pytest.approx(3_037_000)
    assert r.net_subsidy == pytest.approx(3_037_000)
    assert r.net_subsidy_pct == pytest.approx(0.3037)


def test_forgiveness_partial_and_exit_fee(full):
    r = subsidy.analyze(dataclasses.replace(full, b_loan_forgiveness_rate=0.5, exit_fee_rate=0.005))
    # 3,037,000 x 0.5 = 1,518,500; less exit fee 50,000
    assert r.b_loan_forgiven == pytest.approx(1_518_500)
    assert r.net_subsidy == pytest.approx(1_468_500)
    assert r.net_subsidy_pct == pytest.approx(0.14685)


def test_forgiveness_zero(full):
    r = subsidy.analyze(dataclasses.replace(full, b_loan_forgiveness_rate=0.0))
    assert r.b_loan_forgiven == 0 and r.net_subsidy == 0


def test_forgiveness_omitted_refuses_only_dependents(sample_deal):
    r = subsidy.analyze(sample_deal)
    assert r.b_loan_forgiven is None and r.net_subsidy is None and r.net_subsidy_pct is None
    assert r.refused["net_subsidy"] == REFUSED_FORGIVENESS
    assert r.refused["b_loan_forgiven"] == REFUSED_FORGIVENESS
    assert r.blended_qlici_coupon == pytest.approx(
        (6_763_000 * 0.045 + 3_037_000 * 0.01) / 9_800_000)


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_forgiveness_rate_range(sample_deal, bad):
    with pytest.raises(ValueError, match="b_loan_forgiveness_rate must be between 0 and 1 inclusive"):
        dataclasses.replace(sample_deal, b_loan_forgiveness_rate=bad)


@pytest.mark.parametrize("ok", [0, 1])
def test_forgiveness_rate_bounds_inclusive(sample_deal, ok):
    assert dataclasses.replace(sample_deal, b_loan_forgiveness_rate=ok).b_loan_forgiveness_rate == ok


@pytest.mark.parametrize("bad", [float("nan"), "1", True])
def test_forgiveness_rate_finite(sample_deal, bad):
    with pytest.raises(ValueError, match="b_loan_forgiveness_rate must be a finite number or None"):
        dataclasses.replace(sample_deal, b_loan_forgiveness_rate=bad)


# ── interest savings ─────────────────────────────────────────────────────────

def test_interest_savings_literal(full):
    # (6,763,000 x (7% - 4.5%) + 3,037,000 x (7% - 1%)) x 7 = (169,075 + 182,220) x 7
    r = subsidy.analyze(full)
    assert r.interest_savings_to_unwind == pytest.approx(351_295 * 7)


def test_interest_savings_respects_unwind_year(full):
    r = subsidy.analyze(dataclasses.replace(full, unwind_year=4))
    assert r.interest_savings_to_unwind == pytest.approx(351_295 * 4)


def test_interest_savings_negative_when_alternative_is_cheaper(full):
    r = subsidy.analyze(dataclasses.replace(full, qalicb_alternative_borrowing_rate=0.0))
    # -(304,335 + 30,370) x 7
    assert r.interest_savings_to_unwind == pytest.approx(-334_705 * 7)


def test_interest_savings_ignores_leverage_rate(full):
    a = subsidy.analyze(dataclasses.replace(full, leverage_loan_rate=0.01))
    b = subsidy.analyze(dataclasses.replace(full, leverage_loan_rate=0.20))
    assert a.interest_savings_to_unwind == b.interest_savings_to_unwind


def test_audit_case_no_longer_33pct_larger_than_the_loan(sample_deal):
    # 0.2.1: lev 20% -> $4,039,210 "savings" on a $3,037,000 B loan.
    d = dataclasses.replace(sample_deal, leverage_loan_rate=0.20, qlici_a_loan_rate=0.01)
    r = subsidy.analyze(d)
    assert r.interest_savings_to_unwind is None
    assert r.refused["interest_savings_to_unwind"] == REFUSED_ALT_RATE


@pytest.mark.parametrize("bad", [-0.01, 1, 1.5])
def test_alt_rate_range(sample_deal, bad):
    with pytest.raises(ValueError, match="qalicb_alternative_borrowing_rate must be at least 0 and below 1"):
        dataclasses.replace(sample_deal, qalicb_alternative_borrowing_rate=bad)


def test_alt_rate_zero_allowed(sample_deal):
    assert dataclasses.replace(sample_deal, qalicb_alternative_borrowing_rate=0).qalicb_alternative_borrowing_rate == 0


# ── rendering ────────────────────────────────────────────────────────────────

def test_summary_full_values(full, capsys):
    df = subsidy.analyze(dataclasses.replace(full, exit_fee_rate=0.005)).summary()
    v = dict(zip(df["Item"], df["Value"]))
    assert v["Investor Equity (into fund)"] == "$3.24MM"
    assert v["CDE Fee (upfront)"] == "$0.20MM"
    assert v["B Loan to QALICB"] == "$3.04MM"
    assert v["B-Loan Forgiveness Rate"] == "100.0%"
    assert v["B Loan Forgiven at Unwind"] == "$3.04MM"
    assert v["Exit Fee at Unwind"] == "$0.05MM"
    assert v["Net Subsidy at Unwind (t=7)"] == "$2.99MM"
    assert v["Net Subsidy as % of Project"] == "29.9%"
    assert v["QALICB Alternative Rate"] == "7.00%"
    assert v["Interest Savings to Unwind (7 yrs)"] == "$2.46MM"
    out = capsys.readouterr().out
    assert NET_SUBSIDY_NOTE in out
    assert INTEREST_SAVINGS_NOTE.format(k=7) in out
    assert "the loan is not bona fide debt for federal income tax purposes." in out
    assert "p. 17" in out
    assert "typically" not in out


def test_summary_blended_coupon_row(full):
    df = subsidy.analyze(full).summary()
    v = dict(zip(df["Item"], df["Value"]))
    # 334,705 / 9,800,000 = 3.4154%
    assert v["Blended QLICI Coupon"] == "3.42%"


def test_summary_omitted_inputs_render_refused(sample_deal, capsys):
    df = subsidy.analyze(sample_deal).summary()
    assert isinstance(df, pd.DataFrame)
    v = dict(zip(df["Item"], df["Value"]))
    assert v["B Loan Forgiven at Unwind"] == REFUSED_FORGIVENESS
    assert v["Net Subsidy at Unwind (t=7)"] == REFUSED_FORGIVENESS
    assert v["Net Subsidy as % of Project"] == REFUSED_FORGIVENESS
    assert v["B-Loan Forgiveness Rate"] == REFUSED_FORGIVENESS
    assert v["QALICB Alternative Rate"] == REFUSED_ALT_RATE
    assert v["Interest Savings to Unwind (7 yrs)"] == REFUSED_ALT_RATE


def test_summary_recapture_note(full, capsys):
    subsidy.analyze(dataclasses.replace(full, unwind_year=3)).summary()
    out = capsys.readouterr().out
    assert "§45D(g)(3)(C)" in out
    assert "Interest Savings" in out
    subsidy.analyze(full).summary()
    assert "§45D(g)(3)(C)" not in capsys.readouterr().out


def test_to_dict_keys(full):
    d = subsidy.analyze(full).to_dict()
    assert d["net_subsidy"] == pytest.approx(3_037_000)
    assert d["interest_savings_to_unwind"] == pytest.approx(351_295 * 7)
    assert d["b_loan_forgiveness_rate"] == 1.0
    assert d["qalicb_alternative_borrowing_rate"] == 0.07
    assert d["unwind_year"] == 7 and d["in_recapture_period"] is False
    assert d["refused"] == {}
    assert d["exit_fee"] == 0
    assert d["b_loan_forgiven"] == pytest.approx(3_037_000)
    assert d["net_subsidy_pct"] == pytest.approx(0.3037)
    assert "interest_savings_7yr" not in d


def test_atg_quote_constant():
    assert statute.ATG_BONA_FIDE_DEBT_QUOTE.endswith(
        "the loan is not bona fide debt for federal income tax purposes.\"")
    assert "good-faith intent on the part of the recipient" in statute.ATG_BONA_FIDE_DEBT_QUOTE


def test_sweep_net_subsidy_refused_without_rate(sample_deal):
    from nmtccalc import utils
    df = utils.credit_price_sensitivity(sample_deal, prices=[0.80])
    assert df.iloc[0]["Net Subsidy ($MM)"] == "REFUSED"
    assert df.iloc[0]["Subsidy % of Cost"] == "REFUSED (no forgiveness rate)"


def test_sweep_net_subsidy_with_rate(full):
    from nmtccalc import utils
    df = utils.credit_price_sensitivity(full, prices=[0.80, 0.83])
    # B at 0.80 = 3,120,000 - 200,000 = 2,920,000; at 0.83 = 3,037,000 (x 100% forgiven)
    assert list(df["Net Subsidy ($MM)"]) == [2.92, 3.04]
    assert list(df["Subsidy % of Cost"]) == ["29.2%", "30.4%"]
    # 3,037,000 x 0.999 = 3,033,963: 3.03 at two places (3.034 at three)
    df = utils.credit_price_sensitivity(dataclasses.replace(full, b_loan_forgiveness_rate=0.999), prices=[0.83])
    assert df.iloc[0]["Net Subsidy ($MM)"] == 3.03


def test_summary_exit_fee_scale(full):
    # 1% exit fee on 10,000,000 = 100,000 -> "$0.10MM" (divided by 1.1e6 it would be $0.09MM)
    df = subsidy.analyze(dataclasses.replace(full, exit_fee_rate=0.01)).summary()
    assert dict(zip(df["Item"], df["Value"]))["Exit Fee at Unwind"] == "$0.10MM"
