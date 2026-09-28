import collections.abc
import dataclasses
import math
import numbers
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Union

from nmtccalc import statute
from nmtccalc.exceptions import NegativeTrancheError, UnbalancedStackError


class Provenance(str, Enum):
    """Where a capital-stack figure comes from.

    SUPPLIED: the user typed it (a real term).
    DERIVED:  the package computed it from other inputs under a stated rule.
              A DERIVED figure is a screening-time estimate, not a closing term.
    """
    DERIVED = "DERIVED"
    SUPPLIED = "SUPPLIED"


@dataclass(frozen=True)
class Basis:
    """The provenance of one figure and the rule that produced it."""
    provenance: Provenance
    rule: str

    def label(self) -> str:
        return f"{self.provenance.value}: {self.rule}"


# HOUSE: whether guarantee fees enter the DSCR denominator. This is a house
# election, not attributed to any authority. The default EXCLUDES them, which
# makes DSCR higher than including them would; set
# include_guarantee_fee_in_dscr=True for the opposite treatment.
HOUSE_GUARANTEE_FEE_IN_DSCR = False

# Tolerance, in dollars, for A + B reconciling to QLICI total when both are SUPPLIED.
STACK_TOLERANCE_DOLLARS = 1.0

_FLOAT_FIELDS = (
    "total_project_cost", "nmtc_allocation", "credit_price", "leverage_loan_rate",
    "qlici_a_loan_rate", "qlici_b_loan_rate", "cde_fee_rate", "discount_rate",
    "guarantee_fee_rate", "exit_fee_rate",
)
_OPTIONAL_FLOAT_FIELDS = (
    "qlici_a_loan_amount", "qlici_b_loan_amount",
    "b_loan_forgiveness_rate", "qalicb_alternative_borrowing_rate",
)


def _is_finite_real(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, numbers.Real) and math.isfinite(value)


# Rate fields that must lie in [0, 1). Zero is allowed for each: 0% QLICI
# coupons are plausible (and DSCR then REFUSES, see waterfall), and 0% fees
# mean "no fee". credit_price, cde_fee_rate and discount_rate keep their
# stricter open-interval checks below.
_RATE_FIELDS = (
    "leverage_loan_rate", "qlici_a_loan_rate", "qlici_b_loan_rate",
    "guarantee_fee_rate", "exit_fee_rate",
)

# Upper bound on unwind_year. NOT a statutory limit: a sanity bound. The model
# carries interest-only balances with no amortization, so a very long hold is
# not modeled faithfully, and a value above this is almost always a unit
# mistake (a calendar year such as 2033 typed as years after the QEI date).
MAX_UNWIND_YEAR = 30


@dataclass(frozen=True)
class NMTCDeal:
    """
    Core input contract for an NMTC leveraged transaction.
    All dollar amounts in whole dollars (e.g. 10_000_000 for $10MM).

    Every capital-stack figure carries a provenance (see ``provenance`` and
    ``basis``). By default the stack is DERIVED from QEI, credit price and the
    CDE fee rate — a screening model. Where real terms exist, the A/B split can
    be SUPPLIED with ``qlici_a_loan_amount`` and/or ``qlici_b_loan_amount``:

    * one supplied  -> the other is DERIVED as QLICI total less the supplied one;
    * both supplied -> they must reconcile to QLICI total within
      ``STACK_TOLERANCE_DOLLARS`` or construction is refused.

    Investor equity (credits x price) and the leverage loan (QEI less equity,
    in a two-source fund) are identities of this model, not negotiated terms,
    so they are always DERIVED.

    To vary one input across a sweep use ``with_credit_price`` /
    ``with_discount_rate``, which re-derive every DERIVED figure, hold every
    SUPPLIED figure, and re-run all construction checks.
    """
    project_name: str
    total_project_cost: float          # total project budget
    nmtc_allocation: float             # QEI amount
    credit_price: float                # $ per $1 of NMTC benefit e.g. 0.83
    leverage_loan_rate: float          # annual interest rate e.g. 0.045
    qlici_a_loan_rate: float           # senior QLICI loan rate
    qlici_b_loan_rate: float           # subordinate QLICI loan rate
    cde_fee_rate: float                # CDE upfront fee as % of QEI e.g. 0.02
    discount_rate: float = 0.08        # for NPV/IRR calculations
    # Net operating income for years 1..unwind_year: either ONE number applied
    # to every year (flat -- the waterfall then says its DSCR is a single
    # stabilized figure) or a sequence with exactly unwind_year entries.
    noi: Optional[Union[float, Sequence[float]]] = None
    guarantee_fee_rate: float = 0.0    # annual guarantee fee as % of leverage loan e.g. 0.01
    exit_fee_rate: float = 0.0         # exit fee at unwind as % of QEI e.g. 0.005
    investor_name: Optional[str] = None
    cde_name: Optional[str] = None
    project_location: Optional[str] = None
    # Year (t, in years after the QEI date) in which the structure unwinds:
    # QLICIs repaid or forgiven, the put exercised and the QEI redeemed.
    # Default 7 = the end of the 7-year recapture period (§45D(g)(1)).
    # An unwind before 7 is inside the recapture period (§45D(g)(3)(C)).
    unwind_year: int = statute.RECAPTURE_PERIOD_END_YEAR
    # SUPPLIED A/B split, where real terms exist. None = DERIVED.
    qlici_a_loan_amount: Optional[float] = None
    qlici_b_loan_amount: Optional[float] = None
    # Share of the B loan forgiven at unwind, 0..1. NO DEFAULT: forgiveness is
    # a negotiated exit term, and the IRS ATG (p. 17) holds that forgiveness
    # stated in the loan documents defeats bona fide debt. When None, every
    # figure that depends on it is REFUSED; everything else still computes.
    b_loan_forgiveness_rate: Optional[float] = None
    # The QALICB's own alternative borrowing rate, for interest savings. When
    # None, interest savings are REFUSED. (0.2.1 used the Investment Fund's
    # leverage rate, the wrong entity's cost of capital.)
    qalicb_alternative_borrowing_rate: Optional[float] = None
    # HOUSE ELECTION (see HOUSE_GUARANTEE_FEE_IN_DSCR): False excludes the
    # annual guarantee fee from the DSCR denominator; True includes it. Net
    # cash flow deducts the fee either way.
    include_guarantee_fee_in_dscr: bool = HOUSE_GUARANTEE_FEE_IN_DSCR

    def __post_init__(self):
        # Frozen dataclass: values are normalised with object.__setattr__ here,
        # and attribute assignment after construction raises
        # FrozenInstanceError, so no refusal below can be bypassed by mutation.
        # dataclasses.replace() and the with_* methods build a new instance and
        # re-run every check.
        for name in _FLOAT_FIELDS:
            value = getattr(self, name)
            if not _is_finite_real(value):
                raise ValueError(f"{name} must be a finite number")
            object.__setattr__(self, name, float(value))
        for name in _OPTIONAL_FLOAT_FIELDS:
            value = getattr(self, name)
            if value is not None:
                if not _is_finite_real(value):
                    raise ValueError(f"{name} must be a finite number or None")
                object.__setattr__(self, name, float(value))
        for name in _RATE_FIELDS:
            if not (0 <= getattr(self, name) < 1):
                raise ValueError(f"{name} must be at least 0 and below 1 (e.g. 0.045)")
        if self.total_project_cost <= 0:
            raise ValueError("total_project_cost must be positive")
        if self.nmtc_allocation <= 0:
            raise ValueError("nmtc_allocation (QEI) must be positive")
        if self.nmtc_allocation > self.total_project_cost:
            raise ValueError("nmtc_allocation cannot exceed total_project_cost")
        if not (0 < self.credit_price < 1):
            raise ValueError("credit_price must be between 0 and 1 (e.g. 0.83)")
        if not (0 < self.cde_fee_rate < 1):
            raise ValueError("cde_fee_rate must be between 0 and 1 (e.g. 0.02)")
        if isinstance(self.unwind_year, bool) or not isinstance(self.unwind_year, numbers.Integral):
            raise ValueError("unwind_year must be a whole number of years after the QEI date")
        object.__setattr__(self, "unwind_year", int(self.unwind_year))
        if self.unwind_year < 1:
            raise ValueError("unwind_year must be at least 1 (years after the QEI date)")
        if self.unwind_year > MAX_UNWIND_YEAR:
            raise ValueError(
                f"unwind_year must be at most {MAX_UNWIND_YEAR} (years after the QEI date, "
                f"not a calendar year); see MAX_UNWIND_YEAR")
        if not (0 < self.discount_rate < 1):
            raise ValueError("discount_rate must be between 0 and 1 (e.g. 0.08)")
        self._validate_noi()
        if not isinstance(self.include_guarantee_fee_in_dscr, bool):
            raise ValueError("include_guarantee_fee_in_dscr must be True or False")
        if self.b_loan_forgiveness_rate is not None and not (0 <= self.b_loan_forgiveness_rate <= 1):
            raise ValueError("b_loan_forgiveness_rate must be between 0 and 1 inclusive")
        if self.qalicb_alternative_borrowing_rate is not None and \
                not (0 <= self.qalicb_alternative_borrowing_rate < 1):
            raise ValueError("qalicb_alternative_borrowing_rate must be at least 0 and below 1")
        self._refuse_negative_tranches()
        self._refuse_unbalanced_split()

    _NOI_MESSAGE = ("noi must be a finite non-negative number, a sequence of them with "
                    "one entry per year 1..unwind_year, or None")

    def _validate_noi(self):
        noi = self.noi
        if noi is None:
            return
        if _is_finite_real(noi):
            if noi < 0:
                raise ValueError("noi must be non-negative")
            object.__setattr__(self, "noi", float(noi))
            return
        if isinstance(noi, numbers.Real) or isinstance(noi, (str, bytes)) or isinstance(noi, bool):
            raise ValueError(self._NOI_MESSAGE)
        # tuple() of a mapping yields its KEYS and a set has no order, so both
        # would be silently wrong; a 2-D array is not a year-by-year series.
        if isinstance(noi, collections.abc.Mapping):
            raise ValueError("noi must not be a mapping (a dict gives its keys, not its values); "
                             "pass the values in year order")
        if isinstance(noi, (collections.abc.Set, frozenset)):
            raise ValueError("noi must not be a set (a set has no order); pass a list in year order")
        if getattr(noi, "ndim", 1) != 1:
            raise ValueError(f"noi must be one-dimensional (got an array with ndim={noi.ndim})")
        try:
            values = tuple(noi)       # list, tuple, range, numpy array, pandas Series
        except TypeError:
            raise ValueError(self._NOI_MESSAGE) from None
        if len(values) != self.unwind_year:
            raise ValueError(
                f"noi series has {len(values)} entries; it needs exactly one per "
                f"year 1..unwind_year ({self.unwind_year})")
        for v in values:
            if not _is_finite_real(v):
                raise ValueError("noi series entries must be finite numbers")
            if v < 0:
                raise ValueError("noi must be non-negative")
        object.__setattr__(self, "noi", tuple(float(v) for v in values))

    @property
    def noi_schedule(self) -> Optional[list]:
        """NOI for years 1..unwind_year, or None when noi was not supplied."""
        if self.noi is None:
            return None
        if isinstance(self.noi, tuple):
            return list(self.noi)
        return [self.noi] * self.unwind_year

    @property
    def noi_is_series(self) -> bool:
        return isinstance(self.noi, tuple)

    def _refuse_negative_tranches(self):
        """Refuse any capital-stack tranche below zero, at construction.

        A negative tranche is not a structure: a negative B loan produces
        negative B-loan interest, which understates debt service and inflates
        DSCR, and a negative "forgiveness" that renders as a subsidy.
        """
        tranches = (
            ("investor_equity", self.investor_equity),
            ("leverage_loan", self.leverage_loan),
            ("qlici_total", self.qlici_total),
            ("qlici_a_loan", self.qlici_a_loan),
            ("qlici_b_loan", self.qlici_b_loan),
        )
        for name, amount in tranches:
            if amount < 0:
                detail = ""
                if name == "qlici_b_loan" and self.qlici_b_loan_amount is None \
                        and self.qlici_a_loan_amount is None:
                    detail = (
                        f" The CDE fee (${self.cde_fee:,.0f} = "
                        f"{self.cde_fee_rate:.2%} of QEI) exceeds investor equity "
                        f"(${self.investor_equity:,.0f} = "
                        f"{statute.pct_label(statute.TOTAL_CREDIT_RATE)} of QEI x "
                        f"{self.credit_price} credit price). With the B loan derived as "
                        f"equity less fee, cde_fee_rate must not exceed "
                        f"{statute.pct_label(statute.TOTAL_CREDIT_RATE)} x credit_price = "
                        f"{statute.TOTAL_CREDIT_RATE * self.credit_price:.4f}."
                    )
                elif name in ("qlici_a_loan", "qlici_b_loan"):
                    detail = f" ({self.basis[name].label()})"
                raise NegativeTrancheError(
                    f"{name} would be ${amount:,.0f}; a negative tranche is refused."
                    + detail
                )

    def _refuse_unbalanced_split(self):
        """When both A and B are SUPPLIED they must reconcile to QLICI total."""
        if self.qlici_a_loan_amount is None or self.qlici_b_loan_amount is None:
            return
        gap = self.qlici_a_loan_amount + self.qlici_b_loan_amount - self.qlici_total
        if abs(gap) > STACK_TOLERANCE_DOLLARS:
            raise UnbalancedStackError(
                f"SUPPLIED A loan ${self.qlici_a_loan_amount:,.0f} + B loan "
                f"${self.qlici_b_loan_amount:,.0f} = "
                f"${self.qlici_a_loan_amount + self.qlici_b_loan_amount:,.0f}, "
                f"which differs from QLICI total ${self.qlici_total:,.0f} "
                f"(QEI less CDE fee) by ${gap:,.0f}."
            )

    # ── rebalancing constructors ─────────────────────────────────────────────

    def with_credit_price(self, credit_price: float) -> "NMTCDeal":
        """A copy at ``credit_price``: DERIVED figures re-derive (equity,
        leverage loan, and any A/B tranche not SUPPLIED), SUPPLIED figures are
        held, and every construction check re-runs — so a price at which a
        tranche would go negative raises NegativeTrancheError."""
        return dataclasses.replace(self, credit_price=credit_price)

    def with_discount_rate(self, discount_rate: float) -> "NMTCDeal":
        """A copy at ``discount_rate``. The discount rate does not enter the
        capital stack; every figure's provenance is unchanged."""
        return dataclasses.replace(self, discount_rate=discount_rate)

    # ── capital stack ───────────────────────────────────────────────────────

    @property
    def qei(self) -> float:
        """Qualified Equity Investment amount."""
        return self.nmtc_allocation

    @property
    def total_nmtcs(self) -> float:
        """Total tax credits: the §45D(a)(2) percentages summed over the seven
        §45D(a)(3) allowance dates, which is 39% of QEI (not stated in the
        statute; cited to the IRS ATG). Derived from ``statute``, not typed."""
        return self.qei * statute.TOTAL_CREDIT_RATE

    @property
    def investor_equity(self) -> float:
        """Investor equity contribution: total NMTCs × credit price."""
        return self.total_nmtcs * self.credit_price

    @property
    def leverage_loan(self) -> float:
        """Leverage loan amount: QEI minus investor equity."""
        return self.qei - self.investor_equity

    @property
    def cde_fee(self) -> float:
        """CDE upfront fee in dollars."""
        return self.qei * self.cde_fee_rate

    @property
    def qlici_total(self) -> float:
        """Total QLICI to QALICB: QEI minus CDE fee."""
        return self.qei - self.cde_fee

    @property
    def qlici_a_loan(self) -> float:
        """A Loan: SUPPLIED if given; else QLICI total less a SUPPLIED B loan;
        else DERIVED to mirror the leverage loan."""
        if self.qlici_a_loan_amount is not None:
            return self.qlici_a_loan_amount
        if self.qlici_b_loan_amount is not None:
            return self.qlici_total - self.qlici_b_loan_amount
        return self.leverage_loan

    @property
    def qlici_b_loan(self) -> float:
        """B Loan: SUPPLIED if given; else QLICI total less a SUPPLIED A loan;
        else DERIVED as investor equity net of the CDE fee."""
        if self.qlici_b_loan_amount is not None:
            return self.qlici_b_loan_amount
        if self.qlici_a_loan_amount is not None:
            return self.qlici_total - self.qlici_a_loan_amount
        return self.investor_equity - self.cde_fee

    @property
    def guarantee_fee_annual(self) -> float:
        """Annual guarantee fee in dollars: leverage loan × guarantee_fee_rate."""
        return self.leverage_loan * self.guarantee_fee_rate

    @property
    def exit_fee(self) -> float:
        """Exit fee at unwind in dollars: QEI × exit_fee_rate."""
        return self.qei * self.exit_fee_rate

    # ── provenance ──────────────────────────────────────────────────────────

    @property
    def basis(self) -> dict:
        """Quantity name -> Basis (provenance and the rule that produced it)."""
        D, S = Provenance.DERIVED, Provenance.SUPPLIED
        total = statute.pct_label(statute.TOTAL_CREDIT_RATE)
        a_sup = self.qlici_a_loan_amount is not None
        b_sup = self.qlici_b_loan_amount is not None
        if a_sup:
            a = Basis(S, "qlici_a_loan_amount")
        elif b_sup:
            a = Basis(D, "QLICI total - B loan (SUPPLIED)")
        else:
            a = Basis(D, "mirrors the leverage loan")
        if b_sup:
            b = Basis(S, "qlici_b_loan_amount")
        elif a_sup:
            b = Basis(D, "QLICI total - A loan (SUPPLIED)")
        else:
            b = Basis(D, "investor equity - CDE fee")
        return {
            "total_project_cost": Basis(S, "total_project_cost"),
            "qei": Basis(S, "nmtc_allocation"),
            "total_nmtcs": Basis(D, f"{total} x QEI ({statute.CITATION_SCHEDULE}; "
                                    f"{total} per {statute.CITATION_TOTAL_RATE})"),
            "investor_equity": Basis(D, "total NMTCs x credit price"),
            "leverage_loan": Basis(D, "QEI - investor equity (two-source fund)"),
            "cde_fee": Basis(D, "QEI x cde_fee_rate"),
            "qlici_total": Basis(D, "QEI - CDE fee (all net proceeds deployed at closing)"),
            "qlici_a_loan": a,
            "qlici_b_loan": b,
            "guarantee_fee_annual": Basis(D, "leverage loan x guarantee_fee_rate"),
            "exit_fee": Basis(D, "QEI x exit_fee_rate"),
        }

    @property
    def provenance(self) -> dict:
        """Quantity name -> Provenance (DERIVED or SUPPLIED)."""
        return {name: b.provenance for name, b in self.basis.items()}

    @property
    def qei_mm(self) -> float:
        return self.qei / 1_000_000

    @property
    def total_project_cost_mm(self) -> float:
        return self.total_project_cost / 1_000_000

    def __repr__(self):
        return (
            f"NMTCDeal(project='{self.project_name}', "
            f"QEI=${self.qei_mm:.1f}MM, "
            f"NMTCs=${self.total_nmtcs/1e6:.2f}MM, "
            f"credit_price=${self.credit_price:.2f})"
        )
