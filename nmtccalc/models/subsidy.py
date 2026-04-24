from dataclasses import dataclass
import pandas as pd

from nmtccalc.data.schema import NMTCDeal


@dataclass
class SubsidyResult:
    """Output object from NMTC net subsidy analysis."""
    project_name: str
    total_project_cost: float
    qei: float
    investor_equity: float
    cde_fee: float
    qlici_b_loan: float
    net_subsidy: float
    net_subsidy_pct: float
    effective_cost_of_capital: float
    interest_savings_7yr: float

    def summary(self) -> pd.DataFrame:
        rows = [
            ("Investor Equity (into fund)",  f"${self.investor_equity/1e6:.2f}MM"),
            ("Less: CDE Fee",                f"(${self.cde_fee/1e6:.2f}MM)"),
            ("B Loan to QALICB",             f"${self.qlici_b_loan/1e6:.2f}MM"),
            ("",                              ""),
            ("Net Subsidy (est. forgiven)",   f"${self.net_subsidy/1e6:.2f}MM"),
            ("Net Subsidy as % of Project",   f"{self.net_subsidy_pct*100:.1f}%"),
            ("",                              ""),
            ("Effective Cost of Capital",     f"{self.effective_cost_of_capital*100:.2f}%"),
            ("Interest Savings (7yr)",        f"${self.interest_savings_7yr/1e6:.2f}MM"),
        ]

        df = pd.DataFrame(rows, columns=["Item", "Value"])
        print(f"\nNet Subsidy Analysis — {self.project_name}")
        print("=" * 50)
        print(df.to_string(index=False))
        print()
        return df

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "net_subsidy": self.net_subsidy,
            "net_subsidy_pct": self.net_subsidy_pct,
            "effective_cost_of_capital": self.effective_cost_of_capital,
            "interest_savings_7yr": self.interest_savings_7yr,
        }


def analyze(deal: NMTCDeal) -> SubsidyResult:
    """
    Compute the net subsidy and effective cost of capital for the QALICB.

    The net subsidy is the B Loan amount that is typically forgiven
    via put/call at the end of the 7-year compliance period.
    This represents the real economic benefit to the project.

    Args:
        deal: NMTCDeal instance

    Returns:
        SubsidyResult with net subsidy and effective cost metrics
    """
    # Net subsidy: B Loan is typically forgiven at end of compliance period
    net_subsidy = deal.qlici_b_loan
    net_subsidy_pct = net_subsidy / deal.total_project_cost

    # Interest savings: difference between market rate and QLICI B loan rate
    # over the 7-year compliance period on the B loan principal
    market_rate = deal.leverage_loan_rate  # use leverage rate as market proxy
    interest_savings_7yr = deal.qlici_b_loan * (
        market_rate - deal.qlici_b_loan_rate
    ) * deal.compliance_years

    # Effective cost of capital: blended rate on total QLICI
    # weighted average of A and B loan rates by their principal amounts
    total_qlici = deal.qlici_total
    if total_qlici > 0:
        effective_cost_of_capital = (
            (deal.qlici_a_loan * deal.qlici_a_loan_rate) +
            (deal.qlici_b_loan * deal.qlici_b_loan_rate)
        ) / total_qlici
    else:
        effective_cost_of_capital = 0.0

    return SubsidyResult(
        project_name=deal.project_name,
        total_project_cost=deal.total_project_cost,
        qei=deal.qei,
        investor_equity=deal.investor_equity,
        cde_fee=deal.cde_fee,
        qlici_b_loan=deal.qlici_b_loan,
        net_subsidy=net_subsidy,
        net_subsidy_pct=net_subsidy_pct,
        effective_cost_of_capital=effective_cost_of_capital,
        interest_savings_7yr=interest_savings_7yr,
    )
