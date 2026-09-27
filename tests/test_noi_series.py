"""Item 6: NOI is a series; DSCR varies with it; a flat NOI says so."""
import dataclasses

import pytest

from nmtccalc import NMTCDeal, waterfall

DS = 334_705  # 6,763,000 x 4.5% + 3,037,000 x 1.0%


def test_series_gives_per_year_dscr(sample_deal):
    noi = [500_000, 550_000, 600_000, 650_000, 700_000, 750_000, 800_000]
    r = waterfall.analyze(dataclasses.replace(sample_deal, noi=noi))
    assert [y.noi for y in r.years] == noi
    assert [y.dscr for y in r.years] == pytest.approx([n / DS for n in noi])
    assert r.dscr_varies is True
    assert r.noi_is_series is True
    assert r.min_dscr == pytest.approx(500_000 / DS)
    assert r.avg_dscr == pytest.approx(sum(noi) / 7 / DS)
    assert [y.net_cash_flow for y in r.years] == pytest.approx([n - DS for n in noi])


def test_series_summary_prints_avg_and_min(sample_deal, capsys):
    noi = [500_000, 600_000, 600_000, 600_000, 600_000, 600_000, 700_000]
    waterfall.analyze(dataclasses.replace(sample_deal, noi=noi)).summary()
    out = capsys.readouterr().out
    assert f"Avg {600_000 / DS:.2f}x  |  Min {500_000 / DS:.2f}x" in out
    assert "stabilized" not in out


def test_flat_scalar_says_so(sample_deal, capsys):
    r = waterfall.analyze(dataclasses.replace(sample_deal, noi=600_000))
    assert r.dscr_varies is False and r.noi_is_series is False
    r.summary()
    out = capsys.readouterr().out
    assert "DSCR:  1.79x every year. This is one stabilized figure, not a schedule" in out
    assert "NOI is a single number applied to every year" in out
    assert "Avg" not in out


def test_flat_series_says_so(sample_deal, capsys):
    r = waterfall.analyze(dataclasses.replace(sample_deal, noi=[600_000] * 7))
    assert r.dscr_varies is False and r.noi_is_series is True
    r.summary()
    assert "is the same in every year of the series supplied" in capsys.readouterr().out


def test_series_length_must_match_unwind_year(sample_deal):
    with pytest.raises(ValueError, match=r"noi series has 6 entries; it needs exactly one per year 1..unwind_year \(7\)"):
        dataclasses.replace(sample_deal, noi=[1] * 6)
    d = dataclasses.replace(sample_deal, unwind_year=4, noi=[1, 2, 3, 4])
    assert d.noi_schedule == [1, 2, 3, 4]
    with pytest.raises(ValueError, match="noi series"):
        dataclasses.replace(d, unwind_year=5)


@pytest.mark.parametrize("bad", [[1, 2, 3, 4, 5, 6, float("nan")], [1, 2, 3, 4, 5, 6, "7"],
                                 [1, 2, 3, 4, 5, 6, True]])
def test_series_entries_must_be_finite(sample_deal, bad):
    with pytest.raises(ValueError, match="noi series entries must be finite numbers"):
        dataclasses.replace(sample_deal, noi=bad)


def test_series_entries_non_negative(sample_deal):
    with pytest.raises(ValueError, match="noi must be non-negative"):
        dataclasses.replace(sample_deal, noi=[1, 2, 3, 4, 5, 6, -1])


def test_series_zero_allowed(sample_deal):
    assert dataclasses.replace(sample_deal, noi=[0] * 7).noi_schedule == [0] * 7


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "600000", True])
def test_scalar_noi_must_be_finite(sample_deal, bad):
    with pytest.raises(ValueError, match="noi must be a finite number, a sequence of them, or None"):
        dataclasses.replace(sample_deal, noi=bad)


def test_series_stored_as_tuple_and_schedule(sample_deal):
    d = dataclasses.replace(sample_deal, noi=[1, 2, 3, 4, 5, 6, 7])
    assert d.noi == (1, 2, 3, 4, 5, 6, 7)
    assert d.noi_schedule == [1, 2, 3, 4, 5, 6, 7]
    assert dataclasses.replace(sample_deal, noi=5).noi_schedule == [5] * 7
    assert sample_deal.noi_schedule is None
    assert sample_deal.noi_is_series is False


def test_to_dict_carries_flags(sample_deal):
    d = waterfall.analyze(dataclasses.replace(sample_deal, noi=[1] * 6 + [2])).to_dict()
    assert d["dscr_varies"] is True and d["noi_is_series"] is True
