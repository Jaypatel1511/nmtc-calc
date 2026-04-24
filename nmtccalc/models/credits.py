from dataclasses import dataclass
import pandas as pd
import numpy as np

from nmtccalc.data.schema import NMTCDeal


@dataclass
class CreditScheduleResult:
    """Output object from NMTC 7-year credit schedule."""
    project_name: str
    qei: float
    total_nmtcs: float
    annual_credits: list
    cumulative_credits: list
    pv_credits: float
    discount_rate: float

    def summary(self) -> pd.DataFrame:
        rows = []
        for yr, (credit, cumulative) in enumerate(
            zip(self.annual_credits, self.cumulative_credits), 1
        ):
            rate = "5%" if yr <= 3 else "6%"
            rows.append({
                "Year": f"Y{yr}",
                "Credit Rate": rate,
                "Annual Credit ($)": f"${credit:,.0f}",
                "Cumulative ($)": f"${cumulative:,.0f}",
            })

        df = pd.DataFrame(rows)
        print(f"\n7-Year NMTC Credit Schedule — {self.project_name}")
        print(f"QEI: ${self.qei/1e6:.2f}MM  |  Total NMTCs: ${self.total_nmtcs/1e6:.2f}MM")
        print("-" * 60)
        print(df.to_string(index=False))
        print("-" * 60)
        print(f"  Total NMTCs:        ${self.total_nmtcs:,.0f}")
        print(f"  PV of Credits:      ${self.pv_credits:,.0f}  (@ {self.discount_rate*100:.1f}% discount rate)")
        print()
        return df

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "qei": self.qei,
            "total_nmtcs": self.total_nmtcs,
            "annual_credits": self.annual_credits,
            "cumulative_credits": self.cumulative_credits,
            "pv_credits": self.pv_credits,
            "discount_rate": self.discount_rate,
        }


def schedule(deal: NMTCDeal) -> CreditScheduleResult:
    """
    Generate the 7-year NMTC tax credit schedule.

    Credits are earned at:
    - 5% of QEI in years 1, 2, 3
    - 6% of QEI in years 4, 5, 6, 7
    Total: 39% of QEI

    Args:
        deal: NMTCDeal instance

    Returns:
        CreditScheduleResult with annual and cumulative credit schedule
    """
    annual_credits = []
    for yr in range(1, deal.compliance_years + 1):
        rate = 0.05 if yr <= 3 else 0.06
        annual_credits.append(deal.qei * rate)

    cumulative_credits = list(np.cumsum(annual_credits))

    # PV of credits discounted at deal.discount_rate
    pv_credits = sum(
        credit / ((1 + deal.discount_rate) ** yr)
        for yr, credit in enumerate(annual_credits, 1)
    )

    return CreditScheduleResult(
        project_name=deal.project_name,
        qei=deal.qei,
        total_nmtcs=deal.total_nmtcs,
        annual_credits=annual_credits,
        cumulative_credits=cumulative_credits,
        pv_credits=pv_credits,
        discount_rate=deal.discount_rate,
    )
