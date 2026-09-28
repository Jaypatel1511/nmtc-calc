from dataclasses import dataclass
from typing import Optional
import warnings

import pandas as pd

from nmtccalc import statute
from nmtccalc.data.schema import NMTCDeal
from nmtccalc.exceptions import LeverageShortfallWarning
from nmtccalc.models.subsidy import REFUSED_FORGIVENESS


FUND_LINE_DISCLOSURE = (
    "Investment Fund line: the fund services its leverage loan (interest-only, "
    "principal due at unwind) from QLICI flows passed up through the CDE. All "
    "A-loan and B-loan interest is counted as reaching the fund. This package "
    "has no input for ongoing CDE or sub-CDE fees, which would reduce that "
    "amount, nor for fund reserves or other sources, which could cover a gap. "
    "The fund line is therefore neither a floor nor a ceiling on the fund's "
    "true position. To bracket it, the shortfall is also shown counting A-loan "
    "interest only, since B interest reaches the fund only net of CDE costs this "
    "package takes no input for. The principal gap counts A-loan principal only; "
    "any B-loan principal repaid rather than forgiven would also reach the fund, "
    "so the principal gap shown is conservative (it can overstate the gap)."
)

GUARANTEE_FEE_NOTE = (
    "HOUSE ELECTION: guarantee fees are {treatment} the DSCR denominator. This is "
    "a house election, not attributed to any authority. Excluding a recurring fee "
    "makes DSCR higher than including it. For the opposite treatment set "
    "include_guarantee_fee_in_dscr={opposite}. Net cash flow deducts the fee "
    "either way."
)

DSCR_REFUSED_ZERO_DS = (
    "DSCR REFUSED: debt service <= 0 (the A and B coupons are both 0%{fee}), so "
    "coverage is undefined. Net cash flow is still shown."
)
DSCR_NOT_COMPUTED_NO_NOI = "DSCR not computed: noi was not supplied."

FLAT_DSCR_NOTE = (
    "This is one stabilized figure, not a schedule: debt service is interest-only "
    "on fixed balances, and NOI {how}, so every row is the same. Supply noi as a "
    "sequence with one entry per year to model a schedule."
)

SHORTFALL_WARNING = (
    "LEVERAGE SHORTFALL: the Investment Fund cannot service its leverage loan "
    "from the modeled QLICI flows. Annual leverage interest ${lev:,.0f} exceeds "
    "QLICI interest reaching the fund ${qlici:,.0f} by ${short:,.0f} per year "
    "(${total:,.0f} over {years} years){principal}. QALICB coverage (DSCR) does "
    "not measure this, because the leverage loan is the fund's debt, not the "
    "QALICB's."
)

PRINCIPAL_GAP_WARNING = (
    "LEVERAGE SHORTFALL: the A-loan principal repaid to the fund at unwind "
    "(${a:,.0f}) is ${gap:,.0f} less than the leverage loan principal due "
    "(${lev:,.0f})."
)


@dataclass
class WaterfallYear:
    year: int
    noi: Optional[float]
    a_loan_interest: float
    b_loan_interest: float
    total_debt_service: float
    dscr: Optional[float]
    guarantee_fee: float
    net_cash_flow: Optional[float]
    b_loan_forgiven: Optional[float] = 0.0   # None in the unwind year when the forgiveness rate is not supplied
    exit_fee: float = 0.0
    # Investment Fund level (leverage loan)
    leverage_loan_interest: float = 0.0
    fund_qlici_interest: float = 0.0
    fund_net_cash_flow: float = 0.0


@dataclass
class WaterfallResult:
    """Output object from NMTC cash flow waterfall analysis.

    QALICB level: NOI, A/B interest, DSCR, net cash flow.
    Investment Fund level: the leverage loan's annual interest, the QLICI
    interest reaching the fund, and the difference. ``annual_fund_shortfall``
    and ``leverage_principal_gap`` are 0 when the fund can service its loan;
    ``leverage_serviced`` is False otherwise and a LeverageShortfallWarning is
    emitted.
    """
    project_name: str
    years: list
    total_interest_paid: float
    b_loan_forgiven: Optional[float]
    exit_fee: float
    net_subsidy_at_unwind: Optional[float]
    avg_dscr: Optional[float]
    min_dscr: Optional[float]
    dscr_varies: bool
    guarantee_fee_in_dscr: bool
    dscr_refused_reason: Optional[str]
    noi_is_series: bool
    unwind_year: int
    in_recapture_period: bool
    leverage_loan: float
    annual_leverage_interest: float
    annual_fund_qlici_interest: float
    annual_fund_shortfall: float
    annual_fund_shortfall_a_only: float
    qlici_b_loan: float
    basis: dict
    total_fund_shortfall: float
    leverage_principal_due: float
    a_loan_principal_repaid: float
    leverage_principal_gap: float
    leverage_serviced: bool
    warning_messages: tuple

    def summary(self) -> pd.DataFrame:
        rows = []
        for yr in self.years:
            rows.append({
                "Year": f"Y{yr.year}",
                "NOI": f"${yr.noi:,.0f}" if yr.noi is not None else "—",
                "A Int.": f"${yr.a_loan_interest:,.0f}",
                "B Int.": f"${yr.b_loan_interest:,.0f}",
                "Guar. Fee": f"${yr.guarantee_fee:,.0f}" if yr.guarantee_fee else "—",
                "Total DS": f"${yr.total_debt_service:,.0f}",
                "DSCR": (f"{yr.dscr:.2f}x" if yr.dscr is not None
                         else ("REFUSED" if self.dscr_refused_reason else "—")),
                "Net CF": f"${yr.net_cash_flow:,.0f}" if yr.net_cash_flow is not None else "—",
                "Lev. Int.": f"${yr.leverage_loan_interest:,.0f}",
                "Fund Net": f"${yr.fund_net_cash_flow:,.0f}",
            })

        df = pd.DataFrame(rows)
        print(f"\nCash Flow Waterfall — {self.project_name}")
        print("=" * 100)
        print(df.to_string(index=False))
        print()
        print("Investment Fund (leverage loan):")
        print(f"  Leverage Loan:              ${self.leverage_loan:,.0f}")
        print(f"  Annual Leverage Interest:   ${self.annual_leverage_interest:,.0f}")
        print(f"  QLICI Interest to Fund:     ${self.annual_fund_qlici_interest:,.0f}")
        print(f"  Leverage Loan basis:        {self.basis.get('leverage_loan', '')}")
        print(f"  A / B Loan principal:       ${self.a_loan_principal_repaid:,.0f} "
              f"[{self.basis.get('qlici_a_loan', '')}] / ${self.qlici_b_loan:,.0f} "
              f"[{self.basis.get('qlici_b_loan', '')}]")
        print(f"  Annual Fund Shortfall:      ${self.annual_fund_shortfall:,.0f}  (A and B interest)")
        print(f"  Shortfall, A interest only: ${self.annual_fund_shortfall_a_only:,.0f}")
        print(f"  Principal Gap at Unwind:    ${self.leverage_principal_gap:,.0f}")
        for msg in self.warning_messages:
            print(f"  {msg}")
        print(f"  {FUND_LINE_DISCLOSURE}")
        print()
        print(f"Unwind at t={self.unwind_year}:")
        if self.b_loan_forgiven is None:
            print(f"  B Loan Forgiven:  {REFUSED_FORGIVENESS}")
        else:
            print(f"  B Loan Forgiven:  ${self.b_loan_forgiven:,.0f}")
        if self.exit_fee:
            print(f"  Exit Fee:         (${self.exit_fee:,.0f})")
        if self.net_subsidy_at_unwind is None:
            print(f"  Net Subsidy at Unwind (t={self.unwind_year}): {REFUSED_FORGIVENESS}")
        else:
            print(f"  Net Subsidy at Unwind (t={self.unwind_year}): ${self.net_subsidy_at_unwind:,.0f}")
        if self.in_recapture_period:
            print("  " + statute.recapture_disclosure(self.unwind_year))
        elif self.unwind_year == statute.RECAPTURE_PERIOD_END_YEAR:
            print("  " + statute.boundary_disclosure())
        if self.dscr_refused_reason:
            print("\n" + self.dscr_refused_reason)
        elif self.avg_dscr is None:
            print("\n" + DSCR_NOT_COMPUTED_NO_NOI)
        if self.avg_dscr is not None:
            print("\n" + GUARANTEE_FEE_NOTE.format(
                treatment="included in" if self.guarantee_fee_in_dscr else "excluded from",
                opposite=not self.guarantee_fee_in_dscr))
            if self.dscr_varies:
                print(f"\nDSCR:  Avg {self.avg_dscr:.2f}x  |  Min {self.min_dscr:.2f}x")
            else:
                how = ("is the same in every year of the series supplied" if self.noi_is_series
                       else "is a single number applied to every year")
                print(f"\nDSCR:  {self.min_dscr:.2f}x every year. {FLAT_DSCR_NOTE.format(how=how)}")
        print()
        return df

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "total_interest_paid": self.total_interest_paid,
            "b_loan_forgiven": self.b_loan_forgiven,
            "exit_fee": self.exit_fee,
            "net_subsidy_at_unwind": self.net_subsidy_at_unwind,
            "avg_dscr": self.avg_dscr,
            "min_dscr": self.min_dscr,
            "dscr_varies": self.dscr_varies,
            "guarantee_fee_in_dscr": self.guarantee_fee_in_dscr,
            "dscr_refused_reason": self.dscr_refused_reason,
            "noi_is_series": self.noi_is_series,
            "unwind_year": self.unwind_year,
            "in_recapture_period": self.in_recapture_period,
            "leverage_loan": self.leverage_loan,
            "annual_leverage_interest": self.annual_leverage_interest,
            "annual_fund_qlici_interest": self.annual_fund_qlici_interest,
            "annual_fund_shortfall": self.annual_fund_shortfall,
            "annual_fund_shortfall_a_only": self.annual_fund_shortfall_a_only,
            "total_fund_shortfall": self.total_fund_shortfall,
            "leverage_principal_due": self.leverage_principal_due,
            "a_loan_principal_repaid": self.a_loan_principal_repaid,
            "leverage_principal_gap": self.leverage_principal_gap,
            "leverage_serviced": self.leverage_serviced,
        }


def analyze(deal: NMTCDeal) -> WaterfallResult:
    """
    Generate the year-by-year NMTC cash flow waterfall.

    Models interest-only debt service on A and B loans for years 1 through
    ``deal.unwind_year``, with the unwind in that year (B loan forgiveness at
    ``deal.b_loan_forgiveness_rate`` -- REFUSED when not supplied --
    exit fee, put/call exercise, QEI redemption). DSCR is computed each year
    when noi is provided. The default unwind is t=7, the end of the 7-year
    recapture period (§45D(g)(1)); an earlier unwind is inside it and is a
    recapture event (§45D(g)(3)(C)).

    The leverage loan is serviced at the Investment Fund level: interest-only
    at ``leverage_loan_rate`` each year, principal due at unwind. It is
    reconciled against the QLICI interest reaching the fund each year and the
    A-loan principal repaid at unwind. Any shortfall is reported on the result
    and emitted as a ``LeverageShortfallWarning``.

    Guarantee fees (if any) are shown as a separate line item and always
    reduce net cash flow. Whether they enter the DSCR denominator is a HOUSE
    ELECTION (``deal.include_guarantee_fee_in_dscr``, default False =
    excluded), not a cited convention; GUARANTEE_FEE_NOTE renders it.

    Args:
        deal: NMTCDeal instance

    Returns:
        WaterfallResult with annual waterfall rows and the unwind summary
    """
    a_interest = deal.qlici_a_loan * deal.qlici_a_loan_rate
    b_interest = deal.qlici_b_loan * deal.qlici_b_loan_rate
    total_ds = a_interest + b_interest
    guarantee_fee = deal.guarantee_fee_annual
    dscr_denominator = total_ds + (guarantee_fee if deal.include_guarantee_fee_in_dscr else 0.0)

    lev_interest = deal.leverage_loan * deal.leverage_loan_rate
    fund_qlici_interest = a_interest + b_interest
    fund_net = fund_qlici_interest - lev_interest

    k = deal.unwind_year
    rate = deal.b_loan_forgiveness_rate
    forgiven = deal.qlici_b_loan * rate if rate is not None else None
    schedule = deal.noi_schedule
    years = []
    for yr in range(1, k + 1):
        noi = schedule[yr - 1] if schedule is not None else None
        dscr = (noi / dscr_denominator) if (noi is not None and dscr_denominator > 0) else None
        net_cf = (noi - total_ds - guarantee_fee) if noi is not None else None

        years.append(WaterfallYear(
            year=yr,
            noi=noi,
            a_loan_interest=a_interest,
            b_loan_interest=b_interest,
            total_debt_service=total_ds,
            dscr=dscr,
            guarantee_fee=guarantee_fee,
            net_cash_flow=net_cf,
            b_loan_forgiven=forgiven if yr == k else 0.0,
            exit_fee=deal.exit_fee if yr == k else 0.0,
            leverage_loan_interest=lev_interest,
            fund_qlici_interest=fund_qlici_interest,
            fund_net_cash_flow=fund_net,
        ))

    dscrs = [yr.dscr for yr in years if yr.dscr is not None]
    dscr_varies = len(set(dscrs)) > 1

    annual_short = max(0.0, -fund_net)
    principal_gap = max(0.0, deal.leverage_loan - deal.qlici_a_loan)

    messages = []
    if annual_short > 0:
        principal = (
            f", and the A-loan principal repaid at unwind is ${principal_gap:,.0f} "
            f"less than the leverage principal due" if principal_gap > 0 else ""
        )
        messages.append(SHORTFALL_WARNING.format(
            lev=lev_interest, qlici=fund_qlici_interest, short=annual_short,
            total=annual_short * k, years=k, principal=principal,
        ))
    elif principal_gap > 0:
        messages.append(PRINCIPAL_GAP_WARNING.format(
            a=deal.qlici_a_loan, gap=principal_gap, lev=deal.leverage_loan,
        ))
    for msg in messages:
        warnings.warn(msg, LeverageShortfallWarning, stacklevel=2)

    return WaterfallResult(
        project_name=deal.project_name,
        years=years,
        total_interest_paid=total_ds * k,
        b_loan_forgiven=forgiven,
        exit_fee=deal.exit_fee,
        net_subsidy_at_unwind=forgiven - deal.exit_fee if forgiven is not None else None,
        avg_dscr=sum(dscrs) / len(dscrs) if dscrs else None,
        dscr_varies=dscr_varies,
        guarantee_fee_in_dscr=deal.include_guarantee_fee_in_dscr,
        dscr_refused_reason=(DSCR_REFUSED_ZERO_DS.format(
            fee="" if not deal.include_guarantee_fee_in_dscr else ", and the guarantee fee is 0")
            if schedule is not None and dscr_denominator <= 0 else None),
        noi_is_series=deal.noi_is_series,
        min_dscr=min(dscrs) if dscrs else None,
        unwind_year=k,
        in_recapture_period=statute.unwind_in_recapture_period(k),
        leverage_loan=deal.leverage_loan,
        annual_leverage_interest=lev_interest,
        annual_fund_qlici_interest=fund_qlici_interest,
        annual_fund_shortfall=annual_short,
        annual_fund_shortfall_a_only=max(0.0, lev_interest - a_interest),
        qlici_b_loan=deal.qlici_b_loan,
        basis={k: v.label() for k, v in deal.basis.items()},
        total_fund_shortfall=annual_short * k,
        leverage_principal_due=deal.leverage_loan,
        a_loan_principal_repaid=deal.qlici_a_loan,
        leverage_principal_gap=principal_gap,
        leverage_serviced=not messages,
        warning_messages=tuple(messages),
    )
