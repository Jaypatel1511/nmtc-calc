from dataclasses import dataclass
import pandas as pd
import numpy as np

from nmtccalc.data.schema import NMTCDeal


@dataclass
class InvestorResult:
    """Output object from investor economics analysis."""
    project_name: str
    investor_equity: float
    annual_credits: list
    total_nmtcs: float
    credit_price: float
    gross_benefit: float
    net_benefit: float
    irr: float
    moic: float

    def summary(self) -> pd.DataFrame:
        rows = []
        for yr, credit in enumerate(self.annual_credits, 1):
            rows.append({
                "Year": f"Y{yr}",
                "Tax Credit ($)": f"${credit:,.0f}",
            })

        df = pd.DataFrame(rows)
        print(f"\nInvestor Economics — {self.project_name}")
        print(f"Equity In: ${self.investor_equity/1e6:.2f}MM  |  Credit Price: ${self.credit_price:.2f}/$1")
        print("-" * 50)
        print(df.to_string(index=False))
        print("-" * 50)
        print(f"  Total NMTCs:      ${self.total_nmtcs:,.0f}")
        print(f"  Gross Benefit:    ${self.gross_benefit:,.0f}")
        print(f"  Net Benefit:      ${self.net_benefit:,.0f}")
        print(f"  MOIC:             {self.moic:.2f}x")
        print(f"  IRR:              {self.irr*100:.1f}%")
        print()
        return df

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "investor_equity": self.investor_equity,
            "total_nmtcs": self.total_nmtcs,
            "credit_price": self.credit_price,
            "gross_benefit": self.gross_benefit,
            "net_benefit": self.net_benefit,
            "irr": self.irr,
            "moic": self.moic,
        }


def _compute_irr(cash_flows: list) -> float:
    """Compute IRR using numpy."""
    coeffs = cash_flows[::-1]
    try:
        roots = np.roots(coeffs)
        real_roots = [r.real for r in roots if abs(r.imag) < 1e-6 and r.real > 0]
        if not real_roots:
            return float("nan")
        irr = min(real_roots) - 1
        return irr
    except Exception:
        return float("nan")


def analyze(deal: NMTCDeal) -> InvestorResult:
    """
    Compute investor economics for an NMTC transaction.

    The investor puts in equity upfront and receives tax credits
    over the 7-year compliance period.

    Args:
        deal: NMTCDeal instance

    Returns:
        InvestorResult with IRR, MOIC, and credit schedule
    """
    from nmtccalc.models.credits import schedule

    credit_result = schedule(deal)
    annual_credits = credit_result.annual_credits

    gross_benefit = deal.total_nmtcs
    net_benefit = gross_benefit - deal.investor_equity

    # Cash flows: negative equity upfront, credits received each year
    cash_flows = [-deal.investor_equity] + annual_credits

    # IRR via numpy polynomial roots
    irr = _compute_irr(cash_flows)

    moic = sum(annual_credits) / deal.investor_equity

    return InvestorResult(
        project_name=deal.project_name,
        investor_equity=deal.investor_equity,
        annual_credits=annual_credits,
        total_nmtcs=deal.total_nmtcs,
        credit_price=deal.credit_price,
        gross_benefit=gross_benefit,
        net_benefit=net_benefit,
        irr=irr,
        moic=moic,
    )
