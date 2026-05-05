from dataclasses import dataclass
from typing import Optional
import pandas as pd

from nmtccalc.data.schema import NMTCDeal


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
    b_loan_forgiven: float = 0.0
    exit_fee: float = 0.0


@dataclass
class WaterfallResult:
    """Output object from NMTC cash flow waterfall analysis."""
    project_name: str
    years: list
    total_interest_paid: float
    b_loan_forgiven: float
    exit_fee: float
    net_year7_subsidy: float
    avg_dscr: Optional[float]
    min_dscr: Optional[float]

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
                "DSCR": f"{yr.dscr:.2f}x" if yr.dscr is not None else "—",
                "Net CF": f"${yr.net_cash_flow:,.0f}" if yr.net_cash_flow is not None else "—",
            })

        df = pd.DataFrame(rows)
        print(f"\nCash Flow Waterfall — {self.project_name}")
        print("=" * 80)
        print(df.to_string(index=False))
        print()
        print("Year 7 Unwind:")
        print(f"  B Loan Forgiven:  ${self.b_loan_forgiven:,.0f}")
        if self.exit_fee:
            print(f"  Exit Fee:         (${self.exit_fee:,.0f})")
        print(f"  Net Y7 Subsidy:   ${self.net_year7_subsidy:,.0f}")
        if self.avg_dscr is not None:
            print(f"\nDSCR:  Avg {self.avg_dscr:.2f}x  |  Min {self.min_dscr:.2f}x")
        print()
        return df

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "total_interest_paid": self.total_interest_paid,
            "b_loan_forgiven": self.b_loan_forgiven,
            "exit_fee": self.exit_fee,
            "net_year7_subsidy": self.net_year7_subsidy,
            "avg_dscr": self.avg_dscr,
            "min_dscr": self.min_dscr,
        }


def analyze(deal: NMTCDeal) -> WaterfallResult:
    """
    Generate the year-by-year NMTC cash flow waterfall.

    Models interest-only debt service on A and B loans during the 7-year
    compliance period, with the year-7 unwind (B loan forgiveness, exit fees,
    put/call exercise). DSCR is computed each year when noi is provided.

    Guarantee fees (if any) are shown as a separate line item below debt
    service — they reduce net cash flow but are excluded from the DSCR
    denominator, consistent with standard NMTC underwriting convention.

    Args:
        deal: NMTCDeal instance

    Returns:
        WaterfallResult with annual waterfall rows and Y7 unwind summary
    """
    a_interest = deal.qlici_a_loan * deal.qlici_a_loan_rate
    b_interest = deal.qlici_b_loan * deal.qlici_b_loan_rate
    total_ds = a_interest + b_interest
    guarantee_fee = deal.guarantee_fee_annual

    years = []
    for yr in range(1, deal.compliance_years + 1):
        dscr = (deal.noi / total_ds) if (deal.noi is not None and total_ds > 0) else None
        net_cf = (deal.noi - total_ds - guarantee_fee) if deal.noi is not None else None

        years.append(WaterfallYear(
            year=yr,
            noi=deal.noi,
            a_loan_interest=a_interest,
            b_loan_interest=b_interest,
            total_debt_service=total_ds,
            dscr=dscr,
            guarantee_fee=guarantee_fee,
            net_cash_flow=net_cf,
            b_loan_forgiven=deal.qlici_b_loan if yr == deal.compliance_years else 0.0,
            exit_fee=deal.exit_fee if yr == deal.compliance_years else 0.0,
        ))

    dscrs = [yr.dscr for yr in years if yr.dscr is not None]

    return WaterfallResult(
        project_name=deal.project_name,
        years=years,
        total_interest_paid=total_ds * deal.compliance_years,
        b_loan_forgiven=deal.qlici_b_loan,
        exit_fee=deal.exit_fee,
        net_year7_subsidy=deal.qlici_b_loan - deal.exit_fee,
        avg_dscr=sum(dscrs) / len(dscrs) if dscrs else None,
        min_dscr=min(dscrs) if dscrs else None,
    )
