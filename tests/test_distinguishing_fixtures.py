"""Fix round 1, X5: fixtures that separate quantities every earlier fixture made equal.

Every earlier fixture had total_project_cost == QEI and A loan == leverage loan,
so a formula that used the wrong one of each pair gave the same answer. This
deal separates them:

    QEI 10,000,000; project cost 12,500,000; credit price 0.83
    equity 3,237,000; leverage 6,763,000
    CDE fee 2% = 200,000; QLICI total 9,800,000
    A loan SUPPLIED 6,200,000 @ 4.5%; B loan DERIVED 3,600,000 @ 1.0%
    guarantee fee 1%; exit fee 0.5% of QEI = 50,000; forgiveness 90%; alt rate 7%

Expectations are hand-computed in the comments.
"""
import dataclasses
import warnings

import pytest

from nmtccalc import LeverageShortfallWarning, NMTCDeal, subsidy, transaction, utils, waterfall


@pytest.fixture
def distinct():
    return NMTCDeal(
        project_name="Distinct", total_project_cost=12_500_000, nmtc_allocation=10_000_000,
        credit_price=0.83, leverage_loan_rate=0.045, qlici_a_loan_rate=0.045,
        qlici_b_loan_rate=0.010, cde_fee_rate=0.02, qlici_a_loan_amount=6_200_000,
        guarantee_fee_rate=0.01, exit_fee_rate=0.005, b_loan_forgiveness_rate=0.9,
        qalicb_alternative_borrowing_rate=0.07,
    )


def test_fixture_separates_the_pairs(distinct):
    assert distinct.total_project_cost != distinct.qei
    assert distinct.qlici_a_loan != distinct.leverage_loan
    assert distinct.qlici_b_loan == pytest.approx(3_600_000)


def test_deployment_ratio_divides_by_qei_not_cost(distinct):
    # 9,800,000 / 10,000,000 (divided by cost it would be 0.784)
    assert transaction.structure(distinct).closing_qlici_deployment_ratio == pytest.approx(0.98, abs=1e-15)


def test_net_subsidy_pct_divides_by_cost_not_qei(distinct):
    # (3,600,000 x 0.9 - 50,000) / 12,500,000 = 3,190,000 / 12,500,000 (by QEI: 0.319)
    r = subsidy.analyze(distinct)
    assert r.net_subsidy == pytest.approx(3_190_000)
    assert r.net_subsidy_pct == pytest.approx(0.2552, abs=1e-15)


def test_leverage_to_equity_uses_leverage_loan_not_a_loan(distinct):
    # 6,763,000 / 3,237,000 (with the A loan as numerator: 1.9154)
    assert transaction.structure(distinct).leverage_loan_to_equity_ratio == pytest.approx(
        6_763_000 / 3_237_000, abs=1e-12)


def test_interest_savings_on_a_loan_not_leverage_loan(distinct):
    # (6,200,000 x 2.5% + 3,600,000 x 6%) x 7 = (155,000 + 216,000) x 7
    assert subsidy.analyze(distinct).interest_savings_to_unwind == pytest.approx(2_597_000)


def test_guarantee_fee_on_leverage_loan_not_a_loan(distinct):
    # 6,763,000 x 1% (on the A loan it would be 62,000)
    assert distinct.guarantee_fee_annual == pytest.approx(67_630)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = waterfall.analyze(dataclasses.replace(distinct, noi=600_000))
    assert r.years[0].guarantee_fee == pytest.approx(67_630)


def test_shortfall_warning_arguments_in_order(distinct):
    # lev 6,763,000 x 20% = 1,352,600; QLICI 6,200,000 x 4.5% + 3,600,000 x 1% = 279,000 + 36,000
    # = 315,000; short 1,037,600; x 7 = 7,263,200; principal gap 6,763,000 - 6,200,000 = 563,000
    with pytest.warns(LeverageShortfallWarning) as rec:
        r = waterfall.analyze(dataclasses.replace(distinct, leverage_loan_rate=0.20))
    assert str(rec[0].message) == (
        "LEVERAGE SHORTFALL: the Investment Fund cannot service its leverage loan from the "
        "modeled QLICI flows. Annual leverage interest $1,352,600 exceeds QLICI interest "
        "reaching the fund $315,000 by $1,037,600 per year ($7,263,200 over 7 years), and the "
        "A-loan principal repaid at unwind is $563,000 less than the leverage principal due. "
        "QALICB coverage (DSCR) does not measure this, because the leverage loan is the "
        "fund's debt, not the QALICB's.")
    # A-interest-only bracket: 1,352,600 - 279,000
    assert r.annual_fund_shortfall_a_only == pytest.approx(1_073_600)


def test_principal_gap_warning_text(distinct):
    with pytest.warns(LeverageShortfallWarning) as rec:
        waterfall.analyze(distinct)
    # A interest 279,000 + B 36,000 = 315,000 >= lev 304,335, so only the principal gap fires
    assert str(rec[0].message) == (
        "LEVERAGE SHORTFALL: the A-loan principal repaid to the fund at unwind ($6,200,000) "
        "is $563,000 less than the leverage loan principal due ($6,763,000).")


def test_a_only_shortfall_differs_from_a_plus_b(distinct, capsys):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = waterfall.analyze(distinct)
    # A only: 304,335 - 279,000 = 25,335 ; A+B: 0
    assert r.annual_fund_shortfall == 0
    assert r.annual_fund_shortfall_a_only == pytest.approx(25_335)
    r.summary()
    out = capsys.readouterr().out
    assert "Annual Fund Shortfall:      $0  (A and B interest)" in out
    assert "Shortfall, A interest only: $25,335" in out
    assert ("A / B Loan principal:       $6,200,000 [SUPPLIED: qlici_a_loan_amount] / "
            "$3,600,000 [DERIVED: QLICI total - A loan (SUPPLIED)]") in out


def test_sweep_leverage_column(distinct):
    # At 0.70: leverage 7,270,000; interest 327,150 vs 279,000 + 36,000 = 315,000 -> short 12,150;
    #          principal gap 7,270,000 - 6,200,000 = 1,070,000.
    # At 0.90: leverage 6,490,000; interest 292,050 < 315,000 -> no interest shortfall;
    #          principal gap 6,490,000 - 6,200,000 = 290,000.
    df = utils.credit_price_sensitivity(distinct, prices=[0.70, 0.90])
    assert list(df["Leverage Serviced"]) == [
        "NO: short $12,150/yr, principal gap $1,070,000",
        "NO: principal gap $290,000",
    ]


def test_sweep_leverage_column_yes(sample_deal):
    df = utils.credit_price_sensitivity(sample_deal, prices=[0.83])
    assert list(df["Leverage Serviced"]) == ["yes"]


def test_sweep_does_not_leak_warnings(distinct):
    with warnings.catch_warnings():
        warnings.simplefilter("error", LeverageShortfallWarning)
        utils.credit_price_sensitivity(distinct, prices=[0.70])


def test_subsidy_basis_column_with_supplied_a(distinct):
    df = subsidy.analyze(distinct).summary()
    basis = dict(zip(df["Item"], df["Basis"]))
    assert basis["B Loan to QALICB"] == "DERIVED: QLICI total - A loan (SUPPLIED)"
    assert basis["Investor Equity (into fund)"] == "DERIVED: total NMTCs x credit price"
    assert basis["B-Loan Forgiveness Rate"] == "SUPPLIED: b_loan_forgiveness_rate"
