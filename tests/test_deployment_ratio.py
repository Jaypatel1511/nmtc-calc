"""Item 7: closing-date QLICI deployment ratio under its honest name; 85% refused."""
import dataclasses

import pytest

from nmtccalc import statute, transaction


def test_ratio_literal(sample_deal):
    r = transaction.structure(sample_deal)
    assert r.closing_qlici_deployment_ratio == pytest.approx(9_800_000 / 10_000_000, abs=1e-15)


def test_ratio_moves_with_fee(sample_deal):
    r = transaction.structure(dataclasses.replace(sample_deal, cde_fee_rate=0.10))
    assert r.closing_qlici_deployment_ratio == pytest.approx(0.90)


def test_substantially_all_refused_with_five_reasons(sample_deal):
    r = transaction.structure(sample_deal)
    assert r.substantially_all_test == "REFUSED"
    assert len(r.substantially_all_refusal_reasons) == 5
    joined = " ".join(r.substantially_all_refusal_reasons)
    for cite in ("§45D(b)(1)(B)", "§1.45D-1(c)(5)(i)", "§1012", "(c)(5)(ii)", "(c)(5)(iii)",
                 "(c)(5)(iv)", "(c)(5)(v)", "(d)(2)(i)", "75%"):
        assert cite in joined, cite


def test_no_pass_fail_verdict_even_below_85(sample_deal):
    # 20% fee -> 80% deployed at face. No verdict either way is rendered.
    r = transaction.structure(dataclasses.replace(sample_deal, cde_fee_rate=0.20))
    assert r.closing_qlici_deployment_ratio == pytest.approx(0.80)
    assert r.substantially_all_test == "REFUSED"


def test_summary_renders_ratio_and_refusal(sample_deal, capsys):
    df = transaction.structure(sample_deal).summary()
    out = capsys.readouterr().out
    rows = dict(zip(df["Item"], df["Amount"]))
    assert rows["── Closing-date QLICI deployment ratio"] == "98.0% of QEI"
    assert rows["── Substantially-all test"] == "REFUSED"
    assert "It is NOT the substantially-all test of 26 CFR §1.45D-1(c)(5)" in out
    assert "§45D(g)(3)(B)" in out
    for i in range(1, 6):
        assert f"  {i}. " in out
    assert "PASS" not in out and "FAIL" not in out


def test_to_dict(sample_deal):
    d = transaction.structure(sample_deal).to_dict()
    assert d["closing_qlici_deployment_ratio"] == pytest.approx(0.98)
    assert d["substantially_all_test"] == "REFUSED"
    assert len(d["substantially_all_refusal_reasons"]) == 5


def test_statute_constants():
    assert statute.SUBSTANTIALLY_ALL_STATUS == "REFUSED"
    assert statute.CITATION_SUBSTANTIALLY_ALL == "26 CFR §1.45D-1(c)(5)"
