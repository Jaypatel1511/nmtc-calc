"""Item 0: §45D(a)(3) credit-allowance timing and the 7-year recapture period.

Expected values are hand-computed from literals (see the comments), never from
the package's own properties, so a regression in either direction goes red.
"""
import dataclasses

import pytest

from nmtccalc import NMTCDeal, credits, investor, statute, utils, waterfall


# ── statute constants ────────────────────────────────────────────────────────

def test_allowance_dates_are_qei_date_plus_six_anniversaries():
    # §45D(a)(3): the date the QEI is made, and each of the 6 anniversaries.
    assert statute.CREDIT_ALLOWANCE_YEARS == (0, 1, 2, 3, 4, 5, 6)


def test_applicable_percentages_per_45d_a_2():
    assert statute.APPLICABLE_PERCENTAGES == (0.05, 0.05, 0.05, 0.06, 0.06, 0.06, 0.06)


def test_total_credit_rate_is_derived_39pct():
    assert statute.TOTAL_CREDIT_RATE == pytest.approx(0.39, abs=1e-15)


def test_recapture_period_ends_at_seven():
    assert statute.RECAPTURE_PERIOD_END_YEAR == 7
    assert statute.CREDIT_PERIOD_YEARS == 7


@pytest.mark.parametrize("k, inside", [(1, True), (4, True), (6, True), (7, False), (8, False)])
def test_unwind_in_recapture_period(k, inside):
    assert statute.unwind_in_recapture_period(k) is inside


def test_statuses_unwind_at_seven_all_allowed():
    assert statute.allowance_statuses(7) == ("ALLOWED",) * 7


def test_statuses_unwind_at_four():
    assert statute.allowance_statuses(4) == (
        "RECAPTURED", "RECAPTURED", "RECAPTURED", "RECAPTURED",
        "NOT ALLOWABLE", "NOT ALLOWABLE", "NOT ALLOWABLE",
    )


def test_statuses_unwind_at_one():
    assert statute.allowance_statuses(1) == ("RECAPTURED",) + ("NOT ALLOWABLE",) * 6


def test_pct_label():
    assert statute.pct_label(0.05) == "5%"
    assert statute.pct_label(0.39) == "39%"


def test_citations_name_the_right_provisions():
    # The 39% goes to the ATG, never to §45D.
    assert "Audit Technique Guide" in statute.CITATION_TOTAL_RATE
    assert "45D" not in statute.CITATION_TOTAL_RATE
    assert statute.CITATION_REDEMPTION == "26 U.S.C. §45D(g)(3)(C)"
    assert "1.45D-1(c)(5)(i)" in statute.CITATION_RECAPTURE_PERIOD
    assert "§45D(g)(1)" in statute.CITATION_RECAPTURE_PERIOD


# ── credit schedule ──────────────────────────────────────────────────────────

def test_allowance_years_on_result(sample_deal):
    assert credits.schedule(sample_deal).allowance_years == [0, 1, 2, 3, 4, 5, 6]


def test_pv_credits_on_statutory_dates(sample_deal):
    # 500000*(1 + 1/1.08 + 1/1.08**2) + 600000*sum(1/1.08**t for t in 3..6)
    assert credits.schedule(sample_deal).pv_credits == pytest.approx(3_095_401.3237539427, abs=0.01)


def test_pv_credits_is_8pct_above_the_t1_convention(sample_deal):
    # 0.2.1 discounted from t=1..7: 2,866,112.3368. One year of discount at 8%.
    assert credits.schedule(sample_deal).pv_credits / 2_866_112.336809206 == pytest.approx(1.08, abs=1e-9)


def test_first_credit_is_undiscounted(sample_deal):
    r = credits.schedule(dataclasses.replace(sample_deal, discount_rate=0.50))
    # at 50% only the t=0 credit keeps full value; the rest shrink geometrically
    expected = sum(c / 1.5 ** t for t, c in enumerate([500_000] * 3 + [600_000] * 4))
    assert r.pv_credits == pytest.approx(expected, abs=0.01)


def test_default_unwind_retains_all_credits(sample_deal):
    r = credits.schedule(sample_deal)
    assert r.unwind_year == 7
    assert r.in_recapture_period is False
    assert r.statuses == ["ALLOWED"] * 7
    assert r.net_credits_retained == pytest.approx(3_900_000)


@pytest.mark.parametrize("k", [1, 2, 3, 4, 5, 6])
def test_unwind_inside_period_retains_nothing(sample_deal, k):
    r = credits.schedule(dataclasses.replace(sample_deal, unwind_year=k))
    assert r.in_recapture_period is True
    assert r.net_credits_retained == 0
    assert r.statuses.count("RECAPTURED") == k
    assert r.statuses.count("NOT ALLOWABLE") == 7 - k


def test_unwind_after_period_retains_all(sample_deal):
    r = credits.schedule(dataclasses.replace(sample_deal, unwind_year=10))
    assert r.in_recapture_period is False
    assert r.net_credits_retained == pytest.approx(3_900_000)


def test_credit_summary_labels_derived_from_statute(sample_deal, capsys):
    df = credits.schedule(sample_deal).summary()
    assert list(df["Credit Rate"]) == ["5%", "5%", "5%", "6%", "6%", "6%", "6%"]
    assert list(df["Allowance Date"])[0] == "t=0 (QEI date)"
    assert list(df["Allowance Date"])[-1] == "t=6"
    out = capsys.readouterr().out
    assert "(39% × QEI)" in out
    assert "NET CREDITS RETAINED: $3,900,000" in out
    assert "t=0 (the QEI date) through t=6" in out
    assert "whole years" in out  # t=7 boundary disclosure


def test_credit_summary_recapture_renders(sample_deal, capsys):
    df = credits.schedule(dataclasses.replace(sample_deal, unwind_year=4)).summary()
    assert list(df["Status"]) == ["RECAPTURED"] * 4 + ["NOT ALLOWABLE"] * 3
    out = capsys.readouterr().out
    assert "NET CREDITS RETAINED: $0" in out
    assert "§45D(g)(3)(C)" in out
    assert "inside the 7-year recapture period" in out
    assert "not deductible" in out


def test_credit_summary_after_period_has_no_boundary_or_recapture_note(sample_deal, capsys):
    credits.schedule(dataclasses.replace(sample_deal, unwind_year=9)).summary()
    out = capsys.readouterr().out
    assert "whole years" not in out
    assert "recapture event" not in out


def test_credit_to_dict_carries_timing(sample_deal):
    d = credits.schedule(dataclasses.replace(sample_deal, unwind_year=3)).to_dict()
    assert d["allowance_years"] == [0, 1, 2, 3, 4, 5, 6]
    assert d["unwind_year"] == 3
    assert d["in_recapture_period"] is True
    assert d["net_credits_retained"] == 0
    assert d["statuses"][3] == "NOT ALLOWABLE"


# ── investor ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("price, expected", [
    (0.75, 0.10197587819540688),
    (0.83, 0.06336263201148207),
    (0.90, 0.034722764509748205),
])
def test_irr_on_statutory_dates(sample_deal, price, expected):
    # Independent bisection on [-0.39*QEI*p + 500000, 500000, 500000, 600000 x4].
    r = investor.analyze(dataclasses.replace(sample_deal, credit_price=price))
    assert r.irr == pytest.approx(expected, abs=1e-9)


def test_cash_flows_net_equity_and_first_credit_at_t0(sample_deal):
    r = investor.analyze(sample_deal)
    assert r.cash_flows == pytest.approx(
        [-2_737_000, 500_000, 500_000, 600_000, 600_000, 600_000, 600_000])


def test_moic_literal(sample_deal):
    # 3,900,000 / 3,237,000
    assert investor.analyze(sample_deal).moic == pytest.approx(1.2048192771084338, abs=1e-12)


@pytest.mark.parametrize("k", [1, 4, 6])
def test_investor_refused_inside_recapture_period(sample_deal, k):
    r = investor.analyze(dataclasses.replace(sample_deal, unwind_year=k))
    assert r.irr is None
    assert r.moic is None
    assert r.refused_reason.startswith("REFUSED")
    assert f"t={k}" in r.refused_reason
    assert r.net_credits_retained == 0
    assert r.gross_benefit == 0
    assert r.net_benefit == pytest.approx(-3_237_000)
    assert r.in_recapture_period is True


def test_investor_not_refused_at_seven(sample_deal):
    r = investor.analyze(sample_deal)
    assert r.refused_reason is None
    assert r.gross_benefit == pytest.approx(3_900_000)
    assert r.net_benefit == pytest.approx(663_000)


def test_investor_summary_refused(sample_deal, capsys):
    investor.analyze(dataclasses.replace(sample_deal, unwind_year=4)).summary()
    out = capsys.readouterr().out
    assert "MOIC:                 REFUSED" in out
    assert "IRR:                  REFUSED" in out
    assert "NET CREDITS RETAINED: $0" in out
    assert "Net Benefit:          $-3,237,000" in out
    assert "§45D(g)(3)(C)" in out


def test_investor_summary_normal(sample_deal, capsys):
    df = investor.analyze(sample_deal).summary()
    out = capsys.readouterr().out
    assert "IRR:                  6.3%" in out
    assert "MOIC:                 1.20x" in out
    assert list(df["Allowance Date"]) == [f"t={t}" for t in range(7)]
    assert "recapture event" not in out


def test_irr_refused_without_sign_change(sample_deal):
    # At p <= 0.05/0.39 = 0.128205..., the t=0 credit covers the equity.
    r = investor.analyze(dataclasses.replace(sample_deal, credit_price=0.12))
    assert r.irr is None
    assert r.moic == pytest.approx(1 / 0.12)
    assert "no sign change" in r.refused_reason
    assert "0.1282" in r.refused_reason


def test_irr_just_above_threshold_is_finite(sample_deal):
    r = investor.analyze(dataclasses.replace(sample_deal, credit_price=0.13))
    assert r.irr is not None and r.irr > 10


def test_compute_irr_rejects_bad_shapes():
    assert investor._compute_irr([]) is None
    assert investor._compute_irr([100, 50]) is None
    assert investor._compute_irr([-100, -50]) is None
    assert investor._compute_irr([-100, 50, -10, 80]) is None
    assert investor._compute_irr([-100, 0, 0]) is None


def test_compute_irr_simple():
    assert investor._compute_irr([-100, 110]) == pytest.approx(0.10, abs=1e-10)
    assert investor._compute_irr([-100, 0, 121]) == pytest.approx(0.10, abs=1e-10)
    assert investor._compute_irr([-100, 90]) == pytest.approx(-0.10, abs=1e-10)


def test_compute_irr_large_root_expands_bracket():
    assert investor._compute_irr([-1, 10]) == pytest.approx(9.0, abs=1e-8)


def test_investor_to_dict(sample_deal):
    d = investor.analyze(dataclasses.replace(sample_deal, unwind_year=5)).to_dict()
    assert d["irr"] is None and d["moic"] is None
    assert d["unwind_year"] == 5
    assert d["refused_reason"].startswith("REFUSED")
    assert d["cash_flows"][0] == pytest.approx(-2_737_000)


# ── waterfall and sweep ──────────────────────────────────────────────────────

def test_waterfall_unwinds_at_unwind_year(sample_deal):
    r = waterfall.analyze(dataclasses.replace(sample_deal, unwind_year=4, noi=600_000,
                                              b_loan_forgiveness_rate=1.0))
    assert [y.year for y in r.years] == [1, 2, 3, 4]
    assert r.years[-1].b_loan_forgiven == pytest.approx(3_037_000)
    assert all(y.b_loan_forgiven == 0 for y in r.years[:-1])
    assert r.in_recapture_period is True
    # 6,763,000*0.045 + 3,037,000*0.010 = 334,705 per year
    assert r.total_interest_paid == pytest.approx(334_705 * 4)


def test_waterfall_summary_recapture(sample_deal, capsys):
    waterfall.analyze(dataclasses.replace(sample_deal, unwind_year=5)).summary()
    out = capsys.readouterr().out
    assert "Unwind at t=5:" in out
    assert "§45D(g)(3)(C)" in out


def test_waterfall_summary_default_boundary(sample_deal, capsys):
    waterfall.analyze(sample_deal).summary()
    out = capsys.readouterr().out
    assert "Unwind at t=7:" in out
    assert "whole years" in out


def test_sweep_renders_refused_inside_period(sample_deal):
    df = utils.credit_price_sensitivity(dataclasses.replace(sample_deal, unwind_year=4),
                                        prices=[0.80, 0.85])
    assert list(df["IRR"]) == ["REFUSED", "REFUSED"]
    assert list(df["MOIC"]) == ["REFUSED", "REFUSED"]


def test_sweep_irr_column_statutory(sample_deal):
    df = utils.credit_price_sensitivity(sample_deal, prices=[0.75, 0.83, 0.90])
    assert list(df["IRR"]) == ["10.2%", "6.3%", "3.5%"]


# ── schema ───────────────────────────────────────────────────────────────────

def test_compliance_years_is_gone(sample_deal):
    assert "compliance_years" not in {f.name for f in dataclasses.fields(NMTCDeal)}
    with pytest.raises(TypeError):
        dataclasses.replace(sample_deal, compliance_years=7)


@pytest.mark.parametrize("bad", [0, -1])
def test_unwind_year_must_be_positive(sample_deal, bad):
    with pytest.raises(ValueError, match="at least 1"):
        dataclasses.replace(sample_deal, unwind_year=bad)


@pytest.mark.parametrize("bad", [4.5, True, "7", None])
def test_unwind_year_must_be_whole(sample_deal, bad):
    with pytest.raises(ValueError, match="whole number"):
        dataclasses.replace(sample_deal, unwind_year=bad)


def test_total_nmtcs_literal(sample_deal):
    assert sample_deal.total_nmtcs == pytest.approx(3_900_000, abs=1e-6)


def test_waterfall_unwind_label_follows_unwind_year(sample_deal, capsys):
    waterfall.analyze(dataclasses.replace(sample_deal, unwind_year=4, b_loan_forgiveness_rate=1.0)).summary()
    out = capsys.readouterr().out
    assert "Net Subsidy at Unwind (t=4): $3,037,000" in out
    assert "Y7" not in out
