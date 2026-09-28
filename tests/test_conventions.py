"""Item 11: the two convention claims."""
import dataclasses
import inspect

import pytest

from nmtccalc import statute, waterfall
from nmtccalc.data import schema
from nmtccalc.models import credits, waterfall as wf_mod


def test_house_default_excludes_guarantee_fee(sample_deal):
    assert schema.HOUSE_GUARANTEE_FEE_IN_DSCR is False
    r = waterfall.analyze(dataclasses.replace(sample_deal, noi=600_000, guarantee_fee_rate=0.01))
    assert r.guarantee_fee_in_dscr is False
    assert r.years[0].dscr == pytest.approx(600_000 / 334_705)


def test_opposite_treatment_includes_fee(sample_deal):
    r = waterfall.analyze(dataclasses.replace(sample_deal, noi=600_000, guarantee_fee_rate=0.01,
                                              include_guarantee_fee_in_dscr=True))
    # 334,705 + 6,763,000 x 1% = 402,335
    assert r.guarantee_fee_in_dscr is True
    assert r.years[0].dscr == pytest.approx(600_000 / 402_335)
    # net cash flow deducts the fee either way
    assert r.years[0].net_cash_flow == pytest.approx(600_000 - 402_335)


def test_election_rendered_both_ways(sample_deal, capsys):
    waterfall.analyze(dataclasses.replace(sample_deal, noi=600_000)).summary()
    out = capsys.readouterr().out
    assert "HOUSE ELECTION: guarantee fees are excluded from the DSCR denominator" in out
    assert "include_guarantee_fee_in_dscr=True" in out
    assert "not attributed to any authority" in out
    waterfall.analyze(dataclasses.replace(sample_deal, noi=600_000, include_guarantee_fee_in_dscr=True)).summary()
    out = capsys.readouterr().out
    assert "guarantee fees are included in the DSCR denominator" in out
    assert "include_guarantee_fee_in_dscr=False" in out


def test_election_must_be_bool(sample_deal):
    with pytest.raises(ValueError, match="include_guarantee_fee_in_dscr must be True or False"):
        dataclasses.replace(sample_deal, include_guarantee_fee_in_dscr=1)


def test_no_standard_convention_claim_in_source():
    src = inspect.getsource(wf_mod)
    assert "standard NMTC underwriting convention" not in src


def test_39pct_cited_to_atg_not_45d():
    assert "Audit Technique Guide" in statute.CITATION_TOTAL_RATE
    assert "45D" not in statute.CITATION_TOTAL_RATE
    assert "cited to the IRS NMTC Audit Technique Guide" in inspect.getdoc(credits.schedule)
