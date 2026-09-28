"""Fix round 1, X5: every rendered disclosure and refusal renders WHOLE and keeps
its load-bearing clauses.

Each test asserts two independent things:
  1. the summary's output contains the disclosure constant whole (so it is not
     truncated or dropped from the render), and
  2. the constant contains literal clauses typed HERE, independently of the
     source -- the negations above all -- so a clause dropped from the constant
     goes red even though (1), which compares the constant with itself, cannot.
"""
import dataclasses
import warnings

import pytest

from nmtccalc import NMTCDeal, credits, investor, statute, subsidy, transaction, utils, waterfall
from nmtccalc.models import investor as inv_mod
from nmtccalc.models import subsidy as sub_mod
from nmtccalc.models import transaction as tx_mod
from nmtccalc.models import waterfall as wf_mod


def _out(capsys, fn, deal):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = fn(deal)
    r.summary()
    return capsys.readouterr().out


def _has(text, *clauses):
    for c in clauses:
        assert c in text, f"clause missing: {c!r}"


# ── statute disclosures ─────────────────────────────────────────────────────

def test_timing_disclosure(sample_deal, capsys):
    text = statute.timing_convention_disclosure()
    _has(text, "t=0 (the QEI date) through t=6", "is not discounted", "that timing is not modeled",
         "Realization can fall earlier or later than the allowance date",
         "§45D(a)(1)", "neither a floor nor a ceiling on an IRR measured on cash realization")
    assert "upper bound" not in text
    assert text in _out(capsys, credits.schedule, sample_deal)
    assert text in _out(capsys, investor.analyze, sample_deal)


def test_recapture_disclosure(sample_deal, capsys):
    text = statute.recapture_disclosure(4)
    _has(text, "inside the 7-year recapture period", "§45D(g)(3)(C)",
         "Every credit already allowed is recaptured and later allowance dates are not allowable",
         "§6621", "that interest is not deductible", "This package does not compute that interest",
         "§45D(g)(4)(A)", "it does not model a reinvestment")
    d = dataclasses.replace(sample_deal, unwind_year=4)
    for fn in (credits.schedule, investor.analyze, subsidy.analyze, waterfall.analyze):
        assert text in _out(capsys, fn, d), fn


def test_boundary_disclosure(sample_deal, capsys):
    text = statute.boundary_disclosure()
    _has(text, "works in whole years", "do not settle, at the level of a day",
         "before the seventh anniversary date is inside it")
    assert text in _out(capsys, credits.schedule, sample_deal)
    assert text in _out(capsys, waterfall.analyze, sample_deal)


def test_deployment_note_and_reasons(sample_deal, capsys):
    out = _out(capsys, transaction.structure, sample_deal)
    note = statute.deployment_ratio_note()
    _has(note, "It is NOT the substantially-all test", "refuses to compute", "§45D(g)(3)(B)")
    assert note in out
    r = statute.SUBSTANTIALLY_ALL_REFUSAL_REASONS
    _has(r[0], "regulatory, not statutory", "says only")
    _has(r[1], "not their face", "models face amounts only")
    _has(r[2], "two alternative tests with different denominators", "which is not a deal-level quantity")
    _has(r[3], "It is not testable at closing", "within 12 months of payment")
    _has(r[4], "75%, not 85%, in the seventh year")
    for reason in r:
        assert reason in out


def test_forgiveness_note(sample_deal, capsys):
    text = statute.forgiveness_note()
    _has(text, "negotiated exit term", "does not treat it as a feature of the credit", "no default",
         "p. 17", "the loan is not bona fide debt for federal income tax purposes.")
    assert text in _out(capsys, subsidy.analyze, sample_deal)


# ── investor ────────────────────────────────────────────────────────────────

def test_credit_only_note(sample_deal, capsys):
    text = inv_mod.CREDIT_ONLY_NOTE
    _has(text, "and nothing else", "no put or disposition value", "no exit tax",
         "depend on no deal input except the credit price", "REFUSED when the unwind falls inside",
         "They are not an investor IRR or MOIC.")
    assert text in _out(capsys, investor.analyze, sample_deal)


def test_refusal_messages(sample_deal):
    rec = investor.analyze(dataclasses.replace(sample_deal, unwind_year=2)).refused_reason
    assert rec == inv_mod.REFUSAL_RECAPTURE.format(k=2)
    _has(rec, "REFUSED:", "every credit already allowed is recaptured",
         "later allowance dates are not allowable", "No return is computed on credits the investor does not keep")
    nsc = investor.analyze(dataclasses.replace(sample_deal, credit_price=0.10)).refused_reason
    _has(nsc, "REFUSED:", "no sign change, so no IRR exists", "0.1282", "$500,000")
    bound = investor.analyze(sample_deal.with_credit_price(0.05 / 0.39 + 1e-10)).refused_reason
    _has(bound, "REFUSED:", "lies above the solver's search range, which ends at 536,870,912",
         "not a return", "Credit-only MOIC is unaffected", "-$0.00039")


# ── subsidy ─────────────────────────────────────────────────────────────────

def test_subsidy_notes(sample_deal, capsys):
    out = _out(capsys, subsidy.analyze, sample_deal)
    _has(sub_mod.NET_SUBSIDY_NOTE, "less the exit fee", "assumes the QALICB bears it",
         "the model does not know who does", "a list, not a subtraction", "does not deduct",
         "any tax on cancellation-of-debt income", "time value of money")
    _has(sub_mod.BLENDED_COUPON_NOTE, "not a cost of capital", "ignores every fee")
    _has(sub_mod.INTEREST_SAVINGS_NOTE, "simple, undiscounted", "full QLICI principal (A and B loans)",
         "the wrong entity's cost of capital")
    for text in (sub_mod.NET_SUBSIDY_NOTE, sub_mod.BLENDED_COUPON_NOTE,
                 sub_mod.INTEREST_SAVINGS_NOTE.format(k=7)):
        assert text in out
    _has(sub_mod.REFUSED_FORGIVENESS, "REFUSED:", "not supplied", "no default")
    _has(sub_mod.REFUSED_ALT_RATE, "REFUSED:", "not supplied")
    assert sub_mod.REFUSED_FORGIVENESS in out and sub_mod.REFUSED_ALT_RATE in out


# ── transaction ─────────────────────────────────────────────────────────────

def test_transaction_notes(sample_deal, capsys):
    out = _out(capsys, transaction.structure, sample_deal)
    _has(tx_mod.LEVERAGE_RATIO_NOTE, "(1 - 0.39p) / (0.39p)", "depends on the credit price alone",
         "the same for every deal at that price")
    _has(tx_mod.PROVENANCE_NOTE, "screening-time estimates, not closing terms")
    assert tx_mod.LEVERAGE_RATIO_NOTE in out and tx_mod.PROVENANCE_NOTE in out


# ── waterfall ───────────────────────────────────────────────────────────────

def test_fund_line_disclosure(sample_deal, capsys):
    text = wf_mod.FUND_LINE_DISCLOSURE
    _has(text, "which would reduce that amount", "which could cover a gap",
         "neither a floor nor a ceiling", "counting A-loan interest only",
         "only net of CDE costs this package takes no input for",
         "the principal gap shown is conservative")
    assert text in _out(capsys, waterfall.analyze, sample_deal)


def test_shortfall_warning_constant():
    _has(wf_mod.SHORTFALL_WARNING, "cannot service its leverage loan", "does not measure this",
         "fund's debt, not the QALICB's")
    _has(wf_mod.PRINCIPAL_GAP_WARNING, "less than the leverage loan principal due")


def test_guarantee_and_dscr_notes(sample_deal, capsys):
    out = _out(capsys, waterfall.analyze, dataclasses.replace(sample_deal, noi=600_000))
    g = wf_mod.GUARANTEE_FEE_NOTE.format(treatment="excluded from", opposite=True)
    _has(wf_mod.GUARANTEE_FEE_NOTE, "HOUSE ELECTION", "not attributed to any authority",
         "makes DSCR higher", "Net cash flow deducts the fee either way")
    assert g in out
    f = wf_mod.FLAT_DSCR_NOTE.format(how="is a single number applied to every year")
    _has(wf_mod.FLAT_DSCR_NOTE, "one stabilized figure, not a schedule", "so every row is the same")
    assert f in out
    _has(wf_mod.DSCR_REFUSED_ZERO_DS, "DSCR REFUSED", "coverage is undefined", "Net cash flow is still shown")
    _has(wf_mod.DSCR_NOT_COMPUTED_NO_NOI, "DSCR not computed", "noi was not supplied")


# ── sweeps ──────────────────────────────────────────────────────────────────

def test_sweep_notes(sample_deal, capsys):
    utils.credit_price_sensitivity(sample_deal, prices=[0.8])
    out = capsys.readouterr().out
    _has(utils.SWEEP_INVARIANCE_NOTE, "depend on no deal input except the credit price",
         "REFUSED when the unwind falls inside the recapture period",
         "not this deal's investor returns")
    _has(utils.LEVERAGE_COLUMN_NOTE, "a SUPPLIED A loan does not")
    assert utils.SWEEP_INVARIANCE_NOTE in out and utils.LEVERAGE_COLUMN_NOTE in out
    utils.discount_rate_sensitivity(sample_deal, rates=[0.08])
    out = capsys.readouterr().out
    _has(utils.DISCOUNT_INVARIANCE_NOTE, "depends on the discount rate alone",
         "the same for every deal at the same rates")
    assert utils.DISCOUNT_INVARIANCE_NOTE in out


def test_discount_column_is_deal_invariant():
    a = NMTCDeal(project_name="A", total_project_cost=10_000_000, nmtc_allocation=10_000_000,
                 credit_price=0.83, leverage_loan_rate=0.045, qlici_a_loan_rate=0.045,
                 qlici_b_loan_rate=0.01, cde_fee_rate=0.02)
    b = dataclasses.replace(a, nmtc_allocation=45_000_000, total_project_cost=90_000_000,
                            credit_price=0.70, cde_fee_rate=0.05)
    da = utils.discount_rate_sensitivity(a, rates=[0.06, 0.10])
    db = utils.discount_rate_sensitivity(b, rates=[0.06, 0.10])
    assert list(da["PV / Face Value"]) == list(db["PV / Face Value"])
    assert list(da["PV of Credits ($MM)"]) != list(db["PV of Credits ($MM)"])
