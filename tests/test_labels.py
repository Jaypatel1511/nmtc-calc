"""Item 9: labels that say what the numbers are, with invariance disclosed on the face."""
import dataclasses

import pytest

from nmtccalc import NMTCDeal, investor, subsidy, transaction, utils
from nmtccalc.models.investor import CREDIT_ONLY_NOTE
from nmtccalc.models.subsidy import BLENDED_COUPON_NOTE
from nmtccalc.models.transaction import LEVERAGE_RATIO_NOTE
from nmtccalc.utils import SWEEP_INVARIANCE_NOTE

SMALL = dict(project_name="Small", total_project_cost=10_000_000, nmtc_allocation=10_000_000,
             credit_price=0.83, leverage_loan_rate=0.045, qlici_a_loan_rate=0.045,
             qlici_b_loan_rate=0.010, cde_fee_rate=0.02)
BIG = dict(project_name="Big", total_project_cost=500_000_000, nmtc_allocation=45_000_000,
           credit_price=0.83, leverage_loan_rate=0.09, qlici_a_loan_rate=0.07,
           qlici_b_loan_rate=0.001, cde_fee_rate=0.05, discount_rate=0.12)


def test_old_names_are_gone(sample_deal):
    inv = investor.analyze(sample_deal).to_dict()
    assert "irr" not in inv and "moic" not in inv
    assert "credit_only_irr" in inv and "credit_only_moic" in inv
    assert "effective_cost_of_capital" not in subsidy.analyze(sample_deal).to_dict()
    assert "leverage_ratio" not in transaction.structure(sample_deal).to_dict()
    for cls, old in ((investor.InvestorResult, "irr"), (subsidy.SubsidyResult, "effective_cost_of_capital"),
                     (transaction.TransactionResult, "leverage_ratio")):
        assert old not in {f.name for f in dataclasses.fields(cls)}


def test_credit_only_figures_invariant_across_unrelated_deals():
    a, b = investor.analyze(NMTCDeal(**SMALL)), investor.analyze(NMTCDeal(**BIG))
    assert a.credit_only_irr == pytest.approx(b.credit_only_irr, abs=1e-12)
    assert a.credit_only_moic == pytest.approx(b.credit_only_moic, abs=1e-12)
    assert a.credit_only_moic == pytest.approx(1 / 0.83, abs=1e-12)


def test_leverage_to_equity_invariant_and_literal():
    a, b = transaction.structure(NMTCDeal(**SMALL)), transaction.structure(NMTCDeal(**BIG))
    # (1 - 0.39 x 0.83) / (0.39 x 0.83) = 0.6763 / 0.3237
    assert a.leverage_loan_to_equity_ratio == pytest.approx(0.6763 / 0.3237, abs=1e-12)
    assert b.leverage_loan_to_equity_ratio == pytest.approx(a.leverage_loan_to_equity_ratio, abs=1e-12)


def test_blended_coupon_literal(sample_deal):
    assert subsidy.analyze(sample_deal).blended_qlici_coupon == pytest.approx(334_705 / 9_800_000, abs=1e-15)


def test_blended_coupon_moves_with_split(sample_deal):
    d = dataclasses.replace(sample_deal, qlici_a_loan_amount=4_800_000)
    # 4,800,000 x 4.5% + 5,000,000 x 1% = 266,000
    assert subsidy.analyze(d).blended_qlici_coupon == pytest.approx(266_000 / 9_800_000)


def test_investor_summary_discloses_invariance(sample_deal, capsys):
    investor.analyze(sample_deal).summary()
    out = capsys.readouterr().out
    assert CREDIT_ONLY_NOTE in out
    assert "credit-only MOIC = 1 / credit price" in out
    assert "They are not an investor IRR or MOIC." in out
    assert "Credit-only IRR:      6.3%" in out


def test_investor_summary_discloses_even_when_refused(sample_deal, capsys):
    investor.analyze(dataclasses.replace(sample_deal, unwind_year=5)).summary()
    out = capsys.readouterr().out
    assert CREDIT_ONLY_NOTE in out
    assert "Credit-only IRR:      REFUSED" in out


def test_transaction_summary_discloses_ratio(sample_deal, capsys):
    df = transaction.structure(sample_deal).summary()
    out = capsys.readouterr().out
    assert LEVERAGE_RATIO_NOTE in out
    rows = dict(zip(df["Item"], df["Amount"]))
    assert rows["── Leverage Loan / Equity"] == "2.09x"


def test_subsidy_summary_discloses_coupon(sample_deal, capsys):
    df = subsidy.analyze(sample_deal).summary()
    assert BLENDED_COUPON_NOTE in capsys.readouterr().out
    assert dict(zip(df["Item"], df["Value"]))["Blended QLICI Coupon"] == "3.42%"


def test_sweep_columns_identical_across_deals_and_disclosed(capsys):
    prices = [0.75, 0.83, 0.90]
    da = utils.credit_price_sensitivity(NMTCDeal(**SMALL), prices=prices)
    db = utils.credit_price_sensitivity(NMTCDeal(**BIG), prices=prices)
    assert list(da["Credit-only MOIC"]) == list(db["Credit-only MOIC"])
    assert list(da["Credit-only IRR"]) == list(db["Credit-only IRR"])
    assert list(da["Equity ($MM)"]) != list(db["Equity ($MM)"])
    out = capsys.readouterr().out
    assert out.count(SWEEP_INVARIANCE_NOTE) == 2
    assert "MOIC" not in list(da.columns) and "IRR" not in list(da.columns)
