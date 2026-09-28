"""Golden text of every disclosure and refusal constant (fix round 2, R1-4).

A REVIEWED SNAPSHOT, generated from the source when this file was written and then
read line by line. It is not an independent re-typing -- tests/test_disclosure_text.py
and the full-text CREDIT_ONLY_NOTE test hold independently typed clauses. What this
file adds: any edit to any of these strings, including a dropped clause or a lost
"not", fails until it is made here too, deliberately. Regenerate only by hand review.
"""
import importlib

import pytest


GOLDEN = [
    ('nmtccalc.statute', 'CITATION_TOTAL_RATE',
     'IRS NMTC Audit Technique Guide (May 2010), credit overview'),
    ('nmtccalc.statute', 'RECAPTURE_DISCLOSURE',
     ('The structure unwinds at t={k}, inside the 7-year recapture period that runs from the QEI '
      "date to t=7 ({period}). Under this package's definition an unwind redeems the QEI, and "
      'redemption of the QEI by the CDE is a recapture event ({redemption}). Every credit already '
      'allowed is recaptured and later allowance dates are not allowable. The credit recapture '
      'amount is every credit already allowed plus interest at the §6621 underpayment rate, and '
      'that interest is not deductible ({amount}). This package does not compute that interest. It '
      'assumes every credit claimed reduced tax liability (recapture reaches only such credits, '
      '§45D(g)(4)(A)), and it does not model a reinvestment of the proceeds that would avoid '
      'redemption.')),
    ('nmtccalc.statute', 'BOUNDARY_DISCLOSURE',
     ('The unwind is placed at t=7, the end of the 7-year recapture period ({period}). This package '
      'works in whole years. The primary sources do not settle, at the level of a day, whether an '
      'event on the seventh anniversary itself is inside the period. An unwind executed before the '
      'seventh anniversary date is inside it: every credit already allowed is then recaptured, and '
      'later allowance dates are not allowable.')),
    ('nmtccalc.statute', 'TIMING_CONVENTION_DISCLOSURE',
     ('Credits are placed on the statutory credit allowance dates, t=0 (the QEI date) through t=6 '
      '({schedule}). The first credit falls on the date the equity is paid and is not discounted. '
      'The investor realizes a credit in cash through estimated payments and returns filed for the '
      'taxable year in which the allowance date falls, and that timing is not modeled. Realization '
      'can fall earlier or later than the allowance date, depending on where each date falls in the '
      "investor's taxable year (the credit is allowed for that year, §45D(a)(1), and estimated-tax "
      'installments can reflect it), so the credit-only IRR here is neither a floor nor a ceiling '
      'on an IRR measured on cash realization.')),
    ('nmtccalc.statute', 'SUBSTANTIALLY_ALL_REFUSAL_REASONS',
     ('The 85% threshold is regulatory, not statutory: §45D(b)(1)(B) says only "substantially all"; '
      '85% is 26 CFR §1.45D-1(c)(5)(i).',
      "The numerator is the CDE's §1012 cost basis in its QLICIs, not their face amount "
      '(§1.45D-1(c)(5)(ii)-(iii)); this package models face amounts only.',
      'There are two alternative tests with different denominators: direct tracing divides by the '
      "taxpayer's cash investment (§1.45D-1(c)(5)(ii)); the safe harbor divides by the CDE's cost "
      'basis in ALL of its assets (§1.45D-1(c)(5)(iii)), which is not a deal-level quantity.',
      'It is not testable at closing: cash counts as invested only if invested within 12 months of '
      'payment (§1.45D-1(c)(5)(iv)); the test then runs for every annual period of the 7-year '
      'credit period, once in the first and semiannually averaged after (§1.45D-1(c)(5)(i)), with '
      'returned capital reinvested within 12 months (§1.45D-1(d)(2)(i)).',
      'The threshold is 75%, not 85%, in the seventh year (§1.45D-1(c)(5)(v)).')),
    ('nmtccalc.statute', 'DEPLOYMENT_RATIO_NOTE',
     ('The closing-date QLICI deployment ratio is QLICI total / QEI on the closing date, at face. '
      'It is NOT the substantially-all test of {cite}, which this package refuses to compute for '
      'the reasons listed. A breach of that test is a recapture event (§45D(g)(3)(B)).')),
    ('nmtccalc.statute', 'CITATION_ATG_FORGIVENESS',
     ('IRS NMTC Audit Technique Guide (May 2010), p. 17, "Intent to Forgive or Otherwise Not '
      'Collect Debt"')),
    ('nmtccalc.statute', 'ATG_BONA_FIDE_DEBT_QUOTE',
     ('"An essential element of bona fide debt is whether there exists a good-faith intent on the '
      'part of the recipient of the funds to make repayment and a good-faith intent on the part of '
      'the person advancing the funds to enforce repayment." ... "In some instances, as an exit '
      'strategy, the CDE may intend to eventually forgive or otherwise not collect on the debt '
      'after the end of the 7-year credit period. If such an intention is reflected in a '
      'pre-arranged feature; i.e., a statement in the loan documents that the lender will forgive '
      'the loan, the loan is not bona fide debt for federal income tax purposes."')),
    ('nmtccalc.statute', 'FORGIVENESS_NOTE',
     ('B-loan forgiveness is a negotiated exit term of the deal documents; this package does not '
      'treat it as a feature of the credit, so b_loan_forgiveness_rate is an input with no default. '
      'The {cite} states: {quote}')),
    ('nmtccalc.models.investor', 'CREDIT_ONLY_NOTE',
     ('CREDIT-ONLY: these cash flows are the equity paid and the credits received, and nothing '
      'else: no fund-level taxable income or tax drag, no put or disposition value, no exit tax, no '
      'sub-annual timing, no §45D(h) basis reduction, no §38 tax-capacity limit. Investor equity is '
      'always total NMTCs x credit price, so every flow is proportional to QEI. When they are '
      'computed, both figures depend on no deal input except the credit price: credit-only MOIC = 1 '
      '/ credit price, and two deals at the same price report the same credit-only IRR whatever '
      'their size, rates or fees. Both are REFUSED when the unwind falls inside the 7-year '
      'recapture period. They are not an investor IRR or MOIC.')),
    ('nmtccalc.models.investor', 'REFUSAL_RECAPTURE',
     ('REFUSED: the unwind at t={k} is inside the 7-year recapture period, so every credit already '
      'allowed is recaptured (plus nondeductible interest this package does not compute) and later '
      'allowance dates are not allowable. No return is computed on credits the investor does not '
      'keep.')),
    ('nmtccalc.models.investor', 'REFUSAL_IRR_BOUND',
     ("REFUSED: the IRR lies above the solver's search range, which ends at {search_max:,.0f} (an "
      'IRR of {search_pct:,.0f}%). The net t=0 outlay is {t0} against later credits; a figure this '
      'size is an artifact of a near-zero outlay, not a return. Credit-only MOIC is unaffected.')),
    ('nmtccalc.models.investor', 'REFUSAL_NO_SIGN_CHANGE',
     ('REFUSED: the cash flows have no sign change, so no IRR exists. At a credit price at or below '
      '{threshold:.4f} the t=0 credit ({first}) is at least the equity paid on the same date.')),
    ('nmtccalc.models.subsidy', 'REFUSED_FORGIVENESS',
     'REFUSED: b_loan_forgiveness_rate not supplied (it has no default)'),
    ('nmtccalc.models.subsidy', 'REFUSED_ALT_RATE',
     'REFUSED: qalicb_alternative_borrowing_rate not supplied'),
    ('nmtccalc.models.subsidy', 'NET_SUBSIDY_NOTE',
     ('Net subsidy = B loan x b_loan_forgiveness_rate, less the exit fee paid at unwind. Deducting '
      'the exit fee here assumes the QALICB bears it; the model does not know who does, and the '
      'deal documents decide. The rows above are a list, not a subtraction: the B loan follows the '
      'rule in its Basis column. Net subsidy does not deduct interest paid on the QLICI loans, '
      'guarantee fees, the put price, any tax on cancellation-of-debt income from the forgiveness, '
      'or the time value of money; it is a face-amount figure at unwind.')),
    ('nmtccalc.models.subsidy', 'BLENDED_COUPON_NOTE',
     ('Blended QLICI coupon = (A x A rate + B x B rate) / QLICI total. It is a principal-weighted '
      'average coupon, not a cost of capital: it moves with the A/B split and the two rates only, '
      'and ignores every fee, the forgiveness, the put and the exit fee. (0.2.1 called it '
      'effective_cost_of_capital.)')),
    ('nmtccalc.models.subsidy', 'INTEREST_SAVINGS_NOTE',
     ('Interest savings to unwind = simple, undiscounted interest over years 1..{k} on the full '
      "QLICI principal (A and B loans), comparing the QALICB's alternative borrowing rate, which "
      'you supply, with the QLICI coupons. A negative figure means the QLICI loans cost more than '
      "the alternative. 0.2.1 used the Investment Fund's leverage-loan rate here, which is the "
      "wrong entity's cost of capital, and the B loan only.")),
    ('nmtccalc.models.transaction', 'LEVERAGE_RATIO_NOTE',
     ('Leverage loan / equity = (1 - 0.39p) / (0.39p) at credit price p, where 0.39 is the total '
      'credit rate (39% of QEI): with equity and the leverage loan both derived from the price, it '
      'depends on the credit price alone and is the same for every deal at that price. (0.2.1 '
      'called it leverage_ratio.)')),
    ('nmtccalc.models.transaction', 'PROVENANCE_NOTE',
     ('Basis column: SUPPLIED figures are terms you entered. DERIVED figures are computed by the '
      'rule shown and are screening-time estimates, not closing terms. Supply the A/B split with '
      'qlici_a_loan_amount / qlici_b_loan_amount where real terms exist.')),
    ('nmtccalc.models.waterfall', 'FUND_LINE_DISCLOSURE',
     ('Investment Fund line: the fund services its leverage loan (interest-only, principal due at '
      'unwind) from QLICI flows passed up through the CDE. All A-loan and B-loan interest is '
      'counted as reaching the fund. This package has no input for ongoing CDE or sub-CDE fees, '
      'which would reduce that amount, nor for fund reserves or other sources, which could cover a '
      "gap. The fund line is therefore neither a floor nor a ceiling on the fund's true position. "
      'To bracket it, the shortfall is also shown counting A-loan interest only, since B interest '
      'reaches the fund only net of CDE costs this package takes no input for. The principal gap '
      'counts A-loan principal only; any B-loan principal repaid rather than forgiven would also '
      'reach the fund, so the principal gap shown is conservative (it can overstate the gap).')),
    ('nmtccalc.models.waterfall', 'GUARANTEE_FEE_NOTE',
     ('HOUSE ELECTION: guarantee fees are {treatment} the DSCR denominator. This is a house '
      'election, not attributed to any authority. Excluding a recurring fee makes DSCR higher than '
      'including it. For the opposite treatment set include_guarantee_fee_in_dscr={opposite}. Net '
      'cash flow deducts the fee either way.')),
    ('nmtccalc.models.waterfall', 'DSCR_REFUSED_ZERO_DS',
     ('DSCR REFUSED: debt service <= 0 (A-loan and B-loan interest are both zero, each from a zero '
      'principal or a 0% coupon{fee}), so coverage is undefined. Net cash flow is still shown.')),
    ('nmtccalc.models.waterfall', 'DSCR_NOT_COMPUTED_NO_NOI',
     'DSCR not computed: noi was not supplied.'),
    ('nmtccalc.models.waterfall', 'FLAT_DSCR_NOTE',
     ('This is one stabilized figure, not a schedule: debt service is interest-only on fixed '
      'balances, and NOI {how}, so every row is the same. Supply noi as a sequence with one entry '
      'per year to model a schedule.')),
    ('nmtccalc.models.waterfall', 'SHORTFALL_WARNING',
     ('LEVERAGE SHORTFALL: the Investment Fund cannot service its leverage loan from the modeled '
      'QLICI flows. Annual leverage interest ${lev:,.0f} exceeds QLICI interest reaching the fund '
      '${qlici:,.0f} by ${short:,.0f} per year (${total:,.0f} over {years} years){principal}. '
      "QALICB coverage (DSCR) does not measure this, because the leverage loan is the fund's debt, "
      "not the QALICB's.")),
    ('nmtccalc.models.waterfall', 'PRINCIPAL_GAP_WARNING',
     ('LEVERAGE SHORTFALL: the A-loan principal repaid to the fund at unwind (${a:,.0f}) is '
      '${gap:,.0f} less than the leverage loan principal due (${lev:,.0f}).')),
    ('nmtccalc.utils', 'DISCOUNT_INVARIANCE_NOTE',
     ('The PV / Face Value column depends on the discount rate alone: it is the present value of '
      'the statutory 5%/6% schedule divided by its 39% total, so it is the same for every deal at '
      'the same rates. PV of Credits scales with QEI.')),
    ('nmtccalc.utils', 'LEVERAGE_COLUMN_NOTE',
     ("Leverage Serviced is the waterfall's reconciliation at each price: 'yes', or the annual "
      'interest shortfall and/or the principal gap. It counts A-loan and B-loan interest; the '
      "waterfall's A-interest-only bracket is omitted here. The leverage loan moves with the price; "
      'a SUPPLIED A loan does not.')),
    ('nmtccalc.utils', 'SWEEP_BASIS_NOTE',
     ('Equity ($MM) and Leverage Loan ($MM) are DERIVED at each price: equity = total NMTCs x '
      'price; leverage loan = QEI - equity (two-source fund).')),
    ('nmtccalc.utils', 'REFUSED_CELL',
     {'irr_bound': 'REFUSED (IRR above solver search range)',
      'no_sign_change': 'REFUSED (no sign change)',
      'recapture': 'REFUSED (unwind inside recapture period)'}),
    ('nmtccalc.utils', 'SWEEP_INVARIANCE_NOTE',
     ('Where computed, the Credit-only MOIC and Credit-only IRR columns depend on no deal input '
      'except the credit price: they are the same for every deal at the same prices, whatever its '
      'size, rates or fees (MOIC = 1 / price). They are REFUSED when the unwind falls inside the '
      "recapture period. They are a lookup table of the credit price, not this deal's investor "
      'returns. Equity and leverage scale with QEI; net subsidy depends on the A/B split, the fee '
      'and the forgiveness rate.')),
]


@pytest.mark.parametrize("module, name, expected", GOLDEN, ids=[f"{m}.{n}" for m, n, _ in GOLDEN])
def test_golden_text(module, name, expected):
    assert getattr(importlib.import_module(module), name) == expected


def test_golden_covers_every_long_string_constant():
    # a new disclosure constant must be added here, not silently left out
    import ast, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    covered = {(m, n) for m, n, _ in GOLDEN}
    for rel in ("nmtccalc/statute.py", "nmtccalc/models/investor.py", "nmtccalc/models/subsidy.py",
                "nmtccalc/models/transaction.py", "nmtccalc/models/waterfall.py", "nmtccalc/utils/__init__.py"):
        modname = rel[:-3].replace("/", ".").replace(".__init__", "")
        mod = importlib.import_module(modname)
        for node in ast.parse((root / rel).read_text()).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                v = getattr(mod, name, None)
                if name.isupper() and isinstance(v, str) and len(v) >= 40:
                    assert (modname, name) in covered, f"{modname}.{name} is not in GOLDEN"
