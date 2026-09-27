"""First mutation-gate ratchet (audit §4 item 7a / §9 item 4).

Each test here kills survivors from the first campaign: validation boundaries
(six of the ten 0.2.1 validations were still deletable with the suite green),
rendered figures that could be scaled by 1.1 unnoticed, and solver edges.
Every expectation is a literal or a raise.
"""
import dataclasses
import warnings

import pytest

from nmtccalc import (
    LeverageShortfallWarning, NMTCDeal, credits, investor, statute, transaction,
    utils, waterfall,
)

BASE = dict(
    project_name="P", total_project_cost=10_000_000, nmtc_allocation=10_000_000,
    credit_price=0.83, leverage_loan_rate=0.045, qlici_a_loan_rate=0.045,
    qlici_b_loan_rate=0.010, cde_fee_rate=0.02,
)


def deal(**kw):
    return NMTCDeal(**{**BASE, **kw})


# ── the ten 0.2.1 validations, at their boundaries ───────────────────────────

@pytest.mark.parametrize("v", [0, -1])
def test_total_project_cost_must_be_positive(v):
    with pytest.raises(ValueError, match="total_project_cost must be positive"):
        deal(total_project_cost=v, nmtc_allocation=1)


def test_total_project_cost_one_dollar_is_positive():
    d = deal(total_project_cost=1, nmtc_allocation=1)
    assert d.qei == 1


@pytest.mark.parametrize("v", [0, -1])
def test_allocation_must_be_positive(v):
    with pytest.raises(ValueError, match=r"nmtc_allocation \(QEI\) must be positive"):
        deal(nmtc_allocation=v)


def test_allocation_equal_to_cost_allowed():
    assert deal(total_project_cost=5_000_000, nmtc_allocation=5_000_000).qei == 5_000_000


def test_allocation_above_cost_refused():
    with pytest.raises(ValueError, match="cannot exceed"):
        deal(total_project_cost=5_000_000, nmtc_allocation=5_000_001)


@pytest.mark.parametrize("v", [0, 1, 1.5, -0.1])
def test_credit_price_open_interval(v):
    with pytest.raises(ValueError, match="credit_price must be between 0 and 1"):
        deal(credit_price=v)


@pytest.mark.parametrize("v", [0, 1, 1.5, -0.1])
def test_cde_fee_rate_open_interval(v):
    with pytest.raises(ValueError, match="cde_fee_rate must be between 0 and 1"):
        deal(cde_fee_rate=v)


@pytest.mark.parametrize("v", [0, 1, 1.5, -0.1])
def test_discount_rate_open_interval(v):
    with pytest.raises(ValueError, match="discount_rate must be between 0 and 1"):
        deal(discount_rate=v)


def test_noi_negative_refused():
    with pytest.raises(ValueError, match="noi must be non-negative"):
        deal(noi=-1)


@pytest.mark.parametrize("v", [0, 0.5])
def test_noi_zero_and_small_allowed(v):
    assert deal(noi=v).noi == v


def test_guarantee_fee_negative_refused():
    with pytest.raises(ValueError, match="guarantee_fee_rate must be non-negative"):
        deal(guarantee_fee_rate=-0.001)


def test_exit_fee_negative_refused():
    with pytest.raises(ValueError, match="exit_fee_rate must be non-negative"):
        deal(exit_fee_rate=-0.001)


def test_zero_fees_allowed():
    d = deal(guarantee_fee_rate=0, exit_fee_rate=0)
    assert d.guarantee_fee_annual == 0 and d.exit_fee == 0


def test_unwind_year_one_allowed():
    assert deal(unwind_year=1).unwind_year == 1


def test_default_discount_rate_is_8pct():
    assert deal().discount_rate == 0.08


# ── rendered and convenience figures ─────────────────────────────────────────

def test_repr_literal():
    assert repr(deal()) == "NMTCDeal(project='P', QEI=$10.0MM, NMTCs=$3.90MM, credit_price=$0.83)"


def test_mm_properties():
    d = deal(total_project_cost=12_500_000, nmtc_allocation=10_000_000)
    assert d.qei_mm == 10.0
    assert d.total_project_cost_mm == 12.5


def test_pct_label_rounding():
    assert statute.pct_label(0.99) == "99%"
    assert statute.pct_label(0.25) == "25%"


def test_credit_summary_header_figures(capsys):
    credits.schedule(deal()).summary()
    out = capsys.readouterr().out
    assert "QEI: $10.00MM  |  Total NMTCs (39% × QEI): $3.90MM" in out
    assert "(@ 8.0% discount rate, before any recapture)" in out


def test_investor_summary_header_and_reason(capsys):
    investor.analyze(deal()).summary()
    out = capsys.readouterr().out
    assert "Equity In (t=0): $3.24MM  |  Credit Price: $0.83/$1" in out
    investor.analyze(deal(unwind_year=2)).summary()
    out = capsys.readouterr().out
    assert "REFUSED: the unwind at t=2 is inside the 7-year recapture period" in out


def test_investor_summary_no_sign_change_reason(capsys):
    investor.analyze(deal(credit_price=0.10)).summary()
    out = capsys.readouterr().out
    assert "no sign change" in out
    assert "Credit-only MOIC:     10.00x" in out


def test_transaction_summary_amounts():
    d = deal(total_project_cost=12_000_000)
    df = transaction.structure(d).summary()
    amounts = dict(zip(df["Item"], df["Amount"]))
    assert amounts["Total Project Cost"] == "$12.00MM"
    assert amounts["── QEI (NMTC Allocation)"] == "$10.00MM"
    assert amounts["── Total NMTCs (39% × QEI)"] == "$3.90MM"
    assert amounts["── Investor Equity"] == "$3.24MM"
    assert amounts["── Leverage Loan"] == "$6.76MM"
    assert amounts["── Total QEI"] == "$10.00MM"
    assert amounts["── CDE Fee"] == "$0.20MM"
    assert amounts["── Total QLICI"] == "$9.80MM"
    assert amounts["── A Loan (Senior)"] == "$6.76MM"
    assert amounts["── B Loan (Subordinate)"] == "$3.04MM"
    assert amounts["── Credit Price"] == "$0.83 per $1 of NMTCs"
    assert amounts["── NMTC Coverage"] == "32.5% of project cost"
    assert amounts["── Leverage Loan / Equity"] == "2.09x"


def test_transaction_ratios_literal():
    r = transaction.structure(deal(total_project_cost=12_000_000))
    assert r.nmtc_coverage == pytest.approx(3_900_000 / 12_000_000, abs=1e-15)
    assert r.leverage_loan_to_equity_ratio == pytest.approx(6_763_000 / 3_237_000, abs=1e-12)


# ── waterfall edges ──────────────────────────────────────────────────────────

def test_net_cash_flow_literal_with_guarantee_fee():
    r = waterfall.analyze(deal(noi=600_000, guarantee_fee_rate=0.01))
    # 600,000 - 334,705 - 6,763,000 x 1%
    assert r.years[0].net_cash_flow == pytest.approx(197_665)


def test_dscr_none_when_debt_service_zero():
    r = waterfall.analyze(deal(noi=600_000, qlici_a_loan_rate=0.0, qlici_b_loan_rate=0.0,
                               leverage_loan_rate=0.0))
    assert all(y.dscr is None for y in r.years)
    assert r.avg_dscr is None and r.min_dscr is None


def test_dscr_computed_for_tiny_debt_service():
    r = waterfall.analyze(deal(noi=1.0, qlici_a_loan_rate=1e-9, qlici_b_loan_rate=1e-9,
                               leverage_loan_rate=0.0))
    # total debt service = (6,763,000 + 3,037,000) x 1e-9 = 0.0098
    assert r.years[0].dscr == pytest.approx(1.0 / 0.0098)


def test_sub_dollar_interest_shortfall_still_warns():
    be = 0.045 + 30_370 / 6_763_000
    with pytest.warns(LeverageShortfallWarning) as rec:
        r = waterfall.analyze(deal(leverage_loan_rate=be + 0.5 / 6_763_000))
    assert r.annual_fund_shortfall == pytest.approx(0.5, abs=1e-3)
    assert "A-loan principal" not in str(rec[0].message)


def test_sub_dollar_principal_gap_still_warns():
    with pytest.warns(LeverageShortfallWarning, match="A-loan principal repaid"):
        r = waterfall.analyze(deal(qlici_a_loan_amount=6_763_000 - 0.5))
    assert r.leverage_principal_gap == pytest.approx(0.5)


def test_interest_shortfall_message_mentions_principal_only_when_gap():
    with pytest.warns(LeverageShortfallWarning) as rec:
        waterfall.analyze(deal(leverage_loan_rate=0.20))
    assert "A-loan principal" not in str(rec[0].message)
    with pytest.warns(LeverageShortfallWarning) as rec:
        waterfall.analyze(deal(leverage_loan_rate=0.20, qlici_a_loan_amount=6_763_000 - 0.5))
    # gap is $0.50, which ",.0f" renders as "$0"
    assert "A-loan principal repaid at unwind is $0 less" in str(rec[0].message)


def test_warning_points_at_the_caller():
    with pytest.warns(LeverageShortfallWarning) as rec:
        waterfall.analyze(deal(leverage_loan_rate=0.20))
    assert rec[0].filename == __file__


def test_exit_fee_line_only_when_nonzero(capsys):
    waterfall.analyze(deal()).summary()
    assert "Exit Fee:" not in capsys.readouterr().out
    waterfall.analyze(deal(exit_fee_rate=0.005)).summary()
    assert "Exit Fee:         ($50,000)" in capsys.readouterr().out


# ── solver edges ─────────────────────────────────────────────────────────────

def test_irr_with_tiny_inflow():
    # root r = 0.5/100 - 1 = -0.995
    assert investor._compute_irr([-100, 0.5]) == pytest.approx(-0.995, abs=1e-9)


# ── sweep defaults and columns ───────────────────────────────────────────────

def test_credit_price_sweep_default_prices_and_columns():
    df = utils.credit_price_sensitivity(deal())
    assert list(df["Credit Price"]) == [f"${p/100:.2f}" for p in range(70, 92, 2)]
    assert df.iloc[0]["Leverage Loan ($MM)"] == pytest.approx(7.27)   # 10 - 3.9 x 0.70
    assert df.iloc[-1]["Leverage Loan ($MM)"] == pytest.approx(6.49)
    assert df.iloc[0]["Credit-only MOIC"] == pytest.approx(1.429)                 # round(1/0.70, 3)
    assert df.iloc[0]["Equity ($MM)"] == pytest.approx(2.73)


def test_discount_rate_sweep_default_rates_and_columns():
    df = utils.discount_rate_sensitivity(deal())
    assert list(df["Discount Rate"]) == [f"{r}%" for r in range(5, 13)]
    row8 = df[df["Discount Rate"] == "8%"].iloc[0]
    assert row8["PV of Credits ($MM)"] == pytest.approx(3.095)
    # 3,095,401.32 / 3,900,000
    assert row8["PV / Face Value"] == "79.4%"


def test_credit_price_sweep_leverage_rounds_to_cents_of_mm():
    df = utils.credit_price_sensitivity(deal(), prices=[0.82])
    # 10,000,000 - 3,900,000 x 0.82 = 6,802,000 -> 6.8 at two decimals (6.802 at three)
    assert df.iloc[0]["Leverage Loan ($MM)"] == 6.8


def test_discount_rate_label_percent():
    df = utils.discount_rate_sensitivity(deal(), rates=[0.99])
    assert list(df["Discount Rate"]) == ["99%"]
