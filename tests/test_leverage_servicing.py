"""Item 1: the leverage loan is serviced at the fund level and reconciled.

Figures are hand-computed from literals in the comments.
"""
import dataclasses
import warnings

import pytest

from nmtccalc import LeverageShortfallWarning, NMTCDeal, waterfall
from nmtccalc.models.waterfall import FUND_LINE_DISCLOSURE


def _deal(sample_deal, **kw):
    return dataclasses.replace(sample_deal, **kw)


def test_healthy_deal_is_serviced_without_warning(sample_deal):
    with warnings.catch_warnings():
        warnings.simplefilter("error", LeverageShortfallWarning)
        r = waterfall.analyze(sample_deal)
    # leverage 6,763,000 x 4.5% = 304,335; QLICI interest 304,335 + 3,037,000 x 1% = 334,705
    assert r.leverage_loan == pytest.approx(6_763_000)
    assert r.annual_leverage_interest == pytest.approx(304_335)
    assert r.annual_fund_qlici_interest == pytest.approx(334_705)
    assert r.annual_fund_shortfall == 0
    assert r.total_fund_shortfall == 0
    assert r.leverage_principal_gap == 0
    assert r.leverage_serviced is True
    assert r.warning_messages == ()
    assert r.years[0].fund_net_cash_flow == pytest.approx(30_370)


def test_audit_case_20pct_leverage_1pct_a_loan(sample_deal):
    d = _deal(sample_deal, leverage_loan_rate=0.20, qlici_a_loan_rate=0.01, noi=600_000)
    with pytest.warns(LeverageShortfallWarning, match="LEVERAGE SHORTFALL") as rec:
        r = waterfall.analyze(d)
    # lev 6,763,000 x 20% = 1,352,600; QLICI 67,630 + 30,370 = 98,000; short 1,254,600
    assert r.annual_leverage_interest == pytest.approx(1_352_600)
    assert r.annual_fund_qlici_interest == pytest.approx(98_000)
    assert r.annual_fund_shortfall == pytest.approx(1_254_600)
    assert r.total_fund_shortfall == pytest.approx(1_254_600 * 7)
    assert r.leverage_serviced is False
    assert len(rec) == 1
    msg = str(rec[0].message)
    assert "$1,352,600" in msg and "$98,000" in msg and "$1,254,600" in msg
    assert "$8,782,200 over 7 years" in msg
    for y in r.years:
        assert y.leverage_loan_interest == pytest.approx(1_352_600)
        assert y.fund_qlici_interest == pytest.approx(98_000)
        assert y.fund_net_cash_flow == pytest.approx(-1_254_600)


def test_leverage_rate_now_moves_the_waterfall(sample_deal):
    lo = _deal(sample_deal, leverage_loan_rate=0.01, qlici_a_loan_rate=0.01, noi=600_000)
    hi = _deal(sample_deal, leverage_loan_rate=0.20, qlici_a_loan_rate=0.01, noi=600_000)
    r_lo = waterfall.analyze(lo)
    with pytest.warns(LeverageShortfallWarning):
        r_hi = waterfall.analyze(hi)
    assert r_lo.to_dict() != r_hi.to_dict()
    assert r_lo.annual_fund_shortfall == 0
    assert r_hi.annual_fund_shortfall > 1_000_000


def test_shortfall_boundary_exact(sample_deal):
    # Fund breaks even when lev_rate x 6,763,000 == 6,763,000 x a_rate + 30,370.
    # With a_rate = 4.5%: lev_rate = 0.045 + 30,370/6,763,000.
    be = 0.045 + 30_370 / 6_763_000
    with warnings.catch_warnings():
        warnings.simplefilter("error", LeverageShortfallWarning)
        r = waterfall.analyze(_deal(sample_deal, leverage_loan_rate=be - 1e-9))
    assert r.annual_fund_shortfall == 0
    with pytest.warns(LeverageShortfallWarning):
        r = waterfall.analyze(_deal(sample_deal, leverage_loan_rate=be + 1e-6))
    assert r.annual_fund_shortfall == pytest.approx(6_763_000 * 1e-6, rel=1e-3)


def test_shortfall_total_scales_with_unwind_year(sample_deal):
    d = _deal(sample_deal, leverage_loan_rate=0.10, unwind_year=4)
    with pytest.warns(LeverageShortfallWarning, match="over 4 years"):
        r = waterfall.analyze(d)
    # 676,300 - 334,705 = 341,595
    assert r.annual_fund_shortfall == pytest.approx(341_595)
    assert r.total_fund_shortfall == pytest.approx(341_595 * 4)


def test_dscr_is_qalicb_level_and_unchanged_by_leverage(sample_deal):
    lo = waterfall.analyze(_deal(sample_deal, noi=600_000))
    with pytest.warns(LeverageShortfallWarning):
        hi = waterfall.analyze(_deal(sample_deal, noi=600_000, leverage_loan_rate=0.20))
    assert lo.years[0].dscr == pytest.approx(hi.years[0].dscr)
    assert lo.years[0].dscr == pytest.approx(600_000 / 334_705)


def test_summary_renders_fund_line_and_warning(sample_deal, capsys):
    with pytest.warns(LeverageShortfallWarning):
        r = waterfall.analyze(_deal(sample_deal, leverage_loan_rate=0.20, qlici_a_loan_rate=0.01))
    df = r.summary()
    out = capsys.readouterr().out
    assert "Investment Fund (leverage loan):" in out
    assert "Annual Fund Shortfall:      $1,254,600" in out
    assert "LEVERAGE SHORTFALL" in out
    assert FUND_LINE_DISCLOSURE in out
    assert "neither a floor nor a ceiling" in out
    assert list(df["Lev. Int."])[0] == "$1,352,600"
    assert list(df["Fund Net"])[0] == "$-1,254,600"


def test_summary_healthy_has_no_warning(sample_deal, capsys):
    waterfall.analyze(sample_deal).summary()
    out = capsys.readouterr().out
    assert "LEVERAGE SHORTFALL" not in out
    assert "Annual Fund Shortfall:      $0" in out


def test_to_dict_carries_fund_figures(sample_deal):
    with pytest.warns(LeverageShortfallWarning):
        d = waterfall.analyze(_deal(sample_deal, leverage_loan_rate=0.20, qlici_a_loan_rate=0.01)).to_dict()
    assert d["annual_fund_shortfall"] == pytest.approx(1_254_600)
    assert d["total_fund_shortfall"] == pytest.approx(1_254_600 * 7)
    assert d["leverage_serviced"] is False
    assert d["leverage_principal_due"] == pytest.approx(6_763_000)
    assert d["a_loan_principal_repaid"] == pytest.approx(6_763_000)
    assert d["leverage_principal_gap"] == 0
    assert d["annual_leverage_interest"] == pytest.approx(1_352_600)
    assert d["annual_fund_qlici_interest"] == pytest.approx(98_000)
    assert d["leverage_loan"] == pytest.approx(6_763_000)


def test_warning_is_a_userwarning():
    assert issubclass(LeverageShortfallWarning, UserWarning)
