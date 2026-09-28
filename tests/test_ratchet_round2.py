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


# ── fix round 2 ─────────────────────────────────────────────────────────────

def test_dscr_refused_on_zero_principal_not_only_zero_coupon(sample_deal):
    # R1-3: B principal SUPPLIED as 0 (at a 1% coupon), A at 0%: both interest lines are 0.
    d = dataclasses.replace(sample_deal, noi=600_000, qlici_b_loan_amount=0.0, qlici_a_loan_rate=0.0,
                            leverage_loan_rate=0.0)
    r = waterfall.analyze(d)
    assert d.qlici_b_loan == 0 and d.qlici_b_loan_rate == 0.01
    assert r.dscr_refused_reason.startswith(
        "DSCR REFUSED: debt service <= 0 (A-loan and B-loan interest are both zero, each from a "
        "zero principal or a 0% coupon)")


def test_credit_only_note_full_text():
    # R1-4: the whole note, typed here, so any dropped clause goes red.
    from nmtccalc.models import investor as inv_mod
    assert inv_mod.CREDIT_ONLY_NOTE == (
        "CREDIT-ONLY: these cash flows are the equity paid and the credits received, and nothing "
        "else: no fund-level taxable income or tax drag, no put or disposition value, no exit tax, "
        "no sub-annual timing, no §45D(h) basis reduction, no §38 tax-capacity limit. Investor "
        "equity is always total NMTCs x credit price, so every flow is proportional to QEI. When "
        "they are computed, both figures depend on no deal input except the credit price: "
        "credit-only MOIC = 1 / credit price, and two deals at the same price report the same "
        "credit-only IRR whatever their size, rates or fees. Both are REFUSED when the unwind "
        "falls inside the 7-year recapture period. They are not an investor IRR or MOIC.")
    assert "§38" in inv_mod.CREDIT_ONLY_NOTE and "whatever their size, rates or fees" in inv_mod.CREDIT_ONLY_NOTE


def test_sweep_no_sign_change_label(sample_deal):
    df = utils.credit_price_sensitivity(dataclasses.replace(sample_deal, cde_fee_rate=0.001), prices=[0.10])
    assert df.iloc[0]["Credit-only IRR"] == "REFUSED (no sign change)"
    assert df.iloc[0]["Credit-only MOIC"] == 10.0


def test_sweep_irr_bound_label(sample_deal):
    # a 2% fee exceeds 39% x 0.128 (negative B), so use a small-fee deal
    d = dataclasses.replace(sample_deal, cde_fee_rate=0.001)
    df = utils.credit_price_sensitivity(d, prices=[0.05 / 0.39 + 1e-10])
    assert df.iloc[0]["Credit-only IRR"] == "REFUSED (IRR above solver search range)"


def test_total_nmtcs_labelled_in_credit_and_investor_summaries(sample_deal, capsys):
    from nmtccalc import credits
    credits.schedule(sample_deal).summary()
    out = capsys.readouterr().out
    assert "Total NMTCs:          $3,900,000  [DERIVED: 39% x QEI" in out
    investor.analyze(sample_deal).summary()
    out = capsys.readouterr().out
    assert "Total NMTCs:          $3,900,000  [DERIVED: 39% x QEI" in out


def test_sweep_basis_and_leverage_notes(sample_deal, capsys):
    utils.credit_price_sensitivity(sample_deal, prices=[0.8])
    out = capsys.readouterr().out
    assert utils.SWEEP_BASIS_NOTE == (
        "Equity ($MM) and Leverage Loan ($MM) are DERIVED at each price: equity = total NMTCs x "
        "price; leverage loan = QEI - equity (two-source fund).")
    assert utils.SWEEP_BASIS_NOTE in out
    assert "the waterfall's A-interest-only bracket is omitted here" in utils.LEVERAGE_COLUMN_NOTE


def test_irr_search_max_is_derived():
    from nmtccalc.models import investor as inv_mod
    assert inv_mod.IRR_SEARCH_MAX == 2.0 ** 29
    assert inv_mod.IRR_SEARCH_MAX <= inv_mod.IRR_BRACKET_CAP < inv_mod.IRR_SEARCH_MAX * inv_mod.IRR_BRACKET_GROWTH


# ── fix round 3: sign before the currency symbol ────────────────────────────

def test_money_helper_sign_placement():
    from nmtccalc._format import money
    assert money(-0.00039, ".4g") == "-$0.00039"
    assert money(-3_237_000) == "-$3,237,000"
    assert money(1_254_600) == "$1,254,600"
    assert money(0.0) == "$0"
    assert money(-1.5e6 / 1e6, ".2f") == "-$1.50"


def test_negative_money_renders_sign_first_everywhere(sample_deal, capsys):
    from nmtccalc import subsidy as sub
    # net subsidy negative: forgiveness 0%, exit fee 50,000; savings negative: alt rate 0%
    d = dataclasses.replace(sample_deal, b_loan_forgiveness_rate=0.0, exit_fee_rate=0.005,
                            qalicb_alternative_borrowing_rate=0.0, noi=[100_000] * 7,
                            unwind_year=7)
    df = sub.analyze(d).summary()
    v = dict(zip(df["Item"], df["Value"]))
    assert v["Net Subsidy at Unwind (t=7)"] == "-$0.05MM"
    assert v["Interest Savings to Unwind (7 yrs)"] == "-$2.34MM"   # -334,705 x 7
    out = capsys.readouterr().out
    wf = waterfall.analyze(d)
    df = wf.summary()
    assert list(df["Net CF"])[0] == "-$234,705"                     # 100,000 - 334,705
    out = capsys.readouterr().out
    assert "Net Subsidy at Unwind (t=7): -$50,000" in out
    assert "$-" not in out
