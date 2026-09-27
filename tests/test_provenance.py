"""Item 3: derived-and-labelled provenance, SUPPLIED A/B split, with_* rebalancing."""
import dataclasses
import math
import warnings

import numpy as np
import pytest

from nmtccalc import (
    Basis, LeverageShortfallWarning, NegativeTrancheError, NMTCDeal, Provenance,
    UnbalancedStackError, transaction, utils, waterfall,
)
from nmtccalc.data.schema import STACK_TOLERANCE_DOLLARS
from nmtccalc.models.transaction import PROVENANCE_NOTE


# ── default: everything but the user's inputs is DERIVED ─────────────────────

def test_default_provenance(sample_deal):
    p = sample_deal.provenance
    assert p["qei"] is Provenance.SUPPLIED
    assert p["total_project_cost"] is Provenance.SUPPLIED
    for name in ("total_nmtcs", "investor_equity", "leverage_loan", "cde_fee",
                 "qlici_total", "qlici_a_loan", "qlici_b_loan",
                 "guarantee_fee_annual", "exit_fee"):
        assert p[name] is Provenance.DERIVED, name


def test_default_basis_rules(sample_deal):
    b = sample_deal.basis
    assert b["qlici_a_loan"] == Basis(Provenance.DERIVED, "mirrors the leverage loan")
    assert b["qlici_b_loan"] == Basis(Provenance.DERIVED, "investor equity - CDE fee")
    assert b["leverage_loan"].rule == "QEI - investor equity (two-source fund)"
    assert "Audit Technique Guide" in b["total_nmtcs"].rule
    assert "§45D(a)(2)-(3)" in b["total_nmtcs"].rule
    assert b["qlici_a_loan"].label() == "DERIVED: mirrors the leverage loan"


def test_provenance_enum_values():
    assert Provenance.DERIVED.value == "DERIVED"
    assert Provenance.SUPPLIED.value == "SUPPLIED"


# ── SUPPLIED A/B ─────────────────────────────────────────────────────────────

def test_supplied_a_derives_b_as_balance(sample_deal):
    d = dataclasses.replace(sample_deal, qlici_a_loan_amount=6_500_000)
    assert d.qlici_a_loan == 6_500_000
    assert d.qlici_b_loan == pytest.approx(9_800_000 - 6_500_000)
    assert d.provenance["qlici_a_loan"] is Provenance.SUPPLIED
    assert d.provenance["qlici_b_loan"] is Provenance.DERIVED
    assert d.basis["qlici_b_loan"].rule == "QLICI total - A loan (SUPPLIED)"


def test_supplied_b_derives_a_as_balance(sample_deal):
    d = dataclasses.replace(sample_deal, qlici_b_loan_amount=3_000_000)
    assert d.qlici_b_loan == 3_000_000
    assert d.qlici_a_loan == pytest.approx(6_800_000)
    assert d.provenance["qlici_a_loan"] is Provenance.DERIVED
    assert d.basis["qlici_a_loan"].rule == "QLICI total - B loan (SUPPLIED)"


def test_both_supplied_reconciled(sample_deal):
    d = dataclasses.replace(sample_deal, qlici_a_loan_amount=6_000_000,
                            qlici_b_loan_amount=3_800_000)
    assert d.provenance["qlici_a_loan"] is Provenance.SUPPLIED
    assert d.provenance["qlici_b_loan"] is Provenance.SUPPLIED


def test_both_supplied_within_tolerance(sample_deal):
    assert STACK_TOLERANCE_DOLLARS == 1.0
    dataclasses.replace(sample_deal, qlici_a_loan_amount=6_000_000,
                        qlici_b_loan_amount=3_800_001)


@pytest.mark.parametrize("b", [3_800_001.5, 3_799_998.5, 4_000_000])
def test_both_supplied_unbalanced_refused(sample_deal, b):
    with pytest.raises(UnbalancedStackError, match="differs from QLICI total"):
        dataclasses.replace(sample_deal, qlici_a_loan_amount=6_000_000, qlici_b_loan_amount=b)


def test_unbalanced_error_message_figures(sample_deal):
    with pytest.raises(UnbalancedStackError) as ei:
        dataclasses.replace(sample_deal, qlici_a_loan_amount=6_000_000, qlici_b_loan_amount=4_000_000)
    msg = str(ei.value)
    assert "$10,000,000" in msg and "$9,800,000" in msg and "by $200,000" in msg


def test_unbalanced_is_valueerror():
    assert issubclass(UnbalancedStackError, ValueError)


def test_supplied_a_above_qlici_total_refused_as_negative_b(sample_deal):
    with pytest.raises(NegativeTrancheError, match="qlici_b_loan would be") as ei:
        dataclasses.replace(sample_deal, qlici_a_loan_amount=10_000_000)
    assert "QLICI total - A loan (SUPPLIED)" in str(ei.value)
    assert "cde_fee_rate must not exceed" not in str(ei.value)


def test_supplied_negative_a_refused(sample_deal):
    with pytest.raises(NegativeTrancheError, match="qlici_a_loan would be"):
        dataclasses.replace(sample_deal, qlici_a_loan_amount=-1)


@pytest.mark.parametrize("field", ["qlici_a_loan_amount", "qlici_b_loan_amount"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "1000", True])
def test_optional_amounts_must_be_finite(sample_deal, field, bad):
    with pytest.raises(ValueError, match=f"{field} must be a finite number or None"):
        dataclasses.replace(sample_deal, **{field: bad})


@pytest.mark.parametrize("field", [
    "total_project_cost", "nmtc_allocation", "credit_price", "leverage_loan_rate",
    "qlici_a_loan_rate", "qlici_b_loan_rate", "cde_fee_rate", "discount_rate",
    "guarantee_fee_rate", "exit_fee_rate",
])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None, "0.5", False])
def test_numeric_fields_must_be_finite(sample_deal, field, bad):
    with pytest.raises(ValueError, match=f"{field} must be a finite number"):
        dataclasses.replace(sample_deal, **{field: bad})


def test_numpy_scalars_accepted(sample_deal):
    d = dataclasses.replace(sample_deal, nmtc_allocation=np.int64(10_000_000),
                            credit_price=np.float64(0.83), qlici_a_loan_amount=np.float64(6_500_000))
    assert d.qlici_b_loan == pytest.approx(3_300_000)


# ── the reconciliation item 1 promised: principal gap when A is SUPPLIED ─────

def test_supplied_a_below_leverage_warns_principal_gap(sample_deal):
    # leverage 6,763,000; A 6,000,000 -> gap 763,000. A interest 270,000 + B (3,800,000 x 1%) 38,000
    # = 308,000 >= leverage interest 304,335, so only the principal gap fires.
    d = dataclasses.replace(sample_deal, qlici_a_loan_amount=6_000_000)
    with pytest.warns(LeverageShortfallWarning, match=r"A-loan principal repaid to the fund at unwind \(\$6,000,000\) is \$763,000 less"):
        r = waterfall.analyze(d)
    assert r.annual_fund_shortfall == 0
    assert r.leverage_principal_gap == pytest.approx(763_000)
    assert r.a_loan_principal_repaid == 6_000_000
    assert r.leverage_serviced is False


def test_supplied_a_interest_and_principal_both_short(sample_deal):
    d = dataclasses.replace(sample_deal, qlici_a_loan_amount=5_000_000, leverage_loan_rate=0.08)
    with pytest.warns(LeverageShortfallWarning) as rec:
        r = waterfall.analyze(d)
    assert len(rec) == 1
    msg = str(rec[0].message)
    # lev 6,763,000 x 8% = 541,040; QLICI 225,000 + 48,000 = 273,000; short 268,040
    assert r.annual_fund_shortfall == pytest.approx(268_040)
    assert "$1,763,000 less than the leverage principal due" in msg


def test_supplied_a_above_leverage_no_gap(sample_deal):
    d = dataclasses.replace(sample_deal, qlici_a_loan_amount=7_000_000)
    with warnings.catch_warnings():
        warnings.simplefilter("error", LeverageShortfallWarning)
        r = waterfall.analyze(d)
    assert r.leverage_principal_gap == 0


# ── rendering ────────────────────────────────────────────────────────────────

def test_transaction_summary_prints_basis_inline(sample_deal, capsys):
    d = dataclasses.replace(sample_deal, qlici_a_loan_amount=6_500_000)
    df = transaction.structure(d).summary()
    out = capsys.readouterr().out
    rows = dict(zip(df["Item"], df["Basis"]))
    assert rows["── A Loan (Senior)"] == "SUPPLIED: qlici_a_loan_amount"
    assert rows["── B Loan (Subordinate)"] == "DERIVED: QLICI total - A loan (SUPPLIED)"
    assert rows["── Investor Equity"] == "DERIVED: total NMTCs x credit price"
    assert rows["── Total NMTCs (39% × QEI)"].startswith("DERIVED: 39% x QEI")
    assert PROVENANCE_NOTE in out
    # every row with an amount has a basis
    for item, amount, basis in zip(df["Item"], df["Amount"], df["Basis"]):
        if amount:
            assert basis.startswith(("DERIVED", "SUPPLIED", "REFUSED")), item


def test_transaction_to_dict_carries_provenance(sample_deal):
    d = transaction.structure(dataclasses.replace(sample_deal, qlici_b_loan_amount=3_000_000)).to_dict()
    assert d["provenance"]["qlici_b_loan"] == "SUPPLIED"
    assert d["provenance"]["qlici_a_loan"] == "DERIVED"
    assert d["basis"]["qlici_a_loan"] == "DERIVED: QLICI total - B loan (SUPPLIED)"
    assert d["qlici_a_loan"] == pytest.approx(6_800_000)


# ── with_* rebalancing (audit §6) ────────────────────────────────────────────

PRICES = [0.70, 0.74, 0.78, 0.83, 0.86, 0.90]


@pytest.mark.parametrize("supplied", [{}, {"qlici_a_loan_amount": 6_500_000},
                                      {"qlici_b_loan_amount": 3_200_000},
                                      {"qlici_a_loan_amount": 6_600_000, "qlici_b_loan_amount": 3_200_000}])
def test_with_credit_price_keeps_stack_balanced(sample_deal, supplied):
    base = dataclasses.replace(sample_deal, **supplied)
    for p in PRICES:
        d = base.with_credit_price(p)
        assert d.credit_price == p
        assert d.investor_equity == pytest.approx(3_900_000 * p)
        assert d.investor_equity + d.leverage_loan == pytest.approx(d.qei, abs=1e-6)
        assert d.qlici_a_loan + d.qlici_b_loan == pytest.approx(d.qlici_total, abs=STACK_TOLERANCE_DOLLARS)
        assert d.provenance == base.provenance
        for k, v in supplied.items():
            assert getattr(d, k) == v


def test_with_credit_price_derived_rederives_split(sample_deal):
    d = sample_deal.with_credit_price(0.90)
    # audit §6 "TODAY" row: equity 3,510,000, leverage 6,490,000
    assert d.investor_equity == pytest.approx(3_510_000)
    assert d.leverage_loan == pytest.approx(6_490_000)
    assert d.qlici_a_loan == pytest.approx(6_490_000)
    assert d.qlici_b_loan == pytest.approx(3_310_000)


def test_with_credit_price_refuses_negative(sample_deal):
    d = dataclasses.replace(sample_deal, cde_fee_rate=0.30)
    with pytest.raises(NegativeTrancheError):
        d.with_credit_price(0.70)


def test_with_credit_price_validates(sample_deal):
    with pytest.raises(ValueError, match="credit_price"):
        sample_deal.with_credit_price(1.5)


def test_with_discount_rate(sample_deal):
    d = sample_deal.with_discount_rate(0.10)
    assert d.discount_rate == 0.10
    assert d.provenance == sample_deal.provenance
    assert d.qlici_b_loan == sample_deal.qlici_b_loan
    with pytest.raises(ValueError, match="discount_rate"):
        sample_deal.with_discount_rate(0)


def test_with_methods_return_new_objects(sample_deal):
    assert sample_deal.with_credit_price(0.83) is not sample_deal
    assert sample_deal.with_discount_rate(0.08) is not sample_deal
    assert sample_deal.credit_price == 0.83


def test_sweep_with_supplied_split_balances(sample_deal):
    d = dataclasses.replace(sample_deal, qlici_a_loan_amount=6_500_000, b_loan_forgiveness_rate=1.0)
    df = utils.credit_price_sensitivity(d, prices=[0.75, 0.90])
    # Net subsidy is the B loan: held at 3.30MM across the sweep because it is SUPPLIED-balanced.
    assert list(df["Net Subsidy ($MM)"]) == [3.3, 3.3]
    assert list(df["Equity ($MM)"]) == [2.92, 3.51]  # round(2.925, 2) == 2.92 in binary float


def test_sweep_uses_with_methods(monkeypatch, sample_deal):
    calls = []
    orig = NMTCDeal.with_credit_price

    def spy(self, p):
        calls.append(p)
        return orig(self, p)
    monkeypatch.setattr(NMTCDeal, "with_credit_price", spy)
    utils.credit_price_sensitivity(sample_deal, prices=[0.8, 0.85])
    assert calls == [0.8, 0.85]

    rcalls = []
    orig_r = NMTCDeal.with_discount_rate

    def spy_r(self, r):
        rcalls.append(r)
        return orig_r(self, r)
    monkeypatch.setattr(NMTCDeal, "with_discount_rate", spy_r)
    utils.discount_rate_sensitivity(sample_deal, rates=[0.06, 0.07])
    assert rcalls == [0.06, 0.07]
