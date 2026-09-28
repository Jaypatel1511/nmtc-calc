"""Kills for survivors of the fix-round-1 campaign (text operators included)."""
import dataclasses
import re
import warnings

import pytest

from nmtccalc import LeverageShortfallWarning, NMTCDeal, investor, statute, subsidy, utils, waterfall
from nmtccalc.models import subsidy as sub_mod
from nmtccalc.models import transaction as tx_mod
from nmtccalc.models import waterfall as wf_mod


@pytest.mark.parametrize("field, value, message", [
    ("credit_price", 1.5, "credit_price must be between 0 and 1 (e.g. 0.83)"),
    ("cde_fee_rate", 1.5, "cde_fee_rate must be between 0 and 1 (e.g. 0.02)"),
    ("discount_rate", 1.5, "discount_rate must be between 0 and 1 (e.g. 0.08)"),
])
def test_range_messages_whole(sample_deal, field, value, message):
    with pytest.raises(ValueError, match="^" + re.escape(message) + "$"):
        dataclasses.replace(sample_deal, **{field: value})


def test_note_clauses_second_campaign():
    from nmtccalc.models import investor as inv_mod
    assert "(plus nondeductible interest this package does not compute)" in inv_mod.REFUSAL_RECAPTURE
    assert sub_mod.BLENDED_COUPON_NOTE.endswith("(0.2.1 called it effective_cost_of_capital.)")
    assert tx_mod.PROVENANCE_NOTE.endswith(
        "Supply the A/B split with qlici_a_loan_amount / qlici_b_loan_amount where real terms exist.")
    assert tx_mod.LEVERAGE_RATIO_NOTE.endswith("(0.2.1 called it leverage_ratio.)")
    assert wf_mod.FLAT_DSCR_NOTE.endswith(
        "Supply noi as a sequence with one entry per year to model a schedule.")
    assert "forgive or otherwise not collect on the debt" in statute.ATG_BONA_FIDE_DEBT_QUOTE
    assert utils.DISCOUNT_INVARIANCE_NOTE.endswith("PV of Credits scales with QEI.")
    assert utils.SWEEP_INVARIANCE_NOTE.endswith(
        "Equity and leverage scale with QEI; net subsidy depends on the A/B split, the fee and the "
        "forgiveness rate.")


def test_subsidy_basis_column_blank_when_refused_and_labelled_when_supplied(sample_deal):
    rows = ["B-Loan Forgiveness Rate", "B Loan Forgiven at Unwind", "Net Subsidy at Unwind (t=7)",
            "Net Subsidy as % of Project", "QALICB Alternative Rate", "Interest Savings to Unwind (7 yrs)"]
    refused = dict(zip(*(lambda df: (df["Item"], df["Basis"]))(subsidy.analyze(sample_deal).summary())))
    assert [refused[r] for r in rows] == [""] * 6
    full = dataclasses.replace(sample_deal, b_loan_forgiveness_rate=1.0, qalicb_alternative_borrowing_rate=0.07)
    basis = dict(zip(*(lambda df: (df["Item"], df["Basis"]))(subsidy.analyze(full).summary())))
    assert [basis[r] for r in rows] == [
        "SUPPLIED: b_loan_forgiveness_rate", "DERIVED: B loan x forgiveness rate",
        "DERIVED: B loan forgiven - exit fee", "DERIVED: net subsidy / project cost",
        "SUPPLIED: qalicb_alternative_borrowing_rate",
        "DERIVED: QLICI principal x (alt rate - coupons) x years"]


def test_tiny_positive_debt_service_is_not_refused(sample_deal):
    r = waterfall.analyze(dataclasses.replace(sample_deal, noi=1.0, qlici_a_loan_rate=1e-9,
                                              qlici_b_loan_rate=1e-9, leverage_loan_rate=0.0))
    assert r.dscr_refused_reason is None
    assert r.years[0].dscr == pytest.approx(1.0 / 0.0098)


def test_a_only_shortfall_zero_when_a_covers_leverage(sample_deal):
    # A interest 304,335 == leverage interest 304,335
    assert waterfall.analyze(sample_deal).annual_fund_shortfall_a_only == 0


def test_sweep_interest_shortfall_only(sample_deal):
    # lev 20%: leverage 6,763,000 x 20% = 1,352,600 vs 334,705 -> short 1,017,895; no principal gap
    df = utils.credit_price_sensitivity(dataclasses.replace(sample_deal, leverage_loan_rate=0.20),
                                        prices=[0.83])
    assert list(df["Leverage Serviced"]) == ["NO: short $1,017,895/yr"]


def test_sweep_sub_dollar_gap_and_shortfall(sample_deal):
    d = dataclasses.replace(sample_deal, qlici_a_loan_amount=6_763_000 - 0.5)
    df = utils.credit_price_sensitivity(d, prices=[0.83])
    assert list(df["Leverage Serviced"]) == ["NO: principal gap $0"]
    be = 0.045 + 30_370 / 6_763_000
    d = dataclasses.replace(sample_deal, leverage_loan_rate=be + 0.5 / 6_763_000)
    df = utils.credit_price_sensitivity(d, prices=[0.83])
    assert list(df["Leverage Serviced"]) == ["NO: short $0/yr"]


def test_exact_zero_t0_flow_is_no_sign_change_not_irr_bound():
    # Reachable: QEI 45,000,000 at price 0.1282051282051282 (one ulp from 0.05/0.39) makes the
    # t=0 flow exactly 0.0 in floats (found by scanning QEIs and adjacent prices).
    d = NMTCDeal(project_name="Zero", total_project_cost=45_000_000, nmtc_allocation=45_000_000,
                 credit_price=0.1282051282051282, leverage_loan_rate=0.04, qlici_a_loan_rate=0.04,
                 qlici_b_loan_rate=0.01, cde_fee_rate=0.02)
    r = investor.analyze(d)
    assert r.cash_flows[0] == 0.0
    assert r.refused_code == "no_sign_change"
    assert "no sign change" in r.refused_reason
