"""
Statutory and regulatory constants for the New Markets Tax Credit, each with
the provision it comes from.

Every constant here was retrieved from a primary source when this module was
written (2026-09-27), not recalled:

26 U.S.C. §45D(a)(2):
    "the applicable percentage is—(A) 5 percent with respect to the first 3
    credit allowance dates, and (B) 6 percent with respect to the remainder of
    the credit allowance dates."

26 U.S.C. §45D(a)(3):
    "the term 'credit allowance date' means, with respect to any qualified
    equity investment—(A) the date on which such investment is initially made,
    and (B) each of the 6 anniversary dates of such date thereafter."

26 U.S.C. §45D(g)(1):
    "If, at any time during the 7-year period beginning on the date of the
    original issue of a qualified equity investment ... there is a recapture
    event with respect to such investment, then the tax imposed ... shall be
    increased by the credit recapture amount."

26 U.S.C. §45D(g)(3)(C): a recapture event occurs if "such investment is
    redeemed by such entity."

26 CFR §1.45D-1(c)(5)(i):
    "the 7-year credit period means the period of 7 years beginning on the
    date the qualified equity investment is initially made."

IRS, New Markets Tax Credit Audit Technique Guide (LMSB-04-0510-016, May
2010), p. 3:
    "The credit provided to the investor equals 39% of the QEI and is claimed
    over the seven-year credit period."

Consequences this package relies on:

* There are SEVEN credit allowance dates, at t = 0, 1, ..., 6 years after the
  QEI is made. The first credit falls on the same date as the equity is paid.
  The last falls at t = 6.
* The 7-year credit period (§1.45D-1(c)(5)(i)) and the 7-year recapture
  period (§45D(g)(1)) both begin on the QEI date and run to the seventh
  anniversary, t = 7. They are one period, not two. The seventh-year credit
  has no allowance date at t = 7: the last year of the period (t = 6 to t = 7)
  carries full recapture exposure after the last credit is earned.
* 39% is not stated in the statute or the regulation. It is the sum of the
  §45D(a)(2) percentages over the §45D(a)(3) dates, (3 × 5%) + (4 × 6%), and
  is stated expressly only in the IRS ATG. It is DERIVED below, never typed.

What this package does NOT model, and the day-level boundary: the primary
sources do not say, at the level of a day, whether an event on the seventh
anniversary itself falls inside the period. This package works in whole years
and treats an unwind at t = 7 as the end of the period; an unwind executed
before the seventh anniversary date falls inside it.
"""

# §45D(a)(3): the QEI date (t=0) and each of the 6 anniversary dates thereafter.
NUMBER_OF_ANNIVERSARY_DATES = 6
CREDIT_ALLOWANCE_YEARS = tuple(range(0, NUMBER_OF_ANNIVERSARY_DATES + 1))

# §45D(a)(2): 5% for the first 3 allowance dates, 6% for the remainder.
FIRST_TIER_RATE = 0.05
FIRST_TIER_DATES = 3
SECOND_TIER_RATE = 0.06

APPLICABLE_PERCENTAGES = tuple(
    FIRST_TIER_RATE if i < FIRST_TIER_DATES else SECOND_TIER_RATE
    for i in range(len(CREDIT_ALLOWANCE_YEARS))
)

# Derived, not typed. Stated as 39% only in the IRS ATG (p. 3); see module docstring.
TOTAL_CREDIT_RATE = sum(APPLICABLE_PERCENTAGES)

# §45D(g)(1) / §1.45D-1(c)(5)(i): 7 years beginning on the QEI date.
CREDIT_PERIOD_YEARS = 7
RECAPTURE_PERIOD_END_YEAR = CREDIT_PERIOD_YEARS

CITATION_SCHEDULE = "26 U.S.C. §45D(a)(2)-(3)"
CITATION_TOTAL_RATE = "IRS NMTC Audit Technique Guide (May 2010), p. 3"
CITATION_RECAPTURE_PERIOD = "26 U.S.C. §45D(g)(1); 26 CFR §1.45D-1(c)(5)(i)"
CITATION_REDEMPTION = "26 U.S.C. §45D(g)(3)(C)"
CITATION_RECAPTURE_AMOUNT = "26 U.S.C. §45D(g)(2)"


def pct_label(rate: float) -> str:
    """Render a rate as a percentage label, e.g. 0.05 -> '5%', 0.39 -> '39%'."""
    return f"{rate * 100:.0f}%"


def unwind_in_recapture_period(unwind_year: int) -> bool:
    """True when an unwind at ``unwind_year`` falls inside the 7-year period.

    Whole-year model: an unwind at t < 7 is inside the period; t = 7 is treated
    as its end (see the day-level boundary note in the module docstring).
    """
    return unwind_year < RECAPTURE_PERIOD_END_YEAR


# Allowance-date statuses under an unwind.
STATUS_ALLOWED = "ALLOWED"
STATUS_RECAPTURED = "RECAPTURED"
STATUS_NOT_ALLOWABLE = "NOT ALLOWABLE"


def allowance_statuses(unwind_year: int) -> tuple:
    """Status of each credit allowance date given the year the structure unwinds.

    * Unwind at or after t = 7: every allowance date is ALLOWED.
    * Unwind at t = k < 7: the QEI is redeemed inside the recapture period,
      which is a recapture event under §45D(g)(3)(C). Credits on allowance
      dates before k were claimed and are RECAPTURED under §45D(g)(2); the
      investor no longer holds the QEI on allowance dates at or after k, so
      those credits are NOT ALLOWABLE (§45D(a)(1) requires the taxpayer to
      hold the QEI on the credit allowance date).
    """
    if not unwind_in_recapture_period(unwind_year):
        return tuple(STATUS_ALLOWED for _ in CREDIT_ALLOWANCE_YEARS)
    return tuple(
        STATUS_RECAPTURED if t < unwind_year else STATUS_NOT_ALLOWABLE
        for t in CREDIT_ALLOWANCE_YEARS
    )


RECAPTURE_DISCLOSURE = (
    "The structure unwinds at t={k}, inside the 7-year recapture period that "
    "runs from the QEI date to t=7 ({period}). Under this package's definition "
    "an unwind redeems the QEI, and redemption of the QEI by the CDE is a "
    "recapture event ({redemption}). The credit recapture amount is every "
    "credit already allowed plus interest at the §6621 underpayment rate, and "
    "that interest is not deductible ({amount}). This package does not compute "
    "that interest. It assumes every credit claimed reduced tax liability "
    "(recapture reaches only such credits, §45D(g)(4)(A)), and it does not "
    "model a reinvestment of the proceeds that would avoid redemption."
)


def recapture_disclosure(unwind_year: int) -> str:
    return RECAPTURE_DISCLOSURE.format(
        k=unwind_year,
        period=CITATION_RECAPTURE_PERIOD,
        redemption=CITATION_REDEMPTION,
        amount=CITATION_RECAPTURE_AMOUNT,
    )


BOUNDARY_DISCLOSURE = (
    "The unwind is placed at t=7, the end of the 7-year recapture period "
    "({period}). This package works in whole years. The primary sources do not "
    "settle, at the level of a day, whether an event on the seventh anniversary "
    "itself is inside the period. An unwind executed before the seventh "
    "anniversary date is inside it, and every credit is then recaptured."
)


def boundary_disclosure() -> str:
    return BOUNDARY_DISCLOSURE.format(period=CITATION_RECAPTURE_PERIOD)


TIMING_CONVENTION_DISCLOSURE = (
    "Credits are placed on the statutory credit allowance dates, t=0 (the QEI "
    "date) through t=6 ({schedule}). The first credit falls on the date the "
    "equity is paid and is not discounted. The investor realizes a credit in "
    "cash through estimated payments and returns filed for the taxable year in "
    "which the allowance date falls, and that lag is not modeled."
)


def timing_convention_disclosure() -> str:
    return TIMING_CONVENTION_DISCLOSURE.format(schedule=CITATION_SCHEDULE)


# ── the substantially-all requirement: REFUSED, not computed ─────────────────
#
# Retrieved 2026-09-27:
#   26 U.S.C. §45D(b)(1)(B): "substantially all of such cash is used by the
#     qualified community development entity to make qualified low-income
#     community investments" -- no percentage in the statute.
#   26 CFR §1.45D-1(c)(5)(i): "the term substantially all means at least 85
#     percent"; satisfied "for each annual period in the 7-year credit period",
#     one testing date in the first annual period, then "performed every six
#     months and the average of the two calculations for the annual period is
#     at least 85 percent."
#   §1.45D-1(c)(5)(ii) direct tracing: numerator "the CDE's aggregate cost basis
#     determined under section 1012" in QLICIs traceable to the investment;
#     denominator "the amount of the taxpayer's cash investment".
#   §1.45D-1(c)(5)(iii) safe harbor: numerator the CDE's §1012 cost basis in all
#     its QLICIs; denominator "the CDE's aggregate cost basis determined under
#     section 1012 in all of its assets".
#   §1.45D-1(c)(5)(iv): cash is treated as invested in a QLICI "only to the
#     extent that the cash is so invested within the 12-month period beginning
#     on the date the cash is paid".
#   §1.45D-1(c)(5)(v): "85 percent is reduced to 75 percent for the seventh year
#     of the 7-year credit period".
#   §1.45D-1(d)(2)(i): returned capital must be reinvested "no later than 12
#     months from the date of receipt".

SUBSTANTIALLY_ALL_STATUS = "REFUSED"
CITATION_SUBSTANTIALLY_ALL = "26 CFR §1.45D-1(c)(5)"

SUBSTANTIALLY_ALL_REFUSAL_REASONS = (
    "The 85% threshold is regulatory, not statutory: §45D(b)(1)(B) says only "
    "\"substantially all\"; 85% is 26 CFR §1.45D-1(c)(5)(i).",
    "The numerator is the CDE's §1012 cost basis in its QLICIs, not their face "
    "amount (§1.45D-1(c)(5)(ii)-(iii)); this package models face amounts only.",
    "There are two alternative tests with different denominators: direct tracing "
    "divides by the taxpayer's cash investment (§1.45D-1(c)(5)(ii)); the safe "
    "harbor divides by the CDE's cost basis in ALL of its assets "
    "(§1.45D-1(c)(5)(iii)), which is not a deal-level quantity.",
    "It is not testable at closing: cash counts as invested only if invested "
    "within 12 months of payment (§1.45D-1(c)(5)(iv)); the test then runs for "
    "every annual period of the 7-year credit period, once in the first and "
    "semiannually averaged after (§1.45D-1(c)(5)(i)), with returned capital "
    "reinvested within 12 months (§1.45D-1(d)(2)(i)).",
    "The threshold is 75%, not 85%, in the seventh year (§1.45D-1(c)(5)(v)).",
)

DEPLOYMENT_RATIO_NOTE = (
    "The closing-date QLICI deployment ratio is QLICI total / QEI on the closing "
    "date, at face. It is NOT the substantially-all test of {cite}, which this "
    "package refuses to compute for the reasons listed. A breach of that test is "
    "a recapture event (§45D(g)(3)(B))."
)


def deployment_ratio_note() -> str:
    return DEPLOYMENT_RATIO_NOTE.format(cite=CITATION_SUBSTANTIALLY_ALL)


# ── B-loan forgiveness and bona fide debt (IRS ATG) ──────────────────────────
# Retrieved 2026-09-27: IRS, New Markets Tax Credit Audit Technique Guide
# (LMSB-04-0510-016, May 2010), p. 17, under the heading "Intent to Forgive or
# Otherwise Not Collect Debt". The two sentences below are quoted verbatim.

CITATION_ATG_FORGIVENESS = (
    "IRS NMTC Audit Technique Guide (May 2010), p. 17, "
    "\"Intent to Forgive or Otherwise Not Collect Debt\""
)
ATG_BONA_FIDE_DEBT_QUOTE = (
    "\"An essential element of bona fide debt is whether there exists a good-faith "
    "intent on the part of the recipient of the funds to make repayment and a "
    "good-faith intent on the part of the person advancing the funds to enforce "
    "repayment.\" ... \"In some instances, as an exit strategy, the CDE may intend "
    "to eventually forgive or otherwise not collect on the debt after the end of the "
    "7-year credit period. If such an intention is reflected in a pre-arranged "
    "feature; i.e., a statement in the loan documents that the lender will forgive "
    "the loan, the loan is not bona fide debt for federal income tax purposes.\""
)

FORGIVENESS_NOTE = (
    "B-loan forgiveness is a negotiated exit term of the deal documents; this "
    "package does not treat it as a feature of the credit, so "
    "b_loan_forgiveness_rate is an input with no default. The {cite} states: {quote}"
)


def forgiveness_note() -> str:
    return FORGIVENESS_NOTE.format(cite=CITATION_ATG_FORGIVENESS, quote=ATG_BONA_FIDE_DEBT_QUOTE)
